# [CHAT-017] 챗봇 메모리 소유자 분리 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 챗봇 메모리를 소유자별로 나누어, 한 사용자가 저장한 정보가 다른 사용자의 시스템 프롬프트와 `/memory view` 응답에 실리지 않게 한다.

**Architecture:** `chatbot_memories` 테이블의 기본 키를 `memory_key` 에서 `(owner_id, memory_key)` 로 옮기고, `owner_id = ''` 를 **공용 영역**으로 정한다. `MemoryManager` 의 모든 메서드가 `owner_id` 를 선택 인자로 받되 생략하면 공용으로 정규화하므로, 코드가 캐시 용도로 부르는 자리 넷은 한 줄도 고치지 않고 지금 동작을 유지한다. 노출 경로 둘(`format_for_prompt`, `/memory` 명령)만 「소유자가 없으면 아무것도 내주지 않는다」로 판정한다.

**Tech Stack:** Python 3.11, SQLite (표준 라이브러리 `sqlite3`, 실측 버전 3.53.4), pytest

**Spec:** `docs/dev-cycle/TODO.md` 의 `[CHAT-017]` 항목. 이 계획은 그 항목의 체크박스 다섯 개를 그대로 구현한다.

## Global Constraints

- 저장소 스키마를 건드리므로 dev-cycle 티어는 **T3** 이다. `.claude/skills/dev-cycle/references/tier-rules.md` §2 「저장소 스키마」가 `chatbot/storage_sqlite_common.py` 를 `chatbot_memories` 를 정의하는 모듈로 명시한다.
- 파이썬 파일 머리말은 `#!/usr/bin/env python3` 와 `# -*- coding: utf-8 -*-` 를 유지한다.
- 타입 힌트를 붙인다. `from __future__ import annotations` 를 쓰는 파일은 그 관례를 따른다.
- 새 프레임워크나 픽스처 계층을 들이지 않는다. 기존 `tests/chatbot/test_*.py` 형식을 따른다.
- `data/` 아래 파일은 읽기 전용으로만 연다. 검사는 `tmp_path` 픽스처를 쓴다.
- 공용 소유자 값은 빈 문자열 `""` 이며 상수 이름은 `PUBLIC_OWNER_ID` 다. 이 이름과 값을 모든 작업이 그대로 쓴다.
- 세션 테이블의 `owner_id IS NULL`(레거시, 누구나 접근 가능)과 메모리의 `owner_id = ''`(공용, 아무에게도 노출되지 않음)는 **의미가 반대다.** 두 규칙을 섞지 않는다.

---

## 배경 — 실측으로 확인한 사실

작업을 시작하기 전에 이 절을 읽는다. 여기 적힌 것은 이미 확인한 사실이므로 다시 조사하지 않는다.

### 결함

`chatbot/__init__.py:11` 의 `get_chatbot()` 이 `KRStockChatbot("default_user")` 를 프로세스에 하나만 만든다. 그래서 `chatbot/core.py:123` 의 `MemoryManager("default_user")` 인스턴스 하나를 모든 사용자가 공유하고, `chatbot/storage_memory_manager.py:171` 의 `MemoryManager.memories` 가 소유자 구분이 없는 키-값 딕셔너리 하나다.

두 갈래로 새어 나간다.

- **프롬프트**: `chatbot/payload_service.py:52-53` 이 매 요청마다 `format_for_prompt()` 로 저장된 메모리 전부를 시스템 프롬프트에 넣는다.
- **직접 조회**: `/memory view` 명령이 `chatbot/command_service.py:123` 의 `render_memory_view` 에서 전체 메모리를 소유자 구분 없이 돌려준다.

### 저장소에 실제로 무엇이 들어 있는가

`data/chatbot_storage.db` 의 `chatbot_memories` 테이블에 행이 **2건** 있다.

| 키 | 크기 | 정체 |
|---|---|---|
| `interest` | 6바이트 (2026-02-24) | `chatbot/intent_detail_service.py:26` 이 종가베팅 질문마다 쓰는 고정 문자열 `"종가베팅"` |
| `daily_suggestions_default_empty` | 724바이트 (2026-09-05) | `chatbot/daily_suggestions_service.py:65` 가 저장하는 추천 질문 캐시. 유효 기간 1시간 |

둘 다 사용자가 입력한 개인 정보가 아니라 **프로세스 공용 캐시**다. 그런데 `format_for_prompt()` 가 이것들을 「## 사용자 정보 (Long-term Memory)」라는 제목으로 매 요청 프롬프트에 싣고 있다. 724바이트짜리 추천 질문 JSON 이 사용자 정보 행세를 하는 것이다. 이 계획은 유출을 막으면서 그 오염도 함께 없앤다.

현재 테이블 정의는 다음과 같다.

```sql
CREATE TABLE chatbot_memories (
    memory_key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
```

`.env` 에 `USER_PROFILE` 변수가 없어서 `chatbot/runtime_setup_service.py:162` 의 `init_user_profile_from_env` 는 아무것도 저장하지 않으며, DB 에도 `user_profile` 행이 없다.

### 저장소를 쓰는 자리 전부

| 위치 | 호출 | 성격 |
|---|---|---|
| `chatbot/intent_detail_service.py:26` | `memory.add("interest", "종가베팅")` | 공용 (고정값) |
| `chatbot/daily_suggestions_service.py:65` | `bot.memory.add(cache_key, suggestions)` | 공용 (캐시 쓰기) |
| `chatbot/data_service.py:133` | `memory.get(cache_key)` | 공용 (캐시 읽기) |
| `chatbot/runtime_setup_service.py:166,172,185` | `user_profile` 저장·조회 | 공용 (이번 범위 밖) |
| `chatbot/command_service.py:123,152,160,161,166` | `/memory` 의 view·clear·add·update·remove | **소유자별로 바꾼다** |
| `chatbot/payload_service.py:52-53` | `format_for_prompt()` | **소유자별로 바꾼다** |
| `chatbot/core.py:322,326,329,342` | `get_memory`·`update_memory`·`clear_memory`·`memory_count` | `memory_count` 만 바꾼다 |

앞의 넷은 `owner_id` 인자를 주지 않고 부른다. 정규화 규칙(`None` → 공용) 덕분에 **한 줄도 고치지 않는다.** 이것이 이 설계를 고른 이유다.

### 이번 범위에서 제외하는 것

프로필 API(`services/kr_market_chatbot_request_helpers.py:85` 의 `handle_chatbot_profile_request`)에는 소유자 판정이 아예 없다. `bot.get_user_profile()` 을 소유자 없이 부르므로 `user_profile` 은 공용에 남고 모든 사용자가 같은 프로필을 본다. 이것을 소유자별로 나누면 프런트엔드와 「흑기사」 기본 프로필 초기화까지 함께 봐야 하므로 별도 항목이다. 이번에는 공용에 두어 지금 동작을 유지한다.

`format_for_prompt` 가 공용을 싣지 않게 되므로 `user_profile` 은 시스템 프롬프트에서 빠진다. 기능 손실이 아니다. 프로필의 페르소나는 `chatbot/prompts.py:85` 의 `build_system_prompt(persona=...)` 인자로 이미 별도 경로를 거치고, 이름은 프런트엔드가 `/profile` API 로 직접 가져다 쓴다. 게다가 지금 DB 에 `user_profile` 행이 없어 실제로 실리는 것도 없다.

---

## File Structure

