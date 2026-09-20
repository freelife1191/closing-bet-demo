#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""정규 가격 공급자와 기존 보유 코드의 평가 연결을 보장한다."""
import pytest

from services.paper_trading_valuation_helpers import (
    build_valuated_holding,
    calculate_stock_value_from_rows,
)


@pytest.mark.parametrize('ticker,canonical', [('5930', '005930'), ('0007c0', '0007C0')])
def test_legacy_holding_uses_normalized_price_without_changing_stored_code(ticker, canonical):
    row = {'ticker': ticker, 'avg_price': 100, 'quantity': 3}
    valued, total = build_valuated_holding(row, {canonical: 120})
    assert valued['ticker'] == ticker
    assert valued['current_price'] == 120
    assert valued['is_stale'] is False
    assert total == 360
    assert calculate_stock_value_from_rows([row], {canonical: 120}) == 360


def test_canonical_price_precedes_legacy_and_invalid_key_never_uses_empty_price():
    row = {'ticker': '0007c0', 'avg_price': 100, 'quantity': 3}
    valued, total = build_valuated_holding(row, {'0007c0': 110, '0007C0': 120})
    assert valued['current_price'] == 120 and total == 360
    legacy_only, total = build_valuated_holding(row, {'0007c0': 110})
    assert legacy_only['current_price'] == 110 and total == 330
    invalid, total = build_valuated_holding({**row, 'ticker': '000000'}, {'': 999})
    assert invalid['is_stale'] is True and total == 300
