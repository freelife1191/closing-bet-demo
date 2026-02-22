#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Stock Detail Service 리팩토링 테스트
"""

from __future__ import annotations

import sys
import types

import pandas as pd

from services.kr_market_stock_detail_service import (
    _get_padded_ticker_series,
    append_investor_trend_5day,
    load_naver_stock_detail_payload,
)


def test_get_padded_ticker_series_creates_cache_column_once():
    df = pd.DataFrame({"ticker": [5930, 660]})

    first = _get_padded_ticker_series(df)
    second = _get_padded_ticker_series(df)

    assert first.tolist() == ["005930", "000660"]
    assert second.tolist() == ["005930", "000660"]
    assert "_ticker_padded" in df.columns


def test_append_investor_trend_5day_aggregates_recent_five_rows():
    trend_df = pd.DataFrame(
        [
            {"ticker": "005930", "foreign_buy": 1, "inst_buy": 10},
            {"ticker": "005930", "foreign_buy": 2, "inst_buy": 20},
            {"ticker": "005930", "foreign_buy": 3, "inst_buy": 30},
            {"ticker": "005930", "foreign_buy": 4, "inst_buy": 40},
            {"ticker": "005930", "foreign_buy": 5, "inst_buy": 50},
            {"ticker": "005930", "foreign_buy": 6, "inst_buy": 60},
        ]
    )
    payload: dict[str, object] = {}

    append_investor_trend_5day(
        payload=payload,
        ticker_padded="005930",
        load_csv_file=lambda _filename: trend_df,
        logger=type("L", (), {"warning": lambda *_a, **_k: None})(),
    )

    assert payload["investorTrend5Day"] == {"foreign": 20, "institution": 200}


def test_append_investor_trend_5day_skips_when_required_columns_missing():
    trend_df = pd.DataFrame([{"ticker": "005930"}])
    payload: dict[str, object] = {}

    append_investor_trend_5day(
        payload=payload,
        ticker_padded="005930",
        load_csv_file=lambda _filename: trend_df,
        logger=type("L", (), {"warning": lambda *_a, **_k: None})(),
    )

    assert "investorTrend5Day" not in payload


def test_load_naver_stock_detail_payload_clears_event_loop_after_run(monkeypatch):
    fake_collectors = types.ModuleType("engine.collectors")

    class _FakeCollector:
        async def get_stock_detail_info(self, _ticker):
            return {"name": "테스트"}

        async def get_financials(self, _ticker):
            return {"revenue": 1}

    fake_collectors.NaverFinanceCollector = _FakeCollector
    monkeypatch.setitem(sys.modules, "engine.collectors", fake_collectors)

    calls: list[object] = []

    import services.kr_market_stock_detail_service as stock_detail_service

    original_set_event_loop = stock_detail_service.asyncio.set_event_loop

    def _spy_set_event_loop(loop):
        calls.append(loop)
        return original_set_event_loop(loop)

    monkeypatch.setattr(stock_detail_service.asyncio, "set_event_loop", _spy_set_event_loop)

    payload = load_naver_stock_detail_payload("005930")

    assert payload is not None
    assert calls
    assert calls[-1] is None
