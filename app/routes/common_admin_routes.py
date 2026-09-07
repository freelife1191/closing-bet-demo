#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Common Admin Routes
"""

from __future__ import annotations

from flask import g, jsonify

from app.routes.common_route_context import CommonRouteContext
from services.admin_helpers import is_admin_email


def register_common_admin_routes(common_bp, ctx: CommonRouteContext) -> None:
    """관리자 권한 관련 라우트를 등록한다."""

    @common_bp.route("/admin/check")
    def check_admin():
        """
        ADMIN 권한 확인 API
        - 프론트엔드의 useAdmin 훅에서 호출

        판정 근거는 요청자가 정한 `?email=` 이 아니라 before_request 가 서명으로
        확정해 둔 `g.user_email` 이다. 종전에는 누구든 이메일을 하나씩 넣어
        ADMIN_EMAILS 에 누가 있는지 확인할 수 있었다. 신원이 없으면 관리자가 아니므로
        400 으로 끊지 않고 200 과 함께 isAdmin: false 를 돌려준다.
        """
        email = g.get("user_email")
        is_admin = is_admin_email(email)
        ctx.logger.debug(f"Admin check: {email} -> {is_admin}")
        # 종전에는 URL 이 `?email=` 로 갈려 어떤 캐시도 사용자마다 키를 나눴다. 이제 URL 은
        # 모두에게 같고 본문만 신원에 따라 다르므로, 앞단에 공유 캐시가 놓이면 관리자의
        # true 응답이 다른 사람에게 재사용된다. `api/system/env/route.ts` 와 같은 조치다.
        response = jsonify({"isAdmin": is_admin})
        response.headers["Cache-Control"] = "no-store"
        return response
