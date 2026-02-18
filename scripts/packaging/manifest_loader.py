#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import yaml


def _load_yaml(path: Path) -> Dict:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid manifest payload type: {path}")
    return payload


def _validate_mapping_entries(entries: List[Dict[str, str]]) -> List[Dict[str, str]]:
    validated: List[Dict[str, str]] = []
    seen_targets: set[str] = set()
    for item in entries:
        source = str(item.get("source", "")).strip()
        target = str(item.get("target", "")).strip()
        if not source:
            raise ValueError("skills map requires non-empty source")
        if not target.startswith("psk-"):
            raise ValueError(f"target must start with psk-: {target}")
        if target in seen_targets:
            raise ValueError(f"duplicate target skill found: {target}")
        seen_targets.add(target)
        validated.append({"source": source, "target": target})
    return validated


def load_skills_map(path: Path) -> Dict[str, List[Dict[str, str]]]:
    payload = _load_yaml(path)
    entries = payload.get("skills", [])
    if not isinstance(entries, list):
        raise ValueError("skills map must define a list at key 'skills'")
    parsed: List[Dict[str, str]] = []
    for item in entries:
        if not isinstance(item, dict):
            raise ValueError("each skill entry must be a mapping")
        parsed.append({str(key): str(value) for key, value in item.items()})
    return {"skills": _validate_mapping_entries(parsed)}


def load_tool_map(path: Path) -> Dict:
    payload = _load_yaml(path)
    tools = payload.get("tools", [])
    if not isinstance(tools, list):
        raise ValueError("tool map must define a list at key 'tools'")
    for item in tools:
        if not isinstance(item, dict):
            raise ValueError("each tool entry must be a mapping")
        name = str(item.get("name", "")).strip()
        if not name:
            raise ValueError("tool entry requires non-empty name")
    return payload

