#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from scripts.packaging.skill_rename_plan import build_rename_plan


def test_build_rename_plan_includes_qwen_and_video_families() -> None:
    plan = build_rename_plan()
    targets = {item["target"] for item in plan}
    assert "psk-video-manifest-planner" in targets
    assert "psk-qwen3-tts-universal" in targets


def test_build_rename_plan_has_unique_targets() -> None:
    plan = build_rename_plan()
    targets = [item["target"] for item in plan]
    assert len(targets) == len(set(targets))
