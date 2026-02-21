#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market 라우트 헬퍼 모듈

판별/등급 재산정 로직을 분리해 라우트 파일 결합도를 낮춘다.
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


_VALID_AI_ACTIONS = {"BUY", "SELL", "HOLD"}
_INVALID_AI_REASONS = {
    "",
    "-",
    "n/a",
    "na",
    "none",
    "null",
    "분석 실패",
    "분석 대기중",
    "분석 대기 중",
    "분석중",
    "분석 중",
    "no analysis available.",
    "no analysis available",
    "analysis failed",
    "failed",
}

_JONGGA_GRADE_PRIORITY = {"S": 3, "A": 2, "B": 1}


def _normalize_text(value: Any) -> str:
    """문자열 정규화 (None-safe)."""
    if value is None:
        return ""
    return str(value).strip()


def _is_meaningful_ai_reason(reason: Any) -> bool:
    """AI 분석 사유 텍스트가 실질적인 내용인지 판별."""
    reason_text = _normalize_text(reason)
    if not reason_text:
        return False
    return reason_text.lower() not in _INVALID_AI_REASONS


def _is_jongga_ai_analysis_completed(signal: dict) -> bool:
    """
    종가베팅 시그널의 AI 분석 완료 여부 판별.
    - 의미 있는 reason이 있어야 완료로 간주
    - action이 존재하면 BUY/SELL/HOLD 중 하나여야 완료로 간주
    """
    if not isinstance(signal, dict):
        return False

    ai_evaluation = signal.get("ai_evaluation")
    score = signal.get("score") if isinstance(signal.get("score"), dict) else {}

    ai_reason = ai_evaluation.get("reason") if isinstance(ai_evaluation, dict) else None
    llm_reason = score.get("llm_reason")

    if _is_meaningful_ai_reason(ai_reason):
        candidate_reason = ai_reason
    else:
        candidate_reason = llm_reason

    if not _is_meaningful_ai_reason(candidate_reason):
        return False

    if isinstance(ai_evaluation, dict):
        action = _normalize_text(ai_evaluation.get("action")).upper()
        if action and action not in _VALID_AI_ACTIONS:
            return False

    return True


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


def _recalculate_jongga_grade(signal: dict) -> tuple[str, bool]:
    """종가베팅 단일 시그널 등급을 현재 기준으로 재산정."""
    try:
        tv = float(signal.get("trading_value", 0) or 0)
        change_pct = float(signal.get("change_pct", 0) or 0)
        score = signal.get("score") or {}
        score_total = int((score.get("total") if isinstance(score, dict) else score) or 0)
        score_details = signal.get("score_details") or {}
        foreign_net_buy = float(score_details.get("foreign_net_buy", 0) or 0)
        inst_net_buy = float(score_details.get("inst_net_buy", 0) or 0)
        has_dual_buy = foreign_net_buy > 0 and inst_net_buy > 0
    except Exception:
        return "D", False

    prev_grade = str(signal.get("grade", "")).strip().upper()
    new_grade = "D"
    if (
        tv >= 1_000_000_000_000
        and score_total >= 10
        and change_pct >= 3.0
        and has_dual_buy
    ):
        new_grade = "S"
    elif (
        tv >= 500_000_000_000
        and score_total >= 8
        and change_pct >= 3.0
        and has_dual_buy
    ):
        new_grade = "A"
    elif (
        tv >= 100_000_000_000
        and score_total >= 6
        and change_pct >= 3.0
        and has_dual_buy
    ):
        new_grade = "B"

    if prev_grade != new_grade:
        signal["grade"] = new_grade
        return new_grade, True

    return new_grade, False


def _recalculate_jongga_grades(data: dict) -> bool:
    """종가베팅 signals grade + by_grade 동기화."""
    if not data or "signals" not in data:
        return False

    signals = data.get("signals", [])
    if not isinstance(signals, list):
        return False

    changed = False
    grade_count = {"S": 0, "A": 0, "B": 0, "C": 0, "D": 0}

    for sig in signals:
        if not isinstance(sig, dict):
            continue
        _, did_change = _recalculate_jongga_grade(sig)
        changed = changed or did_change
        grade = str(sig.get("grade", "D")).strip().upper()
        if grade not in grade_count:
            grade_count[grade] = 0
        grade_count[grade] += 1

    prev_by_grade = data.get("by_grade")
    new_by_grade = {"S": 0, "A": 0, "B": 0, "C": 0, "D": 0}
    if isinstance(prev_by_grade, dict):
        for grade_key in new_by_grade:
            if grade_key in prev_by_grade:
                value = prev_by_grade[grade_key]
                if isinstance(value, (int, float)):
                    new_by_grade[grade_key] = int(value)
                else:
                    new_by_grade[grade_key] = 0

    for grade_key, count in grade_count.items():
        if grade_key in new_by_grade:
            new_by_grade[grade_key] = count
        elif count > 0:
            new_by_grade[grade_key] = count

    if data.get("by_grade") != new_by_grade:
        data["by_grade"] = new_by_grade
        changed = True

    return changed


