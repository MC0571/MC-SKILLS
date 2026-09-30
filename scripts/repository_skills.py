"""Shared metadata and source validation for standalone skills."""

from __future__ import annotations

from pathlib import Path


SKILLS_SOURCE = (
    "https://github.com/MC-and-his-Agents/MC-AGENT-KIT/tree/main/skills"
)
NPX_ADD_PREFIX = f"npx skills add {SKILLS_SOURCE} --full-depth"

# Source: https://developers.openai.com/plugins/deploy/submission-errors#listing-and-interface-errors
SKILL_CATEGORIES = frozenset(
    {
        "Productivity",
        "Creativity",
        "Developer Tools",
        "Business & Operations",
        "Data & Analytics",
        "Communication",
        "Education & Research",
        "Security",
        "Finance",
        "Healthcare",
        "Travel",
        "Entertainment",
        "Other",
    }
)


def error(path: Path, rule: str, fix: str) -> str:
    return f"{path.as_posix()}: [{rule}] {fix}"


def validate_npx_readmes(root: Path) -> list[str]:
    errors: list[str] = []
    for relative in (Path("README.md"), Path("README.zh-CN.md")):
        path = root / relative
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            valid_source = line == NPX_ADD_PREFIX or line.startswith(
                f"{NPX_ADD_PREFIX} "
            )
            if line.startswith("npx skills add ") and not valid_source:
                errors.append(
                    error(
                        relative,
                        "npx-source-boundary",
                        "use the skills/ source with --full-depth so plugin skills stay private",
                    )
                )
    return errors
