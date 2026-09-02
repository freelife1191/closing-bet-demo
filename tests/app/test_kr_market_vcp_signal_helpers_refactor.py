#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market VCP 시그널 헬퍼 리팩토링 회귀 테스트
"""

from __future__ import annotations

import app.routes.kr_market_vcp_signal_helpers as vcp_helpers


def test_sort_and_limit_vcp_signals_uses_runtime_limit_when_not_provided(monkeypatch):
    monkeypatch.setattr(vcp_helpers, "resolve_vcp_signals_to_show", lambda **_kwargs: 1)
    signals = [{"score": 10}, {"score": 30}, {"score": 20}]

    result = vcp_helpers._sort_and_limit_vcp_signals(signals)

    assert len(result) == 1
    assert result[0]["score"] == 30


def test_build_vcp_signal_from_row_respects_runtime_min_score(monkeypatch):
    monkeypatch.setattr(vcp_helpers, "resolve_vcp_min_score", lambda **_kwargs: 70.0)
    row = {
        "ticker": "005930",
        "name": "삼성전자",
        "signal_date": "2026-02-24",
        "market": "KOSPI",
        "status": "OPEN",
        "score": 69.9,
    }

    assert vcp_helpers._build_vcp_signal_from_row(row) is None


def test_build_vcp_signal_from_row_requires_vcp_pattern():
    row = {
        "ticker": "005930",
        "name": "삼성전자",
        "signal_date": "2026-02-24",
        "market": "KOSPI",
        "status": "OPEN",
        "score": 90.0,
        "vcp_score": 4,
        "is_vcp": False,
    }

    assert vcp_helpers._build_vcp_signal_from_row(row) is None

    row["is_vcp"] = True
    result = vcp_helpers._build_vcp_signal_from_row(row)

    assert result is not None
    assert result["ticker"] == "005930"
    assert result["vcp_score"] == 4
    assert result["is_vcp"] is True


def _vcp_row(**overrides) -> dict:
    row = {
        "ticker": "034730",
        "name": "SK",
        "signal_date": "2026-05-05",
        "market": "KOSPI",
        "status": "OPEN",
        "score": 90.0,
        "vcp_score": 4,
        "is_vcp": True,
        "entry_price": 475_500,
        "current_price": 586_000,
    }
    row.update(overrides)
    return row


def test_exit_prices_follow_entry_price_not_current_price():
    """손절가와 목표가의 기준가는 현재가가 아니라 진입가다.

    신호 발생 뒤 주가가 오른 종목에서 현재가를 기준으로 삼으면 손절가가 진입가
    위에 놓여, 체결되는 순간 이익 실현이 되는 주문이 손실 구간처럼 표시된다.
    """
    result = vcp_helpers._build_vcp_signal_from_row(_vcp_row())

    assert result is not None
    assert result["stop_price"] == round(475_500 * 0.97)
    assert result["target_price"] == round(475_500 * 1.05)


def test_exit_prices_never_invert_against_entry_price():
    """진입가 대비 방향이 뒤집히지 않는다.

    현재가가 진입가보다 크게 높든 낮든 손절가는 진입가 아래, 목표가는 진입가
    위에 놓여야 한다.
    """
    for current_price in (200_000, 475_500, 900_000):
        result = vcp_helpers._build_vcp_signal_from_row(
            _vcp_row(current_price=current_price)
        )

        assert result is not None
        assert result["stop_price"] < result["entry_price"]
        assert result["target_price"] > result["entry_price"]


def test_exit_prices_keep_backend_values_when_present():
    """저장된 값이 있으면 다시 만들지 않고 그대로 내보낸다."""
    result = vcp_helpers._build_vcp_signal_from_row(
        _vcp_row(stop_price=400_000, target_price=520_000)
    )

    assert result is not None
    assert result["stop_price"] == 400_000
    assert result["target_price"] == 520_000


def test_exit_prices_stay_empty_without_entry_price():
    """진입가가 없으면 임의로 만들지 않고 비워 둔다."""
    result = vcp_helpers._build_vcp_signal_from_row(_vcp_row(entry_price=0))

    assert result is not None
    assert result["stop_price"] is None
    assert result["target_price"] is None


def test_exit_prices_fill_only_the_missing_side():
    """한쪽만 저장되어 있으면 비어 있는 쪽만 채운다."""
    only_stop = vcp_helpers._build_vcp_signal_from_row(_vcp_row(stop_price=400_000))
    only_target = vcp_helpers._build_vcp_signal_from_row(_vcp_row(target_price=520_000))

    assert only_stop is not None
    assert only_stop["stop_price"] == 400_000
    assert only_stop["target_price"] == round(475_500 * 1.05)

    assert only_target is not None
    assert only_target["target_price"] == 520_000
    assert only_target["stop_price"] == round(475_500 * 0.97)


def test_exit_prices_survive_unusable_entry_price():
    """진입가가 NaN 이나 무한대여도 한 행이 응답 전체를 무너뜨리지 않는다."""
    for broken in (float("nan"), float("inf"), "inf"):
        result = vcp_helpers._build_vcp_signal_from_row(_vcp_row(entry_price=broken))

        assert result is not None
        assert result["stop_price"] is None
        assert result["target_price"] is None
