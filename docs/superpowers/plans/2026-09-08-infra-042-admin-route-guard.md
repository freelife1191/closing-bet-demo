# [INFRA-042] 관리자 라우트 게이트 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 화면이 이미 관리자 전용으로 막았는데 서버만 열려 있는 라우트 여섯에 인가
게이트를 세운다.

**Architecture:** `require_admin` 데코레이터 하나를 `app/routes/route_guards.py` 에 두고
여섯 라우트에 붙인다. 판정은 기존 `services.admin_helpers.is_admin_email` 이 맡고
데코레이터는 `g.user_email` 을 꺼내 넘기는 일만 한다. 판정 규칙이 파이썬과 타입스크립트에
두 벌 존재하므로 같은 케이스 목록을 두 검사가 함께 읽어 표류를 잡는다.

**Tech Stack:** Flask (`g`, `jsonify`, `functools.wraps`), pytest, vitest

**Spec:** 대화 설계(2026-09-08)와 `docs/dev-cycle/TODO.md` 의 `[INFRA-042]` 항목. 범위
확정과 게이트 표준, `OPTIONS` 예외의 근거가 그 항목에 있다.

## Global Constraints

- 티어 T3. 리뷰는 `/ponytail-review` → `feature-dev:code-reviewer` → `/review` 순서를
  지키고, 인가 변경이므로 `oh-my-claudecode:security-reviewer` 를 더한다.
- 게이트 판정은 `is_admin_email(g.get("user_email"))` 하나로 통일한다.
  `verify_admin_api_token` 은 이 자리에 쓰지 않는다.
- 거부 응답은 `{"error": "Forbidden"}` 과 403 이다. **저장소에 Forbidden 응답 형식이 두
  가지 공존한다.** `common_update_routes.py:230` 의 관리자 토큰 게이트가
  `jsonify({"error": "Forbidden"}), 403` 이고, `common_notification_routes.py:136` 은
  `_build_error_response("Forbidden", 403)` 을 거쳐 `{"status": "error", "message":
  "Forbidden"}` 을 낸다(그 함수는 같은 파일 `:88-89`). 앞엣것을 고른다. 이 게이트가 하는
  일이 인가 거부이고 그것이 `common_update_routes.py:230` 과 같기 때문이며, 두 형식 모두
  `frontend/src/lib/api.ts:34` 의 `data?.message || data?.error` 가 문구를 올리므로 화면
  동작은 같다. **형식을 통일하는 것은 이번 범위가 아니다.**
- 부류 B(`kr/refresh`, `market-gate/update`, `config/interval`)와 부류 C(모의투자 넷)는
  건드리지 않는다. 이유는 TODO 항목의 「범위 확정」에 있다.
- 기존 게이트 두 자리(`common_notification_routes.py:135`,
  `common_update_routes.py:229`)를 데코레이터로 바꾸지 않는다. 승인 범위 밖이다.
- `.env` 파일에 쓰지 않고, 알림을 실제로 발송하지 않으며, 사용자가 띄워 둔 5501·3500
  프로세스를 재기동하지 않는다.

---

## 사전 실측 — 이 계획이 딛고 선 사실

구현 전에 확인해 둔 것이며, 계획의 각 결정이 이 가운데 어느 것에 기대는지 적는다.

1. **부류 A 여섯은 화면이 이미 막고 있다.** `useAdmin` 훅(`frontend/src/hooks/useAdmin.ts`)이
   `/api/admin/check` 를 불러 `isAdmin` 을 받는다. 라우트별 호출자와 그 방어는 이렇다.

   경로를 줄여 적되 깊이가 다르다는 것을 먼저 밝힌다. `closing-bet/page.tsx` 와
   `vcp/page.tsx` 는 `frontend/src/app/dashboard/kr/` 아래이고 `data-status/page.tsx` 는
   `frontend/src/app/dashboard/` 바로 아래다. 셋을 같은 깊이로 읽으면 헛걸음한다.

   | 라우트 | 화면 호출자 | 무엇이 막는가 |
   |---|---|---|
   | `jongga-v2/run` | `closing-bet/page.tsx:1741` (`requestCostlyAction`) | `:1728` 의 `if (!isAdmin)` |
   | `jongga-v2/reanalyze-gemini` | `closing-bet/page.tsx:938` 과 `:1765` **두 자리** | `:918` 과 `:1728` 의 `if (!isAdmin)` |
   | `jongga-v2/message` | `data-status/page.tsx:419` (`performSendMessage`) | **버튼 렌더링뿐** (`:647`) |
   | `signals/run` | `frontend/src/lib/api.ts:201` 의 `krAPI.runVCPScreener` 경유, 호출은 `vcp/page.tsx:1264` | `:1254` 의 `if (!isAdmin)` |
   | `init-data` | **없음** (`frontend/src` 전체에서 `init-data`·`initData` 무결과) | — |
   | `system/start-update` | `data-status/page.tsx:275`·`:349` | `:303`·`:330` 의 `if (!isAdmin)` |

   → Task 2 가 화면을 한 줄도 고치지 않는 근거다.

   **`jongga-v2/message` 만 방어가 한 겹이라는 것을 특히 적어 둔다.**
   `performSendMessage`(`data-status/page.tsx:415`)에는 다른 다섯과 달리 함수 본문에
   `if (!isAdmin)` 이 **없다.** 관리자 전용인 근거가 `:647` 의
   `{file.name === 'AI Jongga V2' && isAdmin && (` 라는 조건부 렌더링 하나뿐이다. 즉 여섯
   가운데 **가장 위험한 라우트가 방어도 가장 얇다.** 이것은 게이트를 미룰 이유가 아니라
   서두를 이유다. 조건부 렌더링은 개발자 도구로 걷어낼 수 있고, 서버가 열려 있으면
   화면을 거치지 않고 곧바로 칠 수도 있다.

2. **`/api/admin/check` 는 서버 게이트와 같은 함수를 쓴다.**
   `app/routes/common_admin_routes.py:30` 이 `is_admin_email(g.get("user_email"))` 이다.
   → Task 1 이 같은 판정을 고른 근거다. 두 판정이 갈리면 버튼은 보이는데 요청은 403 이
   되거나 그 반대가 된다.

3. **`before_request` 는 OPTIONS 에서 일찍 반환한다.** `app/__init__.py:171` 의
   `if request.method == 'OPTIONS': return` 이 `g.user_email` 대입보다 앞에 있다.
   그래서 OPTIONS 요청에서 `g.get("user_email")` 은 항상 `None` 이고, 예외를 두지 않으면
   `is_admin_email(None)` 이 `False` 를 내 403 이 나간다.
   → Task 1 Step 3 의 OPTIONS 예외가 여기서 나온다.

