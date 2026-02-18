#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path


def test_required_checklist_contains_gate_a_to_d() -> None:
    text = Path("project/project-showcase-kit-dist/checklists/required.md").read_text(encoding="utf-8")
    for gate in ["Gate A", "Gate B", "Gate C", "Gate D"]:
        assert gate in text


def test_required_checklist_mentions_evidence_bundle() -> None:
    text = Path("project/project-showcase-kit-dist/checklists/required.md").read_text(encoding="utf-8")
    assert "validation_report" in text
    assert "manager_report" in text
    assert "signoff" in text
