# [INFRA-050] `.env` 쓰기 직렬화 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `update_env_file` 이 `.env` 를 원자적으로 교체하고, 겹치는 저장 요청을 파일
잠금으로 직렬화하여 부분 기록과 갱신 소실을 함께 없앤다.

**Architecture:** `services/common_env_service.py` 에 `fcntl.flock` 기반 컨텍스트 매니저
`_env_file_lock` 을 두고, `update_env_file` 의 읽기-수정-쓰기 한 벌을 그 안에서 수행한다.
`open(env_path, "w")` 직접 쓰기를 저장소가 이미 갖고 있는 `atomic_write_text` 로 바꾼다.
`os.environ` 갱신은 파일 저장이 성공한 뒤로 옮긴다.

**Tech Stack:** Python 3.11, `fcntl`(stdlib), `contextlib.contextmanager`(stdlib),
기존 `services.kr_market_data_cache_core.atomic_write_text`, pytest

**Spec:** 이 항목은 bounded 로 분류되어 별도 설계 문서를 두지 않는다. 근거와 완료
조건은 `docs/dev-cycle/TODO.md` 의 `[INFRA-050]` 절에 있고, 그 절이 이 계획의 사양이다.
설계는 2026-09-08 대화에서 승인받았고, 아래 「사양의 정정」이 그 절에서 고쳐야 할
부분을 짚는다.

## Global Constraints

- 티어는 **T3** 이다. `tier-rules.md` §2 「시크릿과 인증」이 「`.env` 로 시작하는 모든
  파일」을 접촉 패턴으로 정하므로 줄 수와 무관하다.
- 운영 `.env`, `.env.production`, `.env.vertex` 에 쓰지 않는다. 검증은 전부 `tmp_path`
  또는 스크래치패드에서 수행한다.
- `.env` 값을 출력하지 않는다. 키 이름과 값의 유무·길이까지만 다룬다.
- 사용자가 기동해 둔 5501 gunicorn 과 3500 next-server 를 재기동하지 않는다.
  `./restart_all.sh` 와 `./stop_all.sh` 를 실행하지 않는다.
- 임시로 띄우는 프로세스에는 `SCHEDULER_ENABLED=false` 와 `NOTIFICATION_ENABLED=false`
  를 함께 넘긴다. 운영 `.env` 의 `NOTIFICATION_ENABLED` 는 `true` 이고 디스코드 웹훅과
  텔레그램 토큰이 실제 값이다.
- 루트 `package.json` 은 추적하지 않고 그대로 둔다. 다른 작업의 파일을
  스테이징·삭제·스태시하지 않는다.
- 커밋 메시지 끝에 아래 두 줄을 붙인다.

  ```
  Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01AeQQtEk7wbuVAnf9kCJmBN
  ```

---

## 사양의 정정 — 경합의 실제 주체

TODO 의 `[INFRA-050]` 절은 경합의 주체를 「`update_env_file` 과
`persist_market_gate_interval_to_env`」로 적고, Codex 가 모형 실행으로 재현한 시퀀스를
확정 사실로 담았다. **그 시퀀스는 현재 배포에서 일어날 수 없다.** 두 함수가 서로 다른
파일을 보기 때문이다.

- `resolve_env_path()` → `<루트>/.env` (`services/common_env_service.py:69-71`)
- `project_env_path(kr_market.__file__)` → `<루트>/app/.env`
  (`services/kr_market_interval_service.py:14-20`)

`app/routes/kr_market.py:101` 이 자기 `__file__` 을 넘기는데 그 파일은 `app/routes/`
아래에 있어 `dirname` 두 번이 `app/` 에서 멈춘다. `app/.env` 는 존재하지 않으므로
`persist_market_gate_interval_to_env` 는 첫 줄의 존재 검사에서 조용히 반환한다.
`45ad2a6 refactor: complete modular split` 에서 들어온 계산이며, 함수의 docstring 은
「프로젝트 루트 .env 파일 경로를 반환한다」라고 적혀 있어 의도와 어긋난다. 계획 검토가
독립적으로 같은 결론에 도달했다.

TODO 에서 고칠 문장은 둘이다. ① Codex 의 소실 시퀀스는 두 함수에 같은 경로를 직접
넘긴 모형이며 배선을 건너뛰었다. ② 「`POST /api/kr/config/interval` 이 인증 없이 호출
가능하므로 임의 시점에 경합을 유발할 수 있다」는 문장은 근거를 잃었다. 그 엔드포인트는
지금 `.env` 를 만지지 않는다.

**그래도 이 항목은 유효하다. 경합의 주체가 다를 뿐이고, 실제 위험은 오히려 더 나쁘다.**

### 실재하는 경합과 그 결과

화면이 `POST /api/system/env` 를 내는 자리를 둘 갖고 있다.
`frontend/src/app/components/SettingsModal.tsx:167` 의 「저장」 버튼은 `envVars` 전체를
보내고, `:279` 의 알림 테스트는 발송 직전에 `pickNotificationEnv(envVars)` 를 따로
보낸다. gunicorn 이 `--workers 2 --threads 8` 로 뜨므로 둘은 동시에 처리된다.

**위험 1 — 부분 기록과 꼬리 잔존 (원자적 교체가 닫는다).** `open(env_path, "w")` 는
여는 시점에 잘라내고 닫는 시점에는 잘라내지 않는다. 두 요청이 각각 열면 서로 다른
기술자가 **각자 offset 0 에서** 쓴다. 나중에 쓴 쪽이 더 짧으면 먼저 쓴 쪽의 꼬리가
그대로 남는다. 순서 조작 없이 재현한 결과다.

