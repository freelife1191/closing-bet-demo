#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from engine.messenger_formatters import (
    MessageData,
    MessageDataBuilder,
    MoneyFormatter,
    SignalData,
    TelegramFormatter,
)


@dataclass
class _ScoreObj:
    total: float
    llm_reason: str


@dataclass
class _FakeSignal:
    stock_name: str
    stock_code: str
    market: str
    grade: str
    score: object
    change_pct: float
    volume_ratio: float
    trading_value: int
    entry_price: int
    target_price: int
    stop_price: int
    score_details: dict


@dataclass
class _FakeResult:
    date: date
    signals: list
    by_grade: dict
    market_status: dict


def test_money_formatter_handles_large_units():
    assert MoneyFormatter.format(150_000_000_000) == "+1.5조"
    assert MoneyFormatter.format(500_000_000) == "+5억"
    assert MoneyFormatter.format(15_000) == "+2만"


def test_message_data_builder_sorts_by_grade_then_score_desc():
    result = _FakeResult(
        date=date(2026, 2, 21),
        signals=[
            _FakeSignal(
                stock_name="A",
                stock_code="000001",
                market="KOSPI",
                grade="A",
                score={"total": 70, "llm_reason": "a"},
                change_pct=1.0,
                volume_ratio=1.0,
                trading_value=100_000_000,
                entry_price=1000,
                target_price=1100,
                stop_price=950,
                score_details={},
            ),
            _FakeSignal(
                stock_name="B",
                stock_code="000002",
                market="KOSDAQ",
                grade="S",
                score={"total": 60, "llm_reason": "b"},
                change_pct=2.0,
                volume_ratio=1.1,
                trading_value=200_000_000,
                entry_price=2000,
                target_price=2200,
                stop_price=1900,
                score_details={},
            ),
            _FakeSignal(
                stock_name="C",
                stock_code="000003",
                market="KOSPI",
                grade="S",
                score=_ScoreObj(total=80, llm_reason="c"),
                change_pct=3.0,
                volume_ratio=1.2,
                trading_value=300_000_000,
                entry_price=3000,
                target_price=3300,
                stop_price=2850,
                score_details={},
            ),
        ],
        by_grade={"S": 2, "A": 1},
        market_status={"status": "OPEN", "total_score": 88},
    )

    data = MessageDataBuilder.build(result)

    assert [s.name for s in data.signals] == ["C", "B", "A"]
    assert data.gate_info == "Market Gate: OPEN (88점)"


def test_telegram_formatter_truncates_reason_and_handles_empty_signals():
    formatter = TelegramFormatter()
    long_reason = "x" * 200
    message_data = MessageData(
        title="제목",
        summary_title="요약",
        summary_desc="설명",
        gate_info="게이트",
        signals=[
            SignalData(
                index=1,
                name="종목",
                code="005930",
                market="KOSPI",
                market_icon="🔵",
                grade="S",
                score=90,
                change_pct=1.5,
                volume_ratio=2.0,
                trading_value=120_000_000,
                f_buy=10_000_000,
                i_buy=5_000_000,
                entry=1000,
                target=1100,
                stop=950,
                ai_reason=long_reason,
            )
        ],
        timestamp="2026-02-21T00:00:00",
    )

    formatted = formatter.format(message_data)
    assert "<b>제목</b>" in formatted
    assert "🤖 <i>" in formatted
    assert "..." in formatted

    empty_data = MessageData(
        title="제목",
        summary_title="요약",
        summary_desc="설명",
        gate_info="게이트",
        signals=[],
        timestamp="2026-02-21T00:00:00",
    )
    empty_formatted = formatter.format(empty_data)
    assert "추천 종목이 없습니다" in empty_formatted
