#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LLMAnalyzer batch 결과의 품질 모니터링 로깅 검증."""

from __future__ import annotations

import logging
from typing import Dict

import pytest

from engine.llm_analyzer import LLMAnalyzer


def _result(action: str, reason: str = "x" * 300) -> Dict:
    return {"score": 2, "action": action, "confidence": 80, "reason": reason, "model": "gemini-test"}


class TestActionDistributionLogging:
    def test_low_buy_ratio_emits_warning(self, caplog):
        results = {
            "A": _result("HOLD"),
            "B": _result("HOLD"),
            "C": _result("HOLD"),
            "D": _result("SELL"),
            "E": _result("HOLD"),
        }
        with caplog.at_level(logging.WARNING, logger="engine.llm_analyzer"):
            LLMAnalyzer._log_jongga_action_distribution(results)
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert any("BUY 비율" in r.getMessage() for r in warnings)

    def test_healthy_buy_ratio_no_warning(self, caplog):
        results = {
            "A": _result("BUY"),
            "B": _result("BUY"),
            "C": _result("HOLD"),
            "D": _result("HOLD"),
            "E": _result("BUY"),
        }
        with caplog.at_level(logging.WARNING, logger="engine.llm_analyzer"):
            LLMAnalyzer._log_jongga_action_distribution(results)
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING and "BUY 비율" in r.getMessage()]
        assert warnings == []

    def test_small_sample_skips_warning(self, caplog):
        """5건 미만이면 통계적으로 의미 없으므로 경고 안 띄움."""
        results = {"A": _result("HOLD"), "B": _result("HOLD")}
        with caplog.at_level(logging.WARNING, logger="engine.llm_analyzer"):
            LLMAnalyzer._log_jongga_action_distribution(results)
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING and "BUY 비율" in r.getMessage()]
        assert warnings == []

    def test_empty_results_safe(self, caplog):
        with caplog.at_level(logging.WARNING, logger="engine.llm_analyzer"):
            LLMAnalyzer._log_jongga_action_distribution({})
        # no exception, no warning
        assert all("BUY 비율" not in r.getMessage() for r in caplog.records)

    def test_short_reason_emits_warning(self, caplog):
        """reason이 250자 미만인 비율이 높으면 경고."""
        results = {
            f"S{i}": _result("HOLD", reason="짧음")
            for i in range(6)
        }
        with caplog.at_level(logging.WARNING, logger="engine.llm_analyzer"):
            LLMAnalyzer._log_jongga_action_distribution(results)
        msgs = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
        assert any("reason" in m.lower() and ("짧" in m or "250" in m) for m in msgs)
