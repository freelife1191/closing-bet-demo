#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Collectors (데이터 수집기)
"""

from datetime import date, datetime, timedelta
from typing import Dict, List, Optional
import logging
import math
import os

from engine.investor_personal_flow import cached_personal_value, personal_flow_total
from engine.models import StockData, ChartData, SupplyData
from engine.ticker_utils import normalize_ticker
from engine.toss_collector import TossCollector
from services.investor_trend_5day_service import get_investor_trend_5day_for_ticker, has_csv_anomaly_flags
from services.kr_market_data_cache_service import file_signature as _shared_file_signature, load_csv_file as _load_shared_csv_file
from services.kr_market_data_cache_sqlite_payload import load_json_payload_from_sqlite as _load_json_payload_from_sqlite, save_json_payload_to_sqlite as _save_json_payload_to_sqlite

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class KRXCollectorLocalDataMixin:
    def _get_data_dir(self) -> str:
        directory = str(getattr(getattr(self, "config", None), "DATA_DIR", "data") or "data")
        return directory if os.path.isabs(directory) else os.path.join(BASE_DIR, directory)

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
            f"exact-target-v2:{source_token}:{market_token}:{int(top_n)}:{target_token}:{min_change_token}:"
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
                return None

            code = normalize_ticker(row[0])
            if not code:
                return None

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
                return None
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
        except (TypeError, ValueError):
            return None
        retail = cached_personal_value(payload, "retail_buy_5d")
        return {
            "foreign_buy_5d": foreign,
            "inst_buy_5d": inst,
            "retail_buy_5d": retail,
            "individual_schema": 1 if retail is not None else 0,
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

    def _load_from_toss_prices(self, market: str, top_n: int) -> List[StockData]:
        """Toss 현재가 배치 API로 최신 상승률 후보를 생성한다."""
        data_dir = self._get_data_dir()
        stocks_path = os.path.join(data_dir, 'korean_stocks_list.csv')
        stocks_signature = _shared_file_signature(stocks_path)
        if stocks_signature is None:
            logger.warning("Toss fallback skipped: korean_stocks_list.csv 파일 없음")
            return []

        stock_usecols = ['ticker', 'name', 'market', 'sector']
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
            existing_columns = [column for column in stock_usecols if column in stocks_df.columns]
            if existing_columns:
                stocks_df = stocks_df.loc[:, existing_columns]
        except Exception as error:
            logger.warning("Toss fallback stock list load failed: %s", error)
            return []

        if stocks_df.empty or 'ticker' not in stocks_df.columns:
            logger.warning("Toss fallback skipped: 종목 리스트가 비어 있습니다.")
            return []

        normalized_market = str(market or "").strip().upper()
        working = stocks_df.copy()
        working['ticker'] = working['ticker'].astype(str).str.zfill(6)
        if 'market' in working.columns:
            working['market'] = working['market'].astype(str).str.upper()
            working = working[working['market'] == normalized_market]
        if working.empty:
            logger.warning("Toss fallback skipped: %s 종목 리스트가 비어 있습니다.", normalized_market)
            return []

        codes = working['ticker'].dropna().astype(str).str.zfill(6).tolist()
        try:
            prices = TossCollector(self.config).get_prices_batch(codes)
        except Exception as error:
            logger.warning("Toss fallback price fetch failed: %s", error)
            return []

        min_change_pct = float(getattr(self.config, "min_change_pct", 0.0))
        results: list[StockData] = []
        for row in working.itertuples(index=False):
            ticker = str(getattr(row, 'ticker', '')).zfill(6)
            price = prices.get(ticker)
            if not isinstance(price, dict):
                continue

            close = float(price.get('current') or 0)
            change_pct = float(price.get('change_pct') or 0.0)
            trading_value = float(price.get('trading_value') or 0.0)
            if close < 1000 or trading_value < 1_000_000_000 or change_pct < min_change_pct:
                continue

            results.append(StockData(
                code=ticker,
                name=str(getattr(row, 'name', '') or ticker),
                market=normalized_market,
                sector=str(getattr(row, 'sector', '') or ''),
                close=close,
                change_pct=change_pct,
                trading_value=trading_value,
                volume=int(price.get('volume') or 0),
                marcap=int(price.get('market_cap') or 0),
                high_52w=0,
                low_52w=0,
            ))

        results.sort(key=lambda item: item.change_pct, reverse=True)
        logger.info("Toss fallback에서 %s개 종목 로드 완료 (%s)", len(results[:top_n]), normalized_market)
        return results[:top_n]

    def _load_from_local_csv(self, market: str, top_n: int, target_date: str = None) -> List[StockData]:
        """로컬 daily_prices.csv에서 상승률 상위 종목 로드"""
        import pandas as pd

        data_dir = self._get_data_dir()
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
                    logger.warning(f"로컬 CSV에 {target_date} 데이터 없음. 과거 날짜로 대체하지 않습니다.")
                    return []
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

    async def get_chart_data(
        self,
        code: str,
        days: int,
        target_date: str | date | datetime | None = None,
    ) -> Optional[ChartData]:
        """차트 데이터 조회"""
        try:
            # logger.info(f"Chart data generation for {code} (FIX_V2)") # 디버그용 로그
            import random

            # 실제 데이터 조회 (pykrx)
            from pykrx import stock
            normalized_code = str(code).zfill(6)

            # 종료일: explicit target_date가 있으면 해당 날짜를 사용한다.
            end_date_str = self._normalize_top_gainers_target_token(
                str(target_date) if target_date is not None else None
            )
            if end_date_str == "latest":
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

    async def get_supply_data(
        self,
        code: str,
        target_date: str | date | datetime | None = None,
    ) -> Optional[SupplyData]:
        """수급 데이터 조회 - 단일 5일 합산 서비스(CSV 캐시) 우선."""
        try:
            data_dir = str(getattr(getattr(self, "config", None), "DATA_DIR", "data") or "data")
            if not os.path.isabs(data_dir):
                base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                data_dir = os.path.join(base_dir, data_dir)

            normalized_target_date = self._normalize_top_gainers_target_token(
                str(target_date) if target_date is not None else None
            )
            target_datetime = None if normalized_target_date == "latest" else normalized_target_date
            explicit_target_requested = target_datetime is not None
            trend_data = get_investor_trend_5day_for_ticker(
                ticker=str(code).zfill(6),
                data_dir=data_dir,
                target_datetime=target_datetime,
                verify_with_references=False,
            )
            if (
                not explicit_target_requested
                and isinstance(trend_data, dict)
                and not has_csv_anomaly_flags(trend_data)
            ):
                return SupplyData(
                    foreign_buy_5d=int(trend_data.get("foreign", 0)),
                    inst_buy_5d=int(trend_data.get("institution", 0)),
                    retail_buy_5d=trend_data.get("individual") if isinstance(trend_data, dict) else None,
                )
            if not explicit_target_requested and isinstance(trend_data, dict):
                logger.debug(
                    "통합 5일 수급 이상징후 감지(%s): pykrx fallback 사용",
                    str(code).zfill(6),
                )

            from pykrx import stock

            end_date = normalized_target_date
            if end_date == "latest":
                end_date = self._get_latest_market_date()
            cached_supply = self._load_cached_pykrx_supply_summary(
                ticker=str(code).zfill(6),
                end_date=end_date,
            )
            if isinstance(cached_supply, dict):
                return SupplyData(
                    foreign_buy_5d=int(cached_supply.get("foreign_buy_5d", 0)),
                    inst_buy_5d=int(cached_supply.get("inst_buy_5d", 0)),
                    retail_buy_5d=cached_supply.get("retail_buy_5d"),
                )

            end_dt = datetime.strptime(end_date, "%Y%m%d")
            start_date = (end_dt - timedelta(days=10)).strftime("%Y%m%d")

            df = stock.get_market_trading_value_by_date(start_date, end_date, code)
            if df.empty:
                if isinstance(trend_data, dict):
                    return SupplyData(
                        foreign_buy_5d=int(trend_data.get("foreign", 0)),
                        inst_buy_5d=int(trend_data.get("institution", 0)),
                        retail_buy_5d=trend_data.get("individual") if isinstance(trend_data, dict) else None,
                    )
                empty_payload = {
                    "foreign_buy_5d": 0,
                    "inst_buy_5d": 0,
                    "retail_buy_5d": None,
                    "individual_schema": 0,
                }
                self._save_cached_pykrx_supply_summary(
                    ticker=str(code).zfill(6),
                    end_date=end_date,
                    payload=empty_payload,
                )
                return SupplyData(foreign_buy_5d=0, inst_buy_5d=0, retail_buy_5d=None)

            df = df.tail(5)
            foreign_col = "외국인합계" if "외국인합계" in df.columns else "외국인"
            inst_col = "기관합계" if "기관합계" in df.columns else "기관"
            retail_col = "개인" if "개인" in df.columns else "개인합계"

            foreign_5d = int(df[foreign_col].sum()) if foreign_col in df.columns else 0
            inst_5d = int(df[inst_col].sum()) if inst_col in df.columns else 0
            retail_5d = personal_flow_total([{ "date": str(day)[:10], "netIndividualsBuyVolume": row[retail_col]} for day, row in df.iterrows()]) if retail_col in df.columns else None

            resolved_payload = {
                "foreign_buy_5d": foreign_5d,
                "inst_buy_5d": inst_5d,
                "retail_buy_5d": retail_5d,
                "individual_schema": 1 if retail_5d is not None else 0,
            }
            self._save_cached_pykrx_supply_summary(
                ticker=str(code).zfill(6),
                end_date=end_date,
                payload=resolved_payload,
            )
            return SupplyData(foreign_buy_5d=foreign_5d, inst_buy_5d=inst_5d, retail_buy_5d=retail_5d)
        except Exception as e:
            if isinstance(locals().get("trend_data"), dict):
                return SupplyData(
                    foreign_buy_5d=int(trend_data.get("foreign", 0)),
                    inst_buy_5d=int(trend_data.get("institution", 0)),
                    retail_buy_5d=trend_data.get("individual") if isinstance(trend_data, dict) else None,
                )
            logger.error(f"수급 데이터 조회 실패 ({code}): {e}")
            return None
