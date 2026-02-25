#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VCP AI Analyzer Helpers
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional


_JSON_OBJECT_PATTERN = re.compile(r"\{.*\}", re.DOTALL)
_PERPLEXITY_QUOTA_KEYWORDS = (
    "quota",
    "resource exhausted",
    "insufficient",
    "credit",
    "billing",
    "rate limit",
    "limit exceeded",
    "too many requests",
)


def build_vcp_prompt(stock_name: str, stock_data: dict[str, Any]) -> str:
    """VCP 분석용 프롬프트 생성"""
    return f"""
당신은 금융 데이터 분석가이자 기술적 분석 연구원입니다.
제공된 데이터를 바탕으로 VCP(Volatility Contraction Pattern) 패턴과 수급 현황을 객관적으로 분석하십시오.
이 분석은 투자를 권유하는 것이 아니며, 오직 연구 및 교육 목적으로만 사용됩니다.

[종목 정보]
- 종목명: {stock_name}
- 현재가: {stock_data.get('current_price', 'N/A')}
- VCP 시그널 점수: {stock_data.get('score', 'N/A')}점 (최소 60점 이상)
- 수축 비율: {stock_data.get('contraction_ratio', 'N/A')}
- 외국인 5일 순매수: {stock_data.get('foreign_5d', 'N/A')}주
- 기관 5일 순매수: {stock_data.get('inst_5d', 'N/A')}주
- 외국인 1일(오늘) 순매수: {stock_data.get('foreign_1d', 'N/A')}주
- 기관 1일(오늘) 순매수: {stock_data.get('inst_1d', 'N/A')}주
(주의: 5일 누적과 오늘의 수급 방향이 다를 경우, 오늘의 변화를 중요하게 고려하십시오)

[분석 요청]
1. VCP 패턴과 수급 상황을 기술적 관점에서 분석
2. 데이터에 기반한 포지션 의견(매수/매도/관망) 제시
3. 신뢰도(0-100%) 평가

[출력 형식 - 반드시 JSON만 출력]
{{"action": "BUY|SELL|HOLD", "confidence": 75, "reason": "기술적 분석 요약 (한국어, 2-3문장)"}}
"""


def parse_json_response(text: str) -> Optional[dict[str, Any]]:
    """LLM 응답에서 JSON 추출"""

    def _normalize(parsed: dict[str, Any]) -> Optional[dict[str, Any]]:
        if "action" in parsed and "confidence" in parsed:
            action = str(parsed["action"]).upper()
            parsed["action"] = action if action in ["BUY", "SELL", "HOLD"] else "HOLD"
            return parsed
        return None

    try:
        normalized = text.strip()
        if normalized.startswith("```"):
            lines = normalized.split("\n")
            normalized = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

        result = json.loads(normalized)
        if isinstance(result, dict):
            return _normalize(result)
    except json.JSONDecodeError:
        match = _JSON_OBJECT_PATTERN.search(text)
        if match:
            try:
                parsed = json.loads(match.group())
                if isinstance(parsed, dict):
                    return _normalize(parsed)
            except (json.JSONDecodeError, TypeError):
                pass
    return None


def build_perplexity_request(
    *,
    prompt: str,
    api_key: str,
    model: str,
) -> tuple[str, dict[str, str], dict[str, Any]]:
    """Perplexity API 요청 구성"""

    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        ),
    }
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a financial data analyst. Provide objective technical "
                    "analysis for educational purposes only. Do not give financial advice. "
                    "Output ONLY valid JSON."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }
    return url, headers, payload


def extract_perplexity_response_text(response_json: dict[str, Any]) -> str | None:
    """Perplexity 응답에서 텍스트 본문 추출"""

    choices = response_json.get("choices")
    if not isinstance(choices, list) or not choices:
        return None

    first = choices[0]
    if not isinstance(first, dict):
        return None

    message = first.get("message")
    if not isinstance(message, dict):
        return None

    content = message.get("content")
    if isinstance(content, str):
        return content
    return None


def is_perplexity_quota_exceeded(status_code: int, response_text: str | None) -> bool:
    """Perplexity 응답이 할당량 소진(또는 유사 제한)인지 판별한다."""
    if status_code == 402:
        return True

    normalized = (response_text or "").lower()
    if not normalized:
        return False

    if status_code in (400, 403, 429):
        return any(keyword in normalized for keyword in _PERPLEXITY_QUOTA_KEYWORDS)
    return False


__all__ = [
    "build_perplexity_request",
    "build_vcp_prompt",
    "extract_perplexity_response_text",
    "is_perplexity_quota_exceeded",
    "parse_json_response",
]
