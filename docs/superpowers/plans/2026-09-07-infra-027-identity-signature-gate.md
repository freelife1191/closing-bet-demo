# [INFRA-027] 신원 서명 게이트 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 브라우저가 보낸 `X-User-Email` 헤더를 신원으로 삼던 구조를, NextAuth 세션을 확인한 `proxy.ts` 가 HMAC 으로 서명한 헤더만 신뢰하는 구조로 바꾼다.

**Architecture:** Next.js 16 의 `proxy.ts` 가 `/api/*` 를 rewrite 보다 먼저 가로챈다. 클라이언트가 보낸 신원 헤더를 무조건 지우고, NextAuth 세션이 있을 때만 `X-Auth-Identity: <b64url(email)>.<exp>.<hmac>` 를 붙여 Flask 로 넘긴다. Flask 의 `before_request` 는 그 서명을 공유 비밀로 검증한 결과만 `g.user_email` 에 담는다. 쿼터를 소모하는 경로는 검증된 신원을 요구하고, 익명 사용자는 세션 ID 로 챗봇 조회만 계속 쓴다.

**Tech Stack:** Next.js 16.3.4 (`proxy.ts`, Node.js 런타임), next-auth 4.24.13 (`getToken`), `node:crypto` 의 `createHmac`, Flask, Python `hmac`·`hashlib`, pytest, vitest.

**Spec:** 이 문서에 함께 담았다. 설계는 2026-09-07 대화에서 승인되었고 그 내용이 아래 「설계」 절이다.

## Global Constraints

- Next.js 16 에서 `middleware.js` 는 폐지되었다. **파일 이름은 반드시 `proxy.ts` 이며 `middleware.ts` 를 만들면 안 된다.** 근거: `frontend/node_modules/next/dist/docs/01-app/03-api-reference/03-file-conventions/proxy.md`
- Proxy 는 Node.js 런타임이 기본이다(v16.0.0). `node:crypto` 와 `next-auth/jwt` 를 그대로 쓴다. `runtime` 설정을 넣으면 오류가 난다.
- 실행 순서는 `Proxy(3) → afterFiles rewrites(6)` 이다. **`frontend/next.config.js` 는 바꾸지 않는다.**
- 요청 헤더는 `NextResponse.next({ request: { headers } })` 로만 넘긴다. `NextResponse.next({ headers })` 는 클라이언트에게 노출된다.
- 공유 비밀 이름은 `INTERNAL_IDENTITY_SECRET` 이다. `ADMIN_API_TOKEN` 을 재사용하지 않으며 `NEXT_PUBLIC_` 접두사를 붙이지 않는다.
- 서명 형식은 `<base64url(email, 패딩 없음)>.<exp 유닉스 초>.<hex 소문자 HMAC-SHA256>` 이다. HMAC 의 입력은 `<b64url>.<exp>` 두 마디이며 서명 자체는 포함하지 않는다.
- 만료는 발급 시각 + 120초다.
- 비밀이 비어 있으면 **어떤 요청도 통과시키지 않는다.** 비었을 때 열어 두면 설정을 빠뜨린 배포가 그대로 인증 없는 배포가 된다. `verify_admin_api_token` 이 이미 같은 규칙을 쓴다.
- 비교는 `hmac.compare_digest` 로 하며 인자를 바이트로 인코딩한 뒤 넘긴다. `str` 에 비ASCII 가 섞이면 `TypeError` 가 나 403 대신 500 이 나간다.
- `.env` 로 시작하는 파일은 `.env.example` 만 추적한다. 값은 어떤 출력에도 싣지 않는다.

## 설계

### 신뢰 사슬

```
브라우저: NextAuth 세션 쿠키 (이미 존재. 지금은 서버로 가지 않는다)
   ↓
frontend/src/proxy.ts
   ① 클라이언트가 보낸 X-User-Email 과 X-Auth-Identity 를 무조건 지운다
   ② getToken() 으로 세션을 확인한다
   ③ 세션이 있을 때만 X-Auth-Identity 를 붙인다
   ④ X-Session-Id 는 그대로 통과시킨다 (익명 챗봇 유지)
   ↓ next.config.js 의 rewrite — 바꾸지 않는다
Flask before_request
   - HMAC 을 검증해 g.user_email 을 확정한다. 실패나 부재는 None
   - X-Session-Id 는 `anon_` 접두사를 요구해 g.session_id 에 담는다. 아니면 None
```

①이 핵심이다. 삭제를 세션 확인보다 먼저 하지 않으면, 공격자가 위조한 `X-Auth-Identity` 가 세션 없는 요청에 그대로 실려 Flask 에 닿는다.

### 익명 ID 도 검증해야 하는 이유

`X-Session-Id` 를 그대로 믿으면 **게이트가 헤더 이름 하나로 통째로 우회된다.** 챗봇의 `owner_id` 와 쿼터 키가 검증된 이메일과 클라이언트가 보낸 세션 ID 를 같은 문자열 공간에 담기 때문이다.

```
X-Session-Id: victim@example.com
```

`g.user_email` 이 None 이므로 `resolve_chatbot_owner_id(None, "victim@example.com")` 이 그 문자열을 그대로 돌려주고, 그다음이 전부 열린다.

- `bot.history.get_all_sessions(owner_id="victim@example.com")` 으로 로그인 사용자의 세션 목록을 읽는다
- `chatbot/storage_history_helpers.py:153` 의 `session_owner == owner_id` 를 통과하므로 히스토리 조회와 삭제까지 된다
- `handle_chatbot_profile_request` 의 POST 가 남의 프로필을 덮어쓴다
- `services/kr_market_chatbot_quota_helpers.py:49` 의 `is_admin_email(usage_key)` 까지 통과하므로, **관리자 이메일을 넣으면 쿼터 제한 없이 서버 키로 챗봇을 무제한 사용한다**

그래서 익명 ID 가 이메일 모양이면 버린다. 이메일에는 반드시 `@` 가 있고 어떤 익명 ID 에도 없으므로, 이 한 글자가 두 공간을 가른다.

**접두사 화이트리스트(`anon_` 만 허용)를 먼저 채택했다가 되돌렸다.** 구현 중 `/review` 의 Enum & Value Completeness 가 익명 ID 를 만드는 자리가 셋이고 형식이 제각각임을 찾아냈다.

| 자리 | 형식 |
|---|---|
| `frontend/src/lib/session.ts:16` | `anon_<uuid>` |
| `frontend/src/app/dashboard/kr/vcp/page.tsx:1043` | `vcp_<티커>_<uuid>` |
| `chatbot/storage.py:295` | `<uuid>` (접두사 없음) |

셋째가 결정적이다. `chatbot/session_access.py:82` 가 소유자 불일치를 발견하면 접두사 없는 새 세션을 배정하고, VCP 화면이 그 값을 저장해(`page.tsx:1101`) 다음 요청의 `X-Session-Id` 로 쓴다. 접두사를 요구하면 이 경로가 조용히 끊긴다. **로그인 사용자는 이메일이 소유자라 멀쩡해 보이므로 로그인한 채로 확인하면 발견하지 못한다.**

`@` 배제는 「검증된 신원이 이메일이다」는 오늘의 사실에 기댄다. 신원이 Google `sub` 나 내부 사용자 ID 로 바뀌면 이 검사도 함께 고쳐야 한다. 그 사실을 `EMAIL_MARKER` 주석에 적어 둔다.

접두사 없이 저장된 옛 익명 대화는 이 방식에서 문제가 되지 않는다. 확인한 사실은 다음과 같다.

- `data/usage.db` 의 `api_usage` 와 `usage_log` 두 테이블이 모두 비어 있다
- `data/chatbot_storage.db` 와 `data/user_quota.json` 은 존재하지 않는다
- `backup/user_quota.json` 의 키 다섯 가운데 셋은 `anon_` 접두사이고, 나머지 둘은
  `user_a_...` 와 `user_b_...` 다. 그 두 문자열은 저장소의 어떤 소스 파일에도 없으므로
  QA 에서 사람이 손으로 넣은 값이다. `@` 가 없으니 이 방식에서는 그대로 통과한다

가드는 클라이언트가 보낸 세션 ID 에만 걸고 검증을 통과한 이메일에는 걸지 않는다. `resolve_anonymous_id` 를 별도 함수로 두는 이유가 그 경계를 코드에서 눈에 보이게 하기 위해서다.

### 지금 열려 있는 것

| 경로 | 하는 일 | 헤더를 바꾸면 |
|---|---|---|
| `kr_market_system_http_routes.py:129` `/api/kr/reanalyze/gemini` | `g.user_email` 로 401 판정 + 무료 10회 집계 | 무제한 호출, 남의 쿼터 소진 |
| `kr_market_chatbot_http_routes.py` 네 자리 | 챗봇 세션·히스토리·프로필 소유자 | 남의 대화와 프로필 읽기·덮어쓰기 |
| `kr_market_quota_http_routes.py` 두 자리 | 쿼터 조회·충전 | 남의 쿼터 조회 |
| `common_update_routes.py:181` | 활동 로그의 `user_id` | 로그 오염 |
| `app/__init__.py:175` → `:186` 의 `_resolve_user_id` | `g.user_email` 이 없으면 `g.session_id` 로 떨어져 활동 로그의 `user_id` 가 된다 | 로그 오염. 세션 ID 침범도 여기로 들어온다 |

여기에 더해 `Sidebar.tsx:299` 의 `+` 버튼이 `/api/kr/user/quota/recharge` 를 상한 없이 부른다. 헤더를 위조하지 않아도 두 번 누르면 10회가 초기화된다.

### 익명 사용자

