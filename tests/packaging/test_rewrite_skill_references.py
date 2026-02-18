#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from scripts.packaging.rewrite_skill_references import rewrite_text


def test_rewrite_text_replaces_legacy_skill_names() -> None:
    text = ".agent/skills/video-manifest-planner/SKILL.md"
    mapping = {"video-manifest-planner": "psk-video-manifest-planner"}
    assert rewrite_text(text, mapping) == ".agent/skills/psk-video-manifest-planner/SKILL.md"


def test_rewrite_text_preserves_unmapped_words() -> None:
    text = "docs mention video-manifest but not a mapped skill"
    mapping = {"video-manifest-planner": "psk-video-manifest-planner"}
    assert rewrite_text(text, mapping) == text
