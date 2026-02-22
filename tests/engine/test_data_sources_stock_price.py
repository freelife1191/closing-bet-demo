#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
data_sources.fetch_stock_price 회귀 테스트
"""

import engine.data_sources as data_sources


def test_fetch_stock_price_returns_toss_payload_first(monkeypatch):
    calls = []

    def fake_toss(ticker):
        calls.append(("toss", ticker))
        return {"price": 70000, "change_pct": 1.1, "prev_close": 69200, "volume": 10, "source": "toss"}

    def fake_naver(ticker):
        calls.append(("naver", ticker))
        return {"source": "naver"}

    def fake_yf(ticker):
        calls.append(("yf", ticker))
        return {"source": "yfinance"}

    monkeypatch.setattr(data_sources, "_fetch_stock_price_from_toss", fake_toss)
    monkeypatch.setattr(data_sources, "_fetch_stock_price_from_naver", fake_naver)
    monkeypatch.setattr(data_sources, "_fetch_stock_price_from_yfinance", fake_yf)

    result = data_sources.fetch_stock_price("5930")

    assert result["source"] == "toss"
    assert calls == [("toss", "005930")]


def test_fetch_stock_price_falls_back_to_naver(monkeypatch):
    calls = []

    def fake_toss(ticker):
        calls.append(("toss", ticker))
        return None

    def fake_naver(ticker):
        calls.append(("naver", ticker))
        return {"price": 70100, "change_pct": 0.2, "prev_close": 69900, "volume": 11, "source": "naver"}

    def fake_yf(ticker):
        calls.append(("yf", ticker))
        return {"source": "yfinance"}

    monkeypatch.setattr(data_sources, "_fetch_stock_price_from_toss", fake_toss)
    monkeypatch.setattr(data_sources, "_fetch_stock_price_from_naver", fake_naver)
    monkeypatch.setattr(data_sources, "_fetch_stock_price_from_yfinance", fake_yf)

    result = data_sources.fetch_stock_price("005930")

    assert result["source"] == "naver"
    assert calls == [("toss", "005930"), ("naver", "005930")]


def test_fetch_stock_price_returns_none_when_all_providers_fail(monkeypatch):
    monkeypatch.setattr(data_sources, "_fetch_stock_price_from_toss", lambda _ticker: None)
    monkeypatch.setattr(data_sources, "_fetch_stock_price_from_naver", lambda _ticker: None)
    monkeypatch.setattr(data_sources, "_fetch_stock_price_from_yfinance", lambda _ticker: None)

    assert data_sources.fetch_stock_price("005930") is None
