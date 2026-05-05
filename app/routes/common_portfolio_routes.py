#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Common Portfolio Routes
"""

from __future__ import annotations

from flask import jsonify, request

from app.routes.common_route_context import CommonRouteContext
from services.paper_trading_constants import (
    DEFAULT_ASSET_HISTORY_LIMIT,
    DEFAULT_TRADE_HISTORY_LIMIT,
    INITIAL_CASH_KRW,
    MAX_ASSET_HISTORY_LIMIT,
    MAX_HISTORY_LIMIT,
)


def _execute_portfolio_route(
    *,
    handler,
    ctx: CommonRouteContext,
    error_label: str,
    error_payload_builder,
):
    try:
        return handler()
    except Exception as error:
        ctx.logger.error(f"{error_label}: {error}")
        return jsonify(error_payload_builder(error)), 500


def _parse_positive_int(value: object, *, default: int) -> int:
    try:
        parsed = int(float(value))
    except (TypeError, ValueError):
        return int(default)
    return parsed if parsed > 0 else int(default)


def _parse_positive_float(value: object, *, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return float(default)
    return parsed if parsed > 0 else float(default)


def _parse_history_limit(raw_value: object, *, default: int, cap: int = MAX_HISTORY_LIMIT) -> int:
    parsed = _parse_positive_int(raw_value, default=default)
    return min(parsed, int(cap))


def _register_portfolio_overview_routes(common_bp, ctx: CommonRouteContext) -> None:
    @common_bp.route("/portfolio")
    def get_portfolio_data():
        """포트폴리오 데이터 (Fast - Cached)."""
        def _handler():
            ctx.paper_trading.start_background_sync()
            data = ctx.paper_trading.get_portfolio_valuation()
            return jsonify(data)

        return _execute_portfolio_route(
            handler=_handler,
            ctx=ctx,
            error_label="Error fetching portfolio",
            error_payload_builder=lambda error: {"error": str(error)},
        )

    @common_bp.route("/portfolio/reset", methods=["POST"])
    def reset_portfolio():
        """모의 투자 초기화."""
        ctx.paper_trading.reset_account()
        return jsonify(
            {
                "status": "success",
                "message": f"Account reset to {int(INITIAL_CASH_KRW):,} KRW",
            }
        )


def _register_portfolio_trade_routes(common_bp, ctx: CommonRouteContext) -> None:
    @common_bp.route("/portfolio/buy", methods=["POST"])
    def buy_stock():
        """모의 투자 매수."""
        def _handler():
            data = request.get_json(silent=True) or {}
            ticker = data.get("ticker")
            name = data.get("name")
            price = _parse_positive_float(data.get("price"), default=0.0)
            quantity = _parse_positive_int(data.get("quantity", 0), default=0)

            if not all([ticker, name, price, quantity]):
                return jsonify({"status": "error", "message": "Missing data"}), 400

            result = ctx.paper_trading.buy_stock(ticker, name, price, quantity)
            return jsonify(result)

        return _execute_portfolio_route(
            handler=_handler,
            ctx=ctx,
            error_label="Error buying stock",
            error_payload_builder=lambda error: {"status": "error", "message": str(error)},
        )

    @common_bp.route("/portfolio/buy/bulk", methods=["POST"])
    def buy_stocks_bulk():
        """모의 투자 일괄 매수."""
        def _handler():
            data = request.get_json(silent=True) or {}
            orders = data.get("orders")
            if not isinstance(orders, list) or not orders:
                return jsonify({"status": "error", "message": "Missing orders"}), 400

            result = ctx.paper_trading.buy_stocks_bulk(orders)
            return jsonify(result)

        return _execute_portfolio_route(
            handler=_handler,
            ctx=ctx,
            error_label="Error bulk buying stocks",
            error_payload_builder=lambda error: {"status": "error", "message": str(error)},
        )

    @common_bp.route("/portfolio/sell", methods=["POST"])
    def sell_stock():
        """모의 투자 매도."""
        def _handler():
            data = request.get_json(silent=True) or {}
            ticker = data.get("ticker")
            price = _parse_positive_float(data.get("price"), default=0.0)
            quantity = _parse_positive_int(data.get("quantity", 0), default=0)

            if not all([ticker, price, quantity]):
                return jsonify({"status": "error", "message": "Missing data"}), 400

            result = ctx.paper_trading.sell_stock(ticker, price, quantity)
            return jsonify(result)

        return _execute_portfolio_route(
            handler=_handler,
            ctx=ctx,
            error_label="Error selling stock",
            error_payload_builder=lambda error: {"status": "error", "message": str(error)},
        )

    @common_bp.route("/portfolio/deposit", methods=["POST"])
    def deposit_cash():
        """예수금 충전."""
        def _handler():
            data = request.get_json(silent=True) or {}
            amount = _parse_positive_int(data.get("amount", 0), default=0)
            result = ctx.paper_trading.deposit_cash(amount)
            return jsonify(result)

        return _execute_portfolio_route(
            handler=_handler,
            ctx=ctx,
            error_label="Error depositing cash",
            error_payload_builder=lambda error: {"status": "error", "message": str(error)},
        )


def _register_portfolio_history_routes(common_bp, ctx: CommonRouteContext) -> None:
    @common_bp.route("/portfolio/history")
    def get_trade_history():
        """거래 내역 조회. ticker 쿼리 파라미터로 종목별 필터링 가능."""
        def _handler():
            limit = _parse_history_limit(
                request.args.get("limit", DEFAULT_TRADE_HISTORY_LIMIT),
                default=DEFAULT_TRADE_HISTORY_LIMIT,
            )
            ticker_param = request.args.get("ticker")
            ticker_filter = ticker_param.strip() if ticker_param else None
            data = ctx.paper_trading.get_trade_history(limit, ticker=ticker_filter)
            return jsonify(data)

        return _execute_portfolio_route(
            handler=_handler,
            ctx=ctx,
            error_label="Error getting trade history",
            error_payload_builder=lambda error: {"error": str(error)},
        )

    @common_bp.route("/portfolio/history/asset")
    def get_asset_history():
        """자산 변동 내역 조회 (차트용)."""
        def _handler():
            raw_days = request.args.get("days")
            days_param: int | None = None
            if raw_days is not None:
                try:
                    parsed_days = int(float(raw_days))
                    if parsed_days > 0:
                        days_param = parsed_days
                except (TypeError, ValueError):
                    days_param = None
            # 자산 히스토리는 하루 1건 스냅샷이므로 일반 캡(MAX_HISTORY_LIMIT)이 아닌
            # MAX_ASSET_HISTORY_LIMIT(약 10년치)을 캡으로 사용한다.
            # 기간 필터(days)가 있으면 그 기간을 모두 담을 수 있도록 limit 기본값을 캡까지 늘린다.
            default_limit = (
                MAX_ASSET_HISTORY_LIMIT if days_param is not None else DEFAULT_ASSET_HISTORY_LIMIT
            )
            limit = _parse_history_limit(
                request.args.get("limit", default_limit),
                default=default_limit,
                cap=MAX_ASSET_HISTORY_LIMIT,
            )
            data = ctx.paper_trading.get_asset_history(limit, days=days_param)
            return jsonify({"history": data})

        return _execute_portfolio_route(
            handler=_handler,
            ctx=ctx,
            error_label="Error getting asset history",
            error_payload_builder=lambda error: {"error": str(error)},
        )


def register_common_portfolio_routes(common_bp, ctx: CommonRouteContext) -> None:
    """포트폴리오/거래 관련 라우트를 등록한다."""
    _register_portfolio_overview_routes(common_bp, ctx)
    _register_portfolio_trade_routes(common_bp, ctx)
    _register_portfolio_history_routes(common_bp, ctx)
