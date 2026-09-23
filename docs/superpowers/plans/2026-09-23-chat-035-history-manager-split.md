# HistoryManager 책임 분리 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `chatbot/storage.py` 의 `HistoryManager` 에서 레거시 스냅샷·읽기 캐시·델타 장부를 상태를 가진 부품으로 떼어 내고, 동작은 한 가지도 바꾸지 않는다.

**Architecture:** 새 모듈 `chatbot/storage_history_parts.py` 에 잠금 없는 클래스 세 개와 서명 함수 하나를 둔다. `HistoryManager` 는 세 부품을 조립하고, 유일한 `RLock` 을 쥔 채로만 부품을 부른다. 외부가 `hasattr` 로 부르는 비공개 메서드 네 개는 이름을 유지한 위임으로 남긴다.

**Tech Stack:** Python 3.11, pytest, SQLite(기존 헬퍼 그대로)

**Spec:** `docs/superpowers/specs/2026-09-23-chat-035-history-manager-split-design.md`

## Global Constraints

- 동작 변화 0. `_save`·`_reload_sessions`·`_load`·`_restore_lost_messages_from_snapshot` 의 분기와 호출 순서를 그대로 옮긴다.
- 잠금은 `HistoryManager._lock`(RLock) 하나. 부품에 잠금을 두지 않는다.
- `_mark_session_changed`·`_invalidate_message_cache`·`_invalidate_session_list_cache`·`_save` 는 이름과 `@locked` 를 유지한다(`chatbot/command_service.py:31-38`·`:103-107`, `chatbot/session_access.py:30-37` 이 `hasattr` 로 부른다).
- 테스트는 내부 접근 경로만 바꾸고 기대값은 바꾸지 않는다. 하위호환 별칭 속성을 만들지 않는다.
- `_SANITIZED_MESSAGES_CACHE_MAX_ENTRIES`·`_SESSION_LIST_CACHE_MAX_ENTRIES` 상수와 `sanitize_session_messages`·`has_meaningful_user_message` 호출은 `chatbot/storage.py` 에 남긴다. 테스트가 이 이름들을 `chatbot.storage` 모듈에서 몽키패치한다(`test_history_manager_sync.py:161·179·235·254·287`).
- `chatbot/storage.py` 는 `MemoryManager` 를 계속 재수출한다(`chatbot/core.py:43`).
- 캐시 상한 상수는 prune 때가 아니라 `HistoryManager` 생성 때 한 번 읽는다. 기동 뒤 상수를 바꾸는 운영 경로가 없고 테스트는 생성 전에 패치하므로 동작 변화로 보지 않는다(critic 참고 3).
- 원본 `data/`·`.env` 를 열지 않고, 3500·5501 에 요청하지 않으며, 실제 LLM 을 호출하지 않는다.

---

### Task 1: 부품 모듈과 단위 검사

**Files:**
- Create: `chatbot/storage_history_parts.py`
- Test: `tests/chatbot/test_storage_history_parts_refactor.py`

**Interfaces:**
- Produces:
  - `LegacySnapshot(file_path: Path, interval_seconds: float)`; 속성 `file_path`, `interval_seconds`, `last_monotonic: Optional[float]`; `LegacySnapshot.from_env(file_path) -> LegacySnapshot`; `write(data: Dict[str, Any]) -> None`; `sync(data, force: bool = False) -> bool`
  - `HistoryReadCache(messages_max_entries: int, session_list_max_entries: int)`; 속성 `messages`, `session_list`, `session_list_version`; `get_messages(session_id, fingerprint) -> Optional[list]`; `put_messages(session_id, fingerprint, sanitized) -> list`; `get_session_list(owner_id) -> Optional[list]`; `put_session_list(owner_id, sessions) -> list`; `invalidate_messages(session_id=None) -> None`; `invalidate_session_list() -> None`
  - `SessionDeltaLedger()`; 속성 `changed: set[str]`, `deleted: set[str]`, `clear_all: bool`; `mark_changed(id)`, `mark_deleted(id)`, `mark_clear_all()`, 프로퍼티 `has_delta -> bool`, `reset()`
  - `storage_signature(db_path: Path, file_path: Path) -> Any`

