#!/usr/bin/env python3
"""Build the publish matrix for changed standalone Skills."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from repository_artifacts import changed_skill_matrix


def select_skill(result: dict, skill_name: str) -> dict:
    """Filter a release result only after checking the name against its full matrix."""
    include = result["matrix"]["include"]
    if skill_name and not any(item["name"] == skill_name for item in include):
        raise ValueError(f"skill_name is not in the release Skill matrix: {skill_name!r}")
    selected = [item for item in include if not skill_name or item["name"] == skill_name]
    return {**result, "matrix": {**result["matrix"], "include": selected}}


def run_self_test() -> None:
    full = {
        "matrix": {
            "include": [
                {"name": "alpha", "path": "skills/alpha", "version": "1.0.0"},
                {"name": "beta", "path": "skills/beta", "version": "2.0.0"},
            ]
        }
    }
    assert len(select_skill(full, "")["matrix"]["include"]) == 2
    assert select_skill(full, "beta")["matrix"]["include"] == [
        {"name": "beta", "path": "skills/beta", "version": "2.0.0"}
    ]
    try:
        select_skill(full, "missing")
    except ValueError as exc:
        assert "not in the release Skill matrix" in str(exc)
    else:
        raise AssertionError("an unchanged Skill was accepted for retry")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", help="base Git ref or the all-zero SHA")
    parser.add_argument("--target", help="target Git ref")
    parser.add_argument("--skill-name", default="", help="filter to a Skill in the full changed matrix")
    parser.add_argument("--github-output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    try:
        if args.self_test:
            run_self_test()
            print("Skill release matrix self-test passed.")
            return 0
        if not args.base or not args.target:
            parser.error("--base and --target are required")
        result, errors = changed_skill_matrix(Path.cwd(), args.base, args.target)
        result = select_skill(result, args.skill_name)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.github_output:
            with args.github_output.open("a", encoding="utf-8") as output:
                matrix = json.dumps(result["matrix"], separators=(",", ":"))
                output.write(f"matrix={matrix}\n")
                output.write(f"has_changes={'true' if result['matrix']['include'] else 'false'}\n")
                output.write(f"count={len(result['matrix']['include'])}\n")
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return bool(errors)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
