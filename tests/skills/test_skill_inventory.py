#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from scripts.skills.skill_inventory import load_target_skills


def test_target_skills_count_and_names() -> None:
    skills = load_target_skills("scripts/skills/target_skills.yaml")
    names = {skill["name"] for skill in skills}

    assert len(skills) == 19
    assert "video-orchestration-manager" in names
    assert "qwen3-tts-universal" in names
    assert "playwright-scene-recorder" in names
