#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Toss collector parser refactor 회귀 테스트
"""

import os
import sys


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from engine.toss_collector import TossCollector
from engine.toss_collector_parsers import (
    parse_financials,
    parse_investment_indicators,
    parse_investor_trend,
    parse_price_details,
    parse_prices_batch,
    parse_stability,
    parse_stock_info,
)


def test_parse_stock_info_handles_result_wrapper():
    payload = {
        "result": {
            "name": "삼성전자",
            "market": {"displayName": "코스피", "code": "KSP"},
            "sector": "반도체",
            "logoImageUrl": "https://example.com/logo.png",
        }
    }

    parsed = parse_stock_info("005930", payload)

    assert parsed is not None
    assert parsed["code"] == "005930"
    assert parsed["name"] == "삼성전자"
    assert parsed["market"] == "코스피"
    assert parsed["market_code"] == "KSP"


def test_parse_price_details_with_single_object():
    payload = {
        "result": {
            "close": 100,
            "base": 80,
            "open": 90,
            "high": 110,
            "low": 70,
            "volume": 1000,
            "value": 12_345,
            "marketCap": 1_000_000,
        }
    }

    parsed = parse_price_details(payload)

    assert parsed is not None
    assert parsed["current"] == 100
    assert parsed["prev_close"] == 80
    assert parsed["change"] == 20
    assert parsed["change_pct"] == 25.0


def test_parse_prices_batch_handles_mixed_codes():
    payload = {
        "result": [
            {"code": "A005930", "close": 100, "base": 80, "open": 90},
            {"code": "000660", "close": 50, "base": 40, "open": 45},
        ]
    }

    parsed = parse_prices_batch(payload)

    assert set(parsed.keys()) == {"005930", "000660"}
    assert parsed["005930"]["change"] == 20
    assert parsed["000660"]["change_pct"] == 25.0


def test_parse_investment_indicators_strips_units():
    payload = {
        "result": {
            "indicatorSections": [
                {
                    "sectionName": "가치평가",
                    "data": {"displayPer": "62.9배", "displayPbr": "8.1배", "displayPsr": "3.4배"},
                },
                {
                    "sectionName": "수익",
                    "data": {"epsKrw": 1000, "bpsKrw": 2000, "roe": "14.0%"},
                },
                {
                    "sectionName": "배당",
                    "data": {"dividendYieldRatio": 0.0051},
                },
            ]
        }
    }

    parsed = parse_investment_indicators(payload)

    assert parsed is not None
    assert parsed["per"] == 62.9
    assert parsed["pbr"] == 8.1
    assert parsed["psr"] == 3.4
    assert parsed["roe"] == 14.0
    assert parsed["dividend_yield"] == 0.51


def test_parse_investor_trend_accumulates_value():
    payload = {
        "result": {
            "body": [
                {
                    "netForeignerBuyVolume": 10,
                    "netInstitutionBuyVolume": 5,
                    "netIndividualsBuyVolume": -15,
                    "close": 1000,
                },
                {
                    "netForeignerBuyVolume": -2,
                    "netInstitutionBuyVolume": 3,
                    "netIndividualsBuyVolume": -1,
                    "close": 900,
                },
            ]
        }
    }

    parsed = parse_investor_trend(payload, days=2)

    assert parsed is not None
    assert parsed["foreign"] == 8_200
    assert parsed["institution"] == 7_700
    assert parsed["individual"] == -15_900
    assert parsed["days"] == 2


def test_parse_investor_trend_ignores_non_dict_or_zero_close_items():
    payload = {
        "result": {
            "body": [
                {"netForeignerBuyVolume": 2, "netInstitutionBuyVolume": 1, "netIndividualsBuyVolume": -3, "close": 0},
                "INVALID",
                {"netForeignerBuyVolume": 5, "netInstitutionBuyVolume": -2, "netIndividualsBuyVolume": -3, "close": 100},
            ]
        }
    }

    parsed = parse_investor_trend(payload, days=3)

    assert parsed is not None
    assert parsed["foreign"] == 500
    assert parsed["institution"] == -200
    assert parsed["individual"] == -300
    # [INFRA-109] details 는 합계에 넣은 행만 담는다. 종가 없는 행이 1일 순매수 자리를 차지하지 않는다
    assert parsed["details"] == [payload["result"]["body"][2]]


def test_parse_investor_trend_treats_no_valid_row_as_missing():
    """[VCP-055] 200 빈 응답을 순매수 0 으로 만들면 호출자가 폴백하지 않고 0 을 저장한다."""
    assert parse_investor_trend({"result": {"body": []}}, days=5) is None
    assert parse_investor_trend({"error": {"code": "X"}}, days=5) is None
    zero_close = {"result": {"body": [{"netForeignerBuyVolume": 7, "close": 0}, "INVALID"]}}
    assert parse_investor_trend(zero_close, days=5) is None


def test_parse_financials_builds_latest_and_quarterly():
    revenue_payload = {
        "result": {
            "table": [
                {"period": "2025Q1", "revenueKrw": 100, "netProfitKrw": 10},
                {"period": "2025Q2", "revenueKrw": 200, "netProfitKrw": 20},
                {"period": "2025Q3", "revenueKrw": 300, "netProfitKrw": 30},
                {"period": "2025Q4", "revenueKrw": 400, "netProfitKrw": 40},
                {"period": "2026Q1", "revenueKrw": 500, "netProfitKrw": 50},
            ]
        }
    }
    operating_payload = {
        "result": {
            "table": [
                {"period": "2025Q4", "operatingIncomeKrw": 40},
                {"period": "2026Q1", "operatingIncomeKrw": 60},
            ]
        }
    }

    parsed = parse_financials(revenue_payload, operating_payload)

    assert parsed["revenue"] == 500
    assert parsed["net_income"] == 50
    assert parsed["operating_profit"] == 60
    assert len(parsed["revenue_quarterly"]) == 4
    assert parsed["revenue_quarterly"][-1]["period"] == "2026Q1"


def test_parse_stability_handles_result_wrapper():
    payload = {
        "result": {
            "liabilityRatio": 20.1,
            "currentRatio": 101.2,
            "interestCoverageRatio": 3.4,
        }
    }

    parsed = parse_stability(payload)

    assert parsed is not None
    assert parsed["debt_ratio"] == 20.1
    assert parsed["current_ratio"] == 101.2
    assert parsed["interest_coverage"] == 3.4


def test_toss_collector_get_prices_batch_merges_chunk_results(monkeypatch):
    collector = TossCollector()

    responses = iter(
        [
            {"result": [{"code": "A005930", "close": 100, "base": 90}]},
            {"result": [{"code": "A000660", "close": 50, "base": 40}]},
        ]
    )
    monkeypatch.setattr(collector, "_safe_request", lambda *_args, **_kwargs: next(responses))

    parsed = collector.get_prices_batch(["005930"] * 20 + ["000660"])

    assert parsed["005930"]["change"] == 10
    assert parsed["000660"]["change_pct"] == 25.0


def test_financial_periods_follow_the_exact_value_row():
    parsed = parse_financials(
        {"result": {"table": [{"period": "2025Q4", "netProfitKrw": -12}, {"period": "2026Q1", "netProfitKrw": 26, "revenueKrw": 100}]}},
        {"result": {"table": [{"period": "2025", "operatingIncomeKrw": 80}]}},
    )
    from services.kr_market_stock_detail_service import build_toss_detail_payload
    detail = build_toss_detail_payload("005930", {"financials": parsed, "indicators": {"eps": -266}})
    assert detail["financials"]["netIncomePeriod"] == "2026Q1"
    assert detail["financials"]["revenuePeriod"] == "2026Q1"
    assert detail["financials"]["operatingProfitPeriod"] == "2025"
    assert detail["financials"]["netIncome"] == 26
    assert detail["indicators"]["eps"] == -266


def test_financial_period_missing_or_invalid_does_not_reuse_previous_row():
    from services.kr_market_stock_detail_service import build_toss_detail_payload
    for latest in [None, {}, {"period": None}, {"period": {}}, {"period": " "}, {"period": "x" * 1000}]:
        parsed = parse_financials({"result": {"table": [{"period": "2025Q4"}, latest]}}, None)
        detail = build_toss_detail_payload("005930", {"financials": parsed})
        assert detail["financials"]["netIncomePeriod"] is None
        assert detail["financials"]["operatingProfitPeriod"] is None


def test_financial_period_requires_the_corresponding_metric():
    parsed = parse_financials({"result": {"table": [{"period": "2026Q1", "revenueKrw": 100, "netProfitKrw": None}]}}, None)
    assert parsed["revenue_period"] == "2026Q1"
    assert parsed["net_income_period"] is None
    missing = parse_financials({"result": {"table": [{"period": "2026Q1", "revenueKrw": 100}]}}, None)
    assert missing["net_income_period"] is None


def _trend_rows(foreign, institution):
    return {
        "result": {
            "body": [
                {"netForeignerBuyVolume": f, "netInstitutionBuyVolume": i, "netIndividualsBuyVolume": 0, "close": 100}
                for f, i in zip(foreign, institution)
            ]
        }
    }


def test_parse_investor_trend_skips_blank_day_in_sum_without_zero_fill():
    """[INFRA-109] 빈 수량은 그날만 결측이다. 합계는 값 있는 날의 합이고 details 원본은 그대로다."""
    parsed = parse_investor_trend(_trend_rows(["", 2, "1,000", 4, 5], [None, 1, 1, 1, 1]), days=5)

    assert parsed["foreign"] == (2 + 1_000 + 4 + 5) * 100
    assert parsed["institution"] == 4 * 100
    assert parsed["details"][0]["netForeignerBuyVolume"] == ""


def test_parse_investor_trend_all_blank_field_sum_is_missing_and_real_zero_is_kept():
    parsed = parse_investor_trend(_trend_rows([None, "", "-", "nan", None], [0, "0", 0.0, 0, 0]), days=5)

    assert parsed["foreign"] is None
    assert parsed["institution"] == 0


def test_parse_investor_trend_all_real_zero_is_zero_and_closeless_latest_row_is_dropped():
    payload = _trend_rows([0, 0, 0, 0, 0], [0, 0, 0, 0, 0])
    payload["result"]["body"].insert(0, {"netForeignerBuyVolume": None, "netInstitutionBuyVolume": None, "close": None})

    parsed = parse_investor_trend(payload, days=5)

    assert parsed["foreign"] == 0 and parsed["institution"] == 0
    assert parsed["details"][0]["netForeignerBuyVolume"] == 0


def test_parse_investor_trend_counts_days_with_value_per_side():
    """[FE-048] 합계에 들어간 날 수를 따로 센다. 빈 날은 빠지고 실제 0 은 센다."""
    parsed = parse_investor_trend(_trend_rows(["", 2, 0, 4, 5], [None, "", "-", 1, 0]), days=5)

    assert parsed["foreign_days"] == 4
    assert parsed["institution_days"] == 2
    assert parsed["foreign"] == (2 + 0 + 4 + 5) * 100


def test_toss_detail_payload_exposes_summed_days():
    from services.kr_market_stock_detail_service import build_toss_detail_payload

    parsed = parse_investor_trend(_trend_rows(["", 2, 3, 4, 5], [None, None, None, None, None]), days=5)
    trend = build_toss_detail_payload("005930", {"investor_trend": parsed})["investorTrend"]

    assert trend["foreign"] == 1_400 and trend["foreignDays"] == 4
    assert trend["institution"] is None and trend["institutionDays"] == 0


def test_toss_detail_payload_keeps_missing_trend_as_none():
    """[FE-048] 추세 요청이 실패하거나 빈 응답이면 파서가 None 을 주고 수집기는 {} 를 넘긴다. 0 이 아니라 결측이다."""
    from services.kr_market_stock_detail_service import build_toss_detail_payload

    trend = build_toss_detail_payload("005930", {"investor_trend": {}})["investorTrend"]

    assert trend["foreign"] is None and trend["institution"] is None