def _jongga_sort_key(signal: dict) -> tuple[int, float]:
    """종가베팅 시그널 정렬 키: Grade(S>A>B) 우선, 이후 점수 내림차순."""
    grade_value = _JONGGA_GRADE_PRIORITY.get(
        str(signal.get("grade", "")).strip().upper(),
        0,
    )
    raw_score = signal.get("score", 0)
    if isinstance(raw_score, dict):
        score_value = raw_score.get("total", 0)
    else:
        score_value = raw_score
    try:
        numeric_score = float(score_value or 0)
    except Exception:
        numeric_score = 0
    return grade_value, numeric_score


def _sort_jongga_signals(signals: List[dict]) -> None:
    """종가베팅 시그널 리스트를 규칙에 맞춰 정렬한다."""
    if not isinstance(signals, list):
        return
    signals.sort(key=_jongga_sort_key, reverse=True)


def _apply_latest_prices_to_jongga_signals(
    signals: List[dict],
    latest_price_map: Dict[str, float],
) -> int:
    """
    종가베팅 시그널에 최신가를 반영하고 수익률(return_pct)을 재계산한다.
    반환값은 가격 반영된 시그널 수.
    """
    if not isinstance(signals, list) or not isinstance(latest_price_map, dict):
        return 0

    updated_count = 0
    for signal in signals:
        if not isinstance(signal, dict):
            continue

        raw_code = signal.get("code") or signal.get("ticker") or signal.get("stock_code")
        ticker = str(raw_code).strip().zfill(6) if raw_code else ""
        if not ticker or ticker == "000000":
            continue
        if ticker not in latest_price_map:
            continue

        real_price = latest_price_map[ticker]
        signal["current_price"] = real_price

        entry_price = signal.get("entry_price") or signal.get("close")
        try:
            entry_price = float(entry_price)
        except Exception:
            entry_price = 0

        if entry_price > 0:
            return_pct = ((real_price - entry_price) / entry_price) * 100
            signal["return_pct"] = round(return_pct, 2)

        updated_count += 1

    return updated_count


def _normalize_jongga_signal_for_frontend(signal: dict) -> None:
    """
    종가베팅 시그널을 프론트엔드 기대 스키마로 정규화한다.
    (in-place)
    """
    if not isinstance(signal, dict):
        return

    if "stock_code" not in signal:
        signal["stock_code"] = str(signal.get("ticker", signal.get("code", ""))).zfill(6)
    if "stock_name" not in signal:
        signal["stock_name"] = signal.get("name", "")

    if "change_pct" not in signal and "return_pct" in signal:
        signal["change_pct"] = signal["return_pct"]
    elif "change_pct" not in signal:
        entry = signal.get("entry_price", 0)
        current = signal.get("current_price", 0)
        try:
            entry_float = float(entry or 0)
            current_float = float(current or 0)
        except Exception:
            entry_float = 0
            current_float = 0
        if entry_float > 0 and current_float:
            signal["change_pct"] = round(((current_float - entry_float) / entry_float) * 100, 2)
        else:
            signal["change_pct"] = 0

    raw_score = signal.get("score", 0)
    if not isinstance(raw_score, dict):
        try:
            score_int = int(float(raw_score or 0))
        except Exception:
            score_int = 0
        signal["score"] = {
            "total": score_int,
            "base_score": score_int,
            "bonus_score": 0,
        }

    if "checklist" not in signal:
        signal["checklist"] = {
            "has_news": False,
            "volume_surge": False,
            "supply_demand": signal.get("foreign_5d", 0) > 0 or signal.get("inst_5d", 0) > 0,
        }

    entry = signal.get("entry_price", 0)
    try:
        entry_float = float(entry or 0)
    except Exception:
        entry_float = 0
    if not signal.get("target_price") and entry_float > 0:
        signal["target_price"] = round(entry_float * 1.09)
    if not signal.get("stop_price") and entry_float > 0:
        signal["stop_price"] = round(entry_float * 0.95)

    if "ai_evaluation" not in signal and signal.get("ai_action"):
        signal["ai_evaluation"] = {
            "action": signal.get("ai_action", "HOLD"),
            "confidence": signal.get("ai_confidence", 0),
            "reason": signal.get("ai_reason", ""),
            "model": "gemini",
        }


