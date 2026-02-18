#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path


def test_target_skills_uses_psk_prefix() -> None:
    text = Path("scripts/skills/target_skills.yaml").read_text(encoding="utf-8")
    assert ".agent/skills/psk-" in text
    assert ".agent/skills/video-manifest-planner" not in text


def test_runtime_scripts_use_psk_qwen_paths() -> None:
    gen_voice_text = Path("scripts/video/gen_voice.py").read_text(encoding="utf-8")
    preflight_text = Path("scripts/pipeline/preflight_check.sh").read_text(encoding="utf-8")
    assert ".agent/skills/psk-qwen3-tts-universal" in gen_voice_text
    assert ".agent/skills/psk-qwen3-tts-m1-local" in gen_voice_text
    assert ".agent/skills/psk-qwen3-tts-universal" in preflight_text
    assert ".agent/skills/psk-qwen3-tts-m1-local" in preflight_text
