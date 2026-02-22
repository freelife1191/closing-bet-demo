#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scorer 뉴스 점수 보정 회귀 테스트
"""

import os
import sys
from datetime import datetime


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from engine.models import NewsItem, StockData
from engine.scorer import Scorer


def _build_stock(name: str, trading_value: float) -> StockData:
    return StockData(
        code="000001",
        name=name,
        market="KOSPI",
        close=100_000,
        change_pct=5.0,
        trading_value=trading_value,
        volume=1_000_000,
        high_52w=120_000,
        low_52w=70_000,
    )


def test_irrelevant_news_uses_trading_value_fallback_floor():
    """종목 무관 뉴스만 있을 때는 거래대금 기반 하한 점수를 적용한다."""
    scorer = Scorer()
    stock = _build_stock("한화솔루션", 2_000_000_000_000)  # 2조
    news = [
        NewsItem(
            title="삼성전자, 장중 19만원 돌파",
            source="SBS Biz",
            url="https://example.com/news1",
            published_at=datetime.now(),
        )
    ]

    score, _, _ = scorer.calculate(
        stock=stock,
        charts=None,
        news=news,
        supply=None,
        llm_result={"score": 1, "reason": "무관 뉴스"},
    )

    assert score.news == 3


def test_relevant_news_keeps_llm_score():
    """종목 관련 뉴스가 있으면 LLM 점수를 그대로 반영한다."""
    scorer = Scorer()
    stock = _build_stock("삼성전자", 2_000_000_000_000)  # 2조
    news = [
        NewsItem(
            title="삼성전자, HBM 생산 확대",
            source="한국경제",
            url="https://example.com/news2",
            published_at=datetime.now(),
        )
    ]

    score, _, _ = scorer.calculate(
        stock=stock,
        charts=None,
        news=news,
        supply=None,
        llm_result={"score": 1, "reason": "중립"},
    )

    assert score.news == 1