4. **`reanalyze-gemini` 만 `methods` 에 OPTIONS 를 갖고 있다.**
   `kr_market_jongga_execution_routes.py:167`. 그 라우트는 본문 첫 줄에서
   `if request.method == "OPTIONS": return jsonify({"status": "ok"}), 200` 으로 빠지므로
   부작용이 없다.

   **나머지 다섯에서는 OPTIONS 갈래에 도달조차 하지 않는다.** `methods=["POST"]` 만 둔
   라우트에 OPTIONS 를 보내면 Flask 가 자체 처리로 `200` 과 `Allow` 헤더를 돌려주면서
   **뷰 함수를 아예 부르지 않는다**(계획 검토에서 최소 앱을 세워 실측). 그러므로
   데코레이터의 OPTIONS 갈래는 오직 `reanalyze-gemini` 하나를 위해 존재한다.
   → OPTIONS 를 통과시켜도 게이트에 구멍이 나지 않는 근거다. 동시에, **`methods` 에
   OPTIONS 를 두면서 부작용이 있는 핸들러를 새로 만들면 이 전제가 깨진다**는 뜻이므로
   데코레이터 docstring 에 그 조건을 적는다.

5. **`jongga-v2/message` 는 `{"force": true}` 로 중복 가드를 건너뛴다.**
   같은 파일 `:216` 의 `force_send = bool(data.get("force"))` 가 참이면
   `claim_jongga_notification_send` 를 아예 부르지 않는다. `:238` 이 `Messenger()` 를
   만들고 `:240` 의 `messenger.send_screener_result(result)` 가 **실제 종가베팅 시그널
   메시지**를 보낸다. 횟수 제한이 없다.
   → Task 2 Step 1 의 검사가 이 조합을 직접 친다.

6. **관리자 판정이 두 언어에 두 벌 있다.** `services/admin_helpers.py:20` 의
   `is_admin_email` 과 `frontend/src/lib/adminEmails.ts` 의 `isAdminEmail` 이다. 후자의
   docstring 이 「한쪽을 고치면 다른 쪽도 고친다」고 적고 있을 뿐 강제하는 검사가 없다.
   파이썬 쪽에는 이 함수 전용 검사가 아예 없다(`grep` 으로 확인).
   → Task 3 이 여기서 나온다.

7. **저장소에 이 라우트들을 HTTP 로 부르는 서버 측 자리가 없다.** `services/`, `engine/`,
   `scripts/`, `run.py`, `flask_app.py` 를 훑어 걸린 것은 `kr_market_flow_service.py:263`
   의 주석 한 줄뿐이다. 스케줄러는 함수를 직접 부르지 라우트를 치지 않는다.
   → 게이트가 서버 내부 경로를 끊지 않는 근거다.

8. **게이트로 깨질 기존 검사는 한 파일뿐이다.**
   `tests/app/test_kr_market_jongga_execution_routes_refactor.py` 가 대상 라우트 셋을
   부르고(`:73`, `:224`, `:248`, `:285`, `:286`, `:315`), 그 `_create_client`(`:42`)는
   `before_request` 를 세우지 않아 `g.user_email` 이 아예 없다. `signals/run`,
   `init-data`, `start-update` 를 부르는 검사는 저장소에 없다.
   → Task 2 Step 5 가 이 한 파일만 다루면 된다.

9. **그 파일의 `:211` 이 이미 OPTIONS 를 재고 있다.**
   `client.open("/api/kr/jongga-v2/reanalyze-gemini", method="OPTIONS")` 로 신원 없는
   preflight 가 200 인지 본다. **게이트의 OPTIONS 예외를 빼면 이 기존 검사가 깨진다.**
   회귀 보호가 이미 있다는 뜻이므로 새 검사를 더하되 이 자리를 지운다거나 기대값을 바꾸지
   않는다.

10. **Task 3 의 케이스 13개를 두 구현으로 미리 대조했다.** 파이썬은
    `services.admin_helpers.is_admin_email` 을 직접 불러, 타입스크립트는 `adminEmails.ts`
    의 본문을 그대로 옮긴 스크립트를 `node` 로 돌려 확인했다. **양쪽 모두 13/13 이
    기대값과 일치한다.** 즉 이 케이스 목록은 지금 상태를 고정하는 것이지 새 동작을
    요구하지 않는다.

11. **두 구현이 오늘 실제로 갈리는 입력이 있다. 공백 문자다.** 파이썬 `str.strip()` 과
    자바스크립트 `String.prototype.trim()` 은 공백으로 보는 집합이 다르다. 양쪽 런타임에서
    직접 쟀다.

    | 문자 | 파이썬 `strip()` | 자바스크립트 `trim()` |
    |---|---|---|
    | U+001C 파일 구분자 | 제거함 | 제거 **안 함** |
    | U+0085 NEL | 제거함 | 제거 **안 함** |
    | U+FEFF BOM | 제거 **안 함** | 제거함 |
    | U+00A0 NBSP | 제거함 | 제거함 |
    | U+2028 줄 구분자 | 제거함 | 제거함 |

    **BOM 이 현실적인 위험이다.** 운영자가 `ADMIN_EMAILS` 에 값을 붙여 넣다 앞에 BOM 이
    섞이면, 자바스크립트는 잘라 내 관리자로 판정하고 파이썬은 잘라 내지 않아 거부한다.
    결과는 **버튼은 보이는데 요청이 403 을 받는 상태**이며, 사전 실측 2 가 「두 판정이
    갈리면 생긴다」고 적은 바로 그 증상이다. 지금은 서버 게이트가 알림 하나뿐이라 드러날
    면이 좁지만 이번에 여섯이 늘면 그만큼 넓어진다.

    U+0085 와 U+001C 는 방향이 반대여서 서버가 통과시키고 화면이 거부한다. 이쪽은 실질
    위험이 낮다. `g.user_email` 은 `verify_identity_header` 가 proxy 서명을 검증해 꺼낸
    값이고 그 값은 NextAuth 토큰에서 왔으므로, 공격자가 서명 없이 뒤에 NEL 한 글자를 붙일
    수 없다.

    **들어갈 경로를 확인했다. 공격 경로가 아니다.** `ADMIN_EMAILS` 는
    `services/common_env_service.py:117-132` 의 `EDITABLE_ENV_KEYS` 에 **없다.** 설정
    화면으로는 이 키를 바꿀 수 없고, `:214` 의 필터가 목록 밖 키를 통째로 버린다. 그러므로
    BOM 이 들어가려면 서버 접근 권한이 있는 사람이 `.env` 를 직접 편집해야 한다. 즉 이것은
    **운영자의 붙여넣기 실수** 경로이지 공격자가 쓸 수 있는 경로가 아니다.

    → **이번 범위에서 고치지 않고 별도 항목으로도 올리지 않는다.** 유입 경로가 수작업
    편집뿐이라 항목을 세워도 심각도를 방어할 수 없다. 공유 케이스 파일의 `_ceiling` 에
    천장 한 줄로 남기고, 나중에 정규화를 손대는 항목이 생기면 그때 이 사실을 근거로
    접어 넣는다(계획 검토의 권고).

---

## File Structure

**신규**

- `app/routes/route_guards.py` — `require_admin` 하나. Flask `g` 와 `jsonify` 에 의존하므로
  순수 판정 모듈인 `services/admin_helpers.py` 에 두지 않는다. 소비자가 라우트 파일 넷에
  흩어져 있어 공용 자리가 필요하다.
- `tests/app/test_route_guards.py` — 데코레이터 자체의 검사. 최소 Flask 앱을 세워
  `tests/app/test_identity_gate.py` 의 방식을 따른다.
