# [CHAT-034] 챗봇 SQLite 누락 테이블 복구 래퍼 통합 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 챗봇 저장소 함수 열네 개가 각자 복제한 「누락 테이블 → 스키마 강제 재확인 → 자기 재귀 호출」 골격을 공용 래퍼 한 곳으로 모은다.

**Architecture:** 저장소에 이미 있는 `services/sqlite_ready_gate.run_with_schema_recovery`(누락 테이블이면 `recover()` 뒤 한 번 재시도, 재시도 실패는 `SchemaRecoveryRetryError`)를 챗봇 전용 인자로 감싸는 함수 `run_chatbot_sqlite_with_recovery` 를 `chatbot/storage_sqlite_common.py` 에 둔다. 각 함수는 `try` 안에서 이 래퍼를 한 번 부르고, `except` 의 로그·기본값 반환은 그대로 둔다.

**Tech Stack:** Python 3.11, sqlite3, pytest.

**Spec:** 별도 설계 문서 없음(bounded). 설계는 2026-09-23 대화에서 제시하고 사용자가 「응 진행해」로 승인했다. 요지는 `docs/dev-cycle/TODO.md` 의 `[CHAT-034]` 설계 승인 줄에 있다.

## Global Constraints

- `services/sqlite_utils.py`, `services/sqlite_ready_gate.py` 는 고치지 않는다.
- 공개 함수의 위치 인자·키워드 인자(`owner_id` 포함)와 반환 형식은 그대로 둔다. private 키워드 `_retried` 만 지운다(외부 호출자·테스트 0건, `grep -rn "_retried" chatbot tests` 로 확인).
- 각 함수의 실패 로그 문구와 기본값(`None`/`False`)은 유지한다.
- 재시도 상수는 `storage_sqlite_common` 의 `_SQLITE_RETRY_ATTEMPTS = 2`, `_SQLITE_RETRY_DELAY_SECONDS = 0.03` 을 쓴다(두 모듈의 로컬 값과 같다).
- `chatbot/storage_sqlite_common.py` 는 위험 경로(스키마 정의)이므로 티어는 T3 이다.
- 수용한 동작 차이 세 가지:
  1. `_prune_daily_suggestions_in_sqlite` 의 probe·삭제 두 단계를 operation 하나로 묶으므로, 일시 잠금 재시도 때 읽기 전용 probe 도 다시 돈다. 일시 잠금 재시도 예산도 probe 2회 + 삭제 2회에서 둘을 합쳐 2회로 줄어든다(코드 리뷰 관찰, 수용).
  2. 복구 뒤 재시도까지 실패하면 로그의 오류 부분이 `schema recovery retry failed: <원래 오류>` 가 된다.
  3. 재시도 때 `db_path.exists()`·비강제 스키마 확인을 다시 거치지 않는다. 직전 강제 복구가 같은 일을 했다.

## 대상 함수 표

| 모듈 | 함수 | table_names | 기본값 |
|---|---|---|---|
| history | `load_history_sessions_from_sqlite` | `("chatbot_sessions", "chatbot_messages")` | `None` |
| history | `save_history_sessions_to_sqlite` | 같음 | `False` |
| history | `upsert_history_session_with_messages` | 같음 | `False` |
| history | `apply_history_session_deltas_in_sqlite` | 같음 | `False` |
| history | `delete_history_session_from_sqlite` | 같음 | `False` |
| history | `clear_history_sessions_in_sqlite` | 같음 | `False` |
| memory | `_prune_daily_suggestions_in_sqlite` | `("chatbot_memories",)` | `False` |
| memory | `save_daily_suggestions_in_sqlite` | 같음 | `False` |
| memory | `load_memories_from_sqlite` | 같음 | `None` |
| memory | `save_memories_to_sqlite` | 같음 | `False` |
| memory | `upsert_memory_entry_in_sqlite` | 같음 | `False` |
| memory | `delete_memory_entry_in_sqlite` | 같음 | `False` |
| memory | `clear_memories_in_sqlite` | 같음 | `False` |
| memory | `clear_general_memories_in_sqlite` | 같음 | `False` |

---