- [ ] **Step 1: 실패하는 검사 작성** — `tests/chatbot/test_storage_history_parts_refactor.py`

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HistoryManager 부품의 분기 검사([CHAT-035])."""

import json
import sqlite3

import pytest

import chatbot.storage_history_parts as parts
from chatbot.storage_history_parts import (
    HistoryReadCache,
    LegacySnapshot,
    SessionDeltaLedger,
    storage_signature,
)


def test_delta_ledger_keeps_latest_intent_per_session():
    ledger = SessionDeltaLedger()
    ledger.mark_changed("")
    assert not ledger.has_delta
    ledger.mark_changed("a")
    ledger.mark_deleted("a")
    assert (ledger.changed, ledger.deleted) == (set(), {"a"})
    ledger.mark_changed("a")
    assert (ledger.changed, ledger.deleted) == ({"a"}, set())
    ledger.mark_clear_all()
    assert ledger.clear_all and not ledger.changed and not ledger.deleted
    # 종전 동작 그대로: 변경 표시가 전체 삭제 표시를 내린다
    ledger.mark_changed("b")
    assert ledger.clear_all is False
    ledger.reset()
    assert not ledger.has_delta


def test_legacy_snapshot_writes_only_when_due(tmp_path, monkeypatch):
    now = {"t": 100.0}
    monkeypatch.setattr(parts.time, "monotonic", lambda: now["t"])
    snapshot = LegacySnapshot(tmp_path / "history.json", interval_seconds=15.0)
    assert snapshot.sync({"a": {}}) is True
    assert snapshot.sync({"b": {}}) is False
    assert snapshot.sync({"c": {}}, force=True) is True
    now["t"] += 15.0
    assert snapshot.sync({}) is True
    assert json.loads((tmp_path / "history.json").read_text(encoding="utf-8")) == {}
    snapshot.interval_seconds = 0.0
    assert snapshot.sync({"d": {}}) is True


@pytest.mark.parametrize("raw, expected", [("3", 3.0), ("-1", 0.0), ("abc", 15.0)])
def test_legacy_snapshot_interval_from_env(monkeypatch, tmp_path, raw, expected):
    monkeypatch.setenv("CHATBOT_HISTORY_LEGACY_SNAPSHOT_INTERVAL_SECONDS", raw)
    assert LegacySnapshot.from_env(tmp_path / "h.json").interval_seconds == expected


def test_read_cache_returns_copies_and_evicts_least_recent():
    cache = HistoryReadCache(messages_max_entries=2, session_list_max_entries=2)
    returned = cache.put_messages("s1", ("t1", 1), [{"role": "user", "parts": [{"text": "x"}]}])
    returned[0]["parts"][0]["text"] = "changed"
    assert cache.get_messages("s1", ("t1", 1))[0]["parts"][0]["text"] == "x"
    assert cache.get_messages("s1", ("t1", 2)) is None
    cache.put_messages("s2", ("t2", 1), [])
    cache.get_messages("s1", ("t1", 1))
    cache.put_messages("s3", ("t3", 1), [])
    assert list(cache.messages) == ["s1", "s3"]

    cache.put_session_list("owner", [{"id": "s1"}])
    assert cache.get_session_list("owner") == [{"id": "s1"}]
    cache.invalidate_session_list()
    assert cache.get_session_list("owner") is None
    assert cache.session_list_version == 1


def test_storage_signature_prefers_sqlite_files(tmp_path):
    db_path = tmp_path / "chatbot_storage.db"
    json_path = tmp_path / "chatbot_history.json"
    assert storage_signature(db_path, json_path) is None
    json_path.write_text("{}", encoding="utf-8")
    assert isinstance(storage_signature(db_path, json_path)[0], int)  # JSON 한 파일의 (inode, mtime, size)
    sqlite3.connect(db_path).close()
    db_sig, wal_sig, shm_sig = storage_signature(db_path, json_path)
    assert db_sig is not None and wal_sig is None and shm_sig is None
```

- [ ] **Step 2: 실패 확인**

Run: `venv/bin/python -m pytest tests/chatbot/test_storage_history_parts_refactor.py -q -p no:cacheprovider`
Expected: 수집 오류 `ModuleNotFoundError: No module named 'chatbot.storage_history_parts'`

- [ ] **Step 3: 부품 모듈 작성** — `chatbot/storage_history_parts.py`

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HistoryManager 가 조립하는 부품([CHAT-035])

세 클래스 모두 잠금이 없다. HistoryManager 의 RLock 을 쥔 채로만 부른다. 잠금을 부품마다
두면 부품 사이의 상태가 서로 다른 시점을 보게 되어 [CHAT-033] 같은 경합이 다시 생긴다.
"""

