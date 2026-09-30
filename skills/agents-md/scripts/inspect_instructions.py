#!/usr/bin/env python3
"""只读盘点仓库指令候选；不执行仓库代码、不访问网络、不推断宿主加载。"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

NAMES = {"AGENTS.md", "AGENTS.override.md", "CLAUDE.md", "CLAUDE.local.md"}
DEFAULT_EXCLUDES = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", "target", "dist",
    "build", ".next", ".cache", ".mypy_cache", ".pytest_cache", ".tox",
}
SENSITIVE_PARTS = {".ssh", ".gnupg", "secrets", "credentials"}
SENSITIVE_FILES = {"auth.json", "credentials.json", "token.json", "tokens.json"}
MD_LINK = re.compile(r'!?\[[^\]\n]*\]\((<[^>\n]+>|[^\s)]+)(?:\s+[\"\'][^\n]*?[\"\'])?\)')
IMPORT = re.compile(r"^\s*@([^\s]+)\s*$")
FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")


def inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def sensitive(path: Path) -> bool:
    return (any(p.lower() in SENSITIVE_PARTS or p.lower().startswith(".env") for p in path.parts)
            or path.name.lower() in SENSITIVE_FILES)


def reparse(path: Path) -> bool:
    """Windows 连接点也视为不可递归的链接。"""
    try:
        value = path.lstat()
        return (stat.S_ISLNK(value.st_mode)
                or bool(getattr(value, "st_file_attributes", 0)
                        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)))
    except OSError:
        return False


def visible_lines(text: str):
    """保留原始行号，忽略 fenced code；不是完整 Markdown 解析器。"""
    active = None
    for number, line in enumerate(text.splitlines(), 1):
        match = FENCE.match(line)
        if match:
            marks = match.group(1)
            if active is None:
                active = (marks[0], len(marks))
            elif marks[0] == active[0] and len(marks) >= active[1] and not line[match.end():].strip():
                active = None
            continue
        if active is None:
            yield number, line


def local_reference(raw: str, source: Path, root: Path) -> dict:
    """只检查目标是否存在；绝不读取引用目标或请求外部地址。"""
    raw = raw.strip("<>")
    try:
        url = urlsplit(raw)
    except ValueError:
        return {"status": "unparsed", "note": "目标格式无法解析，未输出原始值"}
    if url.scheme or url.netloc:
        return {"status": "external_not_checked"}
    if not url.path:
        return {"status": "anchor_not_checked"}
    if url.query:
        return {"status": "query_reference_not_checked"}
    decoded = unquote(url.path)
    if any(ord(char) < 32 for char in decoded):
        return {"status": "unparsed", "note": "目标包含控制字符"}
    if "\\" in decoded:
        return {"status": "platform_path_not_checked"}
    target = Path(decoded)
    if target.is_absolute() or decoded.startswith("~"):
        return {"status": "absolute_not_checked"}
    if sensitive(target):
        return {"status": "sensitive_target_not_checked"}
    try:
        resolved = (source.parent / target).resolve()
        if not inside(resolved, root):
            return {"status": "outside_root_not_checked"}
        if sensitive(resolved.relative_to(root)):
            return {"status": "sensitive_target_not_checked"}
        result = {"target": decoded, "resolved": resolved.relative_to(root).as_posix(),
                  "status": "exists" if resolved.exists() else "missing"}
        if url.fragment:
            result["anchor"] = "not_checked"
        return result
    except (OSError, RuntimeError, ValueError):
        return {"status": "unresolvable", "note": "路径不可解析或存在链接循环"}


def inspect_file(path: Path, root: Path, max_bytes: int) -> dict:
    relative = path.relative_to(root)
    item = {"path": relative.as_posix(), "name_is_canonical": path.name in NAMES,
            "link": reparse(path), "role": "requires_context_review"}
    if set(p.lower() for p in relative.parts) & {"examples", "fixtures", "templates", "tests", "test", "skills"}:
        item["role_hint"] = "可能为示例、测试或产品内容；不能据此确定加载作用域"
    try:
        target = path.resolve(strict=True)
        if not inside(target, root):
            item["status"] = "outside_root_not_read"
            return item
        if sensitive(target.relative_to(root)):
            item["status"] = "sensitive_target_not_read"
            return item
        if target.suffix.lower() not in {".md", ".markdown", ".mdx", ".txt"}:
            item["status"] = "unsupported_target_not_read"
            return item
        if not target.is_file():
            item["status"] = "missing_or_nonfile"
            return item
        item["resolved"] = target.relative_to(root).as_posix()
        with target.open("rb") as handle:
            data = handle.read(max_bytes + 1)
        if len(data) > max_bytes:
            item["status"] = "size_limit_not_read"
            item["bytes_at_least"] = len(data)
            return item
        item["bytes"] = len(data)
        text = data.decode("utf-8")
        item["lines"] = len(text.splitlines())
        item["sha256"] = hashlib.sha256(data).hexdigest()
        item["status"] = "read"
        item["references"] = []
        for number, line in visible_lines(text):
            for match in MD_LINK.finditer(line):
                info = local_reference(match.group(1), target, root)
                item["references"].append({"line": number, "kind": "markdown_link", **info})
            match = IMPORT.match(line)
            if match:
                info = local_reference(match.group(1), target, root)
                item["references"].append({"line": number, "kind": "standalone_at_reference", **info})
        return item
    except FileNotFoundError:
        item["status"] = "missing_or_nonfile"
    except UnicodeDecodeError:
        item["status"] = "invalid_utf8"
    except (OSError, RuntimeError, ValueError):
        item["status"] = "unreadable_or_link_cycle"
    return item


def inspect(root: Path, *, max_bytes: int = 262144, max_entries: int = 20000,
            extra_excludes: tuple[str, ...] = ()) -> dict:
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise ValueError("指定根目录不存在或不是目录")
    if max_bytes < 1 or max_entries < 1:
        raise ValueError("扫描上限必须为正整数")
    excluded = DEFAULT_EXCLUDES | set(extra_excludes)
    output = {
        "format": "agents-md.inventory.v1", "root": str(root),
        "read_only": True, "network_used": False,
        "excluded_directory_names": sorted(excluded | SENSITIVE_PARTS),
        "limits": {"max_file_bytes": max_bytes, "max_directory_entries": max_entries},
        "visited_entries": 0, "scan_limit_hit": False, "diagnostics": [],
        "instruction_files": [],
        "limitations": [
            "不是完整 Markdown 解析器；不检查引用式链接、行内导入、标题锚点或代码块中的路径",
            "不解析 .gitignore；不递归链接目录；默认排除依赖、构建、缓存与敏感目录",
            "不递归读取被引用文档；不检查秘密内容、命令语义、权限、指令优先级或实际宿主加载",
            "候选角色与重复正文均需人工判断；名称匹配不表示文件应被执行或应用",
            "引用相对链接按已解析的物理文件位置检查；宿主对链接别名的解析可能不同",
            "面向静态受控工作树；不能替代抵御并发恶意文件替换的操作系统沙箱",
        ],
    }
    stack = [root]
    folded_names = {name.casefold() for name in NAMES}
    while stack and not output["scan_limit_hit"]:
        directory = stack.pop()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    if output["visited_entries"] >= max_entries:
                        output["scan_limit_hit"] = True
                        break
                    output["visited_entries"] += 1
                    path = Path(entry.path)
                    rel = path.relative_to(root)
                    if sensitive(rel):
                        continue
                    if entry.name.casefold() in folded_names:
                        output["instruction_files"].append(inspect_file(path, root, max_bytes))
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name not in excluded and not reparse(path):
                            stack.append(path)
        except OSError:
            output["diagnostics"].append({"path": directory.relative_to(root).as_posix(),
                                          "status": "directory_unreadable"})
    output["instruction_files"].sort(key=lambda item: item["path"])
    hashes = {}
    for item in output["instruction_files"]:
        if "sha256" in item:
            hashes.setdefault(item["sha256"], []).append(item["path"])
    output["same_content_groups"] = [paths for _, paths in sorted(hashes.items()) if len(paths) > 1]
    output["missing_reference_count"] = sum(
        ref["status"] == "missing" for item in output["instruction_files"]
        for ref in item.get("references", []))
    return output


def positive(value: str) -> int:
    try:
        number = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("必须是正整数") from error
    if number < 1:
        raise argparse.ArgumentTypeError("必须是正整数")
    return number


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="仅扫描明确指定的仓库目录")
    parser.add_argument("--max-bytes", type=positive, default=262144, help="单候选文件读取上限，不是 AGENTS.md 标准")
    parser.add_argument("--max-entries", type=positive, default=20000, help="目录条目扫描上限")
    parser.add_argument("--exclude-dir", action="append", default=[], help="额外排除的目录名，可重复")
    args = parser.parse_args()
    try:
        result = inspect(args.root, max_bytes=args.max_bytes, max_entries=args.max_entries,
                         extra_excludes=tuple(args.exclude_dir))
    except (ValueError, OSError, RuntimeError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
