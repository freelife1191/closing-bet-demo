#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path
import subprocess

from scripts.skills.validate_skill_structure import validate_skill_dir


QWEN_SKILLS = [
    Path('.agent/skills/qwen3-tts-universal'),
    Path('.agent/skills/qwen3-tts-m1-local'),
]


def test_qwen_skills_meet_structure_contract() -> None:
    for skill_dir in QWEN_SKILLS:
        result = validate_skill_dir(skill_dir)
        assert result['status'] == 'pass', f"{skill_dir.name} failed: {result}"


def test_legacy_wrapper_redirects_to_universal() -> None:
    completed = subprocess.run(
        [
            'bash',
            '.agent/skills/qwen3-tts-m1-local/scripts/smoke_test_qwen3_tts.sh',
            '--project-root',
            '/Users/freelife/vibe/lecture/hodu/closing-bet-demo',
            '--venv-path',
            '/Users/freelife/vibe/lecture/hodu/closing-bet-demo/.venv-qwen3-tts',
            '--mode',
            'list',
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert 'redirecting to qwen3-tts-universal smoke test' in completed.stdout
