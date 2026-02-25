#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SignalConfig 런타임 속성 회귀 테스트
"""

from __future__ import annotations

from engine.config import SignalConfig


def test_signal_config_exposes_runtime_attributes() -> None:
    cfg = SignalConfig()

    assert hasattr(cfg, "USE_TOSS_DATA")
    assert hasattr(cfg, "DATA_DIR")
    assert isinstance(cfg.USE_TOSS_DATA, bool)
    assert isinstance(cfg.DATA_DIR, str)


def test_signal_config_reads_use_toss_data_from_env(monkeypatch) -> None:
    monkeypatch.setenv("USE_TOSS_DATA", "false")

    cfg = SignalConfig()

    assert cfg.USE_TOSS_DATA is False


def test_signal_config_reads_data_dir_from_env(monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", "/tmp/custom-data")

    cfg = SignalConfig()

    assert cfg.DATA_DIR == "/tmp/custom-data"


def test_signal_config_reads_grade_thresholds_from_env(monkeypatch) -> None:
    monkeypatch.setenv("MIN_S_GRADE", "12")
    monkeypatch.setenv("MIN_A_GRADE", "9")
    monkeypatch.setenv("MIN_B_GRADE", "7")

    cfg = SignalConfig()

    assert cfg.min_s_grade == 12
    assert cfg.min_a_grade == 9
    assert cfg.min_b_grade == 7


def test_signal_config_reads_trading_value_thresholds_from_env(monkeypatch) -> None:
    monkeypatch.setenv("TRADING_VALUE_S", "500000000000")
    monkeypatch.setenv("TRADING_VALUE_A", "300000000000")
    monkeypatch.setenv("TRADING_VALUE_B", "150000000000")
    monkeypatch.setenv("TRADING_VALUE_MIN", "40000000000")

    cfg = SignalConfig()

    assert cfg.trading_value_s == 500_000_000_000
    assert cfg.trading_value_a == 300_000_000_000
    assert cfg.trading_value_b == 150_000_000_000
    assert cfg.trading_value_min == 40_000_000_000
