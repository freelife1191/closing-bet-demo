#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LLMAnalyzer.analyze_news_batch_jongga 메서드 단위 테스트."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from engine.llm_analyzer import LLMAnalyzer


def _sample_item() -> dict:
    return {
        "stock": {
            "stock_code": "005930",
            "stock_name": "삼성전자",
            "current_price": 80_000,
            "change_pct": 2.5,
            "trading_value": 1_000_000_000_000,
            "score": {"total": 11, "news": 2, "volume": 3, "chart": 2, "candle": 1, "timing": 1, "supply": 2},
            "score_details": {
                "foreign_net_buy": 5_000_000_000,
                "inst_net_buy": 3_000_000_000,
                "bonus_breakdown": {"volume": 2, "candle": 1, "limit_up": 0},
            },
        },
        "news": [{"title": "테스트 뉴스", "weight": 1.0}],
        "supply": {"foreign_buy_5d": 5_000_000_000, "inst_buy_5d": 3_000_000_000},
    }


@pytest.fixture
def analyzer():
    a = LLMAnalyzer.__new__(LLMAnalyzer)
    a.provider = "gemini"
    a._client = object()
    a._retry_strategy = None
    a._api_key_source = "test"
    a._last_loaded_key = "test"
    a._client_init_attempted = True
    a._missing_key_warned = False
    return a


class TestAnalyzeNewsBatchJongga:
    def test_uses_jongga_prompt(self, analyzer):
        captured = {}

        async def fake_execute(prompt, timeout):
            captured["prompt"] = prompt
            return '[{"name": "삼성전자", "score": 2, "action": "BUY", "confidence": 80, "reason": "테스트 reason"}]'

        with patch.object(analyzer, "_execute_llm_call", side_effect=fake_execute):
            result = asyncio.run(analyzer.analyze_news_batch_jongga([_sample_item()], market_status=None))

        assert "삼성전자" in result
        prompt = captured["prompt"]
        # jongga 프롬프트 특징 확인
        assert "종가베팅" in prompt
        # VCP를 강제로 평가하라는 지시문이 없어야 한다
        assert "VCP(변동성 수축 패턴)의 기술적 완성도를 반드시 평가에 포함" not in prompt
        assert "이 기술적 지표가 점수에 **가장 큰 영향**" not in prompt
        # closing-bet stocks_text 영역에는 "수축 비율: X" 같은 가짜 메타가 없어야 한다
        assert "수축 비율: 1.0" not in prompt
        assert "**VCP 점수:" not in prompt
        # reason 길이 강제 (전체 350자 + 섹션별 60자)
        assert "350" in prompt
        assert "60" in prompt

    def test_empty_items_returns_empty_dict(self, analyzer):
        with patch.object(analyzer, "_execute_llm_call") as mock:
            result = asyncio.run(analyzer.analyze_news_batch_jongga([], market_status=None))
        assert result == {}
        mock.assert_not_called()

    def test_results_attach_model_name(self, analyzer):
        async def fake_execute(prompt, timeout):
            return '[{"name": "삼성전자", "score": 2, "action": "BUY", "confidence": 80, "reason": "r"}]'

        with patch.object(analyzer, "_execute_llm_call", side_effect=fake_execute):
            result = asyncio.run(analyzer.analyze_news_batch_jongga([_sample_item()], market_status=None))
        assert "삼성전자" in result
        # model 키가 추가됨 (build_result_map_impl 동작)
        assert "model" in result["삼성전자"]
