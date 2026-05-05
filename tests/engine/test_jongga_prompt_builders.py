#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""closing-bet(jongga) 전용 batch prompt / stocks_text 빌더 단위 테스트."""

from __future__ import annotations

import pytest

from engine.llm_analyzer_formatters import build_jongga_stocks_text
from engine.llm_analyzer_prompts import build_jongga_batch_prompt


def _signal_fixture(*, name: str, code: str, change_pct: float, trading_value: float, score_total: int) -> dict:
    return {
        "stock_code": code,
        "stock_name": name,
        "current_price": 50_000,
        "change_pct": change_pct,
        "trading_value": trading_value,
        "score": {
            "total": score_total,
            "news": 2,
            "volume": 3,
            "chart": 2,
            "candle": 1,
            "timing": 1,
            "supply": 2,
        },
        "score_details": {
            "news": 2,
            "volume": 3,
            "chart": 2,
            "candle": 1,
            "consolidation": 1,
            "supply": 2,
            "bonus_score": 3,
            "bonus_breakdown": {"volume": 2, "candle": 1, "limit_up": 0},
            "foreign_net_buy": 50_000_000_000,
            "inst_net_buy": 30_000_000_000,
            "volume_ratio": 4.5,
            "is_new_high": True,
            "is_limit_up": False,
        },
        "news_items": [
            {"title": "테스트 호재 뉴스 A", "weight": 1.5},
            {"title": "테스트 뉴스 B", "weight": 1.0},
        ],
    }


def _make_items(signals: list[dict]) -> list[dict]:
    items = []
    for sig in signals:
        items.append({
            "stock": sig,
            "news": sig.get("news_items", []),
            "supply": {
                "foreign_buy_5d": sig["score_details"]["foreign_net_buy"],
                "inst_buy_5d": sig["score_details"]["inst_net_buy"],
            },
        })
    return items


# ---------------------------------------------------------------------------
# build_jongga_stocks_text
# ---------------------------------------------------------------------------

class TestBuildJonggaStocksText:
    def test_renders_stock_header(self):
        sig = _signal_fixture(
            name="삼성전자", code="005930",
            change_pct=8.06572, trading_value=8_358_799_527_000,
            score_total=11,
        )
        text = build_jongga_stocks_text(_make_items([sig]))
        assert "삼성전자 (005930)" in text

    def test_omits_vcp_metadata(self):
        """jongga 텍스트에는 VCP 점수/수축 비율을 절대 포함하지 않는다."""
        sig = _signal_fixture(
            name="삼성전자", code="005930",
            change_pct=8.0, trading_value=1_000_000_000_000,
            score_total=11,
        )
        text = build_jongga_stocks_text(_make_items([sig]))
        assert "VCP 점수" not in text
        assert "수축 비율" not in text
        assert "Contraction" not in text

    def test_change_pct_two_decimal(self):
        """등락률은 소수점 2자리로 포맷."""
        sig = _signal_fixture(
            name="삼성전자", code="005930",
            change_pct=8.06572068707991, trading_value=1_000_000_000_000,
            score_total=11,
        )
        text = build_jongga_stocks_text(_make_items([sig]))
        assert "8.07%" in text
        assert "8.06572068707991" not in text

    def test_trading_value_clean_format(self):
        """거래대금은 정수 억원으로 포맷되어야 한다."""
        sig = _signal_fixture(
            name="삼성전자", code="005930",
            change_pct=1.0, trading_value=8_358_799_527_000,
            score_total=11,
        )
        text = build_jongga_stocks_text(_make_items([sig]))
        # 8,358,799,527,000원 → 83,587 또는 83,588억원 (소수점 .0 없음)
        assert ("83,587억원" in text) or ("83,588억원" in text)
        assert ".0억원" not in text

    def test_includes_score_breakdown(self):
        """점수 분해(뉴스/거래량/차트/캔들/조정/수급 + 가산점)를 모두 포함."""
        sig = _signal_fixture(
            name="삼성전자", code="005930",
            change_pct=8.0, trading_value=1_000_000_000_000,
            score_total=11,
        )
        text = build_jongga_stocks_text(_make_items([sig]))
        assert "11" in text  # 총점
        assert "19" in text  # 만점
        # 분해 점수 라벨이 있어야 함
        assert "뉴스" in text
        assert "거래" in text
        assert "차트" in text
        assert "수급" in text

    def test_includes_supply_text(self):
        """수급 정보 텍스트 포함 (외인/기관 5일 합)."""
        sig = _signal_fixture(
            name="삼성전자", code="005930",
            change_pct=8.0, trading_value=1_000_000_000_000,
            score_total=11,
        )
        text = build_jongga_stocks_text(_make_items([sig]))
        # 50,000,000,000 = 500억
        assert "외인" in text
        assert "기관" in text
        assert "N/A" not in text

    def test_supply_none_falls_back_to_score_details(self):
        """supply가 None이어도 score_details에서 외인/기관 정보를 추출해야 한다."""
        sig = _signal_fixture(
            name="삼성전자", code="005930",
            change_pct=8.0, trading_value=1_000_000_000_000,
            score_total=11,
        )
        items = [{"stock": sig, "news": sig["news_items"], "supply": None}]
        text = build_jongga_stocks_text(items)
        assert "외인" in text
        assert "기관" in text

    def test_includes_news_titles(self):
        sig = _signal_fixture(
            name="삼성전자", code="005930",
            change_pct=8.0, trading_value=1_000_000_000_000,
            score_total=11,
        )
        text = build_jongga_stocks_text(_make_items([sig]))
        assert "테스트 호재 뉴스 A" in text
        assert "테스트 뉴스 B" in text

    def test_handles_multiple_stocks(self):
        sig1 = _signal_fixture(
            name="삼성전자", code="005930",
            change_pct=8.0, trading_value=1_000_000_000_000,
            score_total=11,
        )
        sig2 = _signal_fixture(
            name="SK하이닉스", code="000660",
            change_pct=5.0, trading_value=500_000_000_000,
            score_total=8,
        )
        text = build_jongga_stocks_text(_make_items([sig1, sig2]))
        assert "삼성전자" in text
        assert "SK하이닉스" in text


