#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
종가베팅 전체 AI 재분석 대상 필터 회귀 테스트
"""

import os
import sys

import pytest


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from app.routes.kr_market import (
    _is_jongga_ai_analysis_completed,
    _parse_reanalyze_request_options,
    _run_jongga_news_reanalysis_batch,
)


def test_completed_when_ai_evaluation_has_valid_action_and_reason():
    signal = {
        "ai_evaluation": {"action": "BUY", "confidence": 81, "reason": "수급과 뉴스가 동시에 개선됨"},
        "score": {},
    }
    assert _is_jongga_ai_analysis_completed(signal) is True


def test_completed_when_score_llm_reason_exists_even_if_ai_reason_missing():
    signal = {
        "ai_evaluation": {"action": "HOLD", "confidence": 60},
        "score": {"llm_reason": "거래량 수축과 기관 순매수가 확인됨"},
    }
    assert _is_jongga_ai_analysis_completed(signal) is True


def test_not_completed_when_reason_is_failure_placeholder():
    signal = {
        "ai_evaluation": {"action": "N/A", "confidence": 0, "reason": "분석 실패"},
        "score": {"llm_reason": "분석 실패"},
    }
    assert _is_jongga_ai_analysis_completed(signal) is False


def test_not_completed_when_only_model_exists_without_reason():
    signal = {
        "ai_evaluation": {"model": "gemini-2.0-flash-lite"},
        "score": {},
    }
    assert _is_jongga_ai_analysis_completed(signal) is False


def test_not_completed_when_signal_has_no_ai_fields():
    signal = {"score": {}}
    assert _is_jongga_ai_analysis_completed(signal) is False


class _DummyAnalyzer:
    provider = "gemini"

    async def analyze_news_batch(self, chunk_data, market_status):
        return {
            item["stock"]["stock_name"]: {
                "action": "BUY" if item["stock"]["stock_name"] != "Beta" else "HOLD",
                "market_status": market_status,
            }
            for item in chunk_data
        }


class _DummyConfig:
    ANALYSIS_LLM_CHUNK_SIZE = 2
    LLM_CHUNK_SIZE = 3
    ANALYSIS_LLM_CONCURRENCY = 1
    LLM_CONCURRENCY = 1
    ANALYSIS_LLM_REQUEST_DELAY = 0


def test_parse_reanalyze_request_options_normalizes_scalar_target():
    tickers, force_update = _parse_reanalyze_request_options(
        {"target_tickers": " 005930 ", "force": 1}
    )

    assert tickers == ["005930"]
    assert force_update is True


def test_run_jongga_news_reanalysis_batch_merges_chunk_results():
    items = [
        {"stock": {"stock_name": "Alpha"}},
        {"stock": {"stock_name": "Beta"}},
        {"stock": {"stock_name": "Gamma"}},
    ]

    results = _run_jongga_news_reanalysis_batch(
        analyzer=_DummyAnalyzer(),
        app_config=_DummyConfig(),
        items_to_analyze=items,
        market_status={"status": "OPEN"},
    )

    assert set(results.keys()) == {"Alpha", "Beta", "Gamma"}
    assert results["Alpha"]["action"] == "BUY"
    assert results["Beta"]["action"] == "HOLD"


def test_run_jongga_news_reanalysis_batch_raises_when_no_items():
    with pytest.raises(ValueError, match="뉴스가 없어"):
        _run_jongga_news_reanalysis_batch(
            analyzer=_DummyAnalyzer(),
            app_config=_DummyConfig(),
            items_to_analyze=[],
            market_status=None,
        )
