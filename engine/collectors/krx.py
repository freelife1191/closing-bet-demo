#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KRX Collector Module

KRX(한국거래소) 데이터를 수집하는 클래스입니다.
"""

from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timedelta

from services.kr_market_data_cache_sqlite_payload import (
    load_json_payload_from_sqlite as _load_json_payload_from_sqlite,
    save_json_payload_to_sqlite as _save_json_payload_to_sqlite,
)

from engine.collectors.base import BaseCollector
from engine.collectors.krx_data_mixin import KRXCollectorDataMixin


logger = logging.getLogger(__name__)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class KRXCollector(KRXCollectorDataMixin, BaseCollector):
    """KRX 데이터 수집기."""

    _market_date_warning_shown = False
    _market_date_cache_lock = threading.Lock()
    _market_date_cache: dict[str, str] = {}
    _market_date_sqlite_max_rows = 512
    _stock_name_sqlite_cache_lock = threading.Lock()
    _stock_name_sqlite_max_rows = 8_192

    def __init__(self, config=None):
        super().__init__(config)
        self._stock_name_cache: dict[str, str] = {}
        self._sector_cache: dict[str, str] = {}

    @classmethod
    def _stable_token_to_int(cls, token: str) -> int:
        normalized = str(token or "")
        if normalized.isdigit():
            try:
                return int(normalized)
            except Exception:
                pass
        acc = 17
        for char in normalized:
            acc = (acc * 31 + ord(char)) % 2_000_000_000
        return int(acc)

    @classmethod
    def _latest_market_date_cache_token(cls, now: datetime) -> str:
        weekday = int(now.weekday())
        if weekday == 5:
            return f"{now.strftime('%Y%m%d')}:saturday"
        if weekday == 6:
            return f"{now.strftime('%Y%m%d')}:sunday"

        market_close_hour = 15
        market_close_minute = 30
        is_before_close = (
            now.hour < market_close_hour
            or (now.hour == market_close_hour and now.minute < market_close_minute)
        )
        session = "preclose" if is_before_close else "postclose"
        return f"{now.strftime('%Y%m%d')}:{session}"

    @classmethod
    def _latest_market_date_sqlite_context(cls, cache_token: str) -> tuple[str, tuple[int, int]]:
        sqlite_key = os.path.join(
            BASE_DIR,
            "data",
            ".krx_collector_cache",
            f"latest_market_date__{cache_token}.snapshot",
        )
        signature = (
            cls._stable_token_to_int(cache_token),
            cls._stable_token_to_int("krx_collector_latest_market_date"),
        )
        return sqlite_key, signature

    @classmethod
    def _load_cached_latest_market_date(cls, cache_token: str) -> str | None:
        with cls._market_date_cache_lock:
            cached = cls._market_date_cache.get(cache_token)
            if isinstance(cached, str) and cached:
                return cached

        sqlite_key, signature = cls._latest_market_date_sqlite_context(cache_token)
        try:
            loaded, payload = _load_json_payload_from_sqlite(
                filepath=sqlite_key,
                signature=signature,
                logger=logger,
            )
        except Exception as error:
            logger.debug("KRX latest market date SQLite cache load failed: %s", error)
            return None

        if not loaded or not isinstance(payload, dict):
            return None

        latest_date = payload.get("latest_market_date")
        if not isinstance(latest_date, str) or not latest_date:
            return None

        with cls._market_date_cache_lock:
            cls._market_date_cache[cache_token] = latest_date
        return latest_date

    @classmethod
    def _save_cached_latest_market_date(cls, cache_token: str, latest_market_date: str) -> None:
        normalized_date = str(latest_market_date or "").strip()
        if not normalized_date:
            return

        with cls._market_date_cache_lock:
            cls._market_date_cache[cache_token] = normalized_date

        sqlite_key, signature = cls._latest_market_date_sqlite_context(cache_token)
        try:
            _save_json_payload_to_sqlite(
                filepath=sqlite_key,
                signature=signature,
                payload={"latest_market_date": normalized_date},
                max_rows=cls._market_date_sqlite_max_rows,
                logger=logger,
            )
        except Exception as error:
            logger.debug("KRX latest market date SQLite cache save failed: %s", error)

    @classmethod
    def clear_latest_market_date_cache(cls) -> None:
        with cls._market_date_cache_lock:
            cls._market_date_cache.clear()

    @classmethod
    def _stock_name_sqlite_context(cls, ticker: str) -> tuple[str, tuple[int, int]]:
        normalized_ticker = str(ticker).zfill(6)
        sqlite_key = os.path.join(
            BASE_DIR,
            "data",
            ".krx_collector_cache",
            "stock_name",
            f"{normalized_ticker}.snapshot",
        )
        signature = (
            cls._stable_token_to_int(normalized_ticker),
            cls._stable_token_to_int("krx_collector_stock_name_v1"),
        )
        return sqlite_key, signature

    @classmethod
    def _load_cached_stock_name(cls, ticker: str) -> str | None:
        sqlite_key, signature = cls._stock_name_sqlite_context(ticker)
        try:
            with cls._stock_name_sqlite_cache_lock:
                loaded, payload = _load_json_payload_from_sqlite(
                    filepath=sqlite_key,
                    signature=signature,
                    logger=logger,
                )
        except Exception as error:
            logger.debug("KRX stock name SQLite cache load failed (%s): %s", ticker, error)
            return None

        if not loaded or not isinstance(payload, dict):
            return None
        cached_name = payload.get("name")
        if not isinstance(cached_name, str) or not cached_name.strip():
            return None
        return cached_name.strip()

    @classmethod
    def _save_cached_stock_name(cls, ticker: str, stock_name: str) -> None:
        normalized_name = str(stock_name or "").strip()
        if not normalized_name:
            return

        sqlite_key, signature = cls._stock_name_sqlite_context(ticker)
        try:
            with cls._stock_name_sqlite_cache_lock:
                _save_json_payload_to_sqlite(
                    filepath=sqlite_key,
                    signature=signature,
                    payload={"name": normalized_name},
                    max_rows=cls._stock_name_sqlite_max_rows,
                    logger=logger,
                )
        except Exception as error:
            logger.debug("KRX stock name SQLite cache save failed (%s): %s", ticker, error)

    def _get_latest_market_date(self) -> str:
        """가장 최근 장 마감 날짜를 반환한다 (pykrx + SQLite snapshot)."""
        now = datetime.now()
        cache_token = self._latest_market_date_cache_token(now)
        cached_market_date = self._load_cached_latest_market_date(cache_token)
        if isinstance(cached_market_date, str) and cached_market_date:
            return cached_market_date

        weekday = now.weekday()
        market_close_hour = 15
        market_close_minute = 30

        if weekday == 5:
            target = now - timedelta(days=1)
        elif weekday == 6:
            target = now - timedelta(days=2)
        elif now.hour < market_close_hour or (now.hour == market_close_hour and now.minute < market_close_minute):
            if weekday == 0:
                target = now - timedelta(days=3)
            else:
                target = now - timedelta(days=1)
        else:
            target = now

        try:
            from pykrx import stock

            start_check = (target - timedelta(days=10)).strftime("%Y%m%d")
            end_check = target.strftime("%Y%m%d")
            kospi_data = stock.get_index_ohlcv_by_date(start_check, end_check, "1001")
            if not kospi_data.empty:
                resolved_date = kospi_data.index[-1].strftime("%Y%m%d")
                self._save_cached_latest_market_date(cache_token, resolved_date)
                return resolved_date
        except ImportError:
            if not self._market_date_warning_shown:
                logger.warning("pykrx 미설치 - 주말 처리만 적용")
                KRXCollector._market_date_warning_shown = True
        except Exception as error:
            if not self._market_date_warning_shown:
                logger.warning(f"개장일 확인 실패: {error} - 주말 처리만 적용")
                KRXCollector._market_date_warning_shown = True

        fallback_date = target.strftime("%Y%m%d")
        self._save_cached_latest_market_date(cache_token, fallback_date)
        return fallback_date

    def _get_stock_name(self, ticker: str) -> str:
        """종목명 조회 (pykrx 사용)."""
        normalized = str(ticker).zfill(6)
        cached = self._stock_name_cache.get(normalized)
        if cached:
            return cached

        sqlite_cached_name = self._load_cached_stock_name(normalized)
        if sqlite_cached_name:
            self._stock_name_cache[normalized] = sqlite_cached_name
            return sqlite_cached_name

        try:
            from pykrx import stock

            name = stock.get_market_ticker_name(normalized)
            if name:
                self._stock_name_cache[normalized] = name
                self._save_cached_stock_name(normalized, name)
                return name
        except Exception as error:
            logger.debug(f"종목명 조회 실패 ({normalized}): {error}")

        names = {
            "005930": "삼성전자",
            "000270": "기아",
            "035420": "NAVER",
            "005380": "현대차",
            "015760": "한화사이언스",
            "068270": "셀트리온",
            "052190": "삼성에스디에스",
            "011200": "HMM",
            "096770": "SK이노베이션",
            "066570": "LG전자",
            "056080": "유진로봇",
        }
        fallback_name = names.get(normalized, "알 수 없는 종목")
        self._stock_name_cache[normalized] = fallback_name
        if fallback_name != "알 수 없는 종목":
            self._save_cached_stock_name(normalized, fallback_name)
        return fallback_name

    def _get_sector(self, ticker: str) -> str:
        """섹터 조회."""
        normalized = str(ticker).zfill(6)
        cached = self._sector_cache.get(normalized)
        if cached:
            return cached

        try:
            from pykrx import stock

            pass
        except Exception as error:
            logger.debug(f"섹터 조회 기본 경로 실패 ({normalized}): {error}")

        sectors = {
            "005930": "반도체",
            "000270": "자동차",
            "035420": "인터넷",
            "005380": "자동차",
            "015760": "반도체",
            "068270": "헬스케어",
            "052190": "반도체",
            "011200": "해운",
            "096770": "통신",
            "066570": "2차전지",
            "056080": "로봇",
        }
        fallback_sector = sectors.get(normalized, "기타")
        self._sector_cache[normalized] = fallback_sector
        return fallback_sector
