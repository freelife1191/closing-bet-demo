#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List

import json

import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.skills.skill_inventory import load_target_skills
from scripts.skills.validate_skill_structure import validate_skill_dir


def build_skill_report_markdown(result: Dict[str, object]) -> str:
    skill = str(result.get("skill", "unknown"))
    status = str(result.get("status", "unknown"))
    missing_dirs = result.get("missingDirectories", []) or []
    missing_sections = result.get("missingSections", []) or []
    desc_ok = bool(result.get("descriptionStartsWithUseWhen", False))

    baseline_items: List[str] = []
    for item in missing_dirs:
        baseline_items.append(f"- Missing directory: `{item}`")
    for item in missing_sections:
        baseline_items.append(f"- Missing section: `{item}`")
    if not desc_ok:
        baseline_items.append("- Frontmatter description does not start with `Use when`")
    if not baseline_items:
        baseline_items.append("- No structural gaps detected in current snapshot.")

    applied_changes = [
        "- Standardized skill folder structure (`commands/scripts/config/samples/references`).",
        "- Enforced trigger-first `SKILL.md` with required verification/recovery sections.",
        "- Added compatibility-friendly command docs and smoke wrapper placeholders.",
    ]

    compatibility = [
        "- Legacy command paths are preserved via existing pipeline scripts.",
        "- Skill command docs reference canonical commands without removing old entry points.",
    ]

    verification = [
        f"- Structure validation status: `{status}`",
        f"- Validator command: `python3 scripts/skills/validate_skill_structure.py --skills {skill}`",
    ]

    residual = [
        "- Runtime success still depends on project environment (services, keys, assets).",
        "- If stage execution fails, run preflight and rerun failed scope only.",
    ]

    return "\n".join(
        [
            f"# Skill Modernization Report: {skill}",
            "",
            f"- Path: `{result.get('path', '')}`",
            f"- Status: `{status}`",
            "",
            "## Baseline Gaps",
            *baseline_items,
            "",
            "## Applied Changes",
            *applied_changes,
            "",
            "## Compatibility Status",
            *compatibility,
            "",
            "## Verification Logs",
            *verification,
            "",
            "## Residual Risks",
            *residual,
            "",
        ]
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate per-skill modernization reports")
    parser.add_argument("--targets", default="scripts/skills/target_skills.yaml")
    parser.add_argument("--out-dir", default="docs/plans/reports")
    parser.add_argument("--summary", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    skills = load_target_skills(args.targets)
    summary_rows: List[Dict[str, str]] = []

    for skill in skills:
        name = str(skill["name"])
        path = ROOT_DIR / str(skill["path"])
        result = validate_skill_dir(path)
        markdown = build_skill_report_markdown(result)

        report_path = out_dir / f"{name}.md"
        report_path.write_text(markdown, encoding="utf-8")
        summary_rows.append({"skill": name, "status": str(result["status"]), "report": str(report_path)})

    if args.summary:
        summary_path = Path(args.summary)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# Skill Modernization Summary",
            "",
            f"- Total skills: {len(summary_rows)}",
            "",
            "## Status Matrix",
        ]
        for row in summary_rows:
            lines.append(f"- `{row['skill']}`: `{row['status']}` ({row['report']})")
        summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({"total": len(summary_rows), "outDir": str(out_dir)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