def _normalize_jongga_signals_for_frontend(signals: List[dict]) -> None:
    """종가베팅 시그널 리스트를 프론트엔드 스키마로 정규화한다."""
    if not isinstance(signals, list):
        return
    for signal in signals:
        _normalize_jongga_signal_for_frontend(signal)


def _safe_float(value: Any, default: float = 0.0) -> float:
    """숫자 변환 실패 시 기본값을 반환한다."""
    try:
        return float(value or 0)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    """정수 변환 실패 시 기본값을 반환한다."""
    try:
        return int(float(value or 0))
    except Exception:
        return default


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


def _select_signals_for_gemini_reanalysis(
    all_signals: List[dict],
    target_tickers: List[str],
    force_update: bool,
) -> List[dict]:
    """Gemini 재분석 대상 시그널을 선택한다."""
    if not isinstance(all_signals, list):
        return []

    if target_tickers:
        target_set = {str(t).strip() for t in target_tickers}
        selected = []
        for signal in all_signals:
            if not isinstance(signal, dict):
                continue
            code = str(signal.get("stock_code", "")).strip()
            name = str(signal.get("stock_name", "")).strip()
            if code in target_set or name in target_set:
                selected.append(signal)
        return selected

    if force_update:
        return [sig for sig in all_signals if isinstance(sig, dict)]

    selected = []
    for signal in all_signals:
        if isinstance(signal, dict) and not _is_jongga_ai_analysis_completed(signal):
            selected.append(signal)
    return selected


def _build_jongga_news_analysis_items(signals: List[dict]) -> List[dict]:
    """LLM 뉴스 배치 분석용 입력 아이템을 생성한다."""
    if not isinstance(signals, list):
        return []

    items: List[dict] = []
    for signal in signals:
        if not isinstance(signal, dict):
            continue
        stock_name = signal.get("stock_name")
        news_items = signal.get("news_items", [])
        if stock_name and news_items:
            items.append({"stock": signal, "news": news_items, "supply": None})
    return items


def _build_normalized_gemini_result_map(results_map: Dict[str, dict]) -> Dict[str, dict]:
    """Gemini 결과 키를 종목명/코드 기준으로 정규화한 맵을 생성한다."""
    normalized_results: Dict[str, dict] = {}
    if not isinstance(results_map, dict):
        return normalized_results

    for key, value in results_map.items():
        clean_name = re.sub(r"\s*\([0-9A-Za-z]+\)\s*$", "", str(key)).strip()
        normalized_results[clean_name] = value
        normalized_results[str(key)] = value
    return normalized_results


def _apply_gemini_reanalysis_results(
    all_signals: List[dict],
    results_map: Dict[str, dict],
) -> int:
    """
    Gemini 재분석 결과를 전체 시그널에 반영한다.
    반환값은 업데이트된 종목 수.
    """
    if not isinstance(all_signals, list) or not isinstance(results_map, dict):
        return 0

    normalized_results = _build_normalized_gemini_result_map(results_map)
    updated_count = 0

    for signal in all_signals:
        if not isinstance(signal, dict):
            continue
        name = signal.get("stock_name")
        stock_code = signal.get("stock_code", "")

        matched_result = None
        if name in normalized_results:
            matched_result = normalized_results[name]
        elif f"{name} ({stock_code})" in results_map:
            matched_result = results_map[f"{name} ({stock_code})"]
        elif stock_code in normalized_results:
            matched_result = normalized_results[stock_code]

        if not isinstance(matched_result, dict):
            continue

        if "score" not in signal or not isinstance(signal.get("score"), dict):
            signal["score"] = {}

        signal["score"]["llm_reason"] = matched_result.get("reason", "")
        signal["score"]["news"] = matched_result.get("score", 0)
        signal["ai_evaluation"] = {
            "action": matched_result.get("action", "HOLD"),
            "confidence": matched_result.get("confidence", 0),
            "model": matched_result.get("model", "gemini-2.0-flash"),
        }
        updated_count += 1

    return updated_count


