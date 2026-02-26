#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Legacy collectors 모듈 수급 통합 서비스 연동 테스트
"""

from __future__ import annotations

import asyncio
import sys
import types

from engine.collectors import KRXCollector


class _Config:
    def __init__(self, data_dir: str):
        self.DATA_DIR = data_dir


def test_legacy_collector_get_supply_data_prefers_unified_service(monkeypatch, tmp_path):
    collector = KRXCollector(_Config(str(tmp_path)))
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "engine.collectors.get_investor_trend_5day_for_ticker",
        lambda **kwargs: captured.update(kwargs) or {"foreign": 123, "institution": 456},
    )

    supply = asyncio.run(collector.get_supply_data("5930"))

    assert supply is not None
    assert captured["ticker"] == "005930"
    assert captured["verify_with_references"] is False
    assert supply.foreign_buy_5d == 123
    assert supply.inst_buy_5d == 456
    assert supply.retail_buy_5d == 0


def test_legacy_collector_get_supply_data_falls_back_when_unified_has_anomaly_flags(monkeypatch, tmp_path):
    collector = KRXCollector(_Config(str(tmp_path)))
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "engine.collectors.get_investor_trend_5day_for_ticker",
        lambda **kwargs: captured.update(kwargs)
        or {
            "foreign": 111,
            "institution": 222,
            "quality": {"csv_anomaly_flags": ["stale_csv"]},
        },
    )
    monkeypatch.setattr(
        KRXCollector,
        "_get_latest_market_date",
        lambda self: "20260221",
    )
    monkeypatch.setattr(
        KRXCollector,
        "_load_cached_pykrx_supply_summary",
        classmethod(
            lambda cls, *, ticker, end_date: {
                "foreign_buy_5d": 700_000_000,
                "inst_buy_5d": -200_000_000,
                "retail_buy_5d": -500_000_000,
            }
        ),
    )
    fake_pykrx = types.ModuleType("pykrx")
    fake_pykrx.stock = types.SimpleNamespace()
    monkeypatch.setitem(sys.modules, "pykrx", fake_pykrx)

    supply = asyncio.run(collector.get_supply_data("5930"))

    assert supply is not None
    assert captured["ticker"] == "005930"
    assert captured["verify_with_references"] is False
    assert supply.foreign_buy_5d == 700_000_000
    assert supply.inst_buy_5d == -200_000_000
    assert supply.retail_buy_5d == -500_000_000
