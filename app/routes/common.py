#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
공통 API 라우트
"""

from __future__ import annotations

import logging
import os
import sys
from threading import Lock

from flask import Blueprint

from app.routes.common_admin_routes import register_common_admin_routes
from app.routes.common_market_mock_routes import register_common_market_mock_routes
from app.routes.common_notification_routes import register_common_notification_routes
from app.routes.common_portfolio_routes import register_common_portfolio_routes
from app.routes.common_route_context import CommonRouteContext
from app.routes.common_update_routes import register_common_update_routes
from services.common_update_service import run_background_update_pipeline
from services.common_update_status_service import (
    finish_update as finish_update_impl,
    load_update_status as load_update_status_impl,
    save_update_status as save_update_status_impl,
    start_update as start_update_impl,
    stop_update as stop_update_impl,
    update_item_status as update_item_status_impl,
)
from services.paper_trading import paper_trading


scripts_dir = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "scripts",
)
if scripts_dir not in sys.path:
    sys.path.append(scripts_dir)

logger = logging.getLogger(__name__)
common_bp = Blueprint("common", __name__)

try:
    import engine.shared as shared_state
except ImportError:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    import engine.shared as shared_state


UPDATE_STATUS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "update_status.json",
)
update_lock = Lock()


def load_update_status():
    """상태 파일 로드."""
    return load_update_status_impl(
        update_status_file=UPDATE_STATUS_FILE,
        logger=logger,
    )


def save_update_status(status):
    """상태 파일 저장 (Atomic Write)."""
    save_update_status_impl(
        status=status,
        update_status_file=UPDATE_STATUS_FILE,
        logger=logger,
    )


def start_update(items_list):
    """업데이트 시작."""
    start_update_impl(
        items_list=items_list,
        update_lock=update_lock,
        update_status_file=UPDATE_STATUS_FILE,
        shared_state=shared_state,
        logger=logger,
    )


def update_item_status(name, status_code):
    """아이템 상태 업데이트."""
    update_item_status_impl(
        name=name,
        status_code=status_code,
        update_lock=update_lock,
        update_status_file=UPDATE_STATUS_FILE,
        logger=logger,
    )


def stop_update():
    """업데이트 중단."""
    stop_update_impl(
        update_lock=update_lock,
        update_status_file=UPDATE_STATUS_FILE,
        shared_state=shared_state,
        logger=logger,
    )


def finish_update():
    """업데이트 완료."""
    finish_update_impl(
        update_lock=update_lock,
        update_status_file=UPDATE_STATUS_FILE,
        logger=logger,
    )


def run_background_update(target_date, selected_items=None, force=False):
    """백그라운드에서 순차적으로 데이터 업데이트 실행."""
    run_background_update_pipeline(
        target_date=target_date,
        selected_items=selected_items,
        force=bool(force),
        update_item_status=update_item_status,
        finish_update=finish_update,
        shared_state=shared_state,
        logger=logger,
    )


route_context = CommonRouteContext(
    logger=logger,
    update_lock=update_lock,
    update_status_file=UPDATE_STATUS_FILE,
    load_update_status=load_update_status,
    start_update=start_update,
    update_item_status=update_item_status,
    stop_update=stop_update,
    finish_update=finish_update,
    run_background_update=run_background_update,
    paper_trading=paper_trading,
)

register_common_admin_routes(common_bp, route_context)
register_common_update_routes(common_bp, route_context)
register_common_portfolio_routes(common_bp, route_context)
register_common_market_mock_routes(common_bp, route_context)
register_common_notification_routes(common_bp, route_context)
