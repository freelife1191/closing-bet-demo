#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Screener 수급 통합 서비스 연동 테스트
"""

from __future__ import annotations

from datetime import datetime

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
    assert captured["verify_with_references"] is False
    assert captured["target_datetime"] == datetime(2026, 2, 24)
    assert result["foreign_5d"] == 60_000_000_000
    assert result["inst_5d"] == 25_000_000_000
    assert result["foreign_1d"] == 10
    assert result["inst_1d"] == 20
    assert result["score"] > 0


def test_calculate_supply_score_csv_returns_zero_when_unified_service_has_no_data(monkeypatch):
    screener = object.__new__(SmartMoneyScreener)
    screener._target_datetime = None
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "engine.screener.get_investor_trend_5day_for_ticker",
        lambda **kwargs: captured.update(kwargs) or None,
    )

    result = SmartMoneyScreener._calculate_supply_score_csv(screener, "005930")

    assert captured["ticker"] == "005930"
    assert captured["verify_with_references"] is False
    assert captured["target_datetime"] is None
    assert result == {"score": 0, "foreign_1d": 0, "inst_1d": 0}


def test_calculate_supply_score_csv_retries_reference_verify_only_on_anomaly(monkeypatch):
    screener = object.__new__(SmartMoneyScreener)
    screener._target_datetime = datetime(2026, 2, 24)
    captured_calls: list[dict[str, object]] = []

    def _fake_trend(**kwargs):
        captured_calls.append(dict(kwargs))
        if kwargs.get("verify_with_references") is False:
            return {
                "foreign": 111,
                "institution": 222,
                "quality": {"csv_anomaly_flags": ["stale_csv"]},
            }
        return {
            "foreign": 333,
            "institution": 444,
            "details": [
                {"netForeignerBuyVolume": 3, "netInstitutionBuyVolume": 4},
            ],
        }

    monkeypatch.setattr(
        "engine.screener.get_investor_trend_5day_for_ticker",
        _fake_trend,
    )

    result = SmartMoneyScreener._calculate_supply_score_csv(screener, "005930")

    assert len(captured_calls) == 2
    assert captured_calls[0]["verify_with_references"] is False
    assert captured_calls[1]["verify_with_references"] is True
    assert result["foreign_5d"] == 333
    assert result["inst_5d"] == 444