### Task 1: 공용 래퍼

**Files:**
- Modify: `chatbot/storage_sqlite_common.py`
- Test: `tests/chatbot/test_storage_sqlite_common_refactor.py` (신규)

**Interfaces:**
- Produces: `run_chatbot_sqlite_with_recovery(db_path: Path, logger: logging.Logger, operation: Callable[[], T], *, table_names: tuple[str, ...]) -> T`

- [ ] **Step 1: 실패하는 테스트 작성** — 래퍼 단위 검사 두 개

```python
def test_wrapper_recovers_missing_table_once(tmp_path):
    db_path = resolve_chatbot_storage_db_path(tmp_path)
    assert ensure_chatbot_storage_schema(db_path, LOGGER)
    with sqlite3.connect(db_path) as conn:
        conn.execute("DROP TABLE chatbot_memories")

    def _count():
        with sqlite3.connect(db_path) as conn:
            return conn.execute("SELECT COUNT(*) FROM chatbot_memories").fetchone()[0]

    assert run_chatbot_sqlite_with_recovery(
        db_path, LOGGER, _count, table_names=("chatbot_memories",)
    ) == 0


def test_wrapper_does_not_recover_other_tables(tmp_path, monkeypatch):
    db_path = resolve_chatbot_storage_db_path(tmp_path)
    recover_calls = []
    monkeypatch.setattr(
        sqlite_common, "ensure_chatbot_storage_schema",
        lambda *a, **k: recover_calls.append(k) or True,
    )

    def _fail():
        raise sqlite3.OperationalError("no such table: chatbot_sessions")

    with pytest.raises(sqlite3.OperationalError):
        run_chatbot_sqlite_with_recovery(
            db_path, LOGGER, _fail, table_names=("chatbot_memories",)
        )
    assert recover_calls == []
```

- [ ] **Step 2: 실패 확인** — `pytest tests/chatbot/test_storage_sqlite_common_refactor.py -q` → ImportError(`run_chatbot_sqlite_with_recovery` 없음)

- [ ] **Step 3: 구현** — `storage_sqlite_common.py` 끝(`__all__` 앞)에 추가하고 `__all__` 에 이름을 더한다. import 에 `Callable`, `TypeVar`, `run_with_schema_recovery`, `is_sqlite_missing_table_error` 추가.

```python
def run_chatbot_sqlite_with_recovery(
    db_path: Path,
    logger: logging.Logger,
    operation: Callable[[], _T],
    *,
    table_names: tuple[str, ...],
) -> _T:
    """테이블이 없어 실패하면 챗봇 스키마를 강제로 다시 만든 뒤 한 번 더 실행한다."""
    return run_with_schema_recovery(
        operation,
        run_with_retry=run_sqlite_with_retry,
        retry_attempts=_SQLITE_RETRY_ATTEMPTS,
        retry_delay_seconds=_SQLITE_RETRY_DELAY_SECONDS,
        is_missing_table=lambda error: is_sqlite_missing_table_error(error, table_names=table_names),
        recover=lambda: ensure_chatbot_storage_schema(db_path, logger, force_recheck=True),
    )
```

`recover` 람다는 호출 시점에 모듈 전역 `ensure_chatbot_storage_schema` 를 찾으므로 Step 1 의 monkeypatch 가 듣는다.

- [ ] **Step 4: 통과 확인** — 같은 명령 → 2 passed

### Task 2: 열네 함수 전환

**Files:**
- Modify: `chatbot/storage_sqlite_history.py`, `chatbot/storage_sqlite_memory.py`
- Test: `tests/chatbot/test_storage_sqlite_common_refactor.py`

**Interfaces:**
- Consumes: Task 1 의 `run_chatbot_sqlite_with_recovery`

- [ ] **Step 1: 특성 테스트 작성** — 표의 열네 함수를 매개변수화한다. 각 경우 스키마를 만든 뒤 표의 table_names 를 모두 DROP 하고 함수를 부른다. 기대: 기본값이 아닌 성공 값(`load_*` 는 `{}`, 나머지 `True`)을 반환하고 DROP 한 테이블이 `sqlite_master` 에 다시 있다. 인자는 다음처럼 준다.

