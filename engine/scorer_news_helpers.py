#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scorer 뉴스 관련 문자열 헬퍼.
"""

from __future__ import annotations

import re
from functools import lru_cache


_NON_ALNUM_KO_RE = re.compile(r"[^0-9A-Za-z가-힣]")
_PREFERRED_STOCK_SUFFIX_RE = re.compile(r"(?:[0-9]+)?우(?:[a-z])?$", re.IGNORECASE)


@lru_cache(maxsize=16_384)
def normalize_news_text(text: str) -> str:
    """종목명/뉴스 제목 매칭용 텍스트 정규화."""
    if not text:
        return ""
    return _NON_ALNUM_KO_RE.sub("", str(text)).lower()


@lru_cache(maxsize=4_096)
def build_stock_aliases(stock_name: str) -> tuple[str, ...]:
    """우선주 접미사 등을 제거한 종목명 별칭 집합 생성."""
    normalized = normalize_news_text(stock_name)
    if not normalized:
        return ()

    aliases = {normalized}
    preferred_base = _PREFERRED_STOCK_SUFFIX_RE.sub("", normalized)
    if preferred_base:
        aliases.add(preferred_base)

    if normalized.endswith("우") and len(normalized) > 1:
        aliases.add(normalized[:-1])

    filtered = [alias for alias in aliases if len(alias) >= 2]
    filtered.sort()
    return tuple(filtered)
