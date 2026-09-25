#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Collectors (데이터 수집기)
"""

from collections import OrderedDict
from datetime import datetime, timedelta
import logging
import os
import threading

from engine.collectors.base import BaseCollector
from engine.collectors.krx_data_mixin import KRXCollectorDataMixin
from services.kr_market_data_cache_sqlite_payload import load_json_payload_from_sqlite as _load_json_payload_from_sqlite, save_json_payload_to_sqlite as _save_json_payload_to_sqlite

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class KRXCollector(KRXCollectorDataMixin, BaseCollector):
    _market_date_warning_shown = False

    _market_date_cache_lock = threading.Lock()

    _market_date_cache: dict[str, str] = {}

    _market_date_sqlite_max_rows = 512

    _market_date_sqlite_namespace_dir = ".krx_collector_cache"

    _top_gainers_cache_lock = threading.Lock()

    _top_gainers_cache: OrderedDict[tuple[str, str, int, str, int, int], dict[str, object]] = OrderedDict()

    _top_gainers_memory_max_entries = 64

    _top_gainers_sqlite_max_rows = 512

    _pykrx_chart_cache_lock = threading.Lock()

    _pykrx_chart_cache: OrderedDict[tuple[str, str, int], dict[str, object]] = OrderedDict()

    _pykrx_chart_memory_max_entries = 512

    _pykrx_chart_sqlite_max_rows = 4_096

    _stock_name_sqlite_cache_lock = threading.Lock()

    _stock_name_sqlite_max_rows = 8_192

    _stock_name_memory_max_entries = 4_096

    _stock_lookup_cache_lock = threading.Lock()

    _stock_lookup_cache: OrderedDict[tuple[str, int, int], dict[str, dict[str, str]]] = OrderedDict()

    _stock_lookup_memory_max_entries = 256

    _stock_lookup_sqlite_max_rows = 2_048

    def __init__(self, config=None):
        super().__init__(config)
        self._stock_name_cache: OrderedDict[str, str] = OrderedDict()

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
        cache_key = os.path.join(
            BASE_DIR,
            "data",
            cls._market_date_sqlite_namespace_dir,
            f"latest_market_date__{cache_token}.snapshot",
        )
        signature = (
            cls._stable_token_to_int(cache_token),
            cls._stable_token_to_int("krx_collector_latest_market_date"),
        )
        return cache_key, signature

    @classmethod
    def _load_cached_latest_market_date(cls, cache_token: str) -> str | None:
        with cls._market_date_cache_lock:
            cached = cls._market_date_cache.get(cache_token)
            if isinstance(cached, str) and cached:
                return cached

        sqlite_key, sqlite_signature = cls._latest_market_date_sqlite_context(cache_token)
        try:
            loaded, payload = _load_json_payload_from_sqlite(
                filepath=sqlite_key,
                signature=sqlite_signature,
                logger=logger,
            )
        except Exception as error:
            logger.debug("KRX latest market date SQLite cache load failed: %s", error)
            return None

        if not loaded or not isinstance(payload, dict):
            return None
        value = payload.get("latest_market_date")
        if not isinstance(value, str) or not value:
            return None

        with cls._market_date_cache_lock:
            cls._market_date_cache[cache_token] = value
        return value

    @classmethod
    def _save_cached_latest_market_date(cls, cache_token: str, latest_market_date: str) -> None:
        normalized_value = str(latest_market_date or "").strip()
        if not normalized_value:
            return

        with cls._market_date_cache_lock:
            cls._market_date_cache[cache_token] = normalized_value

        sqlite_key, sqlite_signature = cls._latest_market_date_sqlite_context(cache_token)
        try:
            _save_json_payload_to_sqlite(
                filepath=sqlite_key,
                signature=sqlite_signature,
                payload={"latest_market_date": normalized_value},
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
    def clear_stock_lookup_cache(cls) -> None:
        with cls._stock_lookup_cache_lock:
            cls._stock_lookup_cache.clear()

    @classmethod
    def _stock_name_sqlite_context(cls, ticker: str) -> tuple[str, tuple[int, int]]:
        normalized_ticker = str(ticker).zfill(6)
        cache_key = os.path.join(
            BASE_DIR,
            "data",
            cls._market_date_sqlite_namespace_dir,
            "stock_name",
            f"{normalized_ticker}.snapshot",
        )
        signature = (
            cls._stable_token_to_int(normalized_ticker),
            cls._stable_token_to_int("krx_collector_stock_name_v1"),
        )
        return cache_key, signature

    def _set_stock_name_memory_cache(self, ticker: str, stock_name: str) -> None:
        ticker_key = str(ticker).zfill(6)
        name_value = str(stock_name or "").strip()
        if not ticker_key or not name_value:
            return

        self._stock_name_cache[ticker_key] = name_value
        self._stock_name_cache.move_to_end(ticker_key)
        normalized_max_entries = max(1, int(self._stock_name_memory_max_entries))
        while len(self._stock_name_cache) > normalized_max_entries:
            self._stock_name_cache.popitem(last=False)

    def _load_cached_stock_name(self, ticker: str) -> str | None:
        ticker_key = str(ticker).zfill(6)
        cached = self._stock_name_cache.get(ticker_key)
        if isinstance(cached, str) and cached:
            self._stock_name_cache.move_to_end(ticker_key)
            return cached

        sqlite_key, sqlite_signature = self._stock_name_sqlite_context(ticker_key)
        try:
            with self._stock_name_sqlite_cache_lock:
                loaded, payload = _load_json_payload_from_sqlite(
                    filepath=sqlite_key,
                    signature=sqlite_signature,
                    logger=logger,
                )
        except Exception as error:
            logger.debug("KRX stock name SQLite cache load failed (%s): %s", ticker_key, error)
            return None

        if not loaded or not isinstance(payload, dict):
            return None

        cached_name = str(payload.get("name") or "").strip()
        if not cached_name:
            return None
        self._set_stock_name_memory_cache(ticker_key, cached_name)
        return cached_name

    def _save_cached_stock_name(self, ticker: str, stock_name: str) -> None:
        ticker_key = str(ticker).zfill(6)
        normalized_name = str(stock_name or "").strip()
        if not ticker_key or not normalized_name:
            return

        self._set_stock_name_memory_cache(ticker_key, normalized_name)
        sqlite_key, sqlite_signature = self._stock_name_sqlite_context(ticker_key)
        try:
            with self._stock_name_sqlite_cache_lock:
                _save_json_payload_to_sqlite(
                    filepath=sqlite_key,
                    signature=sqlite_signature,
                    payload={"name": normalized_name},
                    max_rows=self._stock_name_sqlite_max_rows,
                    logger=logger,
                )
        except Exception as error:
            logger.debug("KRX stock name SQLite cache save failed (%s): %s", ticker_key, error)

    def _get_latest_market_date(self) -> str:
        """
        가장 최근 장 마감 날짜 반환
        - 주말(토/일): 금요일 날짜 반환
        - 금요일이 휴일인 경우: pykrx를 통해 실제 마지막 개장일 확인
        - 평일 장 마감 전(~15:30): 전일 날짜 반환
        - 평일 장 마감 후(15:30~): 당일 날짜 반환
        """
        now = datetime.now()
        cache_token = self._latest_market_date_cache_token(now)
        cached_market_date = self._load_cached_latest_market_date(cache_token)
        if isinstance(cached_market_date, str) and cached_market_date:
            return cached_market_date

        weekday = now.weekday()  # 0=월, 1=화, ..., 5=토, 6=일

        # 장 마감 시간 (15:30)
        market_close_hour = 15
        market_close_minute = 30

        if weekday == 5:  # 토요일 -> 금요일
            target = now - timedelta(days=1)
        elif weekday == 6:  # 일요일 -> 금요일
            target = now - timedelta(days=2)
        elif now.hour < market_close_hour or (now.hour == market_close_hour and now.minute < market_close_minute):
            # 평일 장 마감 전 -> 전일 데이터 (주말 건너뛰기)
            if weekday == 0:  # 월요일 아침 -> 금요일
                target = now - timedelta(days=3)
            else:
                target = now - timedelta(days=1)
        else:
            # 평일 장 마감 후 -> 당일 데이터
            target = now

        # pykrx를 통해 실제 개장일 확인 (휴일 대응)
        try:
            from pykrx import stock

            # 최근 10일간 거래일 조회 (휴일 연속 대비)
            start_check = (target - timedelta(days=10)).strftime('%Y%m%d')
            end_check = target.strftime('%Y%m%d')

            # KOSPI 지수의 OHLCV로 개장일 확인
            kospi_data = stock.get_index_ohlcv_by_date(start_check, end_check, "1001")

            if not kospi_data.empty:
                # 마지막 거래일을 가져옴
                last_trading_date = kospi_data.index[-1]
                last_trading_date_str = last_trading_date.strftime('%Y%m%d')
                self._save_cached_latest_market_date(cache_token, last_trading_date_str)
                return last_trading_date_str

        except ImportError:
            if not self._market_date_warning_shown:
                logger.warning("pykrx 미설치 - 주말 처리만 적용")
                KRXCollector._market_date_warning_shown = True
        except Exception as e:
            if not self._market_date_warning_shown:
                logger.warning(f"개장일 확인 실패: {e} - 주말 처리만 적용")
                KRXCollector._market_date_warning_shown = True

        # 폴백: 주말 처리만 된 날짜 반환
        fallback_date_str = target.strftime('%Y%m%d')
        self._save_cached_latest_market_date(cache_token, fallback_date_str)
        return fallback_date_str

    def _get_stock_name(self, ticker: str) -> str:
        """종목명 조회"""
        normalized_ticker = str(ticker).zfill(6)
        cached_name = self._load_cached_stock_name(normalized_ticker)
        if cached_name:
            return cached_name

        try:
            from pykrx import stock

            resolved_name = str(stock.get_market_ticker_name(normalized_ticker) or "").strip()
            if resolved_name:
                self._save_cached_stock_name(normalized_ticker, resolved_name)
                return resolved_name
        except Exception as error:
            logger.debug("종목명 조회 실패 (%s): %s", normalized_ticker, error)

        names = {
            '005930': '삼성전자', '000270': '기아', '035420': 'NAVER',
            '005380': '현대차', '015760': '한화사이언스',
            '068270': '셀트리온', '052190': '삼성에스디에스',
            '011200': 'HMM', '096770': 'SK이노베이션', '066570': 'LG전자'
        }
        fallback_name = names.get(normalized_ticker, '알 수 없는 종목')
        if fallback_name != '알 수 없는 종목':
            self._save_cached_stock_name(normalized_ticker, fallback_name)
        return fallback_name

    def _get_sector(self, ticker: str) -> str:
        """섹터 조회"""
        sectors = {
            '005930': '반도체', '000270': '자동차', '035420': '인터넷',
            '005380': '자동차', '015760': '반도체', '068270': '헬스케어',
            '052190': '반도체', '011200': '해운', '096770': '통신',
            '066570': '2차전지'
        }
        return sectors.get(ticker, '기타')
