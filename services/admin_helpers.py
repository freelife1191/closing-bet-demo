#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Admin Helpers

ADMIN_EMAILS 환경변수 기반 관리자 판별 유틸리티.
"""

from __future__ import annotations

import hmac
import os


def get_admin_emails() -> list[str]:
    raw = os.environ.get("ADMIN_EMAILS", "")
    return [entry.strip().lower() for entry in raw.split(",") if entry.strip()]


def is_admin_email(email: str | None) -> bool:
    if not email:
        return False
    normalized = str(email).strip().lower()
    if not normalized or normalized == "user@example.com":
        return False
    return normalized in get_admin_emails()


def verify_admin_api_token(provided: str | None) -> bool:
    """서버끼리만 아는 토큰을 상수 시간으로 대조한다.

    Next.js 라우트 핸들러가 NextAuth 세션으로 관리자를 확인한 뒤에만 이 토큰을
    붙인다. 브라우저는 값을 알 수 없으므로 헤더를 지어내도 통과하지 못한다.

    토큰이 비어 있으면 어떤 요청도 통과시키지 않는다. 비었을 때 열어 두면 설정을
    빠뜨린 배포가 그대로 인증 없는 배포가 된다.
    """
    expected = os.environ.get("ADMIN_API_TOKEN", "").strip()
    if not expected or not provided:
        return False
    # 바이트로 비교한다. compare_digest 는 str 인자에 비ASCII 문자가 섞이면
    # TypeError 를 던지므로, 헤더에 한글 한 글자만 넣어도 403 대신 500 이 나간다.
    return hmac.compare_digest(
        provided.strip().encode("utf-8"), expected.encode("utf-8")
    )
