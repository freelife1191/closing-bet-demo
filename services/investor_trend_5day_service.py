#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Investor Trend 5-Day Service

외국인/기관 5거래일 합산 데이터를 단일 경로로 제공한다.
"""

from __future__ import annotations

import logging
import os
import threading
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
from pandas.api.types import is_datetime64_any_dtype

from services.kr_market_data_cache_service import load_csv_file
from services.kr_market_data_cache_sqlite_payload import (
    load_json_payload_from_sqlite,
    save_json_payload_to_sqlite,
)
from services.kr_market_csv_utils import get_ticker_padded_series


logger = logging.getLogger(__name__)

_TREND_FILENAME = "all_institutional_trend_data.csv"
_SQLITE_KEY_SUFFIX = "::investor_trend_5day_unified"
_SQLITE_MAX_ROWS = 256
_REFERENCE_SQLITE_MAX_ROWS = 20_000
_REFERENCE_SQLITE_NAMESPACE_DIR = ".investor_trend_reference_cache"
_PYKRX_MARKET_DATE_SQLITE_MAX_ROWS = 256
_MEMORY_CACHE_MAX_ENTRIES = 32
_REFERENCE_CACHE_MAX_ENTRIES = 4_096
_CSV_EXTREME_ABS_TOTAL = 20_000_000_000_000
_CSV_STALE_DAYS = 4
_DISAGREE_RATIO_THRESHOLD = 2.5
_DISAGREE_SIGNIFICANT_TOTAL = 10_000_000_000
_DISAGREE_SIGNIFICANT_SIDE = 3_000_000_000
_TREND_CACHE_LOCK = threading.Lock()
_TREND_CACHE: OrderedDict[
    tuple[str, int, int, str],
    dict[str, dict[str, Any]],
] = OrderedDict()
_REFERENCE_CACHE_LOCK = threading.Lock()
_REFERENCE_CACHE: OrderedDict[
    tuple[str, str, str],
    dict[str, Any] | None,
] = OrderedDict()
_TOSS_COLLECTOR_LOCK = threading.Lock()
_TOSS_COLLECTOR: Any | None = None
_PYKRX_MARKET_DATE_LOCK = threading.Lock()
_PYKRX_MARKET_DATE_CACHE: dict[str, datetime] = {}


def _normalize_data_dir(data_dir: str) -> str:
    normalized = (data_dir or "").strip()
    if not normalized:
        normalized = "data"
    return os.path.abspath(normalized)


def _normalize_target_datetime(target_datetime: datetime | pd.Timestamp | str | None) -> datetime | None:
    if target_datetime is None:
        return None
    try:
        parsed = pd.to_datetime(target_datetime, errors="coerce")
    except Exception:
        return None
    if parsed is None or pd.isna(parsed):
        return None
    return parsed.to_pydatetime()


def _target_token(target_datetime: datetime | pd.Timestamp | str | None) -> str:
    normalized = _normalize_target_datetime(target_datetime)
    if normalized is None:
        return "latest"
    return normalized.strftime("%Y%m%d")


def _safe_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _safe_sign(value: int) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _extract_abs_total(payload: dict[str, Any] | None) -> int:
    if not isinstance(payload, dict):
        return 0
    foreign_value = _safe_int(payload.get("foreign", 0))
    inst_value = _safe_int(payload.get("institution", 0))
    return abs(foreign_value) + abs(inst_value)


def _parse_date_string(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = pd.to_datetime(value, errors="coerce")
    except Exception:
        return None
    if parsed is None or pd.isna(parsed):
        return None
    return parsed.to_pydatetime()


def _normalize_latest_date_from_details(details: list[dict[str, Any]]) -> str | None:
    if not details:
        return None
    first = details[0]
    if not isinstance(first, dict):
        return None
    for key in ("date", "localDate", "baseDate"):
        parsed = _parse_date_string(first.get(key))
        if parsed is not None:
            return parsed.strftime("%Y-%m-%d")
    return None


def _stable_token_to_int(token: str) -> int:
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


def _reference_time_token(target_datetime: datetime | pd.Timestamp | str | None) -> str:
    normalized_target = _normalize_target_datetime(target_datetime)
    if normalized_target is not None:
        return normalized_target.strftime("%Y%m%d")
    return datetime.now().strftime("%Y%m%d")


def _reference_cache_token(
    *,
    source: str,
    target_datetime: datetime | pd.Timestamp | str | None,
    data_dir: str | None = None,
) -> str:
    normalized_target = _normalize_target_datetime(target_datetime)
    if normalized_target is not None:
        return normalized_target.strftime("%Y%m%d")

    normalized_source = str(source or "").lower().strip()
    if normalized_source == "pykrx":
        try:
            latest_market_dt = _resolve_pykrx_latest_market_date(data_dir=data_dir)
            return latest_market_dt.strftime("%Y%m%d")
        except Exception:
            pass
    return _reference_time_token(target_datetime)


def _pykrx_market_date_sqlite_context(
    *,
    data_dir: str,
    cache_token: str,
) -> tuple[str, tuple[int, int]]:
    normalized_dir = _normalize_data_dir(data_dir)
    namespace_dir = os.path.join(normalized_dir, _REFERENCE_SQLITE_NAMESPACE_DIR, "pykrx")
    cache_key = os.path.join(namespace_dir, f"latest_market_date__{cache_token}.snapshot")
    signature = (_stable_token_to_int(cache_token), _stable_token_to_int("pykrx_market_date"))
    return cache_key, signature


def _reference_sqlite_context(
    *,
    data_dir: str,
    source: str,
    ticker: str,
    target_datetime: datetime | pd.Timestamp | str | None,
) -> tuple[str, tuple[int, int]]:
    normalized_dir = _normalize_data_dir(data_dir)
    token = _reference_cache_token(
        source=source,
        target_datetime=target_datetime,
        data_dir=normalized_dir,
    )
    namespace_dir = os.path.join(
        normalized_dir,
        _REFERENCE_SQLITE_NAMESPACE_DIR,
        str(source or "unknown").strip().lower(),
    )
    cache_key = os.path.join(
        namespace_dir,
        f"{str(ticker).zfill(6)}__{token}.snapshot",
    )
    signature = (_stable_token_to_int(token), _stable_token_to_int(source))
    return cache_key, signature


def _resolve_trend_file_context(
    *,
    data_dir: str,
    filename: str,
) -> tuple[str, tuple[int, int]] | None:
    filepath = os.path.abspath(os.path.join(data_dir, filename))
    try:
        stat = os.stat(filepath)
    except OSError:
        return None
    return filepath, (int(stat.st_mtime_ns), int(stat.st_size))


def _sqlite_cache_key(filepath: str, target_token: str) -> str:
    return f"{filepath}{_SQLITE_KEY_SUFFIX}::{target_token}"


def _serialize_trend_map(trend_map: dict[str, dict[str, Any]]) -> dict[str, object]:
    rows: dict[str, object] = {}
    for ticker, payload in trend_map.items():
        if not isinstance(payload, dict):
            continue
        details = payload.get("details")
        serialized_details: list[list[int]] = []
        if isinstance(details, list):
            for detail in details:
                if not isinstance(detail, dict):
                    continue
                try:
                    foreign_value = int(float(detail.get("netForeignerBuyVolume", 0)))
                    inst_value = int(float(detail.get("netInstitutionBuyVolume", 0)))
                except (TypeError, ValueError):
                    continue
                serialized_details.append([foreign_value, inst_value])

        try:
            foreign_5d = int(float(payload.get("foreign", 0)))
            inst_5d = int(float(payload.get("institution", 0)))
        except (TypeError, ValueError):
            continue

        latest_date = payload.get("latest_date")
        latest_date_value = str(latest_date) if latest_date else ""
        rows[str(ticker).zfill(6)] = [foreign_5d, inst_5d, serialized_details, latest_date_value]
    return {"rows": rows}


def _deserialize_trend_map(payload: dict[str, object]) -> dict[str, dict[str, Any]] | None:
    rows_payload = payload.get("rows")
    if not isinstance(rows_payload, dict):
        return None

    trend_map: dict[str, dict[str, Any]] = {}
    for ticker, row_payload in rows_payload.items():
        if not isinstance(row_payload, (list, tuple)) or len(row_payload) < 2:
            continue

        try:
            foreign_5d = int(float(row_payload[0]))
            inst_5d = int(float(row_payload[1]))
        except (TypeError, ValueError):
            continue

        details_payload = row_payload[2] if len(row_payload) >= 3 else []
        details: list[dict[str, int]] = []
        if isinstance(details_payload, list):
            for item in details_payload:
                if not isinstance(item, (list, tuple)) or len(item) != 2:
                    continue
                try:
                    foreign_value = int(float(item[0]))
                    inst_value = int(float(item[1]))
                except (TypeError, ValueError):
                    continue
                details.append(
                    {
                        "netForeignerBuyVolume": foreign_value,
                        "netInstitutionBuyVolume": inst_value,
                    }
                )
        latest_date_value = ""
        if len(row_payload) >= 4 and isinstance(row_payload[3], str):
            latest_date_value = row_payload[3]

        ticker_key = str(ticker).zfill(6)
        trend_map[ticker_key] = {
            "foreign": foreign_5d,
            "institution": inst_5d,
            "details": details,
            "days": 5,
            "latest_date": latest_date_value,
        }
    return trend_map


def _load_trend_df(
    *,
    data_dir: str,
    filename: str,
    signature: tuple[int, int],
) -> pd.DataFrame:
    usecols = ["ticker", "date", "foreign_buy", "inst_buy"]
    try:
        return load_csv_file(
            data_dir,
            filename,
            deep_copy=False,
            usecols=usecols,
            signature=signature,
        )
    except ValueError:
        loaded = load_csv_file(
            data_dir,
            filename,
            deep_copy=False,
            usecols=None,
            signature=signature,
        )
        existing_columns = [column for column in usecols if column in loaded.columns]
        if existing_columns:
            return loaded.loc[:, existing_columns]
        return loaded


def _build_trend_map(
    trend_df: pd.DataFrame,
    *,
    target_datetime: datetime | pd.Timestamp | str | None = None,
) -> dict[str, dict[str, Any]]:
    if trend_df.empty:
        return {}
    required_columns = {"ticker", "foreign_buy", "inst_buy"}
    if not required_columns.issubset(set(trend_df.columns)):
        return {}

    working = trend_df
    ticker_series = get_ticker_padded_series(working)
    try:
        working["ticker"] = ticker_series
    except Exception:
        working = working.copy()
        working["ticker"] = ticker_series

    working["foreign_buy"] = pd.to_numeric(working["foreign_buy"], errors="coerce").fillna(0)
    working["inst_buy"] = pd.to_numeric(working["inst_buy"], errors="coerce").fillna(0)

    normalized_target_datetime = _normalize_target_datetime(target_datetime)
    has_date = "date" in working.columns
    if has_date:
        if not is_datetime64_any_dtype(working["date"]):
            working["date"] = pd.to_datetime(working["date"], errors="coerce")
        working = working[working["date"].notna()]
        if normalized_target_datetime is not None:
            working = working[working["date"] <= normalized_target_datetime]
        if working.empty:
            return {}
        working = working.sort_values(["ticker", "date"])
    elif normalized_target_datetime is not None:
        return {}
    else:
        working = working.sort_values(["ticker"])

    trend_map: dict[str, dict[str, Any]] = {}
    grouped = working.groupby("ticker", sort=False)
    for ticker, group in grouped:
        recent = group.tail(5)
        if len(recent) < 5:
            continue

        ordered = recent.sort_values("date", ascending=False) if has_date else recent.iloc[::-1]
        details: list[dict[str, int]] = []
        foreign_5d = 0
        inst_5d = 0
        for foreign_value, inst_value in ordered[["foreign_buy", "inst_buy"]].itertuples(index=False, name=None):
            try:
                foreign_int = int(float(foreign_value))
                inst_int = int(float(inst_value))
            except (TypeError, ValueError):
                continue

            foreign_5d += foreign_int
            inst_5d += inst_int
            details.append(
                {
                    "netForeignerBuyVolume": foreign_int,
                    "netInstitutionBuyVolume": inst_int,
                }
            )

        if len(details) < 5:
            continue

        latest_date_value = ""
        if has_date:
            try:
                latest_date_value = ordered["date"].iloc[0].strftime("%Y-%m-%d")
            except Exception:
                latest_date_value = ""

        ticker_key = str(ticker).zfill(6)
        trend_map[ticker_key] = {
            "foreign": int(foreign_5d),
            "institution": int(inst_5d),
            "details": details,
            "days": 5,
            "latest_date": latest_date_value,
        }

    return trend_map


def _normalize_external_trend_payload(
    payload: dict[str, Any] | None,
    *,
    source: str,
) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None

    foreign_value = _safe_int(payload.get("foreign", 0))
    inst_value = _safe_int(payload.get("institution", 0))

    details_payload = payload.get("details")
    details: list[dict[str, int]] = []
    if isinstance(details_payload, list):
        for item in details_payload[:5]:
            if not isinstance(item, dict):
                continue
            foreign_1d = _safe_int(item.get("netForeignerBuyVolume", 0))
            inst_1d = _safe_int(item.get("netInstitutionBuyVolume", 0))
            details.append(
                {
                    "netForeignerBuyVolume": foreign_1d,
                    "netInstitutionBuyVolume": inst_1d,
                }
            )

    if not details and (foreign_value != 0 or inst_value != 0):
        # details가 없더라도 5일합 자체는 유지한다.
        details = []

    latest_date = payload.get("latest_date")
    if not latest_date:
        latest_date = _normalize_latest_date_from_details(payload.get("details", []))

    return {
        "foreign": foreign_value,
        "institution": inst_value,
        "details": details,
        "days": 5,
        "latest_date": str(latest_date) if latest_date else "",
        "source": source,
    }


def _is_large_disagreement(
    base_payload: dict[str, Any],
    reference_payload: dict[str, Any],
) -> bool:
    base_foreign = _safe_int(base_payload.get("foreign", 0))
    base_inst = _safe_int(base_payload.get("institution", 0))
    ref_foreign = _safe_int(reference_payload.get("foreign", 0))
    ref_inst = _safe_int(reference_payload.get("institution", 0))

    base_total = abs(base_foreign) + abs(base_inst)
    ref_total = abs(ref_foreign) + abs(ref_inst)
    high_total = max(base_total, ref_total)
    low_total = max(1, min(base_total, ref_total))

    if high_total < _DISAGREE_SIGNIFICANT_TOTAL:
        return False

    ratio = float(high_total) / float(low_total)
    if ratio >= _DISAGREE_RATIO_THRESHOLD:
        return True

    foreign_sign_mismatch = (
        _safe_sign(base_foreign) != _safe_sign(ref_foreign)
        and abs(base_foreign) >= _DISAGREE_SIGNIFICANT_SIDE
        and abs(ref_foreign) >= _DISAGREE_SIGNIFICANT_SIDE
    )
    inst_sign_mismatch = (
        _safe_sign(base_inst) != _safe_sign(ref_inst)
        and abs(base_inst) >= _DISAGREE_SIGNIFICANT_SIDE
        and abs(ref_inst) >= _DISAGREE_SIGNIFICANT_SIDE
    )
    return foreign_sign_mismatch or inst_sign_mismatch


def _detect_csv_anomaly_flags(
    csv_payload: dict[str, Any] | None,
    *,
    target_datetime: datetime | pd.Timestamp | str | None,
) -> list[str]:
    if not isinstance(csv_payload, dict):
        return ["missing_csv"]

    flags: list[str] = []
    details = csv_payload.get("details")
    if not isinstance(details, list) or len(details) < 5:
        flags.append("insufficient_days")
    else:
        day_abs_totals: list[int] = []
        for detail in details[:5]:
            if not isinstance(detail, dict):
                continue
            day_abs_totals.append(
                abs(_safe_int(detail.get("netForeignerBuyVolume", 0)))
                + abs(_safe_int(detail.get("netInstitutionBuyVolume", 0)))
            )
        if len(day_abs_totals) >= 5:
            peak = max(day_abs_totals)
            baseline_values = sorted(day_abs_totals)[:-1]
            baseline = int(sum(baseline_values) / max(1, len(baseline_values)))
            if peak >= _DISAGREE_SIGNIFICANT_TOTAL and peak >= max(1, baseline) * 10:
                flags.append("single_day_spike")

    abs_total = _extract_abs_total(csv_payload)
    if abs_total >= _CSV_EXTREME_ABS_TOTAL:
        flags.append("extreme_abs_total")

    if target_datetime is None:
        latest_date = _parse_date_string(csv_payload.get("latest_date"))
        if latest_date is not None:
            day_gap = (datetime.now().date() - latest_date.date()).days
            if day_gap > _CSV_STALE_DAYS:
                flags.append("stale_csv")

    return flags


def _resolve_pykrx_latest_market_date(
    *,
    data_dir: str | None = None,
) -> datetime:
    normalized_data_dir = _normalize_data_dir(data_dir or "data")
    cache_token = datetime.now().strftime("%Y%m%d")
    with _PYKRX_MARKET_DATE_LOCK:
        cached_token = _PYKRX_MARKET_DATE_CACHE.get("token")
        cached_value = _PYKRX_MARKET_DATE_CACHE.get("value")
        if cached_token == cache_token and isinstance(cached_value, datetime):
            return cached_value

    sqlite_key, sqlite_signature = _pykrx_market_date_sqlite_context(
        data_dir=normalized_data_dir,
        cache_token=cache_token,
    )
    try:
        loaded, payload = load_json_payload_from_sqlite(
            filepath=sqlite_key,
            signature=sqlite_signature,
            logger=logger,
        )
    except Exception as error:
        logger.debug("Failed to load pykrx latest market date sqlite cache: %s", error)
    else:
        if loaded and isinstance(payload, dict):
            parsed_latest = _parse_date_string(payload.get("latest_market_date"))
            if parsed_latest is not None:
                with _PYKRX_MARKET_DATE_LOCK:
                    _PYKRX_MARKET_DATE_CACHE["token"] = cache_token
                    _PYKRX_MARKET_DATE_CACHE["value"] = parsed_latest
                return parsed_latest

    now = datetime.now()
    fallback = now
    if now.weekday() == 5:
        fallback = now - timedelta(days=1)
    elif now.weekday() == 6:
        fallback = now - timedelta(days=2)

    latest_market_dt = fallback
    try:
        from pykrx import stock

        start_date = (now - timedelta(days=14)).strftime("%Y%m%d")
        end_date = now.strftime("%Y%m%d")
        market_df = stock.get_index_ohlcv_by_date(start_date, end_date, "1001")
        if isinstance(market_df, pd.DataFrame) and not market_df.empty:
            latest_market_dt = market_df.index[-1].to_pydatetime()
    except Exception as error:
        logger.debug("Failed to resolve pykrx latest market date: %s", error)

    with _PYKRX_MARKET_DATE_LOCK:
        _PYKRX_MARKET_DATE_CACHE["token"] = cache_token
        _PYKRX_MARKET_DATE_CACHE["value"] = latest_market_dt

    try:
        save_json_payload_to_sqlite(
            filepath=sqlite_key,
            signature=sqlite_signature,
            payload={"latest_market_date": latest_market_dt.strftime("%Y-%m-%d")},
            max_rows=_PYKRX_MARKET_DATE_SQLITE_MAX_ROWS,
            logger=logger,
        )
    except Exception as error:
        logger.debug("Failed to save pykrx latest market date sqlite cache: %s", error)
    return latest_market_dt


def _fetch_pykrx_reference_trend(
    *,
    ticker: str,
    target_datetime: datetime | pd.Timestamp | str | None,
    data_dir: str | None = None,
) -> dict[str, Any] | None:
    try:
        from pykrx import stock
    except Exception:
        return None

    normalized_target = _normalize_target_datetime(target_datetime)
    end_dt = normalized_target or _resolve_pykrx_latest_market_date(data_dir=data_dir)
    start_dt = end_dt - timedelta(days=14)

    try:
        trend_df = stock.get_market_trading_value_by_date(
            start_dt.strftime("%Y%m%d"),
            end_dt.strftime("%Y%m%d"),
            str(ticker).zfill(6),
        )
    except Exception as error:
        logger.debug("pykrx reference trend fetch failed (%s): %s", ticker, error)
        return None

    if not isinstance(trend_df, pd.DataFrame) or trend_df.empty:
        return None

    trend_df = trend_df.tail(5)
    if len(trend_df) < 5:
        return None

    foreign_col = next((col for col in trend_df.columns if "외국인" in col), None)
    inst_col = next((col for col in trend_df.columns if "기관" in col), None)
    if not foreign_col or not inst_col:
        return None

    ordered = trend_df.iloc[::-1]
    details: list[dict[str, int]] = []
    foreign_sum = 0
    inst_sum = 0
    for foreign_value, inst_value in ordered[[foreign_col, inst_col]].itertuples(index=False, name=None):
        foreign_int = _safe_int(foreign_value)
        inst_int = _safe_int(inst_value)
        foreign_sum += foreign_int
        inst_sum += inst_int
        details.append(
            {
                "netForeignerBuyVolume": foreign_int,
                "netInstitutionBuyVolume": inst_int,
            }
        )

    latest_date = ""
    try:
        latest_date = ordered.index[0].strftime("%Y-%m-%d")
    except Exception:
        latest_date = ""

    return {
        "foreign": int(foreign_sum),
        "institution": int(inst_sum),
        "details": details,
        "days": 5,
        "latest_date": latest_date,
        "source": "pykrx",
    }


def _get_toss_collector() -> Any | None:
    global _TOSS_COLLECTOR
    if _TOSS_COLLECTOR is not None:
        return _TOSS_COLLECTOR

    with _TOSS_COLLECTOR_LOCK:
        if _TOSS_COLLECTOR is not None:
            return _TOSS_COLLECTOR
        try:
            from engine.toss_collector import TossCollector

            _TOSS_COLLECTOR = TossCollector()
        except Exception as error:
            logger.debug("Failed to initialize TossCollector for reference check: %s", error)
            _TOSS_COLLECTOR = None
    return _TOSS_COLLECTOR


def _fetch_toss_reference_trend(
    *,
    ticker: str,
    target_datetime: datetime | pd.Timestamp | str | None,
) -> dict[str, Any] | None:
    # Toss는 과거 기준일 조회가 불가능하므로 최신 조회에서만 사용한다.
    if _normalize_target_datetime(target_datetime) is not None:
        return None

    collector = _get_toss_collector()
    if collector is None:
        return None

    try:
        trend_payload = collector.get_investor_trend(str(ticker).zfill(6), days=5)
    except Exception as error:
        logger.debug("Toss reference trend fetch failed (%s): %s", ticker, error)
        return None
    return _normalize_external_trend_payload(trend_payload, source="toss")


def _get_reference_trend_cached(
    *,
    data_dir: str,
    source: str,
    ticker: str,
    target_datetime: datetime | pd.Timestamp | str | None,
) -> dict[str, Any] | None:
    # Toss는 과거 기준일(reference target_datetime 지정) 조회가 불가능하므로 즉시 종료한다.
    if str(source or "").strip().lower() == "toss" and _normalize_target_datetime(target_datetime) is not None:
        return None

    normalized_data_dir = _normalize_data_dir(data_dir)
    ticker_key = str(ticker).zfill(6)
    target_key = _reference_cache_token(
        source=source,
        target_datetime=target_datetime,
        data_dir=normalized_data_dir,
    )
    cache_key = (source, ticker_key, target_key)

    with _REFERENCE_CACHE_LOCK:
        if cache_key in _REFERENCE_CACHE:
            _REFERENCE_CACHE.move_to_end(cache_key)
            cached = _REFERENCE_CACHE.get(cache_key)
            return dict(cached) if isinstance(cached, dict) else None

    sqlite_key, sqlite_signature = _reference_sqlite_context(
        data_dir=normalized_data_dir,
        source=source,
        ticker=ticker_key,
        target_datetime=target_datetime,
    )
    try:
        loaded, payload = load_json_payload_from_sqlite(
            filepath=sqlite_key,
            signature=sqlite_signature,
            logger=logger,
        )
    except Exception as error:
        logger.debug("Failed to load investor trend reference sqlite cache: %s", error)
    else:
        if loaded and isinstance(payload, dict):
            normalized_sqlite_payload = _normalize_external_trend_payload(payload, source=source)
            if isinstance(normalized_sqlite_payload, dict):
                with _REFERENCE_CACHE_LOCK:
                    _REFERENCE_CACHE[cache_key] = normalized_sqlite_payload
                    _REFERENCE_CACHE.move_to_end(cache_key)
                    while len(_REFERENCE_CACHE) > _REFERENCE_CACHE_MAX_ENTRIES:
                        _REFERENCE_CACHE.popitem(last=False)
                return dict(normalized_sqlite_payload)

    if source == "pykrx":
        payload = _fetch_pykrx_reference_trend(
            ticker=ticker_key,
            target_datetime=target_datetime,
            data_dir=normalized_data_dir,
        )
    elif source == "toss":
        payload = _fetch_toss_reference_trend(ticker=ticker_key, target_datetime=target_datetime)
    else:
        payload = None

    normalized_payload = _normalize_external_trend_payload(payload, source=source) if payload else None
    if isinstance(normalized_payload, dict):
        with _REFERENCE_CACHE_LOCK:
            _REFERENCE_CACHE[cache_key] = normalized_payload
            _REFERENCE_CACHE.move_to_end(cache_key)
            while len(_REFERENCE_CACHE) > _REFERENCE_CACHE_MAX_ENTRIES:
                _REFERENCE_CACHE.popitem(last=False)
    else:
        # miss(None)를 장시간 캐시하지 않아 일시 장애 후 재시도를 허용한다.
        with _REFERENCE_CACHE_LOCK:
            _REFERENCE_CACHE.pop(cache_key, None)

    if isinstance(normalized_payload, dict):
        try:
            save_json_payload_to_sqlite(
                filepath=sqlite_key,
                signature=sqlite_signature,
                payload=normalized_payload,
                max_rows=_REFERENCE_SQLITE_MAX_ROWS,
                logger=logger,
            )
        except Exception as error:
            logger.debug("Failed to save investor trend reference sqlite cache: %s", error)
    return dict(normalized_payload) if isinstance(normalized_payload, dict) else None


def _attach_selection_metadata(
    payload: dict[str, Any],
    *,
    selected_source: str,
    csv_flags: list[str],
    reference_sources: list[str],
) -> dict[str, Any]:
    enriched = dict(payload)
    enriched["source"] = selected_source
    enriched["quality"] = {
        "csv_anomaly_flags": list(csv_flags),
        "reference_sources": list(reference_sources),
    }
    return enriched


def _resolve_best_payload(
    *,
    data_dir: str,
    csv_payload: dict[str, Any] | None,
    ticker: str,
    target_datetime: datetime | pd.Timestamp | str | None,
    verify_with_references: bool,
) -> dict[str, Any] | None:
    csv_flags = _detect_csv_anomaly_flags(csv_payload, target_datetime=target_datetime)
    normalized_csv = _normalize_external_trend_payload(csv_payload, source="csv") if csv_payload else None
    is_latest_reference_window = _normalize_target_datetime(target_datetime) is None
    if normalized_csv is None:
        csv_flags = sorted(set(csv_flags + ["missing_csv"]))

    references: list[dict[str, Any]] = []
    if verify_with_references and csv_flags:
        pykrx_ref = _get_reference_trend_cached(
            data_dir=data_dir,
            source="pykrx",
            ticker=ticker,
            target_datetime=target_datetime,
        )
        if pykrx_ref:
            references.append(pykrx_ref)

        # 기본 우선순위가 pykrx이므로 pykrx가 있으면 Toss 조회를 생략해 지연을 줄인다.
        if not pykrx_ref and is_latest_reference_window:
            toss_ref = _get_reference_trend_cached(
                data_dir=data_dir,
                source="toss",
                ticker=ticker,
                target_datetime=target_datetime,
            )
            if toss_ref:
                references.append(toss_ref)

    reference_sources = [str(item.get("source", "")) for item in references if isinstance(item, dict)]

    if normalized_csv is None:
        if references:
            # 기본 우선순위: pykrx > toss
            selected = next((item for item in references if item.get("source") == "pykrx"), references[0])
            return _attach_selection_metadata(
                selected,
                selected_source=str(selected.get("source", "reference")),
                csv_flags=csv_flags,
                reference_sources=reference_sources,
            )
        return None

    if not references:
        return _attach_selection_metadata(
            normalized_csv,
            selected_source="csv",
            csv_flags=csv_flags,
            reference_sources=[],
        )

    disagreement_flags = [
        _is_large_disagreement(normalized_csv, reference_payload)
        for reference_payload in references
    ]
    should_replace = any(disagreement_flags) or bool(csv_flags)

    if should_replace:
        selected = next((item for item in references if item.get("source") == "pykrx"), references[0])
        return _attach_selection_metadata(
            selected,
            selected_source=str(selected.get("source", "reference")),
            csv_flags=csv_flags,
            reference_sources=reference_sources,
        )

    return _attach_selection_metadata(
        normalized_csv,
        selected_source="csv",
        csv_flags=csv_flags,
        reference_sources=reference_sources,
    )


def _get_or_build_trend_map(
    *,
    data_dir: str,
    filename: str,
    target_datetime: datetime | pd.Timestamp | str | None = None,
) -> dict[str, dict[str, Any]]:
    context = _resolve_trend_file_context(data_dir=data_dir, filename=filename)
    if context is None:
        return {}

    filepath, signature = context
    target_key = _target_token(target_datetime)
    memory_cache_key = (filepath, int(signature[0]), int(signature[1]), target_key)

    with _TREND_CACHE_LOCK:
        cached = _TREND_CACHE.get(memory_cache_key)
        if isinstance(cached, dict):
            _TREND_CACHE.move_to_end(memory_cache_key)
            return cached

    sqlite_key = _sqlite_cache_key(filepath, target_key)
    try:
        loaded, payload = load_json_payload_from_sqlite(
            filepath=sqlite_key,
            signature=signature,
            logger=logger,
        )
    except Exception as error:
        logger.debug("Failed to load investor trend 5day sqlite cache: %s", error)
    else:
        if loaded and isinstance(payload, dict):
            cached_map = _deserialize_trend_map(payload)
            if cached_map is not None:
                with _TREND_CACHE_LOCK:
                    _TREND_CACHE[memory_cache_key] = cached_map
                    _TREND_CACHE.move_to_end(memory_cache_key)
                    while len(_TREND_CACHE) > _MEMORY_CACHE_MAX_ENTRIES:
                        _TREND_CACHE.popitem(last=False)
                return cached_map

    trend_df = _load_trend_df(
        data_dir=data_dir,
        filename=filename,
        signature=signature,
    )
    trend_map = _build_trend_map(trend_df, target_datetime=target_datetime)
    with _TREND_CACHE_LOCK:
        _TREND_CACHE[memory_cache_key] = trend_map
        _TREND_CACHE.move_to_end(memory_cache_key)
        while len(_TREND_CACHE) > _MEMORY_CACHE_MAX_ENTRIES:
            _TREND_CACHE.popitem(last=False)

    try:
        save_json_payload_to_sqlite(
            filepath=sqlite_key,
            signature=signature,
            payload=_serialize_trend_map(trend_map),
            max_rows=_SQLITE_MAX_ROWS,
            logger=logger,
        )
    except Exception as error:
        logger.debug("Failed to save investor trend 5day sqlite cache: %s", error)

    return trend_map


def load_investor_trend_5day_map(
    *,
    data_dir: str,
    filename: str = _TREND_FILENAME,
    target_datetime: datetime | pd.Timestamp | str | None = None,
) -> dict[str, dict[str, Any]]:
    """
    ticker별 5거래일 수급 합산 맵을 반환한다.

    Returns:
        {
            "005930": {
                "foreign": int,
                "institution": int,
                "details": [
                    {"netForeignerBuyVolume": int, "netInstitutionBuyVolume": int},
                    ...
                ],
                "days": 5,
            }
        }
    """
    normalized_data_dir = _normalize_data_dir(data_dir)
    trend_map = _get_or_build_trend_map(
        data_dir=normalized_data_dir,
        filename=filename,
        target_datetime=target_datetime,
    )
    return dict(trend_map)


def get_investor_trend_5day_for_ticker(
    *,
    ticker: str,
    data_dir: str,
    filename: str = _TREND_FILENAME,
    target_datetime: datetime | pd.Timestamp | str | None = None,
    verify_with_references: bool = True,
) -> dict[str, Any] | None:
    """
    단일 ticker의 5거래일 수급 합산 데이터를 반환한다.

    verify_with_references=True이면 CSV 이상징후가 감지될 때 Toss/pykrx를 교차검증해
    더 신뢰 가능한 수급값으로 자동 교체한다.
    """
    normalized_data_dir = _normalize_data_dir(data_dir)
    trend_map = _get_or_build_trend_map(
        data_dir=normalized_data_dir,
        filename=filename,
        target_datetime=target_datetime,
    )
    ticker_key = str(ticker).zfill(6)
    result = trend_map.get(ticker_key)
    normalized_result = result if isinstance(result, dict) else None
    return _resolve_best_payload(
        data_dir=normalized_data_dir,
        csv_payload=normalized_result,
        ticker=ticker_key,
        target_datetime=target_datetime,
        verify_with_references=verify_with_references,
    )


def clear_investor_trend_5day_memory_cache() -> None:
    """테스트/디버깅용: in-memory 캐시를 비운다."""
    with _TREND_CACHE_LOCK:
        _TREND_CACHE.clear()
    with _REFERENCE_CACHE_LOCK:
        _REFERENCE_CACHE.clear()
    with _PYKRX_MARKET_DATE_LOCK:
        _PYKRX_MARKET_DATE_CACHE.clear()


__all__ = [
    "load_investor_trend_5day_map",
    "get_investor_trend_5day_for_ticker",
    "clear_investor_trend_5day_memory_cache",
]
