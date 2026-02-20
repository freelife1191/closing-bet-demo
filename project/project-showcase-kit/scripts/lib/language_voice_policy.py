#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Language selection and speaker policy helpers."""

from __future__ import annotations

import re
from typing import Dict, List

from kr_text_policy import parse_language_codes


DEFAULT_LANGUAGE_SELECTION = "ko+en"
DEFAULT_FALLBACK_SPEAKER = "Vivian"
DEFAULT_SUPERTONIC_FALLBACK_SPEAKER = "Jessica"
SUPERTONIC_SUPPORTED_LANGUAGES = {"ko", "en"}
SPEAKER_BY_LANGUAGE: Dict[str, str] = {
    "ko": "Sohee",
    "en": "Serena",
    "ja": "Ono_Anna",
    "zh": "Vivian",
}
SUPERTONIC_SPEAKER_BY_LANGUAGE: Dict[str, str] = {
    "ko": "Sarah",
    "en": "Jessica",
}

_LEGACY_SCENE_TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "KR 마켓 패키지 데모를 시작합니다.": {
        "en": "Starting the KR market package demo.",
        "ja": "KRマーケットパッケージのデモを開始します。",
        "zh": "开始 KR 市场演示包演示。",
    },
    "Market Gate 결과와 AI 분석 요약을 빠르게 확인합니다.": {
        "en": "Quickly review the Market Gate results and AI analysis summary.",
        "ja": "Market Gate の結果と AI 分析要約を素早く確認します。",
        "zh": "快速查看 Market Gate 结果和 AI 分析摘要。",
    },
    "마지막으로 코스피와 코스닥 지표를 점검합니다.": {
        "en": "Finally, check the KOSPI and KOSDAQ indicators.",
        "ja": "最後にコスピとコスダックの指標を確認します。",
        "zh": "最后检查 KOSPI 和 KOSDAQ 指标。",
    },
}

_EN_FALLBACK_REPLACEMENTS: List[tuple[str, str]] = [
    ("Smart Money Bot은", "Smart Money Bot"),
    ("한국 주식", "Korean stock"),
    ("종가베팅", "closing bet"),
    ("누적 성과", "cumulative performance"),
    ("모의투자", "paper trading"),
    ("재분석", "re-analysis"),
    ("점수", "score"),
    ("등급", "grade"),
    ("시장", "market"),
    ("데이터", "data"),
    ("상태", "status"),
    ("알림", "alerts"),
    ("검증", "verification"),
    ("분석", "analysis"),
    ("플랫폼", "platform"),
    ("통합", "integrated"),
    ("시스템", "system"),
    ("운영", "operations"),
    ("자동", "automated"),
    ("화면", "screen"),
    ("강조", "highlight"),
    ("확인", "review"),
    ("흐름", "workflow"),
    ("전략", "strategy"),
    ("리스크", "risk"),
    ("성능", "performance"),
    ("실행", "execution"),
    ("장마감", "market close"),
    ("코스피", "KOSPI"),
    ("코스닥", "KOSDAQ"),
]


def default_language_selection() -> str:
    """Return default pipeline language expression."""
    return DEFAULT_LANGUAGE_SELECTION


def resolve_target_languages(language_expr: str) -> List[str]:
    """Resolve language expression to ordered short codes."""
    expression = language_expr.strip()
    if not expression:
        expression = DEFAULT_LANGUAGE_SELECTION
    codes = parse_language_codes(expression)
    if not codes:
        return parse_language_codes(DEFAULT_LANGUAGE_SELECTION)
    return codes


def _short_language_code(language_code: str) -> str:
    code = language_code.strip().lower() if language_code else ""
    return code.split("-", 1)[0] if code else ""


def is_supertonic_engine(engine: str) -> bool:
    return engine.strip().lower() == "supertonic-local"


def resolve_speaker(language_code: str, engine: str = "qwen-local-cmd") -> str:
    """Resolve speaker by language code with engine-aware policy."""
    short = _short_language_code(language_code)
    if is_supertonic_engine(engine):
        return SUPERTONIC_SPEAKER_BY_LANGUAGE.get(short, DEFAULT_SUPERTONIC_FALLBACK_SPEAKER)

    return SPEAKER_BY_LANGUAGE.get(short, DEFAULT_FALLBACK_SPEAKER)