```
SMTP_HOST=bb
aaaaaaaaaaaaaaaaa
ADMIN_API_TOKEN=must-survive
```

두 번째 줄은 긴 쪽이 쓴 값의 꼬리이며 키가 없다. `update_env_file` 의 파서는
`"=" not in line_stripped` 인 줄을 그대로 보존하므로(`services/common_env_service.py:137-139`)
이 쓰레기가 영구히 남는다. 꼬리가 줄 중간에 떨어지면 값 자체가 잘린 채 오염되고, 그
자리가 `ADMIN_API_TOKEN` 이나 `ADMIN_EMAILS` 줄이면 TODO 가 적은 fail-closed 결과에
그대로 도달한다. **저장 요청 두 번이면 충분하고 두 경로가 필요하지 않다.**

**위험 2 — 갱신 소실 (잠금이 닫는다).** 원자적 교체만 넣으면 부분 기록은 사라지지만,
옛 내용을 읽은 쪽이 나중에 교체하면 그 사이의 갱신을 통째로 되돌린다. 잃는 것이 자기
키 하나가 아니다. `update_env_file` 은 읽은 내용 전체를 다시 쓰기 때문이다. 두 요청
모두 성공을 반환하므로 화면에서는 아무것도 보이지 않는다. 쓰기 직전에 0.3 초를 넣어
창을 넓히고 두 호출을 0.05 초 간격으로 띄워 재현했다.

심각도가 서로 다르므로 계획도 둘을 나눠 적는다. 원자적 교체가 가용성이 무너지는 쪽을
닫고, 잠금은 그보다 조용한 소실을 닫는다. 두 변경 모두 이 항목 안에서 한다.

### 범위에서 뺀 것

**경로 버그는 이번에 고치지 않는다.** 사용자 승인과 계획 검토가 같은 결론이다.

고치면 인증이 없는 `POST /api/kr/config/interval` 이 운영 `.env` 를 실제로 쓰게 된다.
값 자체는 1~1440 으로 검증된 정수라 주입 위험은 없지만 문제는 쓰기 행위 자체다. 매
호출이 `.env` 전체를 읽고 임시 파일을 만들어 교체한다. 잠금을 넣은 뒤라면 **인증 없는
호출자가 `.env` 잠금을 계속 점유해 관리자 저장을 지연시키는 통로**가 새로 생긴다. 지금은
그 쓰기가 우연히 무동작이라 이 통로가 없다. 우연한 안전에 기대는 상태가 좋다는 뜻은
아니지만, 순서는 분명하다. `[INFRA-042]` 가 게이트를 세운 뒤에 경로를 고쳐야 한다.

**`persist_market_gate_interval_to_env` 에 잠금을 두르는 일도 하지 않는다.** 경로를
고치지 않는 한 배타할 상대가 없다. 그리고 대가가 있다. 존재 검사를 잠금 안으로 옮기면
지금은 아무 흔적도 남기지 않는 이 엔드포인트가 호출될 때마다 `app/.env.lock` 을 만든다.
`.gitignore:23` 의 `.env.*` 가 하위 디렉터리에서도 걸려 작업 트리는 더러워지지 않지만,
인증 없는 경로가 새로 만드는 관찰 가능한 부수 효과라는 점은 남는다. 얻는 것이 없는
자리에 그 대가를 치를 이유가 없다.

후속 항목이 셋을 함께 처리한다. ① `project_env_path` 를 지우고 `resolve_env_path` 를
재사용해 경로 계산을 한 곳으로 모은다. 두 곳에서 따로 계산하는 구조가 이 결함의
원인이므로 합치면 재발이 구조적으로 막힌다. ② 그때
`persist_market_gate_interval_to_env` 를 `_env_file_lock` 에 넣는다. ③ **주기 값이 실제로
`.env` 에 기록되기 시작한다는 동작 변경**을 명시한다. 지금까지 재기동마다 사라지던 값이
남게 되므로 운영자가 인지하지 못한 채 주기가 고정될 수 있다.

---

## 사전 실측 (이 계획이 근거로 삼는 사실)

구현 전에 이미 확인한 것이며 다시 재지 않아도 된다.

1. `fcntl.flock` 은 이 플랫폼(darwin 25.5.0)에서 동작하고, **같은 프로세스 안의 서로
   다른 파일 기술자 사이에서도 배타적이다.** 스레드 셋으로 `in`/`out` 순서를 찍어
   겹침이 없음을 확인했다. `fcntl.lockf` 는 프로세스 단위라 같은 성질이 없으므로
   스레드로 재현하는 검사를 쓸 수 없다. 그래서 `flock` 을 고른다.
2. `os.close(fd)` 는 그 기술자가 들고 있던 `flock` 을 놓는다. 별도의 `LOCK_UN` 이
   필요하지 않다.
3. `atomic_write_text` 의 기본 인자 `invalidate_fn=invalidate_file_cache` 는 `.env` 에
   대해 존재하지 않는 캐시 키를 지울 뿐이라 무해하다
   (`services/kr_market_data_cache_core.py:116-143`).