- `tests/fixtures/admin_email_cases.json` — 두 언어가 함께 읽는 케이스 목록.
- `tests/services/test_admin_helpers.py` — 파이썬 쪽 판정 검사(공유 케이스 사용).

**수정**

- `app/routes/kr_market_jongga_execution_routes.py` — 라우트 셋에 데코레이터
- `app/routes/kr_market_data_signals_routes.py` — `signals/run`
- `app/routes/kr_market_system_http_routes.py` — `init-data`
- `app/routes/common_update_routes.py` — `system/start-update`
- `frontend/src/lib/adminEmails.test.ts` — 공유 케이스를 읽는 검사 추가
- `CLAUDE.md` — `ADMIN_API_TOKEN` 회전 절차

---

## Task 1: `require_admin` 데코레이터

**Files:**
- Create: `app/routes/route_guards.py`
- Test: `tests/app/test_route_guards.py`

**Interfaces:**
- Consumes: `services.admin_helpers.is_admin_email(email: str | None) -> bool`
- Produces: `require_admin(view: Callable) -> Callable` — Flask 뷰 함수를 감싸는
  데코레이터. `@kr_bp.route(...)` **아래**에 붙인다(라우트 등록이 감싼 함수를 보아야 한다).

- [ ] **Step 1: 실패하는 검사를 쓴다**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""관리자 라우트 게이트 회귀 테스트

화면이 버튼을 감추는 것과 서버가 요청을 거부하는 것은 다른 일이다. [INFRA-042] 이전에는
앞의 것만 있었다.
"""

import os
import sys

import pytest
from flask import Flask, jsonify

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from app.routes.route_guards import require_admin


def _create_client(monkeypatch, *, identity_email: str | None):
    """신원이 이미 확정된 상태를 만들어 게이트만 잰다.

    before_request 의 서명 검증은 tests/app/test_identity_gate.py 가 따로 잰다. 여기서
    그것까지 세우면 게이트가 아니라 서명을 재게 된다.
    """
    app = Flask(__name__)
    app.testing = True

    @app.before_request
    def _seed_identity():
        from flask import g, request

        if request.method == "OPTIONS":
            return
        g.user_email = identity_email

    @app.route("/probe", methods=["POST", "OPTIONS"])
    @require_admin
    def probe():
        from flask import request

        if request.method == "OPTIONS":
            return jsonify({"status": "ok"}), 200
        return jsonify({"status": "ran"})

    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")
    return app.test_client()


def test_request_without_identity_is_refused(monkeypatch):
    client = _create_client(monkeypatch, identity_email=None)
    res = client.post("/probe")
    assert res.status_code == 403
    assert res.get_json() == {"error": "Forbidden"}


def test_non_admin_identity_is_refused(monkeypatch):
    client = _create_client(monkeypatch, identity_email="someone@example.com")
    res = client.post("/probe")
    assert res.status_code == 403


def test_admin_identity_passes(monkeypatch):
    """막는 것만 재면 게이트가 전부를 막아도 통과한다. 정상 경로를 함께 잰다."""
    client = _create_client(monkeypatch, identity_email="admin@example.com")
    res = client.post("/probe")
    assert res.status_code == 200
    assert res.get_json() == {"status": "ran"}


def test_options_preflight_passes_without_identity(monkeypatch):
    """preflight 를 막으면 브라우저가 본 요청을 아예 보내지 않는다.

    before_request 가 OPTIONS 에서 일찍 반환해 g.user_email 을 세우지 않으므로
    (app/__init__.py:171), 예외가 없으면 관리자의 preflight 도 403 을 받는다. 그러면
    reanalyze-gemini 를 쓰는 화면이 통째로 멈춘다.
    """
    client = _create_client(monkeypatch, identity_email=None)
    res = client.open("/probe", method="OPTIONS")
    assert res.status_code == 200


def test_decorator_keeps_view_name(monkeypatch):
    """functools.wraps 가 없으면 두 번째 라우트 등록이 터진다.

    Flask 는 뷰 함수의 __name__ 을 엔드포인트 이름으로 삼는다. 감싼 함수의 이름이
    전부 같으면 두 번째 add_url_rule 에서
    AssertionError: View function mapping is overwriting an existing endpoint 가 난다.
    여섯 자리에 붙일 데코레이터이므로 이 성질이 필수다.
    """
    app = Flask(__name__)

    @require_admin
    def some_view():
        return "ok"

    assert some_view.__name__ == "some_view"

    # 실제로 두 라우트를 등록해 본다. 이름만 재면 wraps 를 흉내 낸 구현도 통과한다.
    @app.route("/a", methods=["POST"])
    @require_admin
    def view_a():
        return jsonify({"which": "a"})

    @app.route("/b", methods=["POST"])
    @require_admin
    def view_b():
        return jsonify({"which": "b"})

    assert {"view_a", "view_b"} <= set(app.view_functions)
```

- [ ] **Step 2: 검사가 실패하는 것을 확인한다**

Run: `./venv/bin/python -m pytest tests/app/test_route_guards.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.routes.route_guards'`

- [ ] **Step 3: 데코레이터를 만든다**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Route Guards

라우트에 붙이는 인가 게이트. 판정 자체는 services/admin_helpers.py 가 맡고 여기서는
Flask 의 요청 문맥에서 신원을 꺼내 넘기는 일만 한다.
"""

from __future__ import annotations

import functools
from typing import Any, Callable

from flask import g, jsonify, request

from services.admin_helpers import is_admin_email


def require_admin(view: Callable[..., Any]) -> Callable[..., Any]:
    """관리자 신원이 확정된 요청만 통과시킨다.

    판정 근거는 before_request 가 서명을 검증해 넣어 둔 g.user_email 이다. 브라우저가
    보낸 헤더를 그대로 믿지 않는다. 화면의 useAdmin 훅도 /api/admin/check 를 거쳐 같은
    is_admin_email 로 판정하므로, 버튼이 보이는 조건과 요청이 통과하는 조건이 같다.

    OPTIONS 를 통과시키는 이유가 있다. before_request 는 OPTIONS 에서 일찍 반환해
    g.user_email 을 세우지 않으므로(app/__init__.py:171), 여기서 막으면 preflight 가
    403 을 받아 브라우저가 본 요청을 아예 보내지 않는다. 관리자에게도 화면이 멈춘다.

    이 갈래가 실제로 도달하는 라우트는 하나뿐이다. methods 에 OPTIONS 를 두지 않으면
    Flask 가 자체 처리로 200 과 Allow 헤더를 돌려주면서 뷰 함수를 부르지 않기 때문이다.
    이 저장소에서 methods 에 OPTIONS 를 두는 것은 reanalyze-gemini 하나이고 그 본문이
    {"status": "ok"} 만 낸다. 그래서 통과시켜도 구멍이 나지 않는다.

    바꿔 말하면 조건이 하나 붙는다. methods 에 OPTIONS 를 두면서 부작용이 있는 핸들러를
    새로 만들면 이 전제가 깨진다. 그런 라우트를 추가한다면 이 갈래를 다시 봐야 한다.

    ponytail: 관리자 한 단계만 있다. 역할이 여러 개가 되면 그때 인자를 받는 형태로 바꾼다.
    """

    @functools.wraps(view)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        if request.method == "OPTIONS":
            return view(*args, **kwargs)
        if not is_admin_email(g.get("user_email")):
            return jsonify({"error": "Forbidden"}), 403
        return view(*args, **kwargs)

    return wrapped