def _none_if_nan(value: Any) -> Any:
    """NaN 계열 값을 None으로 치환한다."""
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    return value


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
    ai_action = _none_if_nan(row.get("ai_action"))
    ai_reason = _none_if_nan(row.get("ai_reason"))
    ai_confidence = _none_if_nan(row.get("ai_confidence"))

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
    score = _safe_float(row.get("score", 0), default=0.0)
    status = str(row.get("status", "OPEN"))
    if status != "OPEN":
        return None
    if score < 60:
        return None

    return {
        "ticker": str(row.get("ticker", "")).zfill(6),
        "name": row.get("name"),
        "signal_date": str(row.get("signal_date")),
        "market": row.get("market"),
        "status": row.get("status"),
        "score": score,
        "contraction_ratio": _none_if_nan(row.get("contraction_ratio")),
        "entry_price": _none_if_nan(row.get("entry_price")),
        "target_price": _none_if_nan(row.get("target_price")),
        "stop_price": _none_if_nan(row.get("stop_price")),
        "foreign_5d": _safe_int(row.get("foreign_5d", 0), default=0),
        "inst_5d": _safe_int(row.get("inst_5d", 0), default=0),
        "vcp_score": _safe_int(row.get("vcp_score", 0), default=0),
        "current_price": _none_if_nan(row.get("current_price")),
        "return_pct": _none_if_nan(row.get("return_pct")),
        "gemini_recommendation": _build_vcp_gemini_recommendation(row),
    }


def _build_vcp_signals_from_dataframe(signals_df: Any) -> List[dict]:
    """signals_log DataFrame를 VCP 시그널 리스트로 변환한다."""
    if not isinstance(signals_df, pd.DataFrame) or signals_df.empty:
        return []

    signals: List[dict] = []
    for _, row in signals_df.iterrows():
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


def _extract_jongga_ai_evaluation(signal: dict) -> Optional[dict]:
    """
    종가베팅 시그널에서 AI 평가 객체를 추출한다.
    우선순위: score_details.ai_evaluation -> score.ai_evaluation -> ai_evaluation -> score.llm_reason
    """
    if not isinstance(signal, dict):
        return None

    ai_eval: Any = None
    score_details = signal.get("score_details")
    if isinstance(score_details, dict):
        ai_eval = score_details.get("ai_evaluation")

    score = signal.get("score")
    if not ai_eval and isinstance(score, dict):
        ai_eval = score.get("ai_evaluation")

    if not ai_eval:
        ai_eval = signal.get("ai_evaluation")

    if not ai_eval and isinstance(score, dict):
        ai_eval = score.get("llm_reason")

    if isinstance(ai_eval, str):
        return {"reason": ai_eval, "action": "HOLD", "confidence": 0}

    return ai_eval if isinstance(ai_eval, dict) else None


def _extract_jongga_score_value(signal: dict, allow_numeric_fallback: bool) -> float:
    """종가 시그널에서 정렬/표시용 점수 값을 추출한다."""
    raw_score = signal.get("score")
    if isinstance(raw_score, dict):
        return _safe_float(raw_score.get("total", 0), default=0.0)
    if allow_numeric_fallback:
        return _safe_float(raw_score, default=0.0)
    return 0.0


def _build_ai_signal_from_jongga_signal(
    signal: dict,
    include_without_ai: bool,
    allow_numeric_score_fallback: bool,
) -> Optional[dict]:
    """종가 시그널 1개를 AI 분석 응답 스키마로 변환한다."""
    if not isinstance(signal, dict):
        return None

    ai_eval = _extract_jongga_ai_evaluation(signal)
    if not include_without_ai and not ai_eval:
        return None

    return {
        "ticker": str(signal.get("stock_code", "")).zfill(6),
        "name": signal.get("stock_name", ""),
        "grade": signal.get("grade"),
        "score": _extract_jongga_score_value(signal, allow_numeric_score_fallback),
        "current_price": signal.get("current_price", 0),
        "entry_price": signal.get("entry_price", 0),
        "vcp_score": 0,
        "contraction_ratio": signal.get("contraction_ratio", 0),
        "foreign_5d": signal.get("foreign_5d", 0),
        "inst_5d": signal.get("inst_5d", 0),
        "gemini_recommendation": ai_eval,
        "news": signal.get("news_items", []),
    }


def _build_ai_signals_from_jongga_results(
    signals: Any,
    include_without_ai: bool,
    allow_numeric_score_fallback: bool,
) -> List[dict]:
    """종가베팅 결과(signals)를 AI 응답용 리스트로 변환한다."""
    if not isinstance(signals, list):
        return []

    ai_signals: List[dict] = []
    for signal in signals:
        converted = _build_ai_signal_from_jongga_signal(
            signal,
            include_without_ai=include_without_ai,
            allow_numeric_score_fallback=allow_numeric_score_fallback,
        )
        if converted:
            ai_signals.append(converted)

    _sort_jongga_signals(ai_signals)
    return ai_signals


