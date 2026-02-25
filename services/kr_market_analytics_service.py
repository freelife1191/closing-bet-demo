#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Analytics Service

차트/데이터 상태/백테스트 요약 로직을 route service에서 분리한다.
"""

from __future__ import annotations

import copy
import logging
import os
import threading
from collections import OrderedDict
from datetime import datetime
from typing import Any, Callable

import pandas as pd

from services.kr_market_csv_utils import (
    get_ticker_padded_series as _get_ticker_padded_series,
    load_csv_readonly as _load_csv_readonly,
)
from services.file_row_count_cache import get_cached_file_row_count
from services.kr_market_backtest_cumulative import build_ticker_price_index
from services.kr_market_backtest_summary_cache import (
    build_backtest_summary_cache_signature,
    get_cached_backtest_summary,
    save_cached_backtest_summary,
)


CHART_NUMERIC_COLUMNS = ["open", "high", "low", "close", "volume"]
CHART_REQUIRED_COLUMNS = ["date", *CHART_NUMERIC_COLUMNS]
_DATA_STATUS_CACHE: dict[
    tuple[tuple[str, str, tuple[int, int] | None], ...],
    dict[str, Any],
] = OrderedDict()
_DATA_STATUS_CACHE_LOCK = threading.Lock()
_DATA_STATUS_CACHE_MAX_ENTRIES = 32


def _file_signature(filepath: str) -> tuple[int, int] | None:
    try:
        stat = os.stat(filepath)
    except OSError:
        return None
    return int(stat.st_mtime_ns), int(stat.st_size)


def _iter_data_status_file_entries(
    files: dict[str, str],
    get_data_path: Callable[[str], str],
) -> list[tuple[str, str, tuple[int, int] | None]]:
    entries: list[tuple[str, str, tuple[int, int] | None]] = []
    for key, filename in files.items():
        filepath = get_data_path(filename)
        entries.append((key, filepath, _file_signature(filepath)))
    return entries


def clear_data_status_cache() -> None:
    with _DATA_STATUS_CACHE_LOCK:
        _DATA_STATUS_CACHE.clear()


def _normalize_chart_date(value: Any) -> str:
    """차트 날짜를 lightweight-charts 호환(YYYY-MM-DD) 형식으로 보정한다."""
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass

    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")

    date_str = str(value).strip()
    if not date_str:
        return ""
    if len(date_str) == 8 and date_str.isdigit():
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"

    normalized = date_str.replace("/", "-")
    base_date = normalized.split("T", 1)[0].split(" ", 1)[0]
    if len(base_date) == 10 and base_date[4] == "-" and base_date[7] == "-":
        return base_date

    parsed = pd.to_datetime(date_str, errors="coerce")
    if pd.notna(parsed):
        return parsed.strftime("%Y-%m-%d")

    return ""


def _build_chart_rows(stock_df: pd.DataFrame) -> list[dict[str, Any]]:
    if stock_df.empty:
        return []

    chart_df = stock_df.copy()
    if "date" not in chart_df.columns:
        chart_df["date"] = ""
    chart_df = chart_df.reindex(columns=CHART_REQUIRED_COLUMNS, fill_value=0)
    return [
        {
            "date": _normalize_chart_date(date_value),
            "open": float(open_value),
            "high": float(high_value),
            "low": float(low_value),
            "close": float(close_value),
            "volume": int(volume_value),
        }
        for date_value, open_value, high_value, low_value, close_value, volume_value in chart_df.itertuples(
            index=False,
            name=None,
        )
    ]


def _normalize_chart_numeric_columns(stock_df: pd.DataFrame) -> pd.DataFrame:
    """차트 수치 컬럼 보정/형변환을 벡터화로 수행한다."""
    for col in CHART_NUMERIC_COLUMNS:
        if col not in stock_df.columns:
            stock_df[col] = 0

    stock_df.loc[:, CHART_NUMERIC_COLUMNS] = (
        stock_df.loc[:, CHART_NUMERIC_COLUMNS]
        .apply(pd.to_numeric, errors="coerce")
        .fillna(0)
    )
    return stock_df


def resolve_chart_period_days(period: str | None) -> int:
    period_map = {
        "1m": 30,
        "3m": 90,
        "6m": 180,
        "1y": 365,
    }
    return period_map.get(str(period or "3m").lower(), 90)


def build_stock_chart_payload(
    ticker: str,
    period_days: int,
    load_csv_file: Callable[[str], pd.DataFrame],
    now: datetime | None = None,
) -> dict[str, Any]:
    """종목 차트 응답 payload를 구성한다."""
    current_time = now or datetime.now()
    ticker_padded = str(ticker).zfill(6)
    df = _load_csv_readonly(
        load_csv_file,
        "daily_prices.csv",
        usecols=["date", "ticker", "open", "high", "low", "close", "volume"],
    )

    if df.empty:
        return {
            "ticker": ticker_padded,
            "data": [],
            "message": "데이터 파일이 없습니다.",
        }

    ticker_padded_series = _get_ticker_padded_series(df)
    stock_df = df.loc[ticker_padded_series == ticker_padded].copy()

    if stock_df.empty:
        return {
            "ticker": ticker_padded,
            "data": [],
            "message": "해당 종목 데이터가 없습니다.",
        }

    if "date" in stock_df.columns:
        cutoff_date = (current_time - pd.Timedelta(days=period_days)).strftime("%Y-%m-%d")
        stock_df = stock_df[stock_df["date"] >= cutoff_date]

    stock_df = _normalize_chart_numeric_columns(stock_df)

    stock_df = stock_df[(stock_df["close"] > 0) & (stock_df["volume"] > 0)]

    chart_data = _build_chart_rows(stock_df)

    return {
        "ticker": ticker_padded,
        "data": chart_data,
    }


def build_data_status_payload(
    get_data_path: Callable[[str], str],
    load_csv_file: Callable[[str], pd.DataFrame],
    load_json_file: Callable[[str], dict[str, Any]],
    logger: logging.Logger | None = None,
) -> dict[str, Any]:
    """데이터 수집 상태 payload를 구성한다."""
    app_logger = logger or logging.getLogger(__name__)

    status = {
        "last_update": None,
        "collected_stocks": 0,
        "signals_count": 0,
        "market_status": "UNKNOWN",
        "files": {},
    }

    files = {
        "stocks": "korean_stocks_list.csv",
        "prices": "daily_prices.csv",
        "signals": "signals_log.csv",
        "market_gate": "market_gate.json",
        "jongga": "jongga_v2_latest.json",
    }
    file_entries = _iter_data_status_file_entries(files, get_data_path)
    file_entry_map = {key: (filepath, signature) for key, filepath, signature in file_entries}
    cache_signature = tuple(file_entries)
    with _DATA_STATUS_CACHE_LOCK:
        cached_payload = _DATA_STATUS_CACHE.get(cache_signature)
        if cached_payload is not None:
            _DATA_STATUS_CACHE.move_to_end(cache_signature)
            return copy.deepcopy(cached_payload)

    latest_mtime: datetime | None = None
    for key, filepath, signature in file_entries:
        if signature is None:
            status["files"][key] = {"exists": False}
            continue

        mtime_ns, file_size = signature
        mtime = datetime.fromtimestamp(mtime_ns / 1_000_000_000)
        status["files"][key] = {
            "exists": True,
            "updated_at": mtime.isoformat(),
            "size": file_size,
        }
        if latest_mtime is None or mtime > latest_mtime:
            latest_mtime = mtime

    if latest_mtime is not None:
        status["last_update"] = latest_mtime.isoformat()

    try:
        stocks_entry = file_entry_map.get("stocks")
        if stocks_entry is not None:
            stocks_path, stocks_signature = stocks_entry
            stocks_count = get_cached_file_row_count(
                path=stocks_path,
                signature=stocks_signature,
                logger=app_logger,
            )
            if stocks_count is not None:
                status["collected_stocks"] = int(stocks_count)

        signals_entry = file_entry_map.get("signals")
        if signals_entry is not None:
            signals_path, signals_signature = signals_entry
            signals_count = get_cached_file_row_count(
                path=signals_path,
                signature=signals_signature,
                logger=app_logger,
            )
            if signals_count is not None:
                status["signals_count"] = int(signals_count)

        gate_data = load_json_file("market_gate.json")
        if gate_data:
            status["market_status"] = gate_data.get("status", "UNKNOWN")
    except Exception as e:
        app_logger.warning(f"Failed to enrich data status payload: {e}")

    with _DATA_STATUS_CACHE_LOCK:
        _DATA_STATUS_CACHE[cache_signature] = copy.deepcopy(status)
        _DATA_STATUS_CACHE.move_to_end(cache_signature)
        normalized_max_entries = max(1, int(_DATA_STATUS_CACHE_MAX_ENTRIES))
        while len(_DATA_STATUS_CACHE) > normalized_max_entries:
            _DATA_STATUS_CACHE.popitem(last=False)

    return status


def build_backtest_summary_payload(
    load_json_file: Callable[[str], dict[str, Any]],
    load_backtest_price_snapshot: Callable[[], tuple[pd.DataFrame, dict[str, float]]],
    load_jongga_result_payloads: Callable[[int], list[tuple[str, dict[str, Any]]]],
    calculate_jongga_backtest_stats: Callable[
        [list[dict[str, Any]], list[dict[str, Any]], dict[str, float], pd.DataFrame],
        dict[str, Any],
    ],
    load_csv_file: Callable[[str], pd.DataFrame],
    calculate_vcp_backtest_stats: Callable[[pd.DataFrame, dict[str, float], pd.DataFrame], dict[str, Any]],
    logger: logging.Logger,
    *,
    get_data_path: Callable[[str], str] | None = None,
    data_dir_getter: Callable[[], str] | None = None,
) -> dict[str, Any]:
    """백테스트 요약 payload를 계산한다."""
    cache_signature = build_backtest_summary_cache_signature(
        get_data_path=get_data_path,
        data_dir_getter=data_dir_getter,
        history_limit=30,
    )
    cached_payload = get_cached_backtest_summary(
        signature=cache_signature,
        logger=logger,
    )
    if cached_payload is not None:
        return cached_payload

    candidates: list[dict[str, Any]] = []
    latest_payload = load_json_file("jongga_v2_latest.json")
    if isinstance(latest_payload, dict) and isinstance(latest_payload.get("signals"), list):
        candidates = latest_payload.get("signals", [])

    try:
        price_df_full, price_map = load_backtest_price_snapshot()
    except Exception as e:
        logger.error(f"Backtest price loading failed: {e}")
        price_df_full, price_map = pd.DataFrame(), {}
    shared_price_index = build_ticker_price_index(price_df_full)

    jb_stats = {
        "status": "Accumulating",
        "count": 0,
        "win_rate": 0,
        "avg_return": 0,
        "candidates": candidates,
    }
    try:
        history_payloads = [payload for _, payload in load_jongga_result_payloads(30)]
        try:
            jb_stats = calculate_jongga_backtest_stats(
                candidates,
                history_payloads,
                price_map,
                price_df_full,
                price_index=shared_price_index,
            )
        except TypeError as type_error:
            # 기존 시그니처(4인자) 주입 함수 호환 유지
            if "price_index" not in str(type_error):
                raise
            jb_stats = calculate_jongga_backtest_stats(
                candidates,
                history_payloads,
                price_map,
                price_df_full,
            )
    except Exception as e:
        logger.error(f"Closing Bet Stat Calc Failed: {e}")

    vcp_stats = {
        "status": "Accumulating",
        "count": 0,
        "win_rate": 0,
        "avg_return": 0,
    }
    try:
        vcp_df = _load_csv_readonly(
            load_csv_file,
            "signals_log.csv",
            usecols=["ticker", "signal_date", "entry_price"],
        )
        try:
            vcp_stats = calculate_vcp_backtest_stats(
                vcp_df,
                price_map,
                price_df_full,
                price_index=shared_price_index,
            )
        except TypeError as type_error:
            if "price_index" not in str(type_error):
                raise
            vcp_stats = calculate_vcp_backtest_stats(
                vcp_df,
                price_map,
                price_df_full,
            )
    except Exception as e:
        logger.error(f"VCP Stat Calc Failed: {e}")

    payload = {"vcp": vcp_stats, "closing_bet": jb_stats}
    save_cached_backtest_summary(
        signature=cache_signature,
        payload=payload,
        logger=logger,
    )
    return payload