```

`functools.wraps` 가 필수다. Flask 가 뷰 함수의 `__name__` 을 엔드포인트로 삼으므로,
없으면 두 번째 라우트를 등록할 때 `View function mapping is overwriting an existing
endpoint: wrapped` 로 터진다.

- [ ] **Step 4: 검사가 통과하는 것을 확인한다**

Run: `./venv/bin/python -m pytest tests/app/test_route_guards.py -q`
Expected: PASS, 5건

---

## Task 2: 부류 A 여섯에 게이트를 붙인다

**Files:**
- Modify: `app/routes/kr_market_jongga_execution_routes.py:98`, `:167`, `:194`
- Modify: `app/routes/kr_market_data_signals_routes.py:206`
- Modify: `app/routes/kr_market_system_http_routes.py:214`
- Modify: `app/routes/common_update_routes.py:124`
- Test: `tests/app/test_admin_gated_routes.py` (신규)

**Interfaces:**
- Consumes: `app.routes.route_guards.require_admin` (Task 1)
- Produces: 없음. 라우트의 외부 계약만 바뀐다(신원 없는 요청이 403).

- [ ] **Step 1: 실패하는 검사를 쓴다**

라우트를 실제로 등록해 게이트가 붙었는지 잰다. 등록 함수마다 의존성이 다르므로 최소한의
가짜를 넣는다.

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""부류 A 여섯 라우트에 인가 게이트가 붙어 있는지 잰다([INFRA-042]).

데코레이터 자체는 tests/app/test_route_guards.py 가 잰다. 여기서 재는 것은 「그것이
이 여섯 자리에 실제로 붙어 있는가」다. 둘을 한 파일에 두면 데코레이터를 지웠을 때
어느 쪽이 깨진 것인지 구분이 안 된다.

블루프린트를 url_prefix 없이 등록하므로 경로가 실제 앱(/api/kr/...)과 다르다. 의도한
것이다. 이 파일은 게이트만 재고 경로 배선은 재지 않는다. 그쪽은 각 라우트의 기존
refactor 검사가 맡는다.
"""

import os
import sys

import pytest
from flask import Blueprint, Flask

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)


def _build_app(register, monkeypatch, *, identity_email=None):
    app = Flask(__name__)
    app.testing = True
    bp = Blueprint("probe_bp", __name__)
    register(bp)

    @app.before_request
    def _seed_identity():
        from flask import g, request

        if request.method == "OPTIONS":
            return
        g.user_email = identity_email

    app.register_blueprint(bp)
    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")
    return app.test_client()
```

각 라우트마다 등록 함수를 부르는 케이스를 둔다. 실제 의존성은 「부르면 안 되는 것」이므로
**호출되면 `AssertionError` 를 내는 가짜**로 넣는다. 그러면 게이트가 없을 때 호출이 실제로
일어났다는 것을 검사가 직접 증명한다. 시그니처는 확인해 두었다.

```python
class _NullLogger:
    def error(self, *_a, **_k):
        pass

    def info(self, *_a, **_k):
        pass

    def warning(self, *_a, **_k):
        pass

    def debug(self, *_a, **_k):
        pass


def _must_not_run(*_args, **_kwargs):
    raise AssertionError("게이트를 지나 실행 경로에 도달했다")


def test_signals_run_refuses_anonymous(monkeypatch):
    from app.routes.kr_market_data_signals_routes import _register_vcp_run_route

    def register(bp):
        _register_vcp_run_route(
            bp,
            logger=_NullLogger(),
            vcp_status={},
            start_vcp_screener_run=_must_not_run,
            run_vcp_background=_must_not_run,
        )

    client = _build_app(register, monkeypatch, identity_email=None)
    res = client.post("/signals/run", json={})
    assert res.status_code == 403
    assert res.get_json() == {"error": "Forbidden"}


def test_signals_run_passes_for_admin(monkeypatch):
    """막는 것만 재면 게이트가 전부를 막아도 통과한다."""
    from app.routes.kr_market_data_signals_routes import _register_vcp_run_route

    def register(bp):
        _register_vcp_run_route(
            bp,
            logger=_NullLogger(),
            vcp_status={},
            start_vcp_screener_run=lambda **_k: (200, {"status": "started"}),
            run_vcp_background=lambda *_a: None,
        )

    client = _build_app(register, monkeypatch, identity_email="admin@example.com")
    res = client.post("/signals/run", json={})
    assert res.status_code == 200


def test_init_data_refuses_anonymous(monkeypatch):
    from app.routes.kr_market_system_http_routes import _register_init_data_route

    def register(bp):
        _register_init_data_route(
            bp,
            logger=_NullLogger(),
            deps={"launch_init_data_update": _must_not_run},
        )

    client = _build_app(register, monkeypatch, identity_email=None)
    res = client.post("/init-data", json={"type": "all"})
    assert res.status_code == 403
```

`jongga-v2` 셋은 등록 함수가 의존성 열한 개를 요구하므로
`tests/app/test_kr_market_jongga_execution_routes_refactor.py:25` 의 `_build_deps` 와 같은
모양을 쓴다. 그 파일에서 가져다 쓰지 말고 이 파일에 필요한 만큼만 적는다. 그쪽은 위임을
재느라 성공하는 가짜를 넣지만 여기서는 **불리면 실패하는 가짜**를 넣어야 하므로 목적이
반대다.

```python
def test_jongga_message_refuses_anonymous_even_with_force(monkeypatch, tmp_path):
    """{"force": true} 로도 우회되지 않는다.

    force 는 claim_jongga_notification_send 중복 가드를 건너뛰는 값이라
    (kr_market_jongga_execution_routes.py:216) 게이트가 없으면 횟수 제한 없이 실제
    종가베팅 시그널 메시지가 나간다. 게이트는 그보다 앞에 있어야 한다.

    build_screener_result_for_message 를 실패하는 가짜로 두었다. 게이트가 없으면 그
    함수가 불려 AssertionError 가 나므로, 이 검사는 「403 이 나왔다」와 「발송 준비에
    닿지 않았다」를 함께 잰다.
    """
    from app.routes.kr_market_jongga_execution_routes import (
        register_jongga_execution_routes,
    )

    def register(bp):
        register_jongga_execution_routes(
            bp,
            # tmp_path 를 쓴다. 403 경로는 파일에 닿지 않지만, 나중에 「관리자는 통과한다」
            # 갈래를 보태면 그 경로가 v2_screener_status.json 을 실제로 쓴다. 고정 경로를
            # 두면 그때 /tmp 에 파일이 남는다. 이웃 검사도 전부 tmp_path 를 쓴다.
            data_dir=str(tmp_path),
            logger=_NullLogger(),
            load_json_file=_must_not_run,
            launch_jongga_v2_screener=_must_not_run,
            run_jongga_v2_background_pipeline=_must_not_run,
            execute_single_stock_analysis=_must_not_run,
            execute_jongga_gemini_reanalysis=_must_not_run,
            resolve_jongga_message_filename=_must_not_run,
            build_screener_result_for_message=_must_not_run,
            select_signals_for_reanalysis=_must_not_run,
            build_jongga_news_analysis_items=_must_not_run,
            apply_gemini_reanalysis_results=_must_not_run,
        )

    client = _build_app(register, monkeypatch, identity_email=None)
    res = client.post(
        "/jongga-v2/message", json={"target_date": "2026-02-22", "force": True}
    )
    assert res.status_code == 403
```