| 파일 | 책임 | 작업 |
|---|---|---|
| `chatbot/storage_sqlite_common.py` | 테이블 정의와 마이그레이션 | Task 1 |
| `chatbot/storage_sqlite_memory.py` | 메모리 행의 읽기·쓰기 SQL | Task 2 |
| `chatbot/storage_memory_manager.py` | 인메모리 캐시와 공개 API, 레거시 JSON 스냅샷 | Task 3 |
| `chatbot/command_service.py` | `/memory` 와 `/clear` 명령 라우팅 | Task 4 |
| `chatbot/payload_service.py` | 시스템 프롬프트 조립 | Task 5 |
| `chatbot/core_payload_mixin.py` | payload 래퍼 | Task 5 |
| `chatbot/chat_handlers.py` | 채팅 요청 진입점 | Task 5 |
| `chatbot/core.py` | `get_status` 의 집계 | Task 5 |
| `tests/chatbot/test_memory_owner_access.py` | 신규 회귀 검사 | Task 1~5 에 걸쳐 채운다 |

작업 순서는 저장소 안쪽에서 바깥쪽으로 간다. Task 1 은 스키마만 바꾸고 기존 SQL 을 건드리지 않는데, 새 열에 `DEFAULT ''` 가 있어 기존 `INSERT` 와 `SELECT` 가 그대로 동작하기 때문이다. 그래서 각 작업이 독립적으로 커밋되고 그 시점에 전체 테스트가 통과한다.

---

### Task 1: 저장소 스키마에 소유자 열을 넣고 기존 행을 공용으로 옮긴다

**Files:**
- Modify: `chatbot/storage_sqlite_common.py:118-155` (`_initialize_schema` 안의 `executescript` 와 그 뒤의 마이그레이션 호출부)
- Test: `tests/chatbot/test_memory_owner_access.py` (신규)

**Interfaces:**
- Consumes: 기존 `_load_table_columns(cursor, table_name) -> set[str]` (같은 파일 `:52`)
- Produces: `_ensure_chatbot_memories_owner_column(cursor: sqlite3.Cursor, logger: logging.Logger) -> None`. 새 테이블 정의는 `chatbot_memories(owner_id TEXT NOT NULL DEFAULT '', memory_key TEXT NOT NULL, value_json TEXT NOT NULL, updated_at TEXT NOT NULL, PRIMARY KEY (owner_id, memory_key))` 이다. Task 2 가 이 열 이름과 기본 키를 전제로 SQL 을 쓴다.

- [ ] **Step 1: 마이그레이션 검사를 먼저 쓴다**

`tests/chatbot/test_memory_owner_access.py` 를 새로 만들고 다음을 넣는다. 구 스키마로 테이블을 만들어 행을 넣은 뒤 `ensure_chatbot_storage_schema` 를 부르면 그 행이 공용(`owner_id = ''`)으로 옮겨져야 한다.

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
챗봇 메모리 소유자 분리 회귀 테스트
"""

import logging
import os
import sqlite3
import sys
from pathlib import Path


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from chatbot.storage_sqlite_common import (
    ensure_chatbot_storage_schema,
    resolve_chatbot_storage_db_path,
)


_LOGGER = logging.getLogger("test_memory_owner_access")


def _create_legacy_memory_table(db_path: Path) -> None:
    """소유자 열이 없던 구 스키마를 그대로 만든다."""
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE chatbot_memories (
                memory_key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO chatbot_memories (memory_key, value_json, updated_at)
            VALUES ('interest', '"종가베팅"', '2026-02-24T14:53:29.893673')
            """
        )
        conn.commit()


def test_schema_migration_moves_legacy_rows_to_public_owner(tmp_path: Path):
    """소유자를 알 수 없는 기존 행은 공용('')으로 옮겨진다."""
    db_path = resolve_chatbot_storage_db_path(tmp_path)
    _create_legacy_memory_table(db_path)

    assert ensure_chatbot_storage_schema(db_path, _LOGGER, force_recheck=True)

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT owner_id, memory_key FROM chatbot_memories"
        ).fetchall()
    assert rows == [("", "interest")]


def test_schema_migration_allows_same_key_for_different_owners(tmp_path: Path):
    """기본 키가 (owner_id, memory_key) 로 옮겨졌는지 확인한다."""
    db_path = resolve_chatbot_storage_db_path(tmp_path)
    assert ensure_chatbot_storage_schema(db_path, _LOGGER, force_recheck=True)

    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO chatbot_memories (owner_id, memory_key, value_json, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            [
                ("owner-a", "risk", '"aggressive"', "2026-09-05T00:00:00"),
                ("owner-b", "risk", '"conservative"', "2026-09-05T00:00:01"),
            ],
        )
        conn.commit()
        count = conn.execute("SELECT COUNT(*) FROM chatbot_memories").fetchone()[0]
    assert count == 2
```

- [ ] **Step 2: 검사가 실패하는지 확인한다**

Run: `source venv/bin/activate && pytest tests/chatbot/test_memory_owner_access.py -v`

Expected: 두 검사 모두 FAIL. 첫째는 `sqlite3.OperationalError: no such column: owner_id`, 둘째는 `sqlite3.IntegrityError: UNIQUE constraint failed: chatbot_memories.memory_key` 로 실패한다.

- [ ] **Step 3: 마이그레이션 함수를 만든다**

`chatbot/storage_sqlite_common.py` 의 `_drop_redundant_chatbot_messages_index` (`:79`) 바로 뒤에 다음을 넣는다.

```python
def _ensure_chatbot_memories_owner_column(
    cursor: sqlite3.Cursor,
    logger: logging.Logger,
) -> None:
    """chatbot_memories 의 기본 키를 (owner_id, memory_key) 로 옮긴다.

    SQLite 는 기본 키를 ALTER TABLE 로 바꾸지 못하므로 테이블을 다시 만든다.
    기존 행은 소유자를 알 수 없으므로 공용('')으로 옮긴다. 공용은 프롬프트에도
    /memory view 에도 나타나지 않으므로, 옮기는 것만으로 격리된다.
    """
    columns = _load_table_columns(cursor, "chatbot_memories")
    if not columns or "owner_id" in columns:
        return

    try:
        cursor.executescript(
            """
            ALTER TABLE chatbot_memories RENAME TO chatbot_memories_legacy;
            CREATE TABLE chatbot_memories (
                owner_id TEXT NOT NULL DEFAULT '',
                memory_key TEXT NOT NULL,
                value_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (owner_id, memory_key)
            );
            INSERT INTO chatbot_memories (owner_id, memory_key, value_json, updated_at)
            SELECT '', memory_key, value_json, updated_at FROM chatbot_memories_legacy;
            DROP TABLE chatbot_memories_legacy;
            """
        )
    except sqlite3.OperationalError as error:
        logger.error(f"Failed to migrate chatbot_memories.owner_id: {error}")
        raise
```

- [ ] **Step 4: 새 테이블 정의로 바꾸고 마이그레이션을 부른다**

같은 파일 `_initialize_schema` 안의 `executescript` 에서 `chatbot_memories` 정의를 다음으로 바꾼다.

```sql
CREATE TABLE IF NOT EXISTS chatbot_memories (
    owner_id TEXT NOT NULL DEFAULT '',
    memory_key TEXT NOT NULL,
    value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (owner_id, memory_key)
);
```

그리고 `_drop_redundant_chatbot_messages_index(...)` 호출 바로 뒤, `conn.commit()` 앞에 다음을 넣는다.

```python
            _ensure_chatbot_memories_owner_column(
                cursor=cursor,
                logger=logger,
            )
