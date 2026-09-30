#!/usr/bin/env python3
"""Stage a release bundle from tracked files in an exact Git tree."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path, PurePosixPath

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


def validate_skillhub_public_state(payload: object, publisher: str, local_version: str) -> str:
    if not isinstance(payload, dict):
        raise BundleError("SkillHub returned no public Skill object")
    owner = payload.get("owner")
    owner_handle = owner.get("handle") if isinstance(owner, dict) else None
    if not isinstance(owner_handle, str) or owner_handle.casefold() != publisher.casefold():
        raise BundleError("visible SkillHub slug is owned by a different publisher")
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


def display_name(text: str, source: str) -> str:
    for line in text.splitlines():
        match = HEADING_PATTERN.fullmatch(line)
        if match:
            return match.group(1).strip()
    raise BundleError(f"{source}: add a top-level Markdown heading for Tencent displayName")


def tencent_frontmatter(text: str, source: str, name: str, version: str) -> str:
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
        "slug": f"mc0571-{name}",
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


def stage_skill(repository: Path, ref: str, skill_path: str, destination: Path, market: str) -> dict:
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
                source = tencent_frontmatter(source, entry.path, skill["name"], skill["version"])
            content = source.encode("utf-8")
            skill_file = target
        target.write_bytes(content)
        if entry.mode == "100755":
            target.chmod(0o755)
    source_text = skill_file.read_text(encoding="utf-8") if skill_file else ""
    slug = f"mc0571-{skill['name']}" if market == "skillhub" else skill["name"]
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
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--github-output", type=Path)
    parser.add_argument("--validate-skillhub-public", type=Path)
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
        if args.validate_skillhub_public:
            if not args.publisher or not args.version:
                parser.error("--publisher and --version are required with --validate-skillhub-public")
            payload = json.loads(args.validate_skillhub_public.read_text(encoding="utf-8"))
            status = validate_skillhub_public_state(payload, args.publisher, args.version)
            print(json.dumps({"status": status}))
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
        result = stage_skill(Path.cwd(), args.ref, args.path, args.destination, args.market)
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

    result_filter = (
        Path(__file__).resolve().parents[1]
        / "skills/skill-release/assets/github-actions/skillhub_publish_result.txt"
    )

    def project_skillhub_result(raw: str, slug: str = "mc0571-sample") -> subprocess.CompletedProcess[str]:
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
        "slug": "mc0571-sample",
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
        assert 'slug: "mc0571-sample"' in staged_text
        assert 'version: "1.2.3"' in staged_text
        assert 'displayName: "Sample Display"' in staged_text
        assert "metadata:\n  version: 1.2.3" in staged_text
        assert result["files"] == 4 and not (tencent / "untracked.txt").exists()
        bundled_filter = tencent / "assets/github-actions/skillhub_publish_result.txt"
        assert bundled_filter.is_file()
        assert not bundled_filter.with_suffix(".jq").exists()
        assert not (tencent / ".DS_Store").exists() and not (tencent / "cache.pyc").exists()
        assert not (tencent / "__pycache__").exists()
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
    public_state = {
        "owner": {"handle": "publisher"},
        "latestVersion": {"version": "1.2.2"},
    }
    assert validate_skillhub_public_state(public_state, "publisher", "1.2.3") == "publish"
    assert validate_skillhub_public_state(
        {"owner": {"handle": "publisher"}, "latestVersion": {"version": "1.2.3"}},
        "publisher",
        "1.2.3",
    ) == "skip"
    assert can_create_after_skillhub_404("push", "1")
    assert not can_create_after_skillhub_404("push", "2")
    assert not can_create_after_skillhub_404("workflow_dispatch", "1")
    assert can_create_after_skillhub_404("workflow_dispatch", "1", "all")
    assert not can_create_after_skillhub_404("workflow_dispatch", "2", "all")
    assert not can_create_after_skillhub_404("workflow_dispatch", "1", "changed")
    for invalid_state, owner, version in (
        (public_state, "another-publisher", "1.2.3"),
        (public_state, "publisher", "1.2.1"),
        ({"owner": {"handle": "publisher"}, "latestVersion": {}}, "publisher", "1.2.3"),
    ):
        try:
            validate_skillhub_public_state(invalid_state, owner, version)
        except BundleError:
            pass
        else:
            raise AssertionError("invalid public SkillHub state was accepted")
    print("Skill release bundle self-test passed.")


if __name__ == "__main__":
    raise SystemExit(main())
