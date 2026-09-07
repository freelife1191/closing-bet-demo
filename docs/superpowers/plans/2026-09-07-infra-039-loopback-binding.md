# [INFRA-039] Flask 바인딩을 loopback 으로 좁히는 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `[INFRA-027]` 의 신원 서명이 안전한 근거인 「서명이 proxy 와 Flask 사이에서만 오간다」를 관례가 아니라 바인딩 주소로 강제한다.

**Architecture:** Flask 는 Next.js 의 rewrite 로만 트래픽을 받는다. `next.config.js:20` 이 이미 `http://127.0.0.1:5501` 로 보내고 있고 `.env` 양쪽 모두 `API_URL` 을 설정하지 않으므로, Flask 를 loopback 에만 묶어도 실제 경로는 그대로다. 바인딩을 정하는 자리는 네 곳이며 그 가운데 셋을 `FLASK_HOST` 하나로 모으고, PaaS 전용인 `Procfile` 만 `0.0.0.0` 예외로 남긴다.

**Tech Stack:** Flask 3.1.2, gunicorn, Python `os.getenv`, zsh(`restart_all.sh`), pytest.

**Spec:** 이 문서에 함께 담았다. 설계는 2026-09-07 대화에서 AskUserQuestion 세 건과 「진행해」 응답으로 승인되었다.

## Global Constraints

- **`.env` 로 시작하는 파일은 `.env.example` 만 추적한다.** `.env` 와 `.env.production` 은 값을 고치되 커밋하지 않으며, 어떤 출력에도 그 파일의 다른 값을 싣지 않는다.
- **`Procfile` 의 명령 줄은 바꾸지 않는다.** PaaS 라우터는 컨테이너 밖에서 들어오므로 `0.0.0.0` 이 구조적으로 필수다. 이 파일 자체가 PaaS 전용이며 `$PORT` 도 그 플랫폼이 주는 값이다. 다만 왜 여기만 예외인지 주석 한 줄을 더한다(Task 3 Step 5).
- **`frontend/` 는 건드리지 않는다.** `next.config.js:20` 의 `http://127.0.0.1:5501` 은 이미 loopback 이며 이 변경이 요구하는 조건을 이미 만족한다.
- 티어는 **T3** 이다. `.env.example` 이 `tier-rules.md` §2 「시크릿과 인증」에 해당하므로 한 줄만 바꿔도 T3 이며, 시크릿 확인 3항과 보안 리뷰 보강이 붙는다.
- 되돌리는 방법은 `.env` 의 `FLASK_HOST` 한 줄을 `0.0.0.0` 으로 되돌리고 워커를 재기동하는 것이다. 코드를 되돌릴 필요가 없다.

## 설계

### 지금 상태 (실측)

| 확인 대상 | 값 | 확인 방법 |
|---|---|---|
| Flask 실제 바인딩 | `*:5501` (모든 인터페이스) | `lsof -nP -iTCP:5501 -sTCP:LISTEN` |
| Next → Flask 경로 | `http://127.0.0.1:5501` | `frontend/next.config.js:20` |
| `API_URL`·`NEXT_PUBLIC_API_URL` | `.env`·`.env.production` 양쪽 모두 없음 | `grep -E '^(API_URL\|NEXT_PUBLIC_API_URL)='` |
| `FLASK_HOST` | 양쪽 모두 `0.0.0.0` | 같은 `grep` |
| LAN 주소로 Flask 직접 접속 | **200** | `curl http://192.168.50.7:5501/api/kr/status` |
| LAN 주소로 Next 접속 | 200 | `curl http://192.168.50.7:3500/api/kr/status` |

아래 두 줄이 QA 의 기준값이다. 고친 뒤 5501 은 연결 거부(`curl` 종료 코드 7)여야 하고 3500 은 200 을 유지해야 한다. 이 값은 변경 전에만 확인할 수 있으므로 구현을 시작하기 전에 미리 재 두었다.

**감사 로그 두 줄에 대한 첫 해석은 틀렸다.** 처음에는 `::1` 을 `request.remote_addr` 에서 온 값으로 읽고 「Next.js 의 rewrite 는 `X-Forwarded-For` 를 붙이지 않는다」고 결론지었으나, `infra039-critic` 의 지적으로 두 대목 모두 성립하지 않음이 드러났다. 원인은 `app/__init__.py:187` 의 `_should_skip_activity_logging` 이 `GET` 을 전부 건너뛴다는 것이다. `GET` 으로 재 놓고 로그의 마지막 줄들을 읽었으므로, 본 것은 앞선 라운드가 남긴 다른 요청의 기록이었다.

