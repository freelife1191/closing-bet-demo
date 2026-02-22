#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Jongga Message Builders
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


def resolve_jongga_message_filename(target_date: str | None) -> str:
    """종가 메시지 발송 대상 파일명을 계산한다."""
    if not target_date:
        return "jongga_v2_latest.json"
    return f"jongga_v2_results_{str(target_date).replace('-', '')}.json"


def _parse_signal_date(value: Any) -> datetime.date:
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return datetime.now().date()


def _parse_signal_time(value: Any) -> datetime:
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return datetime.now()


def _parse_enum_or_raw(enum_cls: Any, value: Any) -> Any:
    if isinstance(value, str):
        try:
            return enum_cls(value)
        except ValueError:
            return value
    return value


def build_screener_result_for_message(file_data: dict[str, Any]) -> tuple[Any, int, datetime.date]:
    """
    메시지 발송용 ScreenerResult를 구성한다.
    반환값: (result, signal_count, result_date)
    """
    from engine.models import ChecklistDetail, Grade, ScoreDetail, ScreenerResult, Signal, SignalStatus

    signals = []
    for signal_item in file_data.get("signals", []):
        score_obj = ScoreDetail(**signal_item.get("score", {}))
        checklist_obj = ChecklistDetail(**signal_item.get("checklist", {}))

        signal_obj = Signal(
            stock_code=signal_item["stock_code"],
            stock_name=signal_item["stock_name"],
            market=signal_item["market"],
            sector=signal_item["sector"],
            signal_date=_parse_signal_date(signal_item.get("signal_date")),
            signal_time=_parse_signal_time(signal_item.get("signal_time")),
            grade=_parse_enum_or_raw(Grade, signal_item.get("grade")),
            score=score_obj,
            checklist=checklist_obj,
            news_items=signal_item["news_items"],
            current_price=signal_item["current_price"],
            entry_price=signal_item["entry_price"],
            stop_price=signal_item["stop_price"],
            target_price=signal_item["target_price"],
            r_value=signal_item["r_value"],
            position_size=signal_item["position_size"],
            quantity=signal_item["quantity"],
            r_multiplier=signal_item["r_multiplier"],
            trading_value=signal_item["trading_value"],
            change_pct=signal_item["change_pct"],
            status=_parse_enum_or_raw(SignalStatus, signal_item.get("status")),
            created_at=_parse_signal_time(signal_item.get("created_at")),
            score_details=signal_item.get("score_details"),
            volume_ratio=signal_item.get("volume_ratio"),
            themes=signal_item.get("themes", []),
        )
        signals.append(signal_obj)

    raw_date = file_data.get("date", "")
    if isinstance(raw_date, str) and "T" in raw_date:
        try:
            result_date = datetime.fromisoformat(raw_date).date()
        except ValueError:
            result_date = datetime.now().date()
    else:
        result_date = _parse_signal_date(raw_date)

    result = ScreenerResult(
        date=result_date,
        total_candidates=file_data.get("total_candidates", 0),
        filtered_count=file_data.get("filtered_count", 0),
        scanned_count=file_data.get("scanned_count", 0),
        signals=signals,
        by_grade=file_data.get("by_grade", {}),
        by_market=file_data.get("by_market", {}),
        processing_time_ms=file_data.get("processing_time_ms", 0),
        market_status=file_data.get("market_status"),
        market_summary=file_data.get("market_summary", ""),
        trending_themes=file_data.get("trending_themes", []),
    )
    return result, len(signals), result_date