4. 순환 import 가 생기지 않는다. `common_env_service` 를 import 하는 것은
   `app/routes/common_update_routes.py` 하나이고, `kr_market_data_cache_core` 는
   `services.file_row_count_cache` → `services.sqlite_utils` 와
   `services.kr_market_data_cache_sqlite_payload`, 그리고 `pandas` 를 끌어온다. 어느
   것도 `common_env_service` 를 참조하지 않는다. **다만 지금까지 표준 라이브러리만
   쓰던 이 모듈에 모듈 수준으로 pandas 와 sqlite3 가 붙는다.** 함수 안에서 지연
   import 하면 그것을 피할 수 있으나 monkeypatch 대상이 사라져 경합 검사를 쓸 수 없게
   된다. 이 모듈을 쓰는 곳이 Flask 라우트 하나뿐이고 그 프로세스는 이미 둘 다 로드하고
   있으므로, 모듈 수준 import 를 택한다.
5. 루트 `.env` 는 일반 파일이며 모드는 0600 이다(`[INFRA-053]` 결과).
   `restart_all.sh:21` 이 만드는 심볼릭 링크는 `frontend/.env` → `../.env` 이므로
   **가리키는 쪽**이고, 루트 `.env` 의 inode 가 바뀌어도 경로를 따라간다.
6. `.gitignore:23` 의 `.env.*` 가 `.env.lock` 을 이미 덮는다. 예외는 `.env.example`
   하나뿐이므로 잠금 파일이 작업 트리에 나타나지 않는다.
7. `os.open(path, O_CREAT | O_RDWR)` 는 심볼릭 링크를 따라가 대상 파일을 연다(실측:
   링크와 대상의 inode 가 같았다). `O_NOFOLLOW` 를 더하면 링크일 때 `ELOOP`(errno 62)
   로 거부하고 일반 파일에서는 그대로 열린다.
8. 저장소에 `persist_market_gate_interval_to_env` 를 실제로 부르는 검사가 없다.
   `tests/services/test_kr_market_interval_http_service.py` 는 `persist_interval_fn` 에
   람다만 넘기고(`:18`, `:38`, `:51`, `:58`),
   `tests/app/test_kr_market_route_integration.py:483` 은 무동작으로 대체한다. 그래서
   그 경로를 이번 범위에서 빼도 잃는 검사가 없다.

---

### Task 1: 잠금과 원자적 교체를 `update_env_file` 에 넣는다

**Files:**
- Modify: `services/common_env_service.py:9-13`(import), `:104-` (`update_env_file`)
- Test: `tests/app/test_common_env_service.py`

**Interfaces:**
- Consumes: `services.kr_market_data_cache_core.atomic_write_text(file_path, content, *, invalidate_fn=...)`
- Produces: `_env_file_lock(env_path: str) -> ContextManager[None]` — 후속 항목이
  `persist_market_gate_interval_to_env` 에서 import 한다.
  `update_env_file(env_path, data, environ) -> None` 의 서명은 바뀌지 않는다.

- [ ] **Step 1: 실패하는 검사를 쓴다 — 저장 둘이 겹쳐도 결과가 온전하다**

`tests/app/test_common_env_service.py` 의 맨 끝에 붙인다. 파일 상단의 import 에
`import threading`, `import time`, `import pytest`, `from services import common_env_service`
를 더한다.

```python
def test_concurrent_env_saves_keep_both_updates_and_leave_no_debris(
    tmp_path: Path, monkeypatch
):
    """저장 요청 둘이 겹쳐도 두 갱신이 모두 남고 쓰레기 줄이 생기지 않는다.

    화면이 이 경합을 유발하는 자리를 둘 갖고 있다. SettingsModal.tsx:167 의 「저장」
    버튼은 envVars 전체를 보내고, :279 의 알림 테스트는 발송 직전에 알림 키만 따로
    보낸다. gunicorn 이 --workers 2 --threads 8 로 뜨므로 둘은 동시에 처리된다.

    두 가지를 함께 잰다([INFRA-050]).

    하나는 갱신 소실이다. update_env_file 은 읽은 내용 전체를 다시 쓰므로, 나중에
    쓰는 쪽이 그 사이 다른 요청이 넣은 값을 통째로 되돌린다. 두 요청 모두 성공을
    반환하므로 화면에서는 아무것도 보이지 않는다. 잠금이 이것을 닫는다.

    다른 하나는 꼬리 잔존이다. open(w) 는 여는 시점에 잘라내고 닫는 시점에는 잘라내지
    않으므로, 두 기술자가 각자 offset 0 에서 쓰면 짧은 쪽 뒤에 긴 쪽의 꼬리가 남는다.
    그 꼬리는 키가 없는 줄이 되고, 이 파일의 파서는 = 없는 줄을 그대로 보존하므로
    영구히 남는다. 원자적 교체가 이것을 닫는다.

    지연을 읽기와 쓰기 사이에 넣어 경합 창을 강제로 넓힌다. 잠금이 없으면 나중에 뜬
    쪽이 앞선 쪽의 지연 중에 옛 내용을 읽어 소실이 확정된다.
    """
    env_path = tmp_path / ".env"
    env_path.write_text(
        "SMTP_HOST=old\nDISCORD_WEBHOOK_URL=old-hook\n",
        encoding="utf-8",
    )

    real_write = common_env_service.atomic_write_text

    def slow_write(file_path, content, **kwargs):
        time.sleep(0.3)
        real_write(file_path, content, **kwargs)

    monkeypatch.setattr(common_env_service, "atomic_write_text", slow_write)

    errors: list[Exception] = []

    def save(payload: dict[str, str]):
        try:
            update_env_file(str(env_path), payload, {})
        except Exception as error:  # noqa: BLE001 - 스레드 밖으로 옮겨 보고한다
            errors.append(error)

    # 길이를 일부러 다르게 준다. 두 쓰기의 길이가 같으면 꼬리가 남지 않아 위험 하나가
    # 검사에서 빠진다.
    save_button = threading.Thread(
        target=save, args=({"SMTP_HOST": "smtp.a-very-long-host.example.com"},)
    )
    test_button = threading.Thread(target=save, args=({"DISCORD_WEBHOOK_URL": "h"},))
    save_button.start()
    # 먼저 뜬 쪽이 읽기를 마치고 지연에 들어갈 시간만 준다. tmp 파일 읽기는 마이크로초
    # 단위라 이 값으로 충분하고, 지연 0.3 초보다 훨씬 짧아 경합 창 안에 들어간다.
    time.sleep(0.05)
    test_button.start()
    save_button.join()
    test_button.join()

    assert not errors
    content = env_path.read_text(encoding="utf-8")
    # 잠금이 없으면 이 둘 가운데 하나가 실패한다. 나중에 시작한 쪽이 옛 내용을 읽어
    # 덮기 때문이다.
    assert "SMTP_HOST=smtp.a-very-long-host.example.com" in content
    assert "DISCORD_WEBHOOK_URL=h" in content
    # 원자적 교체가 없으면 여기서 키 없는 꼬리 줄이 잡힌다.
    for line in content.splitlines():
        assert "=" in line, f"키 없는 줄이 남았다: {line!r}"
```