import logging
import os
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, Optional

from .storage_history_helpers import atomic_write_json


logger = logging.getLogger(__name__)


def _path_signature(path: Path) -> tuple[int, int, int] | None:
    """스토리지 경로 변경 감지를 위한 시그니처(inode, mtime_ns, size)를 반환한다."""
    try:
        stat = path.stat()
        return (int(stat.st_ino), int(stat.st_mtime_ns), int(stat.st_size))
    except FileNotFoundError:
        return None
    except Exception as e:
        logger.error(f"Failed to stat storage path ({path}): {e}")
        return None


def storage_signature(db_path: Path, file_path: Path) -> Any:
    """SQLite(db·wal·shm) 서명을, 셋 다 없으면 JSON 파일 서명을 돌려준다. 재적재 판정에 쓴다."""
    sqlite_signature = tuple(
        _path_signature(path)
        for path in (
            db_path,
            db_path.with_name(f"{db_path.name}-wal"),
            db_path.with_name(f"{db_path.name}-shm"),
        )
    )
    if any(signature is not None for signature in sqlite_signature):
        return sqlite_signature
    return _path_signature(file_path)


class LegacySnapshot:
    """레거시 JSON 스냅샷을 간격을 두고 쓴다. SQLite 가 정본이고 이 파일은 복구용 사본이다."""

    def __init__(self, file_path: Path, interval_seconds: float):
        self.file_path = file_path
        self.interval_seconds = interval_seconds
        self.last_monotonic: Optional[float] = None

    @classmethod
    def from_env(cls, file_path: Path) -> "LegacySnapshot":
        raw = os.getenv("CHATBOT_HISTORY_LEGACY_SNAPSHOT_INTERVAL_SECONDS", "15")
        try:
            value = float(raw)
            interval = value if value >= 0 else 0.0
        except (TypeError, ValueError):
            interval = 15.0
        return cls(file_path, interval)

    def write(self, data: Dict[str, Any]) -> None:
        """히스토리 파일을 원자적으로 저장해 부분 저장/빈 파일 상태를 방지한다."""
        atomic_write_json(self.file_path, data)

    def sync(self, data: Dict[str, Any], force: bool = False) -> bool:
        due = (
            force
            or self.interval_seconds <= 0
            or self.last_monotonic is None
            or (time.monotonic() - self.last_monotonic) >= self.interval_seconds
        )
        if not due:
            return False
        self.write(data)
        self.last_monotonic = time.monotonic()
        return True


def _clone_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """캐시 오염 방지를 위해 메시지 목록을 복제해 반환한다."""
    cloned: list[dict[str, Any]] = []
    for msg in messages:
        cloned_parts = [
            dict(part) if isinstance(part, dict) else part
            for part in msg.get("parts", [])
        ]
        cloned_msg = {"role": msg.get("role", "user"), "parts": cloned_parts}
        if "timestamp" in msg:
            cloned_msg["timestamp"] = msg["timestamp"]
        cloned.append(cloned_msg)
    return cloned


def _prune(cache: OrderedDict[Any, Any], max_entries: int) -> None:
    normalized_max_entries = max(1, int(max_entries))
    while len(cache) > normalized_max_entries:
        cache.popitem(last=False)


