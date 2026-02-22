#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Jongga Service

조회/실행/재분석 기능의 호환 레이어.
"""

from services.kr_market_jongga_payload_service import (
    build_jongga_history_payload,
    build_jongga_latest_payload,
    build_screener_result_for_message,
    resolve_jongga_message_filename,
)
from services.kr_market_jongga_reanalyze_service import (
    execute_jongga_gemini_reanalysis,
    load_jongga_signals_for_reanalysis,
    load_market_status_for_reanalysis,
    parse_jongga_reanalyze_request_options,
    persist_reanalyze_payload,
    run_jongga_news_reanalysis_batch,
)
from services.kr_market_jongga_runtime_service import (
    _run_coro_in_fresh_loop,
    _send_jongga_notification_from_result,
    launch_jongga_v2_screener,
    run_jongga_v2_background_pipeline,
)

__all__ = [
    "resolve_jongga_message_filename",
    "build_screener_result_for_message",
    "build_jongga_latest_payload",
    "build_jongga_history_payload",
    "_run_coro_in_fresh_loop",
    "_send_jongga_notification_from_result",
    "run_jongga_v2_background_pipeline",
    "parse_jongga_reanalyze_request_options",
    "load_jongga_signals_for_reanalysis",
    "load_market_status_for_reanalysis",
    "run_jongga_news_reanalysis_batch",
    "persist_reanalyze_payload",
    "execute_jongga_gemini_reanalysis",
    "launch_jongga_v2_screener",
]
