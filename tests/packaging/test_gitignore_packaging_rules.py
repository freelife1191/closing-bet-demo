#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path


def test_gitignore_excludes_generated_video_artifacts() -> None:
    text = Path(".gitignore").read_text(encoding="utf-8")
    assert "project/video/scenes/" in text
    assert "project/video/audio/" in text
    assert "project/video/evidence/*.zip" in text
    assert "project/video/evidence/tmp_videos/" in text
