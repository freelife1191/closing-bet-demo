#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.packaging.rename_skills import rename_skill_dir


def test_rename_skill_dir_moves_folder(tmp_path: Path) -> None:
    source = tmp_path / "video-manifest-planner"
    source.mkdir()
    (source / "SKILL.md").write_text("name: video-manifest-planner\n", encoding="utf-8")
    target = tmp_path / "psk-video-manifest-planner"
    rename_skill_dir(source, target)
    assert target.exists()
    assert not source.exists()


def test_rename_skill_dir_rejects_existing_target(tmp_path: Path) -> None:
    source = tmp_path / "video-manifest-planner"
    source.mkdir()
    target = tmp_path / "psk-video-manifest-planner"
    target.mkdir()
    with pytest.raises(FileExistsError):
        rename_skill_dir(source, target)