- [ ] **Step 2: 검사가 실패하는 것을 확인한다**

```bash
./venv/bin/python -m pytest tests/app/test_common_env_service.py::test_concurrent_env_saves_keep_both_updates_and_leave_no_debris -v
```

기대: FAIL. 지금은 `common_env_service` 에 `atomic_write_text` 속성이 없으므로
`monkeypatch.setattr` 이 `AttributeError` 를 낸다. **이 실패 형태는 결함이 아니라
부재를 가리키므로 증거로 충분하지 않다.** 구현을 넣은 뒤 Step 5 의 돌연변이 둘로
「잠금이 없으면 소실」과 「원자적 교체가 없으면 꼬리」를 각각 확인한다.

- [ ] **Step 3: 잠금 컨텍스트 매니저와 원자적 교체를 넣는다**

`services/common_env_service.py` 의 import 블록을 바꾼다.

```python
import fcntl
import os
import re
from contextlib import contextmanager
from typing import Any, Iterator

from services.kr_market_data_cache_core import atomic_write_text
```

`EDITABLE_ENV_KEYS` 정의 앞, import 블록 바로 뒤에 잠금을 둔다.

```python
@contextmanager
def _env_file_lock(env_path: str) -> Iterator[None]:
    """`.env` 의 읽기-수정-쓰기 한 벌을 프로세스 사이에서 직렬화한다.

    설정 화면이 이 파일에 저장 요청을 내는 자리가 둘이다. SettingsModal.tsx:167 의
    「저장」 버튼과 :279 의 알림 테스트가 각각 POST /api/system/env 를 보내며, gunicorn
    이 워커 둘에 스레드 여덟로 뜨므로 동시에 처리된다. 이 함수는 읽은 내용 전체를 다시
    쓰기 때문에, 옛 내용을 읽은 쪽이 나중에 쓰면 그 사이의 갱신이 자기 키 하나가 아니라
    통째로 되돌아간다. 두 요청 모두 성공을 반환하므로 화면에서는 보이지 않는다
    ([INFRA-050]).

    gunicorn 이 워커를 둘 이상 띄우므로 threading.Lock 은 통하지 않는다. fcntl.flock 은
    파일 기술자 단위라 워커 사이에서 배타적이고, 같은 프로세스 안의 서로 다른 기술자
    사이에서도 배타적이라 스레드로 재현하는 검사를 쓸 수 있다. fcntl.lockf 는 프로세스
    단위라 후자의 성질이 없다.

    잠금을 .env 자체가 아니라 별도 파일에 거는 이유는 os.replace 가 inode 를 갈아
    끼우기 때문이다. .env 에 걸면 교체 순간 잠금이 경로에서 분리된 옛 inode 에 남아,
    다음 주체가 새 inode 를 열어 거는 잠금과 서로 배타되지 않는다. 잠금 파일은
    .gitignore 의 `.env.*` 에 이미 걸리므로 작업 트리에 나타나지 않는다.

    **재진입이 불가능하다.** 진입할 때마다 새 os.open 을 하므로 같은 스레드에서
    중첩하면 flock(LOCK_EX) 이 자기 자신을 기다려 워커가 gunicorn 의 --timeout 120
    까지 멈춘다. 지금 중첩하는 호출자는 없지만, 다른 .env 쓰기 경로를 이 함수에
    위임하는 식으로 고치면 곧바로 여기에 걸린다. 위임하는 쪽이 아니라 감싸는 쪽 한
    자리에서만 이 잠금을 잡아야 한다.

    os.close 가 그 기술자의 잠금을 놓으므로 LOCK_UN 을 따로 부르지 않는다. 프로세스가
    죽어도 커널이 놓기 때문에 잠금이 영구히 남지 않는다. 그래서 대기에 상한을 두지
    않는다. 상한을 넘겼을 때의 처리 분기가 늘어나는 대가에 비해 막는 것이 없다.

    O_NOFOLLOW 를 붙이는 이유는 이 파일이 새 표면이기 때문이다. os.replace 가 .env 의
    링크 교체를 닫았으므로 남는 자리가 잠금 파일이고, 부모 디렉터리에 쓸 수 있는 주체가
    이것을 자기가 이미 잠근 파일의 링크로 바꾸면 저장이 영원히 대기한다. 상한을 두지
    않기로 했으므로 그 대기는 gunicorn 의 --timeout 120 까지 간다. 정상 배포에서 이
    파일은 언제나 일반 파일이라 이 플래그가 막는 것이 없고, 링크였다면 ELOOP 로 저장이
    실패한다. 조용히 엉뚱한 파일을 잠그는 것보다 낫다.
    """
    lock_path = f"{env_path}.lock"
    os.makedirs(os.path.dirname(lock_path) or ".", exist_ok=True)
    lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(lock_fd)
```

