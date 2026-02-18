#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path

from scripts.skills.validate_skill_structure import validate_skill_dir


VIDEO_SKILLS = [
    Path('.agent/skills/video-copywriter-docs'),
    Path('.agent/skills/video-manifest-planner'),
    Path('.agent/skills/video-mastering-editor'),
    Path('.agent/skills/video-orchestration-manager'),
    Path('.agent/skills/video-pipeline-orchestrator'),
    Path('.agent/skills/video-postproduction-remotion'),
    Path('.agent/skills/video-qc-gatekeeper'),
    Path('.agent/skills/video-quality-researcher'),
    Path('.agent/skills/video-tts-local-free'),
]


def test_video_skills_meet_structure_contract() -> None:
    for skill_dir in VIDEO_SKILLS:
        result = validate_skill_dir(skill_dir)
        assert result['status'] == 'pass', f"{skill_dir.name} failed: {result}"
