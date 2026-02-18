#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path

from scripts.skills.skill_inventory import load_target_skills


def test_skills_guide_mentions_all_target_skills() -> None:
    guide = Path('.agent/skills/SKILLS_GUIDE.md').read_text(encoding='utf-8')
    targets = load_target_skills('scripts/skills/target_skills.yaml')

    for item in targets:
        assert item['name'] in guide, f"Missing in SKILLS_GUIDE: {item['name']}"
        run_doc = f".agent/skills/{item['name']}/commands/run.md"
        assert run_doc in guide, f"Missing run command doc reference: {run_doc}"


def test_quick_start_mentions_canonical_qwen_skill() -> None:
    quick_start = Path('project/jobs/QUICK_START.md').read_text(encoding='utf-8')
    assert 'qwen3-tts-universal' in quick_start
    assert 'SKILLS_GUIDE.md' in quick_start
