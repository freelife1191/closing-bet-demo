#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Backtest - KPI/Pagination Helpers
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd


def aggregate_cumulative_kpis(
    trades: list[dict[str, Any]],
    price_df: Any,
    now_dt: datetime,
) -> dict[str, Any]:
    """누적성과 KPI 집계를 계산한다."""
    total_signals = len(trades)
    wins = 0
    losses = 0
    opens = 0
    total_roi = 0.0
    total_days = 0.0

    grade_acc: dict[str, dict[str, float]] = {
        grade: {"count": 0, "total_roi": 0.0, "wins": 0, "losses": 0}
        for grade in ("S", "A", "B")
    }

    gross_profit = 0.0
    gross_loss = 0.0

    for trade in trades:
        outcome = trade.get("outcome")
        roi = float(trade.get("roi", 0))
        days = float(trade.get("days", 0))
        grade = trade.get("grade")

        if outcome == "WIN":
            wins += 1
        elif outcome == "LOSS":
            losses += 1
        elif outcome == "OPEN":
            opens += 1

        total_roi += roi
        total_days += days

        if roi > 0:
            gross_profit += roi
        elif roi < 0:
            gross_loss += abs(roi)

        if grade in grade_acc:
            grade_acc[grade]["count"] += 1
            grade_acc[grade]["total_roi"] += roi
            if outcome == "WIN":
                grade_acc[grade]["wins"] += 1
            elif outcome == "LOSS":
                grade_acc[grade]["losses"] += 1

    closed_trades = wins + losses
    win_rate = round((wins / closed_trades) * 100, 1) if closed_trades > 0 else 0.0
    avg_roi = round(total_roi / total_signals, 2) if total_signals > 0 else 0.0
    avg_days = round(total_days / total_signals, 1) if total_signals > 0 else 0

    # 등급 카드는 이 값만 읽는다. 앞서 화면이 현재 페이지의 거래 목록으로 등급 통계를
    # 다시 계산했는데, 그러면 페이지를 넘길 때마다 같은 등급의 건수와 승률과 부호가
    # 통째로 달라졌다. 승률의 분모는 전체 KPI 와 같이 종료된 거래만 센다.
    roi_by_grade: dict[str, dict[str, Any]] = {}
    for grade in ["S", "A", "B"]:
        grade_count = int(grade_acc[grade]["count"])
        grade_total_roi = float(grade_acc[grade]["total_roi"])
        grade_avg_roi = round(grade_total_roi / grade_count, 2) if grade_count > 0 else 0.0
        grade_wins = int(grade_acc[grade]["wins"])
        grade_losses = int(grade_acc[grade]["losses"])
        grade_closed = grade_wins + grade_losses
        grade_win_rate = (
            round((grade_wins / grade_closed) * 100, 1) if grade_closed > 0 else 0.0
        )
        roi_by_grade[grade] = {
            "count": grade_count,
            "avgRoi": grade_avg_roi,
            "totalRoi": round(grade_total_roi, 1),
            "wins": grade_wins,
            "losses": grade_losses,
            "winRate": grade_win_rate,
        }

    # 손실 거래가 한 건도 없으면 비율이 정의되지 않는다. 앞서 이 자리는 분자인
    # 총이익을 그대로 돌려주었는데, 그 값이 화면에서 2.0 이라는 비율 기준에 걸려
    # 언제나 최고 등급으로 평가되었다. 비율이 아닌 값을 비율 자리에 넣지 않는다.
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else None

    if isinstance(price_df, pd.DataFrame) and not price_df.empty and len(price_df.index) > 0:
        max_price_date = price_df.index.max()
        if hasattr(max_price_date, "strftime"):
            price_date_str = max_price_date.strftime("%Y-%m-%d")
        else:
            price_date_str = str(max_price_date)
    else:
        price_date_str = now_dt.strftime("%Y-%m-%d")

    return {
        "totalSignals": total_signals,
        "winRate": win_rate,
        "wins": wins,
        "losses": losses,
        "open": opens,
        "avgRoi": avg_roi,
        "totalRoi": round(total_roi, 1),
        "roiByGrade": roi_by_grade,
        "avgDays": avg_days,
        "priceDate": price_date_str,
        "profitFactor": profit_factor,
    }


def paginate_items(
    items: list[dict[str, Any]],
    page: int,
    limit: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """목록 페이지네이션을 수행한다."""
    safe_page = page if page > 0 else 1
    safe_limit = limit if limit > 0 else 50
    total = len(items)
    start_idx = (safe_page - 1) * safe_limit
    end_idx = start_idx + safe_limit
    total_pages = (total + safe_limit - 1) // safe_limit if safe_limit > 0 else 0

    return (
        items[start_idx:end_idx],
        {
            "total": total,
            "page": safe_page,
            "limit": safe_limit,
            "totalPages": total_pages,
        },
    )

