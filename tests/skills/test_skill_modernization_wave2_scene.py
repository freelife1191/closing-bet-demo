#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path

from scripts.skills.validate_skill_structure import validate_skill_dir


SCENE_SKILLS = [
    Path('.agent/skills/scene-script-architect'),
    Path('.agent/skills/scene-record-and-capture'),
    Path('.agent/skills/scene-subtitle-builder'),
    Path('.agent/skills/scene-tts-qwen'),
]


def test_scene_skills_meet_structure_contract() -> None:
    for skill_dir in SCENE_SKILLS:
        result = validate_skill_dir(skill_dir)
        assert result['status'] == 'pass', f"{skill_dir.name} failed: {result}"