**등록 시점에는 이 가짜들이 불리지 않는다.** `_build_v2_status_io`
(`kr_market_jongga_execution_routes.py:27-62`)와 `_build_jongga_background_runner`(`:65`)가
클로저만 만들고 어떤 의존성도 호출하지 않기 때문이다(계획 검토에서 확인). 이 성질이
깨지면 검사가 등록 단계에서 터지므로 그때는 필요한 것만 통과하는 가짜로 바꾼다.

`system/start-update` 는 `register_common_update_routes(common_bp, ctx)` 가
`CommonRouteContext` dataclass(`app/routes/common_route_context.py:17-26`)를 받는다. 필드
열 개를 전부 채운다.

**`load_update_status` 는 통과시키고 `start_update` 와 `run_background_update` 만 실패하는
가짜로 둔다.** `api_start_update`(`common_update_routes.py:125-147`)가
`ctx.load_update_status` 를 먼저 부르고 `:136` 에서 `isRunning` 을 본 뒤에야 스레드 기동에
닿기 때문이다. `load_update_status` 까지 실패 가짜로 두면 게이트가 없을 때 첫 호출에서
터져 「403 이 났다」는 재지만 **「스레드가 뜨지 않았다」는 증명하지 못한다.** 무엇을 재는
검사인지 흐려진다.

```python
def test_start_update_refuses_anonymous(monkeypatch):
    from app.routes.common_route_context import CommonRouteContext
    from app.routes.common_update_routes import register_common_update_routes

    ctx = CommonRouteContext(
        logger=_NullLogger(),
        update_lock=threading.Lock(),
        update_status_file="/dev/null",
        # 게이트가 없을 때 여기까지는 와야 아래 두 가짜가 의미를 갖는다.
        load_update_status=lambda **_k: {"isRunning": False},
        start_update=_must_not_run,
        update_item_status=_must_not_run,
        stop_update=_must_not_run,
        finish_update=_must_not_run,
        run_background_update=_must_not_run,
        paper_trading=None,
    )

    client = _build_app(
        lambda bp: register_common_update_routes(bp, ctx),
        monkeypatch,
        identity_email=None,
    )
    res = client.post("/system/start-update", json={"items": ["AI Jongga V2"]})
    assert res.status_code == 403
```

`load_update_status` 가 `**_k` 를 받는 이유는 라우트가 `deep_copy=False` 로 부르고
`TypeError` 를 잡아 인자 없이 다시 부르기 때문이다(`common_update_routes.py:130-133`).

**하지 말 것:** `app.view_functions` 에서 뷰를 꺼내 `__wrapped__` 속성이 있는지 보는 방식은
쓰지 않는다. 데코레이터가 붙었다는 사실만 재고 **거부가 실제로 일어나는지는 재지 못하며**,
`functools.wraps` 를 쓰는 다른 데코레이터에도 똑같이 반응한다.

- [ ] **Step 2: 검사가 실패하는 것을 확인한다**

Run: `./venv/bin/python -m pytest tests/app/test_admin_gated_routes.py -q`
Expected: FAIL — 신원 없는 요청이 200 을 받거나, 발송 가짜가 불려 AssertionError 가 난다

- [ ] **Step 3: 여섯 자리에 데코레이터를 붙인다**

각 파일 상단에 `from app.routes.route_guards import require_admin` 을 더하고, 라우트
데코레이터 **아래**에 붙인다.

```python
    @kr_bp.route("/jongga-v2/run", methods=["POST"])
    @require_admin
    def run_jongga_v2_screener_route():
```

순서가 중요하다. `@kr_bp.route` 가 위에 있어야 Flask 가 감싼 함수를 등록한다. 뒤집으면
게이트를 지나지 않는 원본이 등록된다.

여섯 자리:

| 파일 | 뷰 함수 |
|---|---|
| `kr_market_jongga_execution_routes.py` | `run_jongga_v2_screener_route`, `reanalyze_gemini_all_route`, `send_jongga_v2_message_route` |
| `kr_market_data_signals_routes.py` | `run_vcp_signals_screener` |
| `kr_market_system_http_routes.py` | `init_data_endpoint` |
| `common_update_routes.py` | `api_start_update` |

- [ ] **Step 4: 검사가 통과하는 것을 확인한다**

Run: `./venv/bin/python -m pytest tests/app/test_admin_gated_routes.py -q`
Expected: PASS

- [ ] **Step 5: 깨지는 기존 검사 한 파일을 고친다**

사전 실측 8 에 따라 깨지는 것은 `tests/app/test_kr_market_jongga_execution_routes_refactor.py`
하나다. 그 파일의 `_create_client`(`:42`)가 `before_request` 를 세우지 않아 `g.user_email`
이 없으므로 대상 라우트를 부르는 검사가 전부 403 을 받는다.

`app.register_blueprint` 바로 앞에 아래를 더한다. 열두 검사를 각각 고치지 않고 이 한
자리에서 끝난다.

```python
    @app.before_request
    def _seed_admin_identity():
        # [INFRA-042] 가 이 라우트들에 require_admin 을 붙였다. 이 파일이 재는 것은
        # 게이트가 아니라 그 뒤의 위임 동작이므로, 관리자 신원을 세워 두고 그대로 잰다.
        # 게이트 자체는 tests/app/test_admin_gated_routes.py 가 잰다.
        from flask import g, request

        if request.method == "OPTIONS":
            return
        g.user_email = "admin@example.com"
```

그리고 이 파일 안에서 `ADMIN_EMAILS` 가 그 값을 담도록 해야 한다. `monkeypatch` 를 쓰는
검사가 아니므로 모듈 수준 `autouse` 픽스처가 맞다.

```python
@pytest.fixture(autouse=True)
def _admin_env(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")
```

`:211` 의 OPTIONS 검사는 **그대로 둔다.** 사전 실측 9 대로 그 검사가 게이트의 OPTIONS
예외를 지키는 회귀 보호다. `_seed_admin_identity` 가 OPTIONS 에서 일찍 반환하므로 그
경로는 여전히 신원 없이 게이트를 지난다.

- [ ] **Step 6: 전체 pytest 로 회귀를 본다**

Run: `./venv/bin/python -m pytest -q`
Expected: PASS. 다른 파일이 깨지면 그 검사에도 같은 방식으로 신원을 세운다. **기대값을
403 으로 바꿔 통과시키지 않는다.** 그 검사가 재던 동작이 사라지기 때문이다.

---

## Task 3: 두 언어 판정 일치 검사

**Files:**
- Create: `tests/fixtures/admin_email_cases.json`
- Create: `tests/services/test_admin_helpers.py`
- Modify: `frontend/src/lib/adminEmails.test.ts`