`update_env_file` 의 두 이른 반환 뒤부터 함수 끝까지를 아래로 바꾼다. 루프 본문의
판정 규칙은 그대로 두고, `environ` 을 직접 건드리던 두 자리만 모으기로 바꾼다.

```python
    with _env_file_lock(env_path):
        lines: list[str] = []
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as file:
                lines = file.readlines()

        updated_keys: set[str] = set()
        new_lines: list[str] = []
        # environ 을 루프 안에서 바로 고치면 저장이 실패했을 때 그 워커의 메모리와
        # 디스크가 갈린다. 반영할 것을 모아 두었다가 저장이 성공한 뒤에 옮긴다.
        applied: dict[str, str] = {}
        removed: list[str] = []

        for original_line in lines:
            line_stripped = original_line.strip()
            if not line_stripped or line_stripped.startswith("#"):
                new_lines.append(original_line)
                continue

            if "=" not in line_stripped:
                new_lines.append(original_line)
                continue

            key = line_stripped.split("=", 1)[0]
            if key not in data:
                new_lines.append(original_line)
                continue

            new_value = str(data.get(key, ""))
            updated_keys.add(key)

            if "*" in new_value:
                # 마스킹 값은 사용자 입력이 아닌 조회 결과일 수 있어 기존 값 유지
                new_lines.append(original_line)
                continue

            if not new_value:
                removed.append(key)
                continue

            new_lines.append(f"{key}={new_value}\n")
            applied[key] = new_value

        for key, raw_value in data.items():
            if key in updated_keys:
                continue
            value = str(raw_value)
            if "*" in value or not value:
                continue
            if new_lines and not new_lines[-1].endswith("\n"):
                new_lines[-1] += "\n"
            new_lines.append(f"{key}={value}\n")
            applied[key] = value

        # open(w) 를 직접 쓰던 자리다. 그 방식은 여는 시점에만 잘라내므로, 저장 둘이
        # 겹치면 짧은 쪽이 쓴 뒤에 긴 쪽의 꼬리가 남았다. 그 꼬리는 키 없는 줄이 되고
        # 위 파서가 = 없는 줄을 그대로 보존하므로 영구히 남는다. 줄 중간에 떨어지면
        # 값 자체가 잘린 채 오염된다.
        #
        # [INFRA-053] 이 이 자리에 넣은 os.fchmod 도 여기서 사라진다.
        # atomic_write_text 는 NamedTemporaryFile(0600) 에 쓰고 os.replace 로 옮기므로
        # 모드가 처음부터 좁고, 잘라낸 뒤 실패해 .env 가 빈 채로 남는 창도 없다.
        #
        # os.replace 는 심볼릭 링크를 따라가지 않고 링크 항목 자체를 갈아 끼운다.
        # open(w) 는 따라가서 대상을 잘랐으므로, 부모 디렉터리에 쓸 수 있는 주체가
        # 읽기와 쓰기 사이에 .env 를 다른 파일의 링크로 바꾸면 그 대상이 이 내용으로
        # 덮였다. 그 경로도 함께 닫힌다.
        atomic_write_text(env_path, "".join(new_lines))

    # 잠금 밖에서 옮긴다. environ 은 이 워커의 메모리이고 다른 워커와 공유되지 않으므로
    # 잠금이 지킬 대상이 아니다.
    for key in removed:
        environ.pop(key, None)
    environ.update(applied)
```

- [ ] **Step 4: 파일 전체 검사를 돌린다**

```bash
./venv/bin/python -m pytest tests/app/test_common_env_service.py -v
```

기대: `test_update_env_file_narrows_mode_before_writing` 만 FAIL(그 검사가 재던
`os.fchmod` 호출이 사라졌다), 나머지는 전부 PASS. Step 6 에서 그 검사를 정리한다.

- [ ] **Step 5: 돌연변이 둘로 새 검사의 실효를 확인한다**

**Step 6 을 먼저 수행한 뒤 이 단계를 돌린다.** 무효해진
`test_update_env_file_narrows_mode_before_writing` 이 남아 있으면 두 돌연변이 모두에서
그 검사가 함께 실패해, 돌연변이가 잡은 것인지 무효 검사가 남은 것인지 구분되지 않는다.

저장소 파일을 고치지 않는다. 스크래치패드에 사본을 만들어 확인한다. 두 변경이 각각
다른 위험을 닫으므로 돌연변이도 둘이다.

