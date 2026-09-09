#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Signal Tracker AI 분석 헬퍼.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pandas as pd

from engine.pandas_utils_safe import safe_confidence, safe_optional_float
from engine.screening_runtime import resolve_vcp_signals_to_show
from engine.vcp_ai_orchestration_helpers import VCP_AI_RECOMMENDATION_FIELDS


def _resolve_ai_target_limit(limit: int | None) -> int:
    if limit is None:
        return resolve_vcp_signals_to_show(default=20, minimum=1)
    try:
        return max(int(limit), 0)
    except (TypeError, ValueError):
        return resolve_vcp_signals_to_show(default=20, minimum=1)


def cap_ai_target_signals(
    signals_df: pd.DataFrame,
    limit: int | None = None,
) -> pd.DataFrame:
    """AI 분석 대상을 score 기준 상위 N개로 제한."""
    resolved_limit = _resolve_ai_target_limit(limit)
    if len(signals_df) <= resolved_limit:
        return signals_df
    if "score" not in signals_df.columns:
        return signals_df.head(resolved_limit)
    scores = pd.to_numeric(signals_df["score"], errors="coerce").fillna(0)
    top_indices = scores.nlargest(resolved_limit).index
    return signals_df.loc[top_indices]


# [VCP-011] `build_vcp_prompt` 에 실을 숫자 필드. 행에 없는 값을 0 으로 채우면 프롬프트가
# 그 0 을 사실처럼 적는다. `signals_log.csv` 에는 `foreign_1d`·`inst_1d` 열이 아예 없어서
# 「외국인 1일(오늘) 순매수: 0.0주」가 매번 지어졌고, 프롬프트는 바로 다음 줄에서 오늘의
# 수급 변화를 중요하게 보라고 지시한다. 키를 빼면 `build_vcp_prompt` 가 이미 가진 'N/A'
# 처리로 넘어간다. 재분석 경로(`app/routes/kr_market_vcp_signal_helpers.py`)가 이 목록을
# 그대로 가져다 쓴다. 사본을 두면 두 경로가 어긋나 같은 화면인데 프롬프트 입력이 달라진다.
AI_PROMPT_NUMERIC_FIELDS = (
    "score",
    "vcp_score",
    "contraction_ratio",
    "foreign_5d",
    "inst_5d",
    "foreign_1d",
    "inst_1d",
)


def build_ai_batch_payload(signals_df: pd.DataFrame) -> list[dict[str, Any]]:
    """AI 배치 분석 입력 payload를 생성.

    행에 없는 값은 키째로 뺀다. 0 을 채우면 `build_vcp_prompt` 가 그 0 을 사실처럼 적는다.
    """
    payload: list[dict[str, Any]] = []
    for row in signals_df.itertuples(index=False):
        item: dict[str, Any] = {
            "ticker": getattr(row, "ticker", None),
            "name": getattr(row, "name", None),
        }

        current_price = safe_optional_float(getattr(row, "current_price", None))
        if current_price is None:
            current_price = safe_optional_float(getattr(row, "entry_price", None))
        if current_price is not None:
            item["current_price"] = current_price

        for field in AI_PROMPT_NUMERIC_FIELDS:
            value = safe_optional_float(getattr(row, field, None))
            if value is not None:
                item[field] = value
        payload.append(item)
    return payload


_PROVIDER_PRIORITY: tuple[tuple[str, str], ...] = tuple(
    zip(("gemini", "gpt", "perplexity"), VCP_AI_RECOMMENDATION_FIELDS)
)


def _pick_recommendation(payload: Mapping[str, Any]) -> tuple[str, Mapping[str, Any] | None]:
    """우선순위(gemini→gpt→perplexity) 순으로 첫 유효 추천을 고른다."""
    for provider, key in _PROVIDER_PRIORITY:
        rec = payload.get(key)
        if isinstance(rec, Mapping):
            return provider, rec
    return "N/A", None


def apply_ai_results(
    signals_df: pd.DataFrame,
    ai_results: Mapping[str, dict[str, Any]],
) -> pd.DataFrame:
    """AI 분석 결과를 시그널 프레임에 병합.

    Provider 우선순위(gemini → gpt → perplexity)를 적용해 첫 번째 유효 추천을 선택하고,
    어느 provider가 응답했는지 ai_provider 컬럼에 기록한다.
    """
    if signals_df.empty:
        return signals_df.copy()

    result = signals_df.copy()
    if "ticker" in result.columns:
        ticker_series = result["ticker"]
    else:
        ticker_series = pd.Series([None] * len(result), index=result.index)

    actions: list[Any] = []
    confidences: list[Any] = []
    reasons: list[Any] = []
    providers: list[str] = []

    for ticker in ticker_series:
        ai_payload = ai_results.get(ticker, {}) if isinstance(ai_results, Mapping) else {}
        if not isinstance(ai_payload, Mapping):
            ai_payload = {}

        provider, rec = _pick_recommendation(ai_payload)
        if rec is None:
            actions.append("N/A")
            # [JONGGA-008] 추천이 없으면 확신도도 없다. 0 을 넣으면 이 값이 signals_log 를
            # 거쳐 화면까지 흘러가 "AI 가 0% 확신한다" 는 막대가 된다.
            confidences.append(None)
            reasons.append("분석 실패")
            providers.append("N/A")
        else:
            actions.append(rec.get("action"))
            confidences.append(safe_confidence(rec.get("confidence")))
            reasons.append(rec.get("reason"))
            providers.append(provider)

    result["ai_action"] = actions
    result["ai_confidence"] = confidences
    result["ai_reason"] = reasons
    result["ai_provider"] = providers
    return result
