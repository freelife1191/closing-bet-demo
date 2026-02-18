#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from scripts.packaging.manifest_loader import load_skills_map

DEFAULT_SKILLS_MAP = (
    Path(__file__).resolve().parents[2]
    / "project"
    / "project-showcase-kit-src"
    / "manifest"
    / "skills-map.yaml"
)


def build_rename_plan(skills_map_path: Path | None = None) -> List[Dict[str, str]]:
    path = skills_map_path or DEFAULT_SKILLS_MAP
    payload = load_skills_map(path)
    return payload["skills"]