```python
HISTORY = ("chatbot_sessions", "chatbot_messages")
MEMORY = ("chatbot_memories",)
SESSION = {"id": "s1", "title": "t", "messages": [], "created_at": "2026-09-23T00:00:00",
           "updated_at": "2026-09-23T00:00:00", "model": "m", "owner_id": "o"}
CASES = [
    ("load_history", HISTORY, lambda p: history.load_history_sessions_from_sqlite(p, LOGGER), {}),
    ("save_history", HISTORY, lambda p: history.save_history_sessions_to_sqlite(p, {"s1": SESSION}, LOGGER), True),
    ("upsert_session", HISTORY, lambda p: history.upsert_history_session_with_messages(p, SESSION, LOGGER), True),
    ("apply_deltas", HISTORY, lambda p: history.apply_history_session_deltas_in_sqlite(
        p, {"s1": SESSION}, {"s1"}, set(), False, LOGGER), True),
    ("delete_session", HISTORY, lambda p: history.delete_history_session_from_sqlite(p, "s1", LOGGER), True),
    ("clear_history", HISTORY, lambda p: history.clear_history_sessions_in_sqlite(p, LOGGER), True),
    ("prune_daily", MEMORY, lambda p: memory._prune_daily_suggestions_in_sqlite(p, LOGGER), True),
    ("save_daily", MEMORY, lambda p: memory.save_daily_suggestions_in_sqlite(p, "daily_suggestions_x", [], LOGGER), True),
    ("load_memories", MEMORY, lambda p: memory.load_memories_from_sqlite(p, LOGGER), {}),
    ("save_memories", MEMORY, lambda p: memory.save_memories_to_sqlite(
        p, {"k": {"value": "v", "updated_at": "2026-09-23T00:00:00"}}, LOGGER), True),
    ("upsert_memory", MEMORY, lambda p: memory.upsert_memory_entry_in_sqlite(
        p, "o", "k", {"value": "v", "updated_at": "2026-09-23T00:00:00"}, LOGGER), True),
    ("delete_memory", MEMORY, lambda p: memory.delete_memory_entry_in_sqlite(p, "o", "k", LOGGER), True),
    ("clear_memories", MEMORY, lambda p: memory.clear_memories_in_sqlite(p, LOGGER, owner_id="o"), True),
    ("clear_general", MEMORY, lambda p: memory.clear_general_memories_in_sqlite(p, LOGGER, owner_id="o"), True),
]
```

실제 반환이 표와 다르면(예: 대상 행이 없을 때 `delete_*` 가 `False`) 테스트를 쓰기 전에 현 코드로 한 번 돌려 성공 값을 확인하고 그 값으로 적는다. 복구 실패 경우 하나도 더한다: `ensure_chatbot_storage_schema` 를 `force_recheck=True` 일 때만 `False` 를 돌려주게 monkeypatch 하고 `load_memories_from_sqlite` 가 `None` 을, `save_memories_to_sqlite` 가 `False` 를 돌려주는지 본다(무한 재귀 없음).

- [ ] **Step 2: 현 코드로 통과 확인** — 특성 테스트이므로 전환 전에도 통과해야 한다. 통과하지 않으면 그 함수의 현재 동작을 먼저 확인한다.

- [ ] **Step 3: 전환** — 각 함수에서
  - 시그니처의 `*, _retried: bool = False` 를 지운다(`clear_*memories*` 는 `*, owner_id: str` 만 남긴다).
  - `try` 본문의 `run_sqlite_with_retry(op, max_retries=..., retry_delay_seconds=...)` 를 `run_chatbot_sqlite_with_recovery(db_path, logger, op, table_names=<표>)` 로 바꾼다. 원래 `return run_sqlite_with_retry(...)` 였으면 `return` 을 유지하고, 호출 뒤 `return True` 였으면 그대로 둔다.
  - `except` 의 `if (not _retried) and _is_missing_table_error(...)` 블록을 지우고 `logger.error(...)`·기본값 반환만 남긴다.
  - `_prune_daily_suggestions_in_sqlite` 는 probe·조기 반환·삭제를 내부 함수 `_probe_and_prune() -> bool` 하나로 묶고 두 개의 안쪽 `run_sqlite_with_retry` 호출을 없앤 뒤 `return run_chatbot_sqlite_with_recovery(db_path, logger, _probe_and_prune, table_names=("chatbot_memories",))` 로 부른다.
  - 두 모듈의 로컬 `_is_missing_table_error` 와 쓰지 않게 된 import(`is_sqlite_missing_table_error`, 필요 없어진 `run_sqlite_with_retry`)를 지운다.

