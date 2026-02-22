#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase4SignalFinalizer 보조 로직.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from engine.models import Signal, SignalStatus


def merge_vcp_score_details(*, score_details: Dict[str, Any], vcp_data: Dict[str, Any] | None) -> Dict[str, Any]:
    """VCP 보조 지표를 score_details에 병합한 사본을 반환."""
    merged = dict(score_details)
    if vcp_data:
        merged["vcp_score"] = vcp_data.get("score", 0)
        merged["contraction_ratio"] = vcp_data.get("ratio", 0)
        merged["is_vcp"] = vcp_data.get("is_vcp", False)
    return merged


def serialize_news_items(news: List[Any], limit: int = 5) -> List[Dict[str, Any]]:
    """Signal.news_items 직렬화 포맷으로 변환."""
    return [
        {
            "title": item.title,
            "source": item.source,
            "published_at": item.published_at.isoformat() if item.published_at else "",
            "url": item.url,
            "weight": getattr(item, "weight", 1.0),
        }
        for item in news[:limit]
    ]


def build_signal(
    *,
    stock: Any,
    target_date,
    grade: Any,
    score: Any,
    checklist: Any,
    score_details: Dict[str, Any],
    news_items: List[Dict[str, Any]],
    position: Any,
    themes: List[str],
) -> Signal:
    """Signal 객체 생성."""
    return Signal(
        stock_code=stock.code,
        stock_name=stock.name,
        market=stock.market,
        sector=stock.sector,
        signal_date=target_date,
        signal_time=datetime.now(),
        grade=grade,
        score=score,
        checklist=checklist,
        news_items=news_items,
        current_price=stock.close,
        change_pct=stock.change_pct,
        entry_price=position.entry_price,
        stop_price=position.stop_price,
        target_price=position.target_price,
        r_value=position.r_value,
        position_size=position.position_size,
        quantity=position.quantity,
        r_multiplier=position.r_multiplier,
        trading_value=stock.trading_value,
        volume_ratio=int(score_details.get("volume_ratio", 0.0)),
        status=SignalStatus.PENDING,
        created_at=datetime.now(),
        score_details=score_details,
        themes=themes,
    )

