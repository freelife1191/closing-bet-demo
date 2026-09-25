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
    # [FLOW-031] 하반기. 6/3·7/17·8/17 은 로컬 가격 CSV 에 거래가 없던 평일, 나머지는 공휴일 달력(KRX 공고와 대조하지 않음)
    for day in (
        date(2026, 6, 3), date(2026, 7, 17), date(2026, 8, 17), date(2026, 9, 24), date(2026, 9, 25),
        date(2026, 10, 5), date(2026, 10, 9), date(2026, 12, 25), date(2026, 12, 31),
    ):
        assert MarketSchedule.is_market_open(day) is False, day


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


def _market_schedule_warnings(caplog):
    """다른 로거가 같은 구간에 남긴 경고를 섞지 않는다."""
    return [
        record
        for record in caplog.records
        if record.levelname == "WARNING" and record.name == "engine.market_schedule"
    ]

def test_known_holidays_warns_once_for_a_year_the_calendar_does_not_cover(monkeypatch, caplog):
    MarketSchedule._warn_fallback_calendar_expired.cache_clear()
    # 오늘이 캘린더가 담지 못한 해인 상황을 만든다.
    monkeypatch.setattr(MarketSchedule, "_fallback_holiday_last_year", 2020)

    with caplog.at_level("WARNING", logger="engine.market_schedule"):
        first = MarketSchedule.known_holidays()
        second = MarketSchedule.known_holidays()

    warnings = _market_schedule_warnings(caplog)
    assert len(warnings) == 1
    assert str(date.today().year) in warnings[0].getMessage()
    # 경고는 알림일 뿐이므로 돌려주는 목록 자체는 달라지지 않는다.
    assert first == second == tuple(sorted(MarketSchedule._fallback_holidays))
    # 남겨 두면 뒤에 도는 검사가 같은 키에 걸려 경고를 못 본다.
    MarketSchedule._warn_fallback_calendar_expired.cache_clear()


def test_known_holidays_stays_quiet_for_a_year_the_calendar_covers(monkeypatch, caplog):
    MarketSchedule._warn_fallback_calendar_expired.cache_clear()
    monkeypatch.setattr(MarketSchedule, "_fallback_holiday_last_year", date.today().year)

    with caplog.at_level("WARNING", logger="engine.market_schedule"):
        holidays = MarketSchedule.known_holidays()

    assert _market_schedule_warnings(caplog) == []
    assert holidays == tuple(sorted(MarketSchedule._fallback_holidays))
