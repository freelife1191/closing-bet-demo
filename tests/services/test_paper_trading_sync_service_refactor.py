#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Paper Trading 동기화 서비스 리팩토링 테스트
"""

from __future__ import annotations

import logging

from services.paper_trading_sync_service import refresh_price_cache_once


def test_refresh_price_cache_once_skips_unavailable_providers():
    calls: list[str] = []

    def _fetch_toss(_session, _tickers):
        calls.append("toss")
        return {}

    def _fetch_naver(_session, _tickers):
        calls.append("naver")
        return {}

    def _fetch_yf(_yf_module, _tickers):
        calls.append("yf")
        return {"005930": 70000}

    def _fetch_pykrx(_stock, _tickers):
        calls.append("pykrx")
        return {"005930": 70000}

    resolved, sleep_seconds = refresh_price_cache_once(
        tickers=["005930"],
        session=object(),
        yf_module=None,
        pykrx_stock=None,
        fetch_prices_toss_fn=_fetch_toss,
        fetch_prices_naver_fn=_fetch_naver,
        fetch_prices_yfinance_fn=_fetch_yf,
        fetch_prices_pykrx_fn=_fetch_pykrx,
        update_interval_sec=60,
        empty_portfolio_sleep_sec=10,
        logger=logging.getLogger(__name__),
    )

    assert resolved == {}
    assert sleep_seconds == 60
    assert calls == ["toss", "naver"]


def test_refresh_price_cache_once_fast_path_uses_normalized_unique_tickers():
    captured: dict[str, list[str]] = {}

    def _fetch_toss(_session, tickers):
        captured["tickers"] = list(tickers)
        return {"005930": 71000}

    resolved, _ = refresh_price_cache_once(
        tickers=["005930", "000660", "005930"],
        session=object(),
        yf_module=None,
        pykrx_stock=None,
        fetch_prices_toss_fn=_fetch_toss,
        fetch_prices_naver_fn=lambda *_args: {},
        fetch_prices_yfinance_fn=lambda *_args: {},
        fetch_prices_pykrx_fn=lambda *_args: {},
        update_interval_sec=60,
        empty_portfolio_sleep_sec=10,
        logger=logging.getLogger(__name__),
    )

    assert captured["tickers"] == ["005930", "000660"]
    assert resolved == {"005930": 71000}


def test_refresh_price_cache_once_logs_actual_next_provider_name():
    class _FakeLogger:
        def __init__(self):
            self.messages: list[str] = []

        def info(self, message: str):
            self.messages.append(str(message))

    fake_logger = _FakeLogger()

    resolved, _ = refresh_price_cache_once(
        tickers=["005930"],
        session=object(),
        yf_module=None,
        pykrx_stock=object(),
        fetch_prices_toss_fn=lambda *_args: {},
        fetch_prices_naver_fn=lambda *_args: {},
        fetch_prices_yfinance_fn=lambda *_args: {},
        fetch_prices_pykrx_fn=lambda *_args: {"005930": 70000},
        update_interval_sec=60,
        empty_portfolio_sleep_sec=10,
        logger=fake_logger,  # type: ignore[arg-type]
    )

    assert resolved == {"005930": 70000}
    assert any("Trying pykrx" in msg for msg in fake_logger.messages)
