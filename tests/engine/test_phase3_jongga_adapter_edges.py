#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phase3 → jongga 어댑터 엣지 케이스 회귀 테스트.

기본 happy path는 test_phase3_jongga_adapter.py가 잠그고,
이 파일은 비표준/방어적 입력(dict-shape stock, dict supply, None,
문자열 숫자, news가 없는 경우 등)에 대한 견고성을 잠근다.
"""

from __future__ import annotations

from engine.models import StockData, SupplyData, ScoreDetail
from engine.phases_news_llm import _adapt_to_jongga_signal


def _stock_obj() -> StockData:
    return StockData(
        code="005930",
        name="삼성전자",
        market="KOSPI",
        sector="전기전자",
        close=80_000,
        change_pct=8.07,
        trading_value=8_358_799_527_000,
        volume=10_000_000,
    )


# ---------------------------------------------------------------------------
# stock이 dict로 들어와도 손실 없이 매핑되어야 함
# ---------------------------------------------------------------------------

class TestStockDictPassthrough:
    """일부 호출 경로(테스트, 외부 통합)는 stock을 dict로 넘길 수 있다.
    어댑터는 두 입력 shape를 모두 흡수해야 한다."""

    def _dict_stock(self) -> dict:
        return {
            "code": "005930",
            "name": "삼성전자",
            "close": 80_000,
            "change_pct": 8.07,
            "trading_value": 8_358_799_527_000,
        }

    def test_stock_dict_identity_mapped(self):
        item = {"stock": self._dict_stock(), "pre_score": None, "news": []}
        out = _adapt_to_jongga_signal(item)
        assert out["stock"]["stock_code"] == "005930"
        assert out["stock"]["stock_name"] == "삼성전자"

    def test_stock_dict_price_change_value_mapped(self):
        item = {"stock": self._dict_stock(), "pre_score": None, "news": []}
        out = _adapt_to_jongga_signal(item)
        assert out["stock"]["current_price"] == 80_000
        assert out["stock"]["change_pct"] == 8.07
        assert out["stock"]["trading_value"] == 8_358_799_527_000

    def test_stock_dict_with_alternate_keys(self):
        """stock_code/stock_name/current_price 키로 들어오는 변형도 수용."""
        item = {
            "stock": {
                "stock_code": "000660",
                "stock_name": "SK하이닉스",
                "current_price": 200_000,
                "change_pct": 5.0,
                "trading_value": 500_000_000_000,
            },
            "pre_score": None,
            "news": [],
        }
        out = _adapt_to_jongga_signal(item)
        assert out["stock"]["stock_code"] == "000660"
        assert out["stock"]["stock_name"] == "SK하이닉스"
        assert out["stock"]["current_price"] == 200_000


# ---------------------------------------------------------------------------
# supply가 dict로 들어왔을 때
# ---------------------------------------------------------------------------

class TestSupplyDictInput:
    def test_supply_as_dict_is_used(self):
        item = {
            "stock": _stock_obj(),
            "pre_score": None,
            "score_details": {},
            "supply": {
                "foreign_buy_5d": 12_345_000_000,
                "inst_buy_5d": 6_789_000_000,
            },
            "news": [],
        }
        out = _adapt_to_jongga_signal(item)
        assert out["supply"]["foreign_buy_5d"] == 12_345_000_000
        assert out["supply"]["inst_buy_5d"] == 6_789_000_000

    def test_supply_dict_does_not_fall_back_to_score_details(self):
        """supply dict이 있으면 score_details 폴백을 덮어쓰지 않는다."""
        item = {
            "stock": _stock_obj(),
            "pre_score": None,
            "score_details": {
                "foreign_net_buy": 999_999_999,
                "inst_net_buy": 999_999_999,
            },
            "supply": {
                "foreign_buy_5d": 1_000,
                "inst_buy_5d": 2_000,
            },
            "news": [],
        }
        out = _adapt_to_jongga_signal(item)
        assert out["supply"]["foreign_buy_5d"] == 1_000
        assert out["supply"]["inst_buy_5d"] == 2_000


# ---------------------------------------------------------------------------
# 일부 필드만 누락 / None 으로 들어왔을 때
# ---------------------------------------------------------------------------

class TestPartialMissing:
    def test_pre_score_none_yields_zero_breakdown(self):
        item = {"stock": _stock_obj(), "pre_score": None, "news": []}
        out = _adapt_to_jongga_signal(item)
        s = out["stock"]["score"]
        assert all(v == 0 for v in s.values())

    def test_score_details_none_yields_empty_dict(self):
        item = {"stock": _stock_obj(), "pre_score": None, "score_details": None, "news": []}
        out = _adapt_to_jongga_signal(item)
        assert out["stock"]["score_details"] == {}

    def test_news_none_yields_empty_list(self):
        item = {"stock": _stock_obj(), "pre_score": None, "news": None}
        out = _adapt_to_jongga_signal(item)
        assert out["news"] == []

    def test_stock_none_does_not_crash(self):
        item = {"stock": None, "pre_score": None, "news": []}
        out = _adapt_to_jongga_signal(item)
        assert out["stock"]["stock_code"] == ""
        assert out["stock"]["stock_name"] == ""
        assert out["stock"]["current_price"] == 0


# ---------------------------------------------------------------------------
# 숫자 타입 변형 (str → 정상 변환되거나 0으로 안전하게 떨어져야 함)
# ---------------------------------------------------------------------------

class TestNumericTypeRobustness:
    def test_supply_string_numbers_coerced_to_int(self):
        item = {
            "stock": _stock_obj(),
            "pre_score": None,
            "supply": {"foreign_buy_5d": "12345", "inst_buy_5d": "67890"},
            "news": [],
        }
        out = _adapt_to_jongga_signal(item)
        assert out["supply"]["foreign_buy_5d"] == 12345
        assert out["supply"]["inst_buy_5d"] == 67890

    def test_supply_none_values_inside_dict_become_zero(self):
        item = {
            "stock": _stock_obj(),
            "pre_score": None,
            "score_details": {},
            "supply": {"foreign_buy_5d": None, "inst_buy_5d": None},
            "news": [],
        }
        out = _adapt_to_jongga_signal(item)
        assert out["supply"]["foreign_buy_5d"] == 0
        assert out["supply"]["inst_buy_5d"] == 0


# ---------------------------------------------------------------------------
# 점수 객체가 dict로 들어왔을 때 (Phase 외부 호출 호환)
# ---------------------------------------------------------------------------

class TestPreScoreDictShape:
    def test_pre_score_as_dict_is_mapped(self):
        item = {
            "stock": _stock_obj(),
            "pre_score": {
                "total": 12,
                "news": 3,
                "volume": 3,
                "chart": 2,
                "candle": 1,
                "timing": 1,
                "supply": 2,
            },
            "score_details": {},
            "news": [],
        }
        out = _adapt_to_jongga_signal(item)
        s = out["stock"]["score"]
        assert s["total"] == 12
        assert s["news"] == 3
        assert s["chart"] == 2
        assert s["supply"] == 2


# ---------------------------------------------------------------------------
# 완전히 빈 입력 — 어댑터는 절대 예외를 던지지 않는다
# ---------------------------------------------------------------------------

class TestEmptyInput:
    def test_empty_dict_returns_default_shape(self):
        out = _adapt_to_jongga_signal({})
        assert "stock" in out
        assert "news" in out
        assert "supply" in out
        assert out["stock"]["stock_code"] == ""
        assert out["news"] == []
        assert out["supply"]["foreign_buy_5d"] == 0
