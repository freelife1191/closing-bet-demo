#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VCP AI Analyzer Helpers
"""

from __future__ import annotations

import ast
import json
import re
from typing import Any, Optional


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
_PERPLEXITY_AUTH_KEYWORDS = (
    "invalid api key",
    "invalid_api_key",
    "invalid token",
    "unauthorized",
    "authentication",
    "forbidden",
    "token",
    "api key",
    "bearer",
)
_ACTION_PATTERN = re.compile(
    r"""["']?action["']?\s*:\s*["']?([A-Za-z가-힣_ ]+)""",
    re.IGNORECASE,
)
_CONFIDENCE_PATTERN = re.compile(
    r"""["']?confidence["']?\s*:\s*["']?\s*([0-9]+(?:\.[0-9]+)?)\s*%?""",
    re.IGNORECASE,
)
_REASON_QUOTED_PATTERN = re.compile(
    r"""["']?reason["']?\s*:\s*(["'])(.*?)\1""",
    re.IGNORECASE | re.DOTALL,
)
_REASON_RAW_PATTERN = re.compile(
    r"""["']?reason["']?\s*:\s*([^,\n}]+)""",
    re.IGNORECASE | re.DOTALL,
)
_ACTION_NARRATIVE_PATTERNS = (
    re.compile(
        r"""(?:position\s+recommendation|final\s+recommendation|recommendation|action|opinion|conclusion)"""
        r"""[^A-Za-z가-힣]{0,30}(buy|sell|hold|매수|매도|관망|보유)""",
        re.IGNORECASE,
    ),
    re.compile(r"""\b(buy|sell|hold)\s+position\b""", re.IGNORECASE),
    re.compile(
        r"""(?:추천|의견|결론|판단)[^\n]{0,120}?(매수|매도|관망|보유|buy|sell|hold)""",
        re.IGNORECASE,
    ),
)
_CONFIDENCE_NARRATIVE_PATTERNS = (
    re.compile(
        r"""confidence(?:\s+(?:level|score|assessment|rating))?"""
        r"""[^0-9]{0,20}([0-9]{1,3})(?:\s*/\s*100|%)""",
        re.IGNORECASE,
    ),
    re.compile(
        r"""(?:신뢰도|확신도|신뢰\s*수준)[^0-9]{0,20}([0-9]{1,3})(?:\s*/\s*100|%)?""",
        re.IGNORECASE,
    ),
)
_AMBIGUOUS_ACTION_PATTERNS = (
    re.compile(r"""\b(buy|sell|hold)\b\s*(?:/|\||,|or)\s*\b(buy|sell|hold)\b""", re.IGNORECASE),
    re.compile(r"""(매수|매도|관망|보유)\s*(?:/|\||,|또는)\s*(매수|매도|관망|보유)"""),
)


def _normalize_action_value(value: Any) -> str | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None

    lowered = normalized.lower()
    keyword_hits = {
        "buy": ("매수" in normalized) or ("buy" in lowered),
        "sell": ("매도" in normalized) or ("sell" in lowered),
        "hold": ("관망" in normalized)
        or ("보유" in normalized)
        or ("중립" in normalized)
        or ("hold" in lowered),
    }
    if sum(1 for hit in keyword_hits.values() if hit) > 1:
        # 예: "BUY|SELL|HOLD", "매수/매도/관망" 같은 모호 표현은 폐기
        return None

    upper = normalized.upper()
    if upper in {"BUY", "SELL", "HOLD"}:
        return upper

    if "매수" in normalized or "buy" in lowered:
        return "BUY"
    if "매도" in normalized or "sell" in lowered:
        return "SELL"
    if "관망" in normalized or "보유" in normalized or "hold" in lowered or "중립" in normalized:
        return "HOLD"
    return None


def _normalize_confidence_value(value: Any, default: int = 0) -> int:
    if isinstance(value, str):
        value = value.replace("%", "").replace(",", "").strip()
    try:
        numeric = int(float(value))
    except (TypeError, ValueError):
        numeric = int(default)
    return max(0, min(100, numeric))


def _extract_json_fenced_content(text: str) -> str:
    normalized = text.strip()
    if not normalized.startswith("```"):
        return normalized

    lines = normalized.split("\n")
    if len(lines) < 2:
        return normalized
    if lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return "\n".join(lines[1:]).strip()


def _iter_json_object_candidates(text: str):
    length = len(text)
    for start in range(length):
        if text[start] != "{":
            continue
        depth = 0
        in_string = False
        escaped = False

        for idx in range(start, length):
            ch = text[idx]
            if in_string:
                if escaped:
                    escaped = False
                    continue
                if ch == "\\":
                    escaped = True
                    continue
                if ch == "\"":
                    in_string = False
                continue

            if ch == "\"":
                in_string = True
                continue
            if ch == "{":
                depth += 1
                continue
            if ch == "}":
                depth -= 1
                if depth == 0:
                    yield text[start:idx + 1]
                    break


