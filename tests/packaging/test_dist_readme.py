#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path


def test_dist_readme_lists_install_targets() -> None:
    text = Path("project/project-showcase-kit-dist/README.md").read_text(encoding="utf-8")
    assert "Codex" in text
    assert "ClaudeCode" in text
    assert "Gemini" in text
    assert "Antigravity" in text


def test_packaging_summary_report_exists() -> None:
    path = Path("docs/plans/reports/project-showcase-kit-packaging-summary.md")
    assert path.is_file()