```

`executescript` 는 열려 있는 트랜잭션을 커밋하므로, 마이그레이션을 `CREATE TABLE IF NOT EXISTS` 뒤에 두어야 순서가 어긋나지 않는다. 새 DB 에서는 `CREATE TABLE` 이 이미 `owner_id` 를 넣으므로 마이그레이션 함수가 곧바로 돌아 나온다.

- [ ] **Step 5: 검사가 통과하는지 확인한다**

Run: `source venv/bin/activate && pytest tests/chatbot/test_memory_owner_access.py -v`

Expected: 2 passed.

- [ ] **Step 6: 기존 검사가 깨지지 않았는지 확인한다**

Run: `source venv/bin/activate && pytest tests/chatbot/ -v`

Expected: 전부 통과. 기존 SQL 은 `owner_id` 를 명시하지 않지만 `DEFAULT ''` 가 채워 주므로 그대로 동작한다.

- [ ] **Step 7: 커밋한다**

```bash
git add chatbot/storage_sqlite_common.py tests/chatbot/test_memory_owner_access.py
git commit -m "$(cat <<'EOF'
refactor(챗봇): [CHAT-017] 메모리 테이블의 기본 키를 소유자와 키의 쌍으로 옮긴다

SQLite 는 기본 키를 ALTER TABLE 로 바꾸지 못하므로 테이블을 다시 만든다.
소유자를 알 수 없는 기존 행은 공용('')으로 옮긴다.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_018BpBasN8thvGk5msXuhHUh
EOF
)"
```

---

### Task 2: SQLite 메모리 헬퍼가 소유자를 다루게 한다

**Files:**
- Modify: `chatbot/storage_sqlite_memory.py` 전체 (다섯 개의 공개 함수와 두 개의 커서 헬퍼)
- Test: `tests/chatbot/test_memory_owner_access.py` (덧붙임)

**Interfaces:**
- Consumes: Task 1 이 만든 `chatbot_memories(owner_id, memory_key, value_json, updated_at)` 테이블과 기본 키 `(owner_id, memory_key)`
- Produces: 다섯 함수의 새 시그니처. Task 3 이 이것을 그대로 부른다.
  - `load_memories_from_sqlite(db_path: Path, logger: logging.Logger, *, _retried: bool = False) -> Dict[str, Dict[str, Any]] | None` — 돌려주는 것이 `{owner_id: {memory_key: {"value": ..., "updated_at": ...}}}` 2단 딕셔너리로 바뀐다
  - `save_memories_to_sqlite(db_path: Path, memories: Dict[str, Dict[str, Any]], logger: logging.Logger, *, _retried: bool = False) -> bool` — 2단 딕셔너리를 받는다
  - `upsert_memory_entry_in_sqlite(db_path: Path, owner_id: str, key: str, record: Dict[str, Any], logger: logging.Logger, *, _retried: bool = False) -> bool`
  - `delete_memory_entry_in_sqlite(db_path: Path, owner_id: str, key: str, logger: logging.Logger, *, _retried: bool = False) -> bool`
  - `clear_memories_in_sqlite(db_path: Path, logger: logging.Logger, *, owner_id: str | None = None, _retried: bool = False) -> bool` — `owner_id` 를 주면 그 소유자의 행만, 주지 않으면 전부 지운다

- [ ] **Step 1: 저장과 조회가 소유자를 지키는지 검사한다**

`tests/chatbot/test_memory_owner_access.py` 에 다음을 덧붙인다. 파일 머리의 import 에 `from chatbot.storage_sqlite_memory import (clear_memories_in_sqlite, delete_memory_entry_in_sqlite, load_memories_from_sqlite, save_memories_to_sqlite, upsert_memory_entry_in_sqlite)` 를 더한다.

```python
def test_sqlite_round_trip_keeps_owners_apart(tmp_path: Path):
    """서로 다른 소유자의 같은 키가 각자 저장되고 각자 돌아온다."""
    db_path = resolve_chatbot_storage_db_path(tmp_path)
    memories = {
        "": {"interest": {"value": "종가베팅", "updated_at": "2026-02-24T14:53:29"}},
        "owner-a": {"risk": {"value": "aggressive", "updated_at": "2026-09-05T00:00:00"}},
        "owner-b": {"risk": {"value": "conservative", "updated_at": "2026-09-05T00:00:01"}},
    }

    assert save_memories_to_sqlite(db_path, memories, _LOGGER)
    loaded = load_memories_from_sqlite(db_path, _LOGGER)

    assert loaded is not None
    assert loaded["owner-a"]["risk"]["value"] == "aggressive"
    assert loaded["owner-b"]["risk"]["value"] == "conservative"
    assert loaded[""]["interest"]["value"] == "종가베팅"


def test_sqlite_single_entry_operations_scope_to_owner(tmp_path: Path):
    """단건 저장과 삭제가 다른 소유자의 같은 키를 건드리지 않는다."""
    db_path = resolve_chatbot_storage_db_path(tmp_path)
    record = {"value": "aggressive", "updated_at": "2026-09-05T00:00:00"}

    assert upsert_memory_entry_in_sqlite(db_path, "owner-a", "risk", record, _LOGGER)
    assert upsert_memory_entry_in_sqlite(db_path, "owner-b", "risk", record, _LOGGER)
    assert delete_memory_entry_in_sqlite(db_path, "owner-a", "risk", _LOGGER)

    loaded = load_memories_from_sqlite(db_path, _LOGGER)
    assert loaded is not None
    assert "owner-a" not in loaded
    assert loaded["owner-b"]["risk"]["value"] == "aggressive"


def test_sqlite_clear_scopes_to_owner(tmp_path: Path):
    """소유자를 주고 지우면 그 소유자의 행만 사라진다."""
    db_path = resolve_chatbot_storage_db_path(tmp_path)
    record = {"value": "aggressive", "updated_at": "2026-09-05T00:00:00"}
    assert upsert_memory_entry_in_sqlite(db_path, "owner-a", "risk", record, _LOGGER)
    assert upsert_memory_entry_in_sqlite(db_path, "", "interest", record, _LOGGER)

    assert clear_memories_in_sqlite(db_path, _LOGGER, owner_id="owner-a")

    loaded = load_memories_from_sqlite(db_path, _LOGGER)
    assert loaded is not None
    assert "owner-a" not in loaded
    assert loaded[""]["interest"]["value"] == "aggressive"
```

- [ ] **Step 2: 검사가 실패하는지 확인한다**

Run: `source venv/bin/activate && pytest tests/chatbot/test_memory_owner_access.py -v`

Expected: 새 검사 3건이 FAIL. `upsert_memory_entry_in_sqlite` 가 아직 `owner_id` 를 받지 않으므로 `TypeError` 가 나거나, 2단 딕셔너리를 1단으로 취급해 값이 어긋난다.

- [ ] **Step 3: 커서 헬퍼 둘을 소유자 기준으로 고친다**

`chatbot/storage_sqlite_memory.py` 의 `_upsert_memory_rows_cursor` 와 `_delete_stale_memory_rows_cursor` 를 다음으로 바꾼다. 인라인 분기와 `_SQLITE_INLINE_DELETE_MAX_VARIABLES` 상수(`:29`)는 지운다. 소유자와 키의 쌍으로 판정하려면 임시 테이블이 필요한데, 그러면 분기 하나가 사라져 코드가 짧아진다.

```python
def _upsert_memory_rows_cursor(
    *,
    cursor: sqlite3.Cursor,
    rows: list[tuple[str, str, str, str]],
) -> None:
    if not rows:
        return
    cursor.executemany(
        """
        INSERT INTO chatbot_memories (owner_id, memory_key, value_json, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(owner_id, memory_key) DO UPDATE SET
            value_json = excluded.value_json,
            updated_at = excluded.updated_at
        WHERE
            chatbot_memories.value_json IS NOT excluded.value_json
            OR chatbot_memories.updated_at IS NOT excluded.updated_at
        """,
        rows,
    )


