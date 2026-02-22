#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scheduler job 실행 로직.

기존 services.scheduler에서 실행 책임을 분리한다.
"""

from __future__ import annotations

import importlib
import logging
import os
import sys
from datetime import datetime
from typing import Any, Callable

from engine.market_schedule import MarketSchedule

logger = logging.getLogger(__name__)

_INIT_DATA_FUNCTIONS_CACHE: dict[str, Callable[..., Any]] | None = None


def _load_init_data_functions() -> dict[str, Callable[..., Any]]:
    """scripts/init_data.py의 진입 함수를 지연 로드한다."""
    global _INIT_DATA_FUNCTIONS_CACHE
    if _INIT_DATA_FUNCTIONS_CACHE is not None:
        return _INIT_DATA_FUNCTIONS_CACHE

    scripts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
    if scripts_dir not in sys.path:
        sys.path.append(scripts_dir)

    init_data = importlib.import_module("init_data")
    _INIT_DATA_FUNCTIONS_CACHE = {
        "create_signals_log": getattr(init_data, "create_signals_log"),
        "create_jongga_v2_latest": getattr(init_data, "create_jongga_v2_latest"),
        "create_daily_prices": getattr(init_data, "create_daily_prices"),
        "create_institutional_trend": getattr(init_data, "create_institutional_trend"),
        "send_jongga_notification": getattr(init_data, "send_jongga_notification"),
    }
    return _INIT_DATA_FUNCTIONS_CACHE


def _run_market_gate_analysis() -> None:
    """Market Gate 단일 분석을 실행/저장한다."""
    from engine.market_gate import MarketGate

    market_gate = MarketGate()
    result = market_gate.analyze()
    market_gate.save_analysis(result)


def run_jongga_v2_analysis(test_mode: bool = False) -> None:
    """장 마감 후 AI 종가베팅 분석."""
    now = datetime.now()

    if not test_mode and not MarketSchedule.is_market_open(now.date()):
        logger.info(
            f"[Scheduler] 오늘은 휴장일({now.strftime('%Y-%m-%d')})이므로 종가베팅 분석을 건너뜁니다."
        )
        return

    logger.info(">>> [Scheduler] AI 종가베팅 분석 시작 (16:00 - After Closing Analysis)")
    try:
        init_data_functions = _load_init_data_functions()
        analysis_ok = init_data_functions["create_jongga_v2_latest"]()
        if analysis_ok is False:
            logger.error("[Scheduler] 종가베팅 결과 생성 실패 감지")
        else:
            logger.info("<<< [Scheduler] AI 종가베팅 분석 완료 (16:30)")

        init_data_functions["send_jongga_notification"]()
        logger.info("<<< [Scheduler] AI 종가베팅 분석 완료")
    except Exception as e:
        logger.error(f"[Scheduler] AI 종가베팅 분석 실패: {e}")


def run_daily_closing_analysis(test_mode: bool = False) -> None:
    """장 마감 후 전체 데이터 수집 및 분석 (16:00 - First)."""
    now = datetime.now()

    if not test_mode and not MarketSchedule.is_market_open(now.date()):
        logger.info(
            f"[Scheduler] 오늘은 휴장일({now.strftime('%Y-%m-%d')})이므로 정기 분석을 건너뜁니다."
        )
        return

    logger.info(">>> [Scheduler] 장 마감 정기 분석 시작")
    try:
        init_data_functions = _load_init_data_functions()

        logger.info("[Scheduler] 일별 주가 데이터 수집...")
        prices_ok = init_data_functions["create_daily_prices"]()
        if prices_ok is False:
            logger.error("[Scheduler] 일별 주가 데이터 수집 실패 감지")

        logger.info("[Scheduler] 기관/외인 수급 데이터 수집...")
        inst_ok = init_data_functions["create_institutional_trend"]()
        if inst_ok is False:
            logger.error("[Scheduler] 기관/외인 수급 데이터 수집 실패 감지")

        logger.info("[Scheduler] VCP 시그널 분석...")
        vcp_ok = init_data_functions["create_signals_log"](run_ai=True)
        if vcp_ok is False:
            logger.error("[Scheduler] VCP 시그널 분석 실패 감지")

        logger.info(">>> [Scheduler] Chaining: 데이터 수집 완료 후 AI 종가베팅 분석 즉시 시작")
        run_jongga_v2_analysis(test_mode=test_mode)

        logger.info("<<< [Scheduler] 장 마감 정기 분석 및 종가베팅 완료")
    except Exception as e:
        logger.error(f"[Scheduler] 장 마감 정기 분석 실패: {e}")


def run_market_gate_sync() -> None:
    """주기적 매크로 지표 및 스마트머니 데이터 업데이트 (30분)."""
    now = datetime.now()
    if not MarketSchedule.is_market_open(now.date()):
        return

    logger.debug(">>> [Scheduler] Market Gate 및 전체 데이터 동기화 시작")
    try:
        logger.debug("[Scheduler] 실시간 주가/수급 데이터 갱신 중...")
        _run_market_gate_analysis()
        logger.debug("<<< [Scheduler] Market Gate 및 전체 데이터 동기화 완료")
    except Exception as e:
        logger.error(f"[Scheduler] Market Gate 동기화 실패: {e}")
