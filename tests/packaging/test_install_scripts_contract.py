#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path


def test_install_all_mentions_supported_tools() -> None:
    script = Path("project/project-showcase-kit-dist/install/install_all.sh").read_text(encoding="utf-8")
    assert "codex" in script
    assert "claudecode" in script
    assert "gemini" in script
    assert "antigravity" in script
