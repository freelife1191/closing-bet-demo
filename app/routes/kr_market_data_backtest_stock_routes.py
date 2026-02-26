#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Data Routes - Backtest/Stock
"""

from __future__ import annotations

from typing import Any

from flask import jsonify


def register_market_data_backtest_stock_routes(
    kr_bp: Any,
    *,
    logger: Any,
    deps: dict[str, Any],
) -> None:
    """백테스트/종목상세 라우트를 등록한다."""

    build_backtest_summary_payload = deps["build_backtest_summary_payload"]
    load_json_file = deps["load_json_file"]
    load_backtest_price_snapshot = deps["load_backtest_price_snapshot"]
    load_jongga_result_payloads = deps["load_jongga_result_payloads"]
    calculate_jongga_backtest_stats = deps["calculate_jongga_backtest_stats"]
    load_csv_file = deps["load_csv_file"]
    calculate_vcp_backtest_stats = deps["calculate_vcp_backtest_stats"]
    fetch_stock_detail_payload = deps["fetch_stock_detail_payload"]
    get_data_path = deps.get("get_data_path")
    data_dir_getter = deps.get("data_dir_getter")

    @kr_bp.route('/backtest-summary')
    def get_backtest_summary():
        """백테스팅 결과 요약 (VCP + Closing Bet) - Dynamic Calculation"""
        try:
            payload = build_backtest_summary_payload(
                load_json_file=load_json_file,
                load_backtest_price_snapshot=load_backtest_price_snapshot,
                load_jongga_result_payloads=load_jongga_result_payloads,
                calculate_jongga_backtest_stats=calculate_jongga_backtest_stats,
                load_csv_file=load_csv_file,
                calculate_vcp_backtest_stats=calculate_vcp_backtest_stats,
                logger=logger,
                get_data_path=get_data_path,
                data_dir_getter=data_dir_getter,
            )
            return jsonify(payload)

        except Exception as e:
            logger.error(f"Backtest Summary Error: {e}")
            return jsonify({'error': str(e)}), 500

    @kr_bp.route('/stock-detail/<ticker>')
    def get_stock_detail(ticker: str):
        """종목 상세 정보 조회 API (Toss -> Naver -> 기본값 fallback)."""
        try:
            resolved_data_dir = data_dir_getter() if callable(data_dir_getter) else None
            payload = fetch_stock_detail_payload(
                ticker=ticker,
                load_csv_file=load_csv_file,
                logger=logger,
                data_dir=resolved_data_dir,
            )
            return jsonify(payload)
        except Exception as e:
            logger.error(f"Error getting stock detail for {ticker}: {e}")
            return jsonify({'error': str(e)}), 500
