#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List

import yaml

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.skills.skill_inventory import load_target_skills

REQUIRED_DIRECTORIES = ["commands", "scripts", "config", "samples", "references"]
REQUIRED_SECTIONS = [
    "Mission",
    "Use this skill when",
    "Quick Commands",
    "Verification",
    "Failure & Recovery",
]


def parse_frontmatter(markdown_text: str) -> Dict[str, str]:
    if not markdown_text.startswith("---"):
        return {}

    match = re.match(r"^---\n(.*?)\n---\n", markdown_text, flags=re.DOTALL)
    if not match:
        return {}

    content = match.group(1)
    payload = yaml.safe_load(content) or {}
    if not isinstance(payload, dict):
        return {}
    return {str(k): str(v) for k, v in payload.items()}


def validate_skill_dir(skill_dir: Path) -> Dict[str, object]:
    skill_dir = skill_dir.resolve()
    skill_md = skill_dir / "SKILL.md"

    missing_directories: List[str] = []
    missing_sections: List[str] = []

    for directory in REQUIRED_DIRECTORIES:
        if not (skill_dir / directory).is_dir():
            missing_directories.append(directory)

    skill_text = ""
    if skill_md.exists():
        skill_text = skill_md.read_text(encoding="utf-8")
    else:
        missing_sections.extend(REQUIRED_SECTIONS)

    frontmatter = parse_frontmatter(skill_text)
    description = frontmatter.get("description", "")
    description_ok = description.strip().lower().startswith("use when")

    for section in REQUIRED_SECTIONS:
        if f"## {section}" not in skill_text:
            missing_sections.append(section)

    status = "pass"
    if missing_directories or missing_sections or not description_ok:
        status = "fail"

    return {
        "skill": skill_dir.name,
        "path": str(skill_dir),
        "status": status,
        "missingDirectories": sorted(set(missing_directories)),
        "missingSections": sorted(set(missing_sections)),
        "descriptionStartsWithUseWhen": description_ok,
    }


def validate_targets(targets_file: Path, selected_names: List[str] | None = None) -> Dict[str, object]:
    skills = load_target_skills(str(targets_file))
    selected = {name.strip() for name in (selected_names or []) if name.strip()}
    if selected:
        skills = [item for item in skills if item.get("name") in selected]

    results: List[Dict[str, object]] = []
    for skill in skills:
        path = Path(skill["path"])
        results.append(validate_skill_dir(path))

    failed = [item for item in results if item["status"] != "pass"]
    return {
        "status": "pass" if not failed else "fail",
        "total": len(results),
        "failed": len(failed),
        "results": results,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate project skill structure")
    parser.add_argument(
        "--targets",
        default="scripts/skills/target_skills.yaml",
        help="YAML file listing target skills",
    )
    parser.add_argument(
        "--skills",
        default="",
        help="Comma-separated skill names to validate only selected skills",
    )
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when validation fails")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected = [item.strip() for item in args.skills.split(",") if item.strip()]
    payload = validate_targets(Path(args.targets), selected_names=selected)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.strict and payload["status"] != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
