#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Grade classifier 리팩토링 회귀 테스트
"""

from __future__ import annotations

from engine.grade_classifier import GradeClassifier
from engine.models import Grade, ScoreDetail, StockData, SupplyData


def _build_stock(change_pct: float, trading_value: int) -> StockData:
    return StockData(
        code="000001",
        name="테스트",
        market="KOSPI",
        close=10_000,
        change_pct=change_pct,
        trading_value=trading_value,
        volume=1_000_000,
        high_52w=12_000,
        low_52w=8_000,
    )


def _dual_buy_supply() -> SupplyData:
    return SupplyData(foreign_buy_5d=1_000_000_000, inst_buy_5d=1_000_000_000)


def test_classify_s_grade_when_all_s_conditions_met():
    classifier = GradeClassifier()
    stock = _build_stock(change_pct=10.0, trading_value=1_200_000_000_000)
    score = ScoreDetail(total=10, news=1)

    grade = classifier.classify(stock=stock, score=score, score_details={}, supply=_dual_buy_supply())
    assert grade == Grade.S


def test_classify_none_when_no_dual_buy():
    classifier = GradeClassifier()
    stock = _build_stock(change_pct=10.0, trading_value=1_200_000_000_000)
    score = ScoreDetail(total=10, news=1)
    supply = SupplyData(foreign_buy_5d=1_000_000_000, inst_buy_5d=0)

    grade = classifier.classify(stock=stock, score=score, score_details={}, supply=supply)
    assert grade is None

