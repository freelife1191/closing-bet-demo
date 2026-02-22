#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
signal_context 유틸 회귀 테스트
"""

import logging
import os
import sys
from pathlib import Path


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import chatbot.signal_context as signal_context


LOGGER = logging.getLogger("test.signal_context")


def test_load_jongga_signals_uses_shared_json_loader(monkeypatch, tmp_path: Path):
    target = tmp_path / "jongga_v2_latest.json"
    target.write_text("{}", encoding="utf-8")

    captured = {"path": None}

    def _loader(path: str):
        captured["path"] = path
        return {"signals": [{"stock_name": "삼성전자"}]}

    monkeypatch.setattr(signal_context, "load_json_payload_from_path", _loader)

    signals = signal_context.load_jongga_signals(tmp_path, LOGGER)
    assert captured["path"] == str(target)
    assert signals == [{"stock_name": "삼성전자"}]


def test_load_vcp_ai_signals_prefers_primary_file(monkeypatch, tmp_path: Path):
    primary = tmp_path / "kr_ai_analysis.json"
    fallback = tmp_path / "ai_analysis_results.json"
    primary.write_text("{}", encoding="utf-8")
    fallback.write_text("{}", encoding="utf-8")

    called_paths: list[str] = []

    def _loader(path: str):
        called_paths.append(path)
        return {"signals": [{"name": "PRIMARY"}]}

    monkeypatch.setattr(signal_context, "load_json_payload_from_path", _loader)

    signals = signal_context.load_vcp_ai_signals(tmp_path, LOGGER)
    assert called_paths == [str(primary)]
    assert signals == [{"name": "PRIMARY"}]


def test_load_vcp_ai_signals_falls_back_to_secondary_file(monkeypatch, tmp_path: Path):
    fallback = tmp_path / "ai_analysis_results.json"
    fallback.write_text("{}", encoding="utf-8")

    captured = {"path": None}

    def _loader(path: str):
        captured["path"] = path
        return {"signals": [{"name": "FALLBACK"}]}

    monkeypatch.setattr(signal_context, "load_json_payload_from_path", _loader)

    signals = signal_context.load_vcp_ai_signals(tmp_path, LOGGER)
    assert captured["path"] == str(fallback)
    assert signals == [{"name": "FALLBACK"}]
