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


def test_market_schedule_prefers_pykrx_when_available(monkeypatch, tmp_path):
    monkeypatch.setattr(MarketSchedule, "_lookup_pykrx_market_open", classmethod(lambda cls, _d: True))
    monkeypatch.setattr(
        MarketSchedule,
        "_market_schedule_sqlite_cache_context",
        classmethod(
            lambda cls, target_date: (
                str(tmp_path / ".market_schedule_cache" / f"{target_date.isoformat()}.snapshot"),
                (int(target_date.strftime("%Y%m%d")), 3),
            )
        ),
    )
    with MarketSchedule._cache_lock:
        MarketSchedule._open_cache.clear()
        MarketSchedule._holiday_validation_cache.clear()
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


def test_market_schedule_uses_memory_cache_before_pykrx(monkeypatch, tmp_path):
    calls = {"count": 0}

    def _fake_lookup(cls, _target_date):
        calls["count"] += 1
        return True

    monkeypatch.setattr(MarketSchedule, "_lookup_pykrx_market_open", classmethod(_fake_lookup))
    monkeypatch.setattr(
        MarketSchedule,
        "_market_schedule_sqlite_cache_context",
        classmethod(
            lambda cls, target_date: (
                str(tmp_path / ".market_schedule_cache" / f"{target_date.isoformat()}.snapshot"),
                (int(target_date.strftime("%Y%m%d")), 1),
            )
        ),
    )

    with MarketSchedule._cache_lock:
        MarketSchedule._open_cache.clear()

    target_day = date(2026, 2, 19)
    assert MarketSchedule.is_market_open(target_day) is True
    assert MarketSchedule.is_market_open(target_day) is True
    assert calls["count"] == 1


def test_market_schedule_reuses_sqlite_snapshot_after_memory_clear(monkeypatch, tmp_path):
    calls = {"count": 0}

    def _fake_lookup(cls, _target_date):
        calls["count"] += 1
        return True

    monkeypatch.setattr(MarketSchedule, "_lookup_pykrx_market_open", classmethod(_fake_lookup))
    monkeypatch.setattr(
        MarketSchedule,
        "_market_schedule_sqlite_cache_context",
        classmethod(
            lambda cls, target_date: (
                str(tmp_path / ".market_schedule_cache" / f"{target_date.isoformat()}.snapshot"),
                (int(target_date.strftime("%Y%m%d")), 9),
            )
        ),
    )

    with MarketSchedule._cache_lock:
        MarketSchedule._open_cache.clear()

    target_day = date(2026, 2, 20)
    assert MarketSchedule.is_market_open(target_day) is True
    assert calls["count"] == 1

    with MarketSchedule._cache_lock:
        MarketSchedule._open_cache.clear()
        MarketSchedule._holiday_validation_cache.clear()

    monkeypatch.setattr(
        MarketSchedule,
        "_lookup_pykrx_market_open",
        classmethod(lambda cls, _d: (_ for _ in ()).throw(AssertionError("pykrx lookup should be skipped"))),
    )
    assert MarketSchedule.is_market_open(target_day) is True
    assert calls["count"] == 1


def test_market_schedule_fallback_holiday_revalidates_once_per_token(monkeypatch, tmp_path):
    calls = {"count": 0}

    def _fake_lookup(cls, _target_date):
        calls["count"] += 1
        return None

    monkeypatch.setattr(MarketSchedule, "_lookup_pykrx_market_open", classmethod(_fake_lookup))
    monkeypatch.setattr(
        MarketSchedule,
        "_current_validation_token",
        classmethod(lambda cls, now=None: "20260226"),
    )
    monkeypatch.setattr(
        MarketSchedule,
        "_market_schedule_sqlite_cache_context",
        classmethod(
            lambda cls, target_date: (
                str(tmp_path / ".market_schedule_cache" / f"{target_date.isoformat()}.snapshot"),
                (int(target_date.strftime("%Y%m%d")), 19),
            )
        ),
    )

    with MarketSchedule._cache_lock:
        MarketSchedule._open_cache.clear()
        MarketSchedule._holiday_validation_cache.clear()

    target_day = date(2026, 2, 17)  # fallback holiday
    assert MarketSchedule.is_market_open(target_day) is False
    assert MarketSchedule.is_market_open(target_day) is False
    assert calls["count"] == 1


def test_market_schedule_fallback_holiday_revalidates_on_token_change(monkeypatch, tmp_path):
    calls = {"count": 0}
    token = {"value": "20260226"}

    def _fake_lookup(cls, _target_date):
        calls["count"] += 1
        return None

    monkeypatch.setattr(MarketSchedule, "_lookup_pykrx_market_open", classmethod(_fake_lookup))
    monkeypatch.setattr(
        MarketSchedule,
        "_current_validation_token",
        classmethod(lambda cls, now=None: token["value"]),
    )
    monkeypatch.setattr(
        MarketSchedule,
        "_market_schedule_sqlite_cache_context",
        classmethod(
            lambda cls, target_date: (
                str(tmp_path / ".market_schedule_cache" / f"{target_date.isoformat()}.snapshot"),
                (int(target_date.strftime("%Y%m%d")), 29),
            )
        ),
    )

    with MarketSchedule._cache_lock:
        MarketSchedule._open_cache.clear()
        MarketSchedule._holiday_validation_cache.clear()

    target_day = date(2026, 2, 17)  # fallback holiday
    assert MarketSchedule.is_market_open(target_day) is False
    assert calls["count"] == 1

    token["value"] = "20260227"
    assert MarketSchedule.is_market_open(target_day) is False
    assert calls["count"] == 2
