#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SignalTracker AI 헬퍼 리팩토링 테스트
"""

from __future__ import annotations

import pandas as pd
import engine.signal_tracker_ai_helpers as ai_helpers_module

from engine.signal_tracker_ai_helpers import (
    apply_ai_results,
    build_ai_batch_payload,
    cap_ai_target_signals,
)


def test_cap_ai_target_signals_keeps_top_scores():
    signals_df = pd.DataFrame(
        [{"ticker": f"{i:06d}", "score": i, "entry_price": 100} for i in range(25)]
    )
    capped = cap_ai_target_signals(signals_df, limit=20)

    assert len(capped) == 20
    assert int(capped["score"].min()) == 5
    assert int(capped["score"].max()) == 24


def test_cap_ai_target_signals_without_score_uses_head_fallback():
    signals_df = pd.DataFrame([{"ticker": f"{i:06d}"} for i in range(25)])
    capped = cap_ai_target_signals(signals_df, limit=20)

    assert len(capped) == 20
    assert capped.iloc[0]["ticker"] == "000000"
    assert capped.iloc[-1]["ticker"] == "000019"


def test_build_ai_batch_payload_maps_fields():
    signals_df = pd.DataFrame(
        [
            {
                "ticker": "000001",
                "name": "테스트주",
                "entry_price": 12345,
                "score": 77,
                "vcp_score": 15,
                "contraction_ratio": 0.45,
                "foreign_5d": 100,
                "inst_5d": 200,
                "foreign_1d": 0,
                "inst_1d": -25,
            }
        ]
    )

    payload = build_ai_batch_payload(signals_df)
    assert len(payload) == 1
    assert payload[0]["ticker"] == "000001"
    assert payload[0]["current_price"] == 12345
    assert payload[0]["score"] == 77
    assert payload[0]["foreign_1d"] == 0.0
    assert payload[0]["inst_1d"] == -25.0


def test_build_ai_batch_payload_omits_absent_and_unreadable_fields():
    """[VCP-011] 없는 값은 0 으로 채우지 않고 키째로 뺀다.

    이 payload 는 build_vcp_prompt 로 그대로 들어간다. 0 을 채우면 프롬프트가 그 0 을
    사실 진술로 적고, 수축 비율 0 은 「완벽한 수축」이라는 정반대의 뜻이 된다.
    """
    signals_df = pd.DataFrame(
        [
            {
                "ticker": "000001",
                "name": "테스트주",
                "entry_price": 12345,
                "score": 77,
                "contraction_ratio": float("nan"),
            }
        ]
    )

    payload = build_ai_batch_payload(signals_df)[0]

    assert payload["score"] == 77
    assert "contraction_ratio" not in payload
    assert "vcp_score" not in payload
    assert "foreign_1d" not in payload
    assert "inst_1d" not in payload


def test_build_ai_batch_payload_prefers_current_price_over_entry_price():
    """[VCP-011] 프롬프트의 「현재가」 출처를 재분석 경로와 맞춘다.

    예전에는 이 경로만 entry_price 를 현재가로 실어, 같은 화면인데 어느 경로가
    돌았느냐로 프롬프트가 본 현재가가 달랐다.
    """
    signals_df = pd.DataFrame(
        [{"ticker": "000001", "name": "A", "entry_price": 100, "current_price": 130}]
    )

    assert build_ai_batch_payload(signals_df)[0]["current_price"] == 130.0


def test_apply_ai_results_sets_fallback_when_missing():
    signals_df = pd.DataFrame(
        [
            {"ticker": "000001", "name": "A"},
            {"ticker": "000002", "name": "B"},
        ]
    )
    ai_results = {
        "000001": {
            "gemini_recommendation": {
                "action": "BUY",
                "confidence": 85,
                "reason": "추세 양호",
            }
        }
    }

    merged = apply_ai_results(signals_df, ai_results)
    row1 = merged[merged["ticker"] == "000001"].iloc[0]
    assert row1["ai_action"] == "BUY"
    assert int(row1["ai_confidence"]) == 85

    row2 = merged[merged["ticker"] == "000002"].iloc[0]
    assert row2["ai_action"] == "N/A"
    # [JONGGA-008] action 과 reason 에는 실패 표기가 들어가지만 확신도는 값 없음으로
    # 남는다. 0 을 넣으면 signals_log 를 거쳐 화면이 0% 막대를 그린다.
    assert pd.isna(row2["ai_confidence"])
    assert row2["ai_reason"] == "분석 실패"


def test_apply_ai_results_preserves_existing_columns_and_row_count():
    signals_df = pd.DataFrame(
        [
            {"ticker": "000001", "name": "A", "score": 10},
            {"ticker": "000002", "name": "B", "score": 20},
        ]
    )
    ai_results = {"000001": {"gemini_recommendation": {"action": "HOLD", "confidence": 50, "reason": "중립"}}}

    merged = apply_ai_results(signals_df, ai_results)

    assert len(merged) == 2
    assert merged["score"].tolist() == [10, 20]
    assert merged.iloc[0]["ai_action"] == "HOLD"
    assert merged.iloc[1]["ai_action"] == "N/A"


def test_cap_ai_target_signals_handles_non_numeric_scores():
    signals_df = pd.DataFrame(
        [
            {"ticker": "000001", "score": "10"},
            {"ticker": "000002", "score": "not-number"},
            {"ticker": "000003", "score": "30"},
        ]
    )

    capped = cap_ai_target_signals(signals_df, limit=2)

    assert set(capped["ticker"].tolist()) == {"000001", "000003"}


def test_cap_ai_target_signals_uses_runtime_limit_when_limit_not_provided(monkeypatch):
    signals_df = pd.DataFrame([{"ticker": f"{i:06d}", "score": i} for i in range(5)])
    monkeypatch.setattr(
        ai_helpers_module,
        "resolve_vcp_signals_to_show",
        lambda **_kwargs: 2,
    )

    capped = cap_ai_target_signals(signals_df)

    assert len(capped) == 2
    assert capped["ticker"].tolist() == ["000004", "000003"]


# ---------------------------------------------------------------------------
# 멀티 provider fallback (회귀 잠금). [VCP-043] 부터 선택은 수집·재분석과 같은
# `_extract_vcp_ai_recommendation` 하나로 하고, 읽는 곳이 없던 ai_provider 열은 쓰지 않는다.
# ---------------------------------------------------------------------------


class TestApplyAiResultsProvider:
    def _df(self, tickers):
        return pd.DataFrame([{"ticker": t, "name": t} for t in tickers])

    def test_gemini_succeeds_and_no_ai_provider_column(self):
        ai_results = {
            "000001": {
                "gemini_recommendation": {"action": "BUY", "confidence": 80, "reason": "추세 양호"}
            }
        }
        merged = apply_ai_results(self._df(["000001"]), ai_results)
        assert merged.iloc[0]["ai_action"] == "BUY"
        assert "ai_provider" not in merged.columns

    def test_falls_back_to_gpt_when_gemini_missing(self):
        ai_results = {
            "000001": {
                "gemini_recommendation": None,
                "gpt_recommendation": {"action": "HOLD", "confidence": 60, "reason": "관망 권고"},
            }
        }
        merged = apply_ai_results(self._df(["000001"]), ai_results)
        assert merged.iloc[0]["ai_action"] == "HOLD"
        assert merged.iloc[0]["ai_reason"] == "관망 권고"

    def test_skips_failed_gemini_dict_and_uses_valid_gpt(self):
        # [VCP-043] 실패 dict 도 dict 라서 예전에는 여기서 N/A 가 골라졌다
        ai_results = {
            "000001": {
                "gemini_recommendation": {"action": "N/A", "confidence": 0, "reason": "분석 실패"},
                "gpt_recommendation": {"action": "buy", "confidence": 70, "reason": "수급 개선"},
            }
        }
        merged = apply_ai_results(self._df(["000001"]), ai_results)
        assert merged.iloc[0]["ai_action"] == "BUY"
        assert int(merged.iloc[0]["ai_confidence"]) == 70
        assert merged.iloc[0]["ai_reason"] == "수급 개선"

    def test_only_failed_dicts_marks_failed_without_confidence(self):
        ai_results = {
            "000001": {
                "gemini_recommendation": {"action": "N/A", "confidence": 0, "reason": "분석 실패"},
            }
        }
        merged = apply_ai_results(self._df(["000001"]), ai_results)
        assert merged.iloc[0]["ai_action"] == "N/A"
        assert pd.isna(merged.iloc[0]["ai_confidence"])
        assert merged.iloc[0]["ai_reason"] == "분석 실패"

    def test_falls_back_to_perplexity_when_gemini_and_gpt_missing(self):
        ai_results = {
            "000001": {
                "gemini_recommendation": None,
                "gpt_recommendation": None,
                "perplexity_recommendation": {"action": "BUY", "confidence": 70, "reason": "과거 캐시 판정"},
            }
        }
        merged = apply_ai_results(self._df(["000001"]), ai_results)
        assert merged.iloc[0]["ai_action"] == "BUY"

    def test_all_providers_missing_marks_failed(self):
        ai_results = {
            "000001": {
                "gemini_recommendation": None,
                "gpt_recommendation": None,
                "perplexity_recommendation": None,
            }
        }
        merged = apply_ai_results(self._df(["000001"]), ai_results)
        assert merged.iloc[0]["ai_action"] == "N/A"
        assert merged.iloc[0]["ai_reason"] == "분석 실패"

    def test_missing_ticker_in_results_marks_failed(self):
        merged = apply_ai_results(self._df(["000001"]), {})
        assert merged.iloc[0]["ai_action"] == "N/A"

    def test_gemini_priority_over_others_when_all_present(self):
        ai_results = {
            "000001": {
                "gemini_recommendation": {"action": "BUY", "confidence": 80, "reason": "추세 양호"},
                "gpt_recommendation": {"action": "SELL", "confidence": 50, "reason": "과열"},
                "perplexity_recommendation": {"action": "HOLD", "confidence": 30, "reason": "중립"},
            }
        }
        merged = apply_ai_results(self._df(["000001"]), ai_results)
        assert merged.iloc[0]["ai_action"] == "BUY"

    def test_skips_legacy_template_reason_and_uses_valid_gpt(self):
        # 수집·재분석과 같은 문턱: 옛 템플릿 사유는 실제 판정이 아니다
        ai_results = {
            "000001": {
                "gemini_recommendation": {"action": "BUY", "confidence": 80, "reason": "VCP 패턴 및 외인 매집 추이 확인"},
                "gpt_recommendation": {"action": "HOLD", "confidence": 60, "reason": "돌파 전 관망"},
            }
        }
        merged = apply_ai_results(self._df(["000001"]), ai_results)
        assert merged.iloc[0]["ai_action"] == "HOLD"
        assert merged.iloc[0]["ai_reason"] == "돌파 전 관망"
