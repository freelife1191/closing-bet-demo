#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Common Admin Routes
"""

from __future__ import annotations

from flask import jsonify, request

from app.routes.common_route_context import CommonRouteContext
from services.admin_helpers import is_admin_email


def register_common_admin_routes(common_bp, ctx: CommonRouteContext) -> None:
    """관리자 권한 관련 라우트를 등록한다."""

    @common_bp.route("/admin/check")
    def check_admin():
        """
        ADMIN 권한 확인 API
        - 이메일이 ADMIN_EMAILS 환경변수에 포함되어 있는지 확인
        - 프론트엔드의 useAdmin 훅에서 호출
        """
        email = request.args.get("email", "").strip().lower()
        if not email:
            return jsonify({"isAdmin": False, "error": "Email required"}), 400

        is_admin = is_admin_email(email)
        ctx.logger.debug(f"Admin check: {email} -> {is_admin}")
        return jsonify({"isAdmin": is_admin})
