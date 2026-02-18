#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path

from scripts.skills.validate_skill_structure import validate_skill_dir


WAVE1 = [
    Path('.agent/skills/logo-thumbnail-prompt-designer'),
    Path('.agent/skills/promo-asset-studio'),
    Path('.agent/skills/pipeline-output-validator'),
]


def test_wave1_skills_meet_structure_contract() -> None:
    for skill_dir in WAVE1:
        result = validate_skill_dir(skill_dir)
        assert result['status'] == 'pass', f"{skill_dir.name} failed: {result}"
