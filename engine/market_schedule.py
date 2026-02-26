#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KRX 장 개장일 판별 유틸.
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime
from collections import OrderedDict
from threading import Lock

from services.kr_market_data_cache_sqlite_payload import (
    load_json_payload_from_sqlite,
    save_json_payload_to_sqlite,
)

logger = logging.getLogger(__name__)


class MarketSchedule:
    """한국 증시 개장 여부 판별."""

    _cache_lock = Lock()
    _open_cache: OrderedDict[date, bool] = OrderedDict()
    _holiday_validation_cache: OrderedDict[date, str] = OrderedDict()
    _open_cache_max_entries = 1_024
    _sqlite_cache_max_rows = 2_048
    _sqlite_signature_salt = "market_schedule_v1"

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
    def _stable_token_to_int(cls, token: str) -> int:
        normalized = str(token or "")
        if normalized.isdigit():
            try:
                return int(normalized)
            except Exception:
                pass
        acc = 17
        for ch in normalized:
            acc = (acc * 31 + ord(ch)) % 2_000_000_000
        return int(acc)

    @classmethod
    def _market_schedule_sqlite_cache_context(cls, target_date: date) -> tuple[str, tuple[int, int]]:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cache_key = os.path.join(
            base_dir,
            "data",
            ".market_schedule_cache",
            f"{target_date.isoformat()}.snapshot",
        )
        holiday_token = "|".join(sorted(day.isoformat() for day in cls._fallback_holidays))
        signature_token = f"{cls._sqlite_signature_salt}:{holiday_token}"
        signature = (
            int(target_date.strftime("%Y%m%d")),
            cls._stable_token_to_int(signature_token),
        )
        return cache_key, signature

    @classmethod
    def _current_validation_token(cls, now: datetime | None = None) -> str:
        normalized_now = now or datetime.now()
        return normalized_now.strftime("%Y%m%d")

    @classmethod
    def _load_market_open_from_sqlite(cls, target_date: date) -> tuple[bool | None, str | None]:
        cache_key, signature = cls._market_schedule_sqlite_cache_context(target_date)
        try:
            loaded, payload = load_json_payload_from_sqlite(
                filepath=cache_key,
                signature=signature,
                logger=logger,
            )
        except Exception as exc:
            logger.debug("[MarketSchedule] SQLite 캐시 로드 실패 (%s): %s", target_date, exc)
            return None, None

        if not loaded or not isinstance(payload, dict):
            return None, None

        value = payload.get("is_open")
        validation_token_raw = str(payload.get("validated_on") or "").strip()
        validation_token = validation_token_raw if validation_token_raw else None
        if isinstance(value, bool):
            return value, validation_token
        if isinstance(value, (int, float)):
            return bool(value), validation_token
        return None, validation_token

    @classmethod
    def _save_market_open_to_sqlite(
        cls,
        target_date: date,
        is_open: bool,
        *,
        validation_token: str | None = None,
    ) -> None:
        cache_key, signature = cls._market_schedule_sqlite_cache_context(target_date)
        payload: dict[str, object] = {"is_open": bool(is_open)}
        if isinstance(validation_token, str) and validation_token:
            payload["validated_on"] = validation_token
        try:
            save_json_payload_to_sqlite(
                filepath=cache_key,
                signature=signature,
                payload=payload,
                max_rows=cls._sqlite_cache_max_rows,
                logger=logger,
            )
        except Exception as exc:
            logger.debug("[MarketSchedule] SQLite 캐시 저장 실패 (%s): %s", target_date, exc)

    @classmethod
    def _lookup_pykrx_market_open(cls, target_date: date) -> bool | None:
        root_logger = logging.getLogger()
        previous_root_level = root_logger.level
        suppress_pykrx_info = root_logger.isEnabledFor(logging.INFO)
        if suppress_pykrx_info:
            # pykrx 내부에서 logging.info(args, kwargs) 형태의 포맷 버그가 있어
            # 예외 상황에서 불필요한 Logging error 스택트레이스가 발생한다.
            root_logger.setLevel(logging.WARNING)
        try:
            from pykrx import stock

            day = target_date.strftime("%Y%m%d")
            prev_business_day = stock.get_nearest_business_day_in_a_week(day, prev=True)
            next_business_day = stock.get_nearest_business_day_in_a_week(day, prev=False)
            return day in {prev_business_day, next_business_day}
        except Exception as exc:
            logger.debug("[MarketSchedule] pykrx 영업일 조회 실패 (%s): %s", target_date, exc)
            return None
        finally:
            if suppress_pykrx_info:
                root_logger.setLevel(previous_root_level)

    @classmethod
    def _set_open_cache(
        cls,
        target_date: date,
        is_open: bool,
        *,
        validation_token: str | None = None,
    ) -> None:
        cls._open_cache[target_date] = bool(is_open)
        cls._open_cache.move_to_end(target_date)
        normalized_max_entries = max(1, int(cls._open_cache_max_entries))
        while len(cls._open_cache) > normalized_max_entries:
            cls._open_cache.popitem(last=False)
        if isinstance(validation_token, str) and validation_token:
            cls._holiday_validation_cache[target_date] = validation_token
            cls._holiday_validation_cache.move_to_end(target_date)
            while len(cls._holiday_validation_cache) > normalized_max_entries:
                cls._holiday_validation_cache.popitem(last=False)
        else:
            cls._holiday_validation_cache.pop(target_date, None)

    @classmethod
    def _should_validate_cached_result_with_pykrx(
        cls,
        target_date: date,
        is_open: bool,
        *,
        validation_token: str | None = None,
    ) -> bool:
        # fallback holiday 대상 날짜는 캐시가 true/false 어느 값이든 pykrx 재검증 기회를 보장한다.
        # (예: 과거 캐시/환경 차이로 생성된 stale true를 그대로 신뢰하지 않는다)
        if target_date not in cls._fallback_holidays:
            return False
        normalized_token = str(validation_token or "").strip()
        if not normalized_token:
            return True
        return normalized_token != cls._current_validation_token()

    @classmethod
    def is_market_open(cls, target_date: date) -> bool:
        if not isinstance(target_date, date):
            return False
        if target_date.weekday() >= 5:
            return False

        cached_open: bool | None = None
        with cls._cache_lock:
            cached = cls._open_cache.get(target_date)
            if cached is not None:
                cached_bool = bool(cached)
                cached_validation_token = cls._holiday_validation_cache.get(target_date)
                if not cls._should_validate_cached_result_with_pykrx(
                    target_date,
                    cached_bool,
                    validation_token=cached_validation_token,
                ):
                    cls._open_cache.move_to_end(target_date)
                    if cached_validation_token:
                        cls._holiday_validation_cache.move_to_end(target_date)
                    return cached_bool
                cached_open = cached_bool

        sqlite_cached, sqlite_validation_token = cls._load_market_open_from_sqlite(target_date)
        if sqlite_cached is not None:
            sqlite_cached_bool = bool(sqlite_cached)
            if not cls._should_validate_cached_result_with_pykrx(
                target_date,
                sqlite_cached_bool,
                validation_token=sqlite_validation_token,
            ):
                with cls._cache_lock:
                    cls._set_open_cache(
                        target_date,
                        sqlite_cached_bool,
                        validation_token=sqlite_validation_token,
                    )
                return sqlite_cached_bool
            cached_open = sqlite_cached_bool

        validation_token: str | None = None
        pykrx_open = cls._lookup_pykrx_market_open(target_date)
        if target_date in cls._fallback_holidays:
            validation_token = cls._current_validation_token()
        if pykrx_open is not None:
            is_open = bool(pykrx_open)
        else:
            if target_date in cls._fallback_holidays:
                is_open = False
            elif cached_open is not None:
                is_open = bool(cached_open)
            else:
                is_open = target_date not in cls._fallback_holidays
        with cls._cache_lock:
            cls._set_open_cache(
                target_date,
                is_open,
                validation_token=validation_token,
            )
        cls._save_market_open_to_sqlite(
            target_date,
            is_open,
            validation_token=validation_token,
        )
        return is_open


__all__ = ["MarketSchedule"]
