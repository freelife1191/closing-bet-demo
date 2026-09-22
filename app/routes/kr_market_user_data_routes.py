#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""로그인한 사용자가 서버에 남긴 자기 기록을 한 번에 지우는 경로([FE-045]).

신원은 before_request 가 서명 헤더에서 확정한 g.user_email 뿐이다. 관리자가 남을 지우는
인자는 두지 않는다. 세 저장소는 파일이 달라 한 트랜잭션으로 묶을 수 없으므로 앞이 실패해도
뒤를 계속 지우고, 하나라도 실패하면 500 으로 알려 화면이 로그아웃하지 않게 한다.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from flask import g, jsonify

from app.routes.route_execution import execute_json_route


def delete_user_data(
    *,
    owner_id: str,
    get_chatbot_fn: Callable[[], Any],
    get_paper_trading_fn: Callable[[], Any],
    delete_user_usage_fn: Callable[[str], bool],
    logger: logging.Logger,
) -> tuple[int, dict[str, Any]]:
    # getter 는 각 단계 안에서 부른다. 챗봇의 지연 생성이 던져도 다른 저장소는 계속 지운다.
    # 반환형: clear_for_owner 는 지운 건수(int, 0 도 성공), 나머지 셋은 bool 이다. 실패는
    # 예외 또는 False 뿐이다.
    steps = (
        ("chat_sessions", lambda: get_chatbot_fn().history.clear_for_owner(owner_id)),
        ("chat_memories", lambda: get_chatbot_fn().memory.delete_owner(owner_id)),
        ("paper_trading", lambda: get_paper_trading_fn().delete_account(owner_id=owner_id)),
        ("usage", lambda: delete_user_usage_fn(owner_id)),
    )
    deleted: dict[str, Any] = {}
    failed: list[str] = []
    for name, step in steps:
        try:
            result = step()
        except Exception as error:
            logger.error("User data delete failed at %s: %s", name, error)
            failed.append(name)
            continue
        if result is False:
            failed.append(name)
            continue
        deleted[name] = result
    if failed:
        return 500, {
            "error": "일부 기록을 지우지 못했습니다. 잠시 후 다시 시도해 주세요.",
            "deleted": deleted,
            "failed": failed,
        }
    return 200, {"status": "deleted", "deleted": deleted}


def register_user_data_routes(
    kr_bp: Any,
    *,
    logger: logging.Logger,
    get_chatbot_fn: Callable[[], Any],
    get_paper_trading_fn: Callable[[], Any],
    delete_user_usage_fn: Callable[[str], bool],
) -> None:
    @kr_bp.route("/user/data", methods=["DELETE"])
    def delete_my_data():
        def _handler():
            owner_id = g.get("user_email")
            if not owner_id:
                return jsonify({"error": "로그인이 필요합니다."}), 401
            status_code, payload = delete_user_data(
                owner_id=owner_id,
                get_chatbot_fn=get_chatbot_fn,
                get_paper_trading_fn=get_paper_trading_fn,
                delete_user_usage_fn=delete_user_usage_fn,
                logger=logger,
            )
            return jsonify(payload), status_code

        return execute_json_route(handler=_handler, logger=logger, error_label="Delete user data error")
