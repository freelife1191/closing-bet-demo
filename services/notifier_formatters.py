#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 종가베팅 알림 메시지 포맷터
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any


_GRADE_PRIORITY = {"S": 0, "A": 1, "B": 2, "C": 3, "D": 4}


def _extract_total_score(signal: dict[str, Any]) -> float:
    score_data = signal.get("score", {})
    if isinstance(score_data, dict):
        return float(score_data.get("total", 0) or 0)
    return float(signal.get("total_score", 0) or 0)


def _format_trading_value(trading_value: float) -> str:
    if trading_value >= 1_000_000_000_000:
        return f"{trading_value / 1_000_000_000_000:.1f}조"
    if trading_value >= 100_000_000:
        return f"{int(trading_value // 100_000_000)}억"
    return f"{int(trading_value // 10_000)}만"


def _format_supply(value: float) -> str:
    if value == 0:
        return "0"
    sign = "+" if value > 0 else ""
    if abs(value) >= 100_000_000:
        return f"{sign}{int(value // 100_000_000)}억"
    return f"{sign}{int(value // 10_000)}만"


def format_jongga_message(signals: list[dict[str, Any]], date_str: str | None = None) -> str:
    """
    종가베팅 분석 결과를 메시지 포맷으로 변환한다.
    """
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")

    total_raw_count = len(signals)
    filtered_signals = [s for s in signals if str(s.get("grade", "D")).upper() != "D"]
    filtered_count = total_raw_count - len(filtered_signals)

    filtered_signals.sort(
        key=lambda item: (
            _GRADE_PRIORITY.get(str(item.get("grade", "D")).upper(), 99),
            -_extract_total_score(item),
        )
    )

    grades = [s.get("grade", "D") for s in filtered_signals]
    grade_counts = Counter(grades)
    grade_dist = " | ".join([f"{grade}:{count}" for grade, count in sorted(grade_counts.items())])

    lines = [
        f"📊 종가베팅 ({date_str})",
        "",
        f"✅ 선별된 신호: {len(filtered_signals)}개 (D등급 {filtered_count}개 제외)",
        f"📊 등급 분포: {grade_dist}",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━",
        "📋 Top Signals:",
    ]

    for idx, signal in enumerate(filtered_signals, 1):
        name = signal.get("name", signal.get("stock_name", ""))
        code = signal.get("code", signal.get("stock_code", signal.get("ticker", "")))
        grade = signal.get("grade", "D")
        total_score = _extract_total_score(signal)

        entry_price = int(signal.get("entry_price", signal.get("buy_price", 0)) or 0)
        target_price = int(signal.get("target_price_1", entry_price * 1.05 if entry_price else 0) or 0)
        stop_loss = int(signal.get("stop_loss", entry_price * 0.97 if entry_price else 0) or 0)

        score_details = signal.get("score_details", {})
        rise_pct = score_details.get("rise_pct", signal.get("change_pct", 0))
        volume_ratio = score_details.get("volume_ratio", 0)
        trading_value = float(signal.get("trading_value", 0) or 0)
        foreign_5d = float(score_details.get("foreign_net_buy", 0) or 0)
        inst_5d = float(score_details.get("inst_net_buy", 0) or 0)

        market = signal.get("market")
        market_prefix = f"[{market}] " if market else ""
        lines.append(f"{idx}. {market_prefix}{name} ({code}) - {grade}등급 {total_score:g}점")
        lines.append(
            f"   📈 상승: {float(rise_pct):+.1f}% | 거래배수: {float(volume_ratio):.1f}x | 대금: {_format_trading_value(trading_value)}"
        )
        lines.append(f"   🏦 외인(5일): {_format_supply(foreign_5d)} | 기관(5일): {_format_supply(inst_5d)}")

        ai_eval = signal.get("ai_evaluation", {})
        if ai_eval and ai_eval.get("action"):
            action = ai_eval.get("action")
            reason = ai_eval.get("reason", "")
            if len(reason) > 80:
                reason = reason[:77] + "..."
            lines.append(f"   🤖 AI: {action} - {reason}")

        lines.append(f"   💰 진입: ₩{entry_price:,} | 목표: ₩{target_price:,} | 손절: ₩{stop_loss:,}")
        lines.append("")

    lines.extend(
        [
            "━━━━━━━━━━━━━━━━━━━━━━",
            "",
            "⚠️ 투자 참고용이며 손실에 대한 책임은 본인에게 있습니다.",
        ]
    )

    return "\n".join(lines)

