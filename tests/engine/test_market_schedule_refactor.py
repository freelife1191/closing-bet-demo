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


def test_market_schedule_open_cache_is_bounded_lru(monkeypatch):
    monkeypatch.setattr(MarketSchedule, "_lookup_pykrx_market_open", classmethod(lambda cls, _d: None))
    monkeypatch.setattr(MarketSchedule, "_open_cache_max_entries", 2)

    with MarketSchedule._cache_lock:
        MarketSchedule._open_cache.clear()

    first_day = date(2026, 2, 19)
    second_day = date(2026, 2, 20)
    third_day = date(2026, 2, 23)

    _ = MarketSchedule.is_market_open(first_day)
    _ = MarketSchedule.is_market_open(second_day)
    _ = MarketSchedule.is_market_open(first_day)
    _ = MarketSchedule.is_market_open(third_day)

    with MarketSchedule._cache_lock:
        cached_days = list(MarketSchedule._open_cache.keys())

    assert len(cached_days) == 2
    assert first_day in cached_days
    assert third_day in cached_days
    assert second_day not in cached_days