기록되는 `POST /api/system/log-event` 로 다시 재면 이렇게 나온다.

| 경로 | 기록된 IP |
|---|---|
| Next 경유, 헤더 없음 | `::ffff:127.0.0.1` |
| Next 경유, `X-Forwarded-For: 203.0.113.9` | `203.0.113.9` |
| Flask 직접, `X-Forwarded-For: 198.51.100.4` | `198.51.100.4` |

`frontend/node_modules/next/dist/server/base-server.js:612` 가 근거다.

```js
req.headers['x-forwarded-for'] ??= originalRequest?.socket?.remoteAddress;
```

Next 는 헤더를 **붙이되** `??=` 이므로 클라이언트가 보낸 값을 덮어쓰지 않는다. 따라서 (1) `_resolve_real_ip` 는 지금 실제 클라이언트 IP 를 기록하고 있고, (2) 그것을 지우면 감사 기록의 IP 가 전부 `127.0.0.1` 이 되며, (3) `ProxyFix(x_for=1)` 를 넣어도 위조를 막지 못한다.

**그러므로 이 항목에서 `_resolve_real_ip` 를 손대지 않는다.** 2026-09-07 사용자 결정이다. 위조를 막으면서 진짜 IP 를 지키는 길이 없기 때문이다. `proxy.ts` 도 진짜 소켓 주소를 알 수 없다. Next 15 에서 `request.ip` 가 사라졌고 proxy 는 이미 채워진 헤더만 본다. 같은 패턴이 `app/routes/common_update_routes.py:97` 과 `services/kr_market_chatbot_request_helpers.py:212` 에도 있어 한 자리만 고치면 오히려 의도가 흐려진다. 앞단 배포 구조를 정한 뒤 세 자리를 한꺼번에 다루도록 `[INFRA-045]` 로 올린다.

### 바인딩을 정하는 네 자리

| 자리 | 지금 | 뒤 | 이유 |
|---|---|---|---|
| `config.py:194` | `os.getenv("FLASK_HOST", "0.0.0.0")` | 기본값 `127.0.0.1` | `FLASK_HOST` 를 적지 않은 배포가 기본으로 안전하다 |
| `.env` · `.env.production` | `FLASK_HOST=0.0.0.0` | `FLASK_HOST=127.0.0.1` | 기본값만 고치면 명시된 값에 가려 실제 동작이 그대로다 |
| `restart_all.sh:80` | `--bind 0.0.0.0:$FLASK_PORT` | `--bind ${FLASK_HOST:-127.0.0.1}:$FLASK_PORT` | 운영 gunicorn 이 `config.py` 를 거치지 않으므로 이 자리를 따로 맞춘다 |
| `Procfile:1` | `--bind 0.0.0.0:$PORT` | 명령은 그대로, 주석 추가 | PaaS 는 컨테이너 밖에서 들어온다 |

**그 PaaS 배포가 지금 살아 있는지는 확인되지 않는다.** `Procfile` 은 2026-02-03 의 「Deployment Ready」 커밋 하나로 들어온 뒤 손대지 않았고, `README.md`·`AGENTS.md`·`CLAUDE.md` 어디에도 언급이 없다. 그렇더라도 파일이 남아 있는 한 누군가 그 경로로 배포할 수 있으므로 지운다는 판단은 하지 않는다. 대신 왜 이 파일만 `0.0.0.0` 인지를 파일 자신에 적어, 배포하는 사람이 읽을 자리에 둔다.

`restart_all.sh:11` 이 `set -a; source .env` 를 이미 실행하므로 80행에서 `$FLASK_HOST` 를 읽을 수 있다.

**다섯 번째 자리는 `run.py:95` 이며 손대지 않는다.** 대화형 메뉴의 6번이 `from flask_app import app` 뒤에 인자 없는 `app.run()` 을 부른다. 인자가 없으므로 Flask 기본값인 **`127.0.0.1:5000`** 에 붙으며 `FLASK_HOST` 도 `FLASK_PORT` 도 무시한다. 노출 위험이 없어 이 항목의 목적은 이미 만족하지만, 위 표의 「네 자리」가 전수가 아니라는 뜻이므로 여기 적어 둔다.

