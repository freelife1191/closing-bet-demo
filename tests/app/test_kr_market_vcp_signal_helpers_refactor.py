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


def test_ai_data_map_pads_ticker_to_six_digits():
    """AI 분석 파일의 종목 코드는 여섯 자리로 맞춰서 키로 삼는다.

    시그널 쪽 ticker 는 _build_vcp_signal_from_row 가 항상 zfill(6) 으로 만든다.
    분석 파일은 JSON 이라 종목 코드가 정수 5930 으로 저장되어 있을 수 있는데,
    그 값을 그대로 키로 쓰면 두 자료가 한 종목도 만나지 못해 AI 추천 열이 통째로
    빈다.
    """
    ai_data_map = vcp_helpers._build_ai_data_map(
        {"signals": [{"ticker": 5930, "gemini_recommendation": {"action": "BUY"}}]}
    )

    assert list(ai_data_map) == ["005930"]


def test_ai_data_map_drops_entries_without_a_ticker():
    """종목 코드가 없는 항목은 맵에 넣지 않는다.

    zfill(6) 은 빈 문자열도 "000000" 으로 만든다. 그것을 키로 받아 주면 코드가
    빠진 여러 항목이 한 자리에 겹쳐 쌓이고, 마지막 항목의 분석이 그 자리를
    차지한다.
    """
    ai_data_map = vcp_helpers._build_ai_data_map(
        {
            "signals": [
                {"gemini_recommendation": {"action": "BUY"}},
                {"ticker": 0, "gemini_recommendation": {"action": "HOLD"}},
                {"ticker": "034730", "gemini_recommendation": {"action": "BUY"}},
            ]
        }
    )

    assert list(ai_data_map) == ["034730"]


def test_ai_data_map_survives_an_unusable_payload():
    """파일 모양이 어긋나도 빈 맵으로 끝내고 응답을 무너뜨리지 않는다."""
    assert vcp_helpers._build_ai_data_map(None) == {}
    assert vcp_helpers._build_ai_data_map({"signals": ["034730"]}) == {}


def test_legacy_merge_fills_only_the_missing_recommendation():
    """legacy 파일은 비어 있는 자리만 채우고 이미 있는 추천은 건드리지 않는다.

    legacy 는 예전 형식의 분석 파일이라 오늘 것보다 오래된 판정을 담고 있다.
    조건 없이 대입하면 방금 재분석한 추천이 지난 판정으로 되돌아간다.
    """
    today = {"action": "BUY", "confidence": 80, "reason": "오늘 재분석한 사유입니다."}
    legacy = {"action": "HOLD", "confidence": 50, "reason": "지난 분석의 사유입니다."}
    ai_data_map = {"034730": {"ticker": "034730", "gemini_recommendation": today}}

    vcp_helpers._merge_legacy_ai_fields_into_map(
        ai_data_map,
        {
            "signals": [
                {"ticker": "034730", "gemini_recommendation": legacy,
                 "perplexity_recommendation": legacy}
            ]
        },
    )

    assert ai_data_map["034730"]["gemini_recommendation"] == today
    assert ai_data_map["034730"]["perplexity_recommendation"] == legacy


def test_legacy_merge_does_not_bring_in_new_tickers():
    """legacy 에만 있는 종목은 맵에 들이지 않는다.

    이 함수는 오늘 분석의 빈 필드를 보강하는 자리다. 새 종목까지 받아 주면
    오늘 시그널에 없는 종목의 지난 분석이 응답에 섞인다.
    """
    ai_data_map = {"034730": {"ticker": "034730"}}

    vcp_helpers._merge_legacy_ai_fields_into_map(
        ai_data_map,
        {"signals": [{"ticker": "005930", "gemini_recommendation": {"action": "BUY"}}]},
    )

    assert list(ai_data_map) == ["034730"]