- [ ] **Step 4: 검증**
  - `pytest tests/chatbot -q` (원본 트리에서 이 디렉터리만. 전체 pytest 는 INFRA-083 에 따라 사본에서)
  - `grep -n "_retried\|_is_missing_table_error" chatbot/storage_sqlite_history.py chatbot/storage_sqlite_memory.py` → 0건
  - `python -m pyflakes chatbot/storage_sqlite_history.py chatbot/storage_sqlite_memory.py chatbot/storage_sqlite_common.py` 또는 같은 역할의 설치된 린터 → 미사용 import 0
  - 전체 pytest: `git archive` 사본에서 `set -euo pipefail` 로 실행

## 계획 검토 반영 (2026-09-23, critic 판정 ACCEPT-WITH-RESERVATIONS)

1. (필수) `load_memories` 경우는 prune 이 먼저 복구해 버리므로 `memory._prune_daily_suggestions_in_sqlite` 를 `lambda *a, **k: True` 로 우회한 뒤 DROP 한다.
2. (필수) 복구 실패 테스트는 `ensure_chatbot_storage_schema` 스파이를 `sqlite_common`·`storage_sqlite_history`·`storage_sqlite_memory` 세 모듈에 동시에 패치한다. `load_memories` 에는 1번의 prune 우회를 함께 쓴다.
3. (권고) 모든 경우의 스키마 준비는 `ensure_chatbot_storage_schema(p, LOGGER)` 로 한다(게이트 ready 상태를 만들어야 복구 경로를 탄다).
4. (권고) 세션 행 하나를 남기고 `chatbot_messages` 만 DROP 하는 `load_history` 경우를 더한다(table_names 에서 messages 를 빠뜨린 실수 검출).
5. (권고) `apply_history_session_deltas_in_sqlite` 의 `return bool(...)` 은 유지한다. `save_memories` 인자는 `{"o": {"k": {...}}}` 로 쓴다.
- 수용 차이 3 보강: `load_memories` 는 재시도 때 prune 을 다시 돌리지 않는다.

## 리뷰 반영

- `/ponytail-review`: `test_wrapper_recovers_missing_table_once` 는 매개변수화 14건과 같은 경로를 검사하므로 RED 확인 뒤 삭제했다. 이 시점의 신규 파일은 17건, `tests/chatbot` 는 255건이었다.
- `closing-bet-reviewer`(APPROVE, 최대 low): 위 삭제 사실과 prune 재시도 예산 축소를 이 문서에 기록했다.
- `/review`(T3 심층, 별도 문맥 architect, APPROVE): 지적 2(복구 성공 뒤 재시도 실패 경로의 챗봇 수준 검사 공백)를 반영해 `test_retry_failure_after_recovery_returns_default_with_one_recovery` 를 더했다(신규 18건, `tests/chatbot` 256건). 지적 1(메시지 테이블만 복구된 뒤 JSON 스냅샷을 빈 메시지로 덮는 기존 동작)은 이번 diff 의 회귀가 아니어서 `[CHAT-039]` 로 이월했다. 지적 3 은 수용 차이 1과 같다.
- 전체 pytest(격리 `git archive` 사본, `env -i`): 2609 passed, 55 failed, 8 errors. 변경 전 HEAD 사본의 실패·오류 63건과 목록이 같아 새 실패 0건이다. 63건은 node·frontend `node_modules` 가 없는 사본 환경의 `tests/scripts/test_next_environment.py` 49, `test_identity_cross_runtime.py` 8, `test_sync_dependencies.py` 4, 수명주기 2 이다.
