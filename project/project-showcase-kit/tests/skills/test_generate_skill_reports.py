#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path

from scripts.skills.generate_skill_modernization_report import build_skill_report_markdown


def test_report_contains_before_after_and_verification_sections() -> None:
    payload = {
        'skill': 'demo-skill',
        'path': '/tmp/demo-skill',
        'status': 'pass',
        'missingDirectories': [],
        'missingSections': [],
        'descriptionStartsWithUseWhen': True,
    }

    markdown = build_skill_report_markdown(payload)

    assert '## Baseline Gaps' in markdown
    assert '## Applied Changes' in markdown
    assert '## Compatibility Status' in markdown
    assert '## Verification Logs' in markdown
    assert '## Residual Risks' in markdown
