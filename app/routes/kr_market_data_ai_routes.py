#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Data Routes - AI/Cumulative
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from flask import jsonify, request

from app.routes.route_execution import execute_json_route as _execute_json_route
from services.kr_market_cumulative_cache import (
    build_cumulative_cache_signature,
    get_cached_cumulative_payload,
    save_cached_cumulative_payload,
)
from services.kr_market_csv_utils import load_csv_readonly


def _parse_positive_int_query_arg(
    raw_value: Any,
    *,
    default: int,
    minimum: int = 1,
    maximum: int | None = None,
) -> int:
    """query string 정수 파라미터를 안전하게 파싱한다."""
    try:
        parsed = int(float(str(raw_value).strip()))
    except (TypeError, ValueError):
        return int(default)

    if parsed < int(minimum):
        return int(default)
    if maximum is not None and parsed > int(maximum):
        return int(maximum)
    return parsed


def _load_cumulative_price_source(
    *,
    deps: dict[str, Any],
    logger: Any,
) -> Any:
    snapshot_loader = deps.get("load_backtest_price_snapshot")
    if callable(snapshot_loader):
        try:
            raw_price_df, _ = snapshot_loader()
            return raw_price_df
        except Exception as error:
            logger.warning(f"Backtest snapshot loader failed, fallback to CSV: {error}")

    return load_csv_readonly(
        deps["load_csv_file"],
        "daily_prices.csv",
        usecols=["date", "ticker", "open", "high", "low", "close"],
    )


def register_market_data_ai_routes(
    kr_bp: Any,
    *,
    logger: Any,
    deps: dict[str, Any],
) -> None:
    """AI 분석/누적 성과 라우트를 등록한다."""
    _register_ai_analysis_route(kr_bp, logger=logger, deps=deps)
    _register_cumulative_performance_route(kr_bp, logger=logger, deps=deps)


def _register_ai_analysis_route(
    kr_bp: Any,
    *,
    logger: Any,
    deps: dict[str, Any],
) -> None:
    @kr_bp.route('/ai-analysis')
    def get_kr_ai_analysis():
        """KR AI 분석 전체 - kr_ai_analysis.json 직접 읽기 (V2 호환 최적화)"""
        def _handler():
            target_date = request.args.get("date")
            dated_payload = deps["build_ai_analysis_payload_for_target_date"](
                target_date=target_date,
                load_json_file=deps["load_json_file"],
                build_ai_signals_from_jongga_results=deps["build_ai_signals_from_jongga_results"],
                normalize_ai_payload_tickers=deps["normalize_ai_payload_tickers"],
                logger=logger,
            )
            if dated_payload is not None:
                return jsonify(dated_payload)

            latest_payload = deps["build_latest_ai_analysis_payload"](
                load_json_file=deps["load_json_file"],
                should_use_jongga_ai_payload=deps["should_use_jongga_ai_payload"],
                build_ai_signals_from_jongga_results=deps["build_ai_signals_from_jongga_results"],
                normalize_ai_payload_tickers=deps["normalize_ai_payload_tickers"],
                format_signal_date=deps["format_signal_date"],
            )
            return jsonify(latest_payload)

        return _execute_json_route(
            handler=_handler,
            logger=logger,
            error_label="Error getting AI analysis",
        )


def _register_cumulative_performance_route(
    kr_bp: Any,
    *,
    logger: Any,
    deps: dict[str, Any],
) -> None:
    @kr_bp.route('/closing-bet/cumulative')
    def get_cumulative_performance():
        """종가베팅 누적 성과 조회 (실제 데이터 연동)"""
        def _handler():
            cache_signature = build_cumulative_cache_signature(
                get_data_path=deps.get("get_data_path"),
                data_dir_getter=deps.get("data_dir_getter"),
            )
            cached_payload = get_cached_cumulative_payload(
                signature=cache_signature,
                logger=logger,
            )
            if cached_payload is None:
                result_payloads = deps["load_jongga_result_payloads"]()
                raw_price_df = _load_cumulative_price_source(
                    deps=deps,
                    logger=logger,
                )
                price_df = deps["prepare_cumulative_price_dataframe"](raw_price_df)
                price_index = deps["build_ticker_price_index"](price_df)

                if not raw_price_df.empty and price_df.empty:
                    logger.warning("daily_prices.csv missing required columns (date, ticker)")

                trades = []
                for filepath, data in result_payloads:
                    signals = data.get("signals", [])
                    if not isinstance(signals, list):
                        continue

                    stats_date = deps["extract_stats_date_from_results_filename"](
                        filepath,
                        fallback_date=data.get("date", ""),
                    )
                    for signal in signals:
                        trade = deps["build_cumulative_trade_record"](
                            signal,
                            stats_date,
                            price_df,
                            price_index=price_index,
                        )
                        if trade:
                            trades.append(trade)

                kpi = deps["aggregate_cumulative_kpis"](trades, price_df, datetime.now())
                save_cached_cumulative_payload(
                    signature=cache_signature,
                    payload={"kpi": kpi, "trades": trades},
                    logger=logger,
                )
            else:
                kpi = cached_payload.get("kpi", {})
                trades = cached_payload.get("trades", [])
                if not isinstance(trades, list):
                    trades = []

            page = _parse_positive_int_query_arg(
                request.args.get("page", 1),
                default=1,
                minimum=1,
            )
            limit = _parse_positive_int_query_arg(
                request.args.get("limit", 50),
                default=50,
                minimum=1,
                maximum=500,
            )
            paginated_trades, pagination = deps["paginate_items"](trades, page, limit)

            return jsonify({"kpi": kpi, "trades": paginated_trades, "pagination": pagination})

        return _execute_json_route(
            handler=_handler,
            logger=logger,
            error_label="Error calculating cumulative performance",
        )