class HistoryReadCache:
    """정제한 메시지와 세션 목록을 LRU 로 담는다. 돌려주는 값은 호출자가 고쳐도 되는 사본이다."""

    def __init__(self, messages_max_entries: int, session_list_max_entries: int):
        self.messages: OrderedDict[str, tuple[tuple[str, int], list[dict[str, Any]]]] = OrderedDict()
        self.session_list: OrderedDict[str | None, tuple[int, list[dict[str, Any]]]] = OrderedDict()
        self.session_list_version = 0
        self._messages_max_entries = messages_max_entries
        self._session_list_max_entries = session_list_max_entries

    def get_messages(self, session_id: str, fingerprint: tuple[str, int]) -> Optional[list[dict[str, Any]]]:
        cached = self.messages.get(session_id)
        if not cached or cached[0] != fingerprint:
            return None
        self.messages.move_to_end(session_id)
        return _clone_messages(cached[1])

    def put_messages(
        self, session_id: str, fingerprint: tuple[str, int], sanitized: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        self.messages[session_id] = (fingerprint, sanitized)
        self.messages.move_to_end(session_id)
        _prune(self.messages, self._messages_max_entries)
        return _clone_messages(sanitized)

    def get_session_list(self, owner_id: str | None) -> Optional[list[dict[str, Any]]]:
        cached = self.session_list.get(owner_id)
        if not cached or cached[0] != self.session_list_version:
            return None
        self.session_list.move_to_end(owner_id)
        return list(cached[1])

    def put_session_list(self, owner_id: str | None, sessions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self.session_list[owner_id] = (self.session_list_version, sessions)
        self.session_list.move_to_end(owner_id)
        _prune(self.session_list, self._session_list_max_entries)
        return list(sessions)

    def invalidate_messages(self, session_id: str | None = None) -> None:
        if session_id is None:
            self.messages.clear()
            return
        self.messages.pop(session_id, None)

    def invalidate_session_list(self) -> None:
        self.session_list.clear()
        self.session_list_version += 1


class SessionDeltaLedger:
    """다음 저장에서 SQLite 에 반영할 세션 변경·삭제·전체 삭제 표시를 모은다."""

    def __init__(self):
        self.changed: set[str] = set()
        self.deleted: set[str] = set()
        self.clear_all = False

    def mark_changed(self, session_id: str) -> None:
        if not session_id:
            return
        self.changed.add(session_id)
        self.deleted.discard(session_id)
        self.clear_all = False

    def mark_deleted(self, session_id: str) -> None:
        if not session_id:
            return
        self.deleted.add(session_id)
        self.changed.discard(session_id)

    def mark_clear_all(self) -> None:
        self.clear_all = True
        self.changed.clear()
        self.deleted.clear()

    @property
    def has_delta(self) -> bool:
        return self.clear_all or bool(self.changed) or bool(self.deleted)

    def reset(self) -> None:
        self.changed.clear()
        self.deleted.clear()
        self.clear_all = False
```

- [ ] **Step 4: 통과 확인**

Run: `venv/bin/python -m pytest tests/chatbot/test_storage_history_parts_refactor.py -q -p no:cacheprovider`
Expected: 7 passed

### Task 2: HistoryManager 가 부품을 쓰게 바꾸고 테스트 접근 경로를 옮긴다

**Files:**
- Modify: `chatbot/storage.py` (import 절, `__init__`, 45-296행의 내부 메서드, `get_all_sessions`·`get_messages`·CRUD 의 장부·캐시 호출)
- Modify: `tests/chatbot/test_history_manager_sync.py:194-197, 265-268, 315-318, 349, 363-367, 386-390`

**Interfaces:**
- Consumes: Task 1 의 네 이름 전부
- Produces: `HistoryManager._snapshot: LegacySnapshot`, `HistoryManager._cache: HistoryReadCache`, `HistoryManager._delta: SessionDeltaLedger`. 외부 계약(공개 메서드, `sessions`, 비공개 네 이름)은 그대로.

- [ ] **Step 1: 테스트 접근 경로를 먼저 옮긴다(RED)**

`tests/chatbot/test_history_manager_sync.py` 에서 다음만 바꾼다.

```python
# 194-197
    assert len(manager._cache.messages) == 2
    assert session_one in manager._cache.messages
    assert session_three in manager._cache.messages
    assert session_two not in manager._cache.messages
# 265-268
    assert len(manager._cache.session_list) == 2
    assert "owner-a" in manager._cache.session_list
    assert "owner-c" in manager._cache.session_list
    assert "owner-b" not in manager._cache.session_list
# 315-318: monkeypatch.setattr(reader, "_atomic_write", …) →
    monkeypatch.setattr(
        reader._snapshot,
        "write",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("legacy snapshot rewrite should be skipped")),
    )
# 349
    monkeypatch.setattr(manager._snapshot, "write", lambda *_a, **_k: None)
# 363-367
    manager._snapshot.interval_seconds = 3_600.0
    manager._snapshot.last_monotonic = time.monotonic()
    monkeypatch.setattr(
        manager._snapshot,
        "write",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("legacy snapshot write should be skipped")),
    )
