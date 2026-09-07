# `[INFRA-025]` `/api/system/env` 관리자 게이트 구현 계획

> **For agentic workers:** 이 저장소는 `.claude/skills/dev-cycle/SKILL.md` 의 절차를 따릅니다.
> 계획의 단계는 그 절차의 `[2] 구현과 리뷰` 안에서 순서대로 수행하며, 단계마다 커밋하지 않고
> `[3] 검증` 의 첫 커밋에서 한 번에 남깁니다. 체크박스는 진행 표시용입니다.

**목표:** 인증 없이 서버 `.env` 를 읽고 쓸 수 있는 `/api/system/env` 를, 검증 가능한 관리자
신원을 거친 요청만 통과하도록 닫는다. 같은 요청이 흘리던 `ADMIN_EMAILS` 노출도 함께 막는다.

**접근:** 신뢰의 근거를 Flask 바깥에 둔다. Flask 는 NextAuth 세션을 알지 못하고 앞으로도
알 필요가 없으므로, Next.js 라우트 핸들러가 세션을 확인해 관리자를 판정하고 서버끼리만
공유하는 토큰을 붙여 Flask 로 넘긴다. Flask 는 그 토큰만 확인한다. 토큰은 서버 프로세스의
환경 변수로만 존재하므로 브라우저는 볼 수 없고, 헤더를 위조해도 값을 맞출 수 없다.
gunicorn 이 `0.0.0.0` 에 붙는 배포에서 Next 를 우회해 Flask 를 직접 부르는 경로도 같은
검사에 걸린다.

**기술 스택:** Flask 3, next-auth 4.24.13 (`getServerSession`), Next.js 16.3.4 App Router
라우트 핸들러, pytest, vitest

**설계 근거:** `docs/dev-cycle/TODO.md` 의 `[INFRA-025]` 항목과 2026-09-07 대화 설계.
사용자가 「Next 세션 게이트 + Flask 공유 비밀」과 「마스킹 구멍 동시 수정」을 승인했다.

## 전역 제약

- `ADMIN_API_TOKEN` 에 `NEXT_PUBLIC_` 접두사를 붙이지 않는다. 붙이면 브라우저 번들에
  들어가 토큰이 공개되고 이 설계 전체가 무너진다.
- 토큰이 설정되지 않은 상태는 「열림」이 아니라 「닫힘」이다. 비어 있을 때 통과시키면
  설정을 빠뜨린 배포가 곧 인증 없는 배포가 된다.
- 토큰 비교는 `hmac.compare_digest` 를 쓴다. `==` 는 앞자리부터 갈리는 시점이 응답 시간에
  남는다.
- `.env` 값을 이 계획의 어떤 산출물에도 적지 않는다. 키 이름과 존재 여부까지만 다룬다.
- `frontend/next.config.js.backup` 은 이 항목의 범위가 아니다. 건드리지 않는다.
- 구현 중 발견: `.gitignore` 의 `env/`·`ENV/` 가 루트 한정이 아니어서
  `frontend/src/app/api/system/env/` 를 통째로 무시하고 있었다. macOS 는
  `core.ignorecase` 가 true 라 `ENV/` 도 `env/` 에 걸린다. 그대로 두면 라우트 핸들러가
  커밋되지 않아 배포에서 빠지고, rewrite 로 Flask 에 직접 가서 관리자도 403 을 받는다.
  두 규칙을 `/env/`·`/ENV/` 로 좁혔다. 파이썬 가상환경을 가리는 본래 목적은 그대로다.
- 기존 테스트 관례를 따른다. `tests/app/test_*.py` 는 `Flask(__name__)` 에 블루프린트를
  붙여 `test_client()` 를 만든다. 새 프레임워크나 픽스처 계층을 도입하지 않는다.

---

## 파일 구조

| 파일 | 책임 |
|---|---|
| `services/admin_helpers.py` | 관리자 판정. 기존 이메일 판정 옆에 토큰 검증을 더한다 |
| `services/common_env_service.py` | `.env` 읽기·쓰기 대상 키를 한 곳에서 정한다 |
| `app/routes/common_update_routes.py` | 라우트에서 게이트를 적용하고 죽은 DELETE 를 걷어낸다 |
| `frontend/src/lib/adminEmails.ts` | 「누가 관리자인가」를 정하는 순수 함수 (신규) |
| `frontend/src/lib/adminEmails.test.ts` | 그 판정을 고정한다 (신규) |
| `frontend/src/app/api/system/env/route.ts` | 세션을 확인해 관리자만 Flask 로 중계한다 (신규) |
| `frontend/next.config.js` | 이 경로가 라우트 핸들러로 가도록 rewrite 에서 제외한다 |
| `frontend/src/app/components/SettingsModal.tsx` | 비관리자에게 `.env` 탭을 감추고 요청을 보내지 않는다 |
| `.env.example` | `ADMIN_API_TOKEN` 을 기록한다 |
| `tests/app/test_system_env_admin_gate.py` | 게이트 동작을 고정한다 (신규) |
| `tests/app/test_common_env_service.py` | 허용 목록과 마스킹을 고정한다 |
| `frontend/src/app/components/SettingsModal.admin-gate.test.tsx` | 비관리자 화면을 고정한다 (신규) |

---

### Task 1: Flask 가 공유 토큰을 검증한다

**Files:**
- Modify: `services/admin_helpers.py`
- Test: `tests/app/test_system_env_admin_gate.py` (신규)