세션이 없으면 `X-Auth-Identity` 가 붙지 않는다. `anon_` 으로 시작하는 `X-Session-Id` 는 그대로 가므로 챗봇 대화와 화면 이용은 유지된다.

**비용 경로 가운데 이번에 닫는 것은 Gemini 재분석 하나다.** `services/kr_market_route_service.py:154` 가 `user_email` 부재에 이미 401 을 주므로, `g.user_email` 이 검증 결과가 되는 것만으로 닫힌다.

**챗봇 호출은 익명에게 열어 둔다.** 사용자가 익명 챗봇 유지를 선택했기 때문이다. 그 결과 남는 한계를 여기에 적어 둔다.

> `resolve_chatbot_usage_context` 는 익명에게 세션 ID 를 쿼터 키로 준다. 브라우저의
> `localStorage` 에서 `browser_session_id` 를 지우면 새 키가 발급되어 챗봇 무료 10회가
> 다시 시작된다. 이 우회는 이번 라운드가 막지 않는다. 막으려면 익명 챗봇 자체를 닫거나
> 서버가 익명 ID 를 발급해야 하는데, 둘 다 승인 범위 밖이다.

그래서 **쿼터 조회 응답도 익명에게 지금과 같은 값을 계속 준다.** `resolve_quota_usage_key` 에서 익명 대체를 없애면 `/user/quota` 는 언제나 「무료 10회 사용 가능」을 내는데, 챗봇 쪽 `check_chatbot_quota_guard` 는 여전히 세션 ID 로 세어 10회에서 402 를 낸다. 화면은 10회가 남았다고 하고 서버는 막는 갈림이 생긴다. 표시와 집행을 같은 키로 맞추기 위해 쿼터 키의 익명 대체는 **그대로 둔다.** 이번에 없애는 것은 쿼리 파라미터와 요청 바디로 신원을 받던 경로뿐이다.

### 충전 하루 1회

`load_quota_data_unlocked` 가 모든 값을 `safe_usage_count` 로 정수화하므로 같은 파일에 날짜 문자열을 넣으면 0 으로 뭉개진다. 그래서 날짜를 정수 `20260907` 로 넣는다.

```python
quota_data[f"recharge_day:{usage_key}"] = 20260907
```

새 파일도 새 저장 계층도 마이그레이션도 없다. 접두사 `recharge_day:` 는 이메일이나 세션 ID 와 충돌하지 않는다.

## 파일 구조

| 파일 | 책임 |
|---|---|
| `services/identity_helpers.py` (신규) | 신원 확정 둘. `verify_identity_header(header, now) -> str \| None` 와 `resolve_anonymous_id(session_id) -> str \| None` |
| `frontend/src/lib/identity.ts` (신규) | 서명 생성 하나. `signIdentity(email, secret, expiresAt) -> string` |
| `frontend/src/proxy.ts` (신규) | 헤더 정화와 세션 확인. 서명 생성은 `identity.ts` 에 맡긴다 |
| `app/__init__.py` | `g.user_email` 을 검증 결과로 확정 |
| `services/kr_market_chatbot_request_helpers.py` | 소유자·쿼터 키가 검증된 이메일만 받게 |
| `services/kr_market_quota_service.py` | 쿼터 키에 넘길 값의 조건을 주석으로 못박는다 |
| `services/kr_market_quota_runtime_service.py` | 충전을 하루 한 번으로 |
| `app/routes/kr_market_chatbot_http_routes.py` | 헤더 직접 읽기를 `g.user_email` 로 |
| `app/routes/kr_market_quota_http_routes.py` | 쿼리·바디 신원을 없애고 `g` 로 |
| `app/routes/common_update_routes.py` | 같은 처리 |
| `frontend/src/app/components/{chatHelpers.ts,ChatWidget.tsx,Sidebar.tsx,SettingsModal.tsx}` | 보내 봐야 지워지는 신원 값을 걷어낸다 |
| `.env.example` | `INTERNAL_IDENTITY_SECRET` 추가 |

서명 생성을 `proxy.ts` 안에 두지 않고 `identity.ts` 로 뽑는 이유는 vitest 로 검사하기 위해서다. `proxy.ts` 자체는 `NextRequest` 를 필요로 해 단위 검사가 무겁다.

---

### Task 1: 파이썬 신원 확정 (서명 검증과 익명 ID 검증)

**Files:**
- Create: `services/identity_helpers.py`
- Test: `tests/services/test_identity_helpers.py`

**Interfaces:**
- Consumes: 없음
- Produces: 두 함수를 내보낸다.
  - `verify_identity_header(header: str | None, now: int | None = None) -> str | None` — 검증에 성공하면 소문자로 정규화하지 않은 원본 이메일을 돌려주고, 실패하면 `None` 이다. 비밀은 `INTERNAL_IDENTITY_SECRET` 환경변수에서 읽는다.
  - `resolve_anonymous_id(session_id: str | None) -> str | None` — `anon_` 으로 시작하는 값만 그대로 돌려주고, 아니면 `None` 이다.

두 함수를 한 파일에 두는 이유는 둘이 같은 질문에 답하기 때문이다. 「이 요청자를 무엇으로 부를 것인가」를 정하는 자리가 저장소에 하나여야, 한쪽만 고쳐 네임스페이스가 다시 섞이는 일이 없다.

- [ ] **Step 1: 실패하는 검사를 쓴다**

```python
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

from services.identity_helpers import verify_identity_header


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


def test_anonymous_id_requires_anon_prefix():
    assert resolve_anonymous_id("anon_abc123") == "anon_abc123"
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
    assert resolve_anonymous_id("session-1") is None
    # 접두사가 붙어 있으면 @ 가 섞여도 이메일 네임스페이스와 충돌하지 않는다.
    assert resolve_anonymous_id("anon_victim@example.com") == "anon_victim@example.com"
```

import 줄도 함께 고친다.

```python
from services.identity_helpers import resolve_anonymous_id, verify_identity_header
```

- [ ] **Step 2: 검사가 실패하는 것을 확인한다**

Run: `source venv/bin/activate && pytest tests/services/test_identity_helpers.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.identity_helpers'`

- [ ] **Step 3: 최소 구현을 쓴다**

```python
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
    """익명 사용자의 ID 를 확정한다. `anon_` 으로 시작하지 않으면 버린다.

    이 값은 브라우저가 그대로 보내므로 무엇이든 들어올 수 있다. 그런데 챗봇의
    owner_id 와 쿼터 키는 검증된 이메일과 이 값을 같은 문자열 공간에 담는다. 걸러 내지
    않으면 `X-Session-Id: victim@example.com` 한 줄로 로그인 사용자의 대화와 프로필에
    닿고, 관리자 이메일을 넣으면 `is_admin_email` 판정까지 통과해 쿼터가 무제한이 된다.

    `frontend/src/lib/session.ts` 의 `getBrowserSessionId` 는 어떤 경로로도 `anon_`
    접두사를 빼지 않으므로, 접두사를 요구해도 정상 사용자가 끊기지 않는다.
    """
    if not session_id or not session_id.startswith(ANONYMOUS_ID_PREFIX):
        return None
    return session_id
```

상수도 파일 위쪽 `DEFAULT_PROFILE_EMAIL` 아래에 더한다.

```python
# 브라우저가 발급하는 익명 ID 의 접두사. `frontend/src/lib/session.ts` 와 짝을 이룬다.
ANONYMOUS_ID_PREFIX = "anon_"
```

- [ ] **Step 4: 검사가 통과하는 것을 확인한다**

Run: `source venv/bin/activate && pytest tests/services/test_identity_helpers.py -v`
Expected: PASS, 11 passed

- [ ] **Step 5: 커밋한다**

```bash
git add services/identity_helpers.py tests/services/test_identity_helpers.py
git commit -m "feat(security): [INFRA-027] 신원 서명 검증과 익명 ID 검증을 더한다"
```

---

### Task 2: 타입스크립트 서명 생성

**Files:**
- Create: `frontend/src/lib/identity.ts`
- Test: `frontend/src/lib/identity.test.ts`

**Interfaces:**
- Consumes: Task 1 이 정한 서명 형식. 두 구현이 같은 문자열을 만들어야 한다.
- Produces: `signIdentity(email: string, secret: string, expiresAt: number): string` 와 `IDENTITY_TTL_SECONDS = 120` 을 내보낸다. Task 3 이 쓴다.

- [ ] **Step 1: 실패하는 검사를 쓴다**

Task 1 의 파이썬과 같은 문자열이 나오는지를 고정값으로 못박는다. 두 언어가 어긋나면 모든 로그인 사용자가 조용히 익명으로 떨어지므로, 형식이 맞는지를 검사가 직접 본다.

```ts
import { createHmac } from 'node:crypto';
import { describe, expect, it } from 'vitest';

// [INFRA-027] 서명 형식 회귀 검사. `services/identity_helpers.py` 의
// verify_identity_header 와 같은 문자열을 만들어야 한다. 한쪽만 바뀌면 검증이 전부
// 실패해 로그인 사용자가 조용히 익명으로 떨어진다.

import { IDENTITY_TTL_SECONDS, signIdentity } from './identity';

describe('signIdentity', () => {
  it('b64url(email).exp.hmac 세 마디를 만든다', () => {
    const signed = signIdentity('owner@example.com', 'test-identity-secret', 2000);
    const parts = signed.split('.');

    expect(parts).toHaveLength(3);
    expect(Buffer.from(parts[0], 'base64url').toString('utf8')).toBe('owner@example.com');
    expect(parts[1]).toBe('2000');
  });

  it('base64url 에 패딩을 남기지 않는다', () => {
    // 'a@b.co' 는 6바이트라 표준 base64 라면 '=' 두 개가 붙는다.
    const signed = signIdentity('a@b.co', 'test-identity-secret', 2000);

    expect(signed.split('.')[0]).not.toContain('=');
  });

  it('HMAC 은 앞 두 마디만을 입력으로 삼는다', () => {
    const signed = signIdentity('owner@example.com', 'test-identity-secret', 2000);
    const [encoded, exp, mac] = signed.split('.');
    const expected = createHmac('sha256', 'test-identity-secret')
      .update(`${encoded}.${exp}`)
      .digest('hex');

    expect(mac).toBe(expected);
  });

  it('비밀이 다르면 서명이 달라진다', () => {
    const a = signIdentity('owner@example.com', 'secret-a', 2000);
    const b = signIdentity('owner@example.com', 'secret-b', 2000);

    expect(a).not.toBe(b);
  });

  it('만료는 120초다', () => {
    expect(IDENTITY_TTL_SECONDS).toBe(120);
  });
});
```

