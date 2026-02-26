#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Collectors (데이터 수집기)
"""
import logging
import math
import os
import threading
from collections import OrderedDict
from typing import Any, Dict, List, Optional
from datetime import date, datetime, timedelta
from engine.models import StockData, ChartData, NewsItem, SupplyData
from services.kr_market_data_cache_service import (
    file_signature as _shared_file_signature,
    load_csv_file as _load_shared_csv_file,
)
from services.kr_market_data_cache_sqlite_payload import (
    load_json_payload_from_sqlite as _load_json_payload_from_sqlite,
    save_json_payload_to_sqlite as _save_json_payload_to_sqlite,
)
from services.investor_trend_5day_service import (
    get_investor_trend_5day_for_ticker,
)

logger = logging.getLogger(__name__)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 리팩토링 과정에서 `engine/collectors.py`와 `engine/collectors/` 디렉토리가 공존한다.
# 모듈이 패키지처럼 동작하도록 __path__를 지정해 하위 모듈 import 호환을 유지한다.
_COLLECTORS_SUBMODULE_PATH = os.path.join(os.path.dirname(__file__), "collectors")
if os.path.isdir(_COLLECTORS_SUBMODULE_PATH):
    __path__ = [_COLLECTORS_SUBMODULE_PATH]  # type: ignore[assignment]


class KRXCollector:
    """KRX 데이터 수집기"""


    # 경고 로그 중복 출력 방지 플래그
    _market_date_warning_shown = False
    _market_date_cache_lock = threading.Lock()
    _market_date_cache: dict[str, str] = {}
    _market_date_sqlite_max_rows = 512
    _market_date_sqlite_namespace_dir = ".krx_collector_cache"
    _top_gainers_cache_lock = threading.Lock()
    _top_gainers_cache: OrderedDict[tuple[str, str, int, str, int, int], dict[str, object]] = OrderedDict()
    _top_gainers_memory_max_entries = 64
    _top_gainers_sqlite_max_rows = 512
    _pykrx_supply_cache_lock = threading.Lock()
    _pykrx_supply_cache: OrderedDict[tuple[str, str], dict[str, int]] = OrderedDict()
    _pykrx_supply_memory_max_entries = 1_024
    _pykrx_supply_sqlite_max_rows = 8_192
    _pykrx_chart_cache_lock = threading.Lock()
    _pykrx_chart_cache: OrderedDict[tuple[str, str, int], dict[str, object]] = OrderedDict()
    _pykrx_chart_memory_max_entries = 512
    _pykrx_chart_sqlite_max_rows = 4_096
    _pykrx_fundamental_cache_lock = threading.Lock()
    _pykrx_fundamental_cache: OrderedDict[tuple[str, str], dict[str, float]] = OrderedDict()
    _pykrx_fundamental_memory_max_entries = 2_048
    _pykrx_fundamental_sqlite_max_rows = 16_384
    _stock_name_sqlite_cache_lock = threading.Lock()
    _stock_name_sqlite_max_rows = 8_192
    _stock_name_memory_max_entries = 4_096
    _stock_lookup_cache_lock = threading.Lock()
    _stock_lookup_cache: OrderedDict[tuple[str, int, int], dict[str, dict[str, str]]] = OrderedDict()
    _stock_lookup_memory_max_entries = 256
    _stock_lookup_sqlite_max_rows = 2_048

    def __init__(self, config):
        self.config = config
        self._stock_name_cache: OrderedDict[str, str] = OrderedDict()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

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

    @staticmethod
    def _has_csv_anomaly_flags(trend_data: dict[str, object] | None) -> bool:
        if not isinstance(trend_data, dict):
            return False
        quality = trend_data.get("quality")
        if not isinstance(quality, dict):
            return False
        csv_flags = quality.get("csv_anomaly_flags")
        return isinstance(csv_flags, list) and len(csv_flags) > 0

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

    @classmethod
    def _stock_lookup_memory_cache_key(
        cls,
        *,
        stocks_path: str,
        stocks_signature: tuple[int, int] | None,
    ) -> tuple[str, int, int]:
        normalized_path = os.path.abspath(str(stocks_path or ""))
        if stocks_signature is None:
            sig0, sig1 = 0, 0
        else:
            sig0, sig1 = int(stocks_signature[0]), int(stocks_signature[1])
        return normalized_path, sig0, sig1

    @classmethod
    def _stock_lookup_sqlite_context(
        cls,
        *,
        stocks_path: str,
        stocks_signature: tuple[int, int] | None,
    ) -> tuple[str, tuple[int, int]]:
        normalized_path, sig0, sig1 = cls._stock_lookup_memory_cache_key(
            stocks_path=stocks_path,
            stocks_signature=stocks_signature,
        )
        path_token = cls._stable_token_to_int(normalized_path)
        cache_key = os.path.join(
            BASE_DIR,
            "data",
            cls._market_date_sqlite_namespace_dir,
            "stock_lookup",
            f"{path_token}__{sig0}__{sig1}.snapshot",
        )
        signature_seed = f"{normalized_path}:{sig0}:{sig1}"
        signature = (
            cls._stable_token_to_int(signature_seed),
            cls._stable_token_to_int("krx_collector_stock_lookup_v1"),
        )
        return cache_key, signature

    @classmethod
    def _deserialize_stock_lookup_maps(
        cls,
        payload: dict[str, object],
    ) -> tuple[dict[str, str], dict[str, str]] | None:
        market_payload = payload.get("market_map")
        name_payload = payload.get("name_map")
        if not isinstance(market_payload, dict) or not isinstance(name_payload, dict):
            return None

        market_map: dict[str, str] = {}
        for key, value in market_payload.items():
            if value is None:
                continue
            market_map[str(key).zfill(6)] = str(value)

        name_map: dict[str, str] = {}
        for key, value in name_payload.items():
            if value is None:
                continue
            name_map[str(key).zfill(6)] = str(value)
        return market_map, name_map

    @classmethod
    def _load_cached_stock_lookup_maps(
        cls,
        *,
        stocks_path: str,
        stocks_signature: tuple[int, int],
    ) -> tuple[dict[str, str], dict[str, str]] | None:
        memory_key = cls._stock_lookup_memory_cache_key(
            stocks_path=stocks_path,
            stocks_signature=stocks_signature,
        )
        with cls._stock_lookup_cache_lock:
            cached_payload = cls._stock_lookup_cache.get(memory_key)
            if isinstance(cached_payload, dict):
                market_map = cached_payload.get("market_map")
                name_map = cached_payload.get("name_map")
                if isinstance(market_map, dict) and isinstance(name_map, dict):
                    cls._stock_lookup_cache.move_to_end(memory_key)
                    return dict(market_map), dict(name_map)
                cls._stock_lookup_cache.pop(memory_key, None)

        sqlite_key, sqlite_signature = cls._stock_lookup_sqlite_context(
            stocks_path=stocks_path,
            stocks_signature=stocks_signature,
        )
        try:
            loaded, payload = _load_json_payload_from_sqlite(
                filepath=sqlite_key,
                signature=sqlite_signature,
                logger=logger,
            )
        except Exception as error:
            logger.debug("KRX stock lookup SQLite cache load failed: %s", error)
            return None

        if not loaded or not isinstance(payload, dict):
            return None
        deserialized = cls._deserialize_stock_lookup_maps(payload)
        if deserialized is None:
            return None
        market_map, name_map = deserialized
        normalized_payload = {
            "market_map": dict(market_map),
            "name_map": dict(name_map),
        }
        with cls._stock_lookup_cache_lock:
            cls._stock_lookup_cache[memory_key] = normalized_payload
            cls._stock_lookup_cache.move_to_end(memory_key)
            while len(cls._stock_lookup_cache) > cls._stock_lookup_memory_max_entries:
                cls._stock_lookup_cache.popitem(last=False)
        return market_map, name_map

    @classmethod
    def _save_cached_stock_lookup_maps(
        cls,
        *,
        stocks_path: str,
        stocks_signature: tuple[int, int],
        market_map: dict[str, str],
        name_map: dict[str, str],
    ) -> None:
        memory_key = cls._stock_lookup_memory_cache_key(
            stocks_path=stocks_path,
            stocks_signature=stocks_signature,
        )
        normalized_payload = {
            "market_map": {str(key).zfill(6): str(value) for key, value in market_map.items()},
            "name_map": {str(key).zfill(6): str(value) for key, value in name_map.items()},
        }
        with cls._stock_lookup_cache_lock:
            cls._stock_lookup_cache[memory_key] = normalized_payload
            cls._stock_lookup_cache.move_to_end(memory_key)
            while len(cls._stock_lookup_cache) > cls._stock_lookup_memory_max_entries:
                cls._stock_lookup_cache.popitem(last=False)

        sqlite_key, sqlite_signature = cls._stock_lookup_sqlite_context(
            stocks_path=stocks_path,
            stocks_signature=stocks_signature,
        )
        try:
            _save_json_payload_to_sqlite(
                filepath=sqlite_key,
                signature=sqlite_signature,
                payload=normalized_payload,
                max_rows=cls._stock_lookup_sqlite_max_rows,
                logger=logger,
            )
        except Exception as error:
            logger.debug("KRX stock lookup SQLite cache save failed: %s", error)

    @classmethod
    def _normalize_top_gainers_target_token(cls, target_date: str | None) -> str:
        normalized_target = str(target_date or "").strip()
        if not normalized_target:
            return "latest"
        if len(normalized_target) == 8 and normalized_target.isdigit():
            return normalized_target
        for date_format in ("%Y-%m-%d", "%Y/%m/%d"):
            try:
                return datetime.strptime(normalized_target, date_format).strftime("%Y%m%d")
            except ValueError:
                continue
        return normalized_target

    @classmethod
    def _top_gainers_sqlite_context(
        cls,
        *,
        source: str = "csv",
        market: str,
        top_n: int,
        target_date: str | None,
        min_change_pct: float,
        csv_signature: tuple[int, int] | None,
        stocks_signature: tuple[int, int] | None,
    ) -> tuple[str, tuple[int, int]]:
        target_token = cls._normalize_top_gainers_target_token(target_date)
        source_token = str(source or "csv").strip().lower() or "csv"
        market_token = str(market or "").strip().upper() or "ALL"
        min_change_token = f"{float(min_change_pct):.4f}"
        if csv_signature is None:
            csv_sig = (
                cls._stable_token_to_int(f"{source_token}:{market_token}:{int(top_n)}:{target_token}"),
                cls._stable_token_to_int(f"{source_token}:{min_change_token}"),
            )
        else:
            csv_sig = (int(csv_signature[0]), int(csv_signature[1]))
        stocks_sig = stocks_signature or (0, 0)

        signature_seed = (
            f"{source_token}:{market_token}:{int(top_n)}:{target_token}:{min_change_token}:"
            f"{int(csv_sig[0])}:{int(csv_sig[1])}:{int(stocks_sig[0])}:{int(stocks_sig[1])}"
        )
        signature = (
            cls._stable_token_to_int(signature_seed),
            cls._stable_token_to_int(f"top_gainers::{signature_seed[::-1]}"),
        )

        cache_key = os.path.join(
            BASE_DIR,
            "data",
            cls._market_date_sqlite_namespace_dir,
            "top_gainers",
            f"{source_token}__{market_token}__{int(top_n)}__{target_token}__{min_change_token}.snapshot",
        )
        return cache_key, signature

    @classmethod
    def _top_gainers_memory_cache_key(
        cls,
        *,
        source: str = "csv",
        market: str,
        top_n: int,
        target_date: str | None,
        min_change_pct: float,
        csv_signature: tuple[int, int] | None,
        stocks_signature: tuple[int, int] | None,
    ) -> tuple[str, str, int, str, int, int]:
        target_token = cls._normalize_top_gainers_target_token(target_date)
        source_token = str(source or "csv").strip().lower() or "csv"
        market_token = str(market or "").strip().upper() or "ALL"
        _, sqlite_signature = cls._top_gainers_sqlite_context(
            source=source_token,
            market=market_token,
            top_n=top_n,
            target_date=target_token,
            min_change_pct=min_change_pct,
            csv_signature=csv_signature,
            stocks_signature=stocks_signature,
        )
        return (
            source_token,
            market_token,
            int(top_n),
            target_token,
            int(sqlite_signature[0]),
            int(sqlite_signature[1]),
        )

    @classmethod
    def _serialize_top_gainers(cls, results: List[StockData]) -> dict[str, object]:
        rows: list[list[object]] = []
        for item in results:
            rows.append(
                [
                    str(item.code or "").zfill(6),
                    str(item.name or ""),
                    str(item.market or ""),
                    str(item.sector or ""),
                    float(item.close or 0.0),
                    float(item.change_pct or 0.0),
                    float(item.trading_value or 0.0),
                    int(item.volume or 0),
                    int(item.marcap or 0),
                    float(item.high_52w or 0.0),
                    float(item.low_52w or 0.0),
                ]
            )
        return {"rows": rows}

    @classmethod
    def _deserialize_top_gainers(cls, payload: dict[str, object]) -> List[StockData] | None:
        rows_payload = payload.get("rows")
        if not isinstance(rows_payload, list):
            return None

        results: list[StockData] = []
        for row in rows_payload:
            if not isinstance(row, (list, tuple)) or len(row) < 11:
                continue

            code = str(row[0] or "").zfill(6)
            if not code:
                continue

            try:
                item = StockData(
                    code=code,
                    name=str(row[1] or code),
                    market=str(row[2] or ""),
                    sector=str(row[3] or ""),
                    close=float(row[4] or 0.0),
                    change_pct=float(row[5] or 0.0),
                    trading_value=float(row[6] or 0.0),
                    volume=int(float(row[7] or 0)),
                    marcap=int(float(row[8] or 0)),
                    high_52w=float(row[9] or 0.0),
                    low_52w=float(row[10] or 0.0),
                )
            except (TypeError, ValueError):
                continue
            results.append(item)
        return results

    @classmethod
    def _load_cached_top_gainers(
        cls,
        *,
        source: str = "csv",
        market: str,
        top_n: int,
        target_date: str | None,
        min_change_pct: float,
        csv_signature: tuple[int, int] | None,
        stocks_signature: tuple[int, int] | None,
    ) -> List[StockData] | None:
        memory_key = cls._top_gainers_memory_cache_key(
            source=source,
            market=market,
            top_n=top_n,
            target_date=target_date,
            min_change_pct=min_change_pct,
            csv_signature=csv_signature,
            stocks_signature=stocks_signature,
        )
        with cls._top_gainers_cache_lock:
            memory_payload = cls._top_gainers_cache.get(memory_key)
            if isinstance(memory_payload, dict):
                cls._top_gainers_cache.move_to_end(memory_key)
                cached_results = cls._deserialize_top_gainers(memory_payload)
                if cached_results is not None:
                    return cached_results
                cls._top_gainers_cache.pop(memory_key, None)

        sqlite_key, sqlite_signature = cls._top_gainers_sqlite_context(
            source=source,
            market=market,
            top_n=top_n,
            target_date=target_date,
            min_change_pct=min_change_pct,
            csv_signature=csv_signature,
            stocks_signature=stocks_signature,
        )
        try:
            loaded, sqlite_payload = _load_json_payload_from_sqlite(
                filepath=sqlite_key,
                signature=sqlite_signature,
                logger=logger,
            )
        except Exception as error:
            logger.debug("KRX top gainers SQLite cache load failed: %s", error)
            return None

        if not loaded or not isinstance(sqlite_payload, dict):
            return None
        cached_results = cls._deserialize_top_gainers(sqlite_payload)
        if cached_results is None:
            return None

        with cls._top_gainers_cache_lock:
            cls._top_gainers_cache[memory_key] = sqlite_payload
            cls._top_gainers_cache.move_to_end(memory_key)
            while len(cls._top_gainers_cache) > cls._top_gainers_memory_max_entries:
                cls._top_gainers_cache.popitem(last=False)
        return cached_results

    @classmethod
    def _save_cached_top_gainers(
        cls,
        *,
        source: str = "csv",
        market: str,
        top_n: int,
        target_date: str | None,
        min_change_pct: float,
        csv_signature: tuple[int, int] | None,
        stocks_signature: tuple[int, int] | None,
        results: List[StockData],
    ) -> None:
        memory_key = cls._top_gainers_memory_cache_key(
            source=source,
            market=market,
            top_n=top_n,
            target_date=target_date,
            min_change_pct=min_change_pct,
            csv_signature=csv_signature,
            stocks_signature=stocks_signature,
        )
        payload = cls._serialize_top_gainers(results)
        with cls._top_gainers_cache_lock:
            cls._top_gainers_cache[memory_key] = payload
            cls._top_gainers_cache.move_to_end(memory_key)
            while len(cls._top_gainers_cache) > cls._top_gainers_memory_max_entries:
                cls._top_gainers_cache.popitem(last=False)

        sqlite_key, sqlite_signature = cls._top_gainers_sqlite_context(
            source=source,
            market=market,
            top_n=top_n,
            target_date=target_date,
            min_change_pct=min_change_pct,
            csv_signature=csv_signature,
            stocks_signature=stocks_signature,
        )
        try:
            _save_json_payload_to_sqlite(
                filepath=sqlite_key,
                signature=sqlite_signature,
                payload=payload,
                max_rows=cls._top_gainers_sqlite_max_rows,
                logger=logger,
            )
        except Exception as error:
            logger.debug("KRX top gainers SQLite cache save failed: %s", error)

    @classmethod
    def _pykrx_supply_sqlite_context(
        cls,
        *,
        ticker: str,
        end_date: str,
    ) -> tuple[str, tuple[int, int]]:
        ticker_key = str(ticker).zfill(6)
        date_key = cls._normalize_top_gainers_target_token(end_date)
        cache_key = os.path.join(
            BASE_DIR,
            "data",
            cls._market_date_sqlite_namespace_dir,
            "pykrx_supply_5d",
            f"{ticker_key}__{date_key}.snapshot",
        )
        signature_seed = f"{ticker_key}:{date_key}:pykrx_supply_5d"
        signature = (
            cls._stable_token_to_int(signature_seed),
            cls._stable_token_to_int(f"pykrx_supply::{signature_seed[::-1]}"),
        )
        return cache_key, signature

    @classmethod
    def _deserialize_pykrx_supply_payload(cls, payload: dict[str, object]) -> dict[str, int] | None:
        try:
            foreign = int(float(payload.get("foreign_buy_5d", 0)))
            inst = int(float(payload.get("inst_buy_5d", 0)))
            retail = int(float(payload.get("retail_buy_5d", 0)))
        except (TypeError, ValueError):
            return None
        return {
            "foreign_buy_5d": foreign,
            "inst_buy_5d": inst,
            "retail_buy_5d": retail,
        }

    @classmethod
    def _load_cached_pykrx_supply_summary(
        cls,
        *,
        ticker: str,
        end_date: str,
    ) -> dict[str, int] | None:
        ticker_key = str(ticker).zfill(6)
        date_key = cls._normalize_top_gainers_target_token(end_date)
        memory_key = (ticker_key, date_key)

        with cls._pykrx_supply_cache_lock:
            cached = cls._pykrx_supply_cache.get(memory_key)
            if isinstance(cached, dict):
                cls._pykrx_supply_cache.move_to_end(memory_key)
                return dict(cached)

        sqlite_key, sqlite_signature = cls._pykrx_supply_sqlite_context(
            ticker=ticker_key,
            end_date=date_key,
        )
        try:
            loaded, payload = _load_json_payload_from_sqlite(
                filepath=sqlite_key,
                signature=sqlite_signature,
                logger=logger,
            )
        except Exception as error:
            logger.debug("KRX pykrx supply SQLite cache load failed: %s", error)
            return None

        if not loaded or not isinstance(payload, dict):
            return None
        normalized_payload = cls._deserialize_pykrx_supply_payload(payload)
        if normalized_payload is None:
            return None

        with cls._pykrx_supply_cache_lock:
            cls._pykrx_supply_cache[memory_key] = dict(normalized_payload)
            cls._pykrx_supply_cache.move_to_end(memory_key)
            while len(cls._pykrx_supply_cache) > cls._pykrx_supply_memory_max_entries:
                cls._pykrx_supply_cache.popitem(last=False)
        return dict(normalized_payload)

    @classmethod
    def _save_cached_pykrx_supply_summary(
        cls,
        *,
        ticker: str,
        end_date: str,
        payload: dict[str, int],
    ) -> None:
        normalized_payload = cls._deserialize_pykrx_supply_payload(payload)
        if normalized_payload is None:
            return

        ticker_key = str(ticker).zfill(6)
        date_key = cls._normalize_top_gainers_target_token(end_date)
        memory_key = (ticker_key, date_key)
        with cls._pykrx_supply_cache_lock:
            cls._pykrx_supply_cache[memory_key] = dict(normalized_payload)
            cls._pykrx_supply_cache.move_to_end(memory_key)
            while len(cls._pykrx_supply_cache) > cls._pykrx_supply_memory_max_entries:
                cls._pykrx_supply_cache.popitem(last=False)

        sqlite_key, sqlite_signature = cls._pykrx_supply_sqlite_context(
            ticker=ticker_key,
            end_date=date_key,
        )
        try:
            _save_json_payload_to_sqlite(
                filepath=sqlite_key,
                signature=sqlite_signature,
                payload=normalized_payload,
                max_rows=cls._pykrx_supply_sqlite_max_rows,
                logger=logger,
            )
        except Exception as error:
            logger.debug("KRX pykrx supply SQLite cache save failed: %s", error)

    @classmethod
    def _pykrx_chart_sqlite_context(
        cls,
        *,
        ticker: str,
        end_date: str,
        days: int,
    ) -> tuple[str, tuple[int, int]]:
        ticker_key = str(ticker).zfill(6)
        date_key = cls._normalize_top_gainers_target_token(end_date)
        days_key = max(1, int(days))
        cache_key = os.path.join(
            BASE_DIR,
            "data",
            cls._market_date_sqlite_namespace_dir,
            "pykrx_chart",
            f"{ticker_key}__{date_key}__{days_key}.snapshot",
        )
        signature_seed = f"{ticker_key}:{date_key}:{days_key}:pykrx_chart"
        signature = (
            cls._stable_token_to_int(signature_seed),
            cls._stable_token_to_int(f"pykrx_chart::{signature_seed[::-1]}"),
        )
        return cache_key, signature

    @classmethod
    def _serialize_pykrx_chart_payload(cls, chart_data: ChartData) -> dict[str, object]:
        dates = []
        for value in chart_data.dates:
            if hasattr(value, "isoformat"):
                dates.append(str(value.isoformat()))
            else:
                dates.append(str(value))
        return {
            "dates": dates,
            "opens": [float(item) for item in chart_data.opens],
            "highs": [float(item) for item in chart_data.highs],
            "lows": [float(item) for item in chart_data.lows],
            "closes": [float(item) for item in chart_data.closes],
            "volumes": [float(item) for item in chart_data.volumes],
        }

    @classmethod
    def _deserialize_pykrx_chart_payload(cls, payload: dict[str, object]) -> ChartData | None:
        dates_payload = payload.get("dates")
        opens_payload = payload.get("opens")
        highs_payload = payload.get("highs")
        lows_payload = payload.get("lows")
        closes_payload = payload.get("closes")
        volumes_payload = payload.get("volumes")
        if not all(
            isinstance(item, list)
            for item in (
                dates_payload,
                opens_payload,
                highs_payload,
                lows_payload,
                closes_payload,
                volumes_payload,
            )
        ):
            return None
        series_lengths = (
            len(dates_payload),
            len(opens_payload),
            len(highs_payload),
            len(lows_payload),
            len(closes_payload),
            len(volumes_payload),
        )
        if min(series_lengths, default=0) <= 0 or len(set(series_lengths)) != 1:
            return None

        parsed_dates = []
        for token in dates_payload:
            try:
                parsed_dates.append(datetime.fromisoformat(str(token)).date())
            except Exception:
                try:
                    parsed_dates.append(datetime.strptime(str(token), "%Y-%m-%d").date())
                except Exception:
                    return None
        try:
            return ChartData(
                dates=parsed_dates,
                opens=[float(item) for item in opens_payload],
                highs=[float(item) for item in highs_payload],
                lows=[float(item) for item in lows_payload],
                closes=[float(item) for item in closes_payload],
                volumes=[float(item) for item in volumes_payload],
            )
        except (TypeError, ValueError):
            return None

    @classmethod
    def _load_cached_pykrx_chart_data(
        cls,
        *,
        ticker: str,
        end_date: str,
        days: int,
    ) -> ChartData | None:
        ticker_key = str(ticker).zfill(6)
        date_key = cls._normalize_top_gainers_target_token(end_date)
        days_key = max(1, int(days))
        memory_key = (ticker_key, date_key, days_key)

        with cls._pykrx_chart_cache_lock:
            cached = cls._pykrx_chart_cache.get(memory_key)
            if isinstance(cached, dict):
                cls._pykrx_chart_cache.move_to_end(memory_key)
                resolved = cls._deserialize_pykrx_chart_payload(cached)
                if resolved is not None:
                    return resolved
                cls._pykrx_chart_cache.pop(memory_key, None)

        sqlite_key, sqlite_signature = cls._pykrx_chart_sqlite_context(
            ticker=ticker_key,
            end_date=date_key,
            days=days_key,
        )
        try:
            loaded, payload = _load_json_payload_from_sqlite(
                filepath=sqlite_key,
                signature=sqlite_signature,
                logger=logger,
            )
        except Exception as error:
            logger.debug("KRX pykrx chart SQLite cache load failed: %s", error)
            return None

        if not loaded or not isinstance(payload, dict):
            return None
        chart_data = cls._deserialize_pykrx_chart_payload(payload)
        if chart_data is None:
            return None

        with cls._pykrx_chart_cache_lock:
            cls._pykrx_chart_cache[memory_key] = payload
            cls._pykrx_chart_cache.move_to_end(memory_key)
            while len(cls._pykrx_chart_cache) > cls._pykrx_chart_memory_max_entries:
                cls._pykrx_chart_cache.popitem(last=False)
        return chart_data

    @classmethod
    def _save_cached_pykrx_chart_data(
        cls,
        *,
        ticker: str,
        end_date: str,
        days: int,
        chart_data: ChartData,
    ) -> None:
        ticker_key = str(ticker).zfill(6)
        date_key = cls._normalize_top_gainers_target_token(end_date)
        days_key = max(1, int(days))
        memory_key = (ticker_key, date_key, days_key)
        payload = cls._serialize_pykrx_chart_payload(chart_data)

        with cls._pykrx_chart_cache_lock:
            cls._pykrx_chart_cache[memory_key] = payload
            cls._pykrx_chart_cache.move_to_end(memory_key)
            while len(cls._pykrx_chart_cache) > cls._pykrx_chart_memory_max_entries:
                cls._pykrx_chart_cache.popitem(last=False)

        sqlite_key, sqlite_signature = cls._pykrx_chart_sqlite_context(
            ticker=ticker_key,
            end_date=date_key,
            days=days_key,
        )
        try:
            _save_json_payload_to_sqlite(
                filepath=sqlite_key,
                signature=sqlite_signature,
                payload=payload,
                max_rows=cls._pykrx_chart_sqlite_max_rows,
                logger=logger,
            )
        except Exception as error:
            logger.debug("KRX pykrx chart SQLite cache save failed: %s", error)

    @classmethod
    def _pykrx_fundamental_sqlite_context(
        cls,
        *,
        ticker: str,
        target_date: str,
    ) -> tuple[str, tuple[int, int]]:
        ticker_key = str(ticker).zfill(6)
        date_key = cls._normalize_top_gainers_target_token(target_date)
        cache_key = os.path.join(
            BASE_DIR,
            "data",
            cls._market_date_sqlite_namespace_dir,
            "pykrx_fundamental",
            f"{ticker_key}__{date_key}.snapshot",
        )
        signature_seed = f"{ticker_key}:{date_key}:pykrx_fundamental"
        signature = (
            cls._stable_token_to_int(signature_seed),
            cls._stable_token_to_int(f"pykrx_fundamental::{signature_seed[::-1]}"),
        )
        return cache_key, signature

    @classmethod
    def _deserialize_pykrx_fundamental_payload(cls, payload: dict[str, object]) -> dict[str, float] | None:
        if not isinstance(payload, dict):
            return None

        normalized: dict[str, float] = {}
        for key in ("per", "pbr", "eps", "bps", "dividendYield"):
            raw_value = payload.get(key, 0.0)
            try:
                resolved = float(raw_value)
                if not math.isfinite(resolved):
                    resolved = 0.0
            except (TypeError, ValueError):
                resolved = 0.0
            normalized[key] = resolved
        return normalized

    @classmethod
    def _load_cached_pykrx_fundamental(
        cls,
        *,
        ticker: str,
        target_date: str,
    ) -> dict[str, float] | None:
        ticker_key = str(ticker).zfill(6)
        date_key = cls._normalize_top_gainers_target_token(target_date)
        memory_key = (ticker_key, date_key)

        with cls._pykrx_fundamental_cache_lock:
            cached = cls._pykrx_fundamental_cache.get(memory_key)
            if isinstance(cached, dict):
                cls._pykrx_fundamental_cache.move_to_end(memory_key)
                return dict(cached)

        sqlite_key, sqlite_signature = cls._pykrx_fundamental_sqlite_context(
            ticker=ticker_key,
            target_date=date_key,
        )
        try:
            loaded, payload = _load_json_payload_from_sqlite(
                filepath=sqlite_key,
                signature=sqlite_signature,
                logger=logger,
            )
        except Exception as error:
            logger.debug("KRX pykrx fundamental SQLite cache load failed: %s", error)
            return None

        if not loaded or not isinstance(payload, dict):
            return None

        normalized = cls._deserialize_pykrx_fundamental_payload(payload)
        if normalized is None:
            return None

        with cls._pykrx_fundamental_cache_lock:
            cls._pykrx_fundamental_cache[memory_key] = dict(normalized)
            cls._pykrx_fundamental_cache.move_to_end(memory_key)
            while len(cls._pykrx_fundamental_cache) > cls._pykrx_fundamental_memory_max_entries:
                cls._pykrx_fundamental_cache.popitem(last=False)
        return dict(normalized)

    @classmethod
    def _save_cached_pykrx_fundamental(
        cls,
        *,
        ticker: str,
        target_date: str,
        payload: dict[str, object],
    ) -> None:
        ticker_key = str(ticker).zfill(6)
        date_key = cls._normalize_top_gainers_target_token(target_date)
        normalized = cls._deserialize_pykrx_fundamental_payload(payload)
        if normalized is None:
            return

        memory_key = (ticker_key, date_key)
        with cls._pykrx_fundamental_cache_lock:
            cls._pykrx_fundamental_cache[memory_key] = dict(normalized)
            cls._pykrx_fundamental_cache.move_to_end(memory_key)
            while len(cls._pykrx_fundamental_cache) > cls._pykrx_fundamental_memory_max_entries:
                cls._pykrx_fundamental_cache.popitem(last=False)

        sqlite_key, sqlite_signature = cls._pykrx_fundamental_sqlite_context(
            ticker=ticker_key,
            target_date=date_key,
        )
        try:
            _save_json_payload_to_sqlite(
                filepath=sqlite_key,
                signature=sqlite_signature,
                payload=normalized,
                max_rows=cls._pykrx_fundamental_sqlite_max_rows,
                logger=logger,
            )
        except Exception as error:
            logger.debug("KRX pykrx fundamental SQLite cache save failed: %s", error)

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

    async def get_top_gainers(self, market: str, top_n: int, target_date: str = None) -> List[StockData]:
        """
        상승률 상위 종목 조회 (pykrx 실데이터 + 로컬 CSV Fallback)
        Args:
            market: 'KOSPI' or 'KOSDAQ'
            top_n: 조회할 종목 수
            target_date: (Optional) 특정 날짜 기준 데이터 조회 (YYYYMMDD 형식, 테스트용)
        """
        
        # 1. pykrx 실시간 데이터 시도
        try:
            from pykrx import stock
            import pandas as pd
            min_change_pct = float(getattr(self.config, "min_change_pct", 0.0))
            
            # 테스트 모드: 특정 날짜 지정 시 해당 날짜 사용
            if target_date:
                target_date_str = target_date  # YYYYMMDD 형식
                logger.info(f"[테스트 모드] 지정 날짜 기준 조회: {target_date_str}")
            else:
                # 가장 최근 장 마감 날짜 계산
                target_date_str = self._get_latest_market_date()
                
            logger.info(f"목표 날짜: {target_date_str}")

            cached_pykrx_results = self._load_cached_top_gainers(
                source="pykrx",
                market=market,
                top_n=top_n,
                target_date=target_date_str,
                min_change_pct=min_change_pct,
                csv_signature=None,
                stocks_signature=None,
            )
            if cached_pykrx_results is not None:
                logger.debug(
                    "KRX pykrx top gainers cache hit (market=%s, top_n=%s, target=%s)",
                    market,
                    top_n,
                    target_date_str,
                )
                return cached_pykrx_results
            
            df = None
            
            # 목표 날짜부터 최대 7일 전까지 시도 (공휴일 대응)
            base_date = datetime.strptime(target_date_str, '%Y%m%d')
            for days_ago in range(7):
                try:
                    check_date = (base_date - timedelta(days=days_ago)).strftime('%Y%m%d')
                    df = stock.get_market_ohlcv_by_ticker(check_date, market=market)
                    if not df.empty:
                        logger.info(f"pykrx 데이터 로드 성공: {check_date}")
                        break
                except Exception as e:
                    continue
            
            if df is not None and not df.empty:
                results = self._process_ohlcv_dataframe(df, market, top_n)
                self._save_cached_top_gainers(
                    source="pykrx",
                    market=market,
                    top_n=top_n,
                    target_date=target_date_str,
                    min_change_pct=min_change_pct,
                    csv_signature=None,
                    stocks_signature=None,
                    results=results,
                )
                return results
                
        except Exception as e:
            logger.warning(f"pykrx 실시간 데이터 수집 실패: {e}")
        
        # 2. Fallback: 로컬 daily_prices.csv 사용
        logger.info(f"Fallback: 로컬 daily_prices.csv 사용 ({market}) Target={target_date}")
        return self._load_from_local_csv(market, top_n, target_date)
    
    def _process_ohlcv_dataframe(self, df, market: str, top_n: int) -> List[StockData]:
        """pykrx DataFrame을 StockData 리스트로 변환"""

        # 필터링
        min_change_pct = float(getattr(self.config, "min_change_pct", 0.0))
        mask_price = df['종가'] >= 1000
        mask_vol = df['거래대금'] >= 1_000_000_000
        mask_rise = df['등락률'] >= min_change_pct
        
        filtered_df = df[mask_price & mask_vol & mask_rise].copy()
        filtered_df = filtered_df.sort_values(by='등락률', ascending=False)
        top_df = filtered_df.head(top_n)
        
        results = []
        for code, row in top_df.iterrows():
            try:
                normalized_code = str(code).zfill(6)
                name = self._get_stock_name(normalized_code)
                results.append(StockData(
                    code=normalized_code,
                    name=name,
                    market=market,
                    sector=self._get_sector(normalized_code),
                    close=int(row['종가']),
                    change_pct=float(row['등락률']),
                    trading_value=float(row['거래대금']),
                    volume=int(row['거래량']),
                    marcap=int(row['시가총액']) if '시가총액' in row else 0,
                    high_52w=0,
                    low_52w=0
                ))
            except Exception as e:
                logger.error(f"종목 데이터 변환 실패 ({code}): {e}")
                continue
        return results
    
    def _load_from_local_csv(self, market: str, top_n: int, target_date: str = None) -> List[StockData]:
        """로컬 daily_prices.csv에서 상승률 상위 종목 로드"""
        import pandas as pd
        
        data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
        csv_path = os.path.join(data_dir, 'daily_prices.csv')
        stocks_path = os.path.join(data_dir, 'korean_stocks_list.csv')
        csv_signature = _shared_file_signature(csv_path)

        if csv_signature is None:
            logger.error(f"daily_prices.csv 파일 없음: {csv_path}")
            return []

        stocks_signature = _shared_file_signature(stocks_path)
        min_change_pct = float(getattr(self.config, "min_change_pct", 0.0))
        cached_results = self._load_cached_top_gainers(
            market=market,
            top_n=top_n,
            target_date=target_date,
            min_change_pct=min_change_pct,
            csv_signature=csv_signature,
            stocks_signature=stocks_signature,
        )
        if cached_results is not None:
            logger.debug(
                "KRX local top gainers cache hit (market=%s, top_n=%s, target=%s)",
                market,
                top_n,
                target_date or "latest",
            )
            return cached_results
        
        try:
            daily_usecols = ['ticker', 'date', 'open', 'close', 'volume', 'change_pct', 'trading_value']
            try:
                df = _load_shared_csv_file(
                    data_dir,
                    'daily_prices.csv',
                    deep_copy=False,
                    usecols=daily_usecols,
                    signature=csv_signature,
                )
            except ValueError:
                # 컬럼 스키마가 다를 때는 전체 로드로 fallback
                df = _load_shared_csv_file(
                    data_dir,
                    'daily_prices.csv',
                    deep_copy=False,
                    signature=csv_signature,
                )
                existing_daily_columns = [column for column in daily_usecols if column in df.columns]
                if existing_daily_columns:
                    df = df.loc[:, existing_daily_columns]

            market_map: dict[str, str] = {}
            name_map: dict[str, str] = {}
            stock_lookup_cache_hit = None
            if stocks_signature is not None:
                stock_lookup_cache_hit = self._load_cached_stock_lookup_maps(
                    stocks_path=stocks_path,
                    stocks_signature=stocks_signature,
                )
            if stock_lookup_cache_hit is not None:
                market_map, name_map = stock_lookup_cache_hit
            else:
                stocks_df = pd.DataFrame()
                if stocks_signature is not None:
                    stock_usecols = ['ticker', 'name', 'market']
                    try:
                        stocks_df = _load_shared_csv_file(
                            data_dir,
                            'korean_stocks_list.csv',
                            deep_copy=False,
                            usecols=stock_usecols,
                            signature=stocks_signature,
                        )
                    except ValueError:
                        stocks_df = _load_shared_csv_file(
                            data_dir,
                            'korean_stocks_list.csv',
                            deep_copy=False,
                            signature=stocks_signature,
                        )
                        existing_stock_columns = [column for column in stock_usecols if column in stocks_df.columns]
                        if existing_stock_columns:
                            stocks_df = stocks_df.loc[:, existing_stock_columns]
                if not stocks_df.empty and 'ticker' in stocks_df.columns:
                    tickers = stocks_df['ticker'].astype(str).str.zfill(6)
                    if 'market' in stocks_df.columns:
                        market_map = dict(zip(tickers, stocks_df['market']))
                    if 'name' in stocks_df.columns:
                        name_map = dict(zip(tickers, stocks_df['name']))
                if stocks_signature is not None:
                    self._save_cached_stock_lookup_maps(
                        stocks_path=stocks_path,
                        stocks_signature=stocks_signature,
                        market_map=market_map,
                        name_map=name_map,
                    )
            
            # 날짜 필터링
            df['date'] = pd.to_datetime(df['date'])
            
            if target_date:
                # target_date는 YYYYMMDD 또는 YYYY-MM-DD
                if len(str(target_date)) == 8:
                    dt = datetime.strptime(str(target_date), "%Y%m%d")
                else:
                    dt = pd.to_datetime(target_date)
                
                # 해당 날짜 데이터 검색
                latest_df = df[df['date'].dt.date == dt.date()].copy()
                if latest_df.empty:
                    logger.warning(f"로컬 CSV에 {target_date} 데이터 없음. 최신 날짜로 대체 시도.")
                    latest_date = df['date'].max()
                    latest_df = df[df['date'] == latest_date].copy()
            else:
                latest_date = df['date'].max()
                latest_df = df[df['date'] == latest_date].copy()
            
            logger.info(f"로컬 데이터 날짜: {latest_df['date'].max()}")
            
            # 마켓 필터링
            latest_df['ticker'] = latest_df['ticker'].astype(str).str.zfill(6)
            latest_df['market_actual'] = latest_df['ticker'].map(market_map)
            
            logger.info(f"Market Map Size: {len(market_map)}")
            logger.info(f"Before Market Filter: {len(latest_df)} rows")
            
            latest_df = latest_df[latest_df['market_actual'] == market]
            logger.info(f"After Market Filter ({market}): {len(latest_df)} rows")
            
            # 등락률 계산
            if 'change_pct' not in latest_df.columns:
                if 'open' in latest_df.columns and 'close' in latest_df.columns:
                    latest_df['change_pct'] = ((latest_df['close'] - latest_df['open']) / latest_df['open'] * 100).fillna(0)
                else:
                    latest_df['change_pct'] = 0
            
            # 거래대금 계산 (0인 경우 재계산)
            if 'trading_value' not in latest_df.columns:
                if 'volume' in latest_df.columns and 'close' in latest_df.columns:
                    latest_df['trading_value'] = latest_df['volume'] * latest_df['close']
                else:
                    latest_df['trading_value'] = 0
            else:
                 # 0 또는 NaN인 값 재계산
                 latest_df['trading_value'] = latest_df['trading_value'].fillna(0).astype(float)
                 mask_zero = latest_df['trading_value'] <= 0
                 
                 if mask_zero.any():
                    logger.debug(f"Recalculating 0/NaN trading_value for {mask_zero.sum()} rows")
                    latest_df.loc[mask_zero, 'trading_value'] = latest_df.loc[mask_zero, 'volume'] * latest_df.loc[mask_zero, 'close']
            
            # 필터링
            mask_price = latest_df['close'] >= 1000
            mask_vol = latest_df['trading_value'] >= 1_000_000_000
            mask_rise = latest_df['change_pct'] >= min_change_pct
            
            logger.info(f"TopGainers Filter ({market}): Rise={mask_rise.sum()}, ValidVol={mask_vol.sum()}")
            
            filtered_df = latest_df[mask_price & mask_vol & mask_rise].copy()
            top_df = filtered_df.nlargest(top_n, 'change_pct')
            
            results = []
            for row in top_df.itertuples(index=False):
                ticker = str(getattr(row, 'ticker', '')).zfill(6)
                results.append(StockData(
                    code=ticker,
                    name=name_map.get(ticker, ticker),
                    market=market,
                    sector='',
                    close=int(getattr(row, 'close', 0) or 0),
                    change_pct=float(getattr(row, 'change_pct', 0.0) or 0.0),
                    trading_value=float(getattr(row, 'trading_value', 0.0) or 0.0),
                    volume=int(getattr(row, 'volume', 0) or 0),
                    marcap=0,
                    high_52w=0,
                    low_52w=0
                ))
            
            logger.info(f"로컬 CSV에서 {len(results)}개 종목 로드 완료 ({market})")
            if len(results) == 0:
                logger.warning(f"로컬 CSV 로드 결과가 0개입니다. 파일 내용을 확인하세요. (df shape: {df.shape if 'df' in locals() else 'N/A'})")
            else:
                 # 상위 5개 로그 출력
                for i, s in enumerate(results[:5]):
                    logger.info(f"  [{i+1}] {s.name}: {s.change_pct}%")

            self._save_cached_top_gainers(
                market=market,
                top_n=top_n,
                target_date=target_date,
                min_change_pct=min_change_pct,
                csv_signature=csv_signature,
                stocks_signature=stocks_signature,
                results=results,
            )
            return results
            
        except Exception as e:
            logger.error(f"로컬 CSV 로드 실패: {e}")
            return []

    async def get_stock_detail(self, code: str) -> Optional[Dict]:
        """종목 상세 정보 조회"""
        try:
            return {
                'code': code,
                'name': self._get_stock_name(code),
                'high_52w': 150000,
                'low_52w': 50000
            }
        except Exception as e:
            logger.error(f"종목 상세 조회 실패 ({code}): {e}")
            return None

    async def get_chart_data(self, code: str, days: int) -> Optional[ChartData]:
        """차트 데이터 조회"""
        try:
            # logger.info(f"Chart data generation for {code} (FIX_V2)") # 디버그용 로그
            import random

            # 실제 데이터 조회 (pykrx)
            from pykrx import stock
            normalized_code = str(code).zfill(6)

            # 종료일: 최신 장 마감일
            end_date_str = self._get_latest_market_date()
            cached_chart = self._load_cached_pykrx_chart_data(
                ticker=normalized_code,
                end_date=end_date_str,
                days=days,
            )
            if isinstance(cached_chart, ChartData):
                return cached_chart

            end_date = datetime.strptime(end_date_str, "%Y%m%d")
            
            # 시작일: 휴일 고려하여 넉넉하게 계산 (약 1.6배)
            start_date = end_date - timedelta(days=int(days * 1.6) + 10)
            start_date_str = start_date.strftime("%Y%m%d")
            
            df = stock.get_market_ohlcv_by_date(start_date_str, end_date_str, normalized_code)
            
            if df.empty:
                return None
                
            # 최근 N일 데이터만 사용
            df = df.tail(days)
            
            dates = [d.date() for d in df.index]
            opens = df['시가'].tolist()
            highs = df['고가'].tolist()
            lows = df['저가'].tolist()
            closes = df['종가'].tolist()
            volumes = df['거래량'].tolist()

            resolved_chart = ChartData(
                dates=dates,
                opens=opens,
                highs=highs,
                lows=lows,
                closes=closes,
                volumes=volumes
            )
            self._save_cached_pykrx_chart_data(
                ticker=normalized_code,
                end_date=end_date_str,
                days=days,
                chart_data=resolved_chart,
            )
            return resolved_chart

        except Exception as e:
            logger.error(f"차트 데이터 조회 실패 ({code}): {e}")
            return None

    async def get_supply_data(self, code: str) -> Optional[SupplyData]:
        """수급 데이터 조회 - 단일 5일 합산 서비스(CSV 캐시) 우선."""
        try:
            data_dir = str(getattr(getattr(self, "config", None), "DATA_DIR", "data") or "data")
            if not os.path.isabs(data_dir):
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                data_dir = os.path.join(base_dir, data_dir)

            trend_data = get_investor_trend_5day_for_ticker(
                ticker=str(code).zfill(6),
                data_dir=data_dir,
                verify_with_references=False,
            )
            if isinstance(trend_data, dict) and not self._has_csv_anomaly_flags(trend_data):
                return SupplyData(
                    foreign_buy_5d=int(trend_data.get("foreign", 0)),
                    inst_buy_5d=int(trend_data.get("institution", 0)),
                    retail_buy_5d=0,
                )
            if isinstance(trend_data, dict):
                logger.debug(
                    "통합 5일 수급 이상징후 감지(%s): pykrx fallback 사용",
                    str(code).zfill(6),
                )

            from pykrx import stock

            end_date = self._get_latest_market_date()
            cached_supply = self._load_cached_pykrx_supply_summary(
                ticker=str(code).zfill(6),
                end_date=end_date,
            )
            if isinstance(cached_supply, dict):
                return SupplyData(
                    foreign_buy_5d=int(cached_supply.get("foreign_buy_5d", 0)),
                    inst_buy_5d=int(cached_supply.get("inst_buy_5d", 0)),
                    retail_buy_5d=int(cached_supply.get("retail_buy_5d", 0)),
                )

            end_dt = datetime.strptime(end_date, "%Y%m%d")
            start_date = (end_dt - timedelta(days=10)).strftime("%Y%m%d")

            df = stock.get_market_trading_value_by_date(start_date, end_date, code)
            if df.empty:
                empty_payload = {
                    "foreign_buy_5d": 0,
                    "inst_buy_5d": 0,
                    "retail_buy_5d": 0,
                }
                self._save_cached_pykrx_supply_summary(
                    ticker=str(code).zfill(6),
                    end_date=end_date,
                    payload=empty_payload,
                )
                return SupplyData(**empty_payload)

            df = df.tail(5)
            foreign_col = "외국인합계" if "외국인합계" in df.columns else "외국인"
            inst_col = "기관합계" if "기관합계" in df.columns else "기관"
            retail_col = "개인" if "개인" in df.columns else "개인합계"

            foreign_5d = int(df[foreign_col].sum()) if foreign_col in df.columns else 0
            inst_5d = int(df[inst_col].sum()) if inst_col in df.columns else 0
            retail_5d = int(df[retail_col].sum()) if retail_col in df.columns else 0

            resolved_payload = {
                "foreign_buy_5d": foreign_5d,
                "inst_buy_5d": inst_5d,
                "retail_buy_5d": retail_5d,
            }
            self._save_cached_pykrx_supply_summary(
                ticker=str(code).zfill(6),
                end_date=end_date,
                payload=resolved_payload,
            )
            return SupplyData(**resolved_payload)
        except Exception as e:
            logger.error(f"수급 데이터 조회 실패 ({code}): {e}")
            return None

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

class EnhancedNewsCollector:
    """향상된 뉴스 수집기 - 네이버 금융 크롤링 + 네이버 뉴스 검색"""

    # 주요 언론사 가중치 (PART_07.md 기준)
    MAJOR_SOURCES = {
        "한국경제": 0.9,
        "매일경제": 0.9,
        "머니투데이": 0.85,
        "서울경제": 0.85,
        "이데일리": 0.85,
        "연합뉴스": 0.85,
        "뉴스1": 0.8,
        "파이낸셜뉴스": 0.8,
        "아시아경제": 0.8,
        "헤럴드경제": 0.8,
    }

    def __init__(self, config):
        self.config = config
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Referer': 'https://finance.naver.com/',
        }

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    # 플랫폼별 신뢰도 (AIAnalysis.md 기준)
    PLATFORM_RELIABILITY = {
        "finance": 0.9,  # 네이버 금융 크롤링
        "search_naver": 0.85,  # 네이버 뉴스 검색
        "search_daum": 0.8,   # 다음 뉴스 검색
    }

    def _get_weight(self, source: str, platform: str = 'search_naver') -> float:
        """
        언론사 가중치 + 플랫폼 신뢰도 기반 최종 점수 반환 
        Formula: Publisher Weight * Platform Reliability
        """
        publisher_weight = 0.7 # 기본값
        for major_source, weight in self.MAJOR_SOURCES.items():
            if major_source in source:
                publisher_weight = weight
                break
        
        platform_score = self.PLATFORM_RELIABILITY.get(platform, 0.8)
        
        # 소수점 2자리 반올림
        return round(publisher_weight * platform_score, 2)

    async def get_stock_news(self, code: str, limit: int, name: str = None) -> List[NewsItem]:
        """종목 뉴스 수집 - 다중 소스 통합 (네이버 금융, 네이버 검색, 다음 검색)"""
        try:
            import requests
            from bs4 import BeautifulSoup
            
            stock_name = name or self._get_stock_name(code)
            all_news = []
            seen_titles = set()
            
            # 수집 목록 (각 소스별 최대 수집 개수 - limit보다 넉넉하게)
            SOURCE_LIMIT = limit * 2 
            
            # 1. 네이버 금융 종목 뉴스 페이지 (iframe 내부 URL 사용)
            # /item/news_news.naver는 프레임일 뿐이고, 실제 데이터는 /item/news_news.naver에 있음
            try:
                url = f'https://finance.naver.com/item/news_news.naver?code={code}'
                # 네이버 금융 뉴스 요청 시 Referer를 해당 종목 메인으로 설정
                headers_finance = self.headers.copy()
                headers_finance['Referer'] = f'https://finance.naver.com/item/news.naver?code={code}'
                
                response = requests.get(url, headers=headers_finance, timeout=5)
                
                if response.ok:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # 뉴스 제목 클래스: .tit 또는 .title
                    # 보통 네이버 금융 뉴스 리스트는 div.news_section 또는 table 구조임
                    # /item/news_news.naver 구조: table.type5 사용 (맞음)
                    news_table = soup.select_one('table.type5')
                    
                    if news_table:
                        for row in news_table.select('tr'):
                            # 제목: td.title > a
                            title_el = row.select_one('td.title a')
                            if not title_el: continue
                            
                            title = title_el.text.strip()
                            if not title or title in seen_titles: continue
                            
                            news_url = title_el.get('href', '')
                            if news_url and not news_url.startswith('http'):
                                news_url = f'https://finance.naver.com{news_url}'
                                
                            # 언론사: td.info
                            source_el = row.select_one('td.info')
                            source = source_el.text.strip() if source_el else '네이버금융'
                            
                            seen_titles.add(title)
                            all_news.append(NewsItem(
                                title=title,
                                summary=title,
                                source=source,
                                url=news_url,
                                published_at=datetime.now(),
                                weight=self._get_weight(source)
                            ))
                            if len(all_news) >= SOURCE_LIMIT: break
                            
            except Exception as e:
                logger.debug(f"네이버 금융 뉴스 수집 실패: {e}")

            # 2. 네이버 뉴스 검색 (키워드)
            if stock_name:
                try:
                    search_url = f'https://search.naver.com/search.naver?where=news&query={stock_name}&sort=1'
                    response = requests.get(search_url, headers=self.headers, timeout=5)
                    
                    if response.ok:
                        soup = BeautifulSoup(response.text, 'html.parser')
                        # Selectors often change, try multiple common patterns
                        # div.news_area, div.news_wrap, li.bx, div.news_contents
                        items = soup.select('div.news_wrap') or soup.select('li.bx') or soup.select('div.news_area') or soup.select('div.news_contents')
                        
                        count = 0
                        for item in items:
                            title_el = item.select_one('a.news_tit')
                            if not title_el: continue
                            
                            title = title_el.get('title') or title_el.text.strip()
                            if not title or title in seen_titles: continue
                            
                            # 언론사: a.info.press, span.info.press, div.info_group > a.press
                            source_el = item.select_one('a.info.press') or item.select_one('span.info.press') or item.select_one('a.press')
                            source = source_el.text.strip().replace('언론사 선정', '') if source_el else '네이버검색'
                            
                            seen_titles.add(title)
                            all_news.append(NewsItem(
                                title=title,
                                summary=title, # 요약은 추후 LLM이 처리하거나 본문 수집 시
                                source=source,
                                url=title_el.get('href', ''),
                                published_at=datetime.now(),
                                weight=self._get_weight(source)
                            ))
                            count += 1
                            if count >= SOURCE_LIMIT: break
                            
                except Exception as e:
                    logger.debug(f"네이버 뉴스 검색 실패: {e}")

            # 3. 다음 뉴스 검색
            if stock_name:
                try:
                    daum_url = f'https://search.daum.net/search?w=news&q={stock_name}&sort=recency'
                    response = requests.get(daum_url, headers=self.headers, timeout=5)
                    
                    if response.ok:
                        soup = BeautifulSoup(response.text, 'html.parser')
                        # c-item-content, item-bundle-mid
                        items = soup.select('div.c-item-content') or soup.select('ul.list_news > li') or soup.select('div.item-bundle-mid')
                        
                        count = 0
                        for item in items:
                            link = item.select_one('a.item-title') or item.select_one('a.f_link_b') or item.select_one('a.tit_main')
                            if not link: continue
                            
                            title = link.text.strip()
                            if not title or title in seen_titles: continue
                            
                            source_el = item.select_one('span.txt_info') or item.select_one('a.txt_info') or item.select_one('span.f_nb')
                            source = source_el.text.strip() if source_el else '다음검색'
                            
                            seen_titles.add(title)
                            all_news.append(NewsItem(
                                title=title,
                                summary=title,
                                source=source,
                                url=link.get('href', ''),
                                published_at=datetime.now(),
                                weight=self._get_weight(source)
                            ))
                            count += 1
                            if count >= SOURCE_LIMIT: break
                            
                except Exception as e:
                    logger.debug(f"다음 뉴스 검색 실패: {e}")
            
            if not all_news:
                return []
                
            # 통합 정렬 (1순위: 가중치, 2순위: 원래 순서-최신순)
            # stable sort이므로 weight로만 정렬하면 같은 weight 내에서는 최신순 유지됨 (각 소스가 최신순이라 가정)
            sorted_news = sorted(all_news, key=lambda x: x.weight, reverse=True)
            
            final_news = sorted_news[:limit]
            
                
            # 로그 출력 (디버깅용)
            sources_summary = [f"{n.source}({n.weight})" for n in final_news]
            logger.info(f"뉴스 수집 완료: {stock_name} -> {len(final_news)}개 [{', '.join(sources_summary[:3])}...]")
            
            return final_news
            
        except ImportError as e:
            logger.error(f"requests/BeautifulSoup 미설치: {e}")
            return []
        except Exception as e:
            logger.error(f"뉴스 수집 전체 실패 ({code}): {e}")
            return []
    def _get_stock_name(self, ticker: str) -> str:
        """종목명 조회"""
        names = {
            '005930': '삼성전자', '000270': '기아', '035420': 'NAVER',
            '005380': '현대차', '015760': '한화사이언스',
        }
        return names.get(ticker, '알 수 없는 종목')


class NaverFinanceCollector:
    """네이버 금융 상세 정보 수집기 - 투자지표, 재무정보, 52주 범위 등"""

    def __init__(self, config=None):
        self.config = config
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://finance.naver.com/',
        }

    async def get_stock_detail_info(self, code: str) -> Optional[Dict]:
        """
        네이버 금융에서 종목 상세 정보 수집
        - 시세 정보: 현재가, 전일가, 시가, 고가, 저가
        - 52주 최고/최저가
        - 투자 지표: PER, PBR, ROE 등
        - 시가총액
        """
        try:
            import requests
            from bs4 import BeautifulSoup
            import re

            result = {
                'code': code,
                'market': 'UNKNOWN',
                'name': '',
                'priceInfo': {
                    'current': 0,
                    'prevClose': 0,
                    'open': 0,
                    'high': 0,
                    'low': 0,
                    'change': 0,
                    'change_pct': 0,
                    'volume': 0,
                    'trading_value': 0,
                },
                'yearRange': {
                    'high_52w': 0,
                    'low_52w': 0,
                },
                'indicators': {
                    'marketCap': 0,
                    'per': 0,
                    'pbr': 0,
                    'eps': 0,
                    'bps': 0,
                    'dividendYield': 0,
                },
                'investorTrend': {
                    'foreign': 0,
                    'institution': 0,
                    'individual': 0,
                },
                'safety': {
                    'debtRatio': 0,
                    'currentRatio': 0,
                }
            }

            # 1. 네이버 금융 메인 페이지에서 기본 정보 수집
            url = f'https://finance.naver.com/item/main.naver?code={code}'
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')

            # 종목명 추출
            name_el = soup.select_one('div.wrap_company h2 a')
            if name_el:
                result['name'] = name_el.text.strip()

            # 시장 구분 (KOSPI/KOSDAQ)
            market_img = soup.select_one('img.kospi, img.kosdaq, img[alt*="코스피"], img[alt*="코스닥"]')
            if market_img:
                alt = market_img.get('alt', '').upper()
                if 'KOSDAQ' in alt or '코스닥' in alt:
                    result['market'] = 'KOSDAQ'
                else:
                    result['market'] = 'KOSPI'

            # 현재가
            current_price_el = soup.select_one('p.no_today span.blind')
            if current_price_el:
                try:
                    result['priceInfo']['current'] = int(current_price_el.text.replace(',', ''))
                except:
                    pass

            # 전일가
            prev_close_el = soup.select_one('td.first span.blind')
            if prev_close_el:
                try:
                    result['priceInfo']['prevClose'] = int(prev_close_el.text.replace(',', ''))
                except:
                    pass

            # 시가, 고가, 저가, 거래량 (table.no_info에서)
            no_info_table = soup.select('table.no_info td span.blind')
            if len(no_info_table) >= 4:
                try:
                    result['priceInfo']['high'] = int(no_info_table[1].text.replace(',', '')) if no_info_table[1] else 0
                    result['priceInfo']['low'] = int(no_info_table[3].text.replace(',', '')) if no_info_table[3] else 0
                except:
                    pass

            # 52주 최고/최저가 (우측 박스)
            aside_info = soup.select('table.tab_con1 tr')
            for tr in aside_info:
                th = tr.select_one('th')
                td = tr.select_one('td')
                if th and td:
                    label = th.text.strip()
                    value_el = td.select_one('span.blind')
                    if value_el:
                        try:
                            value = int(value_el.text.replace(',', ''))
                            if '52주' in label and '최고' in label:
                                result['yearRange']['high_52w'] = value
                            elif '52주' in label and '최저' in label:
                                result['yearRange']['low_52w'] = value
                        except:
                            pass

            # 투자 지표 (PER, PBR 등)
            per_el = soup.select_one('#_per')
            pbr_el = soup.select_one('#_pbr')
            
            if per_el:
                try:
                    result['indicators']['per'] = float(per_el.text.replace(',', ''))
                except:
                    pass
            if pbr_el:
                try:
                    result['indicators']['pbr'] = float(pbr_el.text.replace(',', ''))
                except:
                    pass

            # 시가총액
            market_cap_el = soup.select_one('#_market_sum')
            if market_cap_el:
                try:
                    # "2,142,543억원" 형태
                    cap_text = market_cap_el.text.replace(',', '').replace('억원', '').replace('조', '').strip()
                    result['indicators']['marketCap'] = int(float(cap_text) * 100000000)  # 억원 -> 원
                except:
                    pass

            # 2. pykrx에서 투자자 동향 가져오기 (옵션)
            try:
                await self._get_investor_trend(code, result)
            except Exception as e:
                logger.debug(f"투자자 동향 조회 실패 ({code}): {e}")

            # 3. pykrx에서 기본적인 펀더멘탈 데이터 가져오기
            try:
                await self._get_fundamental_data(code, result)
            except Exception as e:
                logger.debug(f"펀더멘탈 데이터 조회 실패 ({code}): {e}")

            logger.info(f"상세 정보 수집 완료: {result['name']} ({code})")
            return result

        except ImportError as e:
            logger.error(f"requests/BeautifulSoup 미설치: {e}")
            return None
        except Exception as e:
            logger.error(f"상세 정보 수집 실패 ({code}): {e}")
            return None

    async def _get_investor_trend(self, code: str, result: Dict) -> None:
        """통합 5일 합산 서비스 우선 + pykrx 요약 캐시 fallback."""
        normalized_code = str(code).zfill(6)
        investor_trend = result.setdefault("investorTrend", {})

        data_dir = str(getattr(getattr(self, "config", None), "DATA_DIR", "data") or "data")
        if not os.path.isabs(data_dir):
            data_dir = os.path.join(BASE_DIR, data_dir)

        try:
            trend_data = get_investor_trend_5day_for_ticker(
                ticker=normalized_code,
                data_dir=data_dir,
                verify_with_references=False,
            )
            if isinstance(trend_data, dict) and not self._has_csv_anomaly_flags(trend_data):
                investor_trend["foreign"] = int(trend_data.get("foreign", 0))
                investor_trend["institution"] = int(trend_data.get("institution", 0))
                return
            if isinstance(trend_data, dict):
                logger.debug(
                    "투자자 동향 통합 서비스 이상징후 감지(%s): pykrx fallback 사용",
                    normalized_code,
                )
        except Exception as error:
            logger.debug("투자자 동향 통합 서비스 조회 실패 (%s): %s", normalized_code, error)

        try:
            from pykrx import stock

            cache_collector = KRXCollector(config=self.config)
            end_date = cache_collector._get_latest_market_date()
            cached_supply = KRXCollector._load_cached_pykrx_supply_summary(
                ticker=normalized_code,
                end_date=end_date,
            )
            if isinstance(cached_supply, dict):
                investor_trend["foreign"] = int(cached_supply.get("foreign_buy_5d", 0))
                investor_trend["institution"] = int(cached_supply.get("inst_buy_5d", 0))
                investor_trend["individual"] = int(cached_supply.get("retail_buy_5d", 0))
                return

            try:
                end_dt = datetime.strptime(end_date, "%Y%m%d")
            except ValueError:
                end_dt = datetime.now()
                end_date = end_dt.strftime("%Y%m%d")
            start_date = (end_dt - timedelta(days=10)).strftime("%Y%m%d")

            df = stock.get_market_trading_value_by_date(start_date, end_date, normalized_code)
            if df.empty:
                empty_payload = {
                    "foreign_buy_5d": 0,
                    "inst_buy_5d": 0,
                    "retail_buy_5d": 0,
                }
                KRXCollector._save_cached_pykrx_supply_summary(
                    ticker=normalized_code,
                    end_date=end_date,
                    payload=empty_payload,
                )
                investor_trend["foreign"] = 0
                investor_trend["institution"] = 0
                investor_trend["individual"] = 0
                return

            df = df.tail(5)
            foreign_col = "외국인합계" if "외국인합계" in df.columns else "외국인"
            inst_col = "기관합계" if "기관합계" in df.columns else "기관"
            if "개인" in df.columns:
                retail_col: str | None = "개인"
            elif "개인합계" in df.columns:
                retail_col = "개인합계"
            else:
                retail_col = None

            resolved_payload = {
                "foreign_buy_5d": int(df[foreign_col].sum()) if foreign_col in df.columns else 0,
                "inst_buy_5d": int(df[inst_col].sum()) if inst_col in df.columns else 0,
                "retail_buy_5d": int(df[retail_col].sum()) if retail_col and retail_col in df.columns else 0,
            }
            KRXCollector._save_cached_pykrx_supply_summary(
                ticker=normalized_code,
                end_date=end_date,
                payload=resolved_payload,
            )
            investor_trend["foreign"] = int(resolved_payload.get("foreign_buy_5d", 0))
            investor_trend["institution"] = int(resolved_payload.get("inst_buy_5d", 0))
            investor_trend["individual"] = int(resolved_payload.get("retail_buy_5d", 0))
        except Exception as error:
            logger.debug("투자자 동향 pykrx 조회 실패 (%s): %s", normalized_code, error)

    async def _get_fundamental_data(self, code: str, result: Dict) -> None:
        """pykrx를 통해 펀더멘탈 데이터 수집"""
        normalized_code = str(code).zfill(6)
        indicators = result.setdefault("indicators", {})

        def _safe_finite_float(value: object) -> float:
            try:
                resolved = float(value)
                return resolved if math.isfinite(resolved) else 0.0
            except (TypeError, ValueError):
                return 0.0

        def _apply_fundamental(payload: dict[str, float]) -> None:
            if indicators.get("per", 0) == 0:
                indicators["per"] = float(payload.get("per", 0.0))
            if indicators.get("pbr", 0) == 0:
                indicators["pbr"] = float(payload.get("pbr", 0.0))
            indicators["eps"] = float(payload.get("eps", 0.0))
            indicators["bps"] = float(payload.get("bps", 0.0))
            indicators["dividendYield"] = float(payload.get("dividendYield", 0.0))

        try:
            from pykrx import stock
            try:
                from engine.collectors.naver_pykrx_mixin import NaverPykrxMixin as _NaverPykrxMixin
            except Exception:
                _NaverPykrxMixin = None

            today = datetime.now().strftime("%Y%m%d")
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")

            for target_date in [today, yesterday]:
                cached_payload = KRXCollector._load_cached_pykrx_fundamental(
                    ticker=normalized_code,
                    target_date=target_date,
                )
                if isinstance(cached_payload, dict):
                    _apply_fundamental(cached_payload)
                    break

                try:
                    resolved_payload = None
                    if _NaverPykrxMixin is not None:
                        resolved_payload = _NaverPykrxMixin._resolve_pykrx_market_fundamental_payload(
                            ticker=normalized_code,
                            target_date=target_date,
                            fetch_market_fundamental_fn=stock.get_market_fundamental_by_ticker,
                        )
                    else:
                        df = stock.get_market_fundamental_by_ticker(target_date)
                        if not df.empty and normalized_code in df.index:
                            row = df.loc[normalized_code]
                            resolved_payload = {
                                "per": _safe_finite_float(row["PER"]) if "PER" in row else 0.0,
                                "pbr": _safe_finite_float(row["PBR"]) if "PBR" in row else 0.0,
                                "eps": _safe_finite_float(row["EPS"]) if "EPS" in row else 0.0,
                                "bps": _safe_finite_float(row["BPS"]) if "BPS" in row else 0.0,
                                "dividendYield": _safe_finite_float(row["DIV"]) if "DIV" in row else 0.0,
                            }

                    if isinstance(resolved_payload, dict):
                        KRXCollector._save_cached_pykrx_fundamental(
                            ticker=normalized_code,
                            target_date=target_date,
                            payload=resolved_payload,
                        )
                        _apply_fundamental(resolved_payload)
                        break
                except Exception as error:
                    logger.debug("펀더멘탈 pykrx 조회 실패 (%s, %s): %s", normalized_code, target_date, error)
                    continue
        except Exception as e:
            logger.debug("펀더멘탈 pykrx 조회 실패 (%s): %s", normalized_code, e)

    async def get_financials(self, code: str) -> Dict:
        """재무 정보 수집 (네이버 금융 기업분석)"""
        try:
            import requests
            from bs4 import BeautifulSoup
            
            result = {
                'revenue': 0,
                'operatingProfit': 0,
                'netIncome': 0,
            }

            # 네이버 기업분석 페이지
            url = f'https://navercomp.wisereport.co.kr/v2/company/c1010001.aspx?cmp_cd={code}'
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.ok:
                soup = BeautifulSoup(response.text, 'html.parser')
                # 재무제표 테이블에서 매출, 영업이익, 순이익 추출
                # (페이지 구조에 따라 셀렉터 조정 필요)
                tables = soup.select('table.gHead01')
                for table in tables:
                    rows = table.select('tr')
                    for row in rows:
                        th = row.select_one('th')
                        tds = row.select('td')
                        if th and tds:
                            label = th.text.strip()
                            if '매출액' in label and tds:
                                try:
                                    result['revenue'] = float(tds[0].text.replace(',', '').strip()) * 100000000
                                except:
                                    pass
                            elif '영업이익' in label and tds:
                                try:
                                    result['operatingProfit'] = float(tds[0].text.replace(',', '').strip()) * 100000000
                                except:
                                    pass
                            elif '순이익' in label or '당기순이익' in label and tds:
                                try:
                                    result['netIncome'] = float(tds[0].text.replace(',', '').strip()) * 100000000
                                except:
                                    pass

            return result
        except Exception as e:
            logger.debug(f"재무정보 수집 실패 ({code}): {e}")
            return {'revenue': 0, 'operatingProfit': 0, 'netIncome': 0}

    async def get_themes(self, code: str) -> List[str]:
        """
        네이버 금융에서 종목 관련 테마 태그 수집
        예: 원전, SMR, 전력인프라, 반도체 등
        """
        try:
            import requests
            from bs4 import BeautifulSoup
            
            themes = []
            
            # 네이버 금융 종목 메인 페이지에서 테마 태그 추출
            url = f'https://finance.naver.com/item/main.naver?code={code}'
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.ok:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 1. 업종/테마 정보 추출 (div.sub_section 내 테마 링크)
                theme_links = soup.select('div.sub_section th em a, div.sub_section td a')
                for link in theme_links:
                    theme_text = link.text.strip()
                    if theme_text and len(theme_text) >= 2 and len(theme_text) <= 20:
                        # 일반적인 메뉴 링크 제외
                        if theme_text not in ['더보기', '차트', '뉴스', '게시판', '종합정보']:
                            themes.append(theme_text)
                
                # 2. 업종 정보 추출
                sector_el = soup.select_one('div.section.trade_compare em a')
                if sector_el:
                    sector = sector_el.text.strip()
                    if sector and sector not in themes:
                        themes.append(sector)
                
                # 3. 분류 정보 (KOSPI/KOSDAQ 제외)
                category_links = soup.select('div.wrap_company a')
                for link in category_links:
                    text = link.text.strip()
                    if text and text not in ['KOSPI', 'KOSDAQ', '', ' '] and len(text) <= 15:
                        if text not in themes:
                            themes.append(text)
            
            # 중복 제거 및 최대 5개로 제한
            unique_themes = list(dict.fromkeys(themes))[:5]
            
            if unique_themes:
                logger.info(f"테마 수집 완료: {code} -> {unique_themes}")
            
            return unique_themes
            
        except Exception as e:
            logger.debug(f"테마 수집 실패 ({code}): {e}")
            return []


try:
    # 모듈형 EnhancedNewsCollector(내장 SQLite 캐시)를 우선 노출한다.
    from engine.collectors.news import EnhancedNewsCollector as _EnhancedNewsCollectorModule

    EnhancedNewsCollector = _EnhancedNewsCollectorModule
except Exception:
    pass

try:
    # 모듈형 NaverFinanceCollector(내장 SQLite 캐시)를 우선 노출한다.
    from engine.collectors.naver import NaverFinanceCollector as _NaverFinanceCollectorModule

    NaverFinanceCollector = _NaverFinanceCollectorModule
except Exception:
    pass
