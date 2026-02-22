#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Common Market Mock Routes
"""

from __future__ import annotations

import random
from collections.abc import Callable

from flask import jsonify, request

from app.routes.common_route_context import CommonRouteContext


def _execute_market_mock_route(
    *,
    handler: Callable[[], object],
    ctx: CommonRouteContext,
    error_label: str,
) -> object:
    try:
        return handler()
    except Exception as error:
        ctx.logger.error(f"{error_label}: {error}")
        return jsonify({"error": str(error)}), 500


def _register_stock_detail_mock_route(common_bp, ctx: CommonRouteContext) -> None:
    @common_bp.route("/stock/<ticker>")
    def get_stock_detail(ticker):
        """개별 종목 상세 정보."""
        def _handler():
            stock_names = {
                "005930": "삼성전자",
                "000270": "기아",
                "035420": "NAVER",
                "005380": "현대차",
            }

            name = stock_names.get(ticker, "알 수 없는 종목")
            price = random.randint(50000, 150000)
            change = random.randint(-5000, 5000)
            change_pct = (change / price) * 100

            return jsonify(
                {
                    "ticker": ticker.zfill(6),
                    "name": name,
                    "sector": "기타",
                    "price": price,
                    "change": change,
                    "change_pct": change_pct,
                    "volume": random.randint(100000, 10000000),
                    "market_cap": price * random.randint(100, 1000),
                    "pe_ratio": round(random.uniform(5, 25), 2),
                    "dividend_yield": round(random.uniform(0, 5), 2),
                }
            )

        return _execute_market_mock_route(
            handler=_handler,
            ctx=ctx,
            error_label="Error getting stock detail",
        )


def _register_realtime_prices_mock_route(common_bp, ctx: CommonRouteContext) -> None:
    @common_bp.route("/realtime-prices", methods=["POST"])
    def get_realtime_prices():
        """실시간 가격 조회."""
        def _handler():
            data = request.get_json() or {}
            tickers = data.get("tickers", [])
            _market = data.get("market", "kr")

            if not tickers:
                return jsonify({"prices": {}})

            prices = {}
            for ticker in tickers:
                prices[str(ticker).zfill(6)] = random.randint(50000, 150000)

            return jsonify({"prices": prices})

        return _execute_market_mock_route(
            handler=_handler,
            ctx=ctx,
            error_label="Error fetching realtime prices",
        )


def _register_backtest_summary_mock_route(common_bp, ctx: CommonRouteContext) -> None:
    @common_bp.route("/kr/backtest-summary")
    def get_backtest_summary():
        """VCP 및 Closing Bet(Jongga V2) 백테스트 요약 반환."""
        def _handler():
            summary = {
                "vcp": {
                    "status": "OK",
                    "win_rate": 62.5,
                    "avg_return": 4.2,
                    "count": 16,
                },
                "closing_bet": {
                    "status": "OK",
                    "win_rate": 58.3,
                    "avg_return": 3.8,
                    "count": 12,
                },
            }
            return jsonify(summary)

        return _execute_market_mock_route(
            handler=_handler,
            ctx=ctx,
            error_label="Error getting backtest summary",
        )


def register_common_market_mock_routes(common_bp, ctx: CommonRouteContext) -> None:
    """샘플 시장/백테스트 라우트를 등록한다."""
    _register_stock_detail_mock_route(common_bp, ctx)
    _register_realtime_prices_mock_route(common_bp, ctx)
    _register_backtest_summary_mock_route(common_bp, ctx)
