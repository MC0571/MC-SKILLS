"""本包自身的静态检查；不是通用 AGENTS.md schema 检查器。"""
from __future__ import annotations

import ast
import json
from pathlib import Path, PurePosixPath
import re
import unittest
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def prose_lines(text):
    fence = None
    for line in text.splitlines():
        match = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if match:
            token = match.group(1)
            if fence is None:
                fence = (token[0], len(token))
            elif token[0] == fence[0] and len(token) >= fence[1] and not line[match.end():].strip():
                fence = None
            continue
        if fence is None:
            yield line


class PackageTests(unittest.TestCase):
    def test_required_files(self):
        for path in ["SKILL.md", "README.md", "agents/openai.yaml", "references/discovery.md",
                     "references/rule-design.md", "references/validation.md", "references/patterns.md",
                     "scripts/inspect_instructions.py", "evals/README.md", "evals/cases.json",
                     "research/repository-analysis.md", "research/sources.json", "research/validation-report.md"]:
            with self.subTest(path=path):
                self.assertTrue((ROOT / path).is_file())

    def test_frontmatter_name_and_description(self):
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"))
        header, body = text[4:].split("\n---\n", 1)
        values = dict(line.split(": ", 1) for line in header.splitlines() if line.startswith(("name: ", "description: ")))
        self.assertEqual(values["name"], ROOT.name)
        self.assertRegex(values["name"], r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
        self.assertLessEqual(len(values["name"]), 64)
        self.assertTrue(1 <= len(values["description"]) <= 1024)
        self.assertIn("普通编码", values["description"])
        self.assertIn("不主动触发", values["description"])
        self.assertTrue(body.strip())

    def test_ui_metadata_is_present(self):
        text = (ROOT / "agents/openai.yaml").read_text(encoding="utf-8")
        for field in ["interface:", "display_name:", "short_description:", "default_prompt:",
                      "policy:", "allow_implicit_invocation:"]:
            self.assertIn(field, text)
        self.assertIn("$agents-md", text)
        self.assertNotIn("dependencies:", text)

    def test_local_markdown_link_targets(self):
        pattern = re.compile(r"\[[^\]\n]*\]\(([^\s)]+)\)")
        checked = 0
        for path in ROOT.rglob("*.md"):
            for line in prose_lines(path.read_text(encoding="utf-8")):
                for match in pattern.finditer(line):
                    url = urlsplit(match.group(1))
                    if url.scheme or url.netloc or not url.path:
                        continue
                    target = (path.parent / unquote(url.path)).resolve()
                    with self.subTest(source=str(path.relative_to(ROOT)), target=url.path):
                        self.assertTrue(target.is_relative_to(ROOT))
                        self.assertTrue(target.exists())
                    checked += 1
        self.assertGreater(checked, 10)

    def test_evaluation_cases_are_safe_fixture_definitions(self):
        data = json.loads((ROOT / "evals/cases.json").read_text(encoding="utf-8"))
        self.assertFalse(data["behavioral_runs_performed"])
        cases = data["cases"]
        self.assertEqual(len(cases), 16)
        self.assertEqual(len(set(case["id"] for case in cases)), len(cases))
        for case in cases:
            self.assertTrue(case["synthetic"])
            for field in ["prompt", "expected", "forbidden", "observable_oracle", "files"]:
                self.assertTrue(case[field])
            for filename, text in case["files"].items():
                path = PurePosixPath(filename)
                self.assertFalse(path.is_absolute())
                self.assertNotIn("..", path.parts)
                self.assertNotIn("\\", filename)
                self.assertIsInstance(text, str)

    def test_source_records_are_pinned_and_scoped(self):
        data = json.loads((ROOT / "research/sources.json").read_text(encoding="utf-8"))
        self.assertEqual(len(data["repositories"]), 7)
        self.assertEqual(data["research_date"], "2026-09-30")
        for repo in data["repositories"]:
            self.assertRegex(repo["reference_commit"], r"^[a-f0-9]{40}$")
            for source in repo["files"]:
                self.assertIn(repo["reference_commit"], source["url"])
                self.assertTrue(source["read_coverage"])

    def test_python_files_parse_as_python310(self):
        for path in ROOT.rglob("*.py"):
            with self.subTest(path=str(path.relative_to(ROOT))):
                ast.parse(path.read_text(encoding="utf-8"), feature_version=(3, 10))

    def test_inventory_has_no_network_or_process_dependencies(self):
        tree = ast.parse((ROOT / "scripts/inspect_instructions.py").read_text(encoding="utf-8"))
        allowed = {"__future__", "argparse", "hashlib", "json", "os", "re", "stat", "sys", "pathlib", "urllib.parse"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertTrue(all(alias.name in allowed for alias in node.names))
            if isinstance(node, ast.ImportFrom):
                self.assertIn(node.module, allowed)
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    self.assertNotIn(node.func.id, {"eval", "exec", "compile", "__import__"})
                if isinstance(node.func, ast.Attribute):
                    self.assertNotIn(node.func.attr, {"write_text", "write_bytes", "unlink", "rmdir", "mkdir", "system", "popen"})

    def test_text_files_are_utf8_with_trailing_newline(self):
        for path in ROOT.rglob("*"):
            if path.is_file() and path.suffix in {".md", ".py", ".json", ".yaml"}:
                with self.subTest(path=str(path.relative_to(ROOT))):
                    data = path.read_bytes()
                    data.decode("utf-8")
                    self.assertTrue(data.endswith(b"\n"))
                    self.assertNotIn(b"\x00", data)


if __name__ == "__main__":
    unittest.main()