```bash
SCRATCH="/private/tmp/claude-501/-Users-freelife-vibe-lecture-hodu-closing-bet-demo/cc259cb9-6ff8-45cb-9bc1-2de7ba649d83/scratchpad/mut-050"
REPO="/Users/freelife/vibe/lecture/hodu/closing-bet-demo"

run_mutation() {
  rm -rf "$SCRATCH" && mkdir -p "$SCRATCH"
  cp -R "$REPO/services" "$REPO/tests" "$SCRATCH"/
  "$REPO/venv/bin/python" - "$SCRATCH" "$1" <<'PY'
import sys
path = f"{sys.argv[1]}/services/common_env_service.py"
source = open(path, encoding="utf-8").read()
if sys.argv[2] == "no-lock":
    # 잠금을 무동작으로 바꾼다 → 갱신 소실이 되살아난다
    source = source.replace(
        '    lock_path = f"{env_path}.lock"',
        '    yield\n    return\n    lock_path = f"{env_path}.lock"',
    )
else:
    # 원자적 교체를 open(w) 로 되돌린다 → 꼬리 잔존이 되살아난다
    source = source.replace(
        '        atomic_write_text(env_path, "".join(new_lines))',
        '        with open(env_path, "w", encoding="utf-8") as handle:\n'
        '            handle.writelines(new_lines)',
    )
open(path, "w", encoding="utf-8").write(source)
PY
  (cd "$SCRATCH" && PYTHONPATH="$SCRATCH" "$REPO/venv/bin/python" -m pytest \
      tests/app/test_common_env_service.py -v 2>&1 | tail -20)
}

echo "=== 돌연변이 1: 잠금 제거 ==="; run_mutation no-lock
echo "=== 돌연변이 2: open(w) 로 되돌리기 ==="; run_mutation no-atomic
rm -rf "$SCRATCH"
```

**실측 결과다.** 계획 단계의 기대와 하나가 달랐으므로 그것을 그대로 적는다.

| 돌연변이 | 실패한 검사 | 걸린 자리 |
|---|---|---|
| 1. 잠금 제거 | 경합 검사 하나 (10 PASS) | 값 단언. 최종 파일이 `SMTP_HOST=old` 로 되돌아갔다 |
| 2. `open(w)` 복귀 | 셋 (8 PASS) | 모드 `420 != 384`, 예외 미전파, 링크 대상 오염 |

**돌연변이 2 는 경합 검사를 실패시키지 못한다.** 지연이 `atomic_write_text` 에 걸려
있으므로 그 호출을 없애는 돌연변이가 지연까지 함께 없애고, 두 스레드가 순차로 돌아
경합 자체가 생기지 않는다. 즉 경합 검사의 꼬리 단언은 최종 상태의 불변식일 뿐이고,
원자적 교체를 되돌리는 회귀를 실제로 잡는 것은 `narrows_file_mode`(모드),
`keeps_environ_and_file_intact`(예외 전파), `replaces_symlink`(링크 추종) 셋이다. 세
검사가 서로 다른 각도에서 같은 회귀를 잡으므로 보호는 충분하고, 꼬리를 직접 재는
검사를 따로 만들지 않는다. 원자적 교체가 있는 코드에서는 꼬리 잔존을 재현할 방법이
없기 때문이다. 이 한계를 검사 docstring 에도 적었다.

- [ ] **Step 6: 무효해진 검사를 정리하고 대체 검사를 넣는다**

`test_update_env_file_narrows_mode_before_writing` 을 삭제한다. 이 검사는 `os.fchmod`
를 스파이해 「모드를 좁히는 시점에 파일이 0바이트」임을 쟀다. `atomic_write_text` 로
옮기면 그 호출이 없어질 뿐 아니라, 임시 파일이 처음부터 0600 이고 교체 뒤에야 경로에
나타나므로 **그 검사가 막던 회귀 자체가 성립하지 않는다.** 같은 파일의
`test_update_env_file_narrows_file_mode` 가 「이 함수가 끝나면 0600」을 계속 재므로
모드에 대한 보호는 남는다.

그 자리에 저장 실패 시의 성질과 심볼릭 링크 방어를 재는 검사를 넣는다.

```python
def test_update_env_file_keeps_environ_and_file_intact_when_write_fails(
    tmp_path: Path, monkeypatch
):
    """저장이 실패하면 그 워커의 메모리도 디스크도 바뀌지 않는다.

    종전에는 environ 을 루프 안에서 먼저 고쳤으므로, 저장이 실패해도 그 워커만 새 값을
    들고 있었다. is_admin_email 처럼 매 요청 os.environ 을 다시 읽는 경로가 있어서,
    같은 요청이 어느 워커에 닿느냐에 따라 다르게 동작했다.

    파일 쪽 단언은 원자적 교체가 실제로 걸렸는지를 함께 잰다. open(w) 로 되돌리면 이미
    잘린 빈 파일이 남아 이 줄이 실패한다.
    """
    env_path = tmp_path / ".env"
    env_path.write_text("SMTP_HOST=old\n", encoding="utf-8")

    def failing_write(file_path, content, **kwargs):
        raise OSError("no space left on device")

    monkeypatch.setattr(common_env_service, "atomic_write_text", failing_write)

    environ = {"SMTP_HOST": "old"}
    with pytest.raises(OSError):
        update_env_file(str(env_path), {"SMTP_HOST": "new"}, environ)

    assert environ == {"SMTP_HOST": "old"}
    assert env_path.read_text(encoding="utf-8") == "SMTP_HOST=old\n"


def test_update_env_file_replaces_symlink_instead_of_following_it(tmp_path: Path):
    """.env 가 다른 파일의 링크로 바뀌어 있어도 그 대상을 덮지 않는다.

    open(w) 는 링크를 따라가 대상을 잘랐다. 부모 디렉터리 항목을 교체할 권한이 있는
    주체가 읽기와 쓰기 사이에 .env 를 갈아 끼우면, 그 대상 파일이 잘리고 .env 내용으로
    덮였다. exists() 나 islink() 사전 검사를 더해도 검사와 쓰기 사이의 경합이 남으므로
    해법은 os.replace 뿐이다.

    운영 배포의 루트 .env 는 일반 파일이다. restart_all.sh 가 만드는 링크는
    frontend/.env → ../.env 로 가리키는 쪽이고, 경로 링크라 루트 .env 의 inode 가
    바뀌어도 따라간다.
    """
    victim = tmp_path / "victim.txt"
    victim.write_text("original\n", encoding="utf-8")
    env_path = tmp_path / ".env"
    env_path.symlink_to(victim)

    update_env_file(str(env_path), {"SMTP_HOST": "new"}, {})

    assert victim.read_text(encoding="utf-8") == "original\n"
    assert not env_path.is_symlink()
    assert "SMTP_HOST=new" in env_path.read_text(encoding="utf-8")
```

