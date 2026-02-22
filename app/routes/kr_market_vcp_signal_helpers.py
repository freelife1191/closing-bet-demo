#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market VCP 시그널 헬퍼
"""

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from app.routes.kr_market_signal_common import (
    _is_meaningful_ai_reason,
    _none_if_nan,
    _normalize_text,
    _safe_float,
    _safe_int,
    _VALID_AI_ACTIONS,
)


def _row_get(row: Any, key: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def _is_vcp_ai_analysis_failed(row: dict) -> bool:
    """
    VCP 시그널의 AI 분석 실패 여부 판별.
    - action이 BUY/SELL/HOLD가 아니면 실패
    - reason이 비어있거나 실패/placeholder 문구면 실패
    """
    if not isinstance(row, dict):
        return True

    action = _normalize_text(row.get("ai_action")).upper()
    reason = row.get("ai_reason")

    if action not in _VALID_AI_ACTIONS:
        return True

    if not _is_meaningful_ai_reason(reason):
        return True

    return False


def _build_vcp_stock_payload(row: dict) -> dict:
    """VCP 재분석 요청용 단일 종목 payload 생성."""
    return {
        "ticker": str(row.get("ticker", "")).zfill(6),
        "name": row.get("name", ""),
        "current_price": _safe_float(row.get("current_price", row.get("entry_price", 0))),
        "score": _safe_float(row.get("score", 0)),
        "vcp_score": _safe_float(row.get("vcp_score", 0)),
        "contraction_ratio": _safe_float(row.get("contraction_ratio", 0)),
        "foreign_5d": _safe_float(row.get("foreign_5d", 0)),
        "inst_5d": _safe_float(row.get("inst_5d", 0)),
        "foreign_1d": _safe_float(row.get("foreign_1d", 0)),
        "inst_1d": _safe_float(row.get("inst_1d", 0)),
    }


def _build_vcp_stock_payloads(rows: List[dict]) -> List[dict]:
    """VCP 재분석 요청용 종목 payload 목록 생성."""
    if not isinstance(rows, list):
        return []
    return [_build_vcp_stock_payload(row) for row in rows if isinstance(row, dict)]


def _extract_vcp_ai_recommendation(
    ai_results: Any,
    ticker: str,
) -> Tuple[bool, str, int, str]:
    """
    ai_results에서 ticker 대상 Gemini 추천을 추출한다.
    반환값: (is_valid, action, confidence, reason)
    """
    if not isinstance(ai_results, dict):
        return False, "N/A", 0, "분석 실패"

    ai_res = ai_results.get(ticker, {})
    if not isinstance(ai_res, dict):
        return False, "N/A", 0, "분석 실패"

    gemini = ai_res.get("gemini_recommendation")
    if not isinstance(gemini, dict):
        return False, "N/A", 0, "분석 실패"

    action = _normalize_text(gemini.get("action")).upper()
    confidence_val = _safe_int(gemini.get("confidence", 0), default=0)
    reason = _normalize_text(gemini.get("reason"))

    if action in _VALID_AI_ACTIONS and _is_meaningful_ai_reason(reason):
        return True, action, confidence_val, reason

    return False, "N/A", 0, "분석 실패"


def _apply_vcp_reanalysis_updates(
    signals_df: Any,
    failed_rows: List[Tuple[int, dict]],
    ai_results: Any,
) -> Tuple[int, int, Dict[str, dict]]:
    """
    재분석 결과를 signals_df에 반영한다.
    반환값: (updated_count, still_failed_count, updated_recommendations)
    """
    updated_count = 0
    still_failed_count = 0
    updated_recommendations: Dict[str, dict] = {}

    for idx, row in failed_rows:
        ticker = str(row.get("ticker", "")).zfill(6)
        is_valid, action, confidence_val, reason = _extract_vcp_ai_recommendation(
            ai_results,
            ticker,
        )

        signals_df.at[idx, "ai_action"] = action
        signals_df.at[idx, "ai_confidence"] = confidence_val
        signals_df.at[idx, "ai_reason"] = reason

        if is_valid:
            updated_recommendations[ticker] = {
                "action": action,
                "confidence": confidence_val,
                "reason": reason,
            }
            updated_count += 1
        else:
            still_failed_count += 1

    return updated_count, still_failed_count, updated_recommendations


def _filter_signals_dataframe_by_date(
    signals_df: Any,
    req_date: Optional[str],
    default_today: str,
) -> Tuple[Any, str]:
    """
    signals_log DataFrame를 요청 날짜 기준으로 필터링한다.
    반환값: (필터된 DataFrame, 비교 기준 today 문자열)
    """
    today = default_today
    if not isinstance(signals_df, pd.DataFrame):
        return pd.DataFrame(), today
    if signals_df.empty or "signal_date" not in signals_df.columns:
        return signals_df, today

    filtered_df = signals_df
    if req_date:
        filtered_df = filtered_df[filtered_df["signal_date"].astype(str) == req_date]
        return filtered_df, today

    latest_date = filtered_df["signal_date"].max()
    if pd.notna(latest_date):
        latest_str = str(latest_date)
        filtered_df = filtered_df[filtered_df["signal_date"].astype(str) == latest_str]
        today = latest_str

    return filtered_df, today


def _build_vcp_gemini_recommendation(row: dict) -> Optional[dict]:
    """CSV 행에서 gemini_recommendation 형태를 생성한다."""
    ai_action = _none_if_nan(_row_get(row, "ai_action"))
    ai_reason = _none_if_nan(_row_get(row, "ai_reason"))
    ai_confidence = _none_if_nan(_row_get(row, "ai_confidence"))

    if not ai_action or not ai_reason:
        return None

    return {
        "action": ai_action,
        "confidence": _safe_int(ai_confidence, default=0),
        "reason": ai_reason,
        "news_sentiment": "positive",
    }


def _build_vcp_signal_from_row(row: dict) -> Optional[dict]:
    """signals_log 단일 행을 API 응답 스키마 시그널로 변환한다."""
    score = _safe_float(_row_get(row, "score", 0), default=0.0)
    status = str(_row_get(row, "status", "OPEN"))
    if status != "OPEN":
        return None
    if score < 60:
        return None

    return {
        "ticker": str(_row_get(row, "ticker", "")).zfill(6),
        "name": _row_get(row, "name"),
        "signal_date": str(_row_get(row, "signal_date")),
        "market": _row_get(row, "market"),
        "status": _row_get(row, "status"),
        "score": score,
        "contraction_ratio": _none_if_nan(_row_get(row, "contraction_ratio")),
        "entry_price": _none_if_nan(_row_get(row, "entry_price")),
        "target_price": _none_if_nan(_row_get(row, "target_price")),
        "stop_price": _none_if_nan(_row_get(row, "stop_price")),
        "foreign_5d": _safe_int(_row_get(row, "foreign_5d", 0), default=0),
        "inst_5d": _safe_int(_row_get(row, "inst_5d", 0), default=0),
        "vcp_score": _safe_int(_row_get(row, "vcp_score", 0), default=0),
        "current_price": _none_if_nan(_row_get(row, "current_price")),
        "return_pct": _none_if_nan(_row_get(row, "return_pct")),
        "gemini_recommendation": _build_vcp_gemini_recommendation(row),
    }


def _build_vcp_signals_from_dataframe(signals_df: Any) -> List[dict]:
    """signals_log DataFrame를 VCP 시그널 리스트로 변환한다."""
    if not isinstance(signals_df, pd.DataFrame) or signals_df.empty:
        return []

    signals: List[dict] = []
    for row in signals_df.itertuples(index=False):
        signal = _build_vcp_signal_from_row(row)
        if signal:
            signals.append(signal)
    return signals


def _sort_and_limit_vcp_signals(signals: List[dict], limit: int = 20) -> List[dict]:
    """점수 내림차순 정렬 후 상위 N개를 반환한다."""
    if not isinstance(signals, list):
        return []
    sorted_signals = sorted(signals, key=lambda x: x.get("score", 0), reverse=True)
    return sorted_signals[: max(limit, 0)]


def _build_ai_data_map(ai_payload: Any) -> Dict[str, dict]:
    """AI payload(signals 배열)를 ticker 기준 맵으로 변환한다."""
    ai_data_map: Dict[str, dict] = {}
    if not isinstance(ai_payload, dict):
        return ai_data_map

    for item in ai_payload.get("signals", []):
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker", "")).zfill(6)
        if ticker and ticker != "000000":
            ai_data_map[ticker] = item
    return ai_data_map


def _merge_legacy_ai_fields_into_map(ai_data_map: Dict[str, dict], legacy_payload: Any) -> None:
    """legacy AI payload의 누락 필드를 ai_data_map에 보강한다."""
    if not isinstance(ai_data_map, dict) or not isinstance(legacy_payload, dict):
        return

    for item in legacy_payload.get("signals", []):
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker", "")).zfill(6)
        if ticker not in ai_data_map:
            continue

        current = ai_data_map[ticker]
        if (
            not current.get("perplexity_recommendation")
            and item.get("perplexity_recommendation")
        ):
            current["perplexity_recommendation"] = item["perplexity_recommendation"]
        if not current.get("gemini_recommendation") and item.get("gemini_recommendation"):
            current["gemini_recommendation"] = item["gemini_recommendation"]


def _merge_ai_data_into_vcp_signals(signals: List[dict], ai_data_map: Dict[str, dict]) -> int:
    """VCP 시그널 리스트에 AI 추천/뉴스 필드를 합친다."""
    if not isinstance(signals, list) or not isinstance(ai_data_map, dict):
        return 0

    merged_count = 0
    for signal in signals:
        if not isinstance(signal, dict):
            continue
        ticker = signal.get("ticker")
        if ticker not in ai_data_map:
            continue
        ai_item = ai_data_map[ticker]
        signal["gemini_recommendation"] = ai_item.get("gemini_recommendation")
        signal["gpt_recommendation"] = ai_item.get("gpt_recommendation")
        signal["perplexity_recommendation"] = ai_item.get("perplexity_recommendation")
        if "news" in ai_item and not signal.get("news"):
            signal["news"] = ai_item["news"]
        merged_count += 1
    return merged_count
