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
    assert len(parsed["details"]) == 3


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