- [ ] **Step 2: 검사가 실패하는 것을 확인한다**

Run: `cd frontend && npx vitest run src/lib/identity.test.ts`
Expected: FAIL — `Failed to resolve import "./identity"`

`frontend/vitest.config.ts` 가 `environment: 'jsdom'` 을 전역으로 두는데 이 검사는
`node:crypto` 와 `Buffer` 를 쓴다. 계획을 세우며 같은 두 호출을 임시 검사로 실제 실행해
jsdom 환경에서 통과하는 것을 확인했으므로 그대로 두면 된다. 그래도 환경 오류가 나면
파일 첫 줄에 `// @vitest-environment node` 를 넣는다.

- [ ] **Step 3: 최소 구현을 쓴다**

```ts
import { createHmac } from 'node:crypto';

/**
 * 신원 서명을 만든다. 검증하는 자리는 `services/identity_helpers.py` 의
 * `verify_identity_header` 하나뿐이며, 두 구현이 같은 문자열을 만들어야 한다.
 *
 * 형식: `<base64url(email, 패딩 없음)>.<exp 유닉스 초>.<hex 소문자 HMAC-SHA256>`
 * HMAC 의 입력은 앞 두 마디이며 서명 자체는 포함하지 않는다.
 */
export const IDENTITY_TTL_SECONDS = 120;

export function signIdentity(email: string, secret: string, expiresAt: number): string {
  // Buffer 의 base64url 은 패딩을 붙이지 않는다. 파이썬 쪽은 디코딩 전에 패딩을 채운다.
  const encoded = Buffer.from(email, 'utf8').toString('base64url');
  const payload = `${encoded}.${expiresAt}`;
  const mac = createHmac('sha256', secret).update(payload).digest('hex');
  return `${payload}.${mac}`;
}
```

- [ ] **Step 4: 검사가 통과하는 것을 확인한다**

Run: `cd frontend && npx vitest run src/lib/identity.test.ts`
Expected: PASS, 5 passed

- [ ] **Step 5: 두 언어가 같은 문자열을 만드는지 직접 대조한다**

`identity.ts` 는 타입스크립트라 `node -e` 로 바로 부를 수 없다. 같은 알고리즘을 두 언어로
각각 돌려 문자열을 비교한다. 서명 형식이 어긋나면 로그인 사용자가 조용히 익명으로
떨어지는데, 그 사고는 검사 하나로는 드러나지 않고 사람이 로그인해 봐야 보인다.

저장소 루트에서 두 명령을 이어 돌린다.

```bash
node -e "
const { createHmac } = require('node:crypto');
const encoded = Buffer.from('owner@example.com','utf8').toString('base64url');
const payload = encoded + '.2000';
console.log(payload + '.' + createHmac('sha256','test-identity-secret').update(payload).digest('hex'));
"
source venv/bin/activate && python3 -c "
import base64, hashlib, hmac
encoded = base64.urlsafe_b64encode(b'owner@example.com').decode().rstrip('=')
payload = encoded + '.2000'
print(payload + '.' + hmac.new(b'test-identity-secret', payload.encode(), hashlib.sha256).hexdigest())
"
```

Expected: 두 줄의 출력이 완전히 같다. 앞의 명령은 `identity.ts` 와 같은 알고리즘이고,
뒤의 명령은 Task 1 검사의 `_sign` 과 같은 알고리즘이다.

- [ ] **Step 6: 커밋한다**

```bash
git add frontend/src/lib/identity.ts frontend/src/lib/identity.test.ts
git commit -m "feat(security): [INFRA-027] 신원 서명 생성 함수를 더한다"
```

---

### Task 3: proxy.ts 가 헤더를 정화하고 서명을 붙인다

**Files:**
- Create: `frontend/src/proxy.ts`
- Modify: `.env.example`

**Interfaces:**
- Consumes: Task 2 의 `signIdentity(email, secret, expiresAt)` 와 `IDENTITY_TTL_SECONDS`
- Produces: Flask 로 가는 `X-Auth-Identity` 헤더. Task 4 가 검증한다.

- [ ] **Step 1: `.env.example` 의 `NEXTAUTH_URL` 에 경고를 적는다**

`:114` 의 `NEXTAUTH_URL=http://localhost:3500` 줄 위에 붙인다. 이 값이 로그인
리디렉션 주소일 뿐이라고 오해하면 운영에서 게이트가 통째로 죽는다.

```bash
# NEXTAUTH_URL 은 로그인 리디렉션 주소일 뿐 아니라, getToken 이 세션 쿠키 이름을 고르는
# 기준입니다. https 로 시작하면 __Secure-next-auth.session-token 을, 아니면
# next-auth.session-token 을 읽습니다(next-auth/jwt/index.js:65). 운영 배포에서 이 값을
# http 로 두거나 비워 두면 getToken 이 언제나 null 을 돌려주어 로그인한 사용자 전원이
# 조용히 익명이 됩니다. 예외도 경고 로그도 남지 않고 "로그인했는데 대화 목록이 비어
# 있다" 로만 나타납니다.
NEXTAUTH_URL=http://localhost:3500
```

- [ ] **Step 2: `.env.example` 에 비밀을 더한다**

`ADMIN_API_TOKEN=` 줄 바로 아래에 붙인다.

```bash
# INTERNAL_IDENTITY_SECRET 은 frontend/src/proxy.ts 가 NextAuth 세션을 확인한 뒤 붙이는
# 신원 서명을 Flask 가 검증할 때 쓰는 서버 전용 공유 비밀입니다. ADMIN_API_TOKEN 과 나눠
# 둡니다. 하나로 합치면 관리자 토큰이 새는 순간 신원 위조까지 가능해집니다.
# 비어 있으면 모든 요청이 익명으로 처리되어 챗봇과 AI 분석이 401 을 받습니다.
# NEXT_PUBLIC_ 접두사를 붙이면 브라우저 번들에 실려 게이트가 무의미해집니다.
# 생성: openssl rand -hex 32
INTERNAL_IDENTITY_SECRET=
```

- [ ] **Step 3: `proxy.ts` 를 쓴다**

파일 이름은 반드시 `proxy.ts` 다. Next 16 에서 `middleware.ts` 는 폐지되었다.

```ts
import { getToken } from 'next-auth/jwt';
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

import { IDENTITY_TTL_SECONDS, signIdentity } from '@/lib/identity';

/**
 * Flask 는 NextAuth 세션 쿠키를 읽지 못한다. 그래서 신원 확정을 여기서 끝내고,
 * 서버끼리만 아는 비밀로 서명한 헤더만 넘긴다.
 *
 * 종전에는 브라우저가 보낸 `X-User-Email` 이 그대로 신원이었다. 그 값은 설정 모달의
 * 자유 입력 칸에서 왔고 NextAuth 세션과 대조되지 않았으므로, 남의 이메일을 아는
 * 사람은 헤더 한 줄로 그 사람의 대화와 쿼터에 닿았다.
 *
 * 실행 순서는 Proxy(3) → afterFiles rewrites(6) 이므로 이 파일이 next.config.js 의
 * rewrite 보다 먼저 돈다. 그래서 rewrite 는 그대로 두어도 된다.
 */

// 클라이언트가 무엇을 보내든 지우는 헤더. 세션 확인보다 먼저 지운다. 나중에 지우면
// 세션이 없는 요청에서 위조한 값이 그대로 Flask 에 닿는다.
const CLIENT_SUPPLIED_IDENTITY_HEADERS = ['x-user-email', 'x-auth-identity'];

const IDENTITY_HEADER = 'X-Auth-Identity';

export async function proxy(request: NextRequest) {
  const requestHeaders = new Headers(request.headers);
  for (const name of CLIENT_SUPPLIED_IDENTITY_HEADERS) {
    requestHeaders.delete(name);
  }

  const secret = (process.env.INTERNAL_IDENTITY_SECRET || '').trim();
  if (secret) {
    const token = await getToken({ req: request });
    const email = token?.email;
    if (email) {
      const expiresAt = Math.floor(Date.now() / 1000) + IDENTITY_TTL_SECONDS;
      requestHeaders.set(IDENTITY_HEADER, signIdentity(email, secret, expiresAt));
    }
  }

  // request 안에 넣어야 rewrite 목적지로 간다. NextResponse.next({ headers }) 로 쓰면
  // 브라우저에게 돌려주는 응답 헤더가 되어 신원이 그대로 노출된다.
  return NextResponse.next({ request: { headers: requestHeaders } });
}

export const config = {
  // NextAuth 자체 경로는 제외한다. 세션을 발급하는 자리에 세션 확인을 걸 이유가 없다.
  // 슬래시까지 적는다. `auth` 만 적으면 `auth` 로 시작하는 모든 경로가 빠지므로,
  // 나중에 `/api/authors` 같은 경로가 생기면 게이트에서 조용히 벗어난다.
  matcher: ['/api/((?!auth/).*)'],
};
```