- [ ] **Step 7: 파일 전체 검사를 다시 돌린다**

```bash
./venv/bin/python -m pytest tests/app/test_common_env_service.py -v
```

기대: 전부 PASS. 검사 수는 9건에서 11건이 된다(1건 삭제, 3건 추가).

---

### Task 2: QA 시나리오를 계획하고 첫 커밋을 남긴다

**Files:**
- Create: `docs/dev-cycle/qa/INFRA-050.md`
- Modify: `docs/dev-cycle/TODO.md` (`[INFRA-050]` 절의 진행 체크와 근거 정정, 후속 항목)

- [ ] **Step 1: 정적 검증을 돌린다**

```bash
./venv/bin/python -m pytest -q 2>&1 | tail -5
```

기대: 전부 통과(종료 코드 0). **vitest 는 돌리지 않는다.** 이번 변경이 `frontend/` 를
한 줄도 건드리지 않으므로 재는 것이 없고, 그 스위트는 `[FE-042]` 로 분리해 둔 간헐
실패를 갖고 있어 무관한 잡음만 더한다. 이 판단을 QA 문서에 적는다.

- [ ] **Step 2: QA 시나리오 문서를 만든다**

`docs/dev-cycle/qa/INFRA-050.md` 를 `archive-format.md` 의 형식으로 쓴다. 필수
시나리오는 아래 아홉이다. 각 줄에 실행 명령과 기대값을 함께 적는다.

| 번호 | 시나리오 | 필수 |
|---|---|---|
| S-1 | 저장 요청 둘이 겹쳐도 두 값이 모두 남는다 | 필수 |
| S-2 | 같은 상황에서 키 없는 꼬리 줄이 생기지 않는다 | 필수 |
| S-3 | 저장이 실패하면 `environ` 과 파일이 모두 그대로다 | 필수 |
| S-4 | `.env` 가 링크로 바뀌어 있어도 대상 파일을 덮지 않는다 | 필수 |
| S-5 | 저장 뒤 `.env` 모드가 0600 이다 | 필수 |
| S-6 | 잠금 파일이 0600 으로 만들어지고 git 이 잡지 않는다 | 필수 |
| S-6b | 잠금 파일이 링크로 바뀌어 있으면 저장이 조용히 진행되지 않는다 | 필수 |
| S-7 | 돌연변이 둘이 각각 다른 단언에서 걸린다 | 필수 |
| S-8 | 기존 검사 전체가 통과한다 | 필수 |
| S-9 | 운영 `.env` 의 수정 시각이 사이클 전과 같다 | 필수 |

**화면 대신 하네스를 쓰는 이유를 문서에 적는다.** 설정 모달의 「저장」은 운영 `.env`
를 실제로 고치므로 누를 수 없고, 그 옆의 알림 테스트는 저장에 더해 운영 디스코드
채널로 실제 발송까지 한다. 그리고 5501 gunicorn 이 `--reload` 없이 떠 있어 지금 떠
있는 워커는 이번 변경 이전의 코드를 들고 있다. 그래서 동적 시나리오는 **스크래치패드에
만든 `.env` 사본**을 대상으로 `update_env_file` 을 직접 호출하는 하네스로 수행한다.

- [ ] **Step 3: TODO 를 고친다**

두 가지를 한다. **항목 자체는 제거하지 않는다.** QA 가 실패하면 재개할 자리가 사라진다.

1. `[INFRA-050]` 절의 진행 체크 두 개를 채우고 설계 승인 기록을 남긴다.
2. **근거 절을 정정한다.** Codex 의 소실 시퀀스가 두 함수에 같은 경로를 직접 넘긴
   모형이라는 것과, 「인증 없이 호출 가능하므로 임의 시점에 경합을 유발할 수 있다」는
   문장이 근거를 잃었다는 것을 적는다. 실재하는 경합이 `update_env_file` 끼리라는 것과
   꼬리 잔존을 재현했다는 것도 함께 적는다. 이것을 빼면 다음 사람이 같은 착오를
   반복한다.

- [ ] **Step 4: 후속 항목을 TODO 에 올린다**

경로 버그를 새 항목으로 만든다. `[INFRA-042]` 뒤에 놓고 의존을 명시한다. 본문에
「범위에서 뺀 것」 절의 셋(경로 계산 통합, `env_file_lock` 적용, 주기 값이 실제로
기록되기 시작하는 동작 변경)을 그대로 옮긴다.

- [ ] **Step 5: 허용 경로만 스테이징하고 검사한다**

리뷰 과정에서 `services/kr_market_data_cache_core.py` 와 그 검사 파일이 범위에 들어왔다.
보안 리뷰의 M1(임시 파일이 `.gitignore` 를 빠져나감)과 적대적 리뷰의 H1(쓰기 실패 시
시크릿을 담은 잔재가 남음)이 그 파일의 `atomic_write_text` 에 있기 때문이다.