**프런트엔드가 Flask 를 부르는 자리도 둘이다.** `next.config.js:20` 의 rewrite 말고 `frontend/src/app/api/system/env/route.ts:17` 이 있다. `process.env.API_URL || 'http://127.0.0.1:5501'` 이므로 이 경로의 기본값도 loopback 이라 바인딩을 좁혀도 깨지지 않는다.

**문서 세 곳이 `0.0.0.0` 을 안내하고 있어 함께 고친다.** 코드만 고치면 다음 사람이 문서를 보고 되돌린다.

| 문서 | 지금 |
|---|---|
| `README.md:64` | `FLASK_HOST=0.0.0.0` |
| `AGENTS.md:88` | `gunicorn ... --bind 0.0.0.0:5501 ...` |
| `CLAUDE.md:35` | 같은 gunicorn 예시 |

### `app/__init__.py` 의 `__main__` 블록을 지우는 근거

실제 진입점은 `flask_app.py` 이며 그것이 `from app import create_app` 으로 팩토리를 쓴다. `python app/__init__.py` 나 `python -m app` 을 부르는 자리가 스크립트에도 문서에도 없다. 호출자가 없는 세 줄이면서 Werkzeug 디버거를 모든 인터페이스에 여는 코드이므로, 좁히는 것보다 지우는 편이 더 짧고 더 안전하다.

---

### Task 1: 바인딩을 loopback 으로 좁힌다

**Files:**
- Modify: `config.py:194`
- Modify: `restart_all.sh:80`
- Modify: `.env`, `.env.production` (추적하지 않는다)
- Test: `tests/app/test_flask_binding.py`

**Interfaces:**
- Consumes: 없음
- Produces: `config.AppConfig.FLASK_HOST` 의 기본값이 `127.0.0.1` 이 된다. Task 3 의 `.env.example` 문구가 이 값을 설명한다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`importlib.reload` 를 쓰지 않는다. `config.py:13` 이 모듈 최상단에서 `load_dotenv()` 를 부르므로 `reload` 는 그 줄을 다시 실행하고, `monkeypatch.delenv("FLASK_HOST")` 직후에는 그 변수가 `os.environ` 에 없어 `.env` 파일의 값이 그대로 채워진다. 그러면 검증 대상이 `config.py` 의 기본값이 아니라 `.env` 의 값이 된다.

저장소에 이미 올바른 본보기가 있다. `tests/engine/test_config_env_precedence.py` 가 `.env` 가 없는 임시 디렉터리에서 하위 프로세스로 값을 읽는다. 같은 방식을 따른다.

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[INFRA-039] Flask 바인딩 기본값 검사."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_READ_HOST = "from config import config; print(config.FLASK_HOST)"


