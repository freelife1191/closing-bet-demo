#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market VCP Service 단위 테스트
"""

import pandas as pd

from services.kr_market_vcp_service import collect_failed_vcp_rows, prepare_vcp_signals_scope


def test_prepare_vcp_signals_scope_uses_latest_date_when_target_missing():
    signals_df = pd.DataFrame(
        [
            {"ticker": "1", "signal_date": "2026-02-20", "ai_action": "BUY", "ai_reason": "ok"},
            {"ticker": "2", "signal_date": "2026-02-21", "ai_action": "N/A", "ai_reason": "분석 실패"},
        ]
    )

    date_key, scoped = prepare_vcp_signals_scope(signals_df, target_date=None)

    assert date_key == "2026-02-21"
    assert len(scoped) == 1
    assert scoped.iloc[0]["ticker"] == "000002"


def test_collect_failed_vcp_rows_preserves_index_and_count():
    scoped_df = pd.DataFrame(
        [
            {"ticker": "000001", "ai_action": "BUY", "ai_reason": "ok"},
            {"ticker": "000002", "ai_action": "N/A", "ai_reason": "분석 실패"},
            {"ticker": "000003", "ai_action": "HOLD", "ai_reason": "No analysis available."},
        ],
        index=[10, 20, 30],
    )

    def is_failed(row):
        return row.get("ai_action") not in {"BUY", "SELL", "HOLD"} or row.get("ai_reason") in {
            "분석 실패",
            "No analysis available.",
        }

    failed_rows, total_count = collect_failed_vcp_rows(scoped_df, is_failed=is_failed)

    assert total_count == 3
    assert [idx for idx, _ in failed_rows] == [20, 30]
    assert failed_rows[0][1]["ticker"] == "000002"
    assert failed_rows[1][1]["ticker"] == "000003"
