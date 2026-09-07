#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Identity Helpers

`frontend/src/proxy.ts` 가 NextAuth 세션을 확인한 뒤 붙이는 신원 서명을 검증한다.

브라우저는 `INTERNAL_IDENTITY_SECRET` 을 알 수 없으므로 헤더를 지어내도 통과하지
못한다. 「이 요청자가 누구인가」를 정하는 자리는 그 파일과 이 파일 둘뿐이다. 서명
형식을 한쪽만 고치면 모든 요청이 익명으로 떨어지므로 반드시 함께 고친다.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import os
import time


# 로그인하지 않은 화면이 쓰는 기본 프로필 이메일. 서명이 맞더라도 신원으로 삼지 않는다.
DEFAULT_PROFILE_EMAIL = "user@example.com"

# 익명 ID 가 로그인 사용자의 네임스페이스를 침범하는지 가르는 표지.
#
# 챗봇 owner_id 와 쿼터 키는 검증된 이메일과 익명 ID 를 같은 문자열 공간에 담는다.
# 그래서 익명 ID 가 이메일 모양이면 그 사람의 대화와 쿼터에 그대로 닿는다. 이메일에는
# 반드시 "@" 가 있고 어떤 익명 ID 에도 없으므로, 이 한 글자가 두 공간을 가른다.
#
# 접두사 화이트리스트(`anon_` 만 허용)를 먼저 검토했으나 쓸 수 없다. 익명 ID 를 만드는
# 자리가 셋인데 형식이 제각각이다.
#
#   1. `frontend/src/lib/session.ts:16`              → `anon_<uuid>`
#   2. `frontend/src/app/dashboard/kr/vcp/page.tsx:1043` → `vcp_<티커>_<uuid>`
#   3. `chatbot/storage.py:295`                      → `<uuid>` (접두사 없음)
#
# 3번은 `chatbot/session_access.py:82` 가 소유자 불일치를 발견해 새 세션을 배정할 때
# 나오고, VCP 화면이 그 값을 저장해(page.tsx:1101) 다음 요청의 X-Session-Id 로 쓴다.
# 접두사를 요구하면 이 경로가 조용히 끊긴다. 로그인 사용자는 이메일이 소유자라 멀쩡해
# 보이므로 로그인한 채로 확인하면 발견하지 못한다.
#
# 검증된 신원이 이메일이 아니게 되면(Google sub, 내부 사용자 ID 등) 이 검사도 그 모양에
# 맞춰 함께 고친다. 그때 두 공간을 가르는 표지가 "@" 가 아니게 되기 때문이다.
EMAIL_MARKER = "@"


def _decode_email(encoded: str) -> str | None:
    padding = "=" * (-len(encoded) % 4)
    try:
        return base64.urlsafe_b64decode(encoded + padding).decode("utf-8")
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return None


def verify_identity_header(header: str | None, now: int | None = None) -> str | None:
    """서명된 신원 헤더를 검증해 이메일을 돌려준다. 실패하면 None 이다."""
    secret = os.environ.get("INTERNAL_IDENTITY_SECRET", "").strip()
    if not secret or not header:
        return None

    parts = header.split(".")
    if len(parts) != 3:
        return None
    encoded_email, raw_exp, provided_mac = parts

    expected_mac = hmac.new(
        secret.encode("utf-8"),
        f"{encoded_email}.{raw_exp}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    # 바이트로 비교한다. compare_digest 는 비ASCII 가 섞인 str 에 TypeError 를 던지므로
    # 헤더에 한글 한 글자만 넣어도 401 대신 500 이 나간다.
    try:
        matched = hmac.compare_digest(
            provided_mac.encode("utf-8"), expected_mac.encode("utf-8")
        )
    except (TypeError, UnicodeEncodeError):
        return None
    if not matched:
        return None

    try:
        expires_at = int(raw_exp)
    except ValueError:
        return None
    current = int(time.time()) if now is None else int(now)
    if current > expires_at:
        return None

    email = _decode_email(encoded_email)
    if not email or email.strip().lower() == DEFAULT_PROFILE_EMAIL:
        return None
    return email


def resolve_anonymous_id(session_id: str | None) -> str | None:
    """익명 사용자의 ID 를 확정한다. 이메일 모양이면 버린다.

    이 값은 브라우저가 그대로 보내므로 무엇이든 들어올 수 있다. 그런데 챗봇의
    owner_id 와 쿼터 키는 검증된 이메일과 이 값을 같은 문자열 공간에 담는다. 걸러 내지
    않으면 `X-Session-Id: victim@example.com` 한 줄로 로그인 사용자의 대화와 프로필에
    닿고, 관리자 이메일을 넣으면 `is_admin_email` 판정까지 통과해 쿼터가 무제한이 된다.

    판정 근거는 위 `EMAIL_MARKER` 주석에 적어 두었다.
    """
    if not session_id or EMAIL_MARKER in session_id:
        return None
    return session_id
