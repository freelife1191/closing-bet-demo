#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
챗봇 마크다운 파서/정규화 유틸.
"""

from __future__ import annotations

import re


_HEADER_DECORATOR = r"(?:\*{1,2}|_{1,2})?"
_OPEN_BRACKET = r"(?:\\?\[)"
_CLOSE_BRACKET = r"(?:\\?\])"

REASONING_START_REGEX = re.compile(
    rf"{_HEADER_DECORATOR}\s*{_OPEN_BRACKET}\s*추론\s*과정\s*{_CLOSE_BRACKET}\s*{_HEADER_DECORATOR}",
    re.IGNORECASE,
)
ANSWER_HEADER_REGEX = re.compile(
    rf"{_HEADER_DECORATOR}\s*{_OPEN_BRACKET}\s*답변\s*{_CLOSE_BRACKET}\s*{_HEADER_DECORATOR}",
    re.IGNORECASE,
)


def _normalize_markdown_text(text: str | None) -> str:
    """응답/히스토리 저장 전 공통 마크다운 정규화."""
    raw = str(text or "")
    normalized = raw.replace("\r\n", "\n").replace("\r", "\n")
    normalized = "\n".join(line.rstrip() for line in normalized.split("\n"))
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized


def _extract_reasoning_and_answer(text: str, is_streaming: bool = False) -> tuple[str, str]:
    """[추론 과정]/[답변] 헤더 기반으로 추론/답변을 분리한다."""
    normalized = _normalize_markdown_text(text).strip()
    if not normalized:
        return "", ""

    reasoning_match = REASONING_START_REGEX.search(normalized)
    answer_match = ANSWER_HEADER_REGEX.search(normalized)

    if reasoning_match and answer_match and reasoning_match.start() <= answer_match.start():
        reasoning = normalized[reasoning_match.end() : answer_match.start()].strip()
        answer = normalized[answer_match.end() :].strip()
        return reasoning, answer

    if reasoning_match and not answer_match:
        if is_streaming:
            reasoning = normalized[reasoning_match.end() :].strip()
            return reasoning, ""
        # non-stream에서는 헤더 파손/부분 응답 가능성을 고려해 전체를 답변으로 취급
        return "", normalized

    if answer_match:
        answer = normalized[answer_match.end() :].strip()
        return "", answer

    return "", normalized


def _compute_stream_delta(previous_text: str, current_text: str) -> tuple[bool, str]:
    """
    스트리밍 텍스트 증분 계산.
    Returns: (reset_required, delta_text)
    """
    prev = str(previous_text or "")
    curr = str(current_text or "")

    if curr == prev:
        return False, ""
    if curr.startswith(prev):
        return False, curr[len(prev) :]
    return True, curr


__all__ = [
    "ANSWER_HEADER_REGEX",
    "REASONING_START_REGEX",
    "_compute_stream_delta",
    "_extract_reasoning_and_answer",
    "_normalize_markdown_text",
]