**Interfaces:**
- Consumes: `services.admin_helpers.is_admin_email`, `frontend/src/lib/adminEmails.isAdminEmail`
- Produces: 없음. 검사만 는다.

- [ ] **Step 1: 공유 케이스 목록을 만든다**

```json
{
  "_comment": "두 언어의 관리자 판정이 같은 답을 내는지 재는 공유 입력이다. services/admin_helpers.py 의 is_admin_email 과 frontend/src/lib/adminEmails.ts 의 isAdminEmail 이 이 목록을 함께 읽는다. 한쪽 규칙만 고치면 반대쪽 검사가 실패한다. 케이스를 더할 때는 양쪽 구현이 실제로 그렇게 동작하는지 먼저 확인한다.",
  "_ceiling": "이 목록은 ASCII 공백만 다룬다. 파이썬 str.strip() 과 자바스크립트 trim() 은 공백으로 보는 문자 집합이 달라서, U+001C 와 U+0085 는 파이썬만 제거하고 U+FEFF(BOM) 는 자바스크립트만 제거한다(양쪽 런타임에서 실측). 그런 입력은 두 구현이 서로 다른 답을 내므로 기대값을 하나만 적을 수 없고, 이 파일로는 표현할 수 없다. 갈림이 실제로 문제가 되면 양쪽에서 ASCII 공백만 잘라 내도록 맞춘 뒤 케이스를 더한다.",
  "cases": [
    {"why": "정확히 일치", "list": "admin@example.com", "email": "admin@example.com", "expected": true},
    {"why": "대문자를 소문자로 맞춘다", "list": "admin@example.com", "email": "ADMIN@Example.com", "expected": true},
    {"why": "목록 쪽 대문자도 맞춘다", "list": "Admin@Example.com", "email": "admin@example.com", "expected": true},
    {"why": "앞뒤 공백을 없앤다", "list": " admin@example.com , other@example.com ", "email": "  admin@example.com  ", "expected": true},
    {"why": "목록에 없으면 거부", "list": "admin@example.com", "email": "guest@example.com", "expected": false},
    {"why": "빈 이메일은 거부", "list": "admin@example.com", "email": "", "expected": false},
    {"why": "공백뿐인 이메일은 거부", "list": "admin@example.com", "email": "   ", "expected": false},
    {"why": "기본 프로필 이메일은 목록에 있어도 거부", "list": "user@example.com", "email": "user@example.com", "expected": false},
    {"why": "목록이 비면 아무도 통과 못 한다", "list": "", "email": "admin@example.com", "expected": false},
    {"why": "쉼표뿐인 목록도 빈 목록이다", "list": " , , ", "email": "admin@example.com", "expected": false},
    {"why": "부분 일치는 통과가 아니다 (접두사 비교를 막는다)", "list": "admin@example.com", "email": "admin@example.com.evil.test", "expected": false},
    {"why": "목록의 다른 항목에 붙어도 통과가 아니다 (원본 문자열 비교를 막는다)", "list": "admin@example.com,b@example.com", "email": "example.com", "expected": false},
    {"why": "줄바꿈은 구분자가 아니다", "list": "admin@example.com\nother@example.com", "email": "admin@example.com", "expected": false}
  ]
}
```

**마지막 세 케이스가 각각 다른 오구현을 겨냥한다.** 하나만 남기면 나머지가 통과한다.

- 「부분 일치」는 `normalized.startswith(entry)` 같은 **접두사 비교**를 죽인다. 공격자가
  가진 도메인의 주소로 관리자가 되는 형태다. 원본 문자열 비교 오구현은 이 케이스를 그냥
  지나간다. `"admin@example.com"` 안에 `"admin@example.com.evil.test"` 가 없기 때문이다.
- 「다른 항목에 붙어도」는 `rawList.includes(email)` 같은 **쪼개지 않은 원본 문자열 비교**를
  죽인다. `"example.com"` 이 `"admin@example.com,b@example.com"` 의 부분 문자열이라
  통과해 버린다. 앞 케이스는 이것을 잡지 못한다.
- 「줄바꿈은 구분자가 아니다」는 한쪽만 `split(/[,\n]/)` 로 「친절하게」 고치는 변경을
  잡는다. 실제로 일어날 법한 종류다. 동시에 **운영자가 쉼표 대신 줄바꿈으로 목록을 적으면
  관리자가 조용히 0명이 된다**는 사실을 문서로 남긴다. 양쪽 다 `false` 인 것을 확인했다.

`null`/`undefined` 케이스는 이 목록에 넣지 않는다. JSON 의 `null` 이 파이썬에서는 `None`,
타입스크립트에서는 `null` 이 되지만 `undefined` 는 JSON 으로 표현할 수 없어 한쪽만
반쪽으로 재게 된다. 그 케이스는 각 언어의 기존 검사가 이미 따로 갖고 있다.

- [ ] **Step 2: 파이썬 쪽 검사를 쓴다**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""관리자 판정이 타입스크립트 쪽과 같은 답을 내는지 잰다([INFRA-042]).

