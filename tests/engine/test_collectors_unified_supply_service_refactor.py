#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Legacy collectors 모듈 수급 통합 서비스 연동 테스트
"""

from __future__ import annotations

import asyncio

from engine.collectors import KRXCollector


class _Config:
    def __init__(self, data_dir: str):
        self.DATA_DIR = data_dir


def _stub(monkeypatch, *, pykrx=None, unified=None):
    calls: dict[str, dict] = {}

    def _fake_pykrx(**kwargs):
        calls["pykrx"] = kwargs
        return pykrx

    def _fake_unified(**kwargs):
        calls["unified"] = kwargs
        return unified

    monkeypatch.setattr("engine.collectors.krx_local_data_mixin.get_pykrx_trend_5day", _fake_pykrx)
    monkeypatch.setattr("engine.collectors.krx_local_data_mixin.get_investor_trend_5day_for_ticker", _fake_unified)
    return calls


def test_get_supply_data_without_target_uses_the_verified_unified_service(monkeypatch, tmp_path):
    calls = _stub(monkeypatch, unified={"foreign": 123, "institution": 456})

    supply = asyncio.run(KRXCollector(_Config(str(tmp_path))).get_supply_data("5930"))

    assert (supply.foreign_buy_5d, supply.inst_buy_5d, supply.retail_buy_5d) == (123, 456, None)
    assert calls["unified"]["ticker"] == "005930"
    assert calls["unified"].get("verify_with_references", True) is True
    assert "pykrx" not in calls


def test_get_supply_data_with_target_prefers_complete_pykrx(monkeypatch, tmp_path):
    calls = _stub(
        monkeypatch,
        pykrx={"foreign": 7, "institution": 8, "individual": -15},
        unified={"foreign": 1, "institution": 2},
    )

    supply = asyncio.run(KRXCollector(_Config(str(tmp_path))).get_supply_data("005930", target_date="20260304"))

    assert (supply.foreign_buy_5d, supply.inst_buy_5d, supply.retail_buy_5d) == (7, 8, -15)
    assert calls["pykrx"]["target_datetime"] == "20260304"
    assert "unified" not in calls


def test_get_supply_data_with_target_falls_back_to_the_verified_service(monkeypatch, tmp_path):
    """[FLOW-026] pykrx 가 5일 값을 주지 못하면 검증 켠 서비스로 넘어간다. 그것도 없으면 0·0 대신 None."""
    calls = _stub(monkeypatch, pykrx=None, unified={"foreign": 1, "institution": 2})
    supply = asyncio.run(KRXCollector(_Config(str(tmp_path))).get_supply_data("005930", target_date="20260304"))
    assert (supply.foreign_buy_5d, supply.inst_buy_5d) == (1, 2)
    assert calls["unified"]["target_datetime"] == "20260304"
    assert calls["unified"].get("verify_with_references", True) is True

    _stub(monkeypatch, pykrx=None, unified=None)
    assert asyncio.run(KRXCollector(_Config(str(tmp_path))).get_supply_data("005930", target_date="20260304")) is None
