#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM Analyzer 응답 파서 모듈.
"""

from __future__ import annotations

import json
import re
from typing import Dict, List, Optional


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
            "confidence": item.get("confidence", 0),
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
