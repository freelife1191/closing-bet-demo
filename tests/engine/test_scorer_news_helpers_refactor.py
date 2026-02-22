#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scorer 뉴스 헬퍼 리팩토링 회귀 테스트
"""

from __future__ import annotations

from engine.scorer_news_helpers import build_stock_aliases, normalize_news_text


def test_normalize_news_text_keeps_korean_english_number_only():
    assert normalize_news_text(" 삼성전자! 2분기, 실적↑ ") == "삼성전자2분기실적"
    assert normalize_news_text("") == ""


def test_build_stock_aliases_handles_preferred_stock_suffix():
    aliases = set(build_stock_aliases("한화솔루션우"))
    assert "한화솔루션우" in aliases
    assert "한화솔루션" in aliases


def test_build_stock_aliases_cache_returns_stable_tuple():
    first = build_stock_aliases("삼성전자")
    second = build_stock_aliases("삼성전자")
    assert first == second
