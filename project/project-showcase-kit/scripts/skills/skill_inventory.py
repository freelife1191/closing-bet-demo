#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import yaml


def load_target_skills(path: str) -> List[Dict[str, str]]:
    target_path = Path(path)
    data = yaml.safe_load(target_path.read_text(encoding="utf-8"))
    skills = data.get("skills", []) if isinstance(data, dict) else []
    return [item for item in skills if isinstance(item, dict)]
