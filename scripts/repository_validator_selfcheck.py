"""Negative checks for the repository validator."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shlex
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from repository_artifacts import artifact_versions_at_ref, snapshot
from repository_skills import NPX_ADD_PREFIX, SKILLS_SOURCE, validate_npx_readmes


def write_skill(
    path: Path,
    name: str,
    description: str = "test",
    version: str = "0.1.0",
    category: str | None = "Developer Tools",
) -> None:
    path.mkdir(parents=True, exist_ok=True)
    category_line = f"  category: {category}\n" if category is not None else ""
    (path / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n"
        f"metadata:\n  version: {version}\n{category_line}---\n",
        encoding="utf-8",
    )


def write_plugin(
    root: Path,
    name: str,
    *,
    skills: object = "./skills/",
    mcp: dict | None = None,
    hooks: dict | None = None,
    private_description: str | None = "test",
) -> None:
    plugin = root / "plugins" / name
    private = plugin / "skills" / f"{name}-private"
    private.mkdir(parents=True)
    description = (
        f"description: {private_description}\n" if private_description is not None else ""
    )
    (private / "SKILL.md").write_text(
        f"---\nname: {name}-private\n{description}metadata:\n  internal: true\n---\n",
        encoding="utf-8",
    )
    (plugin / ".mcp.json").write_text(
        json.dumps(
            mcp
            if mcp is not None
            else {"server": {"command": "codegraph", "args": ["serve", "--mcp"]}}
        ),
        encoding="utf-8",
    )
    base = {
        "name": name,
        "version": "0.1.0",
        "description": "test",
        "author": {"name": "test"},
        "license": "MIT",
        "keywords": [],
        "skills": skills,
        "mcpServers": "./.mcp.json",
    }
    for harness in (".codex-plugin", ".claude-plugin"):
        manifest = plugin / harness / "plugin.json"
        manifest.parent.mkdir(parents=True)
        document = dict(base)
        if harness == ".codex-plugin" and hooks is not None:
            (plugin / "hooks.json").write_text(json.dumps(hooks), encoding="utf-8")
            document["hooks"] = "./hooks.json"
        manifest.write_text(json.dumps(document), encoding="utf-8")


def write_code_atlas_plugin(root: Path, *, valid: bool = True) -> Path:
    plugin = root / "plugins" / "code-atlas"
    skill = plugin / "skills" / "code-atlas"
    skill.mkdir(parents=True, exist_ok=True)
    (skill / "SKILL.md").write_text(
        "---\nname: code-atlas\ndescription: test\n"
        "metadata:\n  internal: true\n  version: 0.3.0\n---\n",
        encoding="utf-8",
    )
    required = (
        "agents/openai.yaml",
        "assets/config.example.yml",
        "references/change-analysis.md",
        "references/codegraph.md",
        "references/dead-code.md",
        "references/exploration.md",
        "references/maintainability.md",
        "references/test-selection.md",
        "references/trace-and-debug.md",
        "scripts/build-evidence-pack.py",
        "scripts/scan-dependencies.py",
        "scripts/scan-duplication.py",
        "scripts/scan-git-churn.py",
        "scripts/scan-literals-comments.py",
        "scripts/scan-size-complexity.py",
        "scripts/scan-tests.py",
    )
    for relative in required:
        path = skill / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture\n", encoding="utf-8")
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {"findings": {"type": "array"}},
    }
    for name in ("decision-report.schema.json", "evidence-pack.schema.json"):
        (skill / "assets" / name).write_text(json.dumps(schema), encoding="utf-8")
    hooks = {
        "hooks": {
            "SessionStart": [
                {
                    "matcher": "startup|resume|clear|compact",
                    "hooks": [{"type": "command", "command": "node \"${CLAUDE_PLUGIN_ROOT}/scripts/code-atlas-hook.js\" SessionStart", "timeout": 30}],
                }
            ],
            "SubagentStart": [
                {
                    "hooks": [{"type": "command", "command": "node \"${CLAUDE_PLUGIN_ROOT}/scripts/code-atlas-hook.js\" SubagentStart", "timeout": 30}],
                }
            ],
        }
    }
    hook_file = plugin / "hooks" / "claude-codex-hooks.json"
    hook_file.parent.mkdir(parents=True, exist_ok=True)
    hook_file.write_text(json.dumps(hooks), encoding="utf-8")
    base = {
        "name": "code-atlas",
        "version": "0.3.0",
        "description": "CodeAtlas analysis workflows are read-only; SessionStart maintains the current worktree .codegraph and required .gitignore.",
        "author": {"name": "test"},
        "license": "MIT",
        "keywords": [],
        "skills": "./skills/",
        "hooks": "./hooks/claude-codex-hooks.json",
    }
    for harness in (".codex-plugin", ".claude-plugin"):
        manifest = plugin / harness / "plugin.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps(base), encoding="utf-8")
    if not valid:
        (plugin / ".mcp.json").write_text("{}", encoding="utf-8")
        (plugin / "hooks" / "hooks.json").write_text("{}", encoding="utf-8")
        extra = plugin / "skills" / "extra"
        extra.mkdir()
        (extra / "SKILL.md").write_text(
            "---\nname: extra\ndescription: test\nmetadata:\n  internal: true\n---\n",
            encoding="utf-8",
        )
        invalid_hooks = json.loads(hook_file.read_text(encoding="utf-8"))
        invalid_hooks["hooks"]["SessionStart"][0]["hooks"][0]["timeout"] = 31
        invalid_hooks["hooks"]["SubagentStart"][0]["hooks"][0]["command"] = "node \"${CLAUDE_PLUGIN_ROOT:-.}/scripts/code-atlas-hook.js\" SubagentStart"
        invalid_hooks["hooks"]["UserPromptSubmit"] = invalid_hooks["hooks"]["SubagentStart"]
        hook_file.write_text(json.dumps(invalid_hooks), encoding="utf-8")
        (skill / "scripts" / "scan-tests.py").unlink()
        (skill / "assets" / "evidence-pack.schema.json").write_text(
            json.dumps({"type": "array"}), encoding="utf-8"
        )
    return plugin


def expect(errors: list[str], source: str, rule: str, failures: list[str]) -> None:
    if not any(source in error and rule in error for error in errors):
        failures.append(f"{source} {rule} self-check did not fail")


def check_skills(root, validate_skills, version_bump_errors, failures) -> None:
    write_skill(root / "skills" / "nested" / "blocked", "blocked")
    write_skill(root / "skills" / "missing-category", "missing-category", category=None)
    write_skill(root / "skills" / "unknown-category", "unknown-category", category="dev")
    wrong_type = root / "skills" / "category-type"
    write_skill(wrong_type, "category-type")
    (wrong_type / "SKILL.md").write_text(
        (wrong_type / "SKILL.md").read_text(encoding="utf-8").replace(
            "category: Developer Tools", "category: true"
        ),
        encoding="utf-8",
    )
    missing = root / "skills" / "missing"
    missing.mkdir()
    (missing / "SKILL.md").write_text(
        "---\nname: missing\ndescription: test\n---\n", encoding="utf-8"
    )
    invalid_description = root / "skills" / "invalid-description"
    invalid_description.mkdir()
    (invalid_description / "SKILL.md").write_text(
        "---\nname: invalid-description\ndescription: true\n"
        "metadata:\n  version: 0.1.0\n---\n",
        encoding="utf-8",
    )
    _, skill_errors = validate_skills(root)
    expect(skill_errors, "skills/nested/blocked", "[skill-layout]", failures)
    expect(skill_errors, "skills/missing-category", "[skill-category]", failures)
    expect(skill_errors, "skills/unknown-category", "[skill-category]", failures)
    expect(skill_errors, "skills/category-type", "[skill-category]", failures)
    expect(skill_errors, "skills/missing", "[skill-version]", failures)
    expect(skill_errors, "skills/invalid-description", "[skill-description]", failures)

    renderer_root = root / "renderer"
    write_skill(
        renderer_root / "skills" / "metadata-source",
        "metadata-source",
        category="Data & Analytics",
    )
    spec = importlib.util.spec_from_file_location(
        "render_plugin_directory", Path(__file__).with_name("render-plugin-directory.py")
    )
    if spec is None or spec.loader is None:
        failures.append("renderer self-check could not load render-plugin-directory.py")
        return
    renderer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(renderer)
    renderer.ROOT = renderer_root
    rendered = renderer.render_skills(("Skill", "Category", "Version", "Description"))
    row = next((line for line in rendered.splitlines() if "metadata-source" in line), "")
    if "| Data & Analytics |" not in row:
        failures.append("renderer category self-check did not use metadata.category")


def check_historical_skill_migration(root, validate_skills, version_bump_errors, failures) -> None:
    repository = root / "history"
    repository.mkdir()
    git(repository, "init", "-b", "main")
    git(repository, "config", "user.name", "self-check")
    git(repository, "config", "user.email", "self-check@example.invalid")
    write_skill(
        repository / "skills" / "dev" / "legacy-skill",
        "legacy-skill",
        version="0.12.0",
        category=None,
    )
    base = commit_all(repository, "legacy nested skill")
    previous = artifact_versions_at_ref(repository, base)
    if previous.get("skill:legacy-skill") != ("skills/dev/legacy-skill", "0.12.0"):
        failures.append("historical nested skill snapshot did not preserve its old path/version")
    if "category" in snapshot(repository, base)["artifacts"][0]:
        failures.append("historical nested skill snapshot inferred category from its path")

    (repository / "skills" / "dev" / "legacy-skill").rename(
        repository / "skills" / "legacy-skill"
    )
    write_skill(
        repository / "skills" / "legacy-skill",
        "legacy-skill",
        version="0.12.0",
        category="Developer Tools",
    )
    current, errors = validate_skills(repository)
    if errors:
        failures.append(f"flat migration fixture failed current validation: {errors}")
    changed = set(git(repository, "diff", "--name-only", base, "--").splitlines())
    expect(
        version_bump_errors(current, previous, changed),
        "skills/legacy-skill",
        "[artifact-version-bump]",
        failures,
    )

    write_skill(
        repository / "skills" / "legacy-skill",
        "legacy-skill",
        version="0.13.0",
        category="Developer Tools",
    )
    current, errors = validate_skills(repository)
    if errors:
        failures.append(f"upgraded flat migration fixture failed current validation: {errors}")
    if version_bump_errors(current, previous, changed):
        failures.append("a correctly upgraded nested-to-flat migration failed version validation")
    upgraded = commit_all(repository, "flatten and upgrade skill")
    if snapshot(repository, upgraded)["artifacts"][0].get("category") != "Developer Tools":
        failures.append("artifact snapshot did not read category from metadata.category")


def check_plugins(root, validate_plugins, failures) -> None:
    write_plugin(root, "bad-type", skills=123)
    write_plugin(root, "bad-path", skills="../outside")
    write_plugin(root, "bad-mcp", mcp={"server": {"command": ""}})
    write_plugin(
        root,
        "bad-mcp-args",
        mcp={"server": {"command": "codegraph", "args": "not-a-list"}},
    )
    write_plugin(root, "bad-hooks", hooks={"hooks": {"SessionStart": "not-a-list"}})
    valid_hook = [{"hooks": [{"type": "command", "command": "true"}]}]
    write_plugin(root, "bad-hook-event", hooks={"hooks": {"NotARealEvent": valid_hook}})
    write_plugin(
        root,
        "bad-hook-matcher",
        hooks={
            "hooks": {
                "SessionStart": [
                    {
                        "matcher": 123,
                        "hooks": [{"type": "command", "command": "true"}],
                    }
                ]
            }
        },
    )
    write_plugin(root, "bad-private", private_description=None)
    _, plugin_errors = validate_plugins(root, set())
    expected = (
        ("plugins/bad-type", "[plugin-component-type]"),
        ("plugins/bad-path", "[plugin-component-path]"),
        ("plugins/bad-mcp/.mcp.json", "[plugin-component-content]"),
        ("plugins/bad-mcp-args/.mcp.json", "[plugin-component-content]"),
        ("plugins/bad-hooks/hooks.json", "[plugin-component-content]"),
        ("plugins/bad-hook-event/hooks.json", "[plugin-component-content]"),
        ("plugins/bad-hook-matcher/hooks.json", "[plugin-component-content]"),
        ("plugins/bad-private", "[plugin-skill-description]"),
    )
    for source, rule in expected:
        expect(plugin_errors, source, rule, failures)

    atlas_root = root / "atlas-contract"
    write_code_atlas_plugin(atlas_root)
    _, atlas_errors = validate_plugins(atlas_root, set())
    if atlas_errors:
        failures.append(f"valid CodeAtlas fixture failed: {atlas_errors}")
    invalid_root = root / "atlas-negative"
    write_code_atlas_plugin(invalid_root, valid=False)
    _, invalid_errors = validate_plugins(invalid_root, set())
    expect(invalid_errors, "plugins/code-atlas", "[code-atlas-no-mcp]", failures)
    expect(invalid_errors, "plugins/code-atlas/hooks/hooks.json", "[code-atlas-standard-hooks-path]", failures)
    expect(invalid_errors, "plugins/code-atlas", "[code-atlas-single-skill]", failures)
    expect(invalid_errors, "plugins/code-atlas/hooks/claude-codex-hooks.json", "[code-atlas-hook-events]", failures)
    expect(invalid_errors, "plugins/code-atlas/hooks/claude-codex-hooks.json", "[code-atlas-hook-timeout]", failures)
    expect(invalid_errors, "plugins/code-atlas/hooks/claude-codex-hooks.json", "[code-atlas-no-user-prompt-hook]", failures)
    expect(invalid_errors, "plugins/code-atlas/hooks/claude-codex-hooks.json", "[code-atlas-no-shell-fallback]", failures)
    expect(invalid_errors, "plugins/code-atlas/skills/code-atlas/scripts/scan-tests.py", "[code-atlas-skill-assets]", failures)
    expect(invalid_errors, "plugins/code-atlas/skills/code-atlas/assets/evidence-pack.schema.json", "[code-atlas-schema-contract]", failures)


def check_npx_readmes(root, failures) -> None:
    (root / "README.md").write_text(
        "npx skills add MC0571/MC-SKILLS --skill same\n",
        encoding="utf-8",
    )
    expect(
        validate_npx_readmes(root),
        "README.md",
        "[npx-source-boundary]",
        failures,
    )
    (root / "README.md").write_text(
        f"{NPX_ADD_PREFIX}-wrong --list\n",
        encoding="utf-8",
    )
    expect(
        validate_npx_readmes(root),
        "README.md",
        "[npx-source-boundary]",
        failures,
    )


def check_marketplace_identity(root, validate_marketplace, failures) -> None:
    path = root / "marketplace.json"
    path.write_text(json.dumps({"name": "mcskills", "plugins": []}), encoding="utf-8")
    errors = validate_marketplace(root, "marketplace.json", "Claude", set())
    expect(errors, "marketplace.json", "[marketplace-identity]", failures)


def file_snapshot(root: Path) -> dict[str, tuple[str, str]]:
    """Return a deterministic file/directory snapshot without following Git metadata."""
    snapshot: dict[str, tuple[str, str]] = {}
    if not root.exists():
        return snapshot
    for item in sorted(root.rglob("*")):
        relative = item.relative_to(root).as_posix()
        if ".git" in Path(relative).parts:
            continue
        if item.is_dir():
            snapshot[relative] = ("dir", "")
        elif item.is_file():
            digest = hashlib.sha256(item.read_bytes()).hexdigest()
            snapshot[relative] = ("file", digest)
    return snapshot


def git_hook_snapshot(worktree: Path) -> dict[str, tuple[str, str]]:
    """Snapshot the configured hooks path without probing repository status."""
    hooks = Path(git(worktree, "rev-parse", "--git-path", "hooks"))
    if not hooks.is_absolute():
        hooks = (worktree / hooks).resolve()
    return file_snapshot(hooks)


def allowed_runtime_changes(before: dict[str, tuple[str, str]], after: dict[str, tuple[str, str]]) -> bool:
    changed = set(before) | set(after)
    for relative in changed:
        if relative in {".gitignore", ".codegraph"} or relative.startswith(".codegraph/"):
            continue
        if before.get(relative) != after.get(relative):
            return False
    return True


def check_code_atlas_hook_runtime(failures: list[str]) -> None:
    """Run the lifecycle runner against an isolated fake CLI/index fixture."""
    runner = Path(__file__).resolve().parents[1] / "plugins/code-atlas/scripts/code-atlas-hook.js"
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        repo = root / "repo"
        repo.mkdir()
        git(repo, "init", "-b", "main")
        git(repo, "config", "user.name", "self-check")
        git(repo, "config", "user.email", "self-check@example.invalid")
        (repo / "README.md").write_text("fixture\n", encoding="utf-8")
        commit_all(repo, "fixture")
        alternate = root / "repo-alternate"
        git(repo, "worktree", "add", "-b", "alternate", str(alternate))
        fake_bin = root / "bin"
        fake_bin.mkdir()
        fake_cli = fake_bin / "codegraph"
        fake_cli.write_text(
            "#!/bin/sh\n"
            "set -eu\n"
            "case \"$1\" in\n"
            "  init) target=\"$2\"; action=init ;;\n"
            "  sync) target=\"$3\"; action=sync ;;\n"
            "  status) target=\"$3\"; printf '{\"initialized\":true,\"projectPath\":\"%s\",\"pendingChanges\":{\"added\":0,\"modified\":0,\"removed\":0}}\\n' \"$target\"; exit 0 ;;\n"
            "  *) exit 2 ;;\n"
            "esac\n"
            "mkdir -p \"$target/.codegraph\"\n"
            "printf 'SQLite format 3\\000%s\\n' \"$action\" > \"$target/.codegraph/codegraph.db\"\n"
            "exit 0\n",
            encoding="utf-8",
        )
        fake_cli.chmod(0o755)
        db = repo / ".codegraph" / "codegraph.db"
        db.parent.mkdir()
        db.write_bytes(b"SQLite format 3\x00self-check\n")
        node_path = shutil.which("node")
        if not node_path:
            failures.append("node is unavailable for lifecycle runner self-check")
            return

        source = runner.read_text(encoding="utf-8")
        for marker in ("quoteWindowsArg", "spawnSpec", "ComSpec", "taskkill", "detached"):
            if marker not in source:
                failures.append(f"runner lacks cross-platform process marker: {marker}")
        command_probe = subprocess.run(
            [
                node_path,
                "-e",
                (
                    f"const h=require({json.dumps(str(runner))});"
                    "const c=h.exactCommand('sync','/tmp/work tree');"
                    "if (!c.includes('work tree')) process.exit(1);"
                    "const q=h.quoteWindowsArg('C:\\\\Program Files\\\\CodeGraph\\\\codegraph.cmd');"
                    "if (!q.startsWith('\\\"') || !q.endsWith('\\\"')) process.exit(2);"
                ),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if command_probe.returncode != 0:
            failures.append(f"cross-platform command construction probe failed: {command_probe.stderr}")

        def run(
            event: str,
            cwd: Path,
            *,
            plugin_data: Path | None = None,
            path_override: str | None = None,
            extra_env: dict[str, str] | None = None,
        ) -> tuple[dict | str, str, str]:
            env = {
                "PATH": path_override or str(fake_bin) + os.pathsep + os.environ.get("PATH", ""),
                "CODEX_CWD": str(cwd),
                "CODEX_WORKSPACE_DIR": "",
                "CLAUDE_PROJECT_DIR": "",
            }
            if plugin_data is not None:
                env["PLUGIN_DATA"] = str(plugin_data)
            if extra_env:
                env.update(extra_env)
            result = subprocess.run(
                [node_path, str(runner), event],
                cwd=cwd,
                env={**env},
                input="ignored stdin\n",
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            if result.returncode != 0:
                failures.append(f"runner {event} exited {result.returncode}: {result.stderr}")
            try:
                parsed: dict | str = json.loads(result.stdout)
            except json.JSONDecodeError:
                parsed = result.stdout
            return parsed, result.stdout, result.stderr

        before_files = file_snapshot(repo)
        before_hooks = git_hook_snapshot(repo)
        native_session, _, stderr = run("SessionStart", repo)
        if stderr or not isinstance(native_session, str):
            failures.append("native SessionStart did not emit raw context with empty stderr")
        elif any(item not in native_session for item in ("status=ready", "needs-agent=false", "action=sync", "worktree=", "git-common-dir=", "git-hooks-dir=", "mcp=unknown")):
            failures.append("native SessionStart context omitted required evidence")
        elif "SubagentStart evidence" in native_session:
            failures.append("native SessionStart included reduced SubagentStart-only context")

        alternate_session, _, stderr = run("SessionStart", alternate)
        expected_common = str((repo / ".git").resolve())
        if stderr or not isinstance(alternate_session, str):
            failures.append("alternate worktree SessionStart did not emit raw context")
        elif any(
            item not in alternate_session
            for item in (
                "status=ready",
                "needs-agent=false",
                "action=init",
                f"worktree={alternate.resolve()}",
                f"git-common-dir={expected_common}",
                f"index={alternate.resolve()}/.codegraph/codegraph.db",
            )
        ):
            failures.append("alternate worktree reused the primary worktree index or identity")
        if isinstance(native_session, str) and f"git-common-dir={expected_common}" not in native_session:
            failures.append("linked worktrees did not share repository identity")

        real_git = shutil.which("git")
        custom_repo = root / "custom-hooks"
        custom_repo.mkdir()
        git(custom_repo, "init", "-b", "custom")
        git(custom_repo, "config", "user.name", "self-check")
        git(custom_repo, "config", "user.email", "self-check@example.invalid")
        (custom_repo / ".custom-hooks").mkdir()
        git(custom_repo, "config", "core.hooksPath", ".custom-hooks")
        custom_bin = root / "custom-bin"
        custom_bin.mkdir()
        custom_cli = custom_bin / "codegraph"
        custom_cli.write_text(
            "#!/bin/sh\n"
            "set -eu\n"
            "case \"$1\" in\n"
            "  init) target=\"$2\"; action=init ;;\n"
            "  sync) target=\"$3\"; action=sync ;;\n"
            "  status) target=\"$3\"; printf '{\"initialized\":true,\"projectPath\":\"%s\",\"pendingChanges\":{\"added\":0,\"modified\":0,\"removed\":0}}\\n' \"$target\"; exit 0 ;;\n"
            "  *) exit 2 ;;\n"
            "esac\n"
            "/bin/mkdir -p \"$target/.codegraph\" \"$target/.custom-hooks\"\n"
            "printf 'SQLite format 3\\000%s\\n' \"$action\" > \"$target/.codegraph/codegraph.db\"\n"
            "printf '#!/bin/sh\\n' > \"$target/.custom-hooks/post-commit\"\n"
            "exit 0\n",
            encoding="utf-8",
        )
        custom_cli.chmod(0o755)
        if real_git:
            (custom_bin / "git").symlink_to(real_git)
        custom_session, _, stderr = run(
            "SessionStart",
            custom_repo,
            path_override=str(custom_bin) + os.pathsep + os.environ.get("PATH", ""),
        )
        if stderr or not isinstance(custom_session, str) or any(
            item not in custom_session
            for item in (
                "status=needs-agent",
                "needs-agent=true",
                "failure=git-hook-write",
                "git-hooks-dir=",
            )
        ):
            failures.append("core.hooksPath fixture did not reject a custom Git hook write")


        native_subagent, _, stderr = run("SubagentStart", repo)
        if stderr or not isinstance(native_subagent, dict) or native_subagent.get("hookSpecificOutput", {}).get("hookEventName") != "SubagentStart":
            failures.append("native SubagentStart protocol/event is invalid")
        elif any(
            item not in native_subagent["hookSpecificOutput"].get("additionalContext", "")
            for item in ("status=cli-only", "worktree=", "cli=", "index=", "mcp=unknown", "observed", "inferred", "unknown")
        ):
            failures.append("native SubagentStart omitted reduced evidence rules")
        elif "action=none" not in native_subagent["hookSpecificOutput"].get("additionalContext", "") or "does not run init or sync" not in native_subagent["hookSpecificOutput"].get("additionalContext", ""):
            failures.append("native SubagentStart unexpectedly performed lifecycle work")

        codex, _, stderr = run("SessionStart", repo, plugin_data=root / "plugin-data")
        if stderr or not isinstance(codex, dict) or codex.get("systemMessage") != "CodeAtlas: ready":
            failures.append("Codex protocol/systemMessage is invalid")
        elif codex.get("hookSpecificOutput", {}).get("hookEventName") != "SessionStart":
            failures.append("Codex SessionStart hook event is invalid")
        elif "mcp=unknown" not in codex["hookSpecificOutput"].get("additionalContext", ""):
            failures.append("Codex SessionStart omitted MCP unknown evidence")

        no_cli_bin = root / "no-cli-bin"
        no_cli_bin.mkdir()
        if real_git:
            (no_cli_bin / "git").symlink_to(real_git)
        missing_cli, _, stderr = run("SessionStart", repo, path_override=str(no_cli_bin))
        if stderr or not isinstance(missing_cli, str) or "status=unavailable" not in missing_cli or "needs-agent=true" not in missing_cli or "@colbymchenry/codegraph" not in missing_cli:
            failures.append("missing CLI fixture did not report unavailable")

        partial = root / "partial"
        partial.mkdir()
        git(partial, "init", "-b", "partial")
        git(partial, "config", "user.name", "self-check")
        git(partial, "config", "user.email", "self-check@example.invalid")
        (partial / ".codegraph").mkdir()
        partial_index, _, stderr = run("SessionStart", partial)
        if stderr or not isinstance(partial_index, str) or any(item not in partial_index for item in ("status=ready", "needs-agent=false", "action=init", "index-state=ready")):
            failures.append("missing index fixture did not retry init")

        corrupt = root / "corrupt"
        corrupt.mkdir()
        git(corrupt, "init", "-b", "corrupt")
        git(corrupt, "config", "user.name", "self-check")
        git(corrupt, "config", "user.email", "self-check@example.invalid")
        (corrupt / ".codegraph").mkdir()
        corrupt_db = corrupt / ".codegraph" / "codegraph.db"
        corrupt_db.write_bytes(b"not-a-sqlite-database\n")
        corrupt_before = corrupt_db.read_bytes()
        corrupt_result, _, stderr = run("SessionStart", corrupt)
        if stderr or not isinstance(corrupt_result, str) or any(item not in corrupt_result for item in ("status=needs-agent", "needs-agent=true", "failure=corrupt-index", "用户确认隔离/重建")):
            failures.append("corrupt index fixture did not report needs-agent takeover")
        elif corrupt_db.read_bytes() != corrupt_before:
            failures.append("corrupt index fixture was overwritten without authorization")

        locked = root / "locked"
        locked.mkdir()
        git(locked, "init", "-b", "locked")
        git(locked, "config", "user.name", "self-check")
        git(locked, "config", "user.email", "self-check@example.invalid")
        (locked / ".codegraph").mkdir()
        (locked / ".codegraph" / "codegraph.db").write_bytes(b"SQLite format 3\x00stable\n")
        lock_file = locked / ".codegraph" / "codegraph.lock"
        lock_file.write_text(f"{os.getpid()}\n", encoding="utf-8")
        # A live owner remains active even when the lock mtime is old.
        old = time.time() - 10 * 60
        os.utime(lock_file, (old, old))
        locked_result, _, stderr = run("SessionStart", locked)
        if stderr or not isinstance(locked_result, str) or any(item not in locked_result for item in ("status=needs-agent", "needs-agent=true", "lock=active", "failure=lock-conflict", "PID")):
            failures.append("active-lock fixture did not report needs-agent without running sync")
        elif (locked / ".codegraph" / "codegraph.db").read_bytes() != b"SQLite format 3\x00stable\n":
            failures.append("active-lock fixture modified the index")

        zero_bin = root / "zero-sync-bin"
        zero_bin.mkdir()
        zero_cli = zero_bin / "codegraph"
        zero_cli.write_text(
            "#!/bin/sh\n"
            "set -eu\n"
            "case \"$1\" in\n"
            "  sync) exit 0 ;;\n"
            "  status) target=\"$3\"; printf '{\"initialized\":true,\"projectPath\":\"%s\",\"pendingChanges\":{\"added\":0,\"modified\":1,\"removed\":0}}\\n' \"$target\"; exit 0 ;;\n"
            "  *) exit 2 ;;\n"
            "esac\n",
            encoding="utf-8",
        )
        zero_cli.chmod(0o755)
        if real_git:
            (zero_bin / "git").symlink_to(real_git)
        zero_result, _, stderr = run(
            "SessionStart",
            repo,
            path_override=str(zero_bin) + os.pathsep + os.environ.get("PATH", ""),
        )
        if stderr or not isinstance(zero_result, str) or any(
            item not in zero_result
            for item in ("status=needs-agent", "failure=status-pending", "pendingChanges")
        ):
            failures.append("zero-shape/race fixture incorrectly reported ready")

        mismatch_bin = root / "mismatch-status-bin"
        mismatch_bin.mkdir()
        mismatch_cli = mismatch_bin / "codegraph"
        mismatch_cli.write_text(
            "#!/bin/sh\n"
            "set -eu\n"
            "case \"$1\" in\n"
            "  sync) exit 0 ;;\n"
            "  status) target=\"$3\"; printf '{\"initialized\":true,\"projectPath\":\"%s\",\"indexPath\":\"%s/.codegraph/other.db\",\"pendingChanges\":{\"added\":0,\"modified\":0,\"removed\":0}}\\n' \"$target\" \"$target\"; exit 0 ;;\n"
            "  *) exit 2 ;;\n"
            "esac\n",
            encoding="utf-8",
        )
        mismatch_cli.chmod(0o755)
        if real_git:
            (mismatch_bin / "git").symlink_to(real_git)
        mismatch_result, _, stderr = run(
            "SessionStart",
            repo,
            path_override=str(mismatch_bin) + os.pathsep + os.environ.get("PATH", ""),
        )
        if stderr or not isinstance(mismatch_result, str) or any(
            item not in mismatch_result
            for item in ("status=needs-agent", "failure=status-index-path")
        ):
            failures.append("status index-path mismatch fixture incorrectly reported ready")

        subagent_missing = root / "subagent-missing"
        subagent_missing.mkdir()
        git(subagent_missing, "init", "-b", "subagent")
        git(subagent_missing, "config", "user.name", "self-check")
        git(subagent_missing, "config", "user.email", "self-check@example.invalid")
        subagent_before = file_snapshot(subagent_missing)
        subagent_missing_result, _, stderr = run("SubagentStart", subagent_missing)
        subagent_after = file_snapshot(subagent_missing)
        if stderr or not isinstance(subagent_missing_result, dict) or any(item not in subagent_missing_result["hookSpecificOutput"].get("additionalContext", "") for item in ("needs-agent=true", "codegraph init", "does not run init or sync")):
            failures.append("SubagentStart missing-index fixture omitted takeover context")
        elif subagent_after != subagent_before:
            failures.append("SubagentStart created or modified the missing index")

        slow_bin = root / "slow-bin"
        slow_bin.mkdir()
        slow_cli = slow_bin / "codegraph"
        grandchild_pid = root / "grandchild.pid"
        grandchild_code = (
            "const fs=require('node:fs'); "
            "fs.writeFileSync(process.argv[1], String(process.pid)); "
            "setTimeout(() => {}, 60000);"
        )
        slow_cli.write_text(
            "#!/bin/sh\n"
            f"{shlex.quote(node_path)} -e {shlex.quote(grandchild_code)} {shlex.quote(str(grandchild_pid))} &\n"
            "wait $!\n",
            encoding="utf-8",
        )
        slow_cli.chmod(0o755)
        if real_git:
            (slow_bin / "git").symlink_to(real_git)
        timed_out, _, stderr = run(
            "SessionStart",
            repo,
            path_override=str(slow_bin),
            extra_env={"CODEATLAS_HOOK_TIMEOUT_MS": "50"},
        )
        if stderr or not isinstance(timed_out, str) or any(item not in timed_out for item in ("status=needs-agent", "needs-agent=true", "50ms", "codegraph sync --quiet")):
            failures.append("timeout fixture did not report bounded needs-agent takeover")
        grandchild_deadline = time.monotonic() + 2
        grandchild_alive = True
        grandchild_value = ""
        while time.monotonic() < grandchild_deadline:
            if grandchild_pid.exists():
                grandchild_value = grandchild_pid.read_text(encoding="utf-8").strip()
                try:
                    os.kill(int(grandchild_value), 0)
                except (ProcessLookupError, ValueError, PermissionError):
                    grandchild_alive = False
                    break
            else:
                grandchild_alive = False
            time.sleep(0.02)
        if grandchild_alive:
            failures.append(f"timeout left orphan grandchild PID {grandchild_value or 'unknown'}")
            if grandchild_value.isdigit():
                try:
                    os.kill(int(grandchild_value), 9)
                except OSError:
                    pass

        non_git = root / "non-git"
        non_git.mkdir()
        nongit, _, stderr = run("SubagentStart", non_git)
        if stderr or not isinstance(nongit, dict) or nongit.get("hookSpecificOutput", {}).get("hookEventName") != "SubagentStart":
            failures.append("non-Git SubagentStart did not fail closed")
        elif "needs-agent=true" not in nongit["hookSpecificOutput"].get("additionalContext", ""):
            failures.append("non-Git SubagentStart omitted needs-agent state")
        after_files = file_snapshot(repo)
        after_hooks = git_hook_snapshot(repo)
        if not allowed_runtime_changes(before_files, after_files):
            failures.append("runner changed files outside .codegraph/.gitignore")
        if before_hooks != after_hooks:
            failures.append("runner changed shared Git hooks")


def run_self_test(
    validate_skills,
    version_bump_errors,
    validate_plugins,
    validate_marketplace,
) -> list[str]:
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        check_skills(root, validate_skills, version_bump_errors, failures)
        check_historical_skill_migration(root, validate_skills, version_bump_errors, failures)
        check_plugins(root, validate_plugins, failures)
        check_npx_readmes(root, failures)
        check_marketplace_identity(root, validate_marketplace, failures)
    check_code_atlas_hook_runtime(failures)
    return failures


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    ).stdout.strip()


def commit_all(root: Path, message: str) -> str:
    git(root, "add", "-A")
    git(root, "commit", "-m", message)
    return git(root, "rev-parse", "HEAD")
