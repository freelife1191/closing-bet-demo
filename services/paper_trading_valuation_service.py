#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Paper Trading Valuation Service

포트폴리오 평가 계산을 PaperTradingService 본체에서 분리한다.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable, Dict

from services.paper_trading_constants import INITIAL_CASH_KRW


def _load_holdings_and_balance(get_read_context_fn: Callable[[], Any]) -> tuple[list[dict], float, float]:
    """DB에서 보유 종목과 현금/입금 총액을 로드한다."""
    with get_read_context_fn() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                p.ticker,
                p.name,
                p.avg_price,
                p.quantity,
                p.total_cost,
                p.last_updated,
                b.cash AS cash,
                b.total_deposit AS total_deposit
            FROM balance b
            LEFT JOIN portfolio p ON 1 = 1
            WHERE b.id = 1
            """
        )
        rows = cursor.fetchall()

    if not rows:
        return [], 0, 0

    first_row = rows[0]
    cash = first_row[6] if first_row[6] is not None else 0
    total_deposit = first_row[7] if first_row[7] is not None else 0

    holdings: list[dict] = [
        {
            "ticker": row[0],
            "name": row[1],
            "avg_price": row[2],
            "quantity": row[3],
            "total_cost": row[4],
            "last_updated": row[5],
        }
        for row in rows
        if row[0] is not None
    ]

    return holdings, cash, total_deposit


def get_portfolio_valuation(
    *,
    get_read_context_fn: Callable[[], Any],
    cache_lock: Any,
    price_cache: Dict[str, int],
    wait_for_initial_price_sync_fn: Callable[[list[dict], Dict[str, int]], Dict[str, int]],
    build_valuated_holding_fn: Callable[[dict, Dict[str, int]], tuple[dict, int]],
    record_asset_history_fn: Callable[[int], None],
    last_update: datetime | None,
    logger: logging.Logger,
    record_asset_history_with_cash_fn: Callable[..., None] | None = None,
    run_db_operation_with_schema_retry_fn: Callable[[Callable[[], Any]], Any] | None = None,
) -> dict[str, Any]:
    """캐시 가격을 기준으로 포트폴리오 평가 결과를 계산한다."""
    load_holdings_fn = lambda: _load_holdings_and_balance(get_read_context_fn)
    if callable(run_db_operation_with_schema_retry_fn):
        holdings, cash, total_deposit = run_db_operation_with_schema_retry_fn(load_holdings_fn)
    else:
        holdings, cash, total_deposit = load_holdings_fn()

    updated_holdings: list[dict] = []
    total_stock_value = 0

    with cache_lock:
        current_prices = price_cache.copy()
    current_prices = wait_for_initial_price_sync_fn(holdings, current_prices)

    if not current_prices and holdings:
        logger.warning("Portfolio Valuation: Price cache is empty! Falling back to purchase price.")
    elif holdings:
        ticker = holdings[0]["ticker"]
        in_cache = ticker in current_prices
        cached_value = current_prices.get(ticker)
        logger.debug(
            f"Portfolio Valuation: Cache Size={len(current_prices)}, Holdings={len(holdings)}. "
            f"Sample ({ticker}): InCache={in_cache}, Val={cached_value}"
        )

    for holding in holdings:
        valued_holding, market_value = build_valuated_holding_fn(holding, current_prices)
        total_stock_value += market_value
        updated_holdings.append(valued_holding)

    total_asset = cash + total_stock_value
    total_principal = INITIAL_CASH_KRW + total_deposit
    total_profit = total_asset - total_principal
    total_profit_rate = (total_profit / total_principal * 100) if total_principal > 0 else 0

    try:
        if callable(record_asset_history_with_cash_fn):
            record_asset_history_with_cash_fn(
                cash=cash,
                current_stock_value=total_stock_value,
            )
        else:
            record_asset_history_fn(total_stock_value)
    except Exception as error:
        logger.error(f"Failed to record asset history on valuation: {error}")

    return {
        "holdings": updated_holdings,
        "cash": cash,
        "total_asset_value": total_asset,
        "total_stock_value": total_stock_value,
        "total_profit": int(total_profit),
        "total_profit_rate": round(total_profit_rate, 2),
        "total_principal": total_principal,
        "last_update": last_update.isoformat() if last_update else None,
    }