def _format_signal_date(value: Any) -> str:
    """신호 날짜를 YYYY-MM-DD 형태로 정규화한다."""
    date_str = str(value or "").strip()
    if len(date_str) == 8 and "-" not in date_str and date_str.isdigit():
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
    return date_str


def _normalize_ai_payload_tickers(payload: Any) -> Any:
    """분석 payload 내 ticker를 6자리 문자열로 정규화한다."""
    if not isinstance(payload, dict):
        return payload

    signals = payload.get("signals")
    if not isinstance(signals, list):
        return payload

    for signal in signals:
        if isinstance(signal, dict) and "ticker" in signal:
            signal["ticker"] = str(signal.get("ticker", "")).zfill(6)

    return payload


def _parse_datetime_safe(value: Any) -> Optional[datetime]:
    """문자열 날짜를 datetime으로 안전하게 변환한다."""
    value_str = str(value or "").strip()
    if not value_str:
        return None

    for parser in (datetime.fromisoformat,):
        try:
            return parser(value_str)
        except Exception:
            continue

    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(value_str, fmt)
        except Exception:
            continue

    return None


def _should_use_jongga_ai_payload(jongga_data: Any, vcp_data: Any) -> bool:
    """jongga_v2 데이터 우선 사용 여부를 판정한다."""
    if not isinstance(jongga_data, dict):
        return False
    signals = jongga_data.get("signals")
    if not isinstance(signals, list) or not signals:
        return False

    if not isinstance(vcp_data, dict) or not vcp_data.get("signals"):
        return True

    jongga_time = _parse_datetime_safe(
        jongga_data.get("updated_at") or jongga_data.get("date")
    )
    vcp_time = _parse_datetime_safe(vcp_data.get("generated_at"))

    if jongga_time and vcp_time:
        return jongga_time >= vcp_time

    # 시간 비교가 불가능하면 jongga를 우선 사용한다(기존 우선순위 유지).
    return True


