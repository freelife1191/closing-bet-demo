#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Common Portfolio Routes
"""

from __future__ import annotations

from flask import jsonify, request

from app.routes.common_route_context import CommonRouteContext


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
        return jsonify({"status": "success", "message": "Account reset to 100M KRW"})


def _register_portfolio_trade_routes(common_bp, ctx: CommonRouteContext) -> None:
    @common_bp.route("/portfolio/buy", methods=["POST"])
    def buy_stock():
        """모의 투자 매수."""
        def _handler():
            data = request.get_json()
            ticker = data.get("ticker")
            name = data.get("name")
            price = data.get("price")
            quantity = int(data.get("quantity", 0))

            if not all([ticker, name, price, quantity]):
                return jsonify({"status": "error", "message": "Missing data"}), 400

            result = ctx.paper_trading.buy_stock(ticker, name, float(price), quantity)
            return jsonify(result)

        return _execute_portfolio_route(
            handler=_handler,
            ctx=ctx,
            error_label="Error buying stock",
            error_payload_builder=lambda error: {"status": "error", "message": str(error)},
        )

    @common_bp.route("/portfolio/sell", methods=["POST"])
    def sell_stock():
        """모의 투자 매도."""
        def _handler():
            data = request.get_json()
            ticker = data.get("ticker")
            price = data.get("price")
            quantity = int(data.get("quantity", 0))

            if not all([ticker, price, quantity]):
                return jsonify({"status": "error", "message": "Missing data"}), 400

            result = ctx.paper_trading.sell_stock(ticker, float(price), quantity)
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
            data = request.get_json()
            amount = int(data.get("amount", 0))
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
        """거래 내역 조회."""
        def _handler():
            limit = request.args.get("limit", 50, type=int)
            data = ctx.paper_trading.get_trade_history(limit)
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
            limit = request.args.get("limit", 30, type=int)
            data = ctx.paper_trading.get_asset_history(limit)
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