- [ ] **Step 4: 타입 검사를 돌린다**

Run: `cd frontend && npm run type-check`
Expected: exit 0

- [ ] **Step 5: 헤더가 Flask 까지 실제로 닿는지 확인한다**

**이 계획 전체가 「proxy 가 붙인 request 헤더가 afterFiles rewrite 의 외부 목적지
(`http://127.0.0.1:5501`)까지 전달된다」는 가정 하나 위에 서 있다.** 그 가정이 틀리면
로그인 사용자 전원이 조용히 익명이 되는데, 이 계획의 어떤 자동 검사도 실패하지 않는다.
파이썬 검사는 헤더를 스스로 만들어 넣고, vitest 는 문자열 형식만 본다. 상태 코드 200 도
증거가 되지 않는다. 익명 응답도 200 이기 때문이다.

그래서 Flask 가 그 헤더를 실제로 보았는지를 직접 확인한다. `app/__init__.py` 의
`check_api_key` 끝에 임시 로그 한 줄을 넣는다. **확인이 끝나면 반드시 지운다.**

```python
        # 임시 확인용. Step 5 를 마치면 지운다. 값 자체는 찍지 않는다.
        import logging
        logging.getLogger(__name__).warning(
            "[INFRA-027 probe] identity header present=%s resolved=%s",
            bool(request.headers.get('X-Auth-Identity')),
            bool(g.user_email),
        )
```

Flask 와 Next 를 모두 띄운 뒤 브라우저에서 Google 로그인을 하고 대시보드를 연다.

```bash
grep 'INFRA-027 probe' logs/backend.log | tail -5
```

Expected: 로그인한 상태의 요청에서 `present=True resolved=True` 가 나온다. 로그아웃
상태에서는 `present=False resolved=False` 다.

`present=False` 가 나오면 proxy 의 헤더가 rewrite 목적지에 닿지 않는 것이므로,
`next.config.js` 의 rewrite 를 라우트 핸들러 중계로 바꾸는 설계 변경이 필요하다.
그 경우 여기서 멈추고 사용자에게 알린다.

`present=True resolved=False` 는 서명은 왔는데 검증이 실패한 것이다. 두 언어의 서명
형식이 어긋났거나 `INTERNAL_IDENTITY_SECRET` 이 Flask 와 Next 에서 다른 값이다.

- [ ] **Step 6: 운영 설정의 `NEXTAUTH_URL` 이 https 인지 확인한다**

```bash
grep '^NEXTAUTH_URL=' .env.production | grep -c '^NEXTAUTH_URL=https://'
```

Expected: `1`. `0` 이면 운영에서 getToken 이 언제나 null 을 돌려주므로, 값을
`https://close.highvalue.kr` 로 고친다. 값 자체는 비밀이 아니므로 출력해도 된다.

`.env.production` 이 없는 환경이면 그 사실을 QA 문서에 적고, 배포 시 확인할 항목으로
남긴다.

- [ ] **Step 7: 임시 로그를 지우고 커밋한다**

Step 5 에서 넣은 로그 세 줄을 지운 뒤 `git diff app/__init__.py` 로 남아 있지 않은지
확인한다.

```bash
git add frontend/src/proxy.ts .env.example
git commit -m "feat(security): [INFRA-027] proxy 가 세션을 확인해 신원을 서명한다"
```

---

### Task 4: Flask 가 서명된 신원만 g.user_email 에 담는다

**Files:**
- Modify: `app/__init__.py:173-176`
- Test: `tests/app/test_identity_gate.py`

**Interfaces:**
- Consumes: Task 1 의 `verify_identity_header(header, now=None) -> str | None` 와 `resolve_anonymous_id(session_id) -> str | None`
- Produces: `g.user_email` 이 검증된 이메일 또는 `None` 이고, `g.session_id` 가 `anon_` 으로 시작하는 익명 ID 또는 `None` 이다. Task 5·6·7 이 두 값을 읽는다.

- [ ] **Step 1: 실패하는 검사를 쓴다**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
신원 게이트 회귀 테스트

