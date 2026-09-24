#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
시그널/뉴스 컨텍스트 로딩 및 텍스트 포맷 유틸
"""

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List

from services.kr_market_data_cache_service import load_json_payload_from_path


def _describe_as_of(signal_date: Any, today: date | None) -> str:
    """「기준일 YYYY-MM-DD, D일 경과」. 모델이 옛 자료를 오늘 것으로 말하지 않게 문맥마다 붙인다([CHAT-031])."""
    raw = str(signal_date or "").strip()[:10]
    try:
        as_of = datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return "기준일 알 수 없음"
    elapsed = ((today or date.today()) - as_of).days
    return f"기준일 {as_of.isoformat()}, {elapsed}일 경과"


def _read_json(path: Path, logger: logging.Logger) -> Dict[str, Any]:
    """JSON 파일을 읽어 dict를 반환한다. 실패 시 빈 dict."""
    try:
        data = load_json_payload_from_path(str(path))
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.error("Failed to read json %s: %s", path, e)
        return {}


def load_jongga_signals(data_dir: Path, logger: logging.Logger) -> List[Dict[str, Any]]:
    """jongga_v2_latest.json의 signals 리스트를 반환한다."""
    path = data_dir / "jongga_v2_latest.json"
    if not path.exists():
        return []
    data = _read_json(path, logger)
    signals = data.get("signals", [])
    return signals if isinstance(signals, list) else []


def build_latest_news_text(
    signals: List[Dict[str, Any]], limit: int = 5, today: date | None = None
) -> str:
    """signals 내 news_items를 합쳐 최근 뉴스 텍스트를 만든다. 첫 줄은 기준일이다."""
    all_news: List[str] = []
    for signal in signals:
        news_items = signal.get("news_items", [])
        if not isinstance(news_items, list):
            continue
        for news in news_items:
            title = news.get("title", "") if isinstance(news, dict) else ""
            source = news.get("source", "") if isinstance(news, dict) else ""
            if title:
                all_news.append(f"- [{source}] {title}")

    if not all_news:
        return ""
    return "\n".join([f"({_describe_as_of(signals[0].get('signal_date'), today)})", *all_news[:limit]])


def build_jongga_candidates_text(
    signals: List[Dict[str, Any]], limit: int = 3, today: date | None = None
) -> str:
    """signals에서 S/A급 종가베팅 후보 텍스트를 만든다. 첫 줄은 기준일이다."""
    candidates = []
    for signal in signals:
        grade = signal.get("grade", "D")
        if grade in ["S", "A"]:
            candidates.append(signal)

    candidates.sort(key=lambda item: item.get("score", {}).get("total", 0), reverse=True)
    if not candidates:
        return ""

    result_text = f"({_describe_as_of(candidates[0].get('signal_date'), today)})\n"
    for signal in candidates[:limit]:
        name = signal.get("stock_name", "N/A")
        code = signal.get("stock_code", "")
        grade = signal.get("grade", "")
        score_val = signal.get("score", {}).get("total", 0)
        date = signal.get("signal_date", "")

        reason = "정보 없음"
        score_details = signal.get("score_details", {})
        if isinstance(score_details, dict):
            ai_eval = score_details.get("ai_evaluation", {})
            if isinstance(ai_eval, dict):
                reason = ai_eval.get("reason", "정보 없음")

        result_text += (
            f"- **{name}** ({code}): {grade}급, 점수 {score_val}점 ({date})\n"
            f"  - AI 분석: {reason[:100]}...\n"
        )

    return result_text


def load_vcp_ai_payload(data_dir: Path, logger: logging.Logger) -> Dict[str, Any]:
    """VCP AI 분석 파일(kr_ai_analysis/ai_analysis_results) 전체를 반환한다. 없으면 빈 dict."""
    primary = data_dir / "kr_ai_analysis.json"
    fallback = data_dir / "ai_analysis_results.json"

    if primary.exists():
        return _read_json(primary, logger)
    if fallback.exists():
        return _read_json(fallback, logger)
    return {}


def _vcp_action(signal: Dict[str, Any]) -> Any:
    gemini_rec = signal.get("gemini_recommendation", {})
    action = gemini_rec.get("action") if isinstance(gemini_rec, dict) else None
    perplexity_rec = signal.get("perplexity_recommendation", {})
    if not action and isinstance(perplexity_rec, dict):
        action = perplexity_rec.get("action")
    return action


def build_vcp_analysis_summary_text(
    payload: Dict[str, Any], today: date | None = None, limit: int = 5
) -> str:
    """분석 건수·기준일·매수 추천 건수 머리글 뒤에 BUY 목록을 붙인다.

    분석이 하나도 없을 때만 빈 문자열이다. 전부 HOLD 여도 「분석 없음」 으로 읽히지 않게 머리글은 남긴다([CHAT-031]).
    """
    signals = payload.get("signals", [])
    if not isinstance(signals, list) or not signals:
        return ""
    buy_count = sum(1 for signal in signals if _vcp_action(signal) == "BUY")
    as_of = payload.get("signal_date") or str(payload.get("generated_at") or "")[:10]
    header = f"분석 {len(signals)}건 ({_describe_as_of(as_of, today)}), 매수 추천 {buy_count}건"
    body = build_vcp_buy_recommendations_text(signals, limit=limit).rstrip("\n")
    return f"{header}\n{body or '- 매수 추천 종목 없음 (분석 결과가 전부 HOLD/SELL)'}"


def build_vcp_buy_recommendations_text(signals: List[Dict[str, Any]], limit: int = 5) -> str:
    """signals에서 BUY 추천 종목 텍스트를 만든다."""
    result_text = ""
    count = 0

    for signal in signals:
        if _vcp_action(signal) != "BUY":
            continue
        gemini_rec = signal.get("gemini_recommendation", {})
        perplexity_rec = signal.get("perplexity_recommendation", {})

        name = signal.get("name") or signal.get("stock_name") or "N/A"
        score = signal.get("score")
        if score is None:
            score = signal.get("vcp_score")
        # 재분석이 캐시에 새로 넣은 행은 점수가 없다. 0점으로 적지 않는다 [CHAT-045]
        score_text = f": {score}점" if score is not None else ""

        reason = gemini_rec.get("reason", "") if isinstance(gemini_rec, dict) else ""
        if not reason and isinstance(perplexity_rec, dict):
            reason = perplexity_rec.get("reason", "")

        result_text += f"- **{name}**{score_text} (매수 추천)\n  - AI 분석: {reason[:120]}...\n"
        count += 1
        if count >= limit:
            break

    return result_text
