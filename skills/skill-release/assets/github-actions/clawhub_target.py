#!/usr/bin/env python3
"""Resolve an explicit ClawHub target and verify its remote ownership."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


HANDLE_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SKILL_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
SLUG_RULE = "3-96 lowercase kebab-case characters"
CLI_NOT_FOUND = "Skill not found or unavailable to this account."
RATE_LIMIT_DETAILS = re.compile(
    r"\((?:retry in \d+s(?:, remaining: \d+/\d+)?(?:, reset in \d+s)?"
    r"|remaining: \d+/\d+(?:, reset in \d+s)?"
    r"|reset in \d+s)\)"
)


class TargetError(ValueError):
    pass


@dataclass(frozen=True)
class Target:
    slug: str
    mode: str


def valid_handle(value: str) -> bool:
    normalized = value.strip().removeprefix("@")
    return 1 <= len(normalized) <= 64 and bool(HANDLE_PATTERN.fullmatch(normalized))


def valid_slug(value: str) -> bool:
    return 3 <= len(value) <= 96 and bool(SLUG_PATTERN.fullmatch(value))


def normalize_handle(value: str) -> str:
    return value.strip().removeprefix("@").lower()


def resolve_target(
    raw_targets: str,
    path: str,
    publisher: str,
    owner: str,
    auto_prefix: str | None = None,
) -> Target:
    try:
        targets = json.loads(raw_targets)
    except json.JSONDecodeError as exc:
        raise TargetError(f"CLAWHUB_TARGETS_JSON is invalid JSON: {exc}") from exc
    skill_path = PurePosixPath(path)
    if skill_path.is_absolute() or ".." in skill_path.parts:
        raise TargetError(f"invalid Skill path: {path!r}")
    if not valid_handle(publisher):
        raise TargetError("CLAWHUB_PUBLISHER must be a valid ClawHub publisher handle")
    if owner and (not valid_handle(owner) or normalize_handle(owner) != normalize_handle(publisher)):
        raise TargetError("CLAWHUB_OWNER must be empty or match CLAWHUB_PUBLISHER")

    if not isinstance(targets, dict):
        raise TargetError("CLAWHUB_TARGETS_JSON must be a JSON object")
    entry = targets.get(path)
    if entry is None and auto_prefix is not None:
        skill_path = PurePosixPath(path)
        if (
            skill_path.is_absolute()
            or len(skill_path.parts) != 2
            or skill_path.parts[0] != "skills"
            or not SKILL_NAME_PATTERN.fullmatch(skill_path.name)
            or (auto_prefix and not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*-", auto_prefix))
        ):
            raise TargetError(f"invalid automatic ClawHub path or slug prefix: {path!r}")
        slug = f"{auto_prefix}{skill_path.name}"
        if not valid_slug(slug):
            raise TargetError(f"generated ClawHub slug must be {SLUG_RULE}: {slug!r}")
        return Target(slug, "auto")
    if not isinstance(entry, dict):
        raise TargetError(f"add an explicit ClawHub target for {path!r}")

    slug, mode = entry.get("slug"), entry.get("mode")
    if not isinstance(slug, str) or not valid_slug(slug):
        raise TargetError(f"{path}: ClawHub slug must be {SLUG_RULE}")
    if mode not in {"new", "update"}:
        raise TargetError(f"{path}: ClawHub mode must be 'new' or 'update'")
    return Target(slug, mode)


def inspect_owner(payload: object) -> str:
    if not isinstance(payload, dict) or not isinstance(payload.get("owner"), dict):
        raise TargetError("ClawHub inspect returned no owner")
    handle = payload["owner"].get("handle")
    if not isinstance(handle, str) or not valid_handle(handle):
        raise TargetError("ClawHub inspect returned an invalid owner handle")
    return normalize_handle(handle)


def _split_known_rate_limit_note(line: str) -> tuple[str, str | None]:
    start = line.rfind(" (")
    if start == -1:
        return line, None
    note = line[start + 1 :]
    if RATE_LIMIT_DETAILS.fullmatch(note):
        return line[:start], note
    return line, None


def is_known_cli_not_found(error: str) -> bool:
    lines = [re.sub(r"\x1b\[[0-9;]*m", "", line).strip() for line in error.splitlines()]
    lines = [line for line in lines if line]
    if len(lines) != 2:
        return False
    first, first_note = _split_known_rate_limit_note(lines[0])
    second, second_note = _split_known_rate_limit_note(lines[1])
    return (
        first == CLI_NOT_FOUND
        and second == f"Error: {CLI_NOT_FOUND}"
        and first_note == second_note
    )


def validate_inspection(
    target: Target,
    publisher: str,
    status: int,
    payload: object | None,
    error: str,
    allow_atomic_create: bool = False,
) -> str:
    if status in {0, 200}:
        if (
            payload is None
            and target.mode in {"new", "auto"}
            and allow_atomic_create
            and is_known_cli_not_found(error)
        ):
            return "unverified"
        if payload is None:
            raise TargetError("ClawHub inspect returned no JSON payload")
        remote_owner = inspect_owner(payload)
        if target.mode == "auto" and remote_owner != normalize_handle(publisher):
            raise TargetError(
                f"ClawHub inspect found {target.slug!r} under {remote_owner!r}; "
                "publisher-scoped status could not be verified"
            )
        if target.mode == "new":
            raise TargetError(
                f"ClawHub slug {target.slug!r} already belongs to {remote_owner!r}; "
                "choose another slug or explicitly configure mode 'update'"
            )
        if remote_owner != normalize_handle(publisher):
            raise TargetError(
                f"ClawHub slug {target.slug!r} belongs to {remote_owner!r}, "
                f"not configured publisher {publisher!r}; choose another slug"
            )
        return "update"
    detail = error.strip() or f"inspect exited with status {status}"
    if (
        target.mode in {"new", "auto"}
        and allow_atomic_create
        and is_known_cli_not_found(detail)
    ):
        return "unverified"
    raise TargetError(f"cannot verify ownership of ClawHub slug {target.slug!r}: {detail}")


def verify_identity(payload: object, publisher: str, owner: str = "") -> str:
    if not isinstance(payload, dict) or not isinstance(payload.get("user"), dict):
        raise TargetError("ClawHub whoami returned no user")
    handle = payload["user"].get("handle")
    if not isinstance(handle, str) or not valid_handle(handle):
        raise TargetError("ClawHub whoami returned an invalid user handle")
    if owner and (
        not valid_handle(owner)
        or normalize_handle(owner) != normalize_handle(publisher)
    ):
        raise TargetError("CLAWHUB_OWNER must match CLAWHUB_PUBLISHER")
    if normalize_handle(handle) != normalize_handle(publisher) and not owner:
        raise TargetError(
            f"ClawHub token belongs to {handle!r}, not configured publisher {publisher!r}"
        )
    return normalize_handle(handle)


def verify_current_identity(publisher: str, owner: str = "") -> str:
    token = os.environ.get("CLAWHUB_TOKEN", "")
    if not token:
        raise TargetError("CLAWHUB_TOKEN is required to verify ClawHub identity")
    request = urllib.request.Request(
        "https://clawhub.ai/api/v1/whoami",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, UnicodeError, json.JSONDecodeError) as exc:
        raise TargetError("ClawHub whoami request failed") from exc
    return verify_identity(payload, publisher, owner)


def write_outputs(path: Path, target: Target, mode: str | None = None) -> None:
    with path.open("a", encoding="utf-8") as output:
        output.write(f"slug={target.slug}\n")
        output.write(f"mode={mode or target.mode}\n")


def assert_error(callable_, text: str) -> None:
    try:
        callable_()
    except TargetError as exc:
        assert text in str(exc), exc
        return
    raise AssertionError(f"expected error containing {text!r}")


def run_self_test() -> None:
    raw = json.dumps({"skills/my-skill": {"slug": "my-skill-mc", "mode": "new"}})
    target = resolve_target(raw, "skills/my-skill", "my-owner", "")
    assert target == Target("my-skill-mc", "new")
    assert resolve_target(raw, "skills/my-skill", "my-owner", "my-owner") == target
    automatic = resolve_target("{}", "skills/my-skill", "my-owner", "", "mc0571-")
    assert automatic == Target("mc0571-my-skill", "auto")
    bare_name = resolve_target("{}", "skills/my-skill", "my-owner", "", "")
    assert bare_name == Target("my-skill", "auto")
    long_skill_name = "a" + "b" * 63
    long_slug = resolve_target(
        "{}", f"skills/{long_skill_name}", "my-owner", "", "mc0571-"
    )
    assert long_slug == Target(f"mc0571-{long_skill_name}", "auto")
    assert len(long_slug.slug) == 71
    assert_error(
        lambda: resolve_target("{}", "skills/my-skill", "my-owner", "", "a" * 88 + "-"),
        "3-96 lowercase kebab-case characters",
    )
    assert_error(
        lambda: resolve_target(
            json.dumps({"skills/my-skill": {"slug": "a" * 97, "mode": "new"}}),
            "skills/my-skill",
            "my-owner",
            "",
        ),
        "3-96 lowercase kebab-case characters",
    )
    assert verify_identity({"user": {"handle": "my-owner"}}, "my-owner") == "my-owner"
    assert_error(lambda: verify_identity({"user": {"handle": "other"}}, "my-owner"), "not configured")
    assert verify_identity({"user": {"handle": "member"}}, "org-owner", "org-owner") == "member"
    assert valid_handle("@MC0571.org_team")
    assert normalize_handle("@MC0571.org_team") == "mc0571.org_team"
    assert resolve_target("{}", "skills/my-skill", "@MC0571", "MC0571", "mc0571-") == Target(
        "mc0571-my-skill", "auto"
    )
    assert_error(lambda: resolve_target("{}", "skills/my-skill", "my-owner", ""), "explicit")
    assert_error(lambda: resolve_target(raw, "skills/my-skill", "my-owner", "other"), "match")
    assert_error(lambda: validate_inspection(target, "my-owner", 1, None, "Skill not found"), "cannot verify ownership")
    assert validate_inspection(
        automatic,
        "my-owner",
        1,
        None,
        f"{CLI_NOT_FOUND}\nError: {CLI_NOT_FOUND}",
        allow_atomic_create=True,
    ) == "unverified"
    rate_limited_not_found = (
        "Skill not found or unavailable to this account. (reset in 15s)\n"
        "Error: Skill not found or unavailable to this account. (reset in 15s)"
    )
    assert is_known_cli_not_found(rate_limited_not_found)
    assert validate_inspection(
        automatic,
        "my-owner",
        1,
        None,
        rate_limited_not_found,
        allow_atomic_create=True,
    ) == "unverified"
    assert is_known_cli_not_found(
        f"{CLI_NOT_FOUND} (retry in 3s, remaining: 0/20, reset in 3s)\n"
        f"Error: {CLI_NOT_FOUND} (retry in 3s, remaining: 0/20, reset in 3s)"
    )
    assert not is_known_cli_not_found(
        f"{CLI_NOT_FOUND} (reset in 15s)\nError: {CLI_NOT_FOUND}"
    )
    assert not is_known_cli_not_found(
        f"{CLI_NOT_FOUND} (reset in 15s) extra\nError: {CLI_NOT_FOUND} (reset in 15s)"
    )
    assert_error(
        lambda: validate_inspection(
            automatic,
            "my-owner",
            0,
            {"owner": {"handle": "another-owner"}},
            "",
            allow_atomic_create=True,
        ),
        "publisher-scoped status",
    )
    assert_error(
        lambda: validate_inspection(automatic, "my-owner", 1, None, "HTTP 403", allow_atomic_create=True),
        "cannot verify ownership",
    )
    for unrelated_error in ("401 Unauthorized", "403 Forbidden", "429 Too Many Requests", "network timeout"):
        assert not is_known_cli_not_found(unrelated_error)
        assert_error(
            lambda unrelated_error=unrelated_error: validate_inspection(
                automatic,
                "my-owner",
                1,
                None,
                unrelated_error,
                allow_atomic_create=True,
            ),
            "cannot verify ownership",
        )
    assert_error(
        lambda: validate_inspection(target, "my-owner", 0, {"owner": {"handle": "other"}}, ""),
        "already belongs",
    )
    update = Target("my-skill-mc", "update")
    validate_inspection(update, "my-owner", 0, {"owner": {"handle": "my-owner"}}, "")
    assert_error(
        lambda: validate_inspection(update, "my-owner", 0, {"owner": {"handle": "other"}}, ""),
        "not configured publisher",
    )
    assert_error(lambda: validate_inspection(update, "my-owner", 1, None, "not found"), "cannot verify")
    assert_error(lambda: validate_inspection(target, "my-owner", 1, None, "timeout"), "cannot verify")
    print("ClawHub target self-test passed.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets-json", default="{}")
    parser.add_argument("--path")
    parser.add_argument("--publisher")
    parser.add_argument("--owner", default="")
    parser.add_argument("--auto-prefix")
    parser.add_argument("--allow-atomic-create", action="store_true")
    parser.add_argument("--verify-identity", action="store_true")
    parser.add_argument("--github-output", type=Path)
    parser.add_argument("--inspect-json", type=Path)
    parser.add_argument("--inspect-error", type=Path)
    parser.add_argument("--inspect-status", type=int)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    try:
        if args.self_test:
            run_self_test()
            return 0
        if not args.publisher:
            parser.error("--publisher is required")
        if args.verify_identity:
            print(json.dumps({"handle": verify_current_identity(args.publisher, args.owner)}))
            return 0
        if not args.path:
            parser.error("--path is required")
        target = resolve_target(
            args.targets_json, args.path, args.publisher, args.owner, args.auto_prefix
        )
        resolved_mode = target.mode
        if args.inspect_status is not None:
            if not args.inspect_json or not args.inspect_error:
                parser.error("--inspect-json and --inspect-error are required with --inspect-status")
            raw_payload = args.inspect_json.read_text(encoding="utf-8")
            payload = json.loads(raw_payload) if raw_payload.strip() else None
            error = args.inspect_error.read_text() if args.inspect_error else ""
            resolved_mode = validate_inspection(
                target,
                args.publisher,
                args.inspect_status,
                payload,
                error,
                args.allow_atomic_create,
            )
        if args.github_output:
            write_outputs(args.github_output, target, resolved_mode)
        print(json.dumps({"slug": target.slug, "mode": resolved_mode}))
        return 0
    except (TargetError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