`g.user_email` 이 검증을 거치지 않으면 헤더 한 줄이 그대로 신원이 된다.
"""

import base64
import hashlib
import hmac
import os
import sys

from flask import Flask, g, jsonify

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from app import _register_request_context


SECRET = "test-identity-secret"


def _sign(email: str, exp: int) -> str:
    encoded = base64.urlsafe_b64encode(email.encode("utf-8")).decode("ascii").rstrip("=")
    payload = f"{encoded}.{exp}"
    mac = hmac.new(SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}.{mac}"


def _create_client():
    app = Flask(__name__)
    app.testing = True
    _register_request_context(app)

    @app.route("/probe")
    def probe():
        return jsonify({"email": g.get("user_email"), "session": g.get("session_id")})

    return app.test_client()


def test_forged_user_email_header_is_ignored(monkeypatch):
    monkeypatch.setenv("INTERNAL_IDENTITY_SECRET", SECRET)
    client = _create_client()

    res = client.get("/probe", headers={"X-User-Email": "victim@example.com"})

    assert res.get_json()["email"] is None


def test_forged_identity_header_is_ignored(monkeypatch):
    monkeypatch.setenv("INTERNAL_IDENTITY_SECRET", SECRET)
    client = _create_client()

    res = client.get("/probe", headers={"X-Auth-Identity": "abc.2000.deadbeef"})

    assert res.get_json()["email"] is None


def test_signed_identity_is_accepted(monkeypatch):
    monkeypatch.setenv("INTERNAL_IDENTITY_SECRET", SECRET)
    client = _create_client()

    far_future = 4102444800  # 2100-01-01
    res = client.get("/probe", headers={"X-Auth-Identity": _sign("owner@example.com", far_future)})

    assert res.get_json()["email"] == "owner@example.com"


def test_session_id_still_passes_through(monkeypatch):
    """익명 사용자의 챗봇 조회가 계속 동작해야 한다."""
    monkeypatch.setenv("INTERNAL_IDENTITY_SECRET", SECRET)
    client = _create_client()

    res = client.get("/probe", headers={"X-Session-Id": "anon_abc"})

    payload = res.get_json()
    assert payload["email"] is None
    assert payload["session"] == "anon_abc"


def test_email_shaped_session_id_is_dropped(monkeypatch):
    """X-Session-Id 로 남의 네임스페이스에 들어가지 못한다.

    챗봇 owner_id 와 쿼터 키는 검증된 이메일과 익명 ID 를 같은 문자열 공간에 담는다.
    이 헤더를 거르지 않으면 서명 게이트를 만들어 두고도 헤더 이름 하나로 우회된다.
    """
    monkeypatch.setenv("INTERNAL_IDENTITY_SECRET", SECRET)
    client = _create_client()

    res = client.get("/probe", headers={"X-Session-Id": "victim@example.com"})

    payload = res.get_json()
    assert payload["email"] is None
    assert payload["session"] is None
```

- [ ] **Step 2: 검사가 실패하는 것을 확인한다**

Run: `source venv/bin/activate && pytest tests/app/test_identity_gate.py -v`
Expected: `test_forged_user_email_header_is_ignored` 가 FAIL — `assert 'victim@example.com' is None`

- [ ] **Step 3: `app/__init__.py` 를 고친다**

`_register_request_context` 안의 두 줄을 바꾼다. 파일 위쪽 import 절에
`from services.identity_helpers import resolve_anonymous_id, verify_identity_header`
를 더한다.

```python
def _register_request_context(app: Flask) -> None:
    @app.before_request
    def check_api_key():
        if request.method == 'OPTIONS':
            return
        # Vertex AI 전환 후 X-Gemini-Key는 무시한다 (사용자별 API 키 기능 제거).
        # 하위 호환을 위해 g.user_api_key 속성은 None으로 유지.
        g.user_api_key = None
        # 브라우저가 보낸 X-User-Email 은 더 이상 읽지 않는다. 그 값은 설정 모달의 자유
        # 입력 칸에서 왔고 서명도 만료도 없었다. frontend/src/proxy.ts 가 NextAuth 세션을
        # 확인해 서명한 헤더만 신원으로 삼는다.
        g.user_email = verify_identity_header(request.headers.get('X-Auth-Identity'))
        # 익명 ID 도 그대로 믿지 않는다. 이 값과 g.user_email 이 같은 문자열 공간에서
        # 챗봇 owner_id 와 쿼터 키가 되므로, 걸러 내지 않으면 헤더 이름만 바꿔 서명
        # 게이트를 우회할 수 있다.
        g.session_id = resolve_anonymous_id(request.headers.get('X-Session-Id'))
```

- [ ] **Step 4: 검사가 통과하는 것을 확인한다**

Run: `source venv/bin/activate && pytest tests/app/test_identity_gate.py -v`
Expected: PASS, 5 passed

- [ ] **Step 5: 기존 검사가 깨지지 않았는지 본다**

Run: `source venv/bin/activate && pytest -q`
Expected: 실패가 있으면 그 검사가 `X-User-Email` 헤더를 직접 넣어 신원을 만들던 것이다. 서명된 헤더를 쓰도록 고친다. 기대값을 바꿔 통과시키지 않는다.

- [ ] **Step 6: 커밋한다**

```bash
git add app/__init__.py tests/app/test_identity_gate.py
git commit -m "fix(security): [INFRA-027] g.user_email 을 서명 검증 결과로 확정한다"
```

---

### Task 5: 챗봇 라우트가 검증된 신원을 쓴다

**Files:**
- Modify: `services/kr_market_chatbot_request_helpers.py:16-24`, `:124-137`
- Modify: `app/routes/kr_market_chatbot_http_routes.py:99-100`, `:132-133`, `:282-283`, `:303-304`
- Test: `tests/app/test_kr_market_chatbot_service.py` (기존 파일에 더한다)

**Interfaces:**
- Consumes: Task 4 의 `g.user_email`
- Produces: 시그니처는 그대로다. 부르는 자리가 헤더 대신 `g.user_email` 을 넘기도록만 바뀐다.

- [ ] **Step 1: 실패하는 검사를 쓴다**

`tests/app/test_kr_market_chatbot_service.py` 끝에 붙인다.

같은 파일의 `test_profile_route_reads_owner_from_session_header` 가 쓰는 조립 방식을
그대로 따른다. 다른 점은 `_register_request_context(app)` 를 함께 부르는 것이다. 그것이
`g.user_email` 을 채우는 자리이므로, 부르지 않으면 이 검사가 게이트를 통과하는지 아니라
`g` 가 비어 있는지를 보게 된다.

```python
def test_chatbot_sessions_ignores_forged_email_header(monkeypatch):
    """[INFRA-027] 위조한 X-User-Email 로 남의 세션 목록을 읽지 못한다.

    proxy 를 거치지 않고 Flask 에 직접 닿는 요청을 흉내 낸다. 배포에서는 proxy 가
    이 헤더를 지우지만, Flask 가 5501 로 직접 노출되는 개발 환경과 잘못된 배포에서는
    그 방어가 없다. 그래서 Flask 쪽 검증이 유일한 실효 방어선이다.
    """
    import logging

    import chatbot as chatbot_pkg
    from flask import Blueprint, Flask

    from app import _register_request_context
    from app.routes.kr_market_chatbot_http_routes import (
        _register_chatbot_welcome_session_routes,
    )

    monkeypatch.setenv("INTERNAL_IDENTITY_SECRET", "test-identity-secret")
    seen = {}

    class _FakeHistory:
        def get_all_sessions(self, owner_id=None):
            seen["owner_id"] = owner_id
            return []

    class _SessionBot:
        history = _FakeHistory()

    monkeypatch.setattr(chatbot_pkg, "get_chatbot", lambda: _SessionBot())

    app = Flask(__name__)
    app.testing = True
    _register_request_context(app)
    blueprint = Blueprint("kr_sessions_test", __name__)
    _register_chatbot_welcome_session_routes(
        blueprint, logger=logging.getLogger("test_sessions_route")
    )
    app.register_blueprint(blueprint, url_prefix="/api/kr")

    response = app.test_client().get(
        "/api/kr/chatbot/sessions",
        headers={"X-User-Email": "victim@example.com", "X-Session-Id": "anon_abc"},
    )

    assert response.status_code == 200
    assert seen["owner_id"] == "anon_abc"


def test_chatbot_sessions_ignores_email_shaped_session_id(monkeypatch):
    """[INFRA-027] X-Session-Id 에 이메일을 넣어 남의 대화에 닿지 못한다.

    앞 검사만으로는 이 구멍이 남는다. owner_id 는 검증된 이메일과 익명 ID 를 같은
    문자열 공간에 담으므로, 세션 ID 에 남의 이메일을 적으면 그대로 소유자가 된다.
    """
    import logging

    import chatbot as chatbot_pkg
    from flask import Blueprint, Flask

    from app import _register_request_context
    from app.routes.kr_market_chatbot_http_routes import (
        _register_chatbot_welcome_session_routes,
    )

    monkeypatch.setenv("INTERNAL_IDENTITY_SECRET", "test-identity-secret")
    seen = {}

    class _FakeHistory:
        def get_all_sessions(self, owner_id=None):
            seen["owner_id"] = owner_id
            return []

    class _SessionBot:
        history = _FakeHistory()

    monkeypatch.setattr(chatbot_pkg, "get_chatbot", lambda: _SessionBot())

    app = Flask(__name__)
    app.testing = True
    _register_request_context(app)
    blueprint = Blueprint("kr_sessions_email_test", __name__)
    _register_chatbot_welcome_session_routes(
        blueprint, logger=logging.getLogger("test_sessions_email_route")
    )
    app.register_blueprint(blueprint, url_prefix="/api/kr")

    response = app.test_client().get(
        "/api/kr/chatbot/sessions",
        headers={"X-Session-Id": "victim@example.com"},
    )

    assert response.status_code == 200
    assert seen["owner_id"] is None
```

- [ ] **Step 2: 검사가 실패하는 것을 확인한다**

Run: `source venv/bin/activate && pytest tests/app/test_kr_market_chatbot_service.py -k forged -v`
Expected: FAIL — `assert 'victim@example.com' == 'anon_abc'`

- [ ] **Step 3: 헬퍼의 주석과 부르는 자리를 고친다**

`services/kr_market_chatbot_request_helpers.py` 의 `resolve_chatbot_owner_id` 에서 `# ponytail:` 주석을 지우고 계약을 다시 적는다.

```python
def resolve_chatbot_owner_id(user_email: str | None, session_id_header: str | None) -> str | None:
    """로그인/비로그인 사용자별 챗봇 owner_id를 계산한다.

    두 인자 모두 `services/identity_helpers.py` 의 검증을 통과한 값만 넣는다.
    user_email 은 `verify_identity_header` 의 반환값이고 session_id_header 는
    `resolve_anonymous_id` 의 반환값이다.

    이 함수는 검증된 이메일과 익명 ID 를 같은 문자열 공간에 담는다. 그래서 검증하지 않은
    세션 ID 를 넘기면 `X-Session-Id: victim@example.com` 한 줄로 남의 대화와 프로필이
    열리고, 관리자 이메일을 넣으면 `is_admin_email` 판정까지 통과해 쿼터가 무제한이 된다.
    """
    if user_email and user_email != "user@example.com":
        return user_email
    return session_id_header
```

`resolve_chatbot_usage_context` 의 docstring 에도 같은 한 줄을 더한다.

```python
    """요청 헤더 기준 사용자/세션/키 컨텍스트를 정규화한다.

    두 인자 모두 `services/identity_helpers.py` 의 검증을 통과한 값만 넣는다. 이 값이
    무료 사용량 집계 키가 되므로, 검증하지 않으면 문자열 하나로 쿼터가 새로 시작되고
    관리자 이메일을 넣으면 쿼터 자체를 우회한다.

    익명 사용자의 쿼터는 여전히 세션 ID 로 센다. 브라우저에서 그 값을 지우면 새 키가
    발급되어 무료 10회가 다시 시작되는데, 이 한계는 `[INFRA-027]` 이 막지 않았다.
    막으려면 서버가 익명 ID 를 발급해야 한다.
    """
```

`app/routes/kr_market_chatbot_http_routes.py` 의 네 자리에서 헤더 직접 읽기를 바꾼다. 파일 위쪽에 `from flask import g` 가 없으면 더한다.

```python
# :99-100
            owner_id = resolve_chatbot_owner_id(
                user_email=g.get("user_email"),
                session_id_header=g.get("session_id"),
            )

# :132-133
            context = resolve_chatbot_usage_context(
                user_api_key_header=None,  # Vertex 전환 후 사용자별 API 키 미지원
                user_email_header=g.get("user_email"),
                session_id_header=g.get("session_id"),
            )

# :282-283 과 :303-304 도 같은 방식으로 user_email=g.get("user_email") 과
# session_id_header=g.get("session_id") 로 바꾼다
```

- [ ] **Step 4: 검사가 통과하는 것을 확인한다**

Run: `source venv/bin/activate && pytest tests/app/test_kr_market_chatbot_service.py -v`
Expected: PASS

- [ ] **Step 5: 남은 헤더 직접 읽기가 없는지 본다**

```bash
grep -n 'X-User-Email\|X-Session-Id' app/routes/kr_market_chatbot_http_routes.py
```
Expected: 출력 없음. 두 헤더 모두 `g` 를 거쳐 읽어야 한다.

- [ ] **Step 6: 커밋한다**

```bash
git add services/kr_market_chatbot_request_helpers.py app/routes/kr_market_chatbot_http_routes.py tests/app/test_kr_market_chatbot_service.py
git commit -m "fix(security): [INFRA-027] 챗봇 소유자를 검증된 신원으로 정한다"
```

---

### Task 6: 쿼터 경로가 쿼리·바디로 신원을 받지 않는다

**Files:**
- Modify: `app/routes/kr_market_quota_http_routes.py:35-36`, `:59-60`
- Modify: `app/routes/common_update_routes.py:181-183`
- Modify: `services/kr_market_quota_service.py:51-54` (주석만)
- Test: `tests/app/test_kr_market_quota_http_routes_refactor.py` (기존 파일을 고친다)

**Interfaces:**
- Consumes: Task 4 의 `g.user_email` 과 `g.session_id`
- Produces: `resolve_quota_usage_key(user_email, session_id)` 의 **시그니처는 그대로다.** 부르는 자리가 헤더·쿼리·바디 대신 `g` 를 넘기도록만 바뀐다.

**왜 시그니처를 바꾸지 않는가.** 익명에게서 쿼터 키를 빼앗으면 `build_quota_info_payload`
의 `not usage_key` 분기가 잡혀 `/user/quota` 가 언제나 「무료 10회 사용 가능」을 낸다.
그런데 `services/kr_market_chatbot_quota_helpers.py` 의 `check_chatbot_quota_guard` 는
여전히 세션 ID 로 세어 10회에서 402 를 낸다. **화면은 10회가 남았다고 하고 서버는 막는
갈림이 생긴다.** 익명 챗봇을 유지하기로 한 이상 표시와 집행이 같은 키를 써야 하므로,
이번에 없애는 것은 쿼리 파라미터와 요청 바디로 신원을 받던 경로뿐이다.

- [ ] **Step 1: 기존 검사를 이번 계약에 맞게 고친다**

`tests/app/test_kr_market_quota_http_routes_refactor.py` 는 지금 쿼리와 바디로 신원을
넘긴다. 그 경로를 없애는 것이 이번 변경이므로, **기대값이 아니라 조립 방식을 고친다.**

`_create_client` 가 `_register_request_context` 를 부르지 않아 `g` 에 속성이 없다.
`g.get("user_email")` 이 없는 속성에 None 을 주므로 지금은 동작하지만, 그 사실에 기대는
검사가 된다. 신원을 주입할 자리를 명시적으로 만든다.

```python
def _create_client(
    *,
    max_free_usage: int = 10,
    get_user_usage_fn: Callable[[str | None], int] | None = None,
    recharge_usage_fn: Callable[[str | None, int], tuple[int, bool]] | None = None,
    user_email: str | None = None,
    session_id: str | None = None,
):
    app = Flask(__name__)
    app.testing = True

    # [INFRA-027] 신원은 before_request 가 확정한다. 라우트가 쿼리나 바디에서 신원을
    # 읽지 않는지 보려면 여기서 g 를 채워 주어야 한다.
    @app.before_request
    def _inject_identity():
        g.user_email = user_email
        g.session_id = session_id

    bp = Blueprint("kr_test_quota_routes", __name__)
    quota_routes.register_quota_routes(
        bp,
        logger=logging.getLogger("test.kr_market_quota_routes"),
        max_free_usage=max_free_usage,
        get_user_usage_fn=get_user_usage_fn or (lambda _usage_key: 0),
        recharge_usage_fn=recharge_usage_fn or (lambda _usage_key, _amount: (0, True)),
    )
    app.register_blueprint(bp, url_prefix="/api/kr")
    return app.test_client()
```

파일 위쪽 import 에 `g` 를 더한다.

```python
from flask import Blueprint, Flask, g
```

그다음 네 검사를 고친다.

```python
def test_get_user_quota_info_returns_expected_payload(monkeypatch):
    # ... monkeypatch 부분은 그대로 ...
    client = _create_client(get_user_usage_fn=lambda _usage_key: 3, session_id="anon_1")

    # 쿼리 파라미터로 신원을 넘기지 않는다. 넘겨도 무시되어야 한다.
    response = client.get("/api/kr/user/quota?email=victim@example.com")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["usage"] == 3
    assert payload["remaining"] == 7
    assert payload["server_key_configured"] is True


def test_get_user_quota_info_returns_error_payload_on_exception(monkeypatch):
    # ... monkeypatch 부분은 그대로 ...
    client = _create_client(
        get_user_usage_fn=lambda _usage_key: (_ for _ in ()).throw(RuntimeError("quota boom")),
        session_id="anon_1",
    )

    response = client.get("/api/kr/user/quota")

    assert response.status_code == 500
    assert response.get_json() == {"error": "quota boom"}


def test_recharge_user_quota_requires_identity():
    """[INFRA-027] 신원 없이는 충전할 수 없다. 종전에는 바디의 session_id 로 충분했다."""
    client = _create_client()

    response = client.post("/api/kr/user/quota/recharge", json={"session_id": "anon_1"})

    assert response.status_code == 401
    assert response.get_json() == {"error": "로그인이 필요합니다."}


def test_recharge_user_quota_returns_success_payload():
    client = _create_client(
        recharge_usage_fn=lambda _usage_key, _amount: (4, True),
        user_email="owner@example.com",
    )

    response = client.post("/api/kr/user/quota/recharge", json={})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "success"
    assert payload["usage"] == 4
    assert payload["remaining"] == 6


def test_recharge_user_quota_returns_error_payload_on_exception():
    client = _create_client(
        recharge_usage_fn=lambda _usage_key, _amount: (
            (_ for _ in ()).throw(RuntimeError("recharge boom"))
        ),
        user_email="owner@example.com",
    )

    response = client.post("/api/kr/user/quota/recharge", json={})

    assert response.status_code == 500
    assert response.get_json() == {"error": "recharge boom"}
```

`test_recharge_user_quota_requires_usage_key` 는 위의 `..._requires_identity` 로
이름과 기대값이 함께 바뀐다. 400 과 「세션 정보가 없습니다.」를 기대하던 검사다.

- [ ] **Step 2: 검사가 실패하는 것을 확인한다**

Run: `source venv/bin/activate && pytest tests/app/test_kr_market_quota_http_routes_refactor.py -v`
Expected: FAIL. 라우트가 아직 쿼리·바디를 읽으므로 `..._requires_identity` 가 401 대신
400 을 받고, 충전 성공 검사는 `usage_key` 가 None 이라 거절된다.

- [ ] **Step 3: 라우트를 고친다**

`app/routes/kr_market_quota_http_routes.py`. 파일 위쪽에 `from flask import g` 를 더한다.

```python
# 조회 (:35-36)
            # 신원은 before_request 가 확정한다. 종전에는 쿼리 파라미터로도 받았는데,
            # 그러면 헤더를 막아도 URL 한 줄로 남의 쿼터를 조회할 수 있었다.
            usage_key = resolve_quota_usage_key(
                user_email=g.get("user_email"),
                session_id=g.get("session_id"),
            )

# 충전 (:59-60)
            # 충전은 익명에게 열지 않는다. 익명 ID 는 브라우저가 지우면 새로 발급되므로
            # 하루 1회 제한이 성립하지 않는다.
            usage_key = g.get("user_email")
```

충전 라우트의 거절 응답도 고친다.

```python
            if not usage_key:
                return jsonify({"error": "로그인이 필요합니다."}), 401
```

`request.args.get("email")`, `request.args.get("session_id")`, `data.get("email")`,
`data.get("session_id")` 네 자리를 지운다. 충전 라우트에서 `data` 를 더 쓰지 않으면
`data = request.get_json() or {}` 줄도 함께 지운다.

`app/routes/common_update_routes.py:181-183`:

```python
            # g 의 두 값은 검증을 거쳤다. 헤더를 그대로 읽으면 활동 로그의 사용자 칸을
            # 아무 문자열로나 채울 수 있다.
            session_id = g.get("session_id")
            user_id = g.get("user_email") or session_id
```

아래에서 `details["session_id"]` 를 채우는 코드는 이 `session_id` 를 그대로 쓴다.

- [ ] **Step 4: 두 헬퍼의 계약을 주석으로 못박는다**

시그니처는 바뀌지 않지만, 넘길 값의 조건이 바뀌었다. 그 조건을 함수 옆에 적지 않으면
다음 사람이 검증하지 않은 값을 넘긴다.

`services/kr_market_quota_service.py` 의 `resolve_quota_usage_key`:

```python
def resolve_quota_usage_key(user_email: str | None, session_id: str | None) -> str | None:
    """로그인 여부를 고려해 quota usage key를 계산한다.

    두 인자 모두 `services/identity_helpers.py` 의 검증을 통과한 값만 넣는다.
    `user_email` 은 `verify_identity_header` 의 반환값이고 `session_id` 는
    `resolve_anonymous_id` 의 반환값이다. 요청 헤더나 쿼리 파라미터를 그대로 넘기면
    문자열 하나로 남의 쿼터를 조회하거나 소진시킬 수 있다.

    아래 `user@example.com` 비교는 `verify_identity_header` 가 이미 걸러 낸 값을 다시
    보는 하류 안전망이다. 실제 게이트는 그쪽 한 자리이므로, 이 비교가 있다는 이유로
    검증하지 않은 값을 넘기지 않는다.
    """
```

`services/kr_market_chatbot_request_helpers.py` 의 두 헬퍼는 Task 5 에서 이미 같은
취지로 고쳤다. 여기서 다시 손대지 않는다.

- [ ] **Step 5: 검사가 통과하는 것을 확인한다**

Run: `source venv/bin/activate && pytest tests/app/test_kr_market_quota_http_routes_refactor.py -v`
Expected: PASS

- [ ] **Step 6: 라우트에 신원을 읽는 다른 경로가 없는지 본다**

```bash
grep -n 'args.get\|data.get' app/routes/kr_market_quota_http_routes.py
```
Expected: `email` 이나 `session_id` 를 읽는 줄이 없다

- [ ] **Step 7: 전체 pytest 를 돌린다**

Run: `source venv/bin/activate && pytest -q`
Expected: 통과. 실패는 옛 계약을 쓰는 검사이므로 호출 쪽을 고친다. 기대값을 바꿔
통과시키지 않는다.

- [ ] **Step 8: 커밋한다**

```bash
git add app/routes/kr_market_quota_http_routes.py app/routes/common_update_routes.py \
        services/kr_market_quota_service.py \
        tests/app/test_kr_market_quota_http_routes_refactor.py
git commit -m "fix(security): [INFRA-027] 쿼터 신원을 쿼리·바디에서 받지 않는다"
```

---

### Task 7: 충전을 하루 한 번으로 제한한다

**Files:**
- Modify: `services/kr_market_quota_runtime_service.py:55-79`
- Modify: `app/routes/kr_market.py:329` (`_recharge_user_usage`)
- Modify: `app/routes/kr_market_quota_http_routes.py:28`, `:66` (충전 응답과 타입 힌트)
- Modify: `app/routes/kr_market_chatbot_routes.py:24` (타입 힌트)
- Test: `tests/services/test_quota_recharge_daily_limit.py` (신규)
- Test: `tests/app/test_kr_market_quota_http_routes_refactor.py` (Task 6 에서 이미 튜플로 고쳤다. 여기서는 통과만 확인한다)

**Interfaces:**
- Consumes: Task 6 이 충전 라우트에서 `usage_key = g.get("user_email")` 로 정한 신원. 충전은 익명에게 열지 않으므로 쿼터 조회와 달리 세션 ID 로 떨어지지 않는다
- Produces: `recharge_user_usage(...)` 에 `today: int` 키워드 인자가 추가되고, 반환이 `tuple[int, bool]` 이 된다. 두 번째 값은 실제로 충전했는지 여부다.

**반환 형이 바뀌므로 아래 네 자리를 함께 고친다.** 하나라도 빠뜨리면 튜플이 정수 자리에
들어가 `max(0, max_free_usage - new_usage)` 에서 `TypeError` 가 난다.

| 파일 | 지금 | 바꿀 것 |
|---|---|---|
| `app/routes/kr_market.py:329` | `def _recharge_user_usage(usage_key: str \| None, amount: int) -> int:` | 반환을 `tuple[int, bool]` 로 하고 `today` 를 채워 넘긴다 |
| `app/routes/kr_market_quota_http_routes.py:28` | `recharge_usage_fn: Callable[[str \| None, int], int]` | `Callable[[str \| None, int], tuple[int, bool]]` |
| `app/routes/kr_market_chatbot_routes.py:24` | 같은 타입 힌트 | 같은 방식으로 바꾼다 |
| `app/routes/kr_market_quota_http_routes.py:66` | `new_usage = int(recharge_usage_fn(usage_key, 5))` | 튜플을 풀어 받는다 |

- [ ] **Step 1: 실패하는 검사를 쓴다**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[INFRA-027] 충전 하루 1회 제한 회귀 테스트

이 제한이 없으면 사이드바의 + 버튼을 두 번 눌러 무료 10회가 초기화된다.
"""

