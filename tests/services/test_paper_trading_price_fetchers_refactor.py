#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Paper Trading 가격 수집 유틸 리팩토링 테스트
"""

from __future__ import annotations

import logging

import pandas as pd

from services.paper_trading_price_fetchers import (
    fetch_prices_naver,
    fetch_prices_yfinance,
)


class _FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return dict(self._payload)


class _FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, headers=None, timeout=0):
        self.calls.append((url, headers, timeout))
        if self.responses:
            return self.responses.pop(0)
        return _FakeResponse(404, {})


def test_fetch_prices_naver_throttles_between_requests_only(monkeypatch):
    sleep_calls: list[float] = []

    def _fake_sleep(seconds: float):
        sleep_calls.append(seconds)

    monkeypatch.setattr("services.paper_trading_price_fetchers.time.sleep", _fake_sleep)

    session = _FakeSession(
        [
            _FakeResponse(200, {"closePrice": "70,100"}),
            _FakeResponse(200, {"closePrice": "121,300"}),
        ]
    )

    prices = fetch_prices_naver(
        session=session,
        tickers=["005930", "000660"],
        throttle_sec=0.2,
        logger=logging.getLogger(__name__),
    )

    assert prices == {"005930": 70100, "000660": 121300}
    assert len(session.calls) == 2
    assert sleep_calls == [0.2]


def test_fetch_prices_yfinance_returns_empty_when_module_invalid():
    prices = fetch_prices_yfinance(
        yf_module=object(),
        tickers=["005930"],
        logger=logging.getLogger(__name__),
    )

    assert prices == {}


def test_fetch_prices_yfinance_parses_multiindex_close_frame():
    class _FakeYF:
        @staticmethod
        def download(_tickers, period="1d", progress=False, threads=False):
            del period, progress, threads
            columns = pd.MultiIndex.from_tuples([("Close", "005930.KS"), ("Close", "000660.KS")])
            return pd.DataFrame([[70123.0, 121456.0]], columns=columns)

    prices = fetch_prices_yfinance(
        yf_module=_FakeYF(),
        tickers=["005930", "000660"],
        logger=logging.getLogger(__name__),
    )

    assert prices == {"005930": 70123, "000660": 121456}