def _delete_stale_memory_rows_cursor(
    *,
    cursor: sqlite3.Cursor,
    active_pairs: list[tuple[str, str]],
) -> None:
    """저장 요청에 없는 행을 지운다. 소유자와 키의 쌍으로 판정한다."""
    normalized_pairs = list(dict.fromkeys(active_pairs))
    if not normalized_pairs:
        cursor.execute("DELETE FROM chatbot_memories")
        return

    cursor.execute(
        """
        CREATE TEMP TABLE IF NOT EXISTS _tmp_chatbot_memory_owner_keys (
            owner_id TEXT NOT NULL,
            memory_key TEXT NOT NULL,
            PRIMARY KEY (owner_id, memory_key)
        )
        """
    )
    cursor.execute("DELETE FROM _tmp_chatbot_memory_owner_keys")
    cursor.executemany(
        """
        INSERT OR IGNORE INTO _tmp_chatbot_memory_owner_keys(owner_id, memory_key)
        VALUES (?, ?)
        """,
        normalized_pairs,
    )
    cursor.execute(
        """
        DELETE FROM chatbot_memories
        WHERE (owner_id, memory_key) NOT IN (
            SELECT owner_id, memory_key
            FROM _tmp_chatbot_memory_owner_keys
        )
        """
    )
```

행 값 비교(`(a, b) NOT IN (SELECT a, b FROM t)`)는 SQLite 3.15 부터 쓸 수 있고, 이 저장소의 실행 환경은 3.53.4 다.

- [ ] **Step 4: 조회 함수가 2단 딕셔너리를 돌려주게 한다**

`load_memories_from_sqlite` 의 `SELECT` 와 행 조립을 다음으로 바꾼다.

```python
                return conn.execute(
                    """
                    SELECT owner_id, memory_key, value_json, updated_at
                    FROM chatbot_memories
                    ORDER BY owner_id ASC, memory_key ASC
                    """
                ).fetchall()

        rows = run_sqlite_with_retry(
            _load_rows,
            max_retries=_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_SQLITE_RETRY_DELAY_SECONDS,
        )
        memories: dict[str, dict[str, dict[str, Any]]] = {}
        for row in rows:
            try:
                value = json.loads(row["value_json"])
            except Exception:
                value = row["value_json"]
            memories.setdefault(str(row["owner_id"]), {})[row["memory_key"]] = {
                "value": value,
                "updated_at": row["updated_at"],
            }
        return memories
```

- [ ] **Step 5: 저장 함수가 2단 딕셔너리를 받게 한다**

`save_memories_to_sqlite` 의 행 조립을 다음으로 바꾼다. 시그니처의 `memories` 타입 힌트를 `Dict[str, Dict[str, Any]]` 로 고친다.

```python
        rows: list[tuple[str, str, str, str]] = []
        for owner_id, owned in memories.items():
            for key, raw_value in (owned or {}).items():
                value = raw_value.get("value") if isinstance(raw_value, dict) else raw_value
                updated_at = (
                    str(raw_value.get("updated_at"))
                    if isinstance(raw_value, dict) and raw_value.get("updated_at")
                    else datetime.now().isoformat()
                )
                rows.append(
                    (
                        str(owner_id),
                        str(key),
                        json.dumps(value, ensure_ascii=False, separators=(",", ":")),
                        updated_at,
                    )
                )
```

그리고 `_save_rows` 안의 두 호출을 다음으로 바꾼다.

```python
                _upsert_memory_rows_cursor(
                    cursor=cursor,
                    rows=rows,
                )
                _delete_stale_memory_rows_cursor(
                    cursor=cursor,
                    active_pairs=[(row[0], row[1]) for row in rows],
                )
```

- [ ] **Step 6: 단건 함수 셋에 소유자를 더한다**

`upsert_memory_entry_in_sqlite` 의 시그니처를 `(db_path: Path, owner_id: str, key: str, record: Dict[str, Any], logger: logging.Logger, *, _retried: bool = False)` 로 바꾸고, 내부 SQL 과 재귀 호출을 함께 고친다.

```python
                conn.execute(
                    """
                    INSERT INTO chatbot_memories (owner_id, memory_key, value_json, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(owner_id, memory_key) DO UPDATE SET
                        value_json=excluded.value_json,
                        updated_at=excluded.updated_at
                    WHERE
                        chatbot_memories.value_json IS NOT excluded.value_json
                        OR chatbot_memories.updated_at IS NOT excluded.updated_at
                    """,
                    (
                        str(owner_id),
                        str(key),
                        json.dumps(value, ensure_ascii=False, separators=(",", ":")),
                        updated_at,
                    ),
                )
```

`delete_memory_entry_in_sqlite` 의 시그니처를 `(db_path: Path, owner_id: str, key: str, logger: logging.Logger, *, _retried: bool = False)` 로 바꾸고 SQL 을 고친다.

```python
                conn.execute(
                    """
                    DELETE FROM chatbot_memories
                    WHERE owner_id = ? AND memory_key = ?
                    """,
                    (str(owner_id), str(key)),
                )
```

`clear_memories_in_sqlite` 의 시그니처에 `owner_id: str | None = None` 을 키워드 전용으로 더하고 SQL 을 고친다.

```python
        def _clear_rows() -> None:
            with connect_sqlite(
                db_path_text,
                timeout_seconds=_SQLITE_TIMEOUT_SECONDS,
                pragmas=_SQLITE_SESSION_PRAGMAS,
            ) as conn:
                if owner_id is None:
                    conn.execute("DELETE FROM chatbot_memories")
                else:
                    conn.execute(
                        "DELETE FROM chatbot_memories WHERE owner_id = ?",
                        (str(owner_id),),
                    )
                conn.commit()
```

세 함수 모두 예외 처리부의 재귀 호출에 새 인자를 그대로 넘기도록 함께 고친다.

- [ ] **Step 7: 검사가 통과하는지 확인한다**

Run: `source venv/bin/activate && pytest tests/chatbot/test_memory_owner_access.py -v`

Expected: 5 passed.

- [ ] **Step 8: 커밋한다**

이 시점에는 `chatbot/storage_memory_manager.py` 가 아직 1단 딕셔너리를 넘기므로 `tests/chatbot/test_storage_sqlite.py` 의 메모리 검사가 깨진다. Task 3 이 그것을 고치므로 Task 2 와 Task 3 을 한 커밋으로 묶는다. Step 8 은 Task 3 의 마지막 단계에서 함께 수행하고, 여기서는 커밋하지 않는다.

---

### Task 3: MemoryManager 를 소유자별 2단 구조로 바꾼다

**Files:**
- Modify: `chatbot/storage_memory_manager.py` 전체
- Modify: `tests/chatbot/test_storage_sqlite.py:114-129` (`test_memory_manager_persists_and_restores_from_sqlite`)
- Test: `tests/chatbot/test_memory_owner_access.py` (덧붙임)

**Interfaces:**
- Consumes: Task 2 가 만든 다섯 함수의 새 시그니처
- Produces: `MemoryManager` 의 공개 API. Task 4 와 Task 5 가 이것을 부른다.
  - `PUBLIC_OWNER_ID: str` (값 `""`) — 모듈 수준 상수
  - `view(owner_id: Optional[str] = None) -> Dict[str, Any]`
  - `get(key: str, owner_id: Optional[str] = None) -> Any`
  - `add(key: str, value: Any, owner_id: Optional[str] = None) -> str`
  - `update(key: str, value: Any, owner_id: Optional[str] = None) -> str`
  - `remove(key: str, owner_id: Optional[str] = None) -> str`
  - `clear(owner_id: Optional[str] = None) -> str`
  - `format_for_prompt(owner_id: Optional[str] = None) -> str`
  - `to_dict() -> Dict[str, Any]` — 2단 딕셔너리 전체를 그대로 돌려준다 (시그니처 무변경)

- [ ] **Step 1: 소유자별 격리를 검사한다**

`tests/chatbot/test_memory_owner_access.py` 에 다음을 덧붙인다. 파일 머리의 import 에 `import chatbot.core as chatbot_core` 를 더한다.

```python
def test_format_for_prompt_excludes_other_owners(monkeypatch, tmp_path: Path):
    """남의 메모리는 프롬프트에 실리지 않는다."""
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)
    memory = chatbot_core.MemoryManager(user_id="u1")
    memory.add("보유종목", "삼성전자", owner_id="owner-a")

    assert "삼성전자" in memory.format_for_prompt("owner-a")
    assert memory.format_for_prompt("owner-b") == ""


