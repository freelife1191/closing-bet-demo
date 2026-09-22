#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[CHAT-032] 종목 질의 문맥이 실제 종목 맵에서 나오는지 확인한다.
"""

from chatbot.core_data_access_mixin import CoreDataAccessMixin


class _Bot(CoreDataAccessMixin):
    stock_map = {"삼성전자": "005930", "삼성전자우": "005935", "레이": "228670", "기아": "000270"}
    ticker_map = {"005930": "삼성전자", "005935": "삼성전자우", "228670": "레이", "000270": "기아"}

    def _format_stock_context(self, name: str, ticker: str) -> str:
        return f"CTX:{name}:{ticker}"


def test_stock_query_context_comes_from_the_stock_map():
    bot = _Bot()

    assert bot._detect_stock_query("삼성전자 어때?") == "CTX:삼성전자:005930"
    # VCP 상담 모드는 선택 종목을 「[종목명(티커)] 」 접두로 붙여 보낸다.
    assert bot._detect_stock_query("[삼성전자우(005935)] 전망은?") == "CTX:삼성전자우:005935"
    assert bot._detect_stock_query("오늘 뭐 살까?") is None
    # 종목 맵에 없는 티커는 무시하고 종목명으로 찾는다.
    assert bot._detect_stock_query("[삼성전자(999999)] 전망은?") == "CTX:삼성전자:005930"
    assert bot._detect_stock_query("005930은 어때?") == "CTX:삼성전자:005930"


def test_short_stock_names_match_only_as_whole_words():
    bot = _Bot()

    assert bot._detect_stock_query("데이트레이딩 전략 알려줘") is None
    assert bot._detect_stock_query("레이더에 걸린 종목") is None
    assert bot._detect_stock_query("기아 어때?") == "CTX:기아:000270"
    assert bot._detect_stock_query("기아는 어때?") == "CTX:기아:000270"