**Interfaces:**
- Produces: `verify_admin_api_token(provided: str | None) -> bool`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`tests/app/test_system_env_admin_gate.py` 를 만든다.

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
/api/system/env 관리자 게이트 회귀 테스트
"""

import os
import sys

import pytest
from flask import Flask


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from app.routes import common
from services.admin_helpers import verify_admin_api_token


def _create_client():
    app = Flask(__name__)
    app.testing = True
    app.register_blueprint(common.common_bp, url_prefix="/api")
    return app.test_client()


def test_verify_admin_api_token_rejects_when_unset(monkeypatch):
    monkeypatch.delenv("ADMIN_API_TOKEN", raising=False)

    assert verify_admin_api_token("anything") is False
    assert verify_admin_api_token(None) is False


def test_verify_admin_api_token_matches_exact_value(monkeypatch):
    monkeypatch.setenv("ADMIN_API_TOKEN", "s3cret-token")

    assert verify_admin_api_token("s3cret-token") is True
    assert verify_admin_api_token(" s3cret-token ") is True
    assert verify_admin_api_token("s3cret-toke") is False
    assert verify_admin_api_token("") is False
    assert verify_admin_api_token(None) is False


def test_verify_admin_api_token_rejects_non_ascii_without_raising(monkeypatch):
    """비ASCII 헤더가 403 이 아니라 500 을 만들지 않는지 고정한다.

    hmac.compare_digest 는 str 인자에 비ASCII 문자가 있으면 TypeError 를 던진다.
    라우트가 그 예외를 그대로 흘리면 헤더에 한글 한 글자를 넣는 것만으로 500 과
    스택 트레이스가 나온다.
    """
    monkeypatch.setenv("ADMIN_API_TOKEN", "s3cret-token")

    assert verify_admin_api_token("토큰") is False
    assert verify_admin_api_token("s3cret-token\u00e9") is False
```

- [ ] **Step 2: 실패를 확인한다**

```
source venv/bin/activate && pytest tests/app/test_system_env_admin_gate.py -v
```

기대: `ImportError: cannot import name 'verify_admin_api_token'`

- [ ] **Step 3: 최소 구현을 넣는다**

`services/admin_helpers.py` 의 `import os` 아래에 `import hmac` 을 더하고 파일 끝에 붙인다.

```python
def get_admin_api_token() -> str:
    return os.environ.get("ADMIN_API_TOKEN", "").strip()


def verify_admin_api_token(provided: str | None) -> bool:
    """서버끼리만 아는 토큰을 상수 시간으로 대조한다.

    토큰이 비어 있으면 어떤 요청도 통과시키지 않는다. 비었을 때 열어 두면 설정을
    빠뜨린 배포가 그대로 인증 없는 배포가 된다.
    """
    expected = get_admin_api_token()
    if not expected or not provided:
        return False
    # 바이트로 비교한다. compare_digest 는 str 인자에 비ASCII 문자가 섞이면
    # TypeError 를 던지므로, 헤더에 한글 한 글자만 넣어도 403 대신 500 이 나간다.
    return hmac.compare_digest(
        provided.strip().encode("utf-8"), expected.encode("utf-8")
    )
```

- [ ] **Step 4: 통과를 확인한다**

```
source venv/bin/activate && pytest tests/app/test_system_env_admin_gate.py -v
```

기대: 3 passed

---

### Task 2: 라우트에 게이트를 걸고 죽은 DELETE 를 걷어낸다

**Files:**
- Modify: `app/routes/common_update_routes.py:19,220-264`
- Modify: `services/common_env_service.py:27-51,159-198`
- Modify: `tests/app/test_common_env_service.py:12,66-95`
- Test: `tests/app/test_system_env_admin_gate.py`

**Interfaces:**
- Consumes: `verify_admin_api_token` (Task 1)
- Produces: 헤더 이름 상수 `ADMIN_TOKEN_HEADER = "X-Admin-Token"`

DELETE 를 지우는 근거는 두 가지다. 화면은 `SettingsModal.tsx:129` 에서
`// [CRITICAL] Do NOT delete server-side .env file` 이라며 이미 호출을 주석 처리했고,
`reset_sensitive_env_and_user_data` 의 호출자를 grep 하면 이 라우트 하나뿐이다. 아무도
부르지 않는 경로가 `.env` 의 민감 값과 `data/` 의 사용자 자료를 지울 수 있는 상태로 열려
있다. 게이트를 씌우기보다 걷어내는 편이 짧고, 되살릴 일이 생기면 이력에서 꺼내면 된다.

게이트를 데코레이터가 아니라 함수로 두는 이유를 적어 둔다. TODO 항목 초안에는 「데코레이터
추가」라고 적혀 있었으나 적용 대상이 이 라우트 하나뿐이다. 호출자 하나에 데코레이터를 두면
`functools.wraps` 와 클로저가 얻는 것 없이 늘어난다. 두 번째 관리자 경로가 생기면 그때
이 함수를 감싸는 데코레이터로 올린다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`tests/app/test_system_env_admin_gate.py` 에 이어 붙인다.

```python
@pytest.mark.parametrize("method", ["get", "post"])
def test_manage_env_rejects_request_without_token(monkeypatch, method):
    monkeypatch.setenv("ADMIN_API_TOKEN", "s3cret-token")
    client = _create_client()

    response = getattr(client, method)("/api/system/env", json={})

    assert response.status_code == 403
    assert response.get_json() == {"error": "Forbidden"}


@pytest.mark.parametrize("method", ["get", "post"])
def test_manage_env_rejects_wrong_token(monkeypatch, method):
    monkeypatch.setenv("ADMIN_API_TOKEN", "s3cret-token")
    client = _create_client()

    response = getattr(client, method)(
        "/api/system/env", json={}, headers={"X-Admin-Token": "wrong"}
    )

    assert response.status_code == 403


def test_manage_env_rejects_every_request_when_token_unset(monkeypatch):
    monkeypatch.delenv("ADMIN_API_TOKEN", raising=False)
    client = _create_client()

    response = client.get("/api/system/env", headers={"X-Admin-Token": ""})

    assert response.status_code == 403


def test_manage_env_allows_get_with_valid_token(monkeypatch, tmp_path):
    monkeypatch.setenv("ADMIN_API_TOKEN", "s3cret-token")
    env_file = tmp_path / ".env"
    env_file.write_text("AI_PROVIDER=gemini\n", encoding="utf-8")
    monkeypatch.setattr(
        common_update_routes, "resolve_env_path", lambda: str(env_file)
    )
    client = _create_client()

    response = client.get("/api/system/env", headers={"X-Admin-Token": "s3cret-token"})

    assert response.status_code == 200
    assert response.get_json() == {"AI_PROVIDER": "gemini"}


def test_manage_env_no_longer_accepts_delete(monkeypatch):
    monkeypatch.setenv("ADMIN_API_TOKEN", "s3cret-token")
    client = _create_client()

    response = client.delete(
        "/api/system/env", headers={"X-Admin-Token": "s3cret-token"}
    )

    assert response.status_code == 405
```

파일 위쪽 import 에 `from app.routes import common_update_routes` 를 더한다.

- [ ] **Step 2: 실패를 확인한다**

```
source venv/bin/activate && pytest tests/app/test_system_env_admin_gate.py -v
```

기대: 게이트가 없으므로 403 을 기대한 네 건이 200 으로 실패하고, DELETE 검사는 200 으로 실패한다.

- [ ] **Step 3: 라우트를 고친다**

`app/routes/common_update_routes.py` 의 import 에서 `reset_sensitive_env_and_user_data`
와 `resolve_data_dir` 을 빼고, `services.admin_helpers` 에서 검증 함수를 가져온다.

```python
from services.admin_helpers import verify_admin_api_token
```

`_register_manage_env_route` 를 다음으로 바꾼다.

```python
ADMIN_TOKEN_HEADER = "X-Admin-Token"


def _reject_unless_admin():
    """관리자 토큰이 없으면 403 응답을, 있으면 None 을 돌려준다.

    이 토큰은 Next.js 라우트 핸들러가 NextAuth 세션을 확인한 뒤에만 붙인다.
    브라우저는 값을 알 수 없으므로 헤더를 지어내도 통과하지 못한다.
    """
    if verify_admin_api_token(request.headers.get(ADMIN_TOKEN_HEADER)):
        return None
    return jsonify({"error": "Forbidden"}), 403


def _register_manage_env_route(common_bp, ctx: CommonRouteContext) -> None:
    @common_bp.route("/system/env", methods=["GET", "POST"])
    def manage_env():
        """환경 변수 관리 (읽기 및 쓰기). 관리자 토큰이 있는 요청만 처리한다."""
        denied = _reject_unless_admin()
        if denied is not None:
            return denied

        if request.method == "GET":
            def _handle_get():
                return jsonify(read_masked_env_vars(resolve_env_path()))

            return _execute_update_route(
                handler=_handle_get,
                ctx=ctx,
                error_label="Error reading .env",
            )

        def _handle_post():
            data = request.get_json() or {}
            if not data:
                return jsonify({"status": "ok"})
            update_env_file(resolve_env_path(), data, os.environ)
            return jsonify({"status": "ok"})

        return _execute_update_route(
            handler=_handle_post,
            ctx=ctx,
            error_label="Error updating .env",
        )
```

- [ ] **Step 4: 죽은 초기화 코드를 지운다**

`services/common_env_service.py` 에서 `FACTORY_RESET_SENSITIVE_KEYS`,
`FACTORY_RESET_DELETE_FILES`, `reset_sensitive_env_and_user_data`, 그리고 그 함수만 쓰는
`resolve_data_dir` 을 지운다. `resolve_data_dir` 의 다른 호출자가 없는지 지우기 전에
`grep -rn "resolve_data_dir" --include='*.py' .` 로 확인하고, 있으면 그 함수는 남긴다.

`tests/app/test_common_env_service.py` 에서 `reset_sensitive_env_and_user_data` import 와
`test_reset_sensitive_env_and_user_data_clears_and_deletes` 를 지운다. 지운 검사가 무엇을
검사했는지는 아카이브에 적는다.

- [ ] **Step 5: 통과를 확인한다**

```
source venv/bin/activate && pytest tests/app/test_system_env_admin_gate.py tests/app/test_common_env_service.py tests/app/test_common_routes_refactor.py -v
```

기대: 전부 통과. `manage_env` 를 부르는 다른 테스트가 403 으로 깨지면 그 테스트에도
`X-Admin-Token` 헤더와 `monkeypatch.setenv` 를 더한다.

---

### Task 3: 응답과 저장 대상을 화면이 쓰는 키로 제한한다

**Files:**
- Modify: `services/common_env_service.py:15-25,69-94,97-155`
- Test: `tests/app/test_common_env_service.py`

**Interfaces:**
- Produces: `EDITABLE_ENV_KEYS: frozenset[str]`, `PLAIN_ENV_KEYS: frozenset[str]`

현재 `_mask_env_value` 는 키 이름에 `KEY`·`SECRET`·`TOKEN` 같은 단어가 있을 때만 가린다.
그래서 현재 `.env` 의 55개 변수 가운데 37개가 값 그대로 나가고, 그 안에 `ADMIN_EMAILS` 와
`GOOGLE_APPLICATION_CREDENTIALS` 가 있다. 관리자 이메일이 새면 `/api/admin/check` 가
이메일 문자열만으로 판정하므로 화면의 관리자 UI 가 그대로 열리고, `X-User-Email` 헤더가
검증 없이 신원이 되므로(`[INFRA-027]`) 쿼터도 함께 뚫린다.

마스킹 규칙을 정교하게 다듬는 대신 응답에 담을 키를 제한한다. `SettingsModal.tsx` 가
읽는 키는 12개뿐이고, 나머지 43개는 화면이 쓰지 않으므로 보낼 이유가 없다. 규칙 하나가
줄고 노출면은 43개만큼 줄어든다.

같은 목록으로 쓰기도 막는다. 게이트를 통과한 관리자라도 `ADMIN_EMAILS` 나
`ADMIN_API_TOKEN` 을 화면에서 덮어쓸 수 있으면 자기 자신을 잠글 수 있다.

**화면 회귀 위험이 없는 근거.** 판정을 뒤집어도 화면이 읽는 12개 키의 결과는 하나도
바뀌지 않는다. `AI_PROVIDER` 와 `SMTP_PORT` 는 현재 `SENSITIVE_KEYWORDS` 의 어느 단어에도
걸리지 않아 평문으로 나가고 있으며 새 방식에서도 `PLAIN_ENV_KEYS` 로 평문이다. 나머지
10개는 `KEY`·`TOKEN`·`PASSWORD`·`USER`·`ID`·`URL`·`HOST`·`RECIPIENTS` 가운데 하나에
반드시 걸려 지금도 마스킹되고 있으며 새 방식에서도 마스킹된다. 그래서
`settingsEnv.ts:15` 의 `stored.includes('*')` 분기와 `common_env_service.py:131` 의
「`*` 가 섞이면 기존 값 유지」 규칙이 지금과 똑같이 동작한다.

**허용 목록의 두 키는 현재 `.env` 에 값이 없다.** `AI_PROVIDER` 와
`GOOGLE_SEARCH_ENGINE_ID` 가 그렇다. `read_masked_env_vars` 는 값이 빈 줄을 건너뛰므로
지금도 응답에 담기지 않으며, 화면은 `envVars['AI_PROVIDER'] || 'gemini'` 로 기본값을
쓴다. 기존 동작 그대로다. 값이 생겼을 때를 위해 두 키를 목록에 남긴다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`tests/app/test_common_env_service.py` 에 더한다.

```python
def test_read_masked_env_vars_returns_only_editable_keys(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "ADMIN_EMAILS=admin@example.com\n"
        "GOOGLE_APPLICATION_CREDENTIALS=/srv/key.json\n"
        "AI_PROVIDER=gemini\n"
        "SMTP_PORT=587\n"
        "TELEGRAM_BOT_TOKEN=bot123456:ABCDEFGH\n",
        encoding="utf-8",
    )

    result = read_masked_env_vars(str(env_file))

    assert "ADMIN_EMAILS" not in result
    assert "GOOGLE_APPLICATION_CREDENTIALS" not in result
    assert result["AI_PROVIDER"] == "gemini"
    assert result["SMTP_PORT"] == "587"
    assert result["TELEGRAM_BOT_TOKEN"].startswith("bot1")
    assert "*" in result["TELEGRAM_BOT_TOKEN"]


def test_update_env_file_ignores_keys_outside_allowlist(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "ADMIN_EMAILS=admin@example.com\nAI_PROVIDER=gemini\n", encoding="utf-8"
    )
    environ: dict[str, str] = {}

    update_env_file(
        str(env_file),
        {"ADMIN_EMAILS": "attacker@example.com", "AI_PROVIDER": "openai"},
        environ,
    )

    written = env_file.read_text(encoding="utf-8")
    assert "ADMIN_EMAILS=admin@example.com" in written
    assert "AI_PROVIDER=openai" in written
    assert "ADMIN_EMAILS" not in environ
```

- [ ] **Step 2: 실패를 확인한다**

```
source venv/bin/activate && pytest tests/app/test_common_env_service.py -v
```

기대: `ADMIN_EMAILS` 가 응답에 들어 있고 덮어써져서 두 건이 실패한다.

- [ ] **Step 3: 허용 목록을 넣는다**

`services/common_env_service.py` 의 `SENSITIVE_KEYWORDS` 를 지우고 그 자리에 둔다.

```python
# 설정 화면(`SettingsModal.tsx`)이 실제로 읽고 쓰는 키만 오간다. 나머지를 함께
# 실어 보내면 관리자 화면 하나가 .env 전체의 사본이 된다. 화면에 필드를 더할 때
# 이 목록에도 키를 더한다.
EDITABLE_ENV_KEYS = frozenset(
    {
        "AI_PROVIDER",
        "DISCORD_WEBHOOK_URL",
        "EMAIL_RECIPIENTS",
        "GOOGLE_SEARCH_ENGINE_ID",
        "OPENAI_API_KEY",
        "PERPLEXITY_API_KEY",
        "SMTP_HOST",
        "SMTP_PASSWORD",
        "SMTP_PORT",
        "SMTP_USER",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
    }
)

# 값 자체가 화면 동작에 필요하고 새어도 무해한 키. AI_PROVIDER 를 가리면 공급자
# 버튼이 어느 것도 선택되지 않고, SMTP_PORT 를 가리면 포트 입력이 별표로 찬다.
PLAIN_ENV_KEYS = frozenset({"AI_PROVIDER", "SMTP_PORT"})
```

`_mask_env_value` 의 판정을 뒤집는다.

```python
def _mask_env_value(key: str, value: str) -> str:
    if key in PLAIN_ENV_KEYS:
        return value
    if len(value) > 8:
        return value[:4] + ("*" * (len(value) - 8)) + value[-4:]
    return "*" * len(value)
```

`read_masked_env_vars` 의 루프에서 `env_vars[key] = ...` 앞에 한 줄을 더한다.

```python
            if key not in EDITABLE_ENV_KEYS:
                continue
```

`update_env_file` 은 들어온 `data` 를 먼저 거른다. 함수 앞부분의 `if not data: return`
바로 아래에 둔다.

```python
    data = {key: value for key, value in data.items() if key in EDITABLE_ENV_KEYS}
    if not data:
        return
```

- [ ] **Step 4: 통과를 확인한다**

```
source venv/bin/activate && pytest tests/app/test_common_env_service.py -v
```

기대: 전부 통과. 기존
`test_read_masked_env_vars_masks_sensitive_and_skips_empty` 와
`test_update_env_file_preserves_masked_input_and_deletes_empty` 가 허용 목록 밖의 키로
검사하고 있으면, 검사 의도를 유지한 채 키를 `EDITABLE_ENV_KEYS` 안의 것으로 바꾼다.
기대값만 바꿔 통과시키지 않는다.

---

### Task 4: Next.js 라우트 핸들러가 세션을 확인해 중계한다

**Files:**
- Create: `frontend/src/lib/adminEmails.ts`
- Create: `frontend/src/lib/adminEmails.test.ts`
- Create: `frontend/src/app/api/system/env/route.ts`
- Modify: `frontend/next.config.js:11-19`

**Interfaces:**
- Consumes: `authOptions` (`frontend/src/lib/auth.ts`), Flask 의 `X-Admin-Token` 계약
- Produces: `isAdminEmail(email, rawList) -> boolean`, `/api/system/env` 의 `GET`·`POST` 핸들러

**판정을 라우트 핸들러 안에 두지 않는다.** 「누가 관리자인가」를 정하는 자리는 이번 변경
전체에서 여기 하나뿐이다. Flask 의 토큰 검사는 「Next 를 거쳤는가」만 확인하므로, 대소문자나
공백 처리가 어긋나도 그쪽에서는 걸리지 않는다. 라우트 핸들러는 `getServerSession` 과
`fetch` 에 얽혀 있어 검사를 붙이기 어려우므로 판정만 순수 함수로 빼고 그 함수를 검사한다.

같은 규칙을 두 언어로 두 번 적는 셈이므로 어긋날 여지가 생긴다. `services/admin_helpers.py`
의 `is_admin_email` 과 규칙을 맞춘다. 쉼표로 나누고, 앞뒤 공백을 없애고, 소문자로 맞추고,
`user@example.com` 을 거부한다. 그 이메일은 `SettingsModal.tsx:25` 가 쓰는 기본값이라
관리자 목록에 들어가서는 안 된다.

읽을 문서: `frontend/node_modules/next/dist/docs/01-app/01-getting-started/15-route-handlers.md`
(라우트 핸들러 파일 규약과 지원 메서드),
`frontend/node_modules/next/dist/docs/01-app/03-api-reference/05-config/01-next-config-js/rewrites.md`
(라우트 검사 순서). 배열을 돌려주는 `rewrites()` 는 `afterFiles` 로 취급되어 파일시스템
라우트 뒤에 검사되므로 이 핸들러가 rewrite 보다 앞선다. 다만 그 순서에 기대지 않고
rewrite 의 `source` 에서 이 경로를 명시적으로 뺀다. 정규식 한 조각이 의도를 드러낸다.

**Flask 쪽 토큰 검사를 「Next 가 이미 막으니 중복」이라며 걷어내지 않는다.** 계획 검토가
확인한 우회 사례가 있다. `/api/system%2Fenv` 는 부정 전방탐색을 빠져나가 rewrite 를 타고
Flask 로 넘어가는데, WSGI 서버가 `PATH_INFO` 를 디코딩하므로 Flask 는 이를
`/api/system/env` 로 라우팅한다. 이때 요청을 세우는 것은 Flask 의 토큰 검사뿐이다.
(같은 검토가 `/api/system/env/` 와 `/api//system/env` 는 각각 부정 전방탐색과 Werkzeug 의
`merge_slashes` 에 걸려 통과하지 못함을 함께 확인했다.)

- [ ] **Step 1: 판정 함수와 그 검사를 만든다**

`frontend/src/lib/adminEmails.ts`:

```ts
/**
 * ADMIN_EMAILS 목록에 이 이메일이 있는지 판정한다.
 *
 * `services/admin_helpers.py` 의 `is_admin_email` 과 같은 규칙을 쓴다. 두 언어에
 * 같은 규칙이 두 벌 있으므로 한쪽을 고치면 다른 쪽도 고친다.
 */
export function isAdminEmail(
  email: string | null | undefined,
  rawList: string | undefined
): boolean {
  const normalized = email?.trim().toLowerCase();
  if (!normalized || normalized === 'user@example.com') {
    return false;
  }
  return (rawList || '')
    .split(',')
    .map((entry) => entry.trim().toLowerCase())
    .filter(Boolean)
    .includes(normalized);
}
```

`frontend/src/lib/adminEmails.test.ts`:

```ts
import { describe, expect, it } from 'vitest';

import { isAdminEmail } from './adminEmails';

describe('isAdminEmail', () => {
  const LIST = ' Alpha@Example.com , beta@example.com ';

  it('대소문자와 공백을 무시하고 대조한다', () => {
    expect(isAdminEmail('ALPHA@example.com', LIST)).toBe(true);
    expect(isAdminEmail('  beta@example.com  ', LIST)).toBe(true);
  });

  it('목록에 없는 이메일을 거부한다', () => {
    expect(isAdminEmail('gamma@example.com', LIST)).toBe(false);
  });

  it('빈 값과 기본 프로필 이메일을 거부한다', () => {
    expect(isAdminEmail(null, LIST)).toBe(false);
    expect(isAdminEmail(undefined, LIST)).toBe(false);
    expect(isAdminEmail('', LIST)).toBe(false);
    expect(isAdminEmail('user@example.com', 'user@example.com')).toBe(false);
  });

  it('목록이 비어 있으면 아무도 통과시키지 않는다', () => {
    expect(isAdminEmail('alpha@example.com', '')).toBe(false);
    expect(isAdminEmail('alpha@example.com', undefined)).toBe(false);
    expect(isAdminEmail('alpha@example.com', ' , , ')).toBe(false);
  });
});
```

검사를 돌린다.

```
cd frontend && npx vitest run src/lib/adminEmails.test.ts
```

기대: 4 passed

- [ ] **Step 2: 라우트 핸들러를 만든다**

```ts
import { getServerSession } from 'next-auth';
import { NextResponse } from 'next/server';

import { isAdminEmail } from '@/lib/adminEmails';
import { authOptions } from '@/lib/auth';

/**
 * Flask 는 NextAuth 세션을 알지 못하므로 신원 확인을 여기서 끝낸다. 세션에서 얻은
 * 이메일이 ADMIN_EMAILS 에 있을 때만 서버끼리 공유하는 토큰을 붙여 넘긴다.
 *
 * ADMIN_API_TOKEN 은 이 파일이 서버에서만 실행되기 때문에 안전하다. NEXT_PUBLIC_
 * 접두사를 붙이면 브라우저 번들에 실려 이 게이트가 무의미해진다.
 */
const FLASK_BASE =
  process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:5501';

async function resolveAdminToken(): Promise<string | null> {
  const session = await getServerSession(authOptions);
  if (!isAdminEmail(session?.user?.email, process.env.ADMIN_EMAILS)) {
    return null;
  }
  const token = (process.env.ADMIN_API_TOKEN || '').trim();
  return token || null;
}

async function proxy(method: 'GET' | 'POST', body?: string) {
  const token = await resolveAdminToken();
  if (!token) {
    return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
  }

  const response = await fetch(`${FLASK_BASE}/api/system/env`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      'X-Admin-Token': token,
    },
    body,
    cache: 'no-store',
  });

  const text = await response.text();
  return new NextResponse(text, {
    status: response.status,
    headers: { 'Content-Type': 'application/json' },
  });
}

export async function GET() {
  return proxy('GET');
}

export async function POST(request: Request) {
  return proxy('POST', await request.text());
}
```

`ADMIN_API_TOKEN` 이 비어 있으면 관리자에게도 403 이 간다. 설정을 빠뜨린 배포에서
게이트가 열리는 것보다 관리자가 설정 화면을 못 여는 편이 낫다.

- [ ] **Step 3: rewrite 에서 이 경로를 뺀다**

`frontend/next.config.js` 의 `source` 를 바꾼다.

```js
        source: '/api/:path((?!auth|system/env).*)',
```

- [ ] **Step 4: 타입 검사를 돌린다**

```
cd frontend && npm run type-check
```

기대: exit 0

---

### Task 5: 비관리자에게 `.env` 탭을 감춘다

**Files:**
- Modify: `frontend/src/app/components/SettingsModal.tsx:23,99-116,155-175,265-275,340-372`
- Test: `frontend/src/app/components/SettingsModal.admin-gate.test.tsx` (신규)

**Interfaces:**
- Consumes: `useAdmin` (`frontend/src/hooks/useAdmin.ts`)

설정 버튼은 관리자 전용이 아니다. `Sidebar.tsx:242` 의 `isAdmin` 은 배지 표시에만 쓰이고
설정 메뉴는 로그인한 모든 사용자에게 보인다. 그래서 게이트를 세우면 일반 사용자가 모달을
열 때마다 403 을 받고, 저장을 누르면 「API 설정」 실패가 뜬다. 요청을 보내지 않게 하고
`.env` 를 다루는 탭을 아예 감춘다.

네 탭 가운데 `api`·`notification`·`system` 이 `.env` 를 다루고, `profile` 은
`saveUserProfile` 이라는 별도 경로를 쓰므로 그대로 둔다.

읽을 문서: `frontend/node_modules/next/dist/docs/01-app/01-getting-started/05-server-and-client-components.md`
(이 파일은 `'use client'` 컴포넌트이고 `useAdmin` 도 클라이언트 훅이므로 경계를 넘지 않음을 확인한다)

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`frontend/src/app/components/SettingsModal.admin-gate.test.tsx` 를 만든다. 기존
`SettingsModal.apikeys.test.tsx` 의 모킹 방식을 그대로 따른다.

`vi.mock` 은 파일 최상단으로 끌어올려지므로 팩토리 안에서 바깥의 `const` 를 참조하면
`Cannot access ... before initialization` 으로 파일 자체가 실행되지 않는다. `vi.hoisted`
로 함께 끌어올린다. 나머지 모킹 대상은 기존 `SettingsModal.apikeys.test.tsx` 와 같다.
`next/navigation` 과 `@/lib/session` 을 빠뜨리면 컴포넌트가 렌더 중에 터진다.

```tsx
import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import SettingsModal from './SettingsModal';

const { mockUseAdmin } = vi.hoisted(() => ({
  mockUseAdmin: vi.fn(() => ({ isAdmin: false, isLoading: false, userEmail: null })),
}));

vi.mock('@/hooks/useAdmin', () => ({
  useAdmin: () => mockUseAdmin(),
}));

vi.mock('next-auth/react', () => ({
  useSession: () => ({ data: null, status: 'unauthenticated' }),
  signIn: vi.fn(),
  signOut: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ refresh: vi.fn(), push: vi.fn() }),
}));

vi.mock('@/lib/session', () => ({
  getBrowserSessionId: () => 'anon_test',
}));

describe('SettingsModal 관리자 게이트', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    global.fetch = vi.fn(async () => ({
      ok: true,
      json: async () => ({}),
    })) as unknown as typeof fetch;
  });

  it('비관리자에게는 .env 탭을 보여주지 않는다', () => {
    mockUseAdmin.mockImplementation(() => ({ isAdmin: false, isLoading: false, userEmail: null }));

    render(
      <SettingsModal isOpen profile={{ name: '', email: '', persona: '' }} onClose={() => {}} onSave={async () => {}} />
    );

    expect(screen.queryByText('API 설정')).toBeNull();
    expect(screen.queryByText('알림 설정')).toBeNull();
  });

  it('비관리자에게는 환경 변수를 조회하지 않는다', async () => {
    mockUseAdmin.mockImplementation(() => ({ isAdmin: false, isLoading: false, userEmail: null }));

    render(
      <SettingsModal isOpen profile={{ name: '', email: '', persona: '' }} onClose={() => {}} onSave={async () => {}} />
    );

    await waitFor(() => {
      const calls = (global.fetch as ReturnType<typeof vi.fn>).mock.calls;
      expect(calls.some(([url]) => String(url).includes('/api/system/env'))).toBe(false);
    });
  });

  it('관리자에게는 환경 변수를 조회한다', async () => {
    mockUseAdmin.mockImplementation(() => ({ isAdmin: true, isLoading: false, userEmail: 'a@b.com' }));

    render(
      <SettingsModal isOpen profile={{ name: '', email: '', persona: '' }} onClose={() => {}} onSave={async () => {}} />
    );

    await waitFor(() => {
      const calls = (global.fetch as ReturnType<typeof vi.fn>).mock.calls;
      expect(calls.some(([url]) => String(url).includes('/api/system/env'))).toBe(true);
    });
  });
});
```

프롭 형태는 `SettingsModal.tsx:11-16` 의 `SettingsModalProps` 와 맞다. 탭 버튼의 실제
문구는 `SettingsModal.tsx:341-370` 에서 확인해 `queryByText` 인자를 맞춘다.

- [ ] **Step 2: 실패를 확인한다**

```
cd frontend && npx vitest run src/app/components/SettingsModal.admin-gate.test.tsx
```

기대: 비관리자에게도 탭이 보이고 요청이 나가므로 두 건이 실패한다.

- [ ] **Step 3: 구현한다**

`useAdmin` 은 이미 `SettingsModal.tsx:7` 에서 import 되어 `:36` 에서 `isAdmin` 으로
받고 있다. 프로필 탭의 관리자 배지(`:380`, `:411`, `:414`)와 사용량 표시(`:540`, `:547`)가
그 값을 쓰는 중이다. 훅을 새로 들이지 말고 그 `isAdmin` 을 그대로 쓴다.

조회 훅을 관리자에게만 돌린다.

```tsx
  useEffect(() => {
    if (isOpen && isAdmin) {
      fetchEnvVars();
    }
  }, [isOpen, isAdmin]);
```

`handleSave` 의 환경 변수 저장 블록을 `if (isAdmin) { ... }` 으로 감싼다. 비관리자는
프로필과 관심종목만 저장하며, 실패 목록에 「API 설정」이 들어가지 않는다.

탭 버튼 세 개(`api`·`notification`·`system`)를 `{isAdmin && (...)}` 으로 감싼다.
비관리자가 URL 이나 이전 상태로 그 탭에 머무는 경우를 막기 위해, 탭 본문 조건도
`activeTab === 'api' && isAdmin` 형태로 바꾼다.

`handleTestNotification` 은 알림 탭 안에만 있으므로 탭을 감추면 닿을 수 없다. 그래도
함수 첫 줄에 `if (!isAdmin) return;` 을 둔다. 화면 조건 하나가 바뀌어도 요청이 새지
않는다.

**이 조치는 화면의 편의일 뿐 엔드포인트를 닫지 않는다.**
`app/routes/common_notification_routes.py:123` 의 `send_test_notification` 에는 권한
검사가 없고 rewrite 제외 대상도 아니다. 그래서 누구든 그 경로로 POST 하면 서버가 저장된
텔레그램·디스코드·메일 자격 증명으로 실제 발송을 수행한다. 이 경로는 `.env` 를 읽지도
쓰지도 않아 `[INFRA-025]` 의 범위가 아니므로 여기서 고치지 않고, `[3] 검증` 의 범위 밖
발견으로 `TODO.md` 에 새 항목을 세운다.

- [ ] **Step 4: 통과를 확인한다**

```
cd frontend && npx vitest run src/app/components/ && npm run type-check
```

기대: 전부 통과. 기존 `SettingsModal.apikeys.test.tsx` 와
`SettingsModal.save-isolation.test.tsx` 가 `useAdmin` 모킹 없이 돌면 `isAdmin` 이
`false` 가 되어 깨진다. 두 파일에 관리자 모킹을 더한다.

---

### Task 6: 설정과 문서를 맞춘다

**Files:**
- Modify: `.env.example`
- Modify: `README.md` (관리자 전용 서술이 있는 절)

- [ ] **Step 1: `.env.example` 에 토큰을 적는다**

`# === Admin Config ===` 절의 `ADMIN_EMAILS` 아래에 붙인다.

```
# Next.js 라우트 핸들러가 관리자 세션을 확인한 뒤 Flask 로 붙이는 서버 전용 토큰.
# 두 프로세스가 같은 .env 를 읽으므로 한 곳에만 적으면 된다. 비어 있으면
# /api/system/env 는 모든 요청을 403 으로 막는다.
# 생성: python3 -c "import secrets; print(secrets.token_urlsafe(32))"
# NEXT_PUBLIC_ 접두사를 붙이지 않는다. 붙이면 브라우저 번들에 실린다.
ADMIN_API_TOKEN=
```

- [ ] **Step 2: README 를 확인한다**

```
grep -n "system/env\|관리자" README.md | head -20
```

`/api/system/env` 를 관리자 전용으로 서술한 문장이 이제 코드와 맞는다. DELETE 를 언급한
문장이 있으면 지운다. 없으면 손대지 않는다.

- [ ] **Step 3: 실제 `.env` 에 토큰을 넣는다**

로컬에서 화면을 확인하려면 실제 `.env` 에도 값이 필요하다. QA 단계에서 값을 만들어
넣되, 그 값을 대화·문서·커밋 어디에도 적지 않는다.

---

## 검증

`tier-rules.md` §1 의 T3 검증을 그대로 수행한다.

```
source venv/bin/activate && pytest
cd frontend && npx vitest run
cd frontend && npm run type-check
```

구현 전 기준선은 2026-09-07 에 측정했다. pytest 는 1746 passed · 2 skipped,
vitest 는 49 files · 305 tests passed 이며 둘 다 exit 0 이었다. 구현 뒤 이 수치보다
줄어들면 무엇이 사라졌는지 밝힌다.

여기에 §1 의 시크릿 확인 세 가지를 더한다. `.env` 로 시작하는 파일을 다루므로
`tier-rules.md` §2 「시크릿과 인증」의 위험 경로에 해당한다.

리뷰는 `/ponytail-review` → `feature-dev:code-reviewer` → `/review` 순서로 하고,
인증 경계를 바꾸므로 `oh-my-claudecode:security-reviewer` 를 더한다.

## QA 시나리오 초안

`[3] 검증` 에서 `/qa-only` 로 정식 행렬을 만든다. 아래는 출발점이다.

| # | 시나리오 | 기대 | 필수 |
|---|---|---|---|
| 1 | 토큰 없이 `GET /api/system/env` 를 직접 호출 | 403, 본문에 환경 변수 없음 | 필수 |
| 2 | 토큰 없이 `POST /api/system/env` 로 값을 보냄 | 403, `.env` 변경 없음 | 필수 |
| 3 | `DELETE /api/system/env` | 405 | 필수 |
| 4 | 관리자로 로그인해 설정 모달을 열고 알림 탭 확인 | 값이 마스킹되어 표시됨 | 필수 |
| 5 | 비관리자로 로그인해 설정 모달을 엶 | 프로필 탭만 보이고 `/api/system/env` 요청이 나가지 않음 | 필수 |
| 6 | 관리자가 `AI_PROVIDER` 를 바꾸고 저장 | `.env` 에 반영, 다른 키는 그대로 | 필수 |
| 7 | `ADMIN_EMAILS` 를 POST 로 덮어쓰려 시도 | 무시되고 기존 값 유지 | 필수 |
| 8 | `ADMIN_API_TOKEN` 을 비운 상태로 관리자가 모달을 엶 | 403, 화면이 깨지지 않음 | 선택 |

2번과 6번은 `.env` 를 실제로 쓰므로 사본을 두고 확인한 뒤 되돌린다.
