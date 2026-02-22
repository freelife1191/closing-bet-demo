#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Backtest Route Helpers

백테스트/누적성과 관련 helper wrapper를 분리한다.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from services.kr_market_backtest_service import (
    aggregate_cumulative_kpis as _aggregate_cumulative_kpis_service,
    build_cumulative_trade_record as _build_cumulative_trade_record_service,
    build_ticker_price_index as _build_ticker_price_index_service,
    build_latest_price_map as _build_latest_price_map_service,
    calculate_cumulative_trade_metrics as _calculate_cumulative_trade_metrics_service,
    calculate_jongga_backtest_stats as _calculate_jongga_backtest_stats_service,
    calculate_scenario_return as _calculate_scenario_return_service,
    calculate_vcp_backtest_stats as _calculate_vcp_backtest_stats_service,
    extract_stats_date_from_results_filename as _extract_stats_date_from_results_filename_service,
    inject_latest_prices_to_candidates as _inject_latest_prices_to_candidates_service,
    paginate_items as _paginate_items_service,
    prepare_cumulative_price_dataframe as _prepare_cumulative_price_dataframe_service,
)


def _prepare_cumulative_price_dataframe(raw_price_df: Any) -> Any:
    return _prepare_cumulative_price_dataframe_service(raw_price_df)


def _extract_stats_date_from_results_filename(filepath: str, fallback_date: Any = "") -> str:
    return _extract_stats_date_from_results_filename_service(filepath, fallback_date)


def _calculate_cumulative_trade_metrics(
    entry_price: float,
    stats_date: str,
    stock_prices: Any,
) -> Dict[str, Any]:
    return _calculate_cumulative_trade_metrics_service(entry_price, stats_date, stock_prices)


def _build_cumulative_trade_record(
    signal: dict,
    stats_date: str,
    price_df: Any,
    price_index: Any = None,
) -> Optional[dict]:
    return _build_cumulative_trade_record_service(
        signal,
        stats_date,
        price_df,
        price_index=price_index,
    )


def _build_ticker_price_index(price_df: Any) -> Dict[str, Any]:
    return _build_ticker_price_index_service(price_df)


def _aggregate_cumulative_kpis(trades: List[dict], price_df: Any, now_dt: datetime) -> dict:
    return _aggregate_cumulative_kpis_service(trades, price_df, now_dt)


def _paginate_items(items: List[dict], page: int, limit: int) -> Tuple[List[dict], dict]:
    return _paginate_items_service(items, page, limit)


def _build_latest_price_map(price_df: Any) -> Dict[str, float]:
    return _build_latest_price_map_service(price_df)


def _inject_latest_prices_to_candidates(candidates: List[dict], price_map: Dict[str, float]) -> None:
    _inject_latest_prices_to_candidates_service(candidates, price_map)


def _calculate_scenario_return(
    ticker: str,
    entry_price: float,
    signal_date: Any,
    current_price: float,
    price_df: Any,
    target_pct: float = 0.15,
    stop_pct: float = 0.05,
) -> float:
    return _calculate_scenario_return_service(
        ticker=ticker,
        entry_price=entry_price,
        signal_date=signal_date,
        current_price=current_price,
        price_df=price_df,
        target_pct=target_pct,
        stop_pct=stop_pct,
    )


def _calculate_jongga_backtest_stats(
    candidates: List[dict],
    history_payloads: List[dict],
    price_map: Dict[str, float],
    price_df: Any,
    price_index: Optional[Dict[str, Any]] = None,
) -> dict:
    return _calculate_jongga_backtest_stats_service(
        candidates=candidates,
        history_payloads=history_payloads,
        price_map=price_map,
        price_df=price_df,
        price_index=price_index,
    )


def _calculate_vcp_backtest_stats(
    vcp_df: Any,
    price_map: Dict[str, float],
    price_df: Any,
    price_index: Optional[Dict[str, Any]] = None,
) -> dict:
    return _calculate_vcp_backtest_stats_service(
        vcp_df=vcp_df,
        price_map=price_map,
        price_df=price_df,
        price_index=price_index,
    )