def _read_flask_host(tmp_path: Path, host: str | None) -> str:
    """`.env` 가 없는 디렉터리에서 config 를 새로 읽는다.

    config.py 는 모듈 최상단에서 load_dotenv() 를 부른다. 같은 프로세스 안에서
    importlib.reload 로 다시 읽으면 그 호출이 저장소 루트의 .env 를 다시 채우므로,
    코드의 기본값이 아니라 .env 의 값을 검사하게 된다. cwd 를 빈 임시 디렉터리로
    두면 load_dotenv() 가 읽을 파일이 없어 기본값이 그대로 드러난다.
    """
    env = os.environ.copy()
    env["PYTHONPATH"] = str(_REPO_ROOT)
    if host is None:
        env.pop("FLASK_HOST", None)
    else:
        env["FLASK_HOST"] = host

    result = subprocess.run(
        [sys.executable, "-c", _READ_HOST],
        cwd=tmp_path,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def test_default_host_is_loopback(tmp_path: Path):
    # FLASK_HOST 를 적지 않은 배포가 기본으로 안전해야 한다. `[INFRA-027]` 의 신원
    # 서명은 경로에도 메서드에도 묶여 있지 않은 120초 bearer 이고, 그것을 받아들이는
    # 근거가 서명이 proxy 와 Flask 사이에서만 오간다는 것이다. 기본값이 0.0.0.0 이면
    # 그 근거가 배포하는 사람의 방화벽 설정에만 남는다.
    assert _read_flask_host(tmp_path, None) == "127.0.0.1"


def test_explicit_host_still_wins(tmp_path: Path):
    # 컨테이너 밖에서 들어오는 배포는 0.0.0.0 이 필요하다. `Procfile` 이 그 경우다.
    # 좁힌 기본값이 그 경로를 막으면 안 된다.
    assert _read_flask_host(tmp_path, "0.0.0.0") == "0.0.0.0"
```

- [ ] **Step 2: 실패를 확인한다**

Run: `source venv/bin/activate && pytest tests/app/test_flask_binding.py -v`
Expected: `test_default_host_is_loopback` 이 `AssertionError: assert '0.0.0.0' == '127.0.0.1'` 로 실패하고, `test_explicit_host_still_wins` 는 통과한다. 실패의 원인이 `config.py` 의 기본값이어야 하며 `.env` 가 아니어야 한다. 하위 프로세스의 `cwd` 가 빈 임시 디렉터리이므로 그 조건이 보장된다.

- [ ] **Step 3: `config.py` 를 고친다**

```python
    # 기본값을 loopback 으로 둔다. `[INFRA-027]` 의 X-Auth-Identity 는 경로에도
    # 메서드에도 nonce 에도 묶여 있지 않은 120초 bearer 이고, 그것을 받아들이는 근거가
    # 서명이 proxy 와 Flask 사이에서만 오간다는 것이다. 모든 인터페이스에 열어 두면
    # 그 근거가 배포하는 사람의 방화벽 설정에만 남는다. 컨테이너 밖에서 들어오는
    # 배포는 FLASK_HOST 로 넓힌다 (`Procfile` 이 그 경우다).
    FLASK_HOST = os.getenv("FLASK_HOST", "127.0.0.1")
```

- [ ] **Step 4: 테스트가 통과하는지 확인한다**

Run: `source venv/bin/activate && pytest tests/app/test_flask_binding.py -v`
Expected: 2 passed

- [ ] **Step 5: `restart_all.sh:80` 을 고친다**

```bash
nohup gunicorn flask_app:app --bind ${FLASK_HOST:-127.0.0.1}:$FLASK_PORT --workers 2 --threads 8 --timeout 120 > logs/backend.log 2>&1 &
```

11행의 `set -a; source .env` 가 앞서 실행되므로 `$FLASK_HOST` 를 읽을 수 있다. `.env` 가 없는 환경에서도 loopback 으로 떨어진다.

- [ ] **Step 6: `.env` 와 `.env.production` 의 `FLASK_HOST` 를 고친다**

`FLASK_HOST=0.0.0.0` 한 줄을 `FLASK_HOST=127.0.0.1` 로 바꾼다. 두 파일 모두 추적하지 않으므로 커밋 대상이 아니며, 다른 줄은 읽지도 출력하지도 않는다.

---

### Task 2: 죽은 개발 진입점을 걷어낸다

**Files:**
- Modify: `app/__init__.py` (`__main__` 블록 삭제)

**Interfaces:**
- Consumes: 없음
- Produces: 없음

`_resolve_real_ip` 는 건드리지 않는다. 위의 「지금 상태」 절에 적은 대로 그 함수는 실제 클라이언트 IP 를 기록하고 있고, 지우면 감사 기록이 후퇴한다.

- [ ] **Step 1: `__main__` 블록을 지운다**

`app/__init__.py:297-299` 의 세 줄을 지운다.

```python
if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5501, debug=True)
```

지우기 전에 호출자가 없음을 다시 확인한다.

Run: `grep -rn "app/__init__\.py\|python -m app" --include='*.sh' --include='*.py' --include='*.md' . | grep -v venv | grep -v node_modules`
Expected: 실행 호출이 하나도 나오지 않는다. 문서의 설명 문장만 나온다.

---

### Task 3: 문서와 주석을 실제 상태에 맞춘다

**Files:**
- Modify: `.env.example` (`FLASK_HOST` 주석, `INTERNAL_IDENTITY_SECRET` 주석)
- Modify: `services/identity_helpers.py:62-71`
- Modify: `README.md:64`, `AGENTS.md:88`, `CLAUDE.md:35`
- Modify: `Procfile` (주석 한 줄만. 명령 줄은 그대로)

**Interfaces:**
- Consumes: Task 1 과 Task 2 의 결과. 두 파일 모두 그 결과를 설명하는 글이므로 마지막에 쓴다.
- Produces: 없음

- [ ] **Step 1: `.env.example` 의 `FLASK_HOST` 에 이유를 적는다**

35행 `FLASK_HOST=0.0.0.0` 을 다음으로 바꾼다.

```
# Flask 는 Next.js 의 rewrite 로만 트래픽을 받으며 그 대상이 127.0.0.1:5501 이다
# (`frontend/next.config.js`). loopback 에 묶어 두는 것은 `[INFRA-027]` 의 신원 서명이
# 안전한 근거이기도 하다. 그 서명은 경로에도 메서드에도 묶여 있지 않은 120초 bearer 라,
# 서명이 오가는 구간이 proxy 와 Flask 사이뿐이라는 전제가 깨지면 관측한 서명을 다른
# 엔드포인트에 그대로 붙일 수 있다.
# 컨테이너 밖에서 들어오는 배포는 0.0.0.0 이 필요하다. `Procfile` 이 그 경우이며 PaaS
# 라우터가 컨테이너 밖에 있으므로 그 파일만 0.0.0.0 을 그대로 둔다.
FLASK_HOST=127.0.0.1
```

- [ ] **Step 2: `INTERNAL_IDENTITY_SECRET` 주석에 알림 테스트를 더한다**

167행의 「비어 있으면 모든 요청이 익명으로 처리되어 챗봇 소유자 판정과 AI 분석이 막힌다」에 `[INFRA-037]` 이 만든 경로를 더한다.

```
# 비어 있으면 모든 요청이 익명으로 처리되어 챗봇 소유자 판정과 AI 분석이 막히고,
# 설정 화면의 알림 테스트 발송도 관리자 판정에서 떨어져 403 이 된다.
```

- [ ] **Step 3: `services/identity_helpers.py` 의 ponytail 주석을 갱신한다**

62-71행의 「그 전제를 코드가 강제하지 않으며, 현재 구성은 오히려 반대다」 문단을 지금 상태로 바꾼다. 이월 표시(`바인딩을 좁히는 일은 [INFRA-039] 다`)를 걷어내고, 남은 한계를 대신 적는다. 남은 한계는 `Procfile` 예외 하나이며, IP 헤더 위조는 이 주석이 다루는 신원 서명과 별개의 문제이므로 여기에 적지 않고 `[INFRA-045]` 로 둔다.

```python
    # ponytail: 이 서명은 경로에도 메서드에도 nonce 에도 묶여 있지 않아, 한 번 새면 만료
    # 전까지 어느 엔드포인트에나 쓸 수 있다. 이것을 받아들이는 근거는 서명이 오가는 구간이
    # proxy 와 Flask 사이뿐이고 브라우저로 돌아가지 않는다는 것이다
    # (`proxy.ts` 가 `NextResponse.next({ request: { headers } })` 를 쓰는 이유다).
    #
    # `[INFRA-039]` 가 그 전제를 바인딩으로 세웠다. `config.py` 의 FLASK_HOST 기본값과
    # `restart_all.sh` 가 loopback 을 쓰므로, 서명을 관측하려면 이미 그 기기 안에
    # 있어야 한다. 남은 예외는 `Procfile` 이며 PaaS 라우터가 컨테이너 밖에 있어
    # 0.0.0.0 이 필수다. 그 경로로 배포한다면 서명에 경로와 메서드를 넣거나 앞단에서
    # 5501 을 막아야 한다.
