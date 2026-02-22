#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
market_gate save_analysis 리팩토링 회귀 테스트
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import engine.market_gate as market_gate_module


class _StubGate:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir

    def _sanitize_for_json(self, data):
        return data


def test_save_analysis_writes_daily_and_latest_when_target_date_missing(monkeypatch, tmp_path: Path):
    writes: list[tuple[str, str]] = []

    def _atomic_write(path: str, content: str):
        writes.append((path, content))
        Path(path).write_text(content, encoding="utf-8")

    monkeypatch.setattr(market_gate_module, "atomic_write_text", _atomic_write)

    gate = _StubGate(str(tmp_path))
    result_path = market_gate_module.MarketGate.save_analysis(
        gate,
        {"dataset_date": "2026-02-22", "total_score": 80},
        target_date=None,
    )

    assert result_path.endswith("market_gate_20260222.json")
    assert len(writes) == 2
    assert any(path.endswith("market_gate_20260222.json") for path, _ in writes)
    assert any(path.endswith("market_gate.json") for path, _ in writes)


def test_save_analysis_skips_latest_when_target_date_is_not_today(monkeypatch, tmp_path: Path):
    writes: list[tuple[str, str]] = []
    monkeypatch.setattr(
        market_gate_module,
        "atomic_write_text",
        lambda path, content: writes.append((path, content)),
    )

    gate = _StubGate(str(tmp_path))
    result_path = market_gate_module.MarketGate.save_analysis(
        gate,
        {"dataset_date": "2026-02-22", "total_score": 70},
        target_date="2020-01-01",
    )

    assert result_path.endswith("market_gate_20200101.json")
    assert len(writes) == 1
    assert writes[0][0].endswith("market_gate_20200101.json")


def test_save_analysis_returns_empty_when_write_fails(monkeypatch, tmp_path: Path):
    def _raise(_path: str, _content: str):
        raise OSError("disk full")

    monkeypatch.setattr(market_gate_module, "atomic_write_text", _raise)

    gate = _StubGate(str(tmp_path))
    result_path = market_gate_module.MarketGate.save_analysis(
        gate,
        {"dataset_date": "2026-02-22", "total_score": 70},
        target_date=None,
    )

    assert result_path == ""
