#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict


def rewrite_text(text: str, mapping: Dict[str, str]) -> str:
    rewritten = text
    for source, target in mapping.items():
        # Replace exact skill tokens only, preventing re-rewrite inside psk-* names.
        pattern = re.compile(rf"(?<![A-Za-z0-9_-]){re.escape(source)}(?![A-Za-z0-9_-])")
        rewritten = pattern.sub(target, rewritten)
    return rewritten


def rewrite_file(path: Path, mapping: Dict[str, str]) -> bool:
    original = path.read_text(encoding="utf-8")
    updated = rewrite_text(original, mapping)
    if updated == original:
        return False
    path.write_text(updated, encoding="utf-8")
    return True
