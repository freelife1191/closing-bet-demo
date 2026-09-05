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
from functools import lru_cache
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

    # 폴백 캘린더를 손으로 채운 마지막 해. _fallback_holidays 에 다음 해의 날짜를
    # 더할 때 이 값도 함께 올린다. 목록에서 max().year 로 계산하지 않는 이유는, 한 해의
    # 일부만 채운 상태를 「그 해를 안다」로 잘못 판정하기 때문이다. 뒤집어 말하면 목록이
    # 상수보다 앞선 해를 담고 있는 것은 정상이므로, 둘이 어긋났는지는 검사로 가릴 수 없다.
    _fallback_holiday_last_year = 2026

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

    @staticmethod
    @lru_cache
    def _warn_fallback_calendar_expired(last_year: int, asked_year: int) -> None:
        # known_holidays 는 종목마다 도는 판정에서 불리므로 워커마다 연도당 한 번만 내보낸다.
        logger.warning(
            "[MarketSchedule] 폴백 휴장일 목록이 %d년까지만 채워져 있어 %d년 휴장일을 "
            "한 건도 알지 못합니다. 한국거래소 휴장일 공고를 보고 engine/market_schedule.py "
            "의 _fallback_holidays 에 그 해의 휴장일을 넣은 다음 "
            "_fallback_holiday_last_year 를 올려 주십시오.",
            last_year,
            asked_year,
        )

    @classmethod
    def known_holidays(cls) -> tuple[date, ...]:
        """pykrx 없이 알 수 있는 휴장일을 날짜 순으로 돌려준다.

        is_market_open 은 하루를 판정하려고 pykrx 를 조회할 수 있다. 날짜 구간을
        훑어야 하는 쪽은 그 비용을 감당할 수 없으므로, 네트워크 없이 아는 만큼만
        내주는 자리를 따로 둔다.

        _fallback_holidays 는 해마다 손으로 채우는 목록이라서, 아직 채우지 않은 해에는
        휴장일이 한 건도 없는 것과 같아진다. 그 상태를 「휴장일이 없는 해」로 오해하지
        않도록, _fallback_holiday_last_year 를 지난 해가 조회되면 경고를 남긴다.
        돌려주는 값 자체는 달라지지 않으므로 호출하는 쪽의 동작은 그대로다.
        """
        asked_year = date.today().year
        if asked_year > cls._fallback_holiday_last_year:
            cls._warn_fallback_calendar_expired(cls._fallback_holiday_last_year, asked_year)
        return tuple(sorted(cls._fallback_holidays))

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