def test_format_for_prompt_excludes_public_area(monkeypatch, tmp_path: Path):
    """공용 영역은 프롬프트에 실리지 않는다.

    추천 질문 캐시(daily_suggestions_*)와 고정값(interest)이 여기 들어 있어서,
    종전에는 724바이트짜리 캐시 JSON 이 「사용자 정보」로 프롬프트에 실렸다.
    """
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)
    memory = chatbot_core.MemoryManager(user_id="u1")
    memory.add("daily_suggestions_default_empty", [{"prompt": "질문"}])

    assert memory.format_for_prompt("owner-a") == ""
    assert memory.format_for_prompt() == ""


def test_view_excludes_other_owners(monkeypatch, tmp_path: Path):
    """남의 메모리는 조회에도 나오지 않는다."""
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)
    memory = chatbot_core.MemoryManager(user_id="u1")
    memory.add("보유종목", "삼성전자", owner_id="owner-a")

    assert "보유종목" in memory.view("owner-a")
    assert memory.view("owner-b") == {}
    assert memory.view() == {}


def test_clear_scopes_to_requesting_owner(monkeypatch, tmp_path: Path):
    """초기화는 요청자의 메모리만 지운다."""
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)
    memory = chatbot_core.MemoryManager(user_id="u1")
    memory.add("보유종목", "삼성전자", owner_id="owner-a")
    memory.add("보유종목", "카카오", owner_id="owner-b")

    memory.clear("owner-a")

    assert memory.view("owner-a") == {}
    assert memory.view("owner-b")["보유종목"]["value"] == "카카오"


def test_legacy_json_snapshot_loads_as_public(monkeypatch, tmp_path: Path):
    """1단으로 저장된 레거시 JSON 스냅샷은 전부 공용으로 읽는다."""
    import json

    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)
    (tmp_path / "chatbot_memory.json").write_text(
        json.dumps({"interest": {"value": "종가베팅", "updated_at": "2026-02-24T00:00:00"}}),
        encoding="utf-8",
    )

    memory = chatbot_core.MemoryManager(user_id="u1")

    assert memory.view()["interest"]["value"] == "종가베팅"
    assert memory.view("owner-a") == {}
```

- [ ] **Step 2: 검사가 실패하는지 확인한다**

Run: `source venv/bin/activate && pytest tests/chatbot/test_memory_owner_access.py -v`

Expected: 새 검사 5건이 FAIL. `add()` 가 아직 `owner_id` 키워드를 받지 않아 `TypeError: add() got an unexpected keyword argument 'owner_id'` 가 난다.

- [ ] **Step 3: 상수와 정규화 함수를 만든다**

`chatbot/storage_memory_manager.py` 의 `logger = logging.getLogger(__name__)` (`:28`) 바로 뒤에 넣는다.

```python
PUBLIC_OWNER_ID = ""


def _normalize_owner_id(owner_id: Optional[str]) -> str:
    """소유자를 모르면 공용으로 본다.

    코드가 캐시 용도로 부르는 자리(daily_suggestions_*, interest, user_profile)는
    owner_id 를 주지 않으므로 공용에 남는다. 사용자가 /memory 로 넣는 것만
    소유자별로 나뉜다. 공용은 프롬프트에도 /memory view 에도 노출되지 않는다.
    """
    return owner_id or PUBLIC_OWNER_ID
```

- [ ] **Step 4: 레거시 JSON 스냅샷을 2단으로 읽고 쓴다**

`_load_legacy_memory` 의 마지막 반환부를 다음으로 바꾼다. 1단으로 저장된 기존 파일을 공용으로 승격한다.

```python
        if isinstance(loaded, dict):
            return _promote_legacy_flat_memories(loaded)
        logger.warning(f"Unexpected memory format type: {type(loaded).__name__}")
        return {}
```

그리고 `_load_legacy_memory` 바로 앞에 승격 함수를 넣는다.

```python
def _promote_legacy_flat_memories(loaded: Dict[str, Any]) -> Dict[str, Any]:
    """1단으로 저장된 레거시 스냅샷을 공용 영역으로 옮긴다.

    2단은 값이 모두 딕셔너리의 딕셔너리다. 1단은 값에 "value" 키가 있다.
    """
    if not loaded:
        return {}
    if all(
        isinstance(value, dict) and "value" not in value
        for value in loaded.values()
    ):
        return loaded
    return {PUBLIC_OWNER_ID: loaded}
```

- [ ] **Step 5: 단건 저장과 삭제, 전체 삭제에 소유자를 흘려보낸다**

`_save_single_entry`, `_delete_single_entry`, `_clear_storage` 를 다음으로 바꾼다.

```python
    def _save_single_entry(self, owner_id: str, key: str) -> None:
        record = self.memories.get(owner_id, {}).get(key)
        if not isinstance(record, dict):
            self._save()
            return

        sqlite_saved = upsert_memory_entry_in_sqlite(
            self.db_path,
            owner_id=owner_id,
            key=key,
            record=record,
            logger=logger,
        )
        if not sqlite_saved:
            logger.warning("SQLite single memory upsert failed; full sync fallback")
            self._save()
            return
        self._save_legacy_memory_snapshot(self.memories)

    def _delete_single_entry(self, owner_id: str, key: str) -> None:
        sqlite_saved = delete_memory_entry_in_sqlite(
            self.db_path,
            owner_id=owner_id,
            key=key,
            logger=logger,
        )
        if not sqlite_saved:
            logger.warning("SQLite memory delete failed; full sync fallback")
            self._save()
            return
        self._write_legacy_memory_snapshot(self.memories)

    def _clear_storage(self, owner_id: str) -> None:
        sqlite_saved = clear_memories_in_sqlite(
            self.db_path,
            logger=logger,
            owner_id=owner_id,
        )
        if not sqlite_saved:
            logger.warning("SQLite memory clear failed; full sync fallback")
            self._save()
            return
        self._write_legacy_memory_snapshot(self.memories)
```

- [ ] **Step 6: 공개 API 를 소유자별로 바꾼다**

`view` 부터 `format_for_prompt` 까지를 다음으로 바꾼다.

```python
    def view(self, owner_id: Optional[str] = None) -> Dict[str, Any]:
        return self.memories.get(_normalize_owner_id(owner_id), {})

    def get(self, key: str, owner_id: Optional[str] = None) -> Any:
        return self.view(owner_id).get(key)

    def add(self, key: str, value: Any, owner_id: Optional[str] = None) -> str:
        owner = _normalize_owner_id(owner_id)
        self.memories.setdefault(owner, {})[key] = {
            "value": value,
            "updated_at": datetime.now().isoformat(),
        }
        self._save_single_entry(owner, key)
        return f"✅ 메모리 저장: {key} = {value}"

    def remove(self, key: str, owner_id: Optional[str] = None) -> str:
        owner = _normalize_owner_id(owner_id)
        owned = self.memories.get(owner, {})
        if key in owned:
            del owned[key]
            self._delete_single_entry(owner, key)
            return f"🗑️ 메모리 삭제: {key}"
        return "⚠️ 해당 키를 찾을 수 없습니다."

    def update(self, key: str, value: Any, owner_id: Optional[str] = None) -> str:
        owner = _normalize_owner_id(owner_id)
        owned = self.memories.get(owner, {})
        if key in owned:
            owned[key]["value"] = value
            owned[key]["updated_at"] = datetime.now().isoformat()
            self._save_single_entry(owner, key)
            return f"✅ 메모리 수정: {key} = {value}"
        return self.add(key, value, owner_id=owner_id)

    def clear(self, owner_id: Optional[str] = None) -> str:
        owner = _normalize_owner_id(owner_id)
        self.memories.pop(owner, None)
        self._clear_storage(owner)
        return "🧹 메모리가 초기화되었습니다."

    def format_for_prompt(self, owner_id: Optional[str] = None) -> str:
        """요청자의 메모리만 프롬프트에 싣는다.

        소유자를 모르면 아무것도 싣지 않는다. 공용도 싣지 않는다. 거기에는
        추천 질문 캐시처럼 사용자 정보가 아닌 것과 소유자를 알 수 없는 레거시
        행이 들어 있기 때문이다.
        """
        owned = self.memories.get(owner_id) if owner_id else None
        if not owned:
            return ""
        text = "## 사용자 정보 (Long-term Memory)\n"
        for k, v in owned.items():
            text += f"- **{k}**: {v['value']}\n"
        return text