같은 규칙이 services/admin_helpers.py 와 frontend/src/lib/adminEmails.ts 에 두 벌 있다.
한쪽만 고치면 같은 사용자가 한 게이트는 통과하고 다른 게이트는 막힌다. 두 검사가 같은
JSON 을 읽으므로 어느 쪽을 고쳐도 반대쪽이 실패한다.
"""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from services.admin_helpers import is_admin_email

CASES_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "admin_email_cases.json"
CASES = json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", CASES, ids=[c["why"] for c in CASES])
def test_shared_admin_email_cases(case, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", case["list"])
    # `is` 가 아니라 `==` 를 쓴다. 지금 구현은 `in` 의 결과를 그대로 돌려주어 진짜 bool
    # 이지만, 나중에 truthy 한 비 bool 을 돌려주게 바뀌면 구현이 옳아도 `is` 가 실패한다.
    assert is_admin_email(case["email"]) == case["expected"], case["why"]


def test_case_file_is_not_empty():
    """목록이 비면 위 검사가 0건으로 통과한다. 그 상태를 통과로 보지 않는다."""
    assert len(CASES) >= 10
```

- [ ] **Step 3: 파이썬 검사를 돌린다**

Run: `./venv/bin/python -m pytest tests/services/test_admin_helpers.py -q`
Expected: PASS, 14건(케이스 13 + 목록 크기 검사 1). 사전 실측 10 에서 앞의 12개를, 계획
검토 뒤에 「줄바꿈」 케이스를 각각 양쪽 구현으로 돌려 전부 일치하는 것을 미리 확인했으므로
실패하면 케이스를 옮겨 적다가 틀린 것이다. **구현을 케이스에 맞추지 말고 옮겨 적은 값을
고친다.**

- [ ] **Step 4: 타입스크립트 쪽 검사를 더한다**

`frontend/src/lib/adminEmails.test.ts` 의 기존 `describe` 는 그대로 두고 아래를 더한다.
기존 검사는 `undefined` 처럼 JSON 이 표현하지 못하는 입력을 재고 있어 대체하지 않는다.

```typescript
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

// 파이썬 검사와 같은 파일을 읽는다. 한쪽 규칙만 고치면 반대쪽이 실패한다.
const CASES: Array<{ why: string; list: string; email: string; expected: boolean }> =
  JSON.parse(
    readFileSync(
      resolve(__dirname, '../../../tests/fixtures/admin_email_cases.json'),
      'utf-8'
    )
  ).cases;

describe('isAdminEmail — 파이썬 구현과 공유하는 케이스', () => {
  it('케이스 파일이 비어 있지 않다', () => {
    expect(CASES.length).toBeGreaterThanOrEqual(10);
  });

  it.each(CASES)('$why', ({ list, email, expected }) => {
    expect(isAdminEmail(email, list)).toBe(expected);
  });
});
```

**구현자 주의:** 상대 경로를 확인한다. `frontend/src/lib/` 에서 저장소 루트의 `tests/` 로
가려면 `../../../` 다. vitest 설정의 `root` 가 `frontend/` 인지 먼저 보고 맞춘다. 경로가
틀리면 이 파일 전체가 로드 단계에서 터진다.

- [ ] **Step 5: vitest 를 돌린다**

Run: `cd frontend && npx vitest run src/lib/adminEmails.test.ts`
Expected: PASS

---

## Task 4: `ADMIN_API_TOKEN` 회전 절차 문서화

**Files:**
- Modify: `CLAUDE.md` (기존 `ADMIN_API_TOKEN` 절)

**Interfaces:** 없음. 문서만 바뀐다.

- [ ] **Step 1: 기존 절을 읽는다**

`CLAUDE.md` 의 `ADMIN_API_TOKEN` 절은 지금 「무엇인가」와 「비면 403 이다」만 적고 있다.
폐기 특성과 회전 절차가 없다.

- [ ] **Step 2: 아래를 그 절 끝에 더한다**

```markdown
**이 토큰은 만료도 폐기 목록도 없는 순수 소지 비밀입니다.** `ADMIN_EMAILS` 에서 어떤
관리자를 지워도 토큰 값을 아는 사람은 loopback 으로 Flask 에 직접 요청해 그대로
통과합니다. 반면 브라우저에서 오는 신원은 `frontend/src/lib/identity.ts:10` 의
`IDENTITY_TTL_SECONDS` 가 120 초라 서명이 곧 만료되고 `ADMIN_EMAILS` 에서 지운 효과가
그 안에 반영됩니다. **두 게이트의 폐기 특성이 이렇게 다릅니다.** 관리자를 내보낼 때는
`ADMIN_EMAILS` 에서 지우는 것만으로 끝나지 않고 이 토큰도 함께 돌려야 합니다.

회전 절차입니다. 순서를 지키지 않으면 관리자 화면이 그 사이 동안 막힙니다.

1. 새 값을 만듭니다. `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`
2. `.env` 와 `.env.production` **양쪽**의 `ADMIN_API_TOKEN` 을 새 값으로 바꿉니다.
   한쪽만 바꾸면 배포 환경에 따라 갈립니다.
3. **워커를 모두 재기동합니다.** 설정 화면으로 바꾸면 요청을 처리한 워커의
   `os.environ` 만 바뀌므로 나머지 워커는 옛 값을 계속 씁니다.
4. Next 쪽도 재기동합니다. 핸들러는 `process.env` 를 호출할 때마다 읽지만
   (`frontend/src/app/api/system/env/route.ts:31`), 그 `process.env` 를 `.env` 에서
   채우는 것은 기동 시점 한 번뿐입니다. `next dev` 는 `.env` 변경을 감지해 다시 읽지만
   `next start` 는 그러지 않습니다.
5. 관리자 화면의 설정 모달을 열어 값이 읽히는지 확인합니다. 403 이 나면 3번이나 4번이
   덜 끝난 것입니다.
```

- [ ] **Step 3: 사실을 확인한다**

계획 작성 중에 이미 확인했다. `IDENTITY_TTL_SECONDS` 는 **환경 변수가 아니라**
`frontend/src/lib/identity.ts:10` 의 상수이며 값이 `120` 이다(`identity.test.ts:45` 가
그 값을 고정한다). `.env.production` 에 `ADMIN_API_TOKEN` 키가 있는 것도 확인했다(값은
읽지 않았다). 구현 시 이 둘이 그대로인지 다시 보고, 다르면 문구를 고친다. **문서에 없는
동작을 적지 않는다.**

---

## Task 5: 정적 검증과 첫 커밋

- [ ] **Step 1: 전체 검사를 돌린다**

```bash
./venv/bin/python -m pytest -q
cd frontend && npx vitest run && npm run type-check
```

기대: pytest 종료 코드 0, vitest 통과, `tsc` 오류 없음. vitest 는 `[FE-042]` 로 분리해 둔
간헐 실패가 있으므로 실패하면 그 항목의 것인지 먼저 대조한다.

- [ ] **Step 2: 시크릿 확인 세 가지 (`tier-rules.md` §1)**

```bash
git ls-files | grep -E '^\.env' || echo "추적되는 .env 없음 (.env.example 만 예외)"
grep -rn "NEXT_PUBLIC_" frontend/src frontend/next.config.* 2>/dev/null | head
```

기대: 추적되는 `.env` 는 `.env.example` 뿐이고, `NEXT_PUBLIC_` 목록에 관리자 토큰이나
`ADMIN_EMAILS` 가 없다. 게이트 응답 본문에 값이 실리지 않는 것도 함께 본다.

- [ ] **Step 3: 티어를 재판정한다**

Run: `git diff --stat`
`tier-rules.md` §3-6 에 따라 상위 티어면 올리고 낮게 나와도 내리지 않는다. 이 항목은
T3 으로 시작했으므로 유지한다.

- [ ] **Step 4: QA 시나리오 문서를 먼저 만든다**

`docs/dev-cycle/qa/INFRA-042.md` 를 이 커밋에 넣어야 하므로 스테이징 전에 만든다.
dev-cycle `[3]` 검증 4번이 정하는 순서이며, 첫 커밋은 「구현 + 계획 + QA 행렬」을 함께
담는다. 내용은 QA 단계에서 채우되 시나리오 목록은 여기서 확정한다.

- [ ] **Step 5: 허용 경로만 스테이징하고 검사한다**

```bash
git add app/routes/route_guards.py \
        app/routes/kr_market_jongga_execution_routes.py \
        app/routes/kr_market_data_signals_routes.py \
        app/routes/kr_market_system_http_routes.py \
        app/routes/common_update_routes.py \
        tests/app/test_route_guards.py tests/app/test_admin_gated_routes.py \
        tests/app/test_kr_market_jongga_execution_routes_refactor.py \
        tests/services/test_admin_helpers.py tests/fixtures/admin_email_cases.json \
        frontend/src/lib/adminEmails.test.ts \
        CLAUDE.md docs/dev-cycle/TODO.md docs/dev-cycle/qa/INFRA-042.md \
        docs/superpowers/plans/2026-09-08-infra-042-admin-route-guard.md
echo "add exit=$?"
# 인덱스가 실제로 채워졌는지 본다. 아래 세 줄을 건너뛰지 않는다.
git diff --cached --name-only | tee /dev/stderr | wc -l
git diff --cached --check; echo "check exit=$?"
git status --short
```

기대: 스테이징된 파일이 13개, `check exit=0`, 그리고 `?? package.json` 만 스테이징 밖에
남는다.

**`add exit=$?` 와 `check exit=0` 만 보고 통과로 판정하지 않는다.** `git add` 는 목록에
없는 경로가 하나라도 섞이면 `fatal: pathspec ... did not match any files` 를 내면서
**아무것도 스테이징하지 않는데, 종료 코드는 0 이다.** 그 상태에서
`git diff --cached --check` 는 빈 인덱스를 보고 `exit=0` 을 돌려주므로 두 신호가 모두
통과로 보이고 빈 커밋이 만들어진다. 실측으로 재현했다. 그래서 `--name-only` 의 줄 수를
함께 세고, `fatal` 이 한 줄이라도 보이면 그 경로를 만들거나 목록에서 빼고 다시 한다.

- [ ] **Step 6: 첫 커밋을 남긴다**

TODO 항목은 이 커밋에서 지우지 않는다. QA 가 실패하면 재개할 자리가 사라진다.

```
fix(infra): [INFRA-042] 관리자 전용 라우트 여섯이 서버에서 열려 있던 것을 닫는다

화면은 useAdmin 으로 이 버튼들을 관리자에게만 보였지만 서버에는 검사가 없었다.
curl 한 줄이면 지나간다.

가장 무거운 것은 /api/kr/jongga-v2/message 다. 본문에 {"force": true} 를 넣으면
중복 가드까지 건너뛰고 실제 종가베팅 시그널 메시지를 횟수 제한 없이 발송한다.
구독자는 정상 발송과 구분하지 못한다.

require_admin 데코레이터를 두고 여섯 자리에 붙였다. 판정은 before_request 가 서명을
검증해 넣어 둔 g.user_email 을 is_admin_email 로 보는 것이며, 화면의 useAdmin 이
/api/admin/check 를 거쳐 쓰는 것과 같은 함수다.

OPTIONS 는 통과시킨다. before_request 가 OPTIONS 에서 일찍 반환해 g.user_email 을
세우지 않으므로, 막으면 preflight 가 403 을 받아 브라우저가 본 요청을 아예 보내지
않는다. 관리자에게도 화면이 멈춘다.

관리자 판정이 파이썬과 타입스크립트에 두 벌 있어 한쪽만 고치면 같은 사용자가 한
게이트는 통과하고 다른 게이트는 막혔다. 두 검사가 같은 JSON 케이스를 읽게 했다.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AeQQtEk7wbuVAnf9kCJmBN
```

---

## 범위에서 뺀 것

마감에서 TODO 에 새 항목으로 올린다.

1. **부류 B 셋** — `kr/refresh`, `market-gate/update`, `config/interval`(POST). 화면이
   일반 사용자에게 그 버튼을 보이므로 게이트를 세우면 403 이 난다. 관리자 전용으로 바꿀
   것인지가 제품 정책 결정이고, `dashboard/kr/page.tsx` 에 `useAdmin` 을 들여 노출 조건과
   오류 처리를 함께 고쳐야 한다.
2. **부류 C 넷** — 모의투자. 관리자 게이트가 답이 아니다. `reset_account()` 와
   `buy_stock()` 에 사용자 인자가 없어 계정이 전역 하나이므로, 실제 문제는 아무나 남의
   포트폴리오를 초기화할 수 있다는 것이고 해법은 소유자 분리다. `services/paper_trading.py`
   와 그 계열 아홉 파일이 `tier-rules.md` §2 의 위험 경로다.
3. **부류 D — `POST /api/kr/reanalyze/gemini`** (`kr_market_system_http_routes.py:129`).
   처음 분류할 때 빠뜨렸다가 계획 검토가 셈이 맞지 않는 것을 짚어 드러났다. 이름이
   `jongga-v2/reanalyze-gemini` 와 비슷하지만 **다른 라우트이고 이미 닫혀 있다.**
   `:142` 가 `g.get('user_email')` 을 읽어 넘기고
   `services/kr_market_route_service.py:153-159` 가 신원이 없으면 401 을 낸다.
   `app/__init__.py:175` 가 `g.user_api_key = None` 으로 고정해 개인 키 갈래는 도달할 수
   없으므로 익명 요청은 예외 없이 401 이다. 화면 호출자도 없다. **손댈 것이 없다.**
   쿼터가 실제로 새지 않는지는 인가가 아니라 쿼터의 문제라 별도 항목으로 올린다.

4. **기존 게이트 두 자리의 데코레이터 전환** — `common_notification_routes.py:135` 와
   `common_update_routes.py:229`. 판정 사본을 줄일 수 있으나 이미 닫힌 자리라 회귀 위험만
   새로 생긴다. 설계 단계에서 선택지로 제시했고 채택되지 않았다.

5. **Forbidden 응답 형식의 통일** — 저장소에 `{"error": ...}` 와
   `{"status": "error", "message": ...}` 두 형식이 공존한다. 화면은 둘 다 처리하므로
   깨지는 것이 없고, 통일은 이 항목이 닫으려는 구멍과 무관하다.

---

## Self-Review

**1. 승인 범위 대비 빠짐**: TODO 의 체크박스 여섯 가운데 다섯을 이 계획이 덮는다.
①「권한 수준과 표준 결정」은 설계에서 끝났고 TODO 에 기록했다. ②「두 언어 일치 검사」→
Task 3. ③「회전 절차 문서화」→ Task 4. ④「데코레이터로 묶고 적용」→ Task 1·2.
⑤「`{"force": true}` 우회 검사」→ Task 2 Step 1. ⑥「발송 없이 확인할 QA 수단」은 QA
단계에서 정한다. 화면을 쓰지 않고 Flask 검사 클라이언트로 거부를 재는 것이 그 수단이며,
발송 가짜가 불리면 실패하는 구조라 실제 발송이 일어날 수 없다.

**2. 자리 표시자**: 없다. 처음에는 Task 2 Step 1 에 `...` 를 두고 「구현 시 시그니처를
확인하라」고 미뤘으나, 등록 함수 넷의 시그니처를 전부 읽어 실제 코드로 채웠다. 남은 것은
`start-update` 의 `CommonRouteContext` 필드 열 개인데, 그 dataclass 정의
(`app/routes/common_route_context.py:14`)를 계획에 인용해 두었으므로 옮겨 적기만 하면 된다.

**3. 이름 일관성**: `require_admin` 은 Task 1 이 정의하고 Task 2 가 쓴다. 공유 케이스
파일 경로 `tests/fixtures/admin_email_cases.json` 는 Task 3 의 세 단계가 같은 문자열을
쓴다. `is_admin_email` 과 `isAdminEmail` 은 기존 이름이며 바꾸지 않는다.

**4. 위험한 자리**: `functools.wraps` 누락과 데코레이터 순서 뒤집기 둘이 조용히 깨진다.
앞의 것은 Task 1 Step 1 의 마지막 검사가 두 라우트를 실제로 등록해 잡고, 뒤의 것은
Task 2 의 거부 검사가 잡는다. 세 번째는 기존 검사가 이 여섯을 신원 없이 부르는 경우인데,
Task 2 Step 5 가 그것을 명시적으로 다루며 기대값을 403 으로 바꾸는 회피를 금지한다.
