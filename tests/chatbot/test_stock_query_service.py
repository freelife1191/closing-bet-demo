#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stock_query_service 유틸 회귀 테스트
"""

import os
import sys


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from chatbot.stock_query_service import detect_stock_query_from_stock_map


class _FakeLogger:
    def __init__(self):
        self.events = []

    def info(self, message, *args):
        self.events.append((message, args))


def test_detect_stock_query_from_stock_map_by_name():
    logger = _FakeLogger()
    result = detect_stock_query_from_stock_map(
        message="삼성전자 어때?",
        stock_map={"삼성전자": "005930"},
        ticker_map={"005930": "삼성전자"},
        format_stock_context_fn=lambda name, ticker: f"{name}:{ticker}",
        logger=logger,
    )
    assert result == "삼성전자:005930"


def test_detect_stock_query_from_stock_map_by_ticker():
    logger = _FakeLogger()
    result = detect_stock_query_from_stock_map(
        message="005930 전망",
        stock_map={"삼성전자": "005930"},
        ticker_map={"005930": "삼성전자"},
        format_stock_context_fn=lambda name, ticker: f"{name}:{ticker}",
        logger=logger,
    )
    assert result == "삼성전자:005930"
