# [INFRA-049] `.env` 를 셸이 실행하지 않게 한다 — 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `restart_all.sh` 와 `stop_all.sh` 가 `.env` 를 `source` 하는 것을 걷어내고, 두
스크립트가 실제로 쓰는 세 값만 셸 해석 없이 읽게 한다.

**Architecture:** `.env` 는 데이터 파일이지 셸 스크립트가 아니다. `set -a; source .env` 는
`KEY=$(...)` 의 오른쪽을 대입 시점에 평가하므로, 설정 화면으로 저장할 수 있는 값이 다음
기동에서 임의 명령이 된다. 두 스크립트가 `.env` 에서 실제로 쓰는 값은 `FLASK_PORT`,
`FRONTEND_PORT`, `FLASK_HOST` 셋뿐이므로 그 셋만 `sed` 로 읽는 함수 하나를 공유한다.
export 는 없앤다. Flask 는 `app/__init__.py:28` 의 `load_dotenv()` 로, Next 는 `@next/env`
로 각자 `.env` 를 읽으므로 셸의 export 는 이미 중복이다.

**Tech Stack:** bash, pytest (`subprocess` 로 bash 함수를 부르는 기존 관례를 따른다 —
`tests/app/test_flask_binding.py`, `tests/engine/test_config_env_precedence.py`)

**Spec:** `docs/dev-cycle/TODO.md` 의 `[INFRA-049]` 항목. 별도 설계 문서는 두지 않는다
(bounded 분류이며 대화 설계로 승인받았다).

## Global Constraints

- **운영 `.env` 파일에 쓰지 않는다.** 읽기만 한다. 검사는 `tmp_path` 안의 `.env` 를 쓴다.
- **`.env` 의 값을 출력하지 않는다.** 길이와 일치 여부까지만 다룬다.
- **돌고 있는 서비스를 재기동하지 않는다.** gunicorn 마스터·워커(5501)와 next-server(3500)가
  기동 중이다. 검증은 임시 포트에 따로 띄운다.
- **임시로 띄우는 프로세스에는 `SCHEDULER_ENABLED=false` 와 `NOTIFICATION_ENABLED=false` 를
  반드시 함께 넘긴다.** 운영 `.env` 의 `NOTIFICATION_ENABLED` 는 `true` 이고 디스코드
  웹훅과 텔레그램 토큰과 SMTP 자격 증명이 실제 값으로 들어 있다. 이 저장소에는 과거에
  운영 채널로 실제 발송된 사고 기록이 있다. `engine/messenger_config.py:35` 와
  `services/notifier.py:43` 이 그 값을 읽고, `load_dotenv()` 가 `override=False` 이므로
  환경으로 넘긴 `false` 가 `.env` 의 `true` 를 이긴다.
- **`ln -sf ../.env frontend/.env` 는 그대로 둔다.** Next 가 그것으로 `.env` 를 읽는다.
- 값의 우선순위를 바꾸지 않는다. 지금 `set -a; source .env` 는 프로세스 환경을 덮어쓰므로
  `.env` 가 이긴다. 새 방식도 `.env` 를 먼저 읽고 없을 때만 코드 기본값으로 떨어진다.

---

## 조사로 확정한 사실

계획을 세우기 전에 실측한 것들이다. 구현 중에 다시 확인하지 않아도 된다.

1. **export 는 중복이다.** `app` 임포트를 추적하니 `load_dotenv()` 이전에 읽히는 환경
   변수는 `LANG`·`LANGUAGE`·`LC_ALL`·`LC_MESSAGES` 넷뿐이고 전부 `.env` 와 무관하다.
   `env -i` 로 깨끗하게 띄운 node 에서 `@next/env` 의 `loadEnvConfig` 를 부르면 `.env` 의
   키 58개가 채워지며 `ADMIN_API_TOKEN`·`NEXTAUTH_SECRET`·`INTERNAL_IDENTITY_SECRET` 이
   모두 들어온다.
