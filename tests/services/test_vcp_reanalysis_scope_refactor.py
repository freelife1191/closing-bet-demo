#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
실패 AI 재분석의 날짜 없는 스코프가 화면의 「최신」 날짜와 같은지 확인하는 회귀 테스트 ([VCP-027])
"""

from __future__ import annotations

import pandas as pd

from app.routes.kr_market_data_signals_routes import _VCP_REANALYSIS_SIGNAL_USECOLS
from services.kr_market_vcp_reanalysis_service import prepare_vcp_signals_scope


def _row(ticker: str, signal_date: str, status: str = "OPEN") -> dict:
    return {"ticker": ticker, "signal_date": signal_date, "status": status, "is_vcp": True}


def test_latest_date_skips_a_date_whose_rows_are_all_closed():
    df = pd.DataFrame(
        [
            _row("1", "2026-09-10"),
            _row("2", "2026-09-10", status="CLOSED"),
            _row("3", "2026-09-15", status="CLOSED"),
        ]
    )
    date_key, scoped = prepare_vcp_signals_scope(df, target_date=None, today="2026-09-23")
    assert date_key == "2026-09-10"
    # 날짜만 화면과 맞추고, 그 날짜의 판정 탈락 행은 종전처럼 재분석 대상에 남는다.
    assert sorted(scoped["ticker"]) == ["000001", "000002"]


def test_latest_date_ignores_future_rows():
    df = pd.DataFrame([_row("1", "2026-09-22"), _row("2", "2026-09-30")])
    date_key, scoped = prepare_vcp_signals_scope(df, target_date=None, today="2026-09-23")
    assert date_key == "2026-09-22"
    assert list(scoped["ticker"]) == ["000001"]


def test_latest_date_without_a_qualifying_date_falls_back_to_today_and_is_empty():
    df = pd.DataFrame([_row("1", "2026-09-15", status="CLOSED")])
    date_key, scoped = prepare_vcp_signals_scope(df, target_date=None, today="2026-09-23")
    assert date_key == "2026-09-23"
    assert scoped.empty


def test_explicit_target_date_still_takes_every_row_of_that_date():
    df = pd.DataFrame([_row("1", "20260915", status="CLOSED"), _row("2", "2026-09-10")])
    date_key, scoped = prepare_vcp_signals_scope(df, target_date="2026-09-15", today="2026-09-23")
    assert date_key == "2026-09-15"
    assert list(scoped["ticker"]) == ["000001"]


def test_reanalysis_route_loads_the_columns_the_screen_judgement_needs():
    # 이 열이 빠지면 모든 행이 판정에서 탈락해 「최신」 재분석이 늘 오늘 날짜의 404 가 된다.
    assert {"status", "is_vcp"} <= set(_VCP_REANALYSIS_SIGNAL_USECOLS)
