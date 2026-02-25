#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market VCP Background Service
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import pandas as pd
from engine.constants import SCREENING


def _set_vcp_status(status_state: dict[str, Any], **kwargs: Any) -> None:
    status_state.update(kwargs)


def run_vcp_background_pipeline(
    target_date: str | None,
    max_stocks: int | None,
    status_state: dict[str, Any],
    logger: logging.Logger,
) -> None:
    """백그라운드 VCP 스크리너 실행 파이프라인."""
    default_max_stocks = int(SCREENING.VCP_SCREENING_DEFAULT_MAX_STOCKS)
    effective_max_stocks = default_max_stocks
    if max_stocks is not None:
        try:
            parsed = int(max_stocks)
            if parsed > 0:
                effective_max_stocks = parsed
        except (TypeError, ValueError):
            effective_max_stocks = default_max_stocks

    start_msg = f"[VCP] 지정 날짜 분석 시작: {target_date}" if target_date else "[VCP] 실시간 분석 시작..."
    _set_vcp_status(
        status_state,
        running=True,
        status="running",
        progress=0,
        message=start_msg,
    )
    logger.info(start_msg)

    try:
        from scripts import init_data

        _set_vcp_status(status_state, message="가격 데이터 업데이트 중...")
        logger.info("[VCP Screener] 최신 가격 데이터 수집 시작")
        init_data.create_daily_prices(target_date=target_date)
        _set_vcp_status(status_state, progress=30)

        _set_vcp_status(status_state, message="수급 데이터 분석 중...")
        logger.info("[VCP Screener] 기관/외인 수급 데이터 업데이트")
        init_data.create_institutional_trend(target_date=target_date)
        _set_vcp_status(status_state, progress=50)

        _set_vcp_status(status_state, message="VCP 패턴 분석 및 AI 진단 중...")
        logger.info("[VCP Screener] VCP 시그널 분석 및 AI 수행")
        result_df = init_data.create_signals_log(
            target_date=target_date,
            run_ai=True,
            max_stocks=effective_max_stocks,
        )
        _set_vcp_status(status_state, progress=80)

        _set_vcp_status(status_state, message="최신 가격 동기화 중...")
        logger.info("[VCP Screener] 최신 가격 동기화 수행")
        init_data.update_vcp_signals_recent_price()
        _set_vcp_status(status_state, progress=100)

        if isinstance(result_df, pd.DataFrame):
            success_msg = f"완료: {len(result_df)}개 시그널 감지"
        elif result_df:
            success_msg = "완료: 성공"
        else:
            success_msg = "완료: 조건 충족 종목 없음"

        _set_vcp_status(status_state, message=success_msg, status="success")
        logger.info(f"[VCP Screener] {success_msg}")
    except Exception as e:
        logger.exception(f"[VCP Screener] 실패: {e}")
        _set_vcp_status(status_state, message=f"실패: {str(e)}", status="error")
    finally:
        _set_vcp_status(
            status_state,
            running=False,
            last_run=datetime.now().isoformat(),
        )


__all__ = ["run_vcp_background_pipeline"]
