#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Screener 수급 통합 서비스 연동 테스트
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from engine.screener import SmartMoneyScreener


def test_calculate_supply_score_csv_uses_unified_5day_service(monkeypatch):
    screener = object.__new__(SmartMoneyScreener)
    screener._target_datetime = datetime(2026, 2, 24)
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "engine.screener.get_investor_trend_5day_for_ticker",
        lambda **kwargs: (
            captured.update(kwargs)
            or {
                "foreign": 60_000_000_000,
                "institution": 25_000_000_000,
                "details": [
                    {"netForeignerBuyVolume": 10, "netInstitutionBuyVolume": 20},
                    {"netForeignerBuyVolume": 5, "netInstitutionBuyVolume": 0},
                ],
            }
        ),
    )

    result = SmartMoneyScreener._calculate_supply_score_csv(screener, "005930")

    assert captured["ticker"] == "005930"
    assert captured["verify_with_references"] is True
    assert captured["target_datetime"] == datetime(2026, 2, 24)
    assert result["foreign_5d"] == 60_000_000_000
    assert result["inst_5d"] == 25_000_000_000
    assert result["foreign_1d"] == 10
    assert result["inst_1d"] == 20
    assert result["score"] > 0


def test_calculate_supply_score_csv_returns_missing_when_unified_service_has_no_data(monkeypatch):
    screener = object.__new__(SmartMoneyScreener)
    screener._target_datetime = None
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "engine.screener.get_investor_trend_5day_for_ticker",
        lambda **kwargs: captured.update(kwargs) or None,
    )

    result = SmartMoneyScreener._calculate_supply_score_csv(screener, "005930")

    assert captured["ticker"] == "005930"
    assert captured["verify_with_references"] is True
    assert captured["target_datetime"] is None
    # [VCP-050] 결측은 0 이 아니라 None 이다
    assert result == {"score": 0, "foreign_5d": None, "inst_5d": None, "foreign_1d": None, "inst_1d": None}


def test_calculate_supply_score_csv_calls_the_service_once(monkeypatch):
    """서비스가 이상징후일 때만 참조를 조회하므로 호출자가 두 번 부를 이유가 없다."""
    screener = object.__new__(SmartMoneyScreener)
    screener._target_datetime = datetime(2026, 2, 24)
    captured_calls: list[dict[str, object]] = []

    def _fake_trend(**kwargs):
        captured_calls.append(dict(kwargs))
        return {
            "foreign": 333,
            "institution": 444,
            "quality": {"csv_anomaly_flags": ["stale_csv"]},
            "details": [
                {"netForeignerBuyVolume": 3, "netInstitutionBuyVolume": 4},
            ],
        }

    monkeypatch.setattr(
        "engine.screener.get_investor_trend_5day_for_ticker",
        _fake_trend,
    )

    result = SmartMoneyScreener._calculate_supply_score_csv(screener, "005930")

    assert len(captured_calls) == 1
    assert captured_calls[0]["verify_with_references"] is True
    assert result["foreign_5d"] == 333
    assert result["inst_5d"] == 444


def test_calculate_supply_score_uses_csv_only_for_historical_target_date(monkeypatch):
    screener = object.__new__(SmartMoneyScreener)
    screener._target_datetime = datetime(2000, 2, 24)
    screener.toss_collector = SimpleNamespace()

    called: dict[str, object] = {"toss": False, "csv": False}

    def _fake_csv(_ticker: str) -> dict[str, int]:
        called["csv"] = True
        return {"score": 11, "foreign_1d": 1, "inst_1d": 2}

    monkeypatch.setattr(
        screener,
        "_calculate_supply_score_csv",
        _fake_csv,
    )
    monkeypatch.setattr(
        "engine.screener.calculate_supply_score_with_toss_impl",
        lambda **_kwargs: called.__setitem__("toss", True) or {"score": 99},
    )

    result = SmartMoneyScreener._calculate_supply_score(screener, "005930")

    assert result == {"score": 11, "foreign_1d": 1, "inst_1d": 2}
    assert called["csv"] is True
    assert called["toss"] is False


def test_calculate_supply_score_keeps_toss_for_current_target_date(monkeypatch):
    screener = object.__new__(SmartMoneyScreener)
    screener._target_datetime = datetime.now()
    screener.toss_collector = SimpleNamespace()

    called: dict[str, object] = {"toss": False}

    monkeypatch.setattr(
        screener,
        "_calculate_supply_score_csv",
        lambda _ticker: {"score": 11, "foreign_1d": 1, "inst_1d": 2},
    )
    monkeypatch.setattr(
        "engine.screener.calculate_supply_score_with_toss_impl",
        lambda **_kwargs: called.__setitem__("toss", True) or {"score": 99},
    )

    result = SmartMoneyScreener._calculate_supply_score(screener, "005930")

    assert result == {"score": 99}
    assert called["toss"] is True
