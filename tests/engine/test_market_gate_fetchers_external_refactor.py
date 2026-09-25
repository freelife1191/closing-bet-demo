#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Market Gate 섹터 ETF 등락률 수집 회귀 테스트
"""

from __future__ import annotations

import logging
import sys
import types

import pandas as pd

from engine.market_gate_fetchers_external import get_sector_data


def test_get_sector_data_keeps_failed_sectors_as_missing(monkeypatch):
    # [INFRA-105] 조회 실패·빈 결과·한 줄 결과는 0.0 이 아니라 결측이다. 0 으로 채우면 급락 감점이 희석된다
    frames = {
        "OK": pd.DataFrame([{"종가": 100.0, "등락률": -3.456}]),
        "EMPTY": pd.DataFrame(),
        "ONE": pd.DataFrame([{"종가": 100.0}]),
    }

    class _FakeStock:
        @staticmethod
        def get_market_ohlcv_by_date(_start, _end, ticker):
            if ticker == "FAIL":
                raise KeyError("KRX response broken")
            return frames[ticker]

    fake_pykrx = types.ModuleType("pykrx")
    fake_pykrx.stock = _FakeStock
    monkeypatch.setitem(sys.modules, "pykrx", fake_pykrx)

    result = get_sector_data(
        sectors={"정상": "OK", "실패": "FAIL", "빈결과": "EMPTY", "한줄": "ONE"},
        target_date=None,
        global_data=None,
        logger=logging.getLogger("test"),
    )

    assert result == {"정상": -3.46, "실패": None, "빈결과": None, "한줄": None}
