#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path


def test_all_tool_templates_exist() -> None:
    root = Path("project/project-showcase-kit-src/templates")
    for tool in ["codex", "claudecode", "gemini", "antigravity"]:
        assert (root / tool / "install.template.sh").is_file()


def test_common_template_exists() -> None:
    path = Path("project/project-showcase-kit-src/templates/common/README.template.md")
    assert path.is_file()