def _prepare_cumulative_price_dataframe(raw_price_df: Any) -> Any:
    """누적성과 계산용 가격 DataFrame을 정규화한다."""
    if not isinstance(raw_price_df, pd.DataFrame) or raw_price_df.empty:
        return pd.DataFrame()
    if "date" not in raw_price_df.columns or "ticker" not in raw_price_df.columns:
        return pd.DataFrame()

    df = raw_price_df.copy()
    df["ticker"] = df["ticker"].astype(str).str.zfill(6)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df[df["date"].notna()]

    for col in ["open", "high", "low", "close"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.sort_values("date")
    df.set_index("date", inplace=True)
    return df


def _extract_stats_date_from_results_filename(filepath: str, fallback_date: Any = "") -> str:
    """파일명에서 통계 기준일(YYYY-MM-DD)을 추출한다."""
    filename = str(filepath).split("/")[-1]
    file_date_str = filename.split("_")[-1].replace(".json", "")
    try:
        return datetime.strptime(file_date_str, "%Y%m%d").strftime("%Y-%m-%d")
    except Exception:
        return _format_signal_date(fallback_date)


def _calculate_cumulative_trade_metrics(
    entry_price: float,
    stats_date: str,
    stock_prices: Any,
) -> Dict[str, Any]:
    """
    종가베팅 1건의 Outcome/ROI/Trail/기간/최대상승률을 계산한다.
    Target +9%, Stop -5% 규칙을 적용한다.
    """
    outcome = "OPEN"
    roi = 0.0
    max_high = 0.0
    days = 0
    price_trail: List[float] = []

    if not isinstance(stock_prices, pd.DataFrame) or stock_prices.empty:
        return {
            "outcome": outcome,
            "roi": roi,
            "max_high": max_high,
            "days": days,
            "price_trail": price_trail,
        }

    try:
        signal_ts = pd.Timestamp(stats_date)
    except Exception:
        signal_ts = None

    if signal_ts is None:
        return {
            "outcome": outcome,
            "roi": roi,
            "max_high": max_high,
            "days": days,
            "price_trail": price_trail,
        }

    period_prices = stock_prices[stock_prices.index > signal_ts]
    required_cols = {"high", "low", "close"}
    if required_cols.issubset(set(period_prices.columns)):
        period_prices = period_prices[
            (period_prices["high"] > 0)
            & (period_prices["low"] > 0)
            & (period_prices["close"] > 0)
        ]

    target_price = entry_price * 1.09
    stop_price = entry_price * 0.95

    exit_date = None
    if required_cols.issubset(set(period_prices.columns)):
        hit_target = period_prices[period_prices["high"] >= target_price]
        hit_stop = period_prices[period_prices["low"] <= stop_price]
        first_win_date = hit_target.index[0] if not hit_target.empty else None
        first_loss_date = hit_stop.index[0] if not hit_stop.empty else None

        if first_win_date is not None and first_loss_date is not None:
            if first_win_date <= first_loss_date:
                outcome = "WIN"
                roi = 9.0
                exit_date = first_win_date
            else:
                outcome = "LOSS"
                roi = -5.0
                exit_date = first_loss_date
        elif first_win_date is not None:
            outcome = "WIN"
            roi = 9.0
            exit_date = first_win_date
        elif first_loss_date is not None:
            outcome = "LOSS"
            roi = -5.0
            exit_date = first_loss_date

    if exit_date is not None:
        trade_period = period_prices[period_prices.index <= exit_date]
    else:
        trade_period = period_prices

    price_trail = [entry_price]
    if "close" in trade_period.columns and not trade_period.empty:
        closes = [float(v) for v in trade_period["close"].tolist() if pd.notna(v)]
        price_trail.extend(closes)
        if len(price_trail) > 1:
            if outcome == "WIN":
                price_trail[-1] = target_price
            elif outcome == "LOSS":
                price_trail[-1] = stop_price

    days = len(trade_period)

    if "high" in trade_period.columns and not trade_period.empty:
        high_price = trade_period["high"].max()
        if pd.notna(high_price) and high_price > 0:
            max_high = round(((high_price - entry_price) / entry_price) * 100, 1)

    if outcome == "OPEN" and price_trail and roi == 0.0:
        last_price = price_trail[-1]
        roi = round(((last_price - entry_price) / entry_price) * 100, 1)

    return {
        "outcome": outcome,
        "roi": roi,
        "max_high": max_high,
        "days": days,
        "price_trail": price_trail,
    }


def _build_cumulative_trade_record(signal: dict, stats_date: str, price_df: Any) -> Optional[dict]:
    """종가베팅 시그널에서 누적성과 trade 레코드 1건을 생성한다."""
    if not isinstance(signal, dict):
        return None

    ticker = str(signal.get("ticker", signal.get("stock_code", ""))).zfill(6)
    if not ticker or ticker == "000000":
        return None

    entry_price = _safe_float(signal.get("entry_price", 0), default=0.0)
    if entry_price <= 0:
        return None

    metrics = {
        "outcome": "OPEN",
        "roi": 0.0,
        "max_high": 0.0,
        "days": 0,
        "price_trail": [],
    }

    if isinstance(price_df, pd.DataFrame) and not price_df.empty and "ticker" in price_df.columns:
        stock_prices = price_df[price_df["ticker"] == ticker]
        metrics = _calculate_cumulative_trade_metrics(entry_price, stats_date, stock_prices)

    score = signal.get("score", {})
    score_value = score.get("total", 0) if isinstance(score, dict) else 0

    return {
        "id": f"{ticker}-{stats_date}",
        "date": stats_date,
        "grade": signal.get("grade"),
        "name": signal.get("name", signal.get("stock_name", "")),
        "code": ticker,
        "market": signal.get("market", ""),
        "entry": entry_price,
        "outcome": metrics["outcome"],
        "roi": metrics["roi"],
        "maxHigh": metrics["max_high"],
        "priceTrail": metrics["price_trail"],
        "days": metrics["days"],
        "score": score_value,
        "themes": signal.get("themes", []),
    }


def _aggregate_cumulative_kpis(trades: List[dict], price_df: Any, now_dt: datetime) -> dict:
    """누적성과 KPI 집계를 계산한다."""
    total_signals = len(trades)
    wins = sum(1 for t in trades if t.get("outcome") == "WIN")
    losses = sum(1 for t in trades if t.get("outcome") == "LOSS")
    opens = sum(1 for t in trades if t.get("outcome") == "OPEN")

    closed_trades = wins + losses
    win_rate = round((wins / closed_trades) * 100, 1) if closed_trades > 0 else 0.0

    total_roi = sum(float(t.get("roi", 0)) for t in trades)
    avg_roi = round(total_roi / total_signals, 2) if total_signals > 0 else 0.0

    roi_by_grade: Dict[str, dict] = {}
    for grade in ["S", "A", "B"]:
        grade_trades = [t for t in trades if t.get("grade") == grade]
        grade_count = len(grade_trades)
        grade_total_roi = sum(float(t.get("roi", 0)) for t in grade_trades)
        grade_avg_roi = round(grade_total_roi / grade_count, 2) if grade_count > 0 else 0.0
        roi_by_grade[grade] = {
            "count": grade_count,
            "avgRoi": grade_avg_roi,
            "totalRoi": round(grade_total_roi, 1),
        }

    gross_profit = sum(float(t.get("roi", 0)) for t in trades if float(t.get("roi", 0)) > 0)
    gross_loss = abs(
        sum(float(t.get("roi", 0)) for t in trades if float(t.get("roi", 0)) < 0)
    )
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else round(gross_profit, 2)

    if isinstance(price_df, pd.DataFrame) and not price_df.empty and len(price_df.index) > 0:
        max_price_date = price_df.index.max()
        if hasattr(max_price_date, "strftime"):
            price_date_str = max_price_date.strftime("%Y-%m-%d")
        else:
            price_date_str = str(max_price_date)
    else:
        price_date_str = now_dt.strftime("%Y-%m-%d")

    avg_days = (
        round(sum(float(t.get("days", 0)) for t in trades) / total_signals, 1)
        if total_signals > 0
        else 0
    )

    return {
        "totalSignals": total_signals,
        "winRate": win_rate,
        "wins": wins,
        "losses": losses,
        "open": opens,
        "avgRoi": avg_roi,
        "totalRoi": round(total_roi, 1),
        "roiByGrade": roi_by_grade,
        "avgDays": avg_days,
        "priceDate": price_date_str,
        "profitFactor": profit_factor,
    }


def _paginate_items(items: List[dict], page: int, limit: int) -> Tuple[List[dict], dict]:
    """목록 페이지네이션을 수행한다."""
    safe_page = page if page > 0 else 1
    safe_limit = limit if limit > 0 else 50
    total = len(items)
    start_idx = (safe_page - 1) * safe_limit
    end_idx = start_idx + safe_limit
    total_pages = (total + safe_limit - 1) // safe_limit if safe_limit > 0 else 0

    return (
        items[start_idx:end_idx],
        {
            "total": total,
            "page": safe_page,
            "limit": safe_limit,
            "totalPages": total_pages,
        },
    )


def _determine_backtest_status(win_rate: float) -> str:
    """백테스트 win_rate 기반 상태를 산출한다."""
    if win_rate == 0:
        return "PENDING"
    if win_rate >= 60:
        return "EXCELLENT"
    if win_rate >= 40:
        return "GOOD"
    return "BAD"


def _build_latest_price_map(price_df: Any) -> Dict[str, float]:
    """가격 DataFrame에서 ticker별 최신 종가 맵을 생성한다."""
    if not isinstance(price_df, pd.DataFrame) or price_df.empty:
        return {}
    if not {"ticker", "close"}.issubset(set(price_df.columns)):
        return {}

    df = price_df.copy()
    df["ticker"] = df["ticker"].astype(str).str.zfill(6)
    if "date" in df.columns:
        df = df.sort_values("date")
    latest_prices = df.groupby("ticker").tail(1)
    latest_prices["close"] = pd.to_numeric(latest_prices["close"], errors="coerce")
    latest_prices = latest_prices[latest_prices["close"].notna()]
    return latest_prices.set_index("ticker")["close"].to_dict()


def _inject_latest_prices_to_candidates(candidates: List[dict], price_map: Dict[str, float]) -> None:
    """종가베팅 후보군에 최신가/수익률을 반영한다."""
    if not isinstance(candidates, list) or not isinstance(price_map, dict):
        return

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        code = str(
            candidate.get("stock_code")
            or candidate.get("code")
            or candidate.get("ticker")
            or ""
        ).zfill(6)
        if code not in price_map:
            continue

        current_price = _safe_float(price_map.get(code), default=0.0)
        if current_price <= 0:
            continue
        candidate["current_price"] = current_price

        entry = _safe_float(candidate.get("entry_price") or candidate.get("close"), default=0.0)
        if entry > 0:
            candidate["return_pct"] = round(((current_price - entry) / entry) * 100, 2)


def _calculate_scenario_return(
    ticker: str,
    entry_price: float,
    signal_date: Any,
    current_price: float,
    price_df: Any,
    target_pct: float = 0.15,
    stop_pct: float = 0.05,
) -> float:
    """
    백테스트 시나리오 수익률 계산.
    - 익절: +target_pct
    - 손절: -stop_pct
    - 미충족: 현재가 기준
    """
    try:
        entry = _safe_float(entry_price, default=0.0)
        current = _safe_float(current_price, default=0.0)
        if entry <= 0:
            return 0.0

        if not isinstance(price_df, pd.DataFrame) or price_df.empty:
            return ((current - entry) / entry) * 100

        if "high" not in price_df.columns or "low" not in price_df.columns:
            ret = ((current - entry) / entry) * 100
            if ret > (target_pct * 100):
                return target_pct * 100
            if ret < -(stop_pct * 100):
                return -(stop_pct * 100)
            return ret

        if "date" in price_df.columns:
            subset = price_df[
                (price_df["ticker"] == ticker) & (price_df["date"] > signal_date)
            ].sort_values("date")
        else:
            subset = price_df[(price_df["ticker"] == ticker)].sort_index()

        for _, day in subset.iterrows():
            low = _safe_float(day.get("low"), default=0.0)
            high = _safe_float(day.get("high"), default=0.0)
            if low <= entry * (1 - stop_pct):
                return -(stop_pct * 100)
            if high >= entry * (1 + target_pct):
                return target_pct * 100

        return ((current - entry) / entry) * 100
    except Exception:
        entry = _safe_float(entry_price, default=0.0)
        current = _safe_float(current_price, default=0.0)
        if entry <= 0:
            return 0.0
        return ((current - entry) / entry) * 100


def _calculate_jongga_backtest_stats(
    candidates: List[dict],
    history_payloads: List[dict],
    price_map: Dict[str, float],
    price_df: Any,
) -> dict:
    """종가베팅 백테스트 요약 통계를 계산한다."""
    stats = {
        "status": "Accumulating",
        "count": 0,
        "win_rate": 0,
        "avg_return": 0,
        "candidates": candidates if isinstance(candidates, list) else [],
    }

    total_signals = 0
    wins = 0
    losses = 0
    total_return = 0.0

    for payload in history_payloads:
        if not isinstance(payload, dict):
            continue
        signals = payload.get("signals", [])
        signal_date = payload.get("date", "")
        if not isinstance(signals, list):
            continue

        for signal in signals:
            if not isinstance(signal, dict):
                continue
            code = str(
                signal.get("stock_code")
                or signal.get("code")
                or signal.get("ticker")
                or ""
            ).zfill(6)
            if not code or code == "000000":
                continue

            entry = _safe_float(
                signal.get("entry_price")
                or signal.get("close")
                or signal.get("current_price"),
                default=0.0,
            )
            if entry <= 0:
                continue

            current_price = _safe_float(price_map.get(code), default=0.0)
            if current_price <= 0:
                continue

            ret = _calculate_scenario_return(
                code,
                entry,
                signal_date,
                current_price,
                price_df,
                target_pct=0.09,
                stop_pct=0.05,
            )
            total_signals += 1
            total_return += ret
            if ret >= 9.0:
                wins += 1
            elif ret <= -5.0:
                losses += 1

    if total_signals > 0:
        stats["count"] = total_signals
        closed_trades = wins + losses
        win_rate = round((wins / closed_trades) * 100, 1) if closed_trades > 0 else 0.0
        stats["win_rate"] = win_rate
        stats["avg_return"] = round(total_return / total_signals, 1)
        stats["status"] = _determine_backtest_status(win_rate)
    elif stats["candidates"]:
        stats["status"] = "OK (New)"

    _inject_latest_prices_to_candidates(stats["candidates"], price_map)
    return stats


def _calculate_vcp_backtest_stats(vcp_df: Any, price_map: Dict[str, float], price_df: Any) -> dict:
    """VCP 백테스트 요약 통계를 계산한다."""
    stats = {
        "status": "Accumulating",
        "count": 0,
        "win_rate": 0,
        "avg_return": 0,
    }

    if not isinstance(vcp_df, pd.DataFrame) or vcp_df.empty:
        return stats

    stats["status"] = "OK"

    total_count = 0
    wins = 0
    losses = 0
    total_return = 0.0

    for _, row in vcp_df.iterrows():
        ticker = str(row.get("ticker", "")).zfill(6)
        entry_price = _safe_float(row.get("entry_price", 0), default=0.0)
        signal_date = str(row.get("signal_date", ""))
        if entry_price <= 0 or not signal_date:
            continue

        current_price = _safe_float(price_map.get(ticker), default=0.0)
        if current_price <= 0:
            continue

        sim_ret = _calculate_scenario_return(
            ticker,
            entry_price,
            signal_date,
            current_price,
            price_df,
            target_pct=0.15,
            stop_pct=0.05,
        )
        total_count += 1
        total_return += sim_ret
        if sim_ret >= 15.0:
            wins += 1
        elif sim_ret <= -5.0:
            losses += 1

    if total_count > 0:
        stats["count"] = total_count
        closed_count = wins + losses
        win_rate = round((wins / closed_count) * 100, 1) if closed_count > 0 else 0.0
        stats["win_rate"] = win_rate
        stats["avg_return"] = round(total_return / total_count, 1)
        stats["status"] = _determine_backtest_status(win_rate)

    return stats
