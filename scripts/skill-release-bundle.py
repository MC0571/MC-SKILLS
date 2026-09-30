#!/usr/bin/env python3
"""Stage a release bundle from tracked files in an exact Git tree."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path, PurePosixPath
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from repository_artifacts import (
    SEMVER_PATTERN,
    TreeEntry,
    blob_text,
    git_bytes,
    is_distributable,
    parse_skill_text,
    semver_key,
    snapshot,
    tracked_tree,
)


SKILL_PATH_PATTERN = re.compile(r"^skills/[a-z0-9][a-z0-9-]{0,63}$")
HEADING_PATTERN = re.compile(r"^#\s+(.+?)\s*#*\s*$")
FIELD_PATTERN = re.compile(r"^(slug|version|displayName)\s*:")


class BundleError(ValueError):
    pass


def superseding_main_version(repository: Path, ref: str, skill_path: str, target_version: str) -> str | None:
    if not SKILL_PATH_PATTERN.fullmatch(skill_path):
        raise BundleError(f"invalid Skill path for release ordering check: {skill_path!r}")
    if not SEMVER_PATTERN.fullmatch(target_version):
        raise BundleError(f"invalid target Skill version: {target_version!r}")
    skill = next(
        (
            artifact
            for artifact in snapshot(repository, ref)["artifacts"]
            if artifact["type"] == "skill" and artifact["path"] == skill_path
        ),
        None,
    )
    if skill is None:
        raise BundleError(f"{skill_path}: Skill is absent from {ref}; refusing to publish the older target")
    main_version = skill["version"]
    return main_version if semver_key(main_version) > semver_key(target_version) else None


def can_create_after_skillhub_404(event_name: str, run_attempt: str, scope: str = "changed") -> bool:
    return run_attempt == "1" and (
        event_name == "push" or (event_name == "workflow_dispatch" and scope == "all")
    )


def validate_skillhub_public_state(
    payload: object,
    publisher: str,
    namespace: str,
    slug: str,
    local_version: str,
) -> str:
    if not isinstance(payload, dict):
        raise BundleError("SkillHub returned no public Skill object")
    owner = payload.get("owner")
    owner_handle = owner.get("handle") if isinstance(owner, dict) else None
    if not isinstance(owner_handle, str) or owner_handle.casefold() != publisher.casefold():
        raise BundleError("visible SkillHub slug is owned by a different publisher")
    public_namespace = payload.get("namespace")
    namespace_handle = public_namespace.get("handle") if isinstance(public_namespace, dict) else None
    if not isinstance(namespace_handle, str) or namespace_handle.casefold() != namespace.casefold():
        raise BundleError("visible SkillHub slug is in a different namespace")
    public_slug = public_namespace.get("publicSlug") if isinstance(public_namespace, dict) else None
    if not isinstance(public_slug, str) or public_slug != slug:
        raise BundleError("SkillHub resolve returned a different public slug")
    latest = payload.get("latestVersion")
    latest_version = latest.get("version") if isinstance(latest, dict) else None
    if not isinstance(latest_version, str) or not SEMVER_PATTERN.fullmatch(latest_version):
        raise BundleError("SkillHub returned an invalid latestVersion.version")
    if not SEMVER_PATTERN.fullmatch(local_version):
        raise BundleError(f"local version is not valid SemVer: {local_version!r}")
    local_key, latest_key = semver_key(local_version), semver_key(latest_version)
    if local_key < latest_key:
        raise BundleError(f"local version {local_version} is below SkillHub latest {latest_version}")
    return "skip" if local_key == latest_key else "publish"


def select_skillhub_target(
    name: str,
    publisher: str,
    namespace: str,
    local_version: str,
    bare_payload: object | None,
    suffix_payload: object | None,
    exact_slug: str | None = None,
) -> dict:
    suffix = f"{name}-mc"
    if exact_slug is not None:
        if exact_slug not in {name, suffix}:
            raise BundleError("unsupported SkillHub slug selection")
        payload = bare_payload if exact_slug == name else suffix_payload
        status = (
            "unverified"
            if payload is None
            else validate_skillhub_public_state(payload, publisher, namespace, exact_slug, local_version)
        )
        return {"slug": exact_slug, "status": status, "fallbackEligible": False}
    if bare_payload is not None:
        status = validate_skillhub_public_state(bare_payload, publisher, namespace, name, local_version)
        return {"slug": name, "status": status, "fallbackEligible": False}
    if suffix_payload is not None:
        status = validate_skillhub_public_state(suffix_payload, publisher, namespace, suffix, local_version)
        return {"slug": suffix, "status": status, "fallbackEligible": False}
    return {"slug": name, "status": "unverified", "fallbackEligible": True}


def fetch_skillhub_coordinate(host: str, namespace: str, slug: str) -> dict | None:
    coordinate = f"@{namespace}/{slug}"
    url = f"{host.rstrip('/')}/api/v1/skills/resolve?{urlencode({'coordinate': coordinate})}"
    try:
        with urlopen(url, timeout=20) as response:
            body = response.read()
    except HTTPError as error:
        if error.code == 404:
            return None
        raise BundleError(f"SkillHub scoped resolve failed with HTTP {error.code}") from None
    except (URLError, TimeoutError) as error:
        raise BundleError(f"SkillHub scoped resolve failed: {type(error).__name__}") from None
    try:
        payload = json.loads(body)
    except (UnicodeError, ValueError, RecursionError) as error:
        raise BundleError("SkillHub scoped resolve returned invalid JSON") from None
    if not isinstance(payload, dict):
        raise BundleError("SkillHub scoped resolve returned no public Skill object")
    return payload


def resolve_skillhub_target(
    host: str,
    namespace: str,
    publisher: str,
    local_version: str,
    name: str,
    exact_slug: str | None = None,
) -> dict:
    if exact_slug is not None:
        payload = fetch_skillhub_coordinate(host, namespace, exact_slug)
        return select_skillhub_target(
            name, publisher, namespace, local_version,
            payload if exact_slug == name else None,
            payload if exact_slug == f"{name}-mc" else None,
            exact_slug,
        )
    bare_payload = fetch_skillhub_coordinate(host, namespace, name)
    if bare_payload is not None:
        return select_skillhub_target(
            name, publisher, namespace, local_version, bare_payload, None
        )
    suffix_payload = fetch_skillhub_coordinate(host, namespace, f"{name}-mc")
    return select_skillhub_target(
        name, publisher, namespace, local_version, None, suffix_payload
    )


def fallback_slug_is_unique(state: dict, skill_path: str) -> bool:
    skill = next(
        (
            artifact
            for artifact in state["artifacts"]
            if artifact["type"] == "skill" and artifact["path"] == skill_path
        ),
        None,
    )
    if skill is None:
        raise BundleError(f"{skill_path}: no standalone Skill exists in the release snapshot")
    fallback_name = f"{skill['name']}-mc"
    return not any(
        artifact["type"] == "skill"
        and artifact["path"] != skill_path
        and artifact["name"] == fallback_name
        for artifact in state["artifacts"]
    )


def is_skillhub_slug_occupancy_conflict(payload: object, publish_exit_code: int) -> bool:
    if publish_exit_code == 0 or not isinstance(payload, dict) or type(payload.get("status")) is not int:
        return False
    if payload["status"] != 409:
        return False
    body = payload.get("body")
    if not isinstance(body, dict):
        return False
    excluded = ("version", "版本", "pending", "review", "审核", "scan", "扫描")
    messages = [body[field].casefold() for field in ("error", "message") if isinstance(body.get(field), str)]
    combined = " ".join(messages)
    if any(term in combined for term in excluded) or re.search(
        r"\b(?:not|isn't|hasn't|never)\b|(?:未|不再|不被|没有|没被|并非|并未)", combined
    ):
        return False
    english = re.compile(
        r"\bslug(?:\s+['\"`]?[a-z0-9][a-z0-9-]{0,63}['\"`]?)?\s+"
        r"(?:(?:(?:is|has been)\s+)?already\s+(?:taken|occupied|in\s+use|exists)|"
        r"(?:(?:is|has been)\s+)?(?:taken|occupied|in\s+use|exists))\b"
    )
    chinese = re.compile(
        r"\bslug(?:\s+[a-z0-9][a-z0-9-]{0,63})?\s*"
        r"(?:已被其他用户占用|已被占用|被占用|已占用|已被使用|已存在)"
    )
    return any(english.search(message) or chinese.search(message) for message in messages)


def display_name(text: str, source: str) -> str:
    for line in text.splitlines():
        match = HEADING_PATTERN.fullmatch(line)
        if match:
            return match.group(1).strip()
    raise BundleError(f"{source}: add a top-level Markdown heading for Tencent displayName")


def tencent_frontmatter(text: str, source: str, name: str, version: str, slug: str) -> str:
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise BundleError(f"{source}: missing opening frontmatter delimiter")
    try:
        closing = lines.index("---", 1)
    except ValueError as exc:
        raise BundleError(f"{source}: missing closing frontmatter delimiter") from exc

    title = display_name("\n".join(lines[closing + 1 :]), source)
    values, _metadata, errors = parse_skill_text(text, source)
    if errors:
        raise BundleError(errors[0])
    if values.get("name") != name:
        raise BundleError(f"{source}: Skill name does not match its directory")
    if not SEMVER_PATTERN.fullmatch(version):
        raise BundleError(f"{source}: metadata.version is not valid SemVer")

    new_fields = {
        "slug": slug,
        "version": version,
        "displayName": title,
    }
    existing = {
        match.group(1): values.get(match.group(1))
        for line in lines[1:closing]
        if (match := FIELD_PATTERN.match(line))
    }
    for key, value in existing.items():
        expected = new_fields[key]
        if value not in {None, "", expected}:
            raise BundleError(f"{source}: top-level {key} conflicts with the derived release value")

    insertion = next(
        (index for index, line in enumerate(lines[1:closing], start=1) if line.startswith("metadata:")),
        closing,
    )
    for key, value in new_fields.items():
        rendered = f"{key}: {json.dumps(value, ensure_ascii=False)}"
        positions = [
            index
            for index, line in enumerate(lines[1:closing], start=1)
            if (match := FIELD_PATTERN.match(line)) and match.group(1) == key
        ]
        if positions:
            if len(positions) != 1 or lines[positions[0]].lstrip().startswith((f"{key}: |", f"{key}: >")):
                raise BundleError(f"{source}: unsupported top-level {key} formatting")
            lines[positions[0]] = rendered
        else:
            lines.insert(insertion, rendered)
            insertion += 1
            closing += 1
    return "\n".join(lines) + "\n"


def stage_skill(
    repository: Path,
    ref: str,
    skill_path: str,
    destination: Path,
    market: str,
    skillhub_slug: str = "name",
) -> dict:
    if market not in {"skillhub", "clawhub"}:
        raise BundleError("market must be 'skillhub' or 'clawhub'")
    if not SKILL_PATH_PATTERN.fullmatch(skill_path):
        raise BundleError(f"automatic release only accepts skills/<skill-name>: {skill_path!r}")

    state = snapshot(repository, ref)
    skill = next(
        (
            artifact
            for artifact in state["artifacts"]
            if artifact["type"] == "skill" and artifact["path"] == skill_path
        ),
        None,
    )
    if skill is None:
        raise BundleError(f"{skill_path}: no standalone Skill exists at {ref}")
    if skillhub_slug not in {"name", "name-mc"}:
        raise BundleError("--skillhub-slug must be 'name' or 'name-mc'")
    slug = skill["name"] if skillhub_slug == "name" else f"{skill['name']}-mc"
    if market == "skillhub" and skillhub_slug == "name-mc" and not fallback_slug_is_unique(state, skill_path):
        raise BundleError("SkillHub fallback slug collides with another standalone Skill name")

    entries = tracked_tree(repository, state["commit"])
    prefix = f"{skill_path}/"
    selected = [entry for entry in entries if entry.path.startswith(prefix)]
    if not selected:
        raise BundleError(f"{skill_path}: no tracked bundle files")
    files: list[tuple[TreeEntry, Path]] = []
    for entry in selected:
        if not is_distributable(entry.path):
            continue
        if entry.kind != "blob" or entry.mode not in {"100644", "100755"}:
            raise BundleError(f"{entry.path}: release bundles may contain only regular files")
        relative = PurePosixPath(entry.path).relative_to(PurePosixPath(skill_path))
        files.append((entry, Path(*relative.parts)))
    if not any(relative.as_posix() == "SKILL.md" for _, relative in files):
        raise BundleError(f"{skill_path}: tracked SKILL.md is missing")

    destination = destination.resolve()
    if destination.exists() and any(destination.iterdir()):
        raise BundleError(f"destination must be empty: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    skill_file = None
    for entry, relative in files:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        content = git_bytes(repository, "cat-file", "blob", entry.oid)
        if relative.as_posix() == "SKILL.md":
            source = content.decode("utf-8")
            if market == "skillhub":
                source = tencent_frontmatter(source, entry.path, skill["name"], skill["version"], slug)
            content = source.encode("utf-8")
            skill_file = target
        target.write_bytes(content)
        if entry.mode == "100755":
            target.chmod(0o755)
    source_text = skill_file.read_text(encoding="utf-8") if skill_file else ""
    if market == "clawhub":
        slug = skill["name"]
    return {
        "name": skill["name"],
        "path": skill_path,
        "version": skill["version"],
        "slug": slug,
        "displayName": display_name(source_text, f"{skill_path}/SKILL.md"),
        "directory": str(destination),
        "files": len(files),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref")
    parser.add_argument("--path")
    parser.add_argument("--market", choices=("skillhub", "clawhub"))
    parser.add_argument("--skillhub-slug", choices=("name", "name-mc"), default="name")
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--github-output", type=Path)
    parser.add_argument("--resolve-skillhub-target", action="store_true")
    parser.add_argument("--host")
    parser.add_argument("--namespace")
    parser.add_argument("--classify-skillhub-conflict", type=Path)
    parser.add_argument("--publish-exit-code", type=int)
    parser.add_argument("--check-current-skill", action="store_true")
    parser.add_argument("--check-skillhub-404", action="store_true")
    parser.add_argument("--event-name")
    parser.add_argument("--scope", choices=("changed", "all"), default="changed")
    parser.add_argument("--run-attempt")
    parser.add_argument("--publisher")
    parser.add_argument("--version")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    try:
        if args.self_test:
            run_self_test()
            return 0
        if args.resolve_skillhub_target:
            if not all((args.ref, args.path, args.host, args.namespace, args.publisher, args.version)):
                parser.error("--ref, --path, --host, --namespace, --publisher and --version are required with --resolve-skillhub-target")
            state = snapshot(Path.cwd(), args.ref)
            skill = next(
                (
                    artifact
                    for artifact in state["artifacts"]
                    if artifact["type"] == "skill" and artifact["path"] == args.path
                ),
                None,
            )
            if skill is None:
                raise BundleError(f"{args.path}: no standalone Skill exists at {args.ref}")
            exact_slug = None
            if args.skillhub_slug == "name-mc":
                exact_slug = f"{skill['name']}-mc"
            result = resolve_skillhub_target(
                args.host,
                args.namespace,
                args.publisher,
                args.version,
                skill["name"],
                exact_slug,
            )
            if result["slug"] == f"{skill['name']}-mc" and not fallback_slug_is_unique(
                state, args.path
            ):
                raise BundleError("SkillHub fallback slug collides with another standalone Skill name")
            print(json.dumps(result))
            return 0
        if args.classify_skillhub_conflict:
            if args.publish_exit_code is None:
                parser.error("--publish-exit-code is required with --classify-skillhub-conflict")
            try:
                payload = json.loads(args.classify_skillhub_conflict.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, ValueError, RecursionError):
                payload = None
            print(json.dumps({
                "slugConflict": is_skillhub_slug_occupancy_conflict(payload, args.publish_exit_code)
            }))
            return 0
        if args.check_current_skill:
            if not args.ref or not args.path or not args.version:
                parser.error("--ref, --path and --version are required with --check-current-skill")
            newer = superseding_main_version(Path.cwd(), args.ref, args.path, args.version)
            print(json.dumps({"status": "superseded" if newer else "current", "mainVersion": newer}))
            return 0
        if args.check_skillhub_404:
            if not args.event_name or not args.run_attempt:
                parser.error("--event-name and --run-attempt are required with --check-skillhub-404")
            if not can_create_after_skillhub_404(args.event_name, args.run_attempt, args.scope):
                raise BundleError("SkillHub public 404 may proceed only on the initial push or first-attempt all-scope run")
            print(json.dumps({"status": "unverified"}))
            return 0
        if not all((args.ref, args.path, args.market, args.destination)):
            parser.error("--ref, --path, --market and --destination are required")
        result = stage_skill(
            Path.cwd(), args.ref, args.path, args.destination, args.market, args.skillhub_slug
        )
        print(json.dumps(result, ensure_ascii=False))
        if args.github_output:
            with args.github_output.open("a", encoding="utf-8") as output:
                for key in ("name", "path", "version", "slug", "displayName", "directory", "files"):
                    output.write(f"{key}={result[key]}\n")
        return 0
    except (BundleError, OSError, UnicodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def run_self_test() -> None:
    from tempfile import TemporaryDirectory
    import subprocess
    import yaml
    from unittest.mock import patch

    class FakeResponse:
        def __init__(self, body: bytes):
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self) -> bytes:
            return self.body

    with patch.object(sys.modules[__name__], "urlopen", return_value=FakeResponse(b'{"ok":true}')):
        assert fetch_skillhub_coordinate("https://example.invalid", "ns", "name") == {"ok": True}
    with patch.object(
        sys.modules[__name__],
        "urlopen",
        side_effect=HTTPError("https://example.invalid", 404, "Not Found", None, None),
    ):
        assert fetch_skillhub_coordinate("https://example.invalid", "ns", "name") is None
    for invalid_json in (b"null", b"[]", b"42", b"not-json"):
        with patch.object(
            sys.modules[__name__], "urlopen", return_value=FakeResponse(invalid_json)
        ):
            try:
                fetch_skillhub_coordinate("https://example.invalid", "ns", "name")
            except BundleError:
                pass
            else:
                raise AssertionError(f"invalid SkillHub resolve response was accepted: {invalid_json!r}")

    result_filter = (
        Path(__file__).resolve().parents[1]
        / "skills/skill-release/assets/github-actions/skillhub_publish_result.txt"
    )

    def project_skillhub_result(raw: str, slug: str = "sample") -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                "jq",
                "-e",
                "--arg",
                "name",
                "sample",
                "--arg",
                "slug",
                slug,
                "--arg",
                "version",
                "1.2.3",
                "-f",
                str(result_filter),
            ],
            input=raw,
            check=False,
            capture_output=True,
            text=True,
        )

    pending_result = project_skillhub_result(
        '{"status":"pending_review","private":{"token":"secret"},"unknown":"discard"}'
    )
    assert pending_result.returncode == 0, pending_result.stderr
    projected = json.loads(pending_result.stdout)
    assert projected == {
        "name": "sample",
        "slug": "sample",
        "version": "1.2.3",
        "skillId": None,
        "status": "pending_review",
        "publicUrl": None,
    }, projected
    assert "secret" not in pending_result.stdout and "unknown" not in pending_result.stdout

    fallback_result = project_skillhub_result(
        '{"skillId":{"unexpected":"shape"},"publicUrl":["unexpected"],"token":"secret"}',
        slug="",
    )
    assert fallback_result.returncode == 0, fallback_result.stderr
    fallback = json.loads(fallback_result.stdout)
    assert fallback["status"] == "submitted", fallback
    assert fallback["skillId"] is None and fallback["publicUrl"] is None, fallback
    assert "slug" not in fallback, fallback
    assert "secret" not in fallback_result.stdout and "unexpected" not in fallback_result.stdout

    rejected_result = project_skillhub_result('{"success":false,"token":"secret"}')
    assert rejected_result.returncode != 0
    assert "success=false" in rejected_result.stderr
    assert "secret" not in rejected_result.stderr and "secret" not in rejected_result.stdout

    malformed_result = project_skillhub_result("not json")
    assert malformed_result.returncode != 0 and "parse error" in malformed_result.stderr
    assert "not json" not in malformed_result.stderr and "not json" not in malformed_result.stdout

    workflow_path = Path(__file__).resolve().parents[1] / ".github/workflows/skill-release.yml"
    workflow_text = workflow_path.read_text(encoding="utf-8")
    workflow = yaml.safe_load(workflow_text)
    refs_step = next(
        step for step in workflow["jobs"]["detect"]["steps"] if step.get("id") == "refs"
    )
    refs_script = refs_step["run"]
    current_sha = "a" * 40
    historical_sha = "c" * 40
    parent_sha = "b" * 40
    git_stub = """git() {
  case "$1" in
    fetch|merge-base) return 0 ;;
    rev-parse)
      case "$2" in
        "$FAKE_TARGET_SHA^{commit}") echo "$FAKE_TARGET_SHA" ;;
        origin/main) echo "$FAKE_CURRENT_SHA" ;;
        "$FAKE_CURRENT_SHA^") echo "$FAKE_PARENT_SHA" ;;
        *) return 1 ;;
      esac
      ;;
    *) return 1 ;;
  esac
}
"""
    with TemporaryDirectory() as temporary:
        for scope in ("changed", "all"):
            for selected_sha in (current_sha, historical_sha):
                output_path = Path(temporary) / f"{scope}-{selected_sha[:1]}.out"
                environment = {
                    **os.environ,
                    "EVENT_NAME": "workflow_dispatch",
                    "EVENT_REF": "refs/heads/main",
                    "INPUT_COMMIT_SHA": selected_sha,
                    "INPUT_SCOPE": scope,
                    "GITHUB_OUTPUT": str(output_path),
                    "FAKE_CURRENT_SHA": current_sha,
                    "FAKE_PARENT_SHA": parent_sha,
                    "FAKE_TARGET_SHA": selected_sha,
                }
                refs_result = subprocess.run(
                    ["bash"],
                    input=f"{git_stub}\n{refs_script}",
                    check=False,
                    capture_output=True,
                    text=True,
                    env=environment,
                )
                accepted = selected_sha == current_sha
                assert (refs_result.returncode == 0) is accepted, refs_result.stderr
                if accepted:
                    assert output_path.read_text(encoding="utf-8") == (
                        f"base_sha={parent_sha}\ntarget_sha={current_sha}\nscope={scope}\n"
                    )
                else:
                    assert "requires commit_sha to equal the current origin/main HEAD" in refs_result.stderr

    publish_step = next(
        step
        for step in workflow["jobs"]["tencent_publish"]["steps"]
        if step.get("name") == "Publish Skills to SkillHub"
    )
    publish_script = publish_step["run"]
    shell_check = subprocess.run(
        ["bash", "-n"], input=publish_script, check=False, capture_output=True, text=True
    )
    assert shell_check.returncode == 0, shell_check.stderr

    diagnostic_section = publish_script.split("# BEGIN SKILLHUB_PUBLISH_FAILURE_DIAGNOSTIC", 1)[1]
    diagnostic_section = diagnostic_section.split("# END SKILLHUB_PUBLISH_FAILURE_DIAGNOSTIC", 1)[0]
    diagnostic_body = diagnostic_section.split("<<'PY'", 1)[1].split("\n", 1)[1]
    diagnostic_program = diagnostic_body.split("\nPY\n", 1)[0]
    assert diagnostic_program.startswith("import json\n"), repr(diagnostic_program[:40])

    api_key = "test-skillhub-key"

    def run_publish_diagnostic(raw: str) -> subprocess.CompletedProcess[str]:
        with TemporaryDirectory() as temporary:
            raw_path = Path(temporary) / "publish-result.json"
            raw_path.write_text(raw, encoding="utf-8")
            environment = os.environ.copy()
            environment["SKILLHUB_KEY"] = api_key
            return subprocess.run(
                [sys.executable, "-c", diagnostic_program, str(raw_path)],
                check=False,
                capture_output=True,
                text=True,
                env=environment,
            )

    failed_response = json.dumps(
        {
            "status": 403,
            "body": {
                "code": "permission_denied",
                "error": f"request rejected for {api_key}\ncheck publisher",
                "token": api_key,
            },
            "unknown": {"secret": api_key},
        }
    )
    failure_process = run_publish_diagnostic(failed_response)
    assert failure_process.returncode == 0, failure_process.stderr
    assert "\n" not in failure_process.stdout.rstrip("\n"), failure_process.stdout
    failure = json.loads(failure_process.stdout.removeprefix("SkillHub publish failed: "))
    assert failure == {
        "message": "SkillHub publish failed",
        "httpStatus": 403,
        "code": "permission_denied",
        "error": "request rejected for [REDACTED]\ncheck publisher",
    }, failure
    assert api_key not in failure_process.stdout and "unknown" not in failure_process.stdout

    numeric_code_process = run_publish_diagnostic(json.dumps({"status": 409, "body": {"code": 409}}))
    numeric_code = json.loads(numeric_code_process.stdout.removeprefix("SkillHub publish failed: "))
    assert numeric_code["httpStatus"] == 409 and numeric_code["code"] == "409", numeric_code

    malformed_process = run_publish_diagnostic(f"CLI error: {api_key}")
    assert malformed_process.returncode == 0
    assert "not valid JSON" in malformed_process.stdout
    assert api_key not in malformed_process.stdout and "CLI error" not in malformed_process.stdout

    unsafe_fields_process = run_publish_diagnostic(
        json.dumps(
            {
                "status": True,
                "body": {"code": [api_key], "error": {"message": api_key}},
                "token": api_key,
            }
        )
    )
    unsafe_fields = json.loads(unsafe_fields_process.stdout.removeprefix("SkillHub publish failed: "))
    assert unsafe_fields == {
        "message": "SkillHub publish failed; CLI returned no safe structured error details"
    }, unsafe_fields
    assert api_key not in unsafe_fields_process.stdout

    bounded_process = run_publish_diagnostic(
        json.dumps(
            {
                "status": "502",
                "body": {"code": "c" * 200, "error": "x" * 395 + api_key + "e" * 800},
            }
        )
    )
    bounded = json.loads(bounded_process.stdout.removeprefix("SkillHub publish failed: "))
    assert len(bounded["code"]) == 80 and len(bounded["error"]) == 400, bounded
    assert "httpStatus" not in bounded, bounded
    assert bounded["error"] == "x" * 395 + "[REDA", bounded
    assert api_key not in bounded_process.stdout

    def git(repository: Path, *args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(repository), *args], check=True, stdout=subprocess.PIPE, text=True
        ).stdout.strip()

    def commit(repository: Path, message: str) -> str:
        git(repository, "add", "-A")
        git(repository, "commit", "-m", message)
        return git(repository, "rev-parse", "HEAD")

    with TemporaryDirectory() as temporary:
        repository = Path(temporary) / "repo"
        repository.mkdir()
        git(repository, "init", "-b", "main")
        git(repository, "config", "user.name", "bundle-self-test")
        git(repository, "config", "user.email", "bundle-self-test@example.invalid")
        source = repository / "skills" / "sample"
        source.mkdir(parents=True)
        (source / "SKILL.md").write_text(
            "---\nname: sample\ndescription: test\nmetadata:\n  version: 1.2.3\n---\n\n# Sample Display\n",
            encoding="utf-8",
        )
        filter_fixture = source / "assets" / "github-actions"
        filter_fixture.mkdir(parents=True)
        (filter_fixture / result_filter.name).write_text(
            result_filter.read_text(encoding="utf-8"), encoding="utf-8"
        )
        (source / "tool.py").write_text("print('ok')\n", encoding="utf-8")
        (source / ".DS_Store").write_text("ignored\n", encoding="utf-8")
        (source / "cache.pyc").write_bytes(b"ignored")
        cache = source / "__pycache__"
        cache.mkdir()
        (cache / "tool.pyc").write_bytes(b"ignored")
        (source / "target.txt").write_text("target\n", encoding="utf-8")
        os.symlink("target.txt", source / "link")
        with_symlink = commit(repository, "with symlink")
        try:
            stage_skill(repository, with_symlink, "skills/sample", Path(temporary) / "bad", "clawhub")
        except BundleError as exc:
            assert "regular files" in str(exc), exc
        else:
            raise AssertionError("tracked symlink was not rejected")
        (source / "link").unlink()
        clean = commit(repository, "remove symlink")
        assert superseding_main_version(repository, clean, "skills/sample", "1.2.2") == "1.2.3"
        assert superseding_main_version(repository, clean, "skills/sample", "1.2.3") is None
        try:
            superseding_main_version(repository, clean, "skills/removed", "1.2.3")
        except BundleError as exc:
            assert "absent" in str(exc), exc
        else:
            raise AssertionError("a missing main Skill was allowed to publish")
        (source / "untracked.txt").write_text("not in Git\n", encoding="utf-8")
        tencent = Path(temporary) / "tencent"
        result = stage_skill(repository, clean, "skills/sample", tencent, "skillhub")
        staged_text = (tencent / "SKILL.md").read_text(encoding="utf-8")
        assert 'slug: "sample"' in staged_text
        assert result["slug"] == "sample"
        assert 'version: "1.2.3"' in staged_text
        assert 'displayName: "Sample Display"' in staged_text
        assert "metadata:\n  version: 1.2.3" in staged_text
        assert result["files"] == 4 and not (tencent / "untracked.txt").exists()
        bundled_filter = tencent / "assets/github-actions/skillhub_publish_result.txt"
        assert bundled_filter.is_file()
        assert not bundled_filter.with_suffix(".jq").exists()
        assert not (tencent / ".DS_Store").exists() and not (tencent / "cache.pyc").exists()
        assert not (tencent / "__pycache__").exists()
        tencent_suffix = Path(temporary) / "tencent-suffix"
        suffix_result = stage_skill(
            repository, clean, "skills/sample", tencent_suffix, "skillhub", "name-mc"
        )
        assert suffix_result["slug"] == "sample-mc"
        assert 'slug: "sample-mc"' in (tencent_suffix / "SKILL.md").read_text(encoding="utf-8")
        clawhub = Path(temporary) / "clawhub"
        claw_bundle = stage_skill(repository, clean, "skills/sample", clawhub, "clawhub")
        assert claw_bundle["slug"] == "sample"
        claw_text = (clawhub / "SKILL.md").read_text(encoding="utf-8")
        assert "slug:" not in claw_text and "displayName:" not in claw_text
        assert "metadata:\n  version: 1.2.3" in claw_text
        for invalid in ("../skills/sample", "skills/sub/sample", "plugins/sample"):
            try:
                stage_skill(repository, clean, invalid, Path(temporary) / "invalid", "skillhub")
            except BundleError:
                pass
            else:
                raise AssertionError(f"invalid release path was accepted: {invalid}")
        collision = repository / "skills" / "sample-mc"
        collision.mkdir()
        (collision / "SKILL.md").write_text(
            "---\nname: sample-mc\ndescription: test\nmetadata:\n  version: 1.0.0\n---\n\n# Sample Variant\n",
            encoding="utf-8",
        )
        collision_ref = commit(repository, "add colliding skill")
        assert not fallback_slug_is_unique(snapshot(repository, collision_ref), "skills/sample")
        try:
            stage_skill(
                repository, collision_ref, "skills/sample", Path(temporary) / "collision",
                "skillhub", "name-mc",
            )
        except BundleError as exc:
            assert "collides" in str(exc), exc
        else:
            raise AssertionError("SkillHub fallback collision was allowed")
    public_state = {
        "owner": {"handle": "publisher"},
        "namespace": {"handle": "indiv-mc", "publicSlug": "sample"},
        "latestVersion": {"version": "1.2.2"},
    }
    assert validate_skillhub_public_state(
        public_state, "publisher", "indiv-mc", "sample", "1.2.3"
    ) == "publish"
    assert validate_skillhub_public_state(
        {**public_state, "latestVersion": {"version": "1.2.3"}},
        "publisher",
        "indiv-mc",
        "sample",
        "1.2.3",
    ) == "skip"
    suffix_state = {
        **public_state,
        "namespace": {"handle": "indiv-mc", "publicSlug": "sample-mc"},
        "latestVersion": {"version": "1.2.3"},
    }
    assert select_skillhub_target(
        "sample", "publisher", "indiv-mc", "1.2.3", None, suffix_state
    ) == {"slug": "sample-mc", "status": "skip", "fallbackEligible": False}
    assert select_skillhub_target(
        "sample", "publisher", "indiv-mc", "1.2.3", None, None, "sample-mc"
    ) == {"slug": "sample-mc", "status": "unverified", "fallbackEligible": False}
    assert select_skillhub_target(
        "sample", "publisher", "indiv-mc", "1.2.3", None, None
    ) == {"slug": "sample", "status": "unverified", "fallbackEligible": True}
    assert select_skillhub_target(
        "sample", "publisher", "indiv-mc", "1.2.3", public_state, suffix_state
    ) == {"slug": "sample", "status": "publish", "fallbackEligible": False}
    assert is_skillhub_slug_occupancy_conflict(
        {"status": 409, "body": {"error": "slug sample is already taken"}}, 1
    )
    assert is_skillhub_slug_occupancy_conflict(
        {"status": 409, "body": {"error": "slug 已被其他用户占用"}}, 1
    )
    assert not is_skillhub_slug_occupancy_conflict(
        {"status": 409, "body": {"error": "slug not taken"}}, 1
    )
    assert not is_skillhub_slug_occupancy_conflict(
        {
            "status": 409,
            "body": {"error": "slug sample is already taken", "message": "slug is not taken"},
        },
        1,
    )
    assert not is_skillhub_slug_occupancy_conflict(
        {
            "status": 409,
            "body": {"error": "slug is invalid", "message": "another item already exists"},
        },
        1,
    )
    assert not is_skillhub_slug_occupancy_conflict(
        {"status": 409, "body": {"error": "slug conflict"}}, 1
    )
    assert not is_skillhub_slug_occupancy_conflict(
        {"status": 409, "body": {"message": "slug already exists during version conflict"}}, 1
    )
    assert not is_skillhub_slug_occupancy_conflict(
        {
            "status": 409,
            "body": {"error": "slug sample is already taken", "message": "version is pending review"},
        },
        1,
    )
    assert not is_skillhub_slug_occupancy_conflict(
        {
            "status": 409,
            "body": {"error": "slug sample is already taken", "message": "security scan is running"},
        },
        1,
    )
    assert not is_skillhub_slug_occupancy_conflict(
        {
            "status": 409,
            "body": {"error": "slug sample is already taken", "message": "slug is under review"},
        },
        1,
    )
    assert not is_skillhub_slug_occupancy_conflict(
        {"status": 409, "body": {"error": "slug is occupied while pending review"}}, 1
    )
    assert not is_skillhub_slug_occupancy_conflict(
        {"status": 403, "body": {"error": "slug is already taken"}}, 1
    )
    assert not is_skillhub_slug_occupancy_conflict(
        {"status": 409, "body": {"error": "slug is already taken"}}, 0
    )
    for invalid_state, owner, namespace, slug, version in (
        (public_state, "another-publisher", "indiv-mc", "sample", "1.2.3"),
        (public_state, "publisher", "another-namespace", "sample", "1.2.3"),
        (public_state, "publisher", "indiv-mc", "other-slug", "1.2.3"),
        (public_state, "publisher", "indiv-mc", "sample", "1.2.1"),
        ({**public_state, "latestVersion": {}}, "publisher", "indiv-mc", "sample", "1.2.3"),
    ):
        try:
            validate_skillhub_public_state(invalid_state, owner, namespace, slug, version)
        except BundleError:
            pass
        else:
            raise AssertionError("invalid scoped public SkillHub state was accepted")
    assert can_create_after_skillhub_404("push", "1")
    assert not can_create_after_skillhub_404("push", "2")
    assert not can_create_after_skillhub_404("workflow_dispatch", "1")
    assert can_create_after_skillhub_404("workflow_dispatch", "1", "all")
    assert not can_create_after_skillhub_404("workflow_dispatch", "2", "all")
    assert not can_create_after_skillhub_404("workflow_dispatch", "1", "changed")
    print("Skill release bundle self-test passed.")


if __name__ == "__main__":
    raise SystemExit(main())
