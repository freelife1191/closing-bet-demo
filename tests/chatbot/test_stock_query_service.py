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


def _detect(message, stock_map):
    ticker_map = {ticker: name for name, ticker in stock_map.items()}
    return detect_stock_query_from_stock_map(
        message=message,
        stock_map=stock_map,
        ticker_map=ticker_map,
        format_stock_context_fn=lambda name, ticker: f"{name}:{ticker}",
        logger=_FakeLogger(),
    )


_SHORT_NAMES = {
    "대상": "001680", "전방": "000950", "러셀": "217500", "한창": "005110",
    "남성": "004270", "동양": "001520", "TP": "007980", "DB": "012030",
    "기아": "000270", "LG": "003550",
}


def test_short_name_used_as_plain_word_is_not_a_stock_query():
    for message in [
        "VCP 분석 대상 종목 알려줘",
        "전방 산업 동향은?",
        "러셀 지수 편입 기준",
        "요즘 한창 뜨는 섹터",
        "남성 소비 트렌드",
        "동양 철학 책 추천",
        "목표가 TP 얼마",
        "DB 오류가 났어",
        "기아랑 현대차 비교",
        "현대기아 주가",
        "VCP 분석 대상 주식 알려줘",
        "한창 매수 중",
        "동양 주식 시장",
        "전방 수급",
        "대상 주가지수 흐름",
        "대상 주가 지수 흐름",
        "대상 매도 시점",
        "VCP 분석 대상 전망",
        "투자 대상 실적은?",
        "관심 대상 차트 보여줘",
        "매수  대상 어때",
        "편입 대상 전망",
    ]:
        assert _detect(message, _SHORT_NAMES) is None, message


def test_short_name_followed_by_query_signal_is_a_stock_query():
    assert _detect("대상 주가 어때?", _SHORT_NAMES) == "대상:001680"
    assert _detect("기아는 어때", _SHORT_NAMES) == "기아:000270"
    assert _detect("LG 전망", _SHORT_NAMES) == "LG:003550"
    assert _detect("기아?", _SHORT_NAMES) == "기아:000270"
    assert _detect("기아 주가는?", _SHORT_NAMES) == "기아:000270"
    assert _detect("기아 실적발표", _SHORT_NAMES) == "기아:000270"
    assert _detect("기아 배당금", _SHORT_NAMES) == "기아:000270"
    assert _detect("LG 차트", _SHORT_NAMES) == "LG:003550"
    assert _detect("요즘 기아 전망 어때?", _SHORT_NAMES) == "기아:000270"
    assert _detect("오늘 대상 주가", _SHORT_NAMES) == "대상:001680"
    assert _detect("분석 말고 기아 전망", _SHORT_NAMES) == "기아:000270"
    assert _detect("분석 대상 전망 말고 대상 주가 어때", _SHORT_NAMES) == "대상:001680"


def test_six_digit_price_in_won_is_not_a_ticker():
    stock_map = {"삼성전자": "005930", "가격겹침": "298000"}
    assert _detect("삼성전자 298000원 가면 팔까?", stock_map) == "삼성전자:005930"
    assert _detect("298000원이면 싸?", stock_map) is None
    assert _detect("298000 원이면 싸?", stock_map) is None
    assert _detect("298000 어때", stock_map) == "가격겹침:298000"
