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
import re
import time


# 로그인하지 않은 화면이 쓰는 기본 프로필 이메일. 서명이 맞더라도 신원으로 삼지 않는다.
DEFAULT_PROFILE_EMAIL = "user@example.com"

# 익명 ID 로 받아들이는 모양. 코드가 실제로 만드는 세 형식만 통과한다.
#
#   1. `frontend/src/lib/session.ts:16`                  → `anon_<uuid4>`
#   2. `frontend/src/app/dashboard/kr/vcp/page.tsx:1043` → `vcp_<티커>_<uuid4>`
#   3. `chatbot/storage.py:295`                          → `<uuid4>` (접두사 없음)
#
# 3번은 `chatbot/session_access.py:82` 가 소유자 불일치를 발견해 새 세션을 배정할 때
# 나오고, VCP 화면이 그 값을 저장해(page.tsx:1101) 다음 요청의 X-Session-Id 로 쓴다.
# 그래서 접두사 화이트리스트(`anon_` 만 허용)는 쓸 수 없다. 이 경로가 조용히 끊기는데,
# 로그인 사용자는 이메일이 소유자라 멀쩡해 보이므로 로그인한 채로는 발견하지 못한다.
#
# 문자 종류로 제한하면 셋을 모두 받으면서 아래 셋이 함께 닫힌다.
#
#   - `@` 가 빠지므로 이메일 모양이 들어오지 못한다. 챗봇 owner_id 와 쿼터 키는 검증된
#     이메일과 익명 ID 를 같은 문자열 공간에 담으므로, 이것을 막지 못하면
#     `X-Session-Id: victim@example.com` 한 줄로 남의 대화와 쿼터에 닿는다.
#   - `:` 가 빠지므로 `kr_market_quota_runtime_service.py` 의 `recharge_day:` 접두사와
#     충돌하지 못한다. 지금은 충전이 로그인 전용이라 문제가 드러나지 않지만, 익명에
#     다시 열면 자기 날짜 표지를 작은 정수로 덮어써 하루 1회 제한을 우회할 수 있다.
#   - 길이 상한이 있으므로 헤더 한도(약 8KB)만큼 큰 키가 `data/user_quota.json` 에
#     무제한으로 쌓이지 못한다. 이 파일은 요청마다 전역 락 안에서 통째로 읽고 쓴다.
ANONYMOUS_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,128}")


def _decode_email(encoded: str) -> str | None:
    padding = "=" * (-len(encoded) % 4)
    try:
        return base64.urlsafe_b64decode(encoded + padding).decode("utf-8")
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return None


def verify_identity_header(header: str | None, now: int | None = None) -> str | None:
    """서명된 신원 헤더를 검증해 이메일을 돌려준다. 실패하면 None 이다.

    # ponytail: 이 서명은 경로에도 메서드에도 nonce 에도 묶여 있지 않아, 한 번 새면 만료
    # 전까지 어느 엔드포인트에나 쓸 수 있다. 지금 이것을 받아들이는 근거는 서명이 오가는
    # 구간이 proxy 와 Flask 사이뿐이고 브라우저로 돌아가지 않는다는 것이다
    # (`proxy.ts` 가 `NextResponse.next({ request: { headers } })` 를 쓰는 이유다).
    #
    # 그 구간이 loopback 이라는 보장은 코드에 없다. `restart_all.sh:80` 과 `Procfile`,
    # `app/__init__.py:299` 가 모두 0.0.0.0 에 바인딩하고, 이 함수도 요청이 proxy 를
    # 거쳤는지 보지 않는다. 5501 이 망에 열린 배포에서는 방화벽이 그 전제를 대신한다.
    # 바인딩 주소를 좁히는 일은 `[INFRA-039]` 로 이월했다.
    """
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
    # 검증된 신원에도 "@" 를 요구한다. 아래 resolve_anonymous_id 가 "@" 있는 값을 익명에서
    # 배제하는 것과 짝을 이루어, 두 네임스페이스가 어느 쪽에서도 겹치지 않게 한다. 한쪽만
    # 강제하면 서명자가 이메일이 아닌 식별자를 넣기 시작하는 순간 불변식이 조용히 깨진다.
    if "@" not in email:
        return None
    return email


def resolve_anonymous_id(session_id: str | None) -> str | None:
    """익명 사용자의 ID 를 확정한다. 코드가 만드는 모양이 아니면 버린다.

    이 값은 브라우저가 그대로 보내므로 무엇이든 들어올 수 있고, 그대로 챗봇 owner_id 와
    쿼터 키가 된다. 무엇을 왜 막는지는 위 `ANONYMOUS_ID_PATTERN` 주석에 적어 두었다.
    """
    if not session_id or not ANONYMOUS_ID_PATTERN.fullmatch(session_id):
        return None
    return session_id