```

`to_dict` 는 그대로 둔다. 2단 딕셔너리를 통째로 돌려주는 것이 그 함수의 원래 뜻이며, 호출자는 `chatbot/core.py:322` 의 `get_memory()` 하나뿐이고 그 함수를 부르는 API 라우트가 없다.

- [ ] **Step 7: 기존 SQLite 검사를 새 API 에 맞춘다**

`tests/chatbot/test_storage_sqlite.py:114-129` 의 `test_memory_manager_persists_and_restores_from_sqlite` 를 다음으로 바꾼다. 소유자를 주어 저장하고 같은 소유자로 돌려받는지 본다.

```python
def test_memory_manager_persists_and_restores_from_sqlite(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)

    memory = chatbot_core.MemoryManager(user_id="u1")
    memory.add("risk", "aggressive", owner_id="owner-a")

    db_path = resolve_chatbot_storage_db_path(tmp_path)
    assert db_path.exists()
    assert _count_rows(db_path, "chatbot_memories") == 1

    memory_file = tmp_path / "chatbot_memory.json"
    if memory_file.exists():
        memory_file.unlink()

    restored = chatbot_core.MemoryManager(user_id="u2")
    assert restored.get("risk", owner_id="owner-a")["value"] == "aggressive"
    assert restored.get("risk") is None
```

- [ ] **Step 8: 검사가 통과하는지 확인한다**

Run: `source venv/bin/activate && pytest tests/chatbot/ -v`

Expected: 전부 통과. `test_memory_owner_access.py` 는 10건이다.

- [ ] **Step 9: 커밋한다**

```bash
git add chatbot/storage_sqlite_memory.py chatbot/storage_memory_manager.py \
  tests/chatbot/test_memory_owner_access.py tests/chatbot/test_storage_sqlite.py
git commit -m "$(cat <<'EOF'
fix(챗봇): [CHAT-017] 메모리 저장소를 소유자별로 나눈다

MemoryManager 가 {owner_id: {key: record}} 2단 구조를 쓰고, 모든 메서드가
owner_id 를 선택 인자로 받는다. 생략하면 공용('')이므로 캐시 용도로 부르는
자리 넷은 고치지 않는다. format_for_prompt 는 요청자의 메모리만 싣고 공용은
싣지 않으므로, 추천 질문 캐시가 시스템 프롬프트를 오염시키던 것도 멈춘다.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_018BpBasN8thvGk5msXuhHUh
EOF
)"
```

---

### Task 4: `/memory` 명령과 `/clear all` 이 요청자의 것만 다루게 한다

**Files:**
- Modify: `chatbot/command_service.py:37-66` (`handle_clear_command`), `:121-129` (`render_memory_view`), `:145-168` (`handle_memory_write_action`), `:170-184` (`handle_memory_command`), `:238-247` (`handle_command` 의 `/memory` 분기)
- Modify: `tests/chatbot/test_command_service.py:60-107` (`_FakeMemory` 와 `_FakeBot.get_status`), `:129` 부근
- Test: `tests/chatbot/test_memory_owner_access.py` (덧붙임)

**Interfaces:**
- Consumes: Task 3 이 만든 `MemoryManager` 의 공개 API
- Produces: `handle_memory_command(bot: Any, args: list[str], owner_id: Optional[str] = None) -> str`, `render_memory_view(bot: Any, owner_id: Optional[str]) -> str`, `handle_memory_write_action(bot: Any, action: str, args: list[str], owner_id: Optional[str]) -> Optional[str]`

- [ ] **Step 1: 명령이 소유자를 지키는지 검사한다**

`tests/chatbot/test_memory_owner_access.py` 에 다음을 덧붙인다. 파일 머리의 import 에 `from chatbot.command_service import handle_memory_command` 를 더한다.

```python
class _FakeOwnedMemory:
    """소유자별 2단 구조를 흉내 낸다."""

    def __init__(self):
        self.store: dict[str, dict[str, dict]] = {}

    def view(self, owner_id=None):
        return self.store.get(owner_id or "", {})

    def add(self, key, value, owner_id=None):
        self.store.setdefault(owner_id or "", {})[key] = {"value": value}
        return "OK_ADD"

    def clear(self, owner_id=None):
        self.store.pop(owner_id or "", None)
        return "OK_CLEAR"


class _MemoryOnlyBot:
    def __init__(self):
        self.memory = _FakeOwnedMemory()


def test_memory_command_shows_only_requesting_owner():
    """/memory view 는 요청자의 메모리만 보여 준다."""
    bot = _MemoryOnlyBot()
    bot.memory.add("보유종목", "삼성전자", owner_id="owner-a")

    assert "삼성전자" in handle_memory_command(bot, ["view"], owner_id="owner-a")
    assert "저장된 메모리가 없습니다" in handle_memory_command(bot, ["view"], owner_id="owner-b")


def test_memory_command_refuses_without_owner():
    """소유자를 모르는 요청은 공용 영역에 닿지 못한다."""
    bot = _MemoryOnlyBot()
    bot.memory.add("daily_suggestions_default_empty", [{"prompt": "질문"}])

    response = handle_memory_command(bot, ["view"], owner_id=None)
    assert response.startswith("⚠️")
    assert "daily_suggestions" not in response


def test_memory_help_works_without_owner():
    """도움말은 소유자가 없어도 볼 수 있다."""
    bot = _MemoryOnlyBot()
    assert "메모리 명령어 도움말" in handle_memory_command(bot, [], owner_id=None)
    assert "메모리 명령어 도움말" in handle_memory_command(bot, ["help"], owner_id=None)
```

- [ ] **Step 2: 검사가 실패하는지 확인한다**

Run: `source venv/bin/activate && pytest tests/chatbot/test_memory_owner_access.py -v`

Expected: 새 검사 3건이 FAIL. `handle_memory_command` 가 아직 `owner_id` 키워드를 받지 않아 `TypeError` 가 난다.

- [ ] **Step 3: `/memory` 계열에 소유자를 전달하고 진입에서 판정한다**

`chatbot/command_service.py` 의 세 함수를 다음으로 바꾼다.

```python
def render_memory_view(bot: Any, owner_id: Optional[str]) -> str:
    memories = bot.memory.view(owner_id)
    if not memories:
        return "📭 저장된 메모리가 없습니다."

    lines = ["🧠 **저장된 메모리**"]
    for key in sorted(memories.keys()):
        value = _normalize_memory_value(memories[key])
        lines.append(f"- `{key}`: {value}")
    return "\n".join(lines)
