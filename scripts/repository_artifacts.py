#!/usr/bin/env python3
"""Read artifact versions from Git trees for repository validation."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


SEMVER_NUMBER = r"(?:0|[1-9]\d*)"
SEMVER_PRERELEASE = rf"(?:{SEMVER_NUMBER}|\d*[A-Za-z-][0-9A-Za-z-]*)"
SEMVER_PATTERN = re.compile(
    rf"^{SEMVER_NUMBER}\.{SEMVER_NUMBER}\.{SEMVER_NUMBER}"
    rf"(?:-{SEMVER_PRERELEASE}(?:\.{SEMVER_PRERELEASE})*)?"
    rf"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
CACHE_PARTS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}


@dataclass(frozen=True)
class TreeEntry:
    mode: str
    kind: str
    oid: str
    path: str


@dataclass(frozen=True)
class Artifact:
    kind: str
    name: str
    version: str
    path: str
    digest: str
    category: str | None = None
    harnesses: tuple[str, ...] = ()

    @property
    def identity(self) -> str:
        return f"{self.kind}:{self.name}"

    def as_dict(self) -> dict:
        result = {
            "type": self.kind,
            "name": self.name,
            "version": self.version,
            "path": self.path,
            "digest": self.digest,
        }
        if self.category:
            result["category"] = self.category
        if self.harnesses:
            result["harnesses"] = list(self.harnesses)
        return result


def failure(path: str | Path, rule: str, fix: str) -> str:
    return f"{Path(path).as_posix()}: [{rule}] {fix}"


def scalar(value: str) -> str | bool:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    if value == "true":
        return True
    if value == "false":
        return False
    return value


def parse_skill_text(text: str, source: str) -> tuple[dict, dict, list[str]]:
    if not text.startswith("---\n"):
        return {}, {}, [failure(source, "skill-frontmatter", "add opening `---`")]
    end = text.find("\n---", 4)
    if end == -1:
        return {}, {}, [failure(source, "skill-frontmatter", "close frontmatter with `---`")]

    values: dict[str, str | bool] = {}
    metadata: dict[str, str | bool] = {}
    in_metadata = False
    for raw_line in text[4:end].splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#") or ":" not in raw_line:
            continue
        key, raw_value = raw_line.split(":", 1)
        if raw_line[:1].isspace():
            if in_metadata:
                metadata[key.strip()] = scalar(raw_value)
            continue
        in_metadata = key.strip() == "metadata"
        values[key.strip()] = scalar(raw_value)
    return values, metadata, []


def semver_key(version: str) -> tuple:
    core, _, _build = version.partition("+")
    release, separator, prerelease = core.partition("-")
    pre = (
        (0, tuple((0, int(item)) if item.isdigit() else (1, item) for item in prerelease.split(".")))
        if separator
        else (1,)
    )
    return (*map(int, release.split(".")), pre)


def git_output(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    ).stdout


def git_bytes(root: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        stdout=subprocess.PIPE,
    ).stdout


def resolve_commit(root: Path, ref: str) -> str:
    return git_output(root, "rev-parse", "--verify", f"{ref}^{{commit}}").strip()


def tracked_tree(root: Path, commit: str) -> list[TreeEntry]:
    raw = git_bytes(root, "ls-tree", "-rz", "--full-tree", commit)
    entries: list[TreeEntry] = []
    for item in raw.split(b"\0"):
        if not item:
            continue
        header, path = item.split(b"\t", 1)
        mode, kind, oid = header.decode("ascii").split()
        entries.append(TreeEntry(mode, kind, oid, path.decode("utf-8")))
    return entries


def blob_text(root: Path, entry: TreeEntry) -> str:
    return git_bytes(root, "cat-file", "blob", entry.oid).decode("utf-8")


def is_distributable(path: str) -> bool:
    parts = Path(path).parts
    return (
        not any(part in CACHE_PARTS for part in parts)
        and not path.endswith((".pyc", ".pyo", ".DS_Store"))
    )


def framed(digest, value: bytes) -> None:
    digest.update(len(value).to_bytes(8, "big"))
    digest.update(value)


def artifact_digest(root: Path, entries: list[TreeEntry], artifact_path: str) -> str:
    digest = hashlib.sha256(b"mc-skills-artifact-v1\0")
    prefix = f"{artifact_path}/"
    artifact_entries = sorted(
        (
            entry
            for entry in entries
            if entry.path.startswith(prefix) and is_distributable(entry.path)
        ),
        key=lambda entry: entry.path,
    )
    for entry in artifact_entries:
        if entry.kind != "blob":
            raise ValueError(f"{entry.path}: artifact trees cannot contain {entry.kind}")
        relative = entry.path.removeprefix(prefix)
        for value in (
            entry.mode.encode("ascii"),
            entry.kind.encode("ascii"),
            relative.encode("utf-8"),
            git_bytes(root, "cat-file", "blob", entry.oid),
        ):
            framed(digest, value)
    return f"sha256:{digest.hexdigest()}"


def parse_skill(entry: TreeEntry, root: Path, entries: list[TreeEntry]) -> Artifact:
    values, metadata, errors = parse_skill_text(blob_text(root, entry), entry.path)
    if errors:
        raise ValueError(errors[0])
    name, version = values.get("name"), metadata.get("version")
    if not isinstance(name, str) or not name:
        raise ValueError(f"{entry.path}: missing skill name")
    if name != Path(entry.path).parent.name:
        raise ValueError(f"{entry.path}: skill name must match its directory")
    if not isinstance(version, str) or not SEMVER_PATTERN.fullmatch(version):
        raise ValueError(f"{entry.path}: invalid skill SemVer")
    artifact_path = str(Path(entry.path).parent)
    return Artifact(
        "skill",
        name,
        version,
        artifact_path,
        artifact_digest(root, entries, artifact_path),
        metadata.get("category") if isinstance(metadata.get("category"), str) else None,
    )


def parse_plugin(
    plugin_path: str,
    manifests: dict[str, TreeEntry],
    root: Path,
    entries: list[TreeEntry],
) -> Artifact:
    parsed = {
        harness: json.loads(blob_text(root, entry))
        for harness, entry in sorted(manifests.items())
    }
    if set(parsed) != {"Claude Code", "Codex"}:
        raise ValueError(f"{plugin_path}: both Codex and Claude Code manifests are required")
    names = {manifest.get("name") for manifest in parsed.values()}
    versions = {manifest.get("version") for manifest in parsed.values()}
    if len(names) != 1 or len(versions) != 1:
        raise ValueError(f"{plugin_path}: plugin manifest name/version drift")
    name, version = names.pop(), versions.pop()
    if not isinstance(name, str) or not name:
        raise ValueError(f"{plugin_path}: missing plugin name")
    if name != Path(plugin_path).name:
        raise ValueError(f"{plugin_path}: plugin name must match its directory")
    if not isinstance(version, str) or not SEMVER_PATTERN.fullmatch(version):
        raise ValueError(f"{plugin_path}: invalid plugin SemVer")
    return Artifact(
        "plugin",
        name,
        version,
        plugin_path,
        artifact_digest(root, entries, plugin_path),
        harnesses=tuple(sorted(parsed)),
    )


def snapshot(root: Path, ref: str) -> dict:
    commit = resolve_commit(root, ref)
    entries = tracked_tree(root, commit)
    artifacts: list[Artifact] = []
    plugin_manifests: dict[str, dict[str, TreeEntry]] = {}
    for entry in entries:
        parts = Path(entry.path).parts
        # Historical base refs still contain skills/<category>/<skill>/SKILL.md.
        if entry.path.endswith("/SKILL.md") and parts[0] == "skills" and len(parts) in {3, 4}:
            artifacts.append(parse_skill(entry, root, entries))
        if len(parts) == 4 and parts[0] == "plugins" and parts[-1] == "plugin.json":
            harness = {
                ".codex-plugin": "Codex",
                ".claude-plugin": "Claude Code",
            }.get(parts[-2])
            if harness:
                plugin_path = str(Path(*parts[:2]))
                plugin_manifests.setdefault(plugin_path, {})[harness] = entry
    for plugin_path, manifests in plugin_manifests.items():
        artifacts.append(parse_plugin(plugin_path, manifests, root, entries))
    artifacts.sort(key=lambda artifact: (artifact.kind, artifact.name))
    identities = [artifact.identity for artifact in artifacts]
    if len(identities) != len(set(identities)):
        raise ValueError("duplicate artifact identity")
    return {
        "schema_version": 1,
        "commit": commit,
        "artifacts": [artifact.as_dict() for artifact in artifacts],
    }


def artifact_versions_at_ref(root: Path, ref: str) -> dict[str, tuple[str, str]]:
    return {
        f"{item['type']}:{item['name']}": (item["path"], item["version"])
        for item in snapshot(root, ref)["artifacts"]
    }


def version_bump_errors(
    current: dict[str, tuple[str, str]],
    previous: dict[str, tuple[str, str | None]],
    changed_paths: set[str],
) -> list[str]:
    errors: list[str] = []
    for identity, (path, version) in current.items():
        if identity not in previous:
            continue
        old_path, old_version = previous[identity]
        changed = any(
            candidate == prefix or candidate.startswith(f"{prefix}/")
            for candidate in changed_paths
            for prefix in {path, old_path}
        )
        if changed and old_version and semver_key(version) <= semver_key(old_version):
            errors.append(
                failure(
                    path,
                    "artifact-version-bump",
                    f"bump {identity} above {old_version}; its distributable files changed",
                )
            )
    return errors
