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

from chatbot.stock_query_service import (
    detect_stock_query,
    detect_stock_query_from_stock_map,
    detect_stock_query_from_vcp_data,
    fallback_response,
    format_stock_info,
)


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


def test_detect_stock_query_from_vcp_data_returns_match():
    result = detect_stock_query_from_vcp_data(
        message="LG에너지솔루션 매수?",
        vcp_stocks=[{"name": "LG에너지솔루션", "ticker": "373220"}],
        format_stock_info_fn=lambda stock: f"INFO:{stock['name']}",
    )
    assert result == "INFO:LG에너지솔루션"


def test_detect_stock_query_uses_vcp_path():
    result = detect_stock_query(
        message="하이닉스",
        get_cached_data_fn=lambda: {"vcp_stocks": [{"name": "하이닉스"}]},
        detect_stock_query_from_vcp_data_fn=lambda message, vcp: (
            f"{message}:{vcp[0]['name']}"
        ),
    )
    assert result == "하이닉스:하이닉스"


def test_fallback_response_returns_recommendation_list():
    result = fallback_response(
        user_message="추천 종목 알려줘",
        vcp_data=[
            {"name": "A", "supply_demand_score": 10},
            {"name": "B", "supply_demand_score": 9},
        ],
    )
    assert "오늘의 수급 상위 종목" in result
    assert "**A**: 10점" in result


def test_fallback_response_returns_unknown_for_other_messages():
    result = fallback_response("안녕", [])
    assert result == "질문을 이해하지 못했습니다."


def test_format_stock_info_contains_key_fields():
    text = format_stock_info(
        {
            "name": "테스트",
            "ticker": "000000",
            "supply_demand_score": 11,
            "supply_demand_stage": "S",
            "foreign_5d": 100,
            "inst_5d": 200,
            "is_double_buy": True,
        }
    )
    assert "**테스트** (000000)" in text
    assert "수급 점수: 11점 (S)" in text
    assert "✅ 쌍끌이" in text
