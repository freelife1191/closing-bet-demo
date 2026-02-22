#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KRX 장 개장일 판별 유틸.
"""

from __future__ import annotations

from datetime import date
from collections import OrderedDict
from threading import Lock


class MarketSchedule:
    """한국 증시 개장 여부 판별."""

    _cache_lock = Lock()
    _open_cache: OrderedDict[date, bool] = OrderedDict()
    _open_cache_max_entries = 1_024

    # pykrx 조회 실패 시 사용되는 보수적(휴장일 중심) 폴백 캘린더
    _fallback_holidays: set[date] = {
        date(2026, 1, 1),
        date(2026, 2, 16),  # 설 연휴
        date(2026, 2, 17),  # 설 연휴
        date(2026, 2, 18),  # 설 연휴
        date(2026, 3, 1),   # 삼일절
        date(2026, 3, 2),   # 삼일절 대체공휴일
        date(2026, 5, 5),   # 어린이날
        date(2026, 5, 24),  # 부처님오신날
        date(2026, 5, 25),  # 대체공휴일
    }

    @classmethod
    def _lookup_pykrx_market_open(cls, target_date: date) -> bool | None:
        try:
            from pykrx import stock

            day = target_date.strftime("%Y%m%d")
            frame = stock.get_index_ohlcv_by_date(day, day, "1001")
            return not frame.empty
        except Exception:
            return None

    @classmethod
    def _set_open_cache(cls, target_date: date, is_open: bool) -> None:
        cls._open_cache[target_date] = bool(is_open)
        cls._open_cache.move_to_end(target_date)
        normalized_max_entries = max(1, int(cls._open_cache_max_entries))
        while len(cls._open_cache) > normalized_max_entries:
            cls._open_cache.popitem(last=False)

    @classmethod
    def is_market_open(cls, target_date: date) -> bool:
        if not isinstance(target_date, date):
            return False
        if target_date.weekday() >= 5:
            return False

        pykrx_open = cls._lookup_pykrx_market_open(target_date)
        if pykrx_open is not None:
            is_open = bool(pykrx_open)
            with cls._cache_lock:
                cls._set_open_cache(target_date, is_open)
            return is_open

        with cls._cache_lock:
            cached = cls._open_cache.get(target_date)
            if cached is not None:
                cls._open_cache.move_to_end(target_date)
                return cached

        is_open = target_date not in cls._fallback_holidays

        with cls._cache_lock:
            cls._set_open_cache(target_date, is_open)
        return is_open


__all__ = ["MarketSchedule"]
