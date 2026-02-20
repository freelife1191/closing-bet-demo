#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path


def test_quick_start_mentions_scene_retry_gate_and_prompt_pack_outputs() -> None:
    quick_start = Path("project/jobs/QUICK_START.md").read_text(encoding="utf-8")

    assert "scene-runner" in quick_start
    assert "최대 3회" in quick_start
    assert "0.15초" in quick_start
    assert "0.10초" in quick_start
    assert "thumbnail_prompt_nanobanana_pro.md" in quick_start
    assert "youtube_description_prompt.md" in quick_start
    assert "project_overview_doc_prompt.md" in quick_start
    assert "ppt_slide_prompt_gemini.md" in quick_start