import os
import sys
import threading

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from services.kr_market_quota_runtime_service import recharge_user_usage


def _make_store(initial: dict[str, int]):
    """load/save 를 메모리 dict 하나로 잇는 최소 하네스."""
    store = dict(initial)

    def load(**_kwargs):
        return dict(store)

    def save(quota_data, **_kwargs):
        store.clear()
        store.update(quota_data)

    return store, load, save


def _recharge(store_fns, usage_key: str, today: int):
    _store, load, save = store_fns
    return recharge_user_usage(
        usage_key=usage_key,
        amount=5,
        today=today,
        quota_lock=threading.Lock(),
        load_quota_data_unlocked=load,
        save_quota_data_unlocked=save,
        load_json_file=lambda *_a, **_k: {},
        atomic_write_text=lambda *_a, **_k: None,
        quota_file_path="unused.json",
    )


def test_first_recharge_of_the_day_succeeds():
    store_fns = _make_store({"owner@example.com": 8})

    usage, recharged = _recharge(store_fns, "owner@example.com", 20260907)

    assert recharged is True
    assert usage == 3


def test_second_recharge_same_day_is_refused():
    store_fns = _make_store({"owner@example.com": 8})

    _recharge(store_fns, "owner@example.com", 20260907)
    usage, recharged = _recharge(store_fns, "owner@example.com", 20260907)

    assert recharged is False
    assert usage == 3


