#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026-09-18 성과 카드용 공통 모의 백테스트 응답 회귀 검사."""

from __future__ import annotations

import logging
import os
import sys
from unittest.mock import Mock

from flask import Blueprint, Flask
from flask.testing import FlaskClient


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from app.routes.common_market_mock_routes import register_common_market_mock_routes
from app.routes.common_route_context import CommonRouteContext


def _create_mock_client() -> FlaskClient:
    app = Flask(__name__)
    app.testing = True
    blueprint = Blueprint("performance_mock", __name__)
    context = CommonRouteContext(
        logger=logging.getLogger(__name__),
        update_lock=Mock(),
        update_status_file="",
        load_update_status=Mock(),
        start_update=Mock(),
        update_item_status=Mock(),
        stop_update=Mock(),
        finish_update=Mock(),
        run_background_update=Mock(),
        paper_trading=Mock(),
    )
    register_common_market_mock_routes(blueprint, context)
    app.register_blueprint(blueprint, url_prefix="/api")
    return app.test_client()


def test_backtest_summary_mock_uses_judged_statuses_for_its_existing_metrics():
    """62.5% VCP와 58.3% 종가 성과는 각각 우수·양호 판정으로 도착한다.

    화면은 OK를 미판정으로 취급한다. 모의 라우트가 이전 OK를 계속 내면, 실제 수치를
    가진 카드가 성적을 숨기는 회귀가 생긴다.
    """
    response = _create_mock_client().get("/api/kr/backtest-summary")

    assert response.status_code == 200
    assert response.get_json() == {
        "vcp": {
            "status": "EXCELLENT",
            "win_rate": 62.5,
            "avg_return": 4.2,
            "count": 16,
        },
        "closing_bet": {
            "status": "GOOD",
            "win_rate": 58.3,
            "avg_return": 3.8,
            "count": 12,
        },
    }
