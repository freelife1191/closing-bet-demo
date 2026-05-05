#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phase4 build_signal 회귀 테스트.

핵심 회귀: ai_evaluation이 Signal 객체의 top-level 필드까지 전달되어야 한다.
이전 버그에서는 score_details['ai_evaluation']에는 들어갔지만 Signal.ai_evaluation은
None으로 남아 저장 JSON에서 LLM 결과가 모두 누락됐다.
"""

from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace
from typing import Any

from engine.models import ScoreDetail, StockData
from engine.phases_phase4_helpers import build_signal


def _stock() -> StockData:
    return StockData(
        code="005930",
        name="삼성전자",
        market="KOSPI",
        sector="전기전자",
        close=80_000,
        change_pct=8.07,
        trading_value=8_358_799_527_000,
        volume=10_000_000,
    )


def _position() -> Any:
    return SimpleNamespace(
        entry_price=80_000,
        stop_price=76_000,
        target_price=88_000,
        r_value=4_000,
        position_size=1,
        quantity=10,
        r_multiplier=2.0,
    )


def _score() -> ScoreDetail:
    return ScoreDetail(total=12, news=3, volume=3, chart=2, candle=1, timing=1, supply=2)


class TestBuildSignalAiEvaluation:
    def test_ai_evaluation_propagates_to_signal(self):
        llm_result = {
            "action": "BUY",
            "confidence": 80,
            "reason": "테스트 응답: ① ② ③ ④ ⑤",
            "model": "test-model",
        }
        signal = build_signal(
            stock=_stock(),
            target_date=date.today(),
            grade="A",
            score=_score(),
            checklist={},
            score_details={"volume_ratio": 2.5, "ai_evaluation": llm_result},
            news_items=[],
            position=_position(),
            themes=[],
            ai_evaluation=llm_result,
        )
        assert signal.ai_evaluation == llm_result
        assert signal.ai_evaluation["action"] == "BUY"
        assert signal.ai_evaluation["reason"].startswith("테스트 응답")

    def test_ai_evaluation_optional_defaults_to_none(self):
        signal = build_signal(
            stock=_stock(),
            target_date=date.today(),
            grade="B",
            score=_score(),
            checklist={},
            score_details={"volume_ratio": 1.0},
            news_items=[],
            position=_position(),
            themes=[],
        )
        assert signal.ai_evaluation is None
