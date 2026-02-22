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
    fetch_prices_pykrx,
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


def test_fetch_prices_yfinance_restores_logger_level_on_failure():
    class _FailingYF:
        @staticmethod
        def download(*_args, **_kwargs):
            raise RuntimeError("network down")

    yf_logger = logging.getLogger("yfinance")
    previous = yf_logger.level
    yf_logger.setLevel(logging.WARNING)
    try:
        prices = fetch_prices_yfinance(
            yf_module=_FailingYF(),
            tickers=["005930"],
            logger=logging.getLogger(__name__),
        )
        assert prices == {}
        assert yf_logger.level == logging.WARNING
    finally:
        yf_logger.setLevel(previous)


def test_fetch_prices_pykrx_prefers_batch_api_for_requested_tickers():
    class _FakePykrxStock:
        def __init__(self):
            self.batch_calls: list[tuple[str, str | None]] = []
            self.single_calls: list[tuple[str, str, str]] = []

        def get_market_ohlcv_by_ticker(self, date, market="ALL"):
            self.batch_calls.append((str(date), str(market)))
            return pd.DataFrame(
                {"종가": [70100, 121300]},
                index=["005930", "000660"],
            )

        def get_market_ohlcv(self, _start, _end, ticker):
            self.single_calls.append((_start, _end, ticker))
            raise AssertionError("single ticker API should not be called when batch data is available")

    fake_stock = _FakePykrxStock()
    prices = fetch_prices_pykrx(
        pykrx_stock=fake_stock,
        tickers=["5930", "005930", "000660"],
        logger=logging.getLogger(__name__),
    )

    assert prices == {"005930": 70100, "000660": 121300}
    assert len(fake_stock.batch_calls) == 1
    assert fake_stock.single_calls == []


def test_fetch_prices_pykrx_uses_yesterday_batch_for_unresolved_tickers():
    class _FakePykrxStock:
        def __init__(self):
            self.batch_calls: list[str] = []

        def get_market_ohlcv_by_ticker(self, date, market="ALL"):
            del market
            date_str = str(date)
            self.batch_calls.append(date_str)
            if len(self.batch_calls) == 1:
                return pd.DataFrame({"종가": [0]}, index=["005930"])
            return pd.DataFrame({"종가": [69900]}, index=["005930"])

    fake_stock = _FakePykrxStock()
    prices = fetch_prices_pykrx(
        pykrx_stock=fake_stock,
        tickers=["005930"],
        logger=logging.getLogger(__name__),
    )

    assert prices == {"005930": 69900}
    assert len(fake_stock.batch_calls) == 2


def test_fetch_prices_pykrx_falls_back_to_single_ticker_api_when_batch_unavailable():
    class _FakePykrxStock:
        def __init__(self):
            self.single_calls: list[str] = []

        def get_market_ohlcv(self, _start, _end, ticker):
            self.single_calls.append(str(ticker))
            return pd.DataFrame({"종가": [12345]})

    fake_stock = _FakePykrxStock()
    prices = fetch_prices_pykrx(
        pykrx_stock=fake_stock,
        tickers=["5930", "005930", "000660"],
        logger=logging.getLogger(__name__),
    )

    assert prices == {"005930": 12345, "000660": 12345}
    assert fake_stock.single_calls == ["005930", "000660"]