# ---------------------------------------------------------------------------
# build_jongga_batch_prompt
# ---------------------------------------------------------------------------

class TestBuildJonggaBatchPrompt:
    def test_no_vcp_directive(self):
        """jongga 프롬프트는 VCP 강제 평가 지시를 포함하지 않는다."""
        sig = _signal_fixture(
            name="삼성전자", code="005930",
            change_pct=8.0, trading_value=1_000_000_000_000,
            score_total=11,
        )
        prompt = build_jongga_batch_prompt(items=_make_items([sig]), market_status=None)
        # 절대 들어가면 안 되는 문구
        assert "VCP(변동성 수축 패턴)의 기술적 완성도를 반드시 평가에 포함" not in prompt
        assert "변동성 수축이 0.1~0.5" not in prompt
        # closing-bet은 19점 만점 종가베팅임을 명시해야 함
        assert "종가베팅" in prompt
        assert "19" in prompt

    def test_requires_min_reason_length(self):
        """reason 최소 길이(전체 350자, 섹션 60자 이상)를 명시적으로 강제."""
        sig = _signal_fixture(
            name="삼성전자", code="005930",
            change_pct=8.0, trading_value=1_000_000_000_000,
            score_total=11,
        )
        prompt = build_jongga_batch_prompt(items=_make_items([sig]), market_status=None)
        assert "350" in prompt  # 전체 길이 강제 문구
        assert "60" in prompt   # 섹션별 길이 강제 문구
        assert "reason" in prompt.lower()

    def test_demands_five_sections(self):
        """reason이 5개 섹션을 모두 포함하도록 명시."""
        sig = _signal_fixture(
            name="삼성전자", code="005930",
            change_pct=8.0, trading_value=1_000_000_000_000,
            score_total=11,
        )
        prompt = build_jongga_batch_prompt(items=_make_items([sig]), market_status=None)
        # 5개 섹션 키워드
        for keyword in ["뉴스", "거래", "수급", "리스크", "전략"]:
            assert keyword in prompt

    def test_response_schema_unchanged(self):
        """기존 JSON 응답 스키마는 호환을 위해 동일 (name/score/action/confidence/reason)."""
        sig = _signal_fixture(
            name="삼성전자", code="005930",
            change_pct=8.0, trading_value=1_000_000_000_000,
            score_total=11,
        )
        prompt = build_jongga_batch_prompt(items=_make_items([sig]), market_status=None)
        for key in ['"name"', '"score"', '"action"', '"confidence"', '"reason"']:
            assert key in prompt
        assert "BUY" in prompt and "HOLD" in prompt and "SELL" in prompt

    def test_includes_market_context_when_provided(self):
        sig = _signal_fixture(
            name="삼성전자", code="005930",
            change_pct=8.0, trading_value=1_000_000_000_000,
            score_total=11,
        )
        market_status = {"status": "BULL", "total_score": 75, "kospi_close": 2900, "kospi_change": 1.2}
        prompt = build_jongga_batch_prompt(items=_make_items([sig]), market_status=market_status)
        assert "BULL" in prompt or "75" in prompt
