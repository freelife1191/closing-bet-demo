#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.packaging.manifest_loader import load_skills_map


def test_load_skills_map_requires_psk_prefix(tmp_path: Path) -> None:
    manifest = tmp_path / "skills-map.yaml"
    manifest.write_text(
        "skills:\n"
        "  - source: video-manifest-planner\n"
        "    target: psk-video-manifest-planner\n",
        encoding="utf-8",
    )
    payload = load_skills_map(manifest)
    assert payload["skills"][0]["target"].startswith("psk-")


def test_load_skills_map_rejects_non_psk_target(tmp_path: Path) -> None:
    manifest = tmp_path / "skills-map.yaml"
    manifest.write_text(
        "skills:\n"
        "  - source: video-manifest-planner\n"
        "    target: video-manifest-planner\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_skills_map(manifest)