def test_next_day_recharge_succeeds():
    store_fns = _make_store({"owner@example.com": 8})

    _recharge(store_fns, "owner@example.com", 20260907)
    usage, recharged = _recharge(store_fns, "owner@example.com", 20260908)

    assert recharged is True
    assert usage == 0


def test_recharge_day_is_recorded_per_user():
    store, load, save = _make_store({"owner@example.com": 8, "other@example.com": 8})

    _recharge((store, load, save), "owner@example.com", 20260907)
    usage, recharged = _recharge((store, load, save), "other@example.com", 20260907)

    assert recharged is True
    assert usage == 3


def test_missing_usage_key_does_nothing():
    store_fns = _make_store({})

    usage, recharged = _recharge(store_fns, "", 20260907)

    assert recharged is False
    assert usage == 0
```

- [ ] **Step 2: 검사가 실패하는 것을 확인한다**

Run: `source venv/bin/activate && pytest tests/services/test_quota_recharge_daily_limit.py -v`
Expected: FAIL — `TypeError: recharge_user_usage() got an unexpected keyword argument 'today'`

- [ ] **Step 3: 구현을 고친다**

`services/kr_market_quota_runtime_service.py`:

```python
# 충전 이력을 같은 파일에 둔다. load_quota_data_unlocked 가 모든 값을 정수로 만들므로
# 날짜를 문자열로 넣으면 0 으로 뭉개진다. 그래서 20260907 형태의 정수로 적는다.
RECHARGE_DAY_PREFIX = "recharge_day:"


def recharge_user_usage(
    *,
    usage_key: str | None,
    amount: int,
    today: int,
    quota_lock,
    load_quota_data_unlocked: Callable,
    save_quota_data_unlocked: Callable,
    load_json_file: Callable[[str], dict],
    atomic_write_text: Callable[[str, str], None],
    quota_file_path: str,
) -> tuple[int, bool]:
    """사용자 사용량을 amount 만큼 감소(충전)한다. 하루 한 번만 허용한다.

    돌려주는 두 번째 값은 실제로 충전했는지 여부다. 부르는 자리가 그것을 보고 안내
    문구를 고른다. 사용량만 돌려주면 거절과 「이미 0회」를 구분할 수 없다.
    """
    if not usage_key:
        return 0, False

    day_key = f"{RECHARGE_DAY_PREFIX}{usage_key}"
    with quota_lock:
        quota_data = load_quota_data_unlocked(load_json_file=load_json_file)
        current_usage = int(quota_data.get(usage_key, 0))
        if int(quota_data.get(day_key, 0)) >= int(today):
            return current_usage, False

        new_usage = max(0, current_usage - int(amount))
        quota_data[usage_key] = new_usage
        quota_data[day_key] = int(today)
        save_quota_data_unlocked(
            quota_data=quota_data,
            atomic_write_text=atomic_write_text,
            quota_file_path=quota_file_path,
        )
    return int(new_usage), True
```

`app/routes/kr_market.py` 의 조립부에서 `recharge_usage_fn` 이 `today` 를 채우게 한다. `_recharge_user_usage` 정의 근처를 본다.

import 는 파일 상단에 둔다. 표준 모듈이고 무거워서 미루는 것이 아니므로 함수 안에서
부를 이유가 없다.

```python
# app/routes/kr_market.py 상단
from datetime import datetime, timedelta, timezone

# 한국 시장을 다루는 서비스이므로 하루의 경계도 KST 로 센다. 서버가 UTC 면 자정부터
# 오전 9시 사이에 하루가 두 번 바뀐 것처럼 보여 충전이 두 번 된다.
KST = timezone(timedelta(hours=9))


def _recharge_user_usage(usage_key: str | None, amount: int) -> tuple[int, bool]:
    """사용자 사용량을 amount 만큼 감소(충전)한다. 하루 한 번만 허용한다."""
    return recharge_user_usage_service(
        usage_key=usage_key,
        amount=amount,
        today=int(datetime.now(KST).strftime("%Y%m%d")),
        quota_lock=_quota_lock,
        load_quota_data_unlocked=load_quota_data_unlocked_service,
        save_quota_data_unlocked=save_quota_data_unlocked_service,
        load_json_file=load_json_file,
        atomic_write_text=_atomic_write_text,
        quota_file_path=QUOTA_FILE,
    )
```

`app/routes/kr_market.py` 상단에 이미 `datetime` 이 import 되어 있으면 그 줄을 쓴다.
중복 import 를 더하지 않는다.

`app/routes/kr_market_quota_http_routes.py` 의 충전 라우트:

```python
            new_usage, recharged = recharge_usage_fn(usage_key, 5)
            remaining = max(0, max_free_usage - new_usage)
            if not recharged:
                return jsonify(
                    {
                        "status": "error",
                        "code": "ALREADY_RECHARGED_TODAY",
                        "usage": new_usage,
                        "limit": max_free_usage,
                        "remaining": remaining,
                        "message": f"충전은 하루 한 번만 가능합니다. (남은 횟수: {remaining}회)",
                    }
                ), 429
            return jsonify(
                {
                    "status": "success",
                    "usage": new_usage,
                    "limit": max_free_usage,
                    "remaining": remaining,
                    "message": f"5회 충전 완료! (남은 횟수: {remaining}회)",
                }
            )
```

- [ ] **Step 4: 검사가 통과하는 것을 확인한다**

Run: `source venv/bin/activate && pytest tests/services/test_quota_recharge_daily_limit.py -v`
Expected: PASS, 5 passed

- [ ] **Step 5: 전체 pytest 를 돌린다**

Run: `source venv/bin/activate && pytest -q`
Expected: 통과

- [ ] **Step 6: 커밋한다**

```bash
git add services/kr_market_quota_runtime_service.py app/routes/kr_market.py app/routes/kr_market_quota_http_routes.py tests/services/test_quota_recharge_daily_limit.py
git commit -m "fix(security): [INFRA-027] 쿼터 충전을 하루 한 번으로 제한한다"
```

---

### Task 8: 프론트엔드에서 죽은 신원 값을 걷어낸다

**Files:**
- Modify: `frontend/src/app/components/chatHelpers.ts:38-56`
- Modify: `frontend/src/app/components/ChatWidget.tsx:246-251`
- Modify: `frontend/src/app/components/Sidebar.tsx:75`, `:105-112`, `:299-311`
- Modify: `frontend/src/app/components/SettingsModal.tsx:48`, `:443` 근처
- Test: `frontend/src/app/components/chatHelpers.test.ts` (기존 파일에 더한다)

**Interfaces:**
- Consumes: Task 3 의 proxy 가 `X-User-Email` 을 지운다는 사실
- Produces: 없음. 정리 작업이다.

이 작업은 기능을 바꾸지 않는다. proxy 가 어차피 지우는 값을 브라우저가 계속 보내면, 다음 사람이 그 헤더가 신원인 줄 알고 새 코드를 붙인다.

- [ ] **Step 1: 실패하는 검사를 쓴다**

`frontend/src/app/components/chatHelpers.test.ts` 에 더한다.

```ts
  it('[INFRA-027] 신원 이메일을 헤더로 보내지 않는다', () => {
    window.localStorage.setItem(
      'user_profile',
      JSON.stringify({ name: '홍길동', email: 'owner@example.com', persona: '' })
    );

    const headers = getAuthHeaders();

    expect(headers['X-User-Email']).toBeUndefined();
    expect(headers['X-Session-Id']).toBeTruthy();
  });
