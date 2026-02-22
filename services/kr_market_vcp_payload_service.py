#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market VCP Payload Service
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable

import pandas as pd

from services.kr_market_csv_utils import load_csv_readonly as _load_csv_readonly
from services.kr_market_vcp_signals_cache import (
    build_vcp_signals_cache_signature,
    get_cached_vcp_signals,
    save_cached_vcp_signals,
)


def build_vcp_signals_payload(
    req_date: str | None,
    load_csv_file: Callable[[str], pd.DataFrame],
    load_json_file: Callable[[str], dict[str, Any]],
    filter_signals_dataframe_by_date: Callable[[pd.DataFrame, str | None, str], tuple[pd.DataFrame, str]],
    build_vcp_signals_from_dataframe: Callable[[pd.DataFrame], list[dict[str, Any]]],
    load_latest_vcp_price_map: Callable[[], dict[str, Any]],
    apply_latest_prices_to_jongga_signals: Callable[[list[dict[str, Any]], dict[str, Any]], int],
    sort_and_limit_vcp_signals: Callable[[list[dict[str, Any]], int], list[dict[str, Any]]],
    build_ai_data_map: Callable[[dict[str, Any]], dict[str, Any]],
    merge_legacy_ai_fields_into_map: Callable[[dict[str, Any], dict[str, Any]], None],
    merge_ai_data_into_vcp_signals: Callable[[list[dict[str, Any]], dict[str, Any]], int],
    count_total_scanned_stocks: Callable[[str], int],
    logger: logging.Logger,
    now: datetime | None = None,
    data_dir: str = "data",
) -> dict[str, Any]:
    """VCP 시그널 응답 payload를 구성한다."""
    current_time = now or datetime.now()
    signals, source = _load_vcp_signals(
        req_date=req_date,
        load_csv_file=load_csv_file,
        filter_signals_dataframe_by_date=filter_signals_dataframe_by_date,
        build_vcp_signals_from_dataframe=build_vcp_signals_from_dataframe,
        logger=logger,
        current_time=current_time,
        data_dir=data_dir,
    )

    try:
        latest_price_map = load_latest_vcp_price_map()
        if latest_price_map:
            apply_latest_prices_to_jongga_signals(signals, latest_price_map)
    except Exception as e:
        logger.warning(f"Failed to inject real-time prices: {e}")

    if signals:
        signals = sort_and_limit_vcp_signals(signals, limit=20)
        try:
            _merge_ai_into_vcp_signals(
                signals=signals,
                load_json_file=load_json_file,
                build_ai_data_map=build_ai_data_map,
                merge_legacy_ai_fields_into_map=merge_legacy_ai_fields_into_map,
                merge_ai_data_into_vcp_signals=merge_ai_data_into_vcp_signals,
                logger=logger,
                current_time=current_time,
            )
        except Exception as e:
            logger.warning(f"Failed to merge AI data into signals: {e}")

    try:
        total_scanned = count_total_scanned_stocks(data_dir)
    except Exception as e:
        logger.warning(f"Failed to count scanned stocks: {e}")
        total_scanned = 0

    return {
        "signals": signals,
        "count": len(signals),
        "total_scanned": total_scanned,
        "generated_at": current_time.isoformat(),
        "source": source,
    }


def _load_vcp_signals(
    req_date: str | None,
    load_csv_file: Callable[[str], pd.DataFrame],
    filter_signals_dataframe_by_date: Callable[[pd.DataFrame, str | None, str], tuple[pd.DataFrame, str]],
    build_vcp_signals_from_dataframe: Callable[[pd.DataFrame], list[dict[str, Any]]],
    logger: logging.Logger,
    current_time: datetime,
    data_dir: str,
) -> tuple[list[dict[str, Any]], str]:
    source = "no_data"
    today = current_time.strftime("%Y-%m-%d")
    cache_signature = build_vcp_signals_cache_signature(
        data_dir=data_dir,
        req_date=req_date,
        today=today,
    )
    cached_signals = get_cached_vcp_signals(
        signature=cache_signature,
        data_dir=data_dir,
        logger=logger,
    )
    if cached_signals is not None:
        if cached_signals:
            source = "signals_log.csv"
        return cached_signals, source

    signals_df = _load_csv_readonly(
        load_csv_file,
        "signals_log.csv",
        usecols=[
            "ticker",
            "name",
            "signal_date",
            "market",
            "status",
            "score",
            "contraction_ratio",
            "entry_price",
            "target_price",
            "stop_price",
            "foreign_5d",
            "inst_5d",
            "vcp_score",
            "current_price",
            "return_pct",
            "ai_action",
            "ai_reason",
            "ai_confidence",
        ],
    )
    signals_df, _ = filter_signals_dataframe_by_date(signals_df, req_date, today)

    if req_date:
        logger.debug(f"Signals requested for explicit date: {req_date}")
    elif not signals_df.empty:
        logger.debug(f"Filtered latest signal rows: {len(signals_df)}")

    signals = build_vcp_signals_from_dataframe(signals_df)
    if signals:
        source = "signals_log.csv"
    save_cached_vcp_signals(
        signature=cache_signature,
        payload=signals,
        data_dir=data_dir,
        logger=logger,
    )
    return signals, source


def _merge_ai_into_vcp_signals(
    signals: list[dict[str, Any]],
    load_json_file: Callable[[str], dict[str, Any]],
    build_ai_data_map: Callable[[dict[str, Any]], dict[str, Any]],
    merge_legacy_ai_fields_into_map: Callable[[dict[str, Any], dict[str, Any]], None],
    merge_ai_data_into_vcp_signals: Callable[[list[dict[str, Any]], dict[str, Any]], int],
    logger: logging.Logger,
    current_time: datetime,
) -> None:
    if not signals:
        return

    sig_date = signals[0].get("signal_date", "")
    date_str = sig_date.replace("-", "") if sig_date else current_time.strftime("%Y%m%d")
    ai_json = load_json_file(f"ai_analysis_results_{date_str}.json")
    if not ai_json or "signals" not in ai_json:
        logger.info("Falling back to kr_ai_analysis.json")
        ai_json = load_json_file("kr_ai_analysis.json")

    logger.debug(
        "AI JSON Loaded: %s, Signals in JSON: %d",
        bool(ai_json),
        len(ai_json.get("signals", [])) if isinstance(ai_json, dict) else 0,
    )

    ai_data_map = build_ai_data_map(ai_json)
    try:
        legacy_json = load_json_file("kr_ai_analysis.json")
        merge_legacy_ai_fields_into_map(ai_data_map, legacy_json)
    except Exception as legacy_error:
        logger.warning(f"Legacy merge failed: {legacy_error}")

    merged_count = merge_ai_data_into_vcp_signals(signals, ai_data_map)
    logger.debug(f"Merged AI data for {merged_count} signals")


__all__ = [
    "build_vcp_signals_payload",
]