```

- [ ] **Step 4: `0.0.0.0` 을 안내하는 문서 세 곳을 고친다**

`README.md:64` 의 `FLASK_HOST=0.0.0.0` 을 `FLASK_HOST=127.0.0.1` 로 바꾸고, `AGENTS.md:88` 과 `CLAUDE.md:35` 의 gunicorn 예시를 `--bind 127.0.0.1:5501` 로 바꾼다. 두 예시에는 왜 loopback 인지 한 줄을 덧붙인다. 코드만 고치고 문서를 두면 다음 사람이 문서를 보고 되돌린다.

Run: `grep -rn '0\.0\.0\.0' --include='*.md' --include='*.sh' --include='*.py' . | grep -v venv | grep -v node_modules | grep -v docs/dev-cycle | grep -v docs/superpowers | grep -v 'Chrome/120'`
Expected: `Procfile` 만 남는다. `Chrome/120.0.0.0` 이 들어간 User-Agent 문자열 셋은 이 항목과 무관하므로 걸러 낸다.

- [ ] **Step 5: `Procfile` 에 예외의 이유를 적는다**

명령 줄은 바꾸지 않고 그 위에 주석 한 줄만 더한다. `.env.example` 의 설명은 `.env` 를 채우는 사람이 읽고, 이 주석은 `Procfile` 로 배포하는 사람이 읽는다.

```
# 이 파일만 0.0.0.0 이다. PaaS 라우터가 컨테이너 밖에 있어 loopback 으로는 닿지 못한다.
# 다른 자리(config.py 기본값, restart_all.sh, .env)는 [INFRA-039] 가 127.0.0.1 로 좁혔다.
web: gunicorn flask_app:app --bind 0.0.0.0:$PORT --workers 2 --threads 8 --timeout 120
```

`#` 로 시작하는 줄은 Procfile 형식에서 주석이며 프로세스 정의로 읽히지 않는다. 명령 줄 자체는 한 글자도 바뀌지 않는다.

