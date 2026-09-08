#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Common Portfolio Routes
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from flask import jsonify, make_response, request

from app.routes.common_route_context import CommonRouteContext
from services.identity_helpers import verify_identity_header
from services.paper_trading_constants import (
    DEFAULT_ASSET_HISTORY_LIMIT,
    DEFAULT_TRADE_HISTORY_LIMIT,
    INITIAL_CASH_KRW,
    MAX_ASSET_HISTORY_LIMIT,
    MAX_HISTORY_LIMIT,
)


def _require_portfolio_owner(handler: Callable[..., Any]) -> Callable[..., Any]:
    """검증된 로그인 신원만 계정 연산에 전달한다. 익명은 DB 초기화 전 거부한다."""
    @wraps(handler)
    def authenticated_handler(*args: Any, **kwargs: Any) -> Any:
        owner_id = verify_identity_header(
            request.headers.get("X-Auth-Identity"),
            method=request.method,
            path=request.path,
        )
        if owner_id is None:
            response = make_response(jsonify(
                status="error", message="모의투자는 로그인 후 사용할 수 있습니다."
            ), 401)
        else:
            response = make_response(handler(*args, owner_id=owner_id, **kwargs))
        response.headers["Cache-Control"] = "private, no-store"
        response.vary.add("Cookie")
        response.vary.add("X-Auth-Identity")
        return response

    return authenticated_handler


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
    @_require_portfolio_owner
    def get_portfolio_data(owner_id: str):
        """포트폴리오 데이터 (Fast - Cached)."""
        def _handler():
            ctx.paper_trading.start_background_sync()
            data = ctx.paper_trading.get_portfolio_valuation(owner_id=owner_id)
            return jsonify(data)

        return _execute_portfolio_route(
            handler=_handler,
            ctx=ctx,
            error_label="Error fetching portfolio",
            error_payload_builder=lambda error: {"error": str(error)},
        )

    @common_bp.route("/portfolio/reset", methods=["POST"])
    @_require_portfolio_owner
    def reset_portfolio(owner_id: str):
        """모의 투자 초기화."""
        if not ctx.paper_trading.reset_account(owner_id=owner_id):
            ctx.logger.error("Failed to reset the requested paper trading account")
            return jsonify(status="error", message="계정 초기화에 실패했습니다."), 500
        return jsonify(
            {
                "status": "success",
                "message": f"Account reset to {int(INITIAL_CASH_KRW):,} KRW",
            }
        )


def _register_portfolio_trade_routes(common_bp, ctx: CommonRouteContext) -> None:
    @common_bp.route("/portfolio/buy", methods=["POST"])
    @_require_portfolio_owner
    def buy_stock(owner_id: str):
        """모의 투자 매수."""
        def _handler():
            data = request.get_json(silent=True) or {}
            ticker = data.get("ticker")
            name = data.get("name")
            price = _parse_positive_float(data.get("price"), default=0.0)
            quantity = _parse_positive_int(data.get("quantity", 0), default=0)

            if not all([ticker, name, price, quantity]):
                return jsonify({"status": "error", "message": "Missing data"}), 400

            result = ctx.paper_trading.buy_stock(ticker, name, price, quantity, owner_id=owner_id)
            return jsonify(result)

        return _execute_portfolio_route(
            handler=_handler,
            ctx=ctx,
            error_label="Error buying stock",
            error_payload_builder=lambda error: {"status": "error", "message": str(error)},
        )

    @common_bp.route("/portfolio/buy/bulk", methods=["POST"])
    @_require_portfolio_owner
    def buy_stocks_bulk(owner_id: str):
        """모의 투자 일괄 매수."""
        def _handler():
            data = request.get_json(silent=True) or {}
            orders = data.get("orders")
            if not isinstance(orders, list) or not orders:
                return jsonify({"status": "error", "message": "Missing orders"}), 400

            result = ctx.paper_trading.buy_stocks_bulk(orders, owner_id=owner_id)
            return jsonify(result)

        return _execute_portfolio_route(
            handler=_handler,
            ctx=ctx,
            error_label="Error bulk buying stocks",
            error_payload_builder=lambda error: {"status": "error", "message": str(error)},
        )

    @common_bp.route("/portfolio/sell", methods=["POST"])
    @_require_portfolio_owner
    def sell_stock(owner_id: str):
        """모의 투자 매도."""
        def _handler():
            data = request.get_json(silent=True) or {}
            ticker = data.get("ticker")
            price = _parse_positive_float(data.get("price"), default=0.0)
            quantity = _parse_positive_int(data.get("quantity", 0), default=0)

            if not all([ticker, price, quantity]):
                return jsonify({"status": "error", "message": "Missing data"}), 400

            result = ctx.paper_trading.sell_stock(ticker, price, quantity, owner_id=owner_id)
            return jsonify(result)

        return _execute_portfolio_route(
            handler=_handler,
            ctx=ctx,
            error_label="Error selling stock",
            error_payload_builder=lambda error: {"status": "error", "message": str(error)},
        )

    @common_bp.route("/portfolio/deposit", methods=["POST"])
    @_require_portfolio_owner
    def deposit_cash(owner_id: str):
        """예수금 충전."""
        def _handler():
            data = request.get_json(silent=True) or {}
            amount = _parse_positive_int(data.get("amount", 0), default=0)
            result = ctx.paper_trading.deposit_cash(amount, owner_id=owner_id)
            return jsonify(result)

        return _execute_portfolio_route(
            handler=_handler,
            ctx=ctx,
            error_label="Error depositing cash",
            error_payload_builder=lambda error: {"status": "error", "message": str(error)},
        )


def _register_portfolio_history_routes(common_bp, ctx: CommonRouteContext) -> None:
    @common_bp.route("/portfolio/history")
    @_require_portfolio_owner
    def get_trade_history(owner_id: str):
        """거래 내역 조회. ticker 쿼리 파라미터로 종목별 필터링 가능."""
        def _handler():
            limit = _parse_history_limit(
                request.args.get("limit", DEFAULT_TRADE_HISTORY_LIMIT),
                default=DEFAULT_TRADE_HISTORY_LIMIT,
            )
            ticker_param = request.args.get("ticker")
            ticker_filter = ticker_param.strip() if ticker_param else None
            data = ctx.paper_trading.get_trade_history(limit, ticker=ticker_filter, owner_id=owner_id)
            return jsonify(data)

        return _execute_portfolio_route(
            handler=_handler,
            ctx=ctx,
            error_label="Error getting trade history",
            error_payload_builder=lambda error: {"error": str(error)},
        )

    @common_bp.route("/portfolio/history/asset")
    @_require_portfolio_owner
    def get_asset_history(owner_id: str):
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
            data = ctx.paper_trading.get_asset_history(limit, days=days_param, owner_id=owner_id)
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
