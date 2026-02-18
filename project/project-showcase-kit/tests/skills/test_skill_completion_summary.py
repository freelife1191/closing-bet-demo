#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path


def test_summary_report_exists_and_has_status_matrix() -> None:
    summary_path = Path('docs/plans/reports/summary.md')
    assert summary_path.exists(), 'summary.md not generated yet'

    content = summary_path.read_text(encoding='utf-8')
    assert '## Status Matrix' in content
    assert 'video-orchestration-manager' in content