# 386-390
    writer._snapshot.interval_seconds = 3_600.0
    writer._snapshot.last_monotonic = time.monotonic()
    monkeypatch.setattr(
        writer._snapshot,
        "write",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("legacy snapshot write should be skipped")),
    )
```

Run: `venv/bin/python -m pytest tests/chatbot/test_history_manager_sync.py -q -p no:cacheprovider`
Expected: 위 여섯 테스트가 `AttributeError: 'HistoryManager' object has no attribute '_cache'`(또는 `_snapshot`)로 실패

- [ ] **Step 2: `chatbot/storage.py` 를 부품 조립으로 바꾼다**

import 절: `os`, `time`, `OrderedDict`, `atomic_write_json`, `backup_corrupt_history` 를 지우고 다음을 더한다.

```python
from .storage_history_parts import (
    HistoryReadCache,
    LegacySnapshot,
    SessionDeltaLedger,
    storage_signature,
)
```

`__init__` 의 상태 필드 부분(52-65행)을 다음으로 바꾼다.

```python
        self.db_path = resolve_chatbot_storage_db_path(self.data_dir)
        self._snapshot = LegacySnapshot.from_env(self.file_path)
        self._cache = HistoryReadCache(
            messages_max_entries=_SANITIZED_MESSAGES_CACHE_MAX_ENTRIES,
            session_list_max_entries=_SESSION_LIST_CACHE_MAX_ENTRIES,
        )
        self._delta = SessionDeltaLedger()
        self._last_reload_signature: Any = None
        self._sync_snapshot_on_load = True
```

(`self._lock` 과 그 위 ponytail 주석, `_load()` 이후 네 줄은 그대로 둔다. `self._get_file_signature()` 는 `storage_signature(self.db_path, self.file_path)` 로 바꾼다.)

지우는 메서드: `_resolve_legacy_snapshot_interval_seconds`, `_get_path_signature`, `_get_file_signature`, `_get_sqlite_storage_signature`, `_should_sync_legacy_snapshot`, `_sync_legacy_snapshot`, `_atomic_write`, `_backup_corrupt_history`, `_prune_ordered_cache`, `_mark_session_deleted`, `_mark_clear_all`, `_clone_sanitized_messages`.

호출 치환(파일 전체):

| 종전 | 새 코드 |
|---|---|
| `self._get_file_signature()` | `storage_signature(self.db_path, self.file_path)` |
| `self._sync_legacy_snapshot(x, force=…)` | `self._snapshot.sync(x, force=…)` |
| `self._mark_session_deleted(sid)` | `self._delta.mark_deleted(sid)` |
| `self._mark_clear_all()` | `self._delta.mark_clear_all()` |
| `_reload_sessions` 의 `self._sanitized_messages_cache.clear()` | `self._cache.invalidate_messages()` |

`_save` 의 장부 사용부:

```python
            has_delta = self._delta.has_delta
            ...
                sqlite_saved = (not has_delta) or apply_history_session_deltas_in_sqlite(
                    self.db_path,
                    sessions=self.sessions,
                    changed_session_ids=self._delta.changed,
                    deleted_session_ids=self._delta.deleted,
                    clear_all=self._delta.clear_all,
                    logger=logger,
                )
                ...
                force_snapshot = (
                    (not sqlite_saved)
                    or self._delta.clear_all
                    or bool(self._delta.deleted)
                )
                self._snapshot.sync(self.sessions, force=force_snapshot)
            self._last_reload_signature = (
                storage_signature(self.db_path, self.file_path) if sqlite_saved else None
            )
            self._delta.reset()
            return bool(sqlite_saved)
