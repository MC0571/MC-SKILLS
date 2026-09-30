#!/usr/bin/env python3
"""Validate repository structure, distribution metadata and artifact versions."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from repository_artifacts import (
    SEMVER_PATTERN,
    artifact_versions_at_ref,
    failure,
    git_output,
    parse_skill_text,
    version_bump_errors,
)
from repository_skills import SKILL_CATEGORIES, validate_npx_readmes
from repository_plugin_components import load_json, valid_hooks, validate_component_path
from repository_validator_selfcheck import run_self_test


ROOT = Path(__file__).resolve().parents[1]
MARKETPLACE_ID = "mc-agent-kit"
SHARED_PLUGIN_FIELDS = (
    "name", "version", "description", "author", "license", "keywords", "skills", "mcpServers"
)
CODE_ATLAS_NAME = "code-atlas"
CODE_ATLAS_HOOKS = "./hooks/claude-codex-hooks.json"
CODE_ATLAS_HOOK_FILE = "hooks/claude-codex-hooks.json"
CODE_ATLAS_RUNNER = 'node "${CLAUDE_PLUGIN_ROOT}/scripts/code-atlas-hook.js"'
CODE_ATLAS_INTERNAL_TIMEOUT_SECONDS = 18
CODE_ATLAS_HOOK_TIMEOUT_SECONDS = 30
CODE_ATLAS_LIFECYCLE_DESCRIPTION_MARKERS = (
    "analysis",
    ".codegraph",
    ".gitignore",
)
CODE_ATLAS_SKILL_FILES = (
    "skills/code-atlas/agents/openai.yaml",
    "skills/code-atlas/assets/config.example.yml",
    "skills/code-atlas/assets/decision-report.schema.json",
    "skills/code-atlas/assets/evidence-pack.schema.json",
    "skills/code-atlas/references/change-analysis.md",
    "skills/code-atlas/references/codegraph.md",
    "skills/code-atlas/references/dead-code.md",
    "skills/code-atlas/references/exploration.md",
    "skills/code-atlas/references/maintainability.md",
    "skills/code-atlas/references/test-selection.md",
    "skills/code-atlas/references/trace-and-debug.md",
    "skills/code-atlas/scripts/build-evidence-pack.py",
    "skills/code-atlas/scripts/scan-dependencies.py",
    "skills/code-atlas/scripts/scan-duplication.py",
    "skills/code-atlas/scripts/scan-git-churn.py",
    "skills/code-atlas/scripts/scan-literals-comments.py",
    "skills/code-atlas/scripts/scan-size-complexity.py",
    "skills/code-atlas/scripts/scan-tests.py",
)
CODE_ATLAS_SCHEMAS = (
    "skills/code-atlas/assets/decision-report.schema.json",
    "skills/code-atlas/assets/evidence-pack.schema.json",
)

def parse_skill(path: Path, root: Path) -> tuple[dict, dict, list[str]]:
    return parse_skill_text(path.read_text(encoding="utf-8"), path.relative_to(root).as_posix())

def validate_skills(root: Path) -> tuple[dict[str, tuple[str, str]], list[str]]:
    skills_root = root / "skills"
    artifacts: dict[str, tuple[str, str]] = {}
    seen: dict[str, str] = {}
    errors: list[str] = []
    for path in sorted(skills_root.rglob("SKILL.md")):
        relative = path.relative_to(skills_root)
        source = path.relative_to(root).as_posix()
        if len(relative.parts) != 2:
            errors.append(
                failure(source, "skill-layout", "use skills/<skill>/SKILL.md")
            )
            continue

        values, metadata, parse_errors = parse_skill(path, root)
        errors.extend(parse_errors)
        name = values.get("name")
        if not isinstance(name, str) or not name:
            errors.append(failure(source, "skill-name", "add a non-empty frontmatter `name`"))
            continue
        if name != path.parent.name:
            errors.append(
                failure(source, "skill-name", f"set `name: {path.parent.name}` to match its directory")
            )
        description = values.get("description")
        if not isinstance(description, str) or not description.strip():
            errors.append(failure(source, "skill-description", "add frontmatter `description`"))
        if name in seen:
            errors.append(
                failure(source, "skill-unique-id", f"rename it; `{name}` already exists at {seen[name]}")
            )
        seen[name] = source
        category = metadata.get("category")
        if not isinstance(category, str) or category not in SKILL_CATEGORIES:
            errors.append(
                failure(
                    source,
                    "skill-category",
                    "set `metadata.category` to an official category",
                )
            )
        version = metadata.get("version")
        if not isinstance(version, str) or not SEMVER_PATTERN.fullmatch(version):
            errors.append(
                failure(source, "skill-version", "set `metadata.version` to a valid SemVer")
            )
            continue
        artifacts[f"skill:{name}"] = (path.parent.relative_to(root).as_posix(), version)
    return artifacts, errors

def validate_private_skills(
    root: Path,
    plugin_dir: Path,
    standalone_names: set[str],
    private_seen: dict[str, str],
) -> list[str]:
    errors: list[str] = []
    for skill_path in sorted((plugin_dir / "skills").rglob("SKILL.md")):
        source = skill_path.relative_to(root).as_posix()
        values, metadata, parse_errors = parse_skill(skill_path, root)
        errors.extend(parse_errors)
        skill_name = values.get("name")
        if not isinstance(skill_name, str) or not skill_name:
            errors.append(failure(source, "plugin-skill-name", "add frontmatter `name`"))
            continue
        if skill_name != skill_path.parent.name:
            errors.append(
                failure(
                    source,
                    "plugin-skill-name",
                    f"set `name: {skill_path.parent.name}` to match its directory",
                )
            )
        description = values.get("description")
        if not isinstance(description, str) or not description.strip():
            errors.append(
                failure(source, "plugin-skill-description", "add frontmatter `description`")
            )
        if metadata.get("internal") is not True:
            errors.append(failure(source, "plugin-skill-private", "set `metadata.internal: true`"))
        if skill_name in standalone_names:
            errors.append(
                failure(
                    source,
                    "duplicate-distribution",
                    f"remove or rename `{skill_name}`; it is also standalone",
                )
            )
        if skill_name in private_seen:
            errors.append(
                failure(
                    source,
                    "plugin-skill-unique-id",
                    f"rename it; `{skill_name}` already exists at {private_seen[skill_name]}",
                )
            )
        private_seen[skill_name] = source
    return errors


def validate_code_atlas(
    root: Path,
    plugin_dir: Path,
    manifests: list[tuple[Path, dict]],
) -> list[str]:
    """Apply identity-specific contracts without constraining future plugins."""
    if plugin_dir.name != CODE_ATLAS_NAME:
        return []

    errors: list[str] = []
    source = plugin_dir.relative_to(root)
    skill_paths = sorted((plugin_dir / "skills").rglob("SKILL.md"))
    if len(skill_paths) != 1:
        errors.append(failure(source, "code-atlas-single-skill", "keep exactly one private Skill"))
    elif skill_paths[0].parent.name != CODE_ATLAS_NAME:
        errors.append(
            failure(
                skill_paths[0].relative_to(root),
                "code-atlas-skill-identity",
                "set the private Skill directory and frontmatter name to `code-atlas`",
            )
        )
    if (plugin_dir / ".mcp.json").exists():
        errors.append(failure(source, "code-atlas-no-mcp", "remove `.mcp.json`"))
    for relative in CODE_ATLAS_SKILL_FILES:
        path = plugin_dir / relative
        if not path.is_file():
            errors.append(
                failure(
                    path.relative_to(root),
                    "code-atlas-skill-assets",
                    "restore the required CodeAtlas reference, scanner, schema or metadata file",
                )
            )
    for relative in CODE_ATLAS_SCHEMAS:
        path = plugin_dir / relative
        if not path.is_file():
            continue
        document, load_errors = load_json(path, root)
        errors.extend(load_errors)
        if document is not None and not (
            isinstance(document.get("$schema"), str)
            and document.get("type") == "object"
            and isinstance(document.get("properties"), dict)
            and "findings" in document["properties"]
        ):
            errors.append(
                failure(
                    path.relative_to(root),
                    "code-atlas-schema-contract",
                    "keep a draft-tagged object schema with a `findings` property",
                )
            )
    standard_hooks = plugin_dir / "hooks" / "hooks.json"
    if standard_hooks.exists():
        errors.append(
            failure(
                standard_hooks.relative_to(root),
                "code-atlas-standard-hooks-path",
                f"remove auto-loaded `hooks/hooks.json`; use `{CODE_ATLAS_HOOKS}`",
            )
        )

    hook_paths: list[str] = []
    for manifest_path, manifest in manifests:
        description_fields = [("description", manifest.get("description"))]
        interface = manifest.get("interface")
        if isinstance(interface, dict):
            description_fields.extend(
                (field, interface.get(field))
                for field in ("shortDescription", "longDescription")
            )
        for field, value in description_fields:
            if not isinstance(value, str) or not all(
                marker.lower() in value.lower()
                for marker in CODE_ATLAS_LIFECYCLE_DESCRIPTION_MARKERS
            ):
                errors.append(
                    failure(
                        manifest_path.relative_to(root),
                        "code-atlas-lifecycle-description",
                        f"{field} must distinguish read-only analysis from SessionStart writes to .codegraph/.gitignore",
                    )
                )
        if "mcpServers" in manifest:
            errors.append(
                failure(
                    manifest_path.relative_to(root),
                    "code-atlas-no-mcp-servers",
                    "remove manifest `mcpServers`; negotiate native MCP at runtime",
                )
            )
        hooks = manifest.get("hooks")
        if hooks != CODE_ATLAS_HOOKS:
            errors.append(
                failure(
                    manifest_path.relative_to(root),
                    "code-atlas-hooks-path",
                    f"register the shared hooks companion exactly once at `{CODE_ATLAS_HOOKS}`",
                )
            )
        elif isinstance(hooks, str):
            hook_paths.append(hooks)

    if hook_paths and len(set(hook_paths)) != 1:
        errors.append(failure(source, "code-atlas-hooks-duplicate", "use one shared hooks path in both manifests"))

    hook_file = plugin_dir / CODE_ATLAS_HOOK_FILE
    document, load_errors = load_json(hook_file, root)
    errors.extend(load_errors)
    if document is None:
        return errors
    if not valid_hooks(document):
        errors.append(failure(hook_file.relative_to(root), "code-atlas-hooks-shape", "use valid host hook matchers"))
        return errors

    events = document.get("hooks", {})
    if set(events) != {"SessionStart", "SubagentStart"}:
        errors.append(
            failure(
                hook_file.relative_to(root),
                "code-atlas-hook-events",
                "register only SessionStart and SubagentStart",
            )
        )
    session = events.get("SessionStart", [])
    if len(session) != 1 or session[0].get("matcher") != "startup|resume|clear|compact":
        errors.append(
            failure(
                hook_file.relative_to(root),
                "code-atlas-session-matcher",
                "use exactly matcher `startup|resume|clear|compact`",
            )
        )
    subagent = events.get("SubagentStart", [])
    if len(subagent) != 1 or "matcher" in subagent[0]:
        errors.append(
            failure(
                hook_file.relative_to(root),
                "code-atlas-subagent-matcher",
                "register one unfiltered SubagentStart matcher",
            )
        )
    expected_commands = {
        "SessionStart": f"{CODE_ATLAS_RUNNER} SessionStart",
        "SubagentStart": f"{CODE_ATLAS_RUNNER} SubagentStart",
    }
    runner_bases: set[str] = set()
    for event, matchers in (("SessionStart", session), ("SubagentStart", subagent)):
        for matcher in matchers:
            for hook in matcher.get("hooks", []):
                command = hook.get("command")
                if command != expected_commands[event]:
                    errors.append(
                        failure(
                            hook_file.relative_to(root),
                            "code-atlas-hook-runner",
                            f"use the direct runner command `{expected_commands[event]}`",
                        )
                    )
                elif isinstance(command, str):
                    runner_bases.add(command.rsplit(" ", 1)[0])
                timeout = hook.get("timeout")
                if (
                    not isinstance(timeout, (int, float))
                    or isinstance(timeout, bool)
                    or timeout <= CODE_ATLAS_INTERNAL_TIMEOUT_SECONDS
                    or timeout > CODE_ATLAS_HOOK_TIMEOUT_SECONDS
                ):
                    errors.append(
                        failure(
                            hook_file.relative_to(root),
                            "code-atlas-hook-timeout",
                            f"set every lifecycle hook timeout above the {CODE_ATLAS_INTERNAL_TIMEOUT_SECONDS}s internal bound and at most {CODE_ATLAS_HOOK_TIMEOUT_SECONDS}s",
                        )
                    )
    if runner_bases != {CODE_ATLAS_RUNNER}:
        errors.append(failure(hook_file.relative_to(root), "code-atlas-hook-runner", "use one direct runner with only the event argument differing"))
    if any(":-" in str(matcher.get("hooks")) for matcher in (*session, *subagent)):
        errors.append(failure(hook_file.relative_to(root), "code-atlas-no-shell-fallback", "do not use POSIX `${A:-...}` fallback syntax"))
    if "UserPromptSubmit" in json.dumps(document, ensure_ascii=False):
        errors.append(failure(hook_file.relative_to(root), "code-atlas-no-user-prompt-hook", "do not register UserPromptSubmit"))
    runner_path = plugin_dir / "scripts" / "code-atlas-hook.js"
    if runner_path.is_file():
        runner_source = runner_path.read_text(encoding="utf-8")
        required_markers = (
            "codegraph init",
            "codegraph sync --quiet",
            "CODEGRAPH_NO_DOWNLOAD",
            "CODEGRAPH_NO_DAEMON",
            "CODEGRAPH_NO_WATCH",
            "CODEGRAPH_FORCE_WATCH",
            "CODEGRAPH_NO_UPDATE_CHECK",
            "DO_NOT_TRACK",
            "codegraph.lock",
            "--git-path",
            "git-hooks-dir",
            "git-hooks-probe",
            "lock-conflict",
            "status --json",
            "STATUS_TIMEOUT_MS",
            "status-pending",
            "status-index-path",
            "needs-agent",
            "SubagentStart does not run init or sync",
        )
        for marker in required_markers:
            if marker not in runner_source:
                errors.append(
                    failure(
                        runner_path.relative_to(root),
                        "code-atlas-lifecycle-contract",
                        f"keep lifecycle marker `{marker}`",
                    )
                )
    return errors

def validate_plugins(
    root: Path, standalone_names: set[str]
) -> tuple[dict[str, tuple[str, str]], list[str]]:
    artifacts: dict[str, tuple[str, str]] = {}
    private_seen: dict[str, str] = {}
    errors: list[str] = []
    plugins_root = root / "plugins"
    for plugin_dir in sorted(path for path in plugins_root.iterdir() if path.is_dir()):
        manifests: list[tuple[Path, dict]] = []
        for relative in (Path(".codex-plugin/plugin.json"), Path(".claude-plugin/plugin.json")):
            path = plugin_dir / relative
            manifest, manifest_errors = load_json(path, root)
            errors.extend(manifest_errors)
            if manifest is not None:
                manifests.append((path, manifest))
        if len(manifests) != 2:
            continue
        first = manifests[0][1]
        plugin_name = first.get("name")
        for field in SHARED_PLUGIN_FIELDS:
            if field == "mcpServers" and plugin_name == CODE_ATLAS_NAME:
                continue
            values = [manifest.get(field) for _, manifest in manifests]
            if any(value is None for value in values) or values[1:] != values[:-1]:
                errors.append(
                    failure(
                        plugin_dir.relative_to(root),
                        "plugin-manifest-drift",
                        f"make `{field}` identical in Codex and Claude manifests",
                    )
                )
        name = first.get("name")
        version = first.get("version")
        if name != plugin_dir.name:
            errors.append(
                failure(
                    manifests[0][0].relative_to(root),
                    "plugin-name",
                    f"set `name` to directory name `{plugin_dir.name}`",
                )
            )
        if not isinstance(version, str) or not SEMVER_PATTERN.fullmatch(version):
            errors.append(
                failure(
                    manifests[0][0].relative_to(root),
                    "plugin-version",
                    "set `version` to a valid SemVer",
                )
            )
        elif isinstance(name, str):
            artifacts[f"plugin:{name}"] = (plugin_dir.relative_to(root).as_posix(), version)
        for manifest_path, manifest in manifests:
            for field in ("skills", "hooks", "mcpServers"):
                errors.extend(
                    validate_component_path(
                        root, plugin_dir, manifest_path, field, manifest.get(field)
                    )
                )
        errors.extend(
            validate_private_skills(root, plugin_dir, standalone_names, private_seen)
        )
        errors.extend(validate_code_atlas(root, plugin_dir, manifests))
    return artifacts, errors

def marketplace_plugin(entry: dict, harness: str) -> tuple[str | None, str | None]:
    name = entry.get("name")
    source = entry.get("source")
    if harness == "Codex" and isinstance(source, dict):
        source = source.get("path")
    return name if isinstance(name, str) else None, source if isinstance(source, str) else None

def validate_marketplace(
    root: Path, relative: str, harness: str, plugin_names: set[str]
) -> list[str]:
    path = root / relative
    marketplace, errors = load_json(path, root)
    if marketplace is None:
        return errors
    if marketplace.get("name") != MARKETPLACE_ID:
        errors.append(
            failure(
                relative,
                "marketplace-identity",
                f"set `name` to `{MARKETPLACE_ID}`",
            )
        )
    entries = marketplace.get("plugins")
    if not isinstance(entries, list):
        errors.append(failure(relative, "marketplace-plugins", "set `plugins` to an array"))
        return errors
    found: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            errors.append(failure(relative, "marketplace-entry", "use an object for each plugin"))
            continue
        name, source = marketplace_plugin(entry, harness)
        if not name or not source:
            errors.append(
                failure(relative, "marketplace-entry", "give each plugin a valid `name` and `source`")
            )
            continue
        target = (root / source).resolve()
        expected = target / f".{harness.lower().split()[0]}-plugin" / "plugin.json"
        if not target.is_relative_to(root.resolve()) or not expected.is_file():
            errors.append(
                failure(relative, "marketplace-path", f"make `{source}` point to a {harness} plugin")
            )
            continue
        manifest, manifest_errors = load_json(expected, root)
        errors.extend(manifest_errors)
        if manifest is not None and manifest.get("name") != name:
            errors.append(
                failure(relative, "marketplace-name", f"make `{name}` match {expected.relative_to(root)}")
            )
        found.add(name)
    if found != plugin_names:
        errors.append(
            failure(
                relative,
                "marketplace-coverage",
                f"list exactly these plugins: {', '.join(sorted(plugin_names))}",
            )
        )
    return errors

def base_artifacts(root: Path, base_ref: str) -> dict[str, tuple[str, str | None]]:
    return artifact_versions_at_ref(root, base_ref)

def run_check(root: Path, command: list[str], rule: str, fix: str) -> list[str]:
    result = subprocess.run(command, cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode == 0:
        return []
    detail = result.stdout.strip().splitlines()
    suffix = f" ({detail[-1]})" if detail else ""
    source = Path(command[1]).relative_to(root) if len(command) > 1 else Path(".")
    return [failure(source, rule, f"{fix}{suffix}")]

def tracked_json_errors(root: Path) -> list[str]:
    paths = git_output(
        root, "ls-files", "--cached", "--others", "--exclude-standard", "--", "*.json"
    ).splitlines()
    errors: list[str] = []
    for relative in paths:
        try:
            json.loads((root / relative).read_text(encoding="utf-8"))
        except FileNotFoundError:
            # A staged deletion is a valid candidate state before commit.
            continue
        except OSError as exc:
            errors.append(failure(relative, "json-read", f"read JSON file: {exc}"))
        except json.JSONDecodeError as exc:
            errors.append(failure(relative, "json-syntax", f"fix JSON syntax: {exc}"))
    return errors

def validate_repository(root: Path, base_ref: str | None = None) -> list[str]:
    skill_artifacts, errors = validate_skills(root)
    plugin_artifacts, plugin_errors = validate_plugins(
        root, {identity.removeprefix("skill:") for identity in skill_artifacts}
    )
    errors.extend(plugin_errors)
    errors.extend(validate_npx_readmes(root))
    plugin_names = {identity.removeprefix("plugin:") for identity in plugin_artifacts}
    errors.extend(
        validate_marketplace(root, ".agents/plugins/marketplace.json", "Codex", plugin_names)
    )
    errors.extend(
        validate_marketplace(root, ".claude-plugin/marketplace.json", "Claude", plugin_names)
    )
    errors.extend(tracked_json_errors(root))
    errors.extend(
        run_check(
            root,
            [sys.executable, str(root / "scripts/render-plugin-directory.py"), "--check"],
            "generated-directory",
            "run `python3 scripts/render-plugin-directory.py`",
        )
    )
    errors.extend(
        run_check(
            root,
            [sys.executable, str(root / "scripts/validate-dev-orchestration.py")],
            "dev-orchestration",
            "fix the shared PMO and Tasks Owner contract or behavior cases",
        )
    )
    if base_ref:
        changed = set(git_output(root, "diff", "--name-only", base_ref, "--").splitlines())
        errors.extend(
            version_bump_errors(
                {**skill_artifacts, **plugin_artifacts},
                base_artifacts(root, base_ref),
                changed,
            )
        )
    return errors

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-ref", help="compare artifact versions with this Git ref")
    parser.add_argument("--self-test", action="store_true", help="run negative contract checks")
    args = parser.parse_args()
    try:
        errors = (
            run_self_test(
                validate_skills,
                version_bump_errors,
                validate_plugins,
                validate_marketplace,
            )
            if args.self_test
            else validate_repository(ROOT, args.base_ref)
        )
        if args.self_test:
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/validate-dev-orchestration.py"), "--self-test"],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            if result.returncode:
                errors.append(failure("scripts/validate-dev-orchestration.py", "orchestration-self-test", result.stdout.strip()))
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        errors = [failure(".", "validator-runtime", f"fix validator input or environment: {exc}")]
    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    if not errors:
        print("Repository validation passed." if not args.self_test else "Validator self-check passed.")
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
