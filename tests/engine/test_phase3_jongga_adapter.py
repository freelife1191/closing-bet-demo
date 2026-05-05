#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phase3 → jongga 어댑터 단위 테스트.

매일 종가베팅 생성 파이프라인의 Phase3 입력을 reanalyze 입력과
동일한 dict 형태로 변환하는 어댑터(_adapt_to_jongga_signal)의 명세를
검증한다. formatter(build_jongga_stocks_text)와 결합하여 최종
프롬프트 텍스트가 깨지지 않는지도 함께 본다.
"""

from __future__ import annotations

from engine.models import ScoreDetail, StockData, SupplyData
from engine.phases_news_llm import _adapt_to_jongga_signal
from engine.llm_analyzer_formatters import build_jongga_stocks_text


def _stock(code: str = "005930", name: str = "삼성전자") -> StockData:
    return StockData(
        code=code,
        name=name,
        market="KOSPI",
        sector="전기전자",
        close=80_000,
        change_pct=8.07,
        trading_value=8_358_799_527_000,
        volume=10_000_000,
        marcap=500_000_000_000_000,
        high_52w=90_000,
        low_52w=60_000,
    )


def _supply() -> SupplyData:
    return SupplyData(foreign_buy_5d=50_000_000_000, inst_buy_5d=30_000_000_000)


def _pre_score() -> ScoreDetail:
    return ScoreDetail(total=11, news=2, volume=3, chart=2, candle=1, timing=1, supply=2)


def _score_details() -> dict:
    return {
        "foreign_net_buy": 50_000_000_000,
        "inst_net_buy": 30_000_000_000,
        "bonus_breakdown": {"volume": 2, "candle": 1, "limit_up": 0},
        "volume_ratio": 4.5,
        "is_new_high": True,
        "is_limit_up": False,
    }


def _phase2_item(*, supply=None) -> dict:
    """Phase1Analyzer + Phase2NewsCollector 결과 한 종목 분량."""
    return {
        "stock": _stock(),
        "charts": object(),
        "supply": _supply() if supply is None else supply,
        "pre_score": _pre_score(),
        "score_details": _score_details(),
        "temp_grade": "B",
        "vcp": None,
        "news": [
            {"title": "테스트 호재 뉴스 A", "weight": 1.5},
            {"title": "테스트 뉴스 B", "weight": 1.0},
        ],
    }


# ---------------------------------------------------------------------------
# shape contract
# ---------------------------------------------------------------------------

class TestAdapterShape:
    def test_top_level_keys(self):
        out = _adapt_to_jongga_signal(_phase2_item())
        assert set(out.keys()) >= {"stock", "news", "supply"}

    def test_stock_is_dict_with_required_fields(self):
        out = _adapt_to_jongga_signal(_phase2_item())
        stock = out["stock"]
        assert isinstance(stock, dict)
        # reanalyze 입력에서 사용하는 필드들
        for key in (
            "stock_code",
            "stock_name",
            "current_price",
            "change_pct",
            "trading_value",
            "score",
            "score_details",
        ):
            assert key in stock, f"missing {key}"

    def test_stock_identity_mapped(self):
        out = _adapt_to_jongga_signal(_phase2_item())
        assert out["stock"]["stock_code"] == "005930"
        assert out["stock"]["stock_name"] == "삼성전자"

    def test_price_change_trading_value_mapped(self):
        out = _adapt_to_jongga_signal(_phase2_item())
        assert out["stock"]["current_price"] == 80_000
        assert out["stock"]["change_pct"] == 8.07
        assert out["stock"]["trading_value"] == 8_358_799_527_000


# ---------------------------------------------------------------------------
# score / score_details preservation
# ---------------------------------------------------------------------------

class TestScorePreservation:
    def test_pre_score_six_fields_mapped(self):
        out = _adapt_to_jongga_signal(_phase2_item())
        score = out["stock"]["score"]
        assert score == {
            "total": 11,
            "news": 2,
            "volume": 3,
            "chart": 2,
            "candle": 1,
            "timing": 1,
            "supply": 2,
        }

    def test_score_details_kept_intact(self):
        out = _adapt_to_jongga_signal(_phase2_item())
        details = out["stock"]["score_details"]
        # foreign_net_buy / inst_net_buy / bonus_breakdown 모두 유지
        assert details["foreign_net_buy"] == 50_000_000_000
        assert details["inst_net_buy"] == 30_000_000_000
        assert details["bonus_breakdown"] == {"volume": 2, "candle": 1, "limit_up": 0}

    def test_missing_pre_score_fills_zero(self):
        item = _phase2_item()
        item.pop("pre_score")
        out = _adapt_to_jongga_signal(item)
        score = out["stock"]["score"]
        assert score["total"] == 0
        assert score["news"] == 0
        assert score["supply"] == 0

    def test_missing_score_details_yields_empty_dict(self):
        item = _phase2_item()
        item.pop("score_details")
        out = _adapt_to_jongga_signal(item)
        assert out["stock"]["score_details"] == {}


# ---------------------------------------------------------------------------
# supply mapping & fallback
# ---------------------------------------------------------------------------

class TestSupplyMapping:
    def test_supply_object_to_dict(self):
        out = _adapt_to_jongga_signal(_phase2_item())
        assert out["supply"] == {
            "foreign_buy_5d": 50_000_000_000,
            "inst_buy_5d": 30_000_000_000,
        }

    def test_supply_none_falls_back_to_score_details(self):
        item = _phase2_item(supply=False)  # supply=False sentinel
        # supply=False 는 falsy → 어댑터는 score_details 폴백 사용
        item["supply"] = None
        out = _adapt_to_jongga_signal(item)
        assert out["supply"]["foreign_buy_5d"] == 50_000_000_000
        assert out["supply"]["inst_buy_5d"] == 30_000_000_000

    def test_supply_and_score_details_both_missing_yields_zero(self):
        item = _phase2_item()
        item["supply"] = None
        item["score_details"] = {}
        out = _adapt_to_jongga_signal(item)
        assert out["supply"]["foreign_buy_5d"] == 0
        assert out["supply"]["inst_buy_5d"] == 0


# ---------------------------------------------------------------------------
# news passthrough
# ---------------------------------------------------------------------------

class TestNewsPassthrough:
    def test_news_list_passes_through(self):
        out = _adapt_to_jongga_signal(_phase2_item())
        assert len(out["news"]) == 2
        assert out["news"][0]["title"] == "테스트 호재 뉴스 A"

    def test_news_missing_yields_empty_list(self):
        item = _phase2_item()
        item.pop("news")
        out = _adapt_to_jongga_signal(item)
        assert out["news"] == []


# ---------------------------------------------------------------------------
# golden integration test: adapter ∘ formatter
# ---------------------------------------------------------------------------

class TestAdapterFormatterIntegration:
    """어댑터 결과를 build_jongga_stocks_text에 통과시켜 LLM 입력 텍스트가
    제대로 채워지는지 확인. 0/19 같은 빈 점수가 나오면 어댑터 고장."""

    def test_text_contains_real_score_breakdown(self):
        adapted = _adapt_to_jongga_signal(_phase2_item())
        text = build_jongga_stocks_text([adapted])
        # 점수 헤더: 11 / 19점
        assert "11 / 19점" in text
        # 분해
        assert "뉴스 2/3" in text
        assert "거래대금 3/3" in text
        assert "차트 2/2" in text
        assert "수급 2/2" in text
        assert "캔들 1/1" in text
        assert "조정 1/1" in text
        # 가산점
        assert "가산점 3/7" in text

    def test_text_does_not_collapse_to_zero(self):
        adapted = _adapt_to_jongga_signal(_phase2_item())
        text = build_jongga_stocks_text([adapted])
        assert "0 / 19점" not in text
        assert "뉴스 0/3" not in text

    def test_text_omits_vcp_metadata(self):
        adapted = _adapt_to_jongga_signal(_phase2_item())
        text = build_jongga_stocks_text([adapted])
        assert "VCP 점수" not in text
        assert "수축 비율" not in text
        assert "Contraction" not in text

    def test_text_includes_supply_real_numbers(self):
        adapted = _adapt_to_jongga_signal(_phase2_item())
        text = build_jongga_stocks_text([adapted])
        assert "외인" in text
        assert "기관" in text
        assert "정보 없음" not in text
        # 50,000,000,000 원이 포맷팅되어 등장
        assert "50,000,000,000" in text

    def test_text_includes_news_titles(self):
        adapted = _adapt_to_jongga_signal(_phase2_item())
        text = build_jongga_stocks_text([adapted])
        assert "테스트 호재 뉴스 A" in text
        assert "테스트 뉴스 B" in text

    def test_handles_multiple_items(self):
        item1 = _phase2_item()
        item2 = _phase2_item()
        item2["stock"] = StockData(
            code="000660",
            name="SK하이닉스",
            market="KOSPI",
            sector="반도체",
            close=200_000,
            change_pct=5.0,
            trading_value=500_000_000_000,
            volume=2_000_000,
            marcap=150_000_000_000_000,
            high_52w=250_000,
            low_52w=150_000,
        )
        adapted = [_adapt_to_jongga_signal(item1), _adapt_to_jongga_signal(item2)]
        text = build_jongga_stocks_text(adapted)
        assert "삼성전자 (005930)" in text
        assert "SK하이닉스 (000660)" in text
