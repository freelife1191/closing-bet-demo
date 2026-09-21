#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM Analyzer 응답 파서 모듈.
"""

from __future__ import annotations

import json
import re
from typing import Dict, List, Optional

from engine.pandas_utils_safe import safe_confidence
from engine.exceptions import LLMResponseParseError


_JSON_OBJECT_PATTERN = re.compile(r"\{.*\}", re.DOTALL)
_JSON_ARRAY_PATTERN = re.compile(r"\[.*\]", re.DOTALL)


def _strip_markdown_code_fence(text: str) -> str:
    normalized = (text or "").strip()
    if normalized.startswith("```") and normalized.endswith("```"):
        lines = normalized.splitlines()
        if len(lines) >= 2:
            return "\n".join(lines[1:-1]).strip()
    return normalized


def _extract_json_candidate(text: str, pattern: re.Pattern[str]) -> str:
    candidate = _strip_markdown_code_fence(text)
    if not candidate:
        return ""

    # 응답이 이미 JSON 형태면 정규식 스캔을 생략해 파싱 비용을 줄인다.
    first_char = candidate[:1]
    last_char = candidate[-1:]
    if (first_char == "{" and last_char == "}") or (first_char == "[" and last_char == "]"):
        return candidate

    matched = pattern.search(candidate)
    return matched.group(0) if matched else candidate


def normalize_model_name(model: str) -> str:
    """표시용 모델명 정규화."""
    if model == "gemini-flash-latest":
        return "Gemini Flash (Latest)"
    return model


def parse_json_response(
    *,
    response_text: str,
    stock_name: str,
    model_name: str,
    logger,
) -> Optional[Dict]:
    """단일 종목 JSON 응답 파싱."""

    result_text = response_text.strip()
    if not result_text:
        logger.warning(f"Empty response for {stock_name}")
        return None

    json_str = _extract_json_candidate(result_text, _JSON_OBJECT_PATTERN)

    try:
        result = json.loads(json_str)
    except json.JSONDecodeError as error:
        logger.error(f"JSON 파싱 실패 ({stock_name}): {error}")
        logger.debug(f"Raw: {result_text}")
        return None

    if isinstance(result, dict) and "model" not in result:
        result["model"] = normalize_model_name(model_name)
    return result


def parse_batch_response(*, response_text: str, logger) -> List[Dict]:
    """배치 JSON 응답 파싱."""

    json_str = _extract_json_candidate(response_text, _JSON_ARRAY_PATTERN)

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as error:
        logger.error(f"배치 JSON 파싱 실패: {error}")
        return []


def build_result_map(*, results_list: List[Dict], model_name: str) -> Dict[str, Dict]:
    """배치 분석 결과를 종목명 키 맵으로 변환."""

    normalized_model = normalize_model_name(model_name)
    final_map: Dict[str, Dict] = {}

    for item in results_list:
        name = item.get("name")
        if not name:
            continue
        final_map[name] = {
            "score": item.get("score", 0),
            "action": item.get("action", "HOLD"),
            "confidence": safe_confidence(item.get("confidence")),
            "reason": item.get("reason", ""),
            "model": normalized_model,
        }

    return final_map


__all__ = [
    "normalize_model_name",
    "parse_json_response",
    "parse_batch_response",
    "build_result_map",
]


_KOREAN_QUANTITY = re.compile(
    r"(?:[영공일이삼사오육칠팔구십백천만억조수]+|한|두|세|네|다섯|여섯|일곱|여덟|아홉|열|몇)"
    r"\s*[십백천만억조]*\s*(?:원|달러|유로|엔|위안|퍼센트|배|점)"
)


def validate_jongga_results(*, results: Dict[str, Dict], items: List[Dict]) -> Dict[str, Dict]:
    """모델 정성 설명을 검사한 뒤 코드가 계산한 원자료 수치만 붙인다."""
    from engine.llm_analyzer_formatters import (
        extract_stock_info, _format_trading_value_eok, _resolve_jongga_supply_text,
    )
    expected = {extract_stock_info(item["stock"])[0]: item for item in items}
    if set(results) != set(expected) or len(expected) != len(items):
        raise LLMResponseParseError("", "종가 응답의 종목 누락/중복/불일치")
    checked = {}
    for name, result in results.items():
        reason = result.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise LLMResponseParseError("", "종가 분석 근거 없음")
        sections = re.findall(r"([①②③④⑤])\s*([^:：\n]{1,24})[:：]([^①②③④⑤]+)", reason)
        if ([part[0] for part in sections] != list("①②③④⑤")
                or len(reason) < 350 or any(len(part[2].strip()) < 60 for part in sections)):
            raise LLMResponseParseError("", "종가 설명의 필수 섹션/내용이 불완전함")
        prose = re.sub(
            r"[①②③④⑤](?=\s*(?:뉴스|거래|수급|리스크|위험|매매|전략)[^:：\n]{0,24}[:：])", "", reason,
        )
        if (any(char.isnumeric() for char in prose) or any(char in prose for char in "%％₩￦")
                or _KOREAN_QUANTITY.search(prose)):
            raise LLMResponseParseError("", "정성 설명에 검증되지 않은 수치가 포함됨")
        item = expected[name]
        _, _, price, _, trading = extract_stock_info(item["stock"])
        facts = (
            f"\n[원자료 수치] 현재가: {int(price):,}원; "
            f"거래대금: {_format_trading_value_eok(trading)} ({int(trading):,}원); "
            f"{_resolve_jongga_supply_text(item)}. "
            "손절·목표가는 화면의 시스템 계산값을 따릅니다."
        )
        checked[name] = {**result, "reason": reason.strip() + facts}
    return checked