```

`getAuthHeaders` 를 import 하지 않고 있으면 파일 위쪽 import 절에 더한다.

- [ ] **Step 2: 검사가 실패하는 것을 확인한다**

Run: `cd frontend && npx vitest run src/app/components/chatHelpers.test.ts`
Expected: FAIL — `expected 'owner@example.com' to be undefined`

- [ ] **Step 3: `chatHelpers.ts` 를 고친다**

```ts
export function getAuthHeaders(): Record<string, string> {
  // 신원은 `frontend/src/proxy.ts` 가 NextAuth 세션에서 확정해 서명한다. 여기서
  // X-User-Email 을 실어 보내도 proxy 가 지우므로, 신원인 것처럼 보이는 값을 남기지
  // 않는다. X-Session-Id 는 익명 사용자의 챗봇 대화를 잇는 데 계속 쓰인다.
  return {
    'X-Session-Id': getBrowserSessionId()
  };
}
```

- [ ] **Step 4: `ChatWidget.tsx` 를 고친다**

`:246-251` 의 헤더에서 `'X-User-Email': userEmail || '',` 줄을 지운다. `userEmail` 을 그 자리에서만 쓰고 있었다면 위쪽의 선언도 함께 지운다. `npm run type-check` 가 미사용 변수를 잡지 못하므로 `grep -n userEmail frontend/src/app/components/ChatWidget.tsx` 로 직접 확인한다.

- [ ] **Step 5: `Sidebar.tsx` 세 자리를 고친다**

`:75` 의 쿼터 조회에서 쿼리 파라미터를 지운다. Task 6 이 서버에서 이 값을 읽지 않게
했으므로 남겨 두면 죽은 값이 된다.

```tsx
    fetch('/api/kr/user/quota')
```

`email` 과 `sessionId` 를 그 자리에서만 쓰고 있었다면 위쪽 선언도 함께 지운다.

`:105-112` 의 `log-event` 호출에서 `'X-User-Email': email,` 줄을 지운다.

`:299-311` 의 충전 버튼에서 요청 바디의 신원을 지우고, 429 응답을 안내한다.

```tsx
                        onClick={async (e) => {
                          e.stopPropagation();
                          try {
                            const res = await fetch('/api/kr/user/quota/recharge', {
                              method: 'POST',
                              headers: { 'Content-Type': 'application/json' }
                            });
                            const data = await res.json();
                            if (res.ok) {
                              setQuota(data);
                              setAlertModal({ isOpen: true, type: 'success', title: '충전 완료', content: data.message });
                            } else {
                              setAlertModal({ isOpen: true, type: 'error', title: '충전할 수 없습니다', content: data.message || data.error || '잠시 후 다시 시도해 주세요.' });
                            }
                          } catch (e) { console.error(e); }
                        }}
```

`title="5회 충전"` 을 `title="5회 충전 (하루 1회)"` 로 바꾼다. 하루 한 번이라는 사실이 화면에 없으면 사용자가 눌러 보고서야 안다.

- [ ] **Step 6: `SettingsModal.tsx` 두 자리를 고친다**

`:48` 의 쿼터 조회에서 쿼리 파라미터를 지운다.

```tsx
      fetch('/api/kr/user/quota')
```

`:443` 근처의 `fetch('/api/kr/user/quota/recharge', ...)` 에서 요청 바디의 `email` 과
`session_id` 를 지우고, 실패 응답을 사용자에게 알린다.

- [ ] **Step 7: 검사와 타입을 확인한다**

Run: `cd frontend && npx vitest run && npm run type-check`
Expected: 둘 다 통과

- [ ] **Step 8: 남은 자리가 없는지 본다**

```bash
grep -rn "X-User-Email" frontend/src --include='*.ts' --include='*.tsx' | grep -v '.test.'
grep -rn "quota?email=\|quota?session_id=" frontend/src
```
Expected: 둘 다 출력 없음.

두 번째 명령이 필요한 이유는, 첫 번째가 헤더만 보기 때문이다. 쿼리 파라미터로 신원을
넘기던 자리를 남기면 이 작업의 목적이 절반만 달성된다. 다음 사람이 그 값을 신원인 줄 알고
새 코드를 붙이는 것을 막는 것이 이 작업의 존재 이유다.

`scripts/patches/` 아래의 옛 패치 스크립트는 실행되지 않는 기록물이라 건드리지 않는다.

- [ ] **Step 9: 커밋한다**

```bash
git add frontend/src/app/components/
git commit -m "refactor(security): [INFRA-027] 프론트에서 죽은 신원 헤더를 걷어낸다"
```

---

## 검증

모든 작업을 마친 뒤 한 번에 돌린다.

```bash
source venv/bin/activate && pytest
cd frontend && npx vitest run
cd frontend && npm run type-check
cd frontend && npm run build
```

`.env` 확인 세 가지(`tier-rules.md` §1):

```bash
git ls-files | grep '^\.env'                          # .env.example 만 나와야 한다
grep -rn 'NEXT_PUBLIC_' frontend/src | grep -i 'secret\|token'   # 출력 없음
grep -rn 'INTERNAL_IDENTITY_SECRET' frontend/src      # proxy.ts 한 자리만
grep '^NEXTAUTH_URL=' .env.production | grep -c '^NEXTAUTH_URL=https://'   # 1
```

서명 헤더가 로그에 남지 않는지도 본다. `X-Auth-Identity` 는 120초 동안 어느
엔드포인트에나 쓸 수 있는 bearer 이므로, 로그에 남으면 로그를 읽을 수 있는 사람이 그
시간 안에 아무 사용자로나 행세할 수 있다.

```bash
grep -rn 'X-Auth-Identity' app/ services/ | grep -iv 'test'   # verify 호출 한 자리만
grep -rn 'request.headers' app/ services/ | grep -i 'log\|print'   # 출력 없음
```

nonce 저장소를 두어 재사용 자체를 막는 방법도 있으나 이 규모에서는 과잉이다. proxy 와
Flask 사이가 loopback 이고 TTL 이 120초이므로, 「로그에 남기지 않는다」를 지키는 것으로
충분하다.

## 리뷰

T3 이므로 순서를 지킨다.

1. `/ponytail-review`
2. `feature-dev:code-reviewer` (`Agent` 도구에 `name` 을 준다)
3. `/review`
4. `oh-my-claudecode:security-reviewer` (`name` 을 준다)

## QA 시나리오 초안

`docs/dev-cycle/qa/INFRA-027.md` 에 옮겨 적는다. 앞의 다섯은 필수다.

**회귀 — 이번에 막은 것**

1. 위조한 `X-User-Email` 로 `/api/kr/chatbot/sessions` 를 불러도 그 사람의 세션 목록이 오지 않는다
2. **`X-Session-Id: <관리자 이메일>` 로 불러도 세션 목록이 오지 않고 쿼터가 무제한이 되지 않는다.** 이 시나리오가 없으면 헤더 이름 하나로 게이트 전체가 우회되는 것을 놓친다
3. 위조한 `X-Auth-Identity` 와 만료된 서명이 익명으로 처리된다
4. 쿼리 파라미터 `?email=<남의 이메일>` 로 `/api/kr/user/quota` 를 불러도 그 사람의 사용량이 오지 않는다
5. `+` 버튼을 두 번째 누르면 429 와 「충전은 하루 한 번만 가능합니다」가 나온다

**인접 — 깨지지 않아야 할 것**

6. 로그인한 사용자의 챗봇 대화 목록이 그대로 보인다. **이것이 M-4 가 지적한 가정을 화면에서 확인하는 자리다.** 여기서 목록이 비면 proxy 의 헤더가 Flask 에 닿지 않은 것이다
7. 익명 사용자가 대시보드를 보고 챗봇으로 대화할 수 있으며, 브라우저를 새로 고쳐도 그 대화가 이어진다
8. 익명 사용자가 `/api/kr/reanalyze/gemini` 에서 401 을 받는다
9. 사이드바의 「N회 남음」 표시와 실제 챗봇 거절 시점이 어긋나지 않는다

**설정 오류 — 조용히 죽는 경로**

10. `INTERNAL_IDENTITY_SECRET` 이 비면 모든 요청이 익명으로 떨어진다. 관리자 화면이나 로그로 그 사실을 알 수 있는지 확인하고, 알 수 없으면 그 사실을 QA 문서에 남긴다
11. `.env.production` 의 `NEXTAUTH_URL` 이 `https://` 로 시작한다. 이 값이 http 이면 운영에서 `getToken` 이 언제나 null 을 돌려주어 로그인 사용자 전원이 조용히 익명이 된다