2. **`sed` 방식은 지금 세 키의 값 모양에서만 다른 파서와 같은 값을 준다.**
   `FLASK_PORT`·`FRONTEND_PORT`·`FLASK_HOST` 셋을 `sed`·python-dotenv·bash 로 읽어
   비교했더니 전부 일치했다. **일반적으로 같지는 않다.** 임시 디렉터리에서 재현한
   갈림은 이렇다.

   | `.env` 의 줄 | `sed` 방식 | `source`(현재) | python-dotenv |
   |---|---|---|---|
   | `K="5501"` | `"5501"` | `5501` | `5501` |
   | `K='5501'` | `'5501'` | `5501` | `5501` |
   | `K=5501 # 백엔드 포트` | `5501 # 백엔드 포트` | `5501` | `5501` |
   | `export K=ok` | (빈 값) | `ok` | `ok` |
   | `K = 5501` | (빈 값) | (빈 값) | `5501` |
   | `K=5501␠␠␠` | 후행 공백 유지 | 제거 | 제거 |

   **인라인 주석은 이 저장소의 집필 관례다.** 운영 `.env` 159줄 가운데 21줄이
   `KEY=값  # 설명` 모양이고 `.env.example` 에도 같은 모양이 24줄 있다. 세 키가 언젠가
   그 모양이 되는 것은 가정이 아니다. 그래서 아래 5번의 포트 검사를 함께 넣는다.
3. **`.env` 는 159줄 전부 `KEY=` 형태**이고 CRLF 가 아니며, 앞에 공백이나 `export` 가 붙은
   줄이 없다. 세 키에는 따옴표도 인라인 주석도 없다. (`.env` 전체로 보면 인라인 `#` 이
   21줄, 공백이 든 값이 22줄 있으나 우리가 읽을 세 키가 아니다.)
4. **`source` 자리는 두 곳뿐이다.** `scripts/init_all.sh` 가 후보로 잡혔으나 실제로는
   `cp .env.example .env` 한 줄이었고 `.env` 를 `source` 하지 않는다.
5. **포트 값이 오염되면 `stop_all.sh` 가 조용히 거짓 성공을 보고한다.** 38행의
   `pids=$(lsof -ti :$port ...)` 는 `$port` 를 인용하지 않으므로, 값이
   `5501 # 백엔드 포트` 가 되면 단어 분리를 거쳐 `lsof -ti :5501 '#' 백엔드 포트` 가 된다.
   실제로 돌려 보니 정상 호출은 PID 3개를 찾고 오염된 호출은 0개를 찾으며, 58행의 최종
   확인 `if lsof -ti :$port >/dev/null 2>&1` 도 함께 실패해 **포트가 살아 있는데
   「✅ Port 5501 freed.」를 출력한다.** 현행 `source` 방식에는 없던 실패 모드이고
   `stop_all.sh` 에는 이것을 시끄럽게 만들 gunicorn 도 없다. 포트 검사로 막는다.

---

## File Structure

| 파일 | 책임 |
|---|---|
| `scripts/env_value.sh` (신규) | `.env` 에서 값 하나를 셸 해석 없이 읽는 `env_value`, 포트를 숫자로만 받는 `env_port` |
| `restart_all.sh` (수정) | 11행 `source` 제거, 세 값을 함수로 읽기, 80행 주석 갱신 |
| `stop_all.sh` (수정) | 13~20행 `source` 블록 제거, 두 포트를 함수로 읽기 |
| `tests/scripts/test_env_value_sh.py` (신규) | 셸 문법 미실행·파서 한계 고정·포트 거부·회귀 방지 |

함수를 파일 하나로 빼는 이유는 셋이다. 두 스크립트가 같은 `.env` 를 읽어 같은 포트를
다뤄야 하므로 한쪽만 고쳐지면 `stop_all.sh` 가 `restart_all.sh` 가 띄운 것을 못 내린다.
한계와 근거를 적을 자리가 한 곳으로 모인다. 그리고 **검사가 대상으로 삼을 자리가
생긴다** — 인라인 두 벌이면 검사가 스크립트 전체를 실행해야 하고 그러면 `pkill` 과
`kill_port` 가 딸려 온다.

`env_port` 를 함께 두는 이유는 조사 5번의 실패 모드 때문이다. 두 스크립트의 포트 두 개에
`case` 를 인라인으로 적으면 네 자리에 같은 문구가 흩어진다.

---

## Task 1: `.env` 값을 셸 해석 없이 읽는 두 함수

**Files:**
- Create: `scripts/env_value.sh`
- Test: `tests/scripts/test_env_value_sh.py`

**Interfaces:**
- Consumes: 없음 (첫 태스크)
- Produces:
  - `env_value <KEY>` — **현재 작업 디렉터리의** `.env` 에서 `KEY` 의 값을 표준 출력으로
    내보낸다. `.env` 가 없거나 키가 없으면 아무것도 내보내지 않고 0 을 돌려준다. 중복
    줄이 있으면 마지막 줄의 값을 쓴다. **따옴표·인라인 주석·후행 공백을 벗기지 않고
    `export KEY=값` 도 읽지 않는다.**
  - `env_port <KEY> <기본값>` — `env_value` 로 읽고, 비면 호출자가 export 한 같은 이름의
    값, 그것도 비면 기본값을 쓴다. 그 결과가 숫자가 아니면 표준 오류에 메시지를 내고 1 을
    돌려준다. 호출자는 `PORT=$(env_port KEY 기본값) || exit 1` 로 받는다.

