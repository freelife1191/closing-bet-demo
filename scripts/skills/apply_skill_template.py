#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Dict, List

REQUIRED_DIRECTORIES = ["commands", "scripts", "config", "samples", "references"]
TEMPLATE_ROOT = Path(__file__).resolve().parent / "templates" / "skill_skeleton"


def _copy_if_missing(src: Path, dst: Path, changed: List[str]) -> None:
    if dst.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    changed.append(str(dst))


def apply_skill_template(skill_dir: Path) -> Dict[str, object]:
    skill_dir = skill_dir.resolve()
    changed: List[str] = []

    for directory in REQUIRED_DIRECTORIES:
        path = skill_dir / directory
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            changed.append(str(path))

    for file_path in TEMPLATE_ROOT.rglob("*"):
        if file_path.is_dir():
            continue
        relative = file_path.relative_to(TEMPLATE_ROOT)
        target = skill_dir / relative
        _copy_if_missing(file_path, target, changed)

    return {
        "skill": skill_dir.name,
        "path": str(skill_dir),
        "changed": bool(changed),
        "created": changed,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply standard skill template")
    parser.add_argument("skill_dir", help="Path to target skill directory")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = apply_skill_template(Path(args.skill_dir))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
