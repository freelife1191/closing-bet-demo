#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Chatbot Routes

chatbot/quota 엔드포인트 등록 진입점.
"""

from __future__ import annotations

from typing import Any, Callable

from app.routes.kr_market_chatbot_http_routes import register_chatbot_routes
from app.routes.kr_market_quota_http_routes import register_quota_routes


def register_chatbot_and_quota_routes(
    kr_bp: Any,
    *,
    logger: Any,
    max_free_usage: int,
    get_user_usage_fn: Callable[[str | None], int],
    increment_user_usage_fn: Callable[[str | None], int],
    recharge_usage_fn: Callable[[str | None, int], int],
) -> None:
    register_chatbot_routes(
        kr_bp,
        logger=logger,
        max_free_usage=max_free_usage,
        get_user_usage_fn=get_user_usage_fn,
        increment_user_usage_fn=increment_user_usage_fn,
    )
    register_quota_routes(
        kr_bp,
        logger=logger,
        max_free_usage=max_free_usage,
        get_user_usage_fn=get_user_usage_fn,
        recharge_usage_fn=recharge_usage_fn,
    )