```

```python
def handle_memory_write_action(
    bot: Any,
    action: str,
    args: list[str],
    owner_id: Optional[str],
) -> Optional[str]:
    """메모리 쓰기 액션(add/update/remove/clear)을 처리한다."""
    action = action.lower()

    if action == "clear":
        return bot.memory.clear(owner_id)

    if action in {"add", "update"}:
        if len(args) < 2:
            return "⚠️ key/value를 함께 입력해주세요."
        key = args[0]
        value = " ".join(args[1:])
        if action == "add":
            return bot.memory.add(key, value, owner_id=owner_id)
        return bot.memory.update(key, value, owner_id=owner_id)

    if action == "remove":
        if not args:
            return "⚠️ 삭제할 key를 입력해주세요."
        return bot.memory.remove(args[0], owner_id=owner_id)

    return None
```

```python
def handle_memory_command(bot: Any, args: list[str], owner_id: Optional[str] = None) -> str:
    """`/memory` 명령 처리. 요청자의 메모리만 다룬다.

    소유자를 모르면 거부한다. 그대로 진행하면 공용 영역에 닿는데, 거기에는
    추천 질문 캐시와 소유자를 알 수 없는 레거시 행이 들어 있다.
    """
    if not args:
        return render_memory_help()

    action = args[0].lower()
    if action in {"help", "?", "h"}:
        return render_memory_help()

    if not owner_id:
        return "⚠️ 사용자를 식별할 수 없어 메모리를 다루지 않았습니다. 페이지를 새로고침한 뒤 다시 시도해 주세요."

    if action == "view":
        return render_memory_view(bot, owner_id)

    result = handle_memory_write_action(bot, action, args[1:], owner_id)
    if result is not None:
        return result
    return f"⚠️ 알 수 없는 memory 명령입니다: `{action}`\n{render_memory_help()}"
```

그리고 `handle_command` 의 `/memory` 분기를 고친다.

```python
    if root == "/memory":
        return handle_memory_command(bot, parts[1:], owner_id)
```

- [ ] **Step 4: `/clear all` 이 요청자의 메모리를 다시 지우게 한다**

`handle_clear_command` 의 docstring 과 본문을 다음으로 바꾼다.

```python
def handle_clear_command(
    bot: Any,
    parts: list[str],
    session_id: Optional[str],
    owner_id: Optional[str] = None,
) -> str:
    """`/clear` 명령 처리.

    `/clear all` 은 종전에 history.clear_all() 과 memory.clear() 를 불러 **모든
    사용자의** 대화와 메모리를 지웠다. 이 명령은 화면의 명령어 목록에 노출되어
    있어 누구든 고를 수 있었다. 이제는 요청자 자신의 대화와 메모리만 지운다.
    """
    subcommand = parts[1].lower() if len(parts) > 1 else ""
    if subcommand == "all":
        if not owner_id:
            return "⚠️ 대화를 식별할 수 없어 초기화하지 않았습니다. 페이지를 새로고침한 뒤 다시 시도해 주세요."
        removed = bot.history.clear_for_owner(owner_id)
        bot.memory.clear(owner_id)
        bot._data_cache = None
        if hasattr(bot, "_cache_timestamp"):
            bot._cache_timestamp = None
        return f"🧹 내 대화 {removed}건과 메모리, 데이터 캐시를 초기화했습니다."

    if clear_current_session_messages(bot, session_id):
        return "🧹 현재 대화 세션이 초기화되었습니다."
    return "⚠️ 초기화할 현재 세션이 없습니다."
```

- [ ] **Step 5: 기존 명령 검사를 새 API 에 맞춘다**

`tests/chatbot/test_command_service.py` 의 `_FakeMemory` 를 소유자를 받는 형태로 바꾼다. `view`, `add`, `update`, `remove`, `clear` 다섯 메서드에 `owner_id=None` 키워드를 더하고, 저장은 `self.store.setdefault(owner_id or "", {})` 에 넣는다. `_FakeBot.get_status` 의 `memory_count` 를 `len(self.memory.view(owner_id))` 로 바꾼다. `:129` 의 `assert bot.memory.cleared is False` 는 `/clear all` 이 이제 메모리를 지우므로 `is True` 로 바꾸고, 그 검사가 `owner_id` 를 주어 부르는지 확인한다.

- [ ] **Step 6: 검사가 통과하는지 확인한다**

Run: `source venv/bin/activate && pytest tests/chatbot/ -v`

Expected: 전부 통과. `test_memory_owner_access.py` 는 13건이다.

- [ ] **Step 7: 커밋한다**

```bash
git add chatbot/command_service.py tests/chatbot/test_command_service.py \
  tests/chatbot/test_memory_owner_access.py
git commit -m "$(cat <<'EOF'
fix(챗봇): [CHAT-017] /memory 명령이 요청자의 메모리만 다루게 한다

소유자를 모르는 요청은 공용 영역에 닿지 못하도록 진입에서 거부한다.
/clear all 이 요청자의 메모리를 다시 지운다. [CHAT-016] 이 「내 메모리만」
지울 방법이 없어 뺐던 호출인데, 이제 방법이 생겼다.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_018BpBasN8thvGk5msXuhHUh
EOF
)"
```

---

### Task 5: 소유자를 프롬프트 조립 경로까지 흘려보낸다

**Files:**
- Modify: `chatbot/payload_service.py:38-72` (`compose_system_prompt`), `:99-146` (`build_chat_payload`)
- Modify: `chatbot/core_payload_mixin.py:31-53` (`_compose_system_prompt`), `:74-91` (`_build_chat_payload`)
- Modify: `chatbot/chat_handlers.py:73` 과 `:160` (`bot._build_chat_payload` 호출 두 곳)
- Modify: `chatbot/core.py:337-344` (`get_status`)
- Modify: `tests/chatbot/test_payload_service.py:36-38` (`_FakeMemory`)
- Test: `tests/chatbot/test_memory_owner_access.py` (덧붙임)

**Interfaces:**
- Consumes: Task 3 이 만든 `format_for_prompt(owner_id)`
- Produces: `compose_system_prompt(..., owner_id: Optional[str] = None)` 과 `build_chat_payload(..., owner_id: Optional[str] = None)`. 두 함수 모두 `owner_id` 를 **마지막 키워드 인자**로 받는다.

- [ ] **Step 1: 프롬프트 조립이 소유자를 쓰는지 검사한다**

`tests/chatbot/test_memory_owner_access.py` 에 다음을 덧붙인다. 파일 머리의 import 에 `from chatbot.payload_service import compose_system_prompt` 를 더한다.

```python
class _PromptFakeMemory:
    def __init__(self):
        self.seen_owner_ids: list = []

    def format_for_prompt(self, owner_id=None):
        self.seen_owner_ids.append(owner_id)
        return "MEM" if owner_id == "owner-a" else ""


class _PromptFakeBot:
    def __init__(self):
        self.memory = _PromptFakeMemory()

    def _detect_stock_query(self, user_message):
        _ = user_message
        return ""


def test_compose_system_prompt_passes_owner_to_memory():
    """프롬프트 조립이 요청자의 소유자 ID 를 메모리에 그대로 넘긴다."""
    bot = _PromptFakeBot()

    owned = compose_system_prompt(
        bot=bot,
        user_message="질문",
        target_model_name="gemini-2.0-flash-lite",
        market_data={},
        vcp_data=[],
        sector_scores={},
        watchlist=None,
        persona=None,
        additional_context="",
        owner_id="owner-a",
    )
    other = compose_system_prompt(
        bot=bot,
        user_message="질문",
        target_model_name="gemini-2.0-flash-lite",
        market_data={},
        vcp_data=[],
        sector_scores={},
        watchlist=None,
        persona=None,
        additional_context="",
        owner_id="owner-b",
    )

    assert bot.memory.seen_owner_ids == ["owner-a", "owner-b"]
    assert "MEM" in owned
    assert "MEM" not in other
