#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Data HTTP Routes

시그널/차트/AI분석/백테스트/종목상세 라우트 등록 오케스트레이션.
"""

from __future__ import annotations

from typing import Any

from app.routes.kr_market_data_ai_routes import register_market_data_ai_routes
from app.routes.kr_market_data_backtest_stock_routes import (
    register_market_data_backtest_stock_routes,
)
from app.routes.kr_market_data_jongga_routes import register_market_data_jongga_routes
from app.routes.kr_market_data_signals_routes import register_market_data_signal_routes


def register_market_data_routes(
    kr_bp: Any,
    *,
    logger: Any,
    deps: dict[str, Any],
) -> None:
    """데이터 조회/분석 관련 라우트를 블루프린트에 등록한다."""

    register_market_data_signal_routes(kr_bp, logger=logger, deps=deps)
    register_market_data_ai_routes(kr_bp, logger=logger, deps=deps)
    register_market_data_jongga_routes(kr_bp, logger=logger, deps=deps)
    register_market_data_backtest_stock_routes(kr_bp, logger=logger, deps=deps)

