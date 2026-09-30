#!/usr/bin/env python3
"""Build a GitHub Actions matrix for changed flat or one-level grouped Skills."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import yaml


ZERO_SHA = "0" * 40
SEMVER_NUMBER = r"(?:0|[1-9]\d*)"
SEMVER_PRERELEASE = rf"(?:{SEMVER_NUMBER}|\d*[A-Za-z-][0-9A-Za-z-]*)"
SEMVER_PATTERN = re.compile(
    rf"^{SEMVER_NUMBER}\.{SEMVER_NUMBER}\.{SEMVER_NUMBER}"
    rf"(?:-{SEMVER_PRERELEASE}(?:\.{SEMVER_PRERELEASE})*)?"
    rf"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
PATH_PART_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
IGNORED_PARTS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}


class DetectionError(ValueError):
    pass

@dataclass(frozen=True)
class TreeEntry:
    mode: str
    kind: str
    oid: str
    path: str


@dataclass(frozen=True)
class Skill:
    name: str
    version: str
    path: str
    digest: str
    has_top_level_version: bool


def git_bytes(repository: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(repository), *args],
        check=True,
        stdout=subprocess.PIPE,
    ).stdout


def resolve_commit(repository: Path, ref: str) -> str | None:
    if not ref or ref == ZERO_SHA:
        return None
    return git_bytes(repository, "rev-parse", "--verify", f"{ref}^{{commit}}").decode().strip()


def tracked_tree(repository: Path, commit: str | None) -> list[TreeEntry]:
    if commit is None:
        return []
    raw = git_bytes(repository, "ls-tree", "-rz", "--full-tree", commit)
    entries: list[TreeEntry] = []
    for item in raw.split(b"\0"):
        if not item:
            continue
        header, raw_path = item.split(b"\t", 1)
        mode, kind, oid = header.decode("ascii").split()
        entries.append(TreeEntry(mode, kind, oid, raw_path.decode("utf-8")))
    return entries


def validate_root(raw_root: str) -> str:
    root = PurePosixPath(raw_root)
    if root.is_absolute() or not root.parts or any(part in {"", ".", ".."} for part in root.parts):
        raise DetectionError(f"invalid Skill root: {raw_root!r}")
    return root.as_posix()


def blob_text(repository: Path, entry: TreeEntry) -> str:
    try:
        return git_bytes(repository, "cat-file", "blob", entry.oid).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DetectionError(f"{entry.path}: SKILL.md must be UTF-8") from exc


def frontmatter_versions(text: str, source: str) -> tuple[str, str | None, str | None]:
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise DetectionError(f"{source}: missing opening frontmatter delimiter")
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise DetectionError(f"{source}: missing closing frontmatter delimiter") from exc
    try:
        frontmatter = yaml.safe_load("\n".join(lines[1:end]))
    except yaml.YAMLError as exc:
        raise DetectionError(f"{source}: invalid YAML frontmatter: {exc}") from exc
    if frontmatter is None:
        frontmatter = {}
    if not isinstance(frontmatter, dict):
        raise DetectionError(f"{source}: frontmatter must be a YAML mapping")

    name = frontmatter.get("name", "")
    metadata = frontmatter.get("metadata")
    if metadata is None:
        metadata = {}
    if not isinstance(name, str):
        raise DetectionError(f"{source}: name must be a string")
    if not isinstance(metadata, dict):
        raise DetectionError(f"{source}: metadata must be a YAML mapping")
    top_version = frontmatter.get("version")
    metadata_version = metadata.get("version")
    if top_version is not None and not isinstance(top_version, str):
        raise DetectionError(f"{source}: version must be a string")
    if metadata_version is not None and not isinstance(metadata_version, str):
        raise DetectionError(f"{source}: metadata.version must be a string")
    return name, top_version, metadata_version


def resolve_version(source: str, top_version: str | None, metadata_version: str | None) -> str:
    if top_version and metadata_version and top_version != metadata_version:
        raise DetectionError(
            f"{source}: top-level version {top_version!r} does not match "
            f"metadata.version {metadata_version!r}"
        )
    version = top_version or metadata_version
    if not version or not SEMVER_PATTERN.fullmatch(version):
        raise DetectionError(f"{source}: set an explicit valid SemVer")
    return version


def validate_clawhub_latest(payload: dict, local_version: str) -> None:
    if not isinstance(payload, dict):
        raise DetectionError("ClawHub dry-run output must be a JSON object")
    latest = payload.get("latestVersion")
    if isinstance(latest, dict):
        latest = latest.get("version")
    if latest is None or latest == "":
        return
    if not isinstance(latest, str) or not SEMVER_PATTERN.fullmatch(latest):
        raise DetectionError("ClawHub dry-run returned an invalid latestVersion")
    if not SEMVER_PATTERN.fullmatch(local_version):
        raise DetectionError(f"local version is not valid SemVer: {local_version!r}")
    if semver_key(local_version) <= semver_key(latest):
        raise DetectionError(
            f"ClawHub latest version is {latest}, but local version is {local_version}; "
            "bump the version and rerun only the failed job"
        )


def semver_key(version: str) -> tuple:
    core, _, _build = version.partition("+")
    release, separator, prerelease = core.partition("-")
    pre = (
        (0, tuple((0, int(item)) if item.isdigit() else (1, item) for item in prerelease.split(".")))
        if separator
        else (1,)
    )
    return (*map(int, release.split(".")), pre)


def distributable(entry: TreeEntry, skill_path: str) -> bool:
    relative = PurePosixPath(entry.path).relative_to(PurePosixPath(skill_path))
    return not any(part in IGNORED_PARTS for part in relative.parts) and not entry.path.endswith(
        (".pyc", ".pyo", ".DS_Store")
    )


def skill_digest(repository: Path, entries: list[TreeEntry], skill_path: str) -> str:
    prefix = f"{skill_path}/"
    digest = hashlib.sha256(b"skill-release-v1\0")
    for entry in sorted(
        (item for item in entries if item.path.startswith(prefix) and distributable(item, skill_path)),
        key=lambda item: item.path,
    ):
        if entry.kind != "blob" or entry.mode == "120000":
            raise DetectionError(f"{entry.path}: Skill bundles may contain only regular files")
        relative = entry.path.removeprefix(prefix).encode("utf-8")
        content = git_bytes(repository, "cat-file", "blob", entry.oid)
        for value in (entry.mode.encode("ascii"), relative, content):
            digest.update(len(value).to_bytes(8, "big"))
            digest.update(value)
    return f"sha256:{digest.hexdigest()}"


def snapshot(repository: Path, commit: str | None, root: str) -> dict[str, Skill]:
    entries = tracked_tree(repository, commit)
    root_parts = PurePosixPath(root).parts
    skill_entries: list[TreeEntry] = []
    for entry in entries:
        parts = PurePosixPath(entry.path).parts
        if len(parts) <= len(root_parts) or parts[: len(root_parts)] != root_parts:
            continue
        if parts[-1] != "SKILL.md":
            continue
        relative_parts = parts[len(root_parts) :]
        if len(relative_parts) not in {2, 3}:
            raise DetectionError(
                f"{entry.path}: use {root}/<skill>/SKILL.md or "
                f"{root}/<collection>/<skill>/SKILL.md"
            )
        if any(not PATH_PART_PATTERN.fullmatch(part) for part in relative_parts[:-1]):
            raise DetectionError(f"{entry.path}: Skill path components must be safe kebab-case")
        skill_entries.append(entry)

    skill_paths = {PurePosixPath(entry.path).parent.as_posix() for entry in skill_entries}
    for skill_path in skill_paths:
        if any(other.startswith(f"{skill_path}/") for other in skill_paths):
            raise DetectionError(f"{skill_path}: a Skill directory cannot also be a collection")

    skills: dict[str, Skill] = {}
    paths: set[str] = set()
    for entry in skill_entries:
        skill_path = PurePosixPath(entry.path).parent.as_posix()
        if skill_path in paths:
            raise DetectionError(f"{skill_path}: duplicate SKILL.md")
        paths.add(skill_path)
        name, top_version, metadata_version = frontmatter_versions(
            blob_text(repository, entry), entry.path
        )
        if not name or name != PurePosixPath(skill_path).name:
            raise DetectionError(f"{entry.path}: name must match parent directory")
        if name in skills:
            raise DetectionError(f"{entry.path}: duplicate Skill name {name!r}")
        version = resolve_version(entry.path, top_version, metadata_version)
        skills[name] = Skill(
            name=name,
            version=version,
            path=skill_path,
            digest=skill_digest(repository, entries, skill_path),
            has_top_level_version=top_version is not None,
        )
    return skills


def matrix_item(skill: Skill, change: str) -> dict[str, str]:
    return {
        "name": skill.name,
        "path": skill.path,
        "version": skill.version,
        "change": change,
    }


def compare(
    repository: Path,
    root: str,
    base_ref: str,
    target_ref: str,
    require_top_level_version: bool = False,
) -> tuple[dict, list[str]]:
    normalized_root = validate_root(root)
    base_commit = resolve_commit(repository, base_ref)
    target_commit = resolve_commit(repository, target_ref)
    if target_commit is None:
        raise DetectionError("target ref must resolve to a commit")
    before = snapshot(repository, base_commit, normalized_root)
    after = snapshot(repository, target_commit, normalized_root)

    changed: list[dict[str, str]] = []
    errors: list[str] = []
    for name in sorted(after.keys() - before.keys()):
        if require_top_level_version and not after[name].has_top_level_version:
            errors.append(f"{after[name].path}: Tencent SkillHub requires top-level version")
            continue
        changed.append(matrix_item(after[name], "added"))
    for name in sorted(before.keys() - after.keys()):
        errors.append(f"removed Skill requires manual handling: {before[name].path}")
    for name in sorted(before.keys() & after.keys()):
        old, new = before[name], after[name]
        if old.path != new.path:
            errors.append(f"moved Skill requires manual handling: {old.path} -> {new.path}")
            continue
        if old.digest == new.digest:
            continue
        if require_top_level_version and not new.has_top_level_version:
            errors.append(f"{new.path}: Tencent SkillHub requires top-level version")
            continue
        if semver_key(new.version) <= semver_key(old.version):
            errors.append(
                f"{new.path}: bump version above {old.version}; distributable content changed"
            )
            continue
        changed.append(matrix_item(new, "updated"))

    result = {
        "schema_version": 1,
        "base_commit": base_commit,
        "target_commit": target_commit,
        "matrix": {"include": changed},
        "removed": [
            {key: getattr(before[name], key) for key in ("name", "version", "path", "digest")}
            for name in sorted(before.keys() - after.keys())
        ],
    }
    return result, errors


def write_github_outputs(path: Path, result: dict) -> None:
    matrix = json.dumps(result["matrix"], ensure_ascii=False, separators=(",", ":"))
    with path.open("a", encoding="utf-8") as output:
        output.write(f"matrix={matrix}\n")
        output.write(f"has_changes={'true' if result['matrix']['include'] else 'false'}\n")
        output.write(f"count={len(result['matrix']['include'])}\n")


def run_git(repository: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repository), *args],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    ).stdout.strip()


def write_skill(
    repository: Path,
    relative: str,
    version: str = "1.0.0",
    *,
    top_version: str | None = None,
    metadata_version: str | None = None,
    body: str = "test\n",
) -> None:
    path = repository / relative / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    top = version if top_version is None else top_version
    metadata = version if metadata_version is None else metadata_version
    lines = ["---", f"name: {path.parent.name}", "description: Test Skill"]
    if top:
        lines.append(f'version: "{top}"')
    if metadata:
        lines.extend(("metadata:", f'  version: "{metadata}"'))
    lines.extend(("---", "", body))
    path.write_text("\n".join(lines), encoding="utf-8")


def commit(repository: Path, message: str) -> str:
    run_git(repository, "add", "-A")
    run_git(repository, "commit", "--allow-empty", "-m", message)
    return run_git(repository, "rev-parse", "HEAD")


def assert_error(callable_, pattern: str) -> None:
    try:
        result = callable_()
    except DetectionError as exc:
        if pattern not in str(exc):
            raise AssertionError(f"expected {pattern!r} in {exc!r}") from exc
        return
    if isinstance(result, tuple) and any(pattern in error for error in result[1]):
        return
    raise AssertionError(f"expected error containing {pattern!r}")


def initialize_test_repository(path: Path) -> None:
    run_git(path, "init", "-q")
    run_git(path, "config", "user.name", "Skill Release Test")
    run_git(path, "config", "user.email", "skill-release@example.invalid")


def test_change_detection() -> None:
    with tempfile.TemporaryDirectory() as raw_directory:
        repository = Path(raw_directory)
        initialize_test_repository(repository)
        write_skill(repository, "skills/flat")
        write_skill(repository, "skills/dev/nested-skill")
        write_skill(repository, "skills/claw-only", top_version="")
        first = commit(repository, "add skills")

        result, errors = compare(repository, "skills", ZERO_SHA, first)
        paths = [item["path"] for item in result["matrix"]["include"]]
        assert not errors and paths == ["skills/claw-only", "skills/flat", "skills/dev/nested-skill"]
        result, errors = compare(repository, "skills", first, first, True)
        assert not errors and not result["matrix"]["include"]

        (repository / "README.md").write_text("unrelated\n", encoding="utf-8")
        unrelated = commit(repository, "unrelated")
        result, errors = compare(repository, "skills", first, unrelated, True)
        assert not errors and not result["matrix"]["include"]

        write_skill(repository, "skills/dev/nested-skill", "1.1.0", body="updated\n")
        nested_update = commit(repository, "update nested")
        result, errors = compare(repository, "skills", unrelated, nested_update, True)
        assert not errors and result["matrix"]["include"] == [
            {"name": "nested-skill", "path": "skills/dev/nested-skill", "version": "1.1.0", "change": "updated"}
        ]

        write_skill(repository, "skills/flat", "1.1.0", body="updated\n")
        write_skill(repository, "skills/dev/nested-skill", "1.2.0", body="updated again\n")
        multiple = commit(repository, "update multiple")
        result, errors = compare(repository, "skills", nested_update, multiple, True)
        assert not errors and len(result["matrix"]["include"]) == 2

        write_skill(repository, "skills/flat", "1.1.0", body="missing bump\n")
        missing_bump = commit(repository, "missing bump")
        assert_error(lambda: compare(repository, "skills", multiple, missing_bump, True), "bump")

        write_skill(repository, "skills/flat", top_version="1.2.0", metadata_version="1.3.0")
        conflict = commit(repository, "version conflict")
        assert_error(lambda: compare(repository, "skills", missing_bump, conflict, True), "does not match")


def test_changed_top_level_requirement() -> None:
    with tempfile.TemporaryDirectory() as raw_directory:
        repository = Path(raw_directory)
        initialize_test_repository(repository)
        write_skill(repository, "skills/claw-only", top_version="")
        before = commit(repository, "add metadata-only skill")
        write_skill(repository, "skills/claw-only", "1.1.0", top_version="", body="updated\n")
        after = commit(repository, "update metadata-only skill")
        assert_error(lambda: compare(repository, "skills", before, after, True), "top-level")


def test_destructive_changes() -> None:
    with tempfile.TemporaryDirectory() as raw_directory:
        repository = Path(raw_directory)
        initialize_test_repository(repository)
        write_skill(repository, "skills/dev/moved")
        write_skill(repository, "skills/flat")
        before_delete = commit(repository, "before delete")
        run_git(repository, "rm", "-r", "skills/flat")
        before_move = commit(repository, "remove flat")
        assert_error(lambda: compare(repository, "skills", before_delete, before_move), "removed Skill")
        (repository / "skills/design").mkdir(parents=True)
        (repository / "skills/dev/moved").rename(repository / "skills/design/moved")
        after_move = commit(repository, "move")
        assert_error(lambda: compare(repository, "skills", before_move, after_move), "moved Skill")

        os.symlink("SKILL.md", repository / "skills/design/moved/link")
        symlink_commit = commit(repository, "symlink")
        assert_error(lambda: compare(repository, "skills", after_move, symlink_commit), "regular files")
        assert_error(lambda: compare(repository, "../skills", before_move, after_move), "invalid Skill root")


def run_self_test() -> None:
    block = "---\nname: block\nmetadata:\n  version: 1.0.0\n---\n"
    flow = "---\nname: flow\nmetadata: {version: 1.0.0}\n---\n"
    assert frontmatter_versions(block, "block") == ("block", None, "1.0.0")
    assert frontmatter_versions(flow, "flow") == ("flow", None, "1.0.0")
    assert_error(lambda: resolve_version("SKILL.md", None, None), "valid SemVer")
    validate_clawhub_latest({}, "1.0.0")
    validate_clawhub_latest({"latestVersion": "0.9.0"}, "1.0.0")
    assert_error(lambda: validate_clawhub_latest({"latestVersion": "1.0.0"}, "1.0.0"), "bump")
    assert_error(lambda: validate_clawhub_latest({"latestVersion": "1.1.0"}, "1.0.0"), "bump")
    test_change_detection()
    test_changed_top_level_requirement()
    test_destructive_changes()
    print("Changed Skill detector self-test passed.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="skills", help="repository-relative Skill root")
    parser.add_argument("--base", help="base Git ref; all-zero SHA means an empty tree")
    parser.add_argument("--target", default="HEAD", help="target Git ref")
    parser.add_argument("--github-output", type=Path, help="append matrix outputs for GitHub Actions")
    parser.add_argument(
        "--require-top-level-version",
        action="store_true",
        help="require Tencent SkillHub's top-level version on added or updated Skills",
    )
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    try:
        if args.self_test:
            run_self_test()
            return 0
        if not args.base:
            parser.error("--base is required unless --self-test is used")
        result, errors = compare(
            Path.cwd(), args.root, args.base, args.target, args.require_top_level_version
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.github_output:
            write_github_outputs(args.github_output, result)
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return bool(errors)
    except (DetectionError, OSError, UnicodeError, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
if __name__ == "__main__":
    raise SystemExit(main())