```bash
git add services/common_env_service.py services/kr_market_data_cache_core.py \
        tests/app/test_common_env_service.py \
        tests/services/test_kr_market_data_cache_service_refactor.py \
        docs/dev-cycle/qa/INFRA-050.md docs/dev-cycle/TODO.md \
        docs/superpowers/plans/2026-09-08-infra-050-env-write-serialization.md
git diff --cached --check; echo "check exit=$?"
git status --short
```

기대: `check exit=0`, 그리고 `?? package.json` 만 스테이징 밖에 남는다. 종료 코드가
0 이 아니면 커밋하지 않고 원인을 고친다.

- [ ] **Step 6: 첫 커밋을 남긴다**

```bash
git commit -m "$(cat <<'EOF'
fix(infra): [INFRA-050] 겹치는 .env 저장이 서로를 깨뜨리지 않게 한다

설정 화면이 POST /api/system/env 를 내는 자리가 둘이다. 「저장」 버튼과 알림 테스트가
각각 보내며 gunicorn 이 워커 둘로 뜨므로 동시에 처리된다.

open(w) 는 여는 시점에만 잘라내므로 두 요청이 각자 offset 0 에서 썼다. 나중에 쓴 쪽이
짧으면 먼저 쓴 쪽의 꼬리가 남아 키 없는 줄이 되고, 이 파일의 파서가 그것을 보존해
영구히 남았다. 줄 중간에 떨어지면 값 자체가 잘린 채 오염됐다.

읽기부터 교체까지를 fcntl.flock 기반 env_file_lock 으로 묶고, 쓰기를 atomic_write_text
로 바꿨다. environ 갱신은 파일 저장이 성공한 뒤로 옮겨, 저장이 실패했을 때 그 워커의
메모리와 디스크가 갈리지 않게 했다.

.env 를 다른 파일의 링크로 갈아 끼우는 경로도 닫는다. 처음에는 os.replace 가 링크를
따라가지 않는다는 것만으로 닫았다고 적었는데 그것은 쓰기에만 참이었다. 읽기는 여전히
따라가 대상의 ADMIN_API_TOKEN 과 ADMIN_EMAILS 를 그대로 새 .env 로 옮겼다. 저장과 조회
두 읽기를 _read_env_lines 로 묶고 O_NOFOLLOW 를 붙였다.

atomic_write_text 는 임시 파일 이름을 대상 파일명으로 시작하게 하고, 이름을 with 블록
첫 줄에서 잡는다. 앞의 것은 .env 사본이 .gitignore 를 빠져나가 커밋에 실리는 것을 막고,
뒤의 것은 fsync 가 실패했을 때 시크릿을 담은 0600 잔재가 남는 것을 막는다.

주기 저장 경로는 이번 범위가 아니다. 그 경로는 존재하지 않는 app/.env 를 보고 있어
배타할 상대가 없으며, 경로를 고치면 인증 없는 엔드포인트가 운영 .env 를 쓰게 되므로
[INFRA-042] 뒤의 별도 항목으로 올렸다.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AeQQtEk7wbuVAnf9kCJmBN
EOF
)"
```

---

## Self-Review

**1. 사양 대비 빠짐**: TODO 의 완료 조건 넷 가운데 셋을 덮고, 하나는 근거를 잃어
정정한다. ①「`atomic_write_text` 로 통일할지 결정」 → Task 1 Step 3 에서 통일한다.
②「두 경로가 겹칠 때 마지막 상태가 온전한지 확인하는 검사」 → **주체를 정정해**
`update_env_file` 두 벌로 재는 검사를 Task 1 Step 1 에 둔다. 두 경로 사이의 검사는
지금 같은 파일을 보지 않으므로 잠금이 아니라 인자 전달을 재게 되어 두지 않는다.
③「`environ` 갱신을 파일 저장 성공 뒤로」 → Task 1 Step 3 의 `applied`/`removed`.
④ P2 로 적힌 심볼릭 링크 지적 → `os.replace` 가 닫고 Task 1 Step 6 의 검사가 지킨다.

**2. 자리 표시자**: 없다. 모든 코드 단계에 실제 코드가 있고, 모든 검증 단계에 실제
명령과 기대값이 있다.

**3. 이름 일관성**: `_env_file_lock` 은 Task 1 이 정의하고 이번 범위 안에서는
`update_env_file` 만 쓴다. 후속 항목이 `persist_market_gate_interval_to_env` 에서
import 할 자리를 Interfaces 에 적어 두었다. `applied`/`removed`/`updated_keys` 는
Task 1 안에서만 쓴다. `atomic_write_text` 는 모듈 수준 import 이므로 monkeypatch
대상이 되며, Task 1 의 검사 셋이 모두 그 사실에 의존한다.

**4. 검토에서 지적받아 고친 것**: 경합 주체의 정정, 주기 저장 경로에 잠금을 두르는
작업(옛 Task 2) 삭제, 꼬리 잔존을 심각도의 근거로 세운 것, 사전 실측 4 의 의존 목록
보정, `_env_file_lock` 의 재진입 불가 명시, 「이 두 파일이 주기 저장 경로를 지나간다」는
틀린 주장 삭제. 마지막 것은 실측으로 확인했다.
`tests/services/test_kr_market_interval_http_service.py` 는 `persist_interval_fn` 에
람다만 넘기고, `tests/app/test_kr_market_route_integration.py:483` 은 무동작으로
대체하므로 저장소에 그 함수를 실제로 부르는 검사가 없다.
