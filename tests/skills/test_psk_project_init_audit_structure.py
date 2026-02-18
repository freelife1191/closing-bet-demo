#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path


def test_psk_project_init_audit_has_required_dirs() -> None:
    root = Path(".agent/skills/psk-project-init-audit")
    for name in ["commands", "scripts", "config", "samples", "references"]:
        assert (root / name).is_dir()


def test_psk_project_init_audit_has_skill_md() -> None:
    path = Path(".agent/skills/psk-project-init-audit/SKILL.md")
    assert path.is_file()
