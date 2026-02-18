#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

from scripts.packaging.skill_rename_plan import build_rename_plan

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_SKILLS_ROOT = ROOT_DIR / ".agent" / "skills"


def rename_skill_dir(source: Path, target: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(source)
    if target.exists():
        raise FileExistsError(target)
    source.rename(target)


def apply_rename_plan(skills_root: Path = DEFAULT_SKILLS_ROOT, dry_run: bool = True) -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []
    for item in build_rename_plan():
        source_dir = skills_root / item["source"]
        target_dir = skills_root / item["target"]
        status = "missing_source"
        if source_dir.exists() and not target_dir.exists():
            if not dry_run:
                rename_skill_dir(source_dir, target_dir)
            status = "renamed" if not dry_run else "planned"
        elif target_dir.exists():
            status = "already_renamed"

        results.append(
            {
                "source": str(source_dir),
                "target": str(target_dir),
                "status": status,
            }
        )
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rename project showcase skills to psk-* namespace")
    parser.add_argument("--skills-root", default=str(DEFAULT_SKILLS_ROOT), help="Root .agent/skills directory")
    parser.add_argument("--apply", action="store_true", help="Apply rename instead of dry-run")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = apply_rename_plan(skills_root=Path(args.skills_root), dry_run=not args.apply)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

