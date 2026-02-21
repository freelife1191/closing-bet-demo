#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
챗봇 응답 마크다운 정규화/스트리밍 파싱 유틸
"""

import re
from typing import List, Tuple


REASONING_START_REGEX = re.compile(
    r"(?:\*\*|__)?\**\[\s*추론\s*과정\s*\]\**(?:\*\*|__)?",
    re.IGNORECASE,
)
ANSWER_HEADER_REGEX = re.compile(
    # Allow inline "[답변]" markers as some model outputs place it on the same line.
    r"(?:---|___|\*\*\*)?\s*(?:\*\*|__)?\**\[\s*답변\s*\]\**(?:\*\*|__)?\s*\n?",
    re.IGNORECASE,
)
REASONING_HEADER_REGEX = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:\*\*|__)?\\?\[\s*추론\s*과정\s*\\?\](?:\*\*|__)?\s*\n?",
    re.IGNORECASE,
)
DOUBLE_ASTERISK_MARKER_REGEX = re.compile(r"(?<!\*)\*\*(?!\*)")
DOUBLE_UNDERSCORE_MARKER_REGEX = re.compile(r"(?<!_)__(?!_)")


def _remove_last_unmatched_marker(line: str, marker_regex: re.Pattern[str], marker_length: int) -> str:
    """라인 내 강조 마커 개수가 홀수면 마지막 마커를 제거한다."""
    matches = list(marker_regex.finditer(line))
    if len(matches) % 2 == 1:
        last = matches[-1]
        return line[:last.start()] + line[last.start() + marker_length :]
    return line


def _normalize_markdown_text(text: str) -> str:
    """LLM 응답에서 자주 깨지는 마크다운 문법 정규화"""
    if not text:
        return text

    normalized = text.replace("\r\n", "\n")

    # Remove accidental marker noise before ordered list starts (e.g. "****1. ")
    normalized = re.sub(r"^\s*\*{3,}(?=\d+[.)]\s)", "", normalized, flags=re.MULTILINE)

    # Split section labels and first ordered item when they are stuck together.
    normalized = re.sub(r"((?:\*\*|__)?\[[^\]\n]{1,20}\](?:\*\*|__)?)\s*(?=[1-9]\d?[.)])", r"\1\n", normalized)

    # Ensure a space after ordered-list markers (e.g. "1.조선", "1.**제목**")
    normalized = re.sub(r"(?<!\d)([1-9]\d?[.)])(?=\*\*|__|[가-힣A-Za-z(])", r"\1 ", normalized)

    # Ensure emphasis opening marker is separated from previous word.
    # Apply only when marker is followed by a real token start, not punctuation (e.g. avoid turning "**텍스트**:" into "**텍스트 **:")
    normalized = re.sub(r"([가-힣A-Za-z0-9])(?=(\*\*|__)\s*[가-힣A-Za-z0-9(])", r"\1 ", normalized)

    # Trim inner spaces in emphasis markers (covers both-sided or one-sided spaces).
    normalized = re.sub(
        r"\*\*([^*\n]+)\*\*",
        lambda m: f"**{m.group(1).strip()}**" if m.group(1).strip() else m.group(0),
        normalized,
    )
    normalized = re.sub(
        r"__([^_\n]+)__",
        lambda m: f"__{m.group(1).strip()}__" if m.group(1).strip() else m.group(0),
        normalized,
    )

    # Remove a last unmatched emphasis marker in each line (e.g. trailing ".**").
    balanced_lines: List[str] = []
    for line in normalized.split("\n"):
        line = _remove_last_unmatched_marker(line, DOUBLE_ASTERISK_MARKER_REGEX, 2)
        line = _remove_last_unmatched_marker(line, DOUBLE_UNDERSCORE_MARKER_REGEX, 2)
        balanced_lines.append(line)
    normalized = "\n".join(balanced_lines)

    # Normalize quoted emphasis wrappers: **\"text\"** / **'text'** -> **text**
    normalized = re.sub(r"\*\*\s*['\"“”‘’]\s*([^*\n]+?)\s*['\"“”‘’]\s*\*\*", r"**\1**", normalized)
    normalized = re.sub(r"__\s*['\"“”‘’]\s*([^_\n]+?)\s*['\"“”‘’]\s*__", r"__\1__", normalized)

    # Ensure spacing after closing emphasis marker when attached to text.
    normalized = re.sub(r"(?<=\S)(\*\*|__)(?=[가-힣A-Za-z0-9])", r"\1 ", normalized)

    # Prevent CJK boundary collapse without crossing lines/other emphasis spans
    normalized = re.sub(r"\*\*([A-Za-z0-9가-힣(][^*\n]*?)\*\*([가-힣])", r"**\1** \2", normalized)
    normalized = re.sub(r"__([A-Za-z0-9가-힣(][^_\n]*?)__([가-힣])", r"__\1__ \2", normalized)

    return normalized


def _extract_reasoning_and_answer(text: str, is_streaming: bool = False) -> Tuple[str, str]:
    """[추론 과정]/[답변] 블록을 분리해 reasoning, answer 텍스트를 반환한다."""
    if not text:
        return "", ""

    processed = text
    reasoning = ""

    start_match = REASONING_START_REGEX.search(processed)
    end_match = ANSWER_HEADER_REGEX.search(
        processed,
        start_match.end() if start_match else 0,
    )

    if start_match:
        start_idx = start_match.start()
        if end_match and end_match.start() >= start_idx:
            reasoning = processed[start_idx:end_match.start()]
            processed = processed[:start_idx] + processed[end_match.end() :]
        elif is_streaming:
            # 스트리밍 중 [답변] 헤더가 아직 오지 않았다면 이후 텍스트는 추론으로 본다.
            reasoning = processed[start_idx:]
            processed = processed[:start_idx]
        else:
            # 최종 응답에서 [답변] 헤더가 누락된 경우,
            # 전체 텍스트를 답변으로 간주해 빈 답변이 되지 않게 한다.
            reasoning = ""
            processed = text
    else:
        processed = ANSWER_HEADER_REGEX.sub("", processed)
        if is_streaming:
            stripped = processed.strip()
            # Early stream often starts with an incomplete "[추론 과정]" header (e.g. "**[추").
            # Hold until header is complete to avoid flashing broken marker text in the answer area.
            if (
                0 < len(stripped) < 40
                and (
                    stripped.startswith("[")
                    or stripped.startswith("\\[")
                    or stripped.startswith("*[")
                    or stripped.startswith("**[")
                    or stripped.startswith("__[")
                )
            ):
                return "", ""

    reasoning = REASONING_HEADER_REGEX.sub("", reasoning, count=1).strip()
    processed = ANSWER_HEADER_REGEX.sub("", processed).strip()

    if is_streaming:
        reasoning = re.sub(r"[\*\_\[\]]+$", "", reasoning)
        processed = re.sub(r"[\*\_\[\]]+$", "", processed)

    return reasoning, processed


def _compute_stream_delta(previous: str, current: str) -> Tuple[bool, str]:
    """
    이전/현재 텍스트를 비교해 델타를 계산한다.
    returns: (reset_needed, delta_text)
    """
    if current.startswith(previous):
        return False, current[len(previous) :]
    return True, current