- [ ] **Step 6: 시크릿 확인 3항을 실행한다**

`.env.example` 을 건드렸으므로 `tier-rules.md` §1 의 세 가지를 확인한다. 값은 어떤 출력에도 싣지 않는다.

---

### Task 4: 전체 검증과 QA

- [ ] **Step 1: 정적 검증**

Run: `source venv/bin/activate && pytest`
Expected: 기존 1792 통과에 신규 2건이 더해져 1794 통과이고 실패가 없다.

`frontend/` 를 건드리지 않으므로 vitest 와 `tsc` 는 회귀 확인용으로만 돌린다.

- [ ] **Step 2: 리뷰**

T3 순서를 지킨다: `/ponytail-review` → `feature-dev:code-reviewer` → `/review` → 보안 리뷰 보강.

- [ ] **Step 3: QA 시나리오와 실행**

`docs/dev-cycle/qa/INFRA-039.md` 를 만들고, 재기동한 서버로 LAN 주소에서 5501 에 닿지 않는 것과 화면이 정상 동작하는 것을 실측한다.

## Self-Review

**Spec coverage** — TODO 의 체크박스 여섯 개 가운데 다섯을 이 계획이 덮고, 나머지 하나는 별도 항목으로 옮긴다.

| TODO 체크박스 | 이 계획에서 |
|---|---|
| 바인딩 방식 결정 | AskUserQuestion 세 건으로 끝났다 |
| 네 자리를 맞춤 | Task 1 (셋) 과 `Procfile` 예외 결정 |
| 개발 진입점 | Task 2 |
| `.env.example` 에 이유 | Task 3 Step 1·2 |
| ponytail 주석 | Task 3 Step 3 |
| `_resolve_real_ip` | **`[INFRA-045]` 로 이월.** 사용자 결정이며 근거는 「지금 상태」 절에 있다 |

계획이 스스로 더한 것이 하나 있다. TODO 에 없던 문서 세 곳(`README.md`·`AGENTS.md`·`CLAUDE.md`)의 `0.0.0.0` 안내를 Task 3 Step 4 에서 함께 고친다. 코드만 고치고 문서를 두면 다음 사람이 문서를 보고 되돌린다.

**Placeholder scan** — TBD 나 「적절히 처리한다」류 문장이 없다. 모든 코드 단계에 실제 코드가 들어 있다.

**검토 반영** — `infra039-critic` 의 지적 다섯 건을 반영했다. (1) IP 헤더에 대한 첫 실측 해석이 틀렸음을 확인하고 사용자에게 다시 물어 이월로 정했다. (2) 같은 패턴이 세 자리라는 지적에 따라 한 자리만 고치지 않고 전부 `[INFRA-045]` 로 묶었다. (3) `test_activity_log_ip.py` 가 `GET` 제외 때문에 고치기 전에도 통과한다는 지적은 그 테스트를 통째로 빼면서 해소되었다. (4) `test_flask_binding.py` 의 `importlib.reload` 가 `load_dotenv()` 를 다시 불러 `.env` 를 검사하게 된다는 지적에 따라 하위 프로세스 방식으로 바꿨다. (5) `create_app()` 이 `SCHEDULER_ENABLED` 로 막히지 않는 `_reset_startup_status_files()` 로 `data/` 를 덮어쓴다는 지적도 그 테스트를 빼면서 해소되었다.

**Type consistency** — 새로 만드는 이름이 없다. `config.FLASK_HOST` 와 `request.remote_addr` 은 기존 이름이다.
