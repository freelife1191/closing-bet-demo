#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Common Admin Routes
"""

from __future__ import annotations

import os

from flask import jsonify, request

from app.routes.common_route_context import CommonRouteContext


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

        admin_emails_str = os.environ.get("ADMIN_EMAILS", "")
        admin_emails = [entry.strip().lower() for entry in admin_emails_str.split(",") if entry.strip()]
        is_admin = email in admin_emails
        ctx.logger.debug(f"Admin check: {email} -> {is_admin}")
        return jsonify({"isAdmin": is_admin})