def _load_json_like(text: str) -> Any:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        try:
            return ast.literal_eval(text)
        except (ValueError, SyntaxError):
            return None


def _find_recommendation_payload(payload: Any) -> Optional[dict[str, Any]]:
    if isinstance(payload, dict):
        if "action" in payload and "confidence" in payload:
            return payload
        for value in payload.values():
            found = _find_recommendation_payload(value)
            if found is not None:
                return found
        return None

    if isinstance(payload, list):
        for item in payload:
            found = _find_recommendation_payload(item)
            if found is not None:
                return found
    return None


def _extract_reason_by_pattern(text: str) -> str:
    quoted_match = _REASON_QUOTED_PATTERN.search(text)
    if quoted_match:
        return str(quoted_match.group(2)).strip()

    raw_match = _REASON_RAW_PATTERN.search(text)
    if raw_match:
        return str(raw_match.group(1)).strip().strip("\"' ")
    return ""


def _parse_recommendation_by_pattern(text: str) -> Optional[dict[str, Any]]:
    action_match = _ACTION_PATTERN.search(text)
    confidence_match = _CONFIDENCE_PATTERN.search(text)
    if not action_match or not confidence_match:
        return None

    action_value = _normalize_action_value(action_match.group(1))
    if action_value is None:
        return None
    confidence_value = _normalize_confidence_value(confidence_match.group(1), default=0)
    reason_value = _extract_reason_by_pattern(text) or "LLM 응답 파싱(부분 성공)"

    return {
        "action": action_value,
        "confidence": confidence_value,
        "reason": reason_value[:600],
    }


def _extract_action_from_narrative(text: str) -> str | None:
    for pattern in _AMBIGUOUS_ACTION_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        left = _normalize_action_value(match.group(1))
        right = _normalize_action_value(match.group(2))
        if left and right and left != right:
            return None

    candidates: list[str] = []
    for pattern in _ACTION_NARRATIVE_PATTERNS:
        for match in pattern.finditer(text):
            action = _normalize_action_value(match.group(1))
            if action:
                candidates.append(action)

    if not candidates:
        return None

    unique = []
    for item in candidates:
        if item not in unique:
            unique.append(item)

    if len(unique) != 1:
        return None
    return unique[0]


def _extract_confidence_from_narrative(text: str) -> int | None:
    for pattern in _CONFIDENCE_NARRATIVE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        try:
            value = int(float(match.group(1)))
        except (TypeError, ValueError):
            continue
        return max(0, min(100, value))
    return None


def _extract_reason_from_narrative(text: str, action_value: str) -> str:
    explicit_reason = _extract_reason_by_pattern(text)
    if explicit_reason:
        return explicit_reason[:600]

    keywords = [
        action_value.lower(),
        "recommendation",
        "confidence",
        "recommend",
        "추천",
        "의견",
        "결론",
        "신뢰도",
        "확신도",
        "매수",
        "매도",
        "관망",
        "보유",
    ]
    compact = " ".join(str(text or "").split())
    for sentence in re.split(r"(?<=[.!?。])\s+", compact):
        normalized = sentence.lower()
        if any(keyword in normalized or keyword in sentence for keyword in keywords):
            if len(sentence.strip()) >= 10:
                return sentence.strip()[:600]

    return compact[:600] if compact else "LLM 서술 응답에서 추론한 결과"


