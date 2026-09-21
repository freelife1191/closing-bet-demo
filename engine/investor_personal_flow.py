#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""관측된 다섯 날짜의 개인 순매수 금액만 합산한다."""
from datetime import date
import logging
import math
from typing import Any

logger = logging.getLogger(__name__)


def cached_personal_value(payload: dict[str, Any], key: str) -> int | None:
    """가용성 표시가 있는 캐시도 숫자 자체를 다시 검증한다."""
    if type(payload.get("individual_schema")) is not int or payload.get("individual_schema") != 1:
        return None
    value = payload.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    try:
        if math.isfinite(value) and value == int(value):
            return int(value)
    except (OverflowError, ValueError):
        logger.debug("Ignoring out-of-range cached personal flow")
        return None
    return None

def personal_flow_details(
    rows: list[dict[str, Any]], *, value_key: str = "netIndividualsBuyVolume",
    price_key: str | None = None,
) -> list[dict[str, Any]]:
    if len(rows) != 5:
        return []
    result = []
    dates = set()
    for row in rows:
        if not isinstance(row, dict):
            return []
        raw_date = next((row.get(key) for key in ("date", "localDate", "baseDate", "tradeDate") if row.get(key)), None)
        value = row.get(value_key)
        price = row.get(price_key) if price_key else 1
        if isinstance(value, bool) or isinstance(price, bool):
            return []
        try:
            day = date.fromisoformat(str(raw_date)[:10]).isoformat()
            amount = float(value)
            multiplier = float(price)
            if not math.isfinite(amount) or not math.isfinite(multiplier) or multiplier <= 0:
                return []
            total = amount * multiplier
            if not math.isfinite(total):
                return []
        except (TypeError, ValueError, OverflowError):
            logger.debug("Ignoring malformed personal flow date or amount")
            return []
        if day in dates:
            return []
        dates.add(day)
        result.append({"date": day, "netIndividualsBuyVolume": int(total)})
    return result

def personal_flow_total(rows: list[dict[str, Any]], *, value_key: str = "netIndividualsBuyVolume") -> int | None:
    details = personal_flow_details(rows, value_key=value_key)
    return sum(item["netIndividualsBuyVolume"] for item in details) if details else None
