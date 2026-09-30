"""只读盘点器的确定性测试；不测试真实 Agent 的指令遵循率。"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "inspect_instructions.py"
SPEC = importlib.util.spec_from_file_location("inventory", SCRIPT)
inventory = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inventory)


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, path: str, text: str = "# 指令\n") -> Path:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return target

    def scan(self, **kwargs):
        return inventory.inspect(self.root, **kwargs)

    def one(self):
        return self.scan()["instruction_files"][0]

    def link(self, name: str, target: Path, directory: bool = False):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.symlink_to(target, target_is_directory=directory)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f"当前环境不支持符号链接: {error}")
        return path

    def test_empty_repo(self):
        self.assertEqual(self.scan()["instruction_files"], [])

    def test_root_and_nested_names(self):
        for path in ["AGENTS.md", "模块/CLAUDE.md", "模块/AGENTS.override.md", "CLAUDE.local.md"]:
            self.write(path)
        self.assertEqual(len(self.scan()["instruction_files"]), 4)

    def test_case_variant_is_not_claimed_canonical(self):
        self.write("agents.MD")
        self.assertFalse(self.one()["name_is_canonical"])

    def test_utf8_counts_and_hash(self):
        text = "# 项目\n保持原约束。\n"
        self.write("AGENTS.md", text)
        got = self.one()
        self.assertEqual(got["bytes"], len(text.encode()))
        self.assertEqual(got["lines"], 2)
        self.assertEqual(got["sha256"], hashlib.sha256(text.encode()).hexdigest())

    def test_default_exclusions(self):
        for name in [".git", "node_modules", "target", ".venv", "dist"]:
            self.write(f"{name}/AGENTS.md")
        self.write("src/AGENTS.md")
        self.assertEqual([x["path"] for x in self.scan()["instruction_files"]], ["src/AGENTS.md"])

    def test_extra_exclusion(self):
        self.write("vendor/AGENTS.md")
        self.assertEqual(self.scan(extra_excludes=("vendor",))["instruction_files"], [])

    def test_sensitive_directories_are_not_descended(self):
        for name in ["secrets", ".ssh", "credentials", ".env.backups"]:
            self.write(f"{name}/AGENTS.md")
        self.assertEqual(self.scan()["instruction_files"], [])

    def test_existing_and_missing_links(self):
        self.write("AGENTS.md", "[设计](docs/design.md)\n[缺失](missing.md)\n")
        self.write("docs/design.md")
        got = self.scan()
        self.assertEqual([r["status"] for r in got["instruction_files"][0]["references"]], ["exists", "missing"])
        self.assertEqual(got["missing_reference_count"], 1)

    def test_reference_uses_source_directory(self):
        self.write("src/AGENTS.md", "[规范](../docs/design.md)\n")
        self.write("docs/design.md")
        self.assertEqual(self.one()["references"][0]["resolved"], "docs/design.md")

    def test_standalone_at_import(self):
        self.write("CLAUDE.md", "@AGENTS.md\n")
        self.write("AGENTS.md")
        claude = next(x for x in self.scan()["instruction_files"] if x["path"] == "CLAUDE.md")
        self.assertEqual(claude["references"][0]["kind"], "standalone_at_reference")
        self.assertEqual(claude["references"][0]["status"], "exists")

    def test_code_fences_are_not_parsed(self):
        self.write("AGENTS.md", "```md\n[示例](absent.md)\n@absent.md\n```\n~~~sh\n@also-absent.md\n~~~\n")
        self.assertEqual(self.one()["references"], [])

    def test_long_fence_requires_matching_close(self):
        self.write("AGENTS.md", "````md\n```\n[示例](absent.md)\n````\n[缺失](real-missing.md)\n")
        refs = self.one()["references"]
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0]["line"], 5)

    def test_url_not_fetched_or_echoed(self):
        self.write("AGENTS.md", "[外部](https://example.invalid/private?token=DO-NOT-ECHO)\n")
        result = self.scan()
        self.assertEqual(result["instruction_files"][0]["references"][0]["status"], "external_not_checked")
        self.assertNotIn("DO-NOT-ECHO", json.dumps(result))
        self.assertFalse(result["network_used"])

    def test_anchor_is_not_claimed_checked(self):
        self.write("AGENTS.md", "[本页](#not-real)\n[章节](doc.md#not-real)\n")
        self.write("doc.md")
        refs = self.one()["references"]
        self.assertEqual(refs[0]["status"], "anchor_not_checked")
        self.assertEqual(refs[1]["status"], "exists")
        self.assertEqual(refs[1]["anchor"], "not_checked")

    def test_query_reference_not_echoed(self):
        self.write("AGENTS.md", "[本地](doc.md?secret=DO-NOT-ECHO)\n")
        self.assertNotIn("DO-NOT-ECHO", json.dumps(self.scan()))
        self.assertEqual(self.one()["references"][0]["status"], "query_reference_not_checked")

    def test_urlencoded_spaces(self):
        self.write("docs/a b.md")
        self.write("AGENTS.md", "[有空格](docs/a%20b.md)\n")
        self.assertEqual(self.one()["references"][0]["status"], "exists")

    def test_angle_bracket_link(self):
        self.write("docs/a b.md")
        self.write("AGENTS.md", "[有空格](<docs/a b.md>)\n")
        self.assertEqual(self.one()["references"][0]["status"], "exists")

    def test_outside_reference_not_read(self):
        self.write("AGENTS.md", "[外部](../outside.md)\n")
        self.assertEqual(self.one()["references"][0]["status"], "outside_root_not_checked")

    def test_encoded_traversal(self):
        self.write("AGENTS.md", "[外部](%2e%2e/outside.md)\n")
        self.assertEqual(self.one()["references"][0]["status"], "outside_root_not_checked")

    def test_absolute_and_home_paths(self):
        self.write("AGENTS.md", "[绝对](/tmp/example.md)\n[主目录](~/private.md)\n")
        self.assertTrue(all(r["status"] == "absolute_not_checked" for r in self.one()["references"]))

    def test_sensitive_references_not_inspected(self):
        self.write("AGENTS.md", "[敏感](.env)\n[密钥](credentials/auth.json)\n")
        self.assertTrue(all(r["status"] == "sensitive_target_not_checked" for r in self.one()["references"]))

    def test_invalid_utf8(self):
        (self.root / "AGENTS.md").write_bytes(b"\xff\xfe")
        self.assertEqual(self.one()["status"], "invalid_utf8")

    def test_size_limit(self):
        self.write("AGENTS.md", "A" * 40)
        got = self.scan(max_bytes=10)["instruction_files"][0]
        self.assertEqual(got["status"], "size_limit_not_read")
        self.assertNotIn("sha256", got)

    def test_entry_limit_reports_partial_scan(self):
        self.write("AGENTS.md")
        self.write("CLAUDE.md")
        got = self.scan(max_entries=1)
        self.assertTrue(got["scan_limit_hit"])
        self.assertEqual(got["visited_entries"], 1)

    def test_same_body_is_candidate_not_error(self):
        self.write("AGENTS.md", "# 相同\n")
        self.write("src/AGENTS.md", "# 相同\n")
        got = self.scan()
        self.assertEqual(got["same_content_groups"], [["AGENTS.md", "src/AGENTS.md"]])
        self.assertNotIn("quality_score", got)

    def test_symlink_inside(self):
        target = self.write("AGENTS.md")
        self.link("CLAUDE.md", target)
        got = self.scan()
        claude = next(x for x in got["instruction_files"] if x["path"] == "CLAUDE.md")
        self.assertTrue(claude["link"])
        self.assertEqual(claude["resolved"], "AGENTS.md")
        self.assertEqual(got["same_content_groups"], [["AGENTS.md", "CLAUDE.md"]])

    def test_symlink_outside(self):
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / "private.md"
            target.write_text("never-read", encoding="utf-8")
            self.link("AGENTS.md", target)
            got = self.one()
            self.assertEqual(got["status"], "outside_root_not_read")
            self.assertNotIn("sha256", got)

    def test_symlink_sensitive(self):
        target = self.write("secrets/private.md", "never-read")
        self.link("AGENTS.md", target)
        self.assertEqual(self.one()["status"], "sensitive_target_not_read")

    def test_symlink_unsupported_target(self):
        target = self.write("payload.py", "raise RuntimeError('not run')")
        self.link("AGENTS.md", target)
        self.assertEqual(self.one()["status"], "unsupported_target_not_read")

    def test_directory_symlink_not_traversed(self):
        self.write("real/AGENTS.md")
        self.link("shortcut", self.root / "real", directory=True)
        self.assertEqual([x["path"] for x in self.scan()["instruction_files"]], ["real/AGENTS.md"])

    def test_symlink_cycle(self):
        self.link("AGENTS.md", self.root / "CLAUDE.md")
        self.link("CLAUDE.md", self.root / "AGENTS.md")
        self.assertTrue(all(x["status"] == "unreadable_or_link_cycle" for x in self.scan()["instruction_files"]))

    def test_broken_symlink(self):
        self.link("AGENTS.md", self.root / "missing.md")
        self.assertEqual(self.one()["status"], "missing_or_nonfile")

    def test_role_hint_does_not_grant_authority(self):
        self.write("examples/demo/CLAUDE.md", "# 虚构示例上下文\n")
        got = self.one()
        self.assertEqual(got["role"], "requires_context_review")
        self.assertIn("role_hint", got)

    def test_no_writes_or_embedded_command_execution(self):
        self.write("AGENTS.md", "```sh\ntouch CREATED-BY-MARKDOWN\n```\n[引用](payload.md)\n")
        self.write("payload.md", "不用执行本文件。\n")
        def snapshot():
            return {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        before = snapshot()
        self.scan()
        self.assertEqual(before, snapshot())
        self.assertFalse((self.root / "CREATED-BY-MARKDOWN").exists())

    def test_invalid_root(self):
        with self.assertRaises(ValueError):
            inventory.inspect(self.root / "absent")

    def test_invalid_limits(self):
        with self.assertRaises(ValueError):
            self.scan(max_entries=0)
        with self.assertRaises(ValueError):
            self.scan(max_bytes=0)

    def test_cli_json_and_no_worktree_write(self):
        self.write("AGENTS.md")
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), "--root", str(self.root)],
                                capture_output=True, text=True, check=False, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["read_only"])
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["AGENTS.md"])

    def test_cli_invalid_root_exit_two(self):
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), "--root", str(self.root / "absent")],
                                capture_output=True, text=True, check=False, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertIn("error", json.loads(result.stderr))


if __name__ == "__main__":
    unittest.main()