def _parse_recommendation_from_narrative(text: str) -> Optional[dict[str, Any]]:
    action_value = _extract_action_from_narrative(text)
    confidence_value = _extract_confidence_from_narrative(text)
    if action_value is None or confidence_value is None:
        return None

    return {
        "action": action_value,
        "confidence": confidence_value,
        "reason": _extract_reason_from_narrative(text, action_value),
    }


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def build_vcp_rule_based_recommendation(
    *,
    stock_name: str,
    stock_data: dict[str, Any],
) -> dict[str, Any]:
    """
    LLM JSON 응답 복구 실패 시 사용하는 규칙 기반 보정 추천.
    """
    score = _safe_float(stock_data.get("score"), 0.0)
    contraction_ratio = _safe_float(stock_data.get("contraction_ratio"), 1.0)
    foreign_5d = _safe_float(stock_data.get("foreign_5d"), 0.0)
    inst_5d = _safe_float(stock_data.get("inst_5d"), 0.0)
    foreign_1d = _safe_float(stock_data.get("foreign_1d"), 0.0)
    inst_1d = _safe_float(stock_data.get("inst_1d"), 0.0)
    flow_5d = foreign_5d + inst_5d
    flow_1d = foreign_1d + inst_1d

    if score >= 78 and contraction_ratio <= 0.80 and flow_5d > 0 and flow_1d >= 0:
        action = "BUY"
        confidence = max(60, min(90, int(score * 0.95 + (4 if contraction_ratio <= 0.70 else 0))))
    elif score <= 62 or (flow_5d < 0 and flow_1d < 0):
        action = "SELL"
        confidence = max(55, min(88, int(72 - max(0.0, score - 50) * 0.35)))
    else:
        action = "HOLD"
        confidence = max(52, min(82, int(58 + max(0.0, score - 60) * 0.4)))

    reason = (
        "LLM JSON 응답을 복구하지 못해 규칙 기반 보정 결과를 사용했습니다. "
        f"{stock_name}의 VCP 점수 {score:.1f}점, 수축비율 {contraction_ratio:.2f}, "
        f"수급(5일 {flow_5d:.0f}주 / 1일 {flow_1d:.0f}주)을 반영해 {action}로 판단합니다."
    )
    return {
        "action": action,
        "confidence": confidence,
        "reason": reason[:600],
    }


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
            action_value = _normalize_action_value(parsed["action"])
            if action_value is None:
                return None
            parsed["action"] = action_value
            parsed["confidence"] = _normalize_confidence_value(parsed.get("confidence"), default=0)
            parsed["reason"] = str(parsed.get("reason") or "분석 근거 없음")[:600]
            return parsed
        return None

    normalized = _extract_json_fenced_content(str(text or ""))
    parsed_payload = _load_json_like(normalized)
    found_payload = _find_recommendation_payload(parsed_payload)
    if found_payload is not None:
        return _normalize(dict(found_payload))

    for candidate in _iter_json_object_candidates(str(text or "")):
        parsed_candidate = _load_json_like(candidate)
        found_payload = _find_recommendation_payload(parsed_candidate)
        if found_payload is not None:
            return _normalize(dict(found_payload))

    by_pattern = _parse_recommendation_by_pattern(str(text or ""))
    if by_pattern is not None:
        return _normalize(by_pattern)

    from_narrative = _parse_recommendation_from_narrative(str(text or ""))
    if from_narrative is not None:
        return _normalize(from_narrative)

    return None


def extract_openai_message_text(content: Any) -> str:
    """OpenAI 호환 message.content(문자열/배열/객체)에서 텍스트를 추출한다."""
    if isinstance(content, str):
        return content
    if content is None:
        return ""

    if isinstance(content, dict):
        for key in ("text", "content", "output_text", "reasoning_content"):
            value = content.get(key)
            if isinstance(value, str):
                return value
        return ""

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                if item.strip():
                    parts.append(item)
                continue
            if isinstance(item, dict):
                for key in ("text", "content", "output_text", "reasoning_content"):
                    value = item.get(key)
                    if isinstance(value, str) and value.strip():
                        parts.append(value)
                        break
                continue

            for attr in ("text", "content", "output_text", "reasoning_content"):
                value = getattr(item, attr, None)
                if isinstance(value, str) and value.strip():
                    parts.append(value)
                    break
        return "\n".join(parts).strip()

    for attr in ("text", "content", "output_text", "reasoning_content"):
        value = getattr(content, attr, None)
        if isinstance(value, str):
            return value
    return ""


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


def classify_perplexity_error(status_code: int, response_text: str | None) -> str:
    """
    Perplexity 오류 유형 분류.

    return:
      - "quota": 할당량/크레딧/레이트 리밋 가능성 높음
      - "auth": 인증/권한 문제 가능성 높음
      - "auth_or_quota": 401/403 등으로 원인이 모호함
      - "other": 기타 오류
    """
    normalized = (response_text or "").lower()

    if status_code in (402, 429):
        return "quota"
    if is_perplexity_quota_exceeded(status_code, response_text):
        return "quota"

    if status_code in (401, 403):
        if any(keyword in normalized for keyword in _PERPLEXITY_QUOTA_KEYWORDS):
            return "quota"
        if any(keyword in normalized for keyword in _PERPLEXITY_AUTH_KEYWORDS):
            return "auth"
        return "auth_or_quota"

    return "other"


__all__ = [
    "build_vcp_rule_based_recommendation",
    "build_perplexity_request",
    "build_vcp_prompt",
    "classify_perplexity_error",
    "extract_openai_message_text",
    "extract_perplexity_response_text",
    "is_perplexity_quota_exceeded",
    "parse_json_response",
]