```

- [ ] **Step 2: 검사가 실패하는지 확인한다**

Run: `source venv/bin/activate && pytest tests/chatbot/test_memory_owner_access.py -v`

Expected: 새 검사 1건이 FAIL. `compose_system_prompt() got an unexpected keyword argument 'owner_id'` 가 난다.

- [ ] **Step 3: `payload_service` 에 소유자를 더한다**

`compose_system_prompt` 의 시그니처 마지막에 `owner_id: Optional[str] = None` 을 더하고, 메모리 조회부를 다음으로 바꾼다.

```python
    memory_text = ""
    if hasattr(bot.memory, "format_for_prompt"):
        memory_text = bot.memory.format_for_prompt(owner_id)
```

`build_chat_payload` 의 시그니처 마지막에도 `owner_id: Optional[str] = None` 을 더하고, `bot._compose_system_prompt(...)` 호출에 `owner_id=owner_id` 를 넘긴다.

- [ ] **Step 4: 믹스인과 진입점에 소유자를 더한다**

`chatbot/core_payload_mixin.py` 의 `_compose_system_prompt` 와 `_build_chat_payload` 시그니처 마지막에 각각 `owner_id: Optional[str] = None` 을 더하고, 대응하는 `_impl` 호출에 `owner_id=owner_id` 를 넘긴다.

`chatbot/chat_handlers.py` 의 `bot._build_chat_payload(...)` 호출 두 곳(`:73`, `:160`)에 `owner_id=owner_id` 를 더한다. 두 함수 모두 이미 `owner_id` 파라미터를 받고 있으므로 그 값을 그대로 넘기면 된다.

- [ ] **Step 5: `get_status` 의 메모리 개수를 요청자 기준으로 센다**

`chatbot/core.py:337-344` 의 `get_status` 에서 `memory_count` 를 다음으로 바꾼다. 세션 개수가 이미 「소유자가 없으면 0」 규칙을 쓰고 있으므로 메모리도 같게 맞춘다.

```python
            "memory_count": len(self.memory.view(owner_id)) if owner_id else 0,
```

- [ ] **Step 6: 기존 payload 검사를 새 API 에 맞춘다**

`tests/chatbot/test_payload_service.py:36-38` 의 `_FakeMemory.format_for_prompt` 가 `owner_id=None` 키워드를 받도록 고친다.

```python
class _FakeMemory:
    def format_for_prompt(self, owner_id=None):
        _ = owner_id
        return "MEM"
```

- [ ] **Step 7: 전체 검증을 돌린다**

Run: `source venv/bin/activate && pytest`

Expected: 전부 통과. 종전 기준은 1,680 통과 2 skipped 였고, 이 계획이 더하는 검사만큼 늘어난다.

Run: `cd frontend && npx vitest run`

Expected: 279 통과. 프런트엔드를 건드리지 않으므로 숫자가 그대로여야 한다.

- [ ] **Step 8: 커밋한다**

```bash
git add chatbot/payload_service.py chatbot/core_payload_mixin.py \
  chatbot/chat_handlers.py chatbot/core.py \
  tests/chatbot/test_payload_service.py tests/chatbot/test_memory_owner_access.py
git commit -m "$(cat <<'EOF'
fix(챗봇): [CHAT-017] 요청자의 소유자 ID 를 프롬프트 조립까지 흘려보낸다

chat_handlers 가 이미 받고 있던 owner_id 를 _build_chat_payload 를 거쳐
format_for_prompt 까지 넘긴다. get_status 의 메모리 개수도 요청자 기준으로
센다. 세션 개수가 쓰던 「소유자가 없으면 0」 규칙과 같게 맞춘 것이다.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_018BpBasN8thvGk5msXuhHUh
EOF
)"
```

---

## 검증 명령 모음

```bash
source venv/bin/activate && pytest              # 전체 (저장소 루트에서)
source venv/bin/activate && pytest tests/chatbot/ -v   # 이번 범위
cd frontend && npx vitest run                   # 회귀 확인용
```

`npm run test` 는 watch 모드라 끝나지 않으므로 쓰지 않는다. `npx vitest` 에 `--root frontend` 를 주면 실패하므로 반드시 `cd frontend` 를 서브셸로 감싸 실행한다.

## Self-Review

**1. 사양 대비 빠짐** — `[CHAT-017]` 의 체크박스 다섯 개를 대조했다.

| 체크박스 | 작업 |
|---|---|
| 메모리 저장과 조회를 소유자별로 나눔. 기존 행을 어떻게 다룰지 먼저 정함 | Task 1(기존 행 → 공용), Task 2, Task 3 |
| `format_for_prompt` 가 요청자의 메모리만 넣도록 고침 | Task 3 Step 6, Task 5 |
| `/memory view` 와 쓰기 명령이 요청자의 것만 다루도록 고침 | Task 4 |
| `/clear all` 이 요청자의 메모리를 다시 지우도록 되살림 | Task 4 Step 4 |
| 소유자가 다른 메모리가 프롬프트와 조회 양쪽에서 빠지는지 pytest 로 고정 | Task 3 Step 1 의 `test_format_for_prompt_excludes_other_owners` 와 `test_view_excludes_other_owners` |

빠진 것이 없다.

**2. 미완성 표현** — 「적절히 처리한다」, 「TODO」, 「나중에」 같은 표현이 없는지 훑었다. 모든 단계에 실제 코드가 들어 있다. Task 4 Step 5 와 Task 5 Step 6 은 기존 테스트를 고치는 단계라 코드 전문 대신 무엇을 어떻게 바꾸는지 문장으로 적었는데, 대상 파일과 줄 번호와 바꿀 값이 모두 명시되어 있다.

**3. 타입 일관성** — 작업 사이를 오가는 이름을 대조했다.

- `PUBLIC_OWNER_ID` 는 Task 3 이 정의하고 Task 1 의 SQL 리터럴 `''` 과 값이 같다.
- `load_memories_from_sqlite` 의 반환형은 Task 2 에서 `Dict[str, Dict[str, Any]]` 로 바뀌고 Task 3 의 `self.memories` 가 그 형태를 그대로 받는다.
- `upsert_memory_entry_in_sqlite` 와 `delete_memory_entry_in_sqlite` 는 Task 2 에서 `owner_id` 를 두 번째 위치 인자로 받고, Task 3 은 키워드로 부른다. 위치와 키워드 어느 쪽으로도 동작한다.
- `clear_memories_in_sqlite` 의 `owner_id` 는 키워드 전용이며 Task 3 의 `_clear_storage` 가 키워드로 부른다.
- `format_for_prompt(owner_id)` 는 Task 3 이 정의하고 Task 5 가 위치 인자로 부른다. Task 5 의 `_PromptFakeMemory` 도 같은 시그니처다.
- `handle_memory_command(bot, args, owner_id)` 는 Task 4 가 정의하고 같은 작업의 `handle_command` 가 위치 인자로 부른다.

어긋난 곳이 없다.

## 실행 방식

이 계획은 dev-cycle 사이클 안에서 실행되므로 `subagent-driven-development` 나 `executing-plans` 로 넘기지 않는다. dev-cycle 의 [2] 구현이 Task 1 부터 Task 5 까지를 차례로 수행하고, 그 뒤 [2] 의 3번이 정한 T3 리뷰 세 종(`/ponytail-review` → `feature-dev:code-reviewer` → `/review`)을 순서대로 돌린다. 커밋은 dev-cycle [4] 마감의 규칙을 따르므로, 위 각 Task 의 커밋 단계는 구현 단위를 나누는 안내로만 쓰고 실제 커밋은 검증과 리뷰를 마친 뒤 [3] 검증의 5번에서 한 번에 만든다.
