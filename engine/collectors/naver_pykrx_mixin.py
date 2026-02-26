#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Naver collector pykrx enrichment mixin
"""

import math
import logging
import os
import threading
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Dict

from services.investor_trend_5day_service import get_investor_trend_5day_for_ticker
from services.kr_market_data_cache_sqlite_payload import (
    load_json_payload_from_sqlite as _load_json_payload_from_sqlite,
    save_json_payload_to_sqlite as _save_json_payload_to_sqlite,
)


logger = logging.getLogger(__name__)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class NaverPykrxMixin:
    """pykrx 기반 투자자/펀더멘탈 보강 로직."""

    _pykrx_fundamental_cache_lock = threading.Lock()
    _pykrx_fundamental_cache: OrderedDict[tuple[str, str], dict[str, float]] = OrderedDict()
    _pykrx_fundamental_memory_max_entries = 2_048
    _pykrx_fundamental_sqlite_max_rows = 16_384
    _pykrx_market_fundamental_cache_lock = threading.Lock()
    _pykrx_market_fundamental_cache: OrderedDict[str, dict[str, dict[str, float]]] = OrderedDict()
    _pykrx_market_fundamental_memory_max_entries = 32
    _pykrx_market_fundamental_sqlite_max_rows = 64
    _pykrx_market_fundamental_schema_version = "pykrx_market_fundamental_v1"

    @staticmethod
    def _resolve_data_dir(config: object) -> str:
        data_dir = str(getattr(config, "DATA_DIR", "data") or "data")
        if os.path.isabs(data_dir):
            return data_dir
        return os.path.join(BASE_DIR, data_dir)

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
    def _pykrx_fundamental_sqlite_context(
        cls,
        *,
        ticker: str,
        target_date: str,
    ) -> tuple[str, tuple[int, int]]:
        ticker_key = str(ticker).zfill(6)
        date_key = str(target_date)
        cache_key = os.path.join(
            BASE_DIR,
            "data",
            ".krx_collector_cache",
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
    def _pykrx_market_fundamental_sqlite_context(
        cls,
        *,
        target_date: str,
    ) -> tuple[str, tuple[int, int]]:
        date_key = str(target_date)
        cache_key = os.path.join(
            BASE_DIR,
            "data",
            ".krx_collector_cache",
            "pykrx_market_fundamental",
            f"{date_key}.snapshot",
        )
        signature_seed = f"{date_key}:{cls._pykrx_market_fundamental_schema_version}"
        signature = (
            cls._stable_token_to_int(signature_seed),
            cls._stable_token_to_int(f"pykrx_market_fundamental::{signature_seed[::-1]}"),
        )
        return cache_key, signature

    @classmethod
    def _normalize_pykrx_fundamental_payload(
        cls,
        payload: dict[str, object],
    ) -> dict[str, float] | None:
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
    def _clone_pykrx_market_fundamental_payload(
        cls,
        payload: dict[str, dict[str, float]],
    ) -> dict[str, dict[str, float]]:
        cloned: dict[str, dict[str, float]] = {}
        for ticker, row in payload.items():
            ticker_key = str(ticker).zfill(6)
            if not ticker_key:
                continue
            normalized_row = cls._normalize_pykrx_fundamental_payload(row)
            if normalized_row is None:
                continue
            cloned[ticker_key] = dict(normalized_row)
        return cloned

    @classmethod
    def _serialize_pykrx_market_fundamental_payload(
        cls,
        payload: dict[str, dict[str, float]],
        *,
        assume_normalized: bool = False,
    ) -> dict[str, object]:
        if assume_normalized:
            normalized = payload
        else:
            normalized = cls._clone_pykrx_market_fundamental_payload(payload)
        rows: dict[str, list[float]] = {}
        for ticker, row in normalized.items():
            rows[ticker] = [
                float(row.get("per", 0.0)),
                float(row.get("pbr", 0.0)),
                float(row.get("eps", 0.0)),
                float(row.get("bps", 0.0)),
                float(row.get("dividendYield", 0.0)),
            ]
        return {"rows": rows}

    @classmethod
    def _deserialize_pykrx_market_fundamental_payload(
        cls,
        payload: dict[str, object],
    ) -> dict[str, dict[str, float]] | None:
        if not isinstance(payload, dict):
            return None
        rows = payload.get("rows")
        if not isinstance(rows, dict):
            return None

        resolved: dict[str, dict[str, float]] = {}
        for ticker, row in rows.items():
            ticker_key = str(ticker).zfill(6)
            if not ticker_key:
                continue

            normalized_row: dict[str, float] | None
            if isinstance(row, dict):
                normalized_row = cls._normalize_pykrx_fundamental_payload(row)
            elif isinstance(row, (list, tuple)) and len(row) >= 5:
                normalized_row = cls._normalize_pykrx_fundamental_payload(
                    {
                        "per": row[0],
                        "pbr": row[1],
                        "eps": row[2],
                        "bps": row[3],
                        "dividendYield": row[4],
                    }
                )
            else:
                normalized_row = None

            if normalized_row is None:
                continue
            resolved[ticker_key] = dict(normalized_row)
        return resolved

    @classmethod
    def _load_pykrx_market_fundamental_snapshot(
        cls,
        *,
        target_date: str,
        copy_payload: bool = True,
    ) -> dict[str, dict[str, float]] | None:
        date_key = str(target_date)
        with cls._pykrx_market_fundamental_cache_lock:
            cached = cls._pykrx_market_fundamental_cache.get(date_key)
            if isinstance(cached, dict):
                cls._pykrx_market_fundamental_cache.move_to_end(date_key)
                if copy_payload:
                    return cls._clone_pykrx_market_fundamental_payload(cached)
                return cached

        sqlite_cache_key, sqlite_signature = cls._pykrx_market_fundamental_sqlite_context(
            target_date=date_key,
        )
        try:
            loaded, payload = _load_json_payload_from_sqlite(
                filepath=sqlite_cache_key,
                signature=sqlite_signature,
                logger=logger,
            )
        except Exception as error:
            logger.debug("시장 펀더멘탈 SQLite 캐시 로드 실패 (%s): %s", date_key, error)
            return None

        if not loaded or not isinstance(payload, dict):
            return None

        normalized = cls._deserialize_pykrx_market_fundamental_payload(payload)
        if normalized is None:
            return None

        with cls._pykrx_market_fundamental_cache_lock:
            cls._pykrx_market_fundamental_cache[date_key] = normalized
            cls._pykrx_market_fundamental_cache.move_to_end(date_key)
            while len(cls._pykrx_market_fundamental_cache) > cls._pykrx_market_fundamental_memory_max_entries:
                cls._pykrx_market_fundamental_cache.popitem(last=False)
        if copy_payload:
            return cls._clone_pykrx_market_fundamental_payload(normalized)
        return normalized

    @classmethod
    def _save_pykrx_market_fundamental_snapshot(
        cls,
        *,
        target_date: str,
        payload: dict[str, dict[str, float]],
    ) -> None:
        date_key = str(target_date)
        normalized_payload = cls._clone_pykrx_market_fundamental_payload(payload)

        with cls._pykrx_market_fundamental_cache_lock:
            cls._pykrx_market_fundamental_cache[date_key] = normalized_payload
            cls._pykrx_market_fundamental_cache.move_to_end(date_key)
            while len(cls._pykrx_market_fundamental_cache) > cls._pykrx_market_fundamental_memory_max_entries:
                cls._pykrx_market_fundamental_cache.popitem(last=False)

        sqlite_cache_key, sqlite_signature = cls._pykrx_market_fundamental_sqlite_context(
            target_date=date_key,
        )
        try:
            _save_json_payload_to_sqlite(
                filepath=sqlite_cache_key,
                signature=sqlite_signature,
                payload=cls._serialize_pykrx_market_fundamental_payload(
                    normalized_payload,
                    assume_normalized=True,
                ),
                max_rows=cls._pykrx_market_fundamental_sqlite_max_rows,
                logger=logger,
            )
        except Exception as error:
            logger.debug("시장 펀더멘탈 SQLite 캐시 저장 실패 (%s): %s", date_key, error)

    @classmethod
    def _build_pykrx_market_fundamental_snapshot(
        cls,
        market_df: object,
    ) -> dict[str, dict[str, float]]:
        if market_df is None:
            return {}
        if bool(getattr(market_df, "empty", False)):
            return {}
        if not hasattr(market_df, "iterrows"):
            return {}

        snapshot: dict[str, dict[str, float]] = {}
        for ticker, row in market_df.iterrows():
            ticker_key = str(ticker).zfill(6)
            if not ticker_key:
                continue
            resolved_payload = cls._normalize_pykrx_fundamental_payload(
                {
                    "per": row["PER"] if "PER" in row else 0.0,
                    "pbr": row["PBR"] if "PBR" in row else 0.0,
                    "eps": row["EPS"] if "EPS" in row else 0.0,
                    "bps": row["BPS"] if "BPS" in row else 0.0,
                    "dividendYield": row["DIV"] if "DIV" in row else 0.0,
                }
            )
            if resolved_payload is None:
                continue
            snapshot[ticker_key] = dict(resolved_payload)
        return snapshot

    @classmethod
    def _resolve_pykrx_market_fundamental_payload(
        cls,
        *,
        ticker: str,
        target_date: str,
        fetch_market_fundamental_fn,
    ) -> dict[str, float] | None:
        ticker_key = str(ticker).zfill(6)
        date_key = str(target_date)

        cached_snapshot = cls._load_pykrx_market_fundamental_snapshot(
            target_date=date_key,
            copy_payload=False,
        )
        if cached_snapshot is not None:
            cached_payload = cached_snapshot.get(ticker_key)
            if isinstance(cached_payload, dict):
                return dict(cached_payload)
            return None

        market_df = fetch_market_fundamental_fn(date_key)
        snapshot = cls._build_pykrx_market_fundamental_snapshot(market_df)
        cls._save_pykrx_market_fundamental_snapshot(
            target_date=date_key,
            payload=snapshot,
        )
        resolved_payload = snapshot.get(ticker_key)
        if isinstance(resolved_payload, dict):
            return dict(resolved_payload)
        return None

    @classmethod
    def _load_pykrx_fundamental_snapshot(
        cls,
        *,
        ticker: str,
        target_date: str,
    ) -> dict[str, float] | None:
        memory_key = (str(ticker).zfill(6), str(target_date))
        with cls._pykrx_fundamental_cache_lock:
            cached = cls._pykrx_fundamental_cache.get(memory_key)
            if isinstance(cached, dict):
                cls._pykrx_fundamental_cache.move_to_end(memory_key)
                return dict(cached)

        sqlite_cache_key, sqlite_signature = cls._pykrx_fundamental_sqlite_context(
            ticker=ticker,
            target_date=target_date,
        )
        try:
            loaded, payload = _load_json_payload_from_sqlite(
                filepath=sqlite_cache_key,
                signature=sqlite_signature,
                logger=logger,
            )
        except Exception as error:
            logger.debug("펀더멘탈 SQLite 캐시 로드 실패 (%s, %s): %s", ticker, target_date, error)
            return None

        if not loaded or not isinstance(payload, dict):
            return None

        normalized = cls._normalize_pykrx_fundamental_payload(payload)
        if normalized is None:
            return None

        with cls._pykrx_fundamental_cache_lock:
            cls._pykrx_fundamental_cache[memory_key] = dict(normalized)
            cls._pykrx_fundamental_cache.move_to_end(memory_key)
            while len(cls._pykrx_fundamental_cache) > cls._pykrx_fundamental_memory_max_entries:
                cls._pykrx_fundamental_cache.popitem(last=False)
        return dict(normalized)

    @classmethod
    def _save_pykrx_fundamental_snapshot(
        cls,
        *,
        ticker: str,
        target_date: str,
        payload: dict[str, object],
    ) -> None:
        normalized = cls._normalize_pykrx_fundamental_payload(payload)
        if normalized is None:
            return

        memory_key = (str(ticker).zfill(6), str(target_date))
        with cls._pykrx_fundamental_cache_lock:
            cls._pykrx_fundamental_cache[memory_key] = dict(normalized)
            cls._pykrx_fundamental_cache.move_to_end(memory_key)
            while len(cls._pykrx_fundamental_cache) > cls._pykrx_fundamental_memory_max_entries:
                cls._pykrx_fundamental_cache.popitem(last=False)

        sqlite_cache_key, sqlite_signature = cls._pykrx_fundamental_sqlite_context(
            ticker=ticker,
            target_date=target_date,
        )
        try:
            _save_json_payload_to_sqlite(
                filepath=sqlite_cache_key,
                signature=sqlite_signature,
                payload=normalized,
                max_rows=cls._pykrx_fundamental_sqlite_max_rows,
                logger=logger,
            )
        except Exception as error:
            logger.debug("펀더멘탈 SQLite 캐시 저장 실패 (%s, %s): %s", ticker, target_date, error)

    @staticmethod
    def _apply_fundamental_payload(indicators: dict, payload: dict[str, float]) -> None:
        if indicators.get("per", 0) == 0:
            indicators["per"] = float(payload.get("per", 0.0))
        if indicators.get("pbr", 0) == 0:
            indicators["pbr"] = float(payload.get("pbr", 0.0))
        indicators["eps"] = float(payload.get("eps", 0.0))
        indicators["bps"] = float(payload.get("bps", 0.0))
        indicators["dividendYield"] = float(payload.get("dividendYield", 0.0))

    @staticmethod
    def _to_finite_float(value: object) -> float:
        try:
            resolved = float(value)
            if math.isfinite(resolved):
                return resolved
        except (TypeError, ValueError):
            pass
        return 0.0

    @staticmethod
    def _has_csv_anomaly_flags(trend_data: dict[str, object] | None) -> bool:
        if not isinstance(trend_data, dict):
            return False
        quality = trend_data.get("quality")
        if not isinstance(quality, dict):
            return False
        csv_flags = quality.get("csv_anomaly_flags")
        return isinstance(csv_flags, list) and len(csv_flags) > 0

    async def _get_investor_trend(self, code: str, result: Dict) -> None:
        """통합 5일 합산 서비스 우선 + pykrx 요약 캐시 fallback."""
        normalized_code = str(code).zfill(6)
        investor_trend = result.setdefault("investorTrend", {})

        try:
            trend_data = get_investor_trend_5day_for_ticker(
                ticker=normalized_code,
                data_dir=self._resolve_data_dir(getattr(self, "config", None)),
                verify_with_references=False,
            )
            if isinstance(trend_data, dict) and not self._has_csv_anomaly_flags(trend_data):
                investor_trend["foreign"] = int(trend_data.get("foreign", 0))
                investor_trend["institution"] = int(trend_data.get("institution", 0))
                investor_trend.setdefault("individual", 0)
                return
            if isinstance(trend_data, dict):
                logger.debug("투자자 동향 통합 서비스 이상징후 감지 (%s): pykrx fallback 사용", normalized_code)
        except Exception as error:
            logger.debug("투자자 동향 통합 서비스 조회 실패 (%s): %s", normalized_code, error)

        try:
            from engine.collectors.krx import KRXCollector
            from pykrx import stock

            cache_collector = KRXCollector(config=getattr(self, "config", None))
            latest_market_date_resolver = getattr(cache_collector, "_get_latest_market_date", None)
            if callable(latest_market_date_resolver):
                end_date = str(latest_market_date_resolver())
            else:
                end_date = datetime.now().strftime("%Y%m%d")
            cached_supply = cache_collector._load_pykrx_supply_summary_snapshot(
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
                cache_collector._save_pykrx_supply_summary_snapshot(
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
                retail_col = "개인"
            elif "개인합계" in df.columns:
                retail_col = "개인합계"
            else:
                retail_col = None

            resolved_payload = {
                "foreign_buy_5d": int(df[foreign_col].sum()) if foreign_col in df.columns else 0,
                "inst_buy_5d": int(df[inst_col].sum()) if inst_col in df.columns else 0,
                "retail_buy_5d": int(df[retail_col].sum()) if retail_col and retail_col in df.columns else 0,
            }
            cache_collector._save_pykrx_supply_summary_snapshot(
                ticker=normalized_code,
                end_date=end_date,
                payload=resolved_payload,
            )
            investor_trend["foreign"] = int(resolved_payload.get("foreign_buy_5d", 0))
            investor_trend["institution"] = int(resolved_payload.get("inst_buy_5d", 0))
            investor_trend["individual"] = int(resolved_payload.get("retail_buy_5d", 0))

        except Exception as e:
            logger.debug("투자자 동향 pykrx 조회 실패 (%s): %s", normalized_code, e)

    async def _get_fundamental_data(self, code: str, result: Dict) -> None:
        """pykrx를 통해 펀더멘탈 데이터 수집"""
        normalized_code = str(code).zfill(6)
        indicators = result.setdefault("indicators", {})
        try:
            from pykrx import stock

            today = datetime.now().strftime("%Y%m%d")
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")

            for target_date in [today, yesterday]:
                cached_fundamental = self._load_pykrx_fundamental_snapshot(
                    ticker=normalized_code,
                    target_date=target_date,
                )
                if isinstance(cached_fundamental, dict):
                    self._apply_fundamental_payload(indicators, cached_fundamental)
                    break
                try:
                    resolved_payload = self._resolve_pykrx_market_fundamental_payload(
                        ticker=normalized_code,
                        target_date=target_date,
                        fetch_market_fundamental_fn=stock.get_market_fundamental_by_ticker,
                    )
                    if isinstance(resolved_payload, dict):
                        self._save_pykrx_fundamental_snapshot(
                            ticker=normalized_code,
                            target_date=target_date,
                            payload=resolved_payload,
                        )
                        self._apply_fundamental_payload(indicators, resolved_payload)
                        break
                except Exception as inner_error:
                    logger.debug(
                        "펀더멘탈 pykrx 조회 실패 (%s, %s): %s",
                        normalized_code,
                        target_date,
                        inner_error,
                    )
                    continue
        except Exception as e:
            logger.debug(f"펀더멘탈 pykrx 조회 실패 ({normalized_code}): {e}")


__all__ = ["NaverPykrxMixin"]
