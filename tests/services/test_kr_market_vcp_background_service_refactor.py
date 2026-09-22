#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[VCP-031] 「Refresh VCP」 백그라운드 파이프라인의 상태 판정 회귀 테스트
"""

from __future__ import annotations

import json
import logging

from scripts import init_data
from services.kr_market_vcp_background_service import run_vcp_background_pipeline


def _run(monkeypatch, tmp_path, *, create_result, latest_signals):
    """init_data 의 네 단계를 가짜로 바꾸고 파이프라인을 돌린 뒤 상태와 가격 동기화 호출 여부를 돌려준다."""
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "vcp_signals_latest.json").write_text(
        json.dumps({"date": "2026-09-21", "signals": latest_signals}), encoding="utf-8"
    )
    monkeypatch.setattr(init_data, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr(init_data, "create_daily_prices", lambda target_date=None: None)
    monkeypatch.setattr(init_data, "create_institutional_trend", lambda target_date=None: None)
    monkeypatch.setattr(init_data, "create_signals_log", lambda **_kwargs: create_result)
    synced: list[bool] = []
    monkeypatch.setattr(init_data, "update_vcp_signals_recent_price", lambda: synced.append(True))

    status: dict = {}
    run_vcp_background_pipeline(
        target_date=None,
        max_stocks=None,
        status_state=status,
        logger=logging.getLogger("test.vcp_background"),
    )
    return status, synced


def test_run_vcp_background_pipeline_reports_save_failure_as_error(monkeypatch, tmp_path):
    """create_signals_log 가 False 면 「조건 충족 종목 없음」 성공이 아니라 error 상태와 실패 문구다."""
    status, synced = _run(monkeypatch, tmp_path, create_result=False, latest_signals=[])

    assert status["status"] == "error"
    assert "시그널 저장 실패" in status["message"]
    assert status["running"] is False
    assert synced == []


def test_run_vcp_background_pipeline_counts_signals_from_latest_payload(monkeypatch, tmp_path):
    """True 면 방금 쓴 vcp_signals_latest.json 의 시그널 수를 문구에 싣는다."""
    status, synced = _run(
        monkeypatch,
        tmp_path,
        create_result=True,
        latest_signals=[{"ticker": "000001"}, {"ticker": "000002"}],
    )

    assert status["status"] == "success"
    assert status["message"] == "완료: 2개 시그널 감지"
    assert synced == [True]


def test_run_vcp_background_pipeline_keeps_no_match_message_for_zero_signals(monkeypatch, tmp_path):
    """True 인데 시그널이 0건이면 종전 문구 「완료: 조건 충족 종목 없음」 을 유지한다."""
    status, _synced = _run(monkeypatch, tmp_path, create_result=True, latest_signals=[])

    assert status["status"] == "success"
    assert status["message"] == "완료: 조건 충족 종목 없음"
