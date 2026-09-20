#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VCP 백테스트가 가격 맵과 같은 종목 키를 사용하는지 확인한다."""
import pandas as pd

from services.kr_market_backtest_service import calculate_vcp_backtest_stats


def test_vcp_backtest_resolves_lowercase_and_excludes_placeholder_keys():
    signals = pd.DataFrame([
        {'ticker': '0007c0', 'signal_date': '2026-09-17', 'entry_price': 100},
        {'ticker': '000000', 'signal_date': '2026-09-17', 'entry_price': 1},
    ])
    prices = pd.DataFrame([{'ticker': '0007C0', 'date': '2026-09-18', 'high': 116, 'low': 100, 'close': 116}])
    result = calculate_vcp_backtest_stats(signals, {'0007C0': 116, '000000': 999}, prices)
    assert result['count'] == 1
    assert result['win_rate'] == 100
    assert result['avg_return'] == 15