- [ ] **Step 1: 실패하는 검사를 쓴다**

`tests/scripts/test_env_value_sh.py` 를 새로 만든다.

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[INFRA-049] 기동 스크립트가 .env 를 셸로 실행하지 않는지 검사한다."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ENV_VALUE_SH = _REPO_ROOT / "scripts" / "env_value.sh"

# 행 앞을 묶었으므로 주석 줄에는 걸리지 않는다. env_value.sh 의 주석이 옛 방식을
# 설명하면서 같은 문구를 담기 때문에 이 구분이 필요하다.
_SOURCES_ENV = re.compile(r"^\s*(?:source|\.)\s+\S*\.env\b", re.M)
_EXPORTS_ALL = re.compile(r"^\s*set\s+-a\b", re.M)


def _run(cwd: Path, snippet: str, *args: str) -> subprocess.CompletedProcess[str]:
    """env_value.sh 를 source 한 bash 에서 snippet 을 돌린다."""
    return subprocess.run(
        ["bash", "-c", f'source "{_ENV_VALUE_SH}"; {snippet}', "_", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def _env_value(cwd: Path, key: str) -> str:
    result = _run(cwd, 'env_value "$1"', key)
    assert result.returncode == 0, result.stderr
    return result.stdout.rstrip("\n")


def test_env_value_does_not_execute_shell_syntax(tmp_path: Path):
    """[INFRA-049] 값 안의 명령 치환·백틱·세미콜론·공백이 실행되지 않는다.

    `set -a; source .env` 는 대입의 오른쪽을 평가하므로 이 넷이 모두 명령이 되었다.
    설정 화면으로 저장할 수 있는 열두 키의 값이 그대로 이 자리에 온다.
    """
    (tmp_path / ".env").write_text(
        "SMTP_HOST=x$(touch pwned_subst)\n"
        "SMTP_USER=y`touch pwned_backtick`\n"
        "SMTP_PASSWORD=z; touch pwned_semi\n"
        "TELEGRAM_CHAT_ID=w touch pwned_space\n",
        encoding="utf-8",
    )

    assert _env_value(tmp_path, "SMTP_HOST") == "x$(touch pwned_subst)"
    assert _env_value(tmp_path, "SMTP_USER") == "y`touch pwned_backtick`"
    assert _env_value(tmp_path, "SMTP_PASSWORD") == "z; touch pwned_semi"
    assert _env_value(tmp_path, "TELEGRAM_CHAT_ID") == "w touch pwned_space"
    # 값이 리터럴로 돌아오는 것과 명령이 돌지 않은 것은 다른 보장이다. 둘 다 잰다.
    assert sorted(p.name for p in tmp_path.glob("pwned_*")) == []


def test_env_value_does_not_strip_quotes_or_inline_comments(tmp_path: Path):
    """[INFRA-049] 이 함수는 dotenv 가 아니다. 벗기지 않는 것을 명시해 둔다.

    `source` 와 python-dotenv 는 따옴표와 인라인 주석을 벗기지만 이 함수는 벗기지
    않는다. 지금 세 키가 그 모양이 아니라서 문제가 없을 뿐이다. 이 저장소의 `.env` 는
    159줄 가운데 21줄이 `KEY=값  # 설명` 모양이므로 언젠가 그 모양이 될 수 있다.
    포트는 env_port 가 막고, 나머지는 이 검사가 한계를 드러낸다.
    """
    (tmp_path / ".env").write_text(
        'QUOTED="5501"\n'
        "COMMENTED=5501 # 백엔드 포트\n"
        "export EXPORTED=ok\n",
        encoding="utf-8",
    )

    assert _env_value(tmp_path, "QUOTED") == '"5501"'
    assert _env_value(tmp_path, "COMMENTED") == "5501 # 백엔드 포트"
    assert _env_value(tmp_path, "EXPORTED") == ""


def test_env_value_takes_last_duplicate(tmp_path: Path):
    """[INFRA-049] 중복 줄에서 나중 것이 이긴다.

    bash 의 source, python-dotenv 의 dotenv_values, @next/env 가 모두 그렇게 읽는다.
    `tail -1` 이 사라지면 세 파서와 어긋나므로 여기서 잡는다.
    """
    (tmp_path / ".env").write_text("FLASK_PORT=1111\nFLASK_PORT=2222\n", encoding="utf-8")

    assert _env_value(tmp_path, "FLASK_PORT") == "2222"


def test_env_value_is_empty_without_env_file(tmp_path: Path):
    """[INFRA-049] .env 가 없으면 빈 값을 주고, 호출자의 기본값이 걸린다."""
    assert _env_value(tmp_path, "FLASK_PORT") == ""


def test_env_port_rejects_non_numeric_value(tmp_path: Path):
    """[INFRA-049] 포트가 숫자가 아니면 기동을 멈춘다.

    stop_all.sh 38행의 `lsof -ti :$port` 는 값을 인용하지 않는다. 값이
    `5501 # 백엔드 포트` 가 되면 단어 분리로 lsof 가 아무것도 못 찾고, 58행의 최종
    확인까지 함께 실패해 포트가 살아 있는데 「✅ Port freed」를 출력한다. 그 조용한
    거짓 성공을 여기서 막는다.
    """
    (tmp_path / ".env").write_text("FLASK_PORT=5501 # 백엔드 포트\n", encoding="utf-8")

    result = _run(tmp_path, 'env_port "$1" "$2"', "FLASK_PORT", "5501")
    assert result.returncode != 0
    assert result.stdout == ""
    assert "FLASK_PORT" in result.stderr


def test_env_port_prefers_env_file_then_inherited_then_default(tmp_path: Path):
    """[INFRA-049] `.env` > 상속 > 기본값 순서가 현행 source 방식과 같다.

    거부만 재면 전부 거부하는 코드도 위 검사를 통과하므로 통과 경로를 함께 잰다.
    `set -a; source .env` 는 `.env` 에 키가 없을 때 아무것도 덮어쓰지 않으므로 호출자가
    export 한 값이 살아남는다. `VAR=$(env_value VAR)` 로 무조건 덮어쓰면 그 순서가
    조용히 깨지므로 세 경우를 모두 잰다.
    """
    env = {"PATH": "/usr/bin:/bin", "FRONTEND_PORT": "4000"}

    # (1) .env 에 있으면 .env 가 이긴다
    (tmp_path / ".env").write_text("FRONTEND_PORT=3500\n", encoding="utf-8")
    result = subprocess.run(
        ["bash", "-c", f'source "{_ENV_VALUE_SH}"; env_port "$1" "$2"', "_", "FRONTEND_PORT", "9999"],
        cwd=tmp_path, env=env, capture_output=True, text=True,
    )
    assert result.stdout == "3500", result.stderr

    # (2) .env 에 없으면 상속받은 값이 산다
    (tmp_path / ".env").write_text("OTHER=x\n", encoding="utf-8")
    result = subprocess.run(
        ["bash", "-c", f'source "{_ENV_VALUE_SH}"; env_port "$1" "$2"', "_", "FRONTEND_PORT", "9999"],
        cwd=tmp_path, env=env, capture_output=True, text=True,
    )
    assert result.stdout == "4000", result.stderr

    # (3) 둘 다 없으면 코드 기본값
    result = subprocess.run(
        ["bash", "-c", f'source "{_ENV_VALUE_SH}"; env_port "$1" "$2"', "_", "FRONTEND_PORT", "9999"],
        cwd=tmp_path, env={"PATH": "/usr/bin:/bin"}, capture_output=True, text=True,
    )
    assert result.stdout == "9999", result.stderr


def test_env_value_matches_dotenv_for_startup_keys():
    """[INFRA-049] 저장소의 실제 .env 에서 세 키가 python-dotenv 와 같은 값이다.

    이 검사만 실제 .env 를 읽는다. 값은 비교만 하고 출력하지 않는다. 두 스크립트가
    쓰는 값이 Flask·Next 가 읽는 값과 갈리면 바인딩 주소가 서로 달라진다. 위의
    한계 검사가 보여 주듯 이 일치는 값의 모양에 달려 있으므로 실제 파일로 잰다.
    """
    from dotenv import dotenv_values

    env_path = _REPO_ROOT / ".env"
    if not env_path.exists():
        pytest.skip(".env 가 없는 환경")

    parsed = dotenv_values(env_path)
    for key in ("FLASK_PORT", "FRONTEND_PORT", "FLASK_HOST"):
        assert _env_value(_REPO_ROOT, key) == (parsed.get(key) or "")
```

- [ ] **Step 2: 검사가 실패하는 것을 확인한다**

Run: `source venv/bin/activate && pytest tests/scripts/test_env_value_sh.py -v`
Expected: 일곱 검사 모두 FAIL. `scripts/env_value.sh` 가 없어 `source` 가 실패한다.

- [ ] **Step 3: 두 함수를 만든다**

`scripts/env_value.sh` 를 새로 만든다.

```bash
#!/bin/bash
# .env 에서 값을 읽는다. 기동 스크립트 둘이 공유한다.
#
# `set -a; source .env` 를 대신한다. bash 는 `KEY=값` 대입의 오른쪽에서 명령 치환을
# 항상 평가하므로, 설정 화면으로 저장할 수 있는 값에 `$(...)` 를 심으면 다음 기동에서
# 임의 명령이 실행되었다([INFRA-049]). 공백 하나만으로도 뒤 토큰이 명령이 되는데 Google
# 앱 비밀번호에는 공백이 들어가므로 값의 모양으로는 막을 수 없다. 원인은 값이 아니라
# 데이터 파일을 셸이 코드로 실행하는 것이라서, 읽는 방식 자체를 바꾼다.
#
# export 는 하지 않는다. Flask 는 app/__init__.py 의 load_dotenv() 로, Next 는
# @next/env 로 각자 .env 를 읽으므로 셸이 미리 넣어 주던 값은 이미 중복이었다.
#
# tail -1 은 중복 줄에서 나중 것이 이기는 세 파서(bash·python-dotenv·@next/env)의
# 동작에 맞춘 것이다.
#
# 읽는 대상은 **현재 작업 디렉터리의** .env 다. 두 스크립트 모두 맨 앞에서
# `cd "$PROJECT_ROOT"` 를 하므로 맞지만, restart_all.sh 는 뒤에서 `cd frontend` 와
# `cd ..` 를 오간다. 호출을 그 아래로 옮기면 조용히 빈 값이 나오므로 옮기지 않는다.
#
# 키 이름은 sed 표현식 안에 그대로 들어간다. 호출자는 리터럴 키 세 개만 넘긴다.
#
# ponytail: 따옴표·인라인 주석·후행 공백을 벗기지 않고 `export KEY=값` 도 읽지 않는다.
# 지금 이 함수가 읽는 세 키가 그 모양이 아니라서 다른 파서와 값이 같을 뿐이다. dotenv 를
# 여기서 재구현하지 않는 이유는 따옴표 안의 `#` 에서 또 갈리기 때문이다. 세 키가 그
# 모양이 되는 것이 실제 문제가 되면 그때 파이썬으로 읽어 넘긴다.
env_value() {
  [ -f .env ] || return 0
  sed -n "s/^$1=//p" .env | tail -1
}

# 포트만 따로 받는다. 호출자가 `lsof -ti :$port` 처럼 인용 없이 쓰기 때문에, 값에 공백이
# 섞이면 단어 분리로 lsof 가 아무것도 찾지 못하고 stop_all.sh 가 포트를 죽이지 못한 채
# 「✅ Port freed」를 출력한다. 그 조용한 거짓 성공을 여기서 끊는다.
#
# ${!1} 은 호출자가 export 한 같은 이름의 값이다. 옛 `set -a; source .env` 는 .env 에
# 키가 없을 때 아무것도 덮어쓰지 않아 그 값이 살아남았으므로, 우선순위를 그대로 지킨다.
env_port() {
  local value
  value=$(env_value "$1")
  value=${value:-${!1}}
  value=${value:-$2}
  case $value in
    ''|*[!0-9]*)
      echo "❌ $1 의 값이 숫자가 아니다. .env 의 해당 줄을 확인하라" >&2
      return 1
      ;;
  esac
  printf '%s' "$value"
}
```

- [ ] **Step 4: 검사가 통과하는 것을 확인한다**

Run: `source venv/bin/activate && pytest tests/scripts/test_env_value_sh.py -v`
Expected: 7 passed (`.env` 가 없는 환경이면 6 passed 1 skipped)

- [ ] **Step 5: 검사가 결함을 실제로 잡는지 확인한다**

**저장소의 `scripts/env_value.sh` 를 고쳐서 하지 않는다.** 돌연변이 상태로 검사 파일
전체를 돌리면 `test_env_value_matches_dotenv_for_startup_keys` 가 `cwd=_REPO_ROOT` 에서
실행되어 **운영 `.env` 를 저장소 루트에서 셸 스크립트로 실행한다.** 그 파일에는 값 뒤에
토큰이 이어지는 줄이 21개 있다. 결함을 증명하려는 단계가 그 결함을 밟게 된다.

대신 스크래치패드에 사본 둘을 만들고 그것만 부른다.

1. `env_value` 본문을 `set -a; source .env; set +a; eval "echo \$$1"` 로 바꾼 사본을
   만들고, 임시 디렉터리의 `.env` 에 `SMTP_HOST=x$(touch pwned_subst)` 를 두어 `pwned_subst`
   가 실제로 만들어지는 것을 확인한다. 지금 구현으로는 만들어지지 않는다.
2. `env_port` 의 `case` 블록을 지운 사본을 만들고, `FLASK_PORT=5501 # 주석` 에 대해 종료
   코드 0 과 오염된 값이 나오는 것을 확인한다. 지금 구현은 1 을 돌려준다.

사본과 임시 `.env` 는 스크래치패드 안에서만 만들고 확인 뒤 지운다.

---

## Task 2: 두 기동 스크립트에서 `source .env` 를 걷어낸다

**Files:**
- Modify: `restart_all.sh:10-21`, `restart_all.sh:80`
- Modify: `stop_all.sh:12-24`
- Test: `tests/scripts/test_env_value_sh.py` (검사 하나 추가)
- Create: `docs/dev-cycle/qa/INFRA-049.md`

**Interfaces:**
- Consumes: Task 1 의 `env_value` 와 `env_port`. `source scripts/env_value.sh` 로 들여온다.
- Produces: 없음 (마지막 태스크)

- [ ] **Step 1: 회귀 검사를 먼저 쓴다**

`tests/scripts/test_env_value_sh.py` 끝에 더한다.

```python
def test_startup_scripts_do_not_source_env():
    """[INFRA-049] 기동 스크립트가 .env 를 셸로 실행하지 않는다.

    함수를 만들어 두어도 옛 줄이 남아 있으면 아무것도 달라지지 않는다. 되살아나는
    것을 막는 자리가 여기다. 부분 문자열 대신 정규식을 쓰는 이유는 `. .env` 와
    `source "$PROJECT_ROOT/.env"` 도 같은 일을 하기 때문이다. env_value.sh 자신도
    검사 대상에 넣는다. 그 파일의 주석이 옛 방식을 설명하면서 같은 문구를 담지만,
    정규식이 행 앞을 묶으므로 주석 줄에는 걸리지 않는다.
    """
    for name in ("restart_all.sh", "stop_all.sh", "scripts/env_value.sh"):
        text = (_REPO_ROOT / name).read_text(encoding="utf-8")
        assert not _SOURCES_ENV.search(text), f"{name} 이 .env 를 source 한다"
        assert not _EXPORTS_ALL.search(text), f"{name} 에 .env 를 export 하던 자리가 남아 있다"
```

- [ ] **Step 2: 검사가 실패하는 것을 확인한다**

Run: `source venv/bin/activate && pytest tests/scripts/test_env_value_sh.py::test_startup_scripts_do_not_source_env -v`
Expected: FAIL — `restart_all.sh 이 .env 를 source 한다`

- [ ] **Step 3: `restart_all.sh` 를 고친다**

10~11행

```bash
# .env 로드
[ -f .env ] && { echo "📄 .env loaded"; set -a; source .env; set +a; }
```

을 이렇게 바꾼다.

```bash
# .env 에서 이 스크립트가 쓰는 값만 읽는다. source 하지 않는 이유는
# scripts/env_value.sh 의 주석에 있다.
source "$PROJECT_ROOT/scripts/env_value.sh" || {
  echo "❌ scripts/env_value.sh 를 읽을 수 없다"; exit 1;
}
[ -f .env ] && echo "📄 .env found"
```

`|| { ... exit 1; }` 이 필요한 이유는 두 스크립트 어디에도 `set -e` 가 없기 때문이다.
파일이 없으면 `source` 가 stderr 한 줄만 흘리고 그대로 진행하며, `env_port` 는 정의되지
않은 명령이 되어 빈 값을 낸다. 그러면 `.env` 의 포트가 아니라 코드 기본값으로 조용히
동작한다.

20~21행

```bash
FRONTEND_PORT=${FRONTEND_PORT:-3500}
FLASK_PORT=${FLASK_PORT:-5501}
```

을 이렇게 바꾼다.

```bash
FRONTEND_PORT=$(env_port FRONTEND_PORT 3500) || exit 1
FLASK_PORT=$(env_port FLASK_PORT 5501) || exit 1
_env_flask_host=$(env_value FLASK_HOST)
FLASK_HOST=${_env_flask_host:-$FLASK_HOST}
```

`FLASK_HOST` 를 두 줄로 받는 이유는 상속 우선순위를 지키기 위해서다. 81행의
`${FLASK_HOST:-127.0.0.1}` 은 그대로 두고 최종 폴백으로 남긴다. 그 자리는 `--bind` 인자
전체가 인용되어 있어 단어 분리가 일어나지 않고, 값이 이상하면 gunicorn 이 기동에 실패해
`logs/backend.log` 에 남는다. 80행 주석의 「11행에서 source 한 .env」를 바뀐 방식에 맞춰
고친다.

- [ ] **Step 4: `stop_all.sh` 를 고친다**

12~20행

```bash
# ==== .env 로드 ====
if [ -f .env ]; then
  echo "📄 Loading .env configuration..."
  set -a
  source .env
  set +a
else
  echo "⚠️  .env file not found! (using defaults)"
fi
```

을 이렇게 바꾼다.

```bash
# ==== .env 에서 포트만 읽기 ====
# source 하지 않는 이유는 scripts/env_value.sh 의 주석에 있다.
source "$PROJECT_ROOT/scripts/env_value.sh" || {
  echo "❌ scripts/env_value.sh 를 읽을 수 없다"; exit 1;
}
if [ -f .env ]; then
  echo "📄 Reading ports from .env..."
else
  echo "⚠️  .env file not found! (using defaults)"
fi
```

22~24행

```bash
# ==== 포트 기본값 ====
FRONTEND_PORT=${FRONTEND_PORT:-3500}
FLASK_PORT=${FLASK_PORT:-5501}
```

을 이렇게 바꾼다.

```bash
# ==== 포트 결정 ====
# 숫자가 아니면 여기서 멈춘다. 이유는 scripts/env_value.sh 의 env_port 주석에 있다.
FRONTEND_PORT=$(env_port FRONTEND_PORT 3500) || exit 1
FLASK_PORT=$(env_port FLASK_PORT 5501) || exit 1
```

- [ ] **Step 5: 회귀 검사와 전체 검사가 통과하는 것을 확인한다**

Run: `source venv/bin/activate && pytest tests/scripts/test_env_value_sh.py -v`
Expected: 8 passed (`.env` 가 없는 환경이면 7 passed 1 skipped)

Run: `source venv/bin/activate && pytest`
Expected: 기존 1799 통과·2 skip 에 새 검사 8 이 더해진다. 실패 0.

- [ ] **Step 6: 두 스크립트의 문법을 확인한다**

Run: `bash -n restart_all.sh && bash -n stop_all.sh && bash -n scripts/env_value.sh && echo OK`
Expected: `OK` (종료 코드 0)

- [ ] **Step 7: 값이 실제로 같은지 대조한다**

돌고 있는 서비스를 건드리지 않고 값만 읽는다.

```bash
source scripts/env_value.sh
for k in FLASK_PORT FRONTEND_PORT FLASK_HOST; do
  new=$(env_value "$k")
  old=$(bash -c 'set -a; source ./.env; set +a; printf "%s" "${'"$k"'}"')
  [ "$new" = "$old" ] && echo "$k: 같음" || echo "$k: 다름"
done
```

Expected: 세 줄 모두 `같음`. 값은 출력하지 않는다.

- [ ] **Step 8: Flask 를 export 없는 환경에서 실제로 띄운다**

`TODO.md` 의 「확인할 것 하나」가 요구하는 실측이다. 돌고 있는 gunicorn(5501)은 건드리지
않고 임시 포트 5599 에 따로 띄운다. `env -i` 에 가까운 환경으로 띄워, `.env` 의 값이 셸
export 가 아니라 `load_dotenv()` 로만 들어오는 상황을 만든다.

**`NOTIFICATION_ENABLED=false` 를 빠뜨리지 않는다.** 운영 `.env` 의 값은 `true` 이고
디스코드·텔레그램·SMTP 자격 증명이 실제 값이다.

```bash
source venv/bin/activate
env -i PATH="$PATH" HOME="$HOME" LANG="${LANG:-en_US.UTF-8}" \
    SCHEDULER_ENABLED=false NOTIFICATION_ENABLED=false \
    "$VIRTUAL_ENV/bin/gunicorn" flask_app:app \
    --bind 127.0.0.1:5599 --workers 1 --threads 2 --timeout 120 \
    > /tmp/infra049-backend.log 2>&1 &
echo "임시 gunicorn PID: $!"
```

기동을 기다린 뒤 확인한다.

```bash
curl -s -o /dev/null -w "%{http_code}\n" --max-time 10 http://127.0.0.1:5599/health
```

Expected: `200`. 그리고 `/tmp/infra049-backend.log` 에 `.env` 값을 못 읽어 생기는 오류가
없어야 한다. 확인이 끝나면 **기억해 둔 PID 만** `kill` 한다. `pkill -f gunicorn` 은 돌고
있는 5501 까지 죽이므로 쓰지 않는다.

- [ ] **Step 9: Next 가 export 없이 값을 얻는지 확인한다**

`next dev` 를 하나 더 띄우면 돌고 있는 next-server 와 `frontend/.next` 를 공유해 서로를
깨뜨린다. 그래서 전체 기동 대신 Next 가 실제로 쓰는 로더를 같은 조건으로 부른다.
`tier-rules.md` §1-1 의 「화면이 없는 경로는 안전한 하네스를 검사 대상으로 삼고 그 사실을
적는다」에 해당하며, QA 문서에 대체 사실을 적는다.

```bash
env -i PATH="$PATH" HOME="$HOME" node -e '
const FE = process.argv[1];
const { loadEnvConfig } = require(FE + "/node_modules/@next/env");
loadEnvConfig(FE, true, { info: () => {}, error: () => {} });
const need = ["FLASK_PORT", "FRONTEND_PORT", "NEXTAUTH_SECRET", "ADMIN_API_TOKEN", "INTERNAL_IDENTITY_SECRET"];
for (const k of need) console.log(k + ": " + (process.env[k] === undefined ? "없음" : "채워짐"));
' "$PWD/frontend"
```

Expected: 다섯 줄 모두 `채워짐`. 값은 출력하지 않는다.

- [ ] **Step 10: QA 시나리오 문서를 만든다**

`docs/dev-cycle/qa/INFRA-049.md` 를 `archive-format.md` §8 형식으로 만든다. 회귀
시나리오는 `TODO.md` 의 「값에 `$(...)` 를 넣어 저장한 뒤 `.env` 를 읽어도 명령이 실행되지
않는다」에서 출발하고, Step 8·9 의 기동 확인과 Step 7 의 값 대조를 시나리오로 옮긴다.
설정 화면의 「저장」은 운영 `.env` 를 다시 쓰므로 누르지 않고, 하네스를 대상으로 삼은
사실을 문서에 적는다.

- [ ] **Step 11: 커밋한다**

`SKILL.md` [3] 검증 5번의 첫 커밋이다. TODO 항목 자체는 남긴다.

```bash
git add scripts/env_value.sh restart_all.sh stop_all.sh \
        tests/scripts/test_env_value_sh.py \
        docs/dev-cycle/qa/INFRA-049.md docs/dev-cycle/TODO.md \
        docs/superpowers/plans/2026-09-08-infra-049-env-source-removal.md
git diff --cached --check
git commit -m "fix(infra): [INFRA-049] .env 를 셸이 실행하지 않게 한다"
```

---

## 이 계획이 하지 않는 것

- **`env_value` 에서 따옴표와 인라인 주석을 벗기지 않는다.** dotenv 를 어설프게
  재구현하는 길이고 따옴표 안의 `#` 에서 또 갈린다. 대신 한계를 주석과 검사로 못 박고,
  실제 사고로 이어지는 포트만 `env_port` 로 막는다.
- **`FLASK_HOST` 에는 형식 검사를 넣지 않는다.** `--bind` 인자 전체가 인용되어 있어 단어
  분리가 일어나지 않고, 값이 이상하면 gunicorn 이 기동에 실패해 로그에 남는다. 포트와
  달리 조용한 실패 경로가 없다.
- **임포트 순서 추적을 영구 검사로 만들지 않는다.** 무겁고 잘 깨지며, 한 번 확인하면 되는
  성질의 사실이다. Step 8·9 의 명령과 출력을 QA 문서에 증거로 남기는 것으로 갈음한다.
- **`.env` 파일을 고치지 않는다.** 읽는 쪽만 바꾼다.
- **`services/common_env_service.py` 를 건드리지 않는다.** `[INFRA-044]` 가 넣은 값 필터는
  설정 화면을 지나는 값만 보므로 이 항목과 겹치지 않는다. 그 필터를 넓히는 일은 이미
  `[INFRA-051]` 과 `[INFRA-050]` 이 맡고 있다.
- **`restart_all.sh:36` 의 `pkill -f "flask_app.py" "next dev" "npm.*dev"` 를 고치지 않는다.**
  `pkill` 은 패턴을 둘 이상 받으면 사용법 오류를 내고 **아무것도 죽이지 않는다.**
  `|| true` 가 그것을 삼키므로 이 줄은 통째로 무동작이며, 지금 프로세스 정리는 35행의
  `kill_port` 만 하고 있다. 범위 밖이므로 별도 TODO 로 이월하되 이월 문구에 이 사실을
  적는다.
- **CRLF 는 이 변경의 회귀가 아니다.** `KEY=5501\r` 에서 `sed` 와 `bash source` 가 둘 다
  `\r` 를 남기고 python-dotenv 만 벗기므로, 이미 있던 차이다.