def validate_supertonic_languages(language_codes: List[str]) -> None:
    """Validate Supertonic-only language policy (ko/en)."""
    unsupported = []
    for code in language_codes:
        short = _short_language_code(code)
        if short not in SUPERTONIC_SUPPORTED_LANGUAGES:
            unsupported.append(code)
    if unsupported:
        joined = ",".join(unsupported)
        raise ValueError(f"supertonic-local supports only ko/en, got: {joined}")


def resolve_supertonic_language(language_code: str) -> str:
    """Resolve supertonic-safe short language code."""
    short = _short_language_code(language_code)
    if short not in SUPERTONIC_SUPPORTED_LANGUAGES:
        return "en"
    return short


def resolve_qwen_language_speaker(language_code: str) -> str:
    """Backward-compatible alias for default(qwen) policy."""
    code = language_code.strip().lower() if language_code else ""
    short = code.split("-", 1)[0] if code else ""
    return SPEAKER_BY_LANGUAGE.get(short, DEFAULT_FALLBACK_SPEAKER)


def translate_legacy_scene_text(text: str, language_code: str) -> str:
    """
    Translate known legacy KR default scene narration to target language.

    Falls back to original text when no deterministic mapping exists.
    """
    source = text.strip()
    if not source:
        return source

    code = language_code.strip().lower().split("-", 1)[0] if language_code else "ko"
    if code == "ko":
        return source

    translations = _LEGACY_SCENE_TRANSLATIONS.get(source)
    if not translations:
        return source
    return translations.get(code, source)


def hangul_ratio(text: str) -> float:
    """Return Hangul character ratio among alpha-like characters."""
    letters = [ch for ch in text if ch.isalpha() or ("가" <= ch <= "힣")]
    if not letters:
        return 0.0
    hangul_count = sum(1 for ch in letters if "가" <= ch <= "힣")
    return hangul_count / float(len(letters))


def _strip_non_english_noise(text: str) -> str:
    updated = re.sub(r"[가-힣]+", " ", text)
    updated = re.sub(r"[ ]{2,}", " ", updated).strip()
    return updated


def fallback_english_narration(
    source_text: str,
    scene_id: str = "",
    screen: str = "",
    subtitle_cue: str = "",
) -> str:
    """
    Build deterministic English narration when direct translation is unavailable.

    This helper intentionally avoids Korean fallback to keep en scripts language-pure.
    """
    updated = source_text.strip()
    for source, target in _EN_FALLBACK_REPLACEMENTS:
        updated = updated.replace(source, target)
    updated = _strip_non_english_noise(updated)

    if not updated:
        scene_label = scene_id.strip() or "Scene"
        screen_hint = screen.strip() or "the dashboard"
        cue_hint = re.sub(r"[^A-Za-z0-9 .,+\-/]", " ", subtitle_cue)
        cue_hint = re.sub(r"\s+", " ", cue_hint).strip()
        if cue_hint:
            updated = f"{scene_label} highlights {cue_hint} on {screen_hint}."
        else:
            updated = f"{scene_label} highlights Smart Money Bot workflows on {screen_hint}."

    if "Smart Money Bot" not in updated:
        updated = f"Smart Money Bot: {updated}"
    if updated and updated[-1] not in {".", "!", "?"}:
        updated = f"{updated}."
    return updated


def override_command_flag(command: str, flag: str, value: str) -> str:
    """
    Override simple CLI flag in a shell command string.

    Example:
    - "--speaker Sohee" -> "--speaker Serena"
    - missing flag -> append "--speaker Serena"
    """
    escaped_flag = re.escape(flag)
    pattern = rf"({escaped_flag}\s+)(\"[^\"]+\"|'[^']+'|[^\s]+)"
    replacement = rf"\1{value}"
    updated, count = re.subn(pattern, replacement, command, count=1)
    if count > 0:
        return updated
    suffix = f" {flag} {value}"
    return f"{command}{suffix}"
