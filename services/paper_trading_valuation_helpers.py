#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PaperTrading 평가/히스토리 계산 헬퍼.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict


def build_valuated_holding(
    holding: dict,
    current_prices: Dict[str, int],
) -> tuple[dict, int]:
    """단일 보유 종목 평가값을 계산한다."""
    ticker = holding["ticker"]
    avg_price = holding["avg_price"]
    quantity = holding["quantity"]

    is_stale = False
    if ticker in current_prices:
        current_price = current_prices[ticker]
    else:
        current_price = avg_price
        is_stale = True

    market_value = int(current_price * quantity)
    profit_loss = market_value - (avg_price * quantity)
    profit_rate = ((current_price - avg_price) / avg_price * 100) if avg_price > 0 else 0

    holding_dict = dict(holding)
    holding_dict["current_price"] = current_price
    holding_dict["market_value"] = market_value
    holding_dict["profit_loss"] = int(profit_loss)
    holding_dict["profit_rate"] = round(profit_rate, 2)
    holding_dict["is_stale"] = is_stale
    return holding_dict, market_value


def calculate_stock_value_from_rows(
    portfolio_rows: list[dict],
    current_prices: Dict[str, int],
) -> int:
    """포트폴리오 행 기준 현재 주식 평가금액 합계를 계산한다."""
    current_stock_val = 0
    for row in portfolio_rows:
        qty = row["quantity"]
        price = current_prices.get(row["ticker"], row["avg_price"])
        current_stock_val += qty * price
    return current_stock_val


def build_dummy_asset_history(
    *,
    current_total: float,
    current_cash: float,
    current_stock_val: float,
) -> list[dict]:
    """차트 최소 포인트 보장을 위한 더미 히스토리 생성."""
    today = datetime.now()
    dummy_data = []
    for i in range(4, -1, -1):
        day = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        dummy_data.append(
            {
                "date": day,
                "total_asset": current_total,
                "cash": current_cash,
                "stock_value": current_stock_val,
            }
        )
    return dummy_data

