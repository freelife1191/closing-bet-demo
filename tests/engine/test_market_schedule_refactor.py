#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MarketSchedule 회귀 테스트
"""

from __future__ import annotations

from datetime import date

from engine.market_schedule import MarketSchedule


def test_market_schedule_returns_false_on_weekend():
    assert MarketSchedule.is_market_open(date(2026, 2, 14)) is False
    assert MarketSchedule.is_market_open(date(2026, 2, 15)) is False


def test_market_schedule_fallback_holidays_cover_known_2026_cases(monkeypatch):
    monkeypatch.setattr(MarketSchedule, "_lookup_pykrx_market_open", classmethod(lambda cls, _d: None))

    assert MarketSchedule.is_market_open(date(2026, 2, 16)) is False
    assert MarketSchedule.is_market_open(date(2026, 2, 17)) is False
    assert MarketSchedule.is_market_open(date(2026, 3, 2)) is False
    assert MarketSchedule.is_market_open(date(2026, 5, 5)) is False
    assert MarketSchedule.is_market_open(date(2026, 5, 25)) is False


def test_market_schedule_prefers_pykrx_when_available(monkeypatch):
    monkeypatch.setattr(MarketSchedule, "_lookup_pykrx_market_open", classmethod(lambda cls, _d: True))
    assert MarketSchedule.is_market_open(date(2026, 2, 17)) is True