```

남기는 위임 세 개(이름과 `@locked` 유지):

```python
    @locked
    def _invalidate_message_cache(self, session_id: str | None = None) -> None:
        self._cache.invalidate_messages(session_id)

    @locked
    def _invalidate_session_list_cache(self) -> None:
        self._cache.invalidate_session_list()

    @locked
    def _mark_session_changed(self, session_id: str) -> None:
        self._delta.mark_changed(session_id)
```

`get_all_sessions` 의 캐시부:

```python
        self._reload_sessions()  # [Fix] Multi-worker Sync
        cached = self._cache.get_session_list(owner_id)
        if cached is not None:
            return cached
        ... (valid_sessions 계산과 정렬은 그대로, has_meaningful_user_message 호출도 그대로) ...
        return self._cache.put_session_list(owner_id, sorted_sessions)
```

`get_messages` 의 캐시부:

```python
        session = self.sessions.get(session_id)
        if session:
            fingerprint = (
                str(session.get("updated_at", "")),
                len(session.get("messages", [])),
            )
            cached = self._cache.get_messages(session_id, fingerprint)
            if cached is not None:
                return cached
            return self._cache.put_messages(session_id, fingerprint, sanitize_session_messages(session))
        return []
```

- [ ] **Step 3: 통과 확인**

Run: `venv/bin/python -m pytest tests/chatbot -q -p no:cacheprovider`
Expected: 269 passed(기준선 262 + 새 검사 7, critic 실측)

Run: `grep -nE '_pending_|_sanitized_messages_cache|[^_]_session_list_cache|_session_list_version|_legacy_snapshot|_atomic_write|_get_file_signature|_get_path_signature|_mark_session_deleted|_mark_clear_all|_sync_legacy_snapshot|_prune_ordered_cache|_clone_sanitized_messages|_backup_corrupt_history' chatbot/storage.py tests/chatbot/test_history_manager_sync.py`
Expected: 출력 없음(범위 밖 `storage_memory_manager.py`·`response_flow_stream.py` 의 같은 이름은 대상이 아니다)

### Task 3: 전체 검증과 리뷰

- [ ] **Step 1:** `venv/bin/python -m pytest -q -p no:cacheprovider` (원본 트리, `[INFRA-083]` 세션 끝 검사 포함) → exit 0
- [ ] **Step 2:** `/ponytail-review` → `closing-bet-reviewer`(`Agent`, `name` 필수, 읽기 전용, 3500·5501 요청 금지, `data/`·`.env` 열람 금지) → `/review`. 지적은 반영하고 TODO 체크에 기록한다.
- [ ] **Step 3:** QA 행렬 `docs/dev-cycle/qa/CHAT-035.md` 작성(`/qa-only`), 허용 경로만 스테이징하고 `git diff --cached --check` 통과 뒤 첫 커밋

```bash
git add chatbot/storage.py chatbot/storage_history_parts.py \
  tests/chatbot/test_history_manager_sync.py tests/chatbot/test_storage_history_parts_refactor.py \
  docs/dev-cycle/qa/CHAT-035.md docs/dev-cycle/TODO.md \
  docs/superpowers/plans/2026-09-23-chat-035-history-manager-split.md
git diff --cached --check && git commit -m "refactor(chatbot): [CHAT-035] split HistoryManager snapshot, read cache and delta ledger

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AeQQtEk7wbuVAnf9kCJmBN"
```

- [ ] **Step 4:** `/qa` 로 격리 사본 브라우저 실측(대화 생성 → 가짜 LLM 응답 수신 → 메시지 삭제 → 대화 삭제 → 새로고침). 결과를 QA 문서에 기록한다.
- [ ] **Step 5:** 월별·일별 아카이브 작성, TODO 항목 제거, 아카이브 커밋
