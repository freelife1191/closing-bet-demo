#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[CHAT-031] 시스템 프롬프트의 시장·섹터 절을 고정 입력으로 대조하는 회귀 테스트
"""

from chatbot.prompts import build_system_prompt


def _prompt() -> str:
    return build_system_prompt(
        market_data={
            "kospi": 7110.759765625,
            "kosdaq": 843.239990234375,
            "usd_krw": 1360.1800537109375,
            "market_gate": "YELLOW",
            "as_of": "2026-09-22",
        },
        sector_scores={"반도체": 2.93, "자동차": -1.2, "바이오": 0.0},
        vcp_data=[],
    )


def test_build_system_prompt_market_section_names_the_as_of_date_and_rounds_indices():
    assert (
        "## 시장 현황 (Market Gate 기준 2026-09-22)\n"
        "- **KOSPI**: 7,110.76\n"
        "- **KOSDAQ**: 843.24\n"
        "- **환율**: 1,360원\n"
        "- **Market Gate**: 🟡 YELLOW\n"
    ) in _prompt()


def test_build_system_prompt_sector_section_is_signed_percent_not_score():
    prompt = _prompt()
    assert (
        "## 섹터 등락률 (Market Gate)\n"
        "🟢 반도체: +2.93%\n"
        "⚪ 바이오: +0.00%\n"
        "🔴 자동차: -1.20%\n"
    ) in prompt
    assert "섹터별 점수" not in prompt
    assert "2.93점" not in prompt


def test_build_system_prompt_market_section_without_as_of_keeps_plain_title():
    prompt = build_system_prompt(market_data={"kospi": "2600.00", "market_gate": "GREEN"})
    assert "## 시장 현황\n- **KOSPI**: 2600.00\n" in prompt
