#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
신원 서명 검증 회귀 테스트

이 검증이 무너지면 헤더 한 줄이 그대로 신원이 된다. 통과 조건을 여기에 고정한다.
"""

import base64
import hashlib
import hmac
import os
import sys

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from services.identity_helpers import resolve_anonymous_id, verify_identity_header


SECRET = "test-identity-secret"


def _sign(email: str, exp: int, secret: str = SECRET) -> str:
    encoded = base64.urlsafe_b64encode(email.encode("utf-8")).decode("ascii").rstrip("=")
    payload = f"{encoded}.{exp}"
    mac = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}.{mac}"


def test_valid_signature_returns_email(monkeypatch):
    monkeypatch.setenv("INTERNAL_IDENTITY_SECRET", SECRET)

    assert verify_identity_header(_sign("owner@example.com", 2000), now=1900) == "owner@example.com"


def test_rejects_when_secret_unset(monkeypatch):
    monkeypatch.delenv("INTERNAL_IDENTITY_SECRET", raising=False)

    assert verify_identity_header(_sign("owner@example.com", 2000), now=1900) is None


def test_rejects_forged_signature(monkeypatch):
    monkeypatch.setenv("INTERNAL_IDENTITY_SECRET", SECRET)

    forged = _sign("intruder@example.com", 2000, secret="wrong-secret")
    assert verify_identity_header(forged, now=1900) is None


def test_rejects_swapped_email_with_valid_mac(monkeypatch):
    """서명은 그대로 두고 이메일만 바꾼 헤더를 거부한다."""
    monkeypatch.setenv("INTERNAL_IDENTITY_SECRET", SECRET)

    valid = _sign("owner@example.com", 2000)
    mac = valid.rsplit(".", 1)[1]
    other = base64.urlsafe_b64encode(b"intruder@example.com").decode("ascii").rstrip("=")
    assert verify_identity_header(f"{other}.2000.{mac}", now=1900) is None


def test_rejects_expired_signature(monkeypatch):
    monkeypatch.setenv("INTERNAL_IDENTITY_SECRET", SECRET)

    assert verify_identity_header(_sign("owner@example.com", 2000), now=2001) is None


def test_accepts_at_exact_expiry(monkeypatch):
    monkeypatch.setenv("INTERNAL_IDENTITY_SECRET", SECRET)

    assert verify_identity_header(_sign("owner@example.com", 2000), now=2000) == "owner@example.com"


def test_rejects_malformed_headers(monkeypatch):
    monkeypatch.setenv("INTERNAL_IDENTITY_SECRET", SECRET)

    assert verify_identity_header(None, now=1900) is None
    assert verify_identity_header("", now=1900) is None
    assert verify_identity_header("only.two", now=1900) is None
    assert verify_identity_header("a.b.c.d", now=1900) is None
    assert verify_identity_header("aaa.not-a-number.bbb", now=1900) is None


def test_rejects_non_ascii_without_raising(monkeypatch):
    """compare_digest 는 비ASCII str 에 TypeError 를 던진다. 500 이 아니라 None 이어야 한다."""
    monkeypatch.setenv("INTERNAL_IDENTITY_SECRET", SECRET)

    assert verify_identity_header("한글.2000.한글", now=1900) is None


def test_rejects_default_profile_email(monkeypatch):
    """user@example.com 은 로그인하지 않은 화면의 기본값이라 신원이 아니다."""
    monkeypatch.setenv("INTERNAL_IDENTITY_SECRET", SECRET)

    assert verify_identity_header(_sign("user@example.com", 2000), now=1900) is None


def test_anonymous_id_accepts_every_shape_the_code_makes():
    """익명 ID 를 만드는 자리가 셋인데 형식이 제각각이라 전부 통과해야 한다.

    하나라도 막으면 그 경로의 비로그인 대화가 조용히 끊긴다. 로그인 사용자는 이메일이
    소유자라 멀쩡해 보이므로 로그인한 채로 확인하면 발견하지 못한다.
    """
    # frontend/src/lib/session.ts:16 의 getBrowserSessionId
    assert resolve_anonymous_id("anon_abc123") == "anon_abc123"
    # frontend/src/app/dashboard/kr/vcp/page.tsx:1043 의 종목별 채팅 세션
    vcp_id = "vcp_005930_0f8c2b1e-1a2b-4c3d-9e8f-7a6b5c4d3e2f"
    assert resolve_anonymous_id(vcp_id) == vcp_id
    # chatbot/storage.py:295 가 소유자 불일치 때 배정하는 순수 uuid4.
    # VCP 화면이 page.tsx:1101 에서 저장해 다음 요청의 X-Session-Id 로 쓴다.
    assigned = "0f8c2b1e-1a2b-4c3d-9e8f-7a6b5c4d3e2f"
    assert resolve_anonymous_id(assigned) == assigned

    assert resolve_anonymous_id(None) is None
    assert resolve_anonymous_id("") is None


def test_anonymous_id_rejects_email_shaped_values():
    """이 한 줄이 없으면 X-Session-Id 헤더로 게이트 전체가 우회된다.

    챗봇 owner_id 와 쿼터 키는 검증된 이메일과 익명 ID 를 같은 문자열 공간에 담는다.
    그래서 X-Session-Id 에 남의 이메일을 넣으면 그 사람의 대화와 프로필에 닿고,
    관리자 이메일을 넣으면 is_admin_email 판정까지 통과해 쿼터가 무제한이 된다.
    """
    assert resolve_anonymous_id("victim@example.com") is None
    assert resolve_anonymous_id("admin@example.com") is None
    # 접두사를 붙여도 "@" 가 있으면 버린다. 이메일 문자열이 그대로 섞여 들어오는 것을
    # 허용하면 그 부분 문자열로 소유자를 맞히는 시도를 열어 두게 된다.
    assert resolve_anonymous_id("anon_victim@example.com") is None
