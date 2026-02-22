#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Toss Collector Metric Parsers
"""

from __future__ import annotations

from typing import Any

from engine.toss_collector_numeric_helpers import normalize_result_payload, to_float, to_int


def parse_investment_indicators(data: dict[str, Any] | None) -> dict[str, Any] | None:
    if not data:
        return None

    result = normalize_result_payload(data)
    if not isinstance(result, dict):
        return None

    sections = result.get("indicatorSections", [])
    if not isinstance(sections, list):
        sections = []

    indicators = {
        "per": 0.0,
        "pbr": 0.0,
        "psr": 0.0,
        "roe": 0.0,
        "eps": 0,
        "bps": 0,
        "dividend_yield": 0.0,
    }

    for section in sections:
        if not isinstance(section, dict):
            continue

        section_data = section.get("data", {})
        if not isinstance(section_data, dict):
            section_data = {}
        section_name = section.get("sectionName", "")

        if section_name == "가치평가":
            indicators["per"] = to_float(section_data.get("displayPer", "0"))
            indicators["pbr"] = to_float(section_data.get("displayPbr", "0"))
            indicators["psr"] = to_float(section_data.get("displayPsr", "0"))
        elif section_name == "수익":
            indicators["eps"] = to_int(section_data.get("epsKrw", 0))
            indicators["bps"] = to_int(section_data.get("bpsKrw", 0))
            indicators["roe"] = to_float(section_data.get("roe", "0"))
        elif section_name == "배당":
            indicators["dividend_yield"] = to_float(section_data.get("dividendYieldRatio", 0)) * 100.0

    return indicators


def parse_investor_trend(data: dict[str, Any] | None, days: int) -> dict[str, Any] | None:
    if not data:
        return None

    result = data.get("result", {})
    if not isinstance(result, dict):
        result = {}

    trends = result.get("body", [])
    if not isinstance(trends, list) or not trends:
        legacy_trends = data.get("trends", [])
        trends = legacy_trends if isinstance(legacy_trends, list) else []

    foreign_sum = 0.0
    institution_sum = 0.0
    individual_sum = 0.0
    for item in trends:
        if not isinstance(item, dict):
            continue

        close = to_float(item.get("close", 0))
        if close == 0:
            continue

        foreign_sum += to_float(item.get("netForeignerBuyVolume", 0)) * close
        institution_sum += to_float(item.get("netInstitutionBuyVolume", 0)) * close
        individual_sum += to_float(item.get("netIndividualsBuyVolume", 0)) * close

    return {
        "foreign": foreign_sum,
        "institution": institution_sum,
        "individual": individual_sum,
        "days": days,
        "details": trends,
    }


def _extract_latest_and_quarterly(
    table: list[dict[str, Any]],
    *,
    value_key: str,
) -> tuple[Any, list[dict[str, Any]]]:
    if not table:
        return 0, []

    latest = table[-1]
    latest_value = latest.get(value_key, 0) if isinstance(latest, dict) else 0
    quarterly = []
    for item in table[-4:]:
        if not isinstance(item, dict):
            continue
        quarterly.append(
            {
                "period": item.get("period"),
                "value": item.get(value_key, 0),
            }
        )
    return latest_value, quarterly


def parse_financials(
    revenue_data: dict[str, Any] | None,
    operating_data: dict[str, Any] | None,
) -> dict[str, Any]:
    result = {
        "revenue": 0,
        "operating_profit": 0,
        "net_income": 0,
        "revenue_quarterly": [],
        "operating_quarterly": [],
        "net_income_quarterly": [],
    }

    if revenue_data:
        revenue_result = revenue_data.get("result", {})
        if isinstance(revenue_result, dict):
            revenue_table = revenue_result.get("table", [])
            if isinstance(revenue_table, list):
                revenue_latest, revenue_quarterly = _extract_latest_and_quarterly(
                    revenue_table,
                    value_key="revenueKrw",
                )
                net_income_latest, net_income_quarterly = _extract_latest_and_quarterly(
                    revenue_table,
                    value_key="netProfitKrw",
                )
                result["revenue"] = revenue_latest
                result["net_income"] = net_income_latest
                result["revenue_quarterly"] = revenue_quarterly
                result["net_income_quarterly"] = net_income_quarterly

    if operating_data:
        operating_result = operating_data.get("result", {})
        if isinstance(operating_result, dict):
            operating_table = operating_result.get("table", [])
            if isinstance(operating_table, list):
                op_latest, op_quarterly = _extract_latest_and_quarterly(
                    operating_table,
                    value_key="operatingIncomeKrw",
                )
                result["operating_profit"] = op_latest
                result["operating_quarterly"] = op_quarterly

    return result


def parse_stability(data: dict[str, Any] | None) -> dict[str, Any] | None:
    if not data:
        return None

    result = normalize_result_payload(data)
    if not isinstance(result, dict):
        return None

    return {
        "debt_ratio": result.get("liabilityRatio", 0),
        "current_ratio": result.get("currentRatio", 0),
        "interest_coverage": result.get("interestCoverageRatio", 0),
    }
