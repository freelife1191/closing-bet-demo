# [CHAT-003] 두 SQLite 캐시 모듈을 공용 골격으로 통합 — 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**목표:** `chatbot/runtime_stock_map_cache.py` 와 `chatbot/stock_context_cache.py` 에 두 벌로 존재하는 2단 캐시 골격을 `services/sqlite_ready_gate.py` 한 곳으로 모아, 스키마 복구와 프루닝 조건을 한 자리에서만 고치면 되도록 만듭니다.

**설계 방향:** 상태를 소유하는 두 클래스(`SqliteReadyGate`, `SeenKeyTracker`)와 상태가 없는 두 함수(`save_bounded_lru_entry`, `run_with_schema_recovery`)를 새 모듈에 둡니다. 두 캐시 모듈은 자기 테이블의 SQL 과 페이로드 직렬화만 남기고 나머지를 골격에 위임합니다. 기존 회귀 테스트가 모듈 전역을 monkeypatch 하므로, 골격은 상한 정수와 `sqlite_utils` 심볼을 **호출 시점에 인자로 받습니다**.

**기술 스택:** Python 3.11, 표준 라이브러리의 `sqlite3`·`threading`·`collections.OrderedDict`, 저장소의 기존 `services/sqlite_utils.py`, pytest.

**근거 문서:** `docs/dev-cycle/audits/AUDIT-CHAT.md` §2.1, `docs/dev-cycle/TODO.md` 의 `[CHAT-003]` 항목.

## 전역 제약

- 공개 함수 여덟 개의 시그니처를 바꾸지 않습니다. `file_signature`, `load_stock_map_cache`, `save_stock_map_cache`, `build_stock_maps`, `clear_stock_map_cache`, `load_cached_result_text`, `save_cached_result_text`, `clear_result_text_cache` 입니다.
- 기존 회귀 테스트 두 파일(`tests/chatbot/test_runtime_stock_map_cache_refactor.py` 14건, `tests/chatbot/test_stock_context_cache_refactor.py` 15건)을 **한 줄도 고치지 않고** 통과시킵니다.
- `services/sqlite_utils.py` 를 수정하지 않습니다. 스물한 개 모듈이 import 하는 공통 접속 계층이므로 건드리면 변경 파급이 저장소 전체가 됩니다.
- 테이블 스키마(`CREATE TABLE` 문의 컬럼 구성)와 SQL 의 의미를 바꾸지 않습니다. 이미 저장된 `runtime_cache.db` 와 어긋나면 마이그레이션 없이 되돌릴 수 없습니다.
- 새 프레임워크나 픽스처 계층을 들이지 않습니다. 기존 `tests/**/test_*_refactor.py` 형식을 따릅니다.
- 검증 명령은 `source venv/bin/activate && pytest` 입니다. 프런트엔드를 건드리지 않으므로 vitest 와 tsc 는 이 항목의 대상이 아닙니다.

---

## 왜 이렇게 나누는가

### 골격을 `services/sqlite_ready_gate.py` 에 두는 이유

같은 단일 비행 골격을 쓰는 모듈이 챗봇 두 개 말고도 아홉 개 더 있습니다.

```
services/kr_market_data_cache_sqlite_payload.py
services/kr_market_vcp_signals_cache.py
services/kr_market_jongga_payload_helpers.py
services/kr_market_realtime_price_cache.py
services/paper_trading_db_setup.py
chatbot/storage_sqlite_common.py
engine/signal_tracker_source_cache.py
engine/signal_tracker_analysis_source_cache.py
engine/kr_ai_stock_info_cache.py
```

표본으로 `engine/kr_ai_stock_info_cache.py:155-221` 을 대조하니 챗봇 두 모듈의 `_ensure_*` 와 글자 단위로 같았습니다. 골격을 `chatbot/` 아래에 두면 `engine/` 과 `services/` 가 나중에 그것을 쓸 때 계층이 역전됩니다.

그렇다고 `services/sqlite_utils.py` 안에 넣지도 않습니다. 그 파일은 564줄이고 티어 규칙이 「공통 접속 계층」으로 지정한 위험 경로입니다. 별도 파일로 두면 이번 변경에서 그 파일을 열 필요조차 없습니다.

### 이번 범위에서 제외하는 것

위의 아홉 개 모듈은 이번에 옮기지 않습니다. 항목이 정한 범위는 챗봇 두 모듈이고, 열한 개를 한꺼번에 옮기면 규모가 통제를 벗어납니다. 이 사실은 사이클 마감에서 `docs/dev-cycle/TODO.md` 에 후속 항목으로 올립니다.

### 기존 테스트가 만든 제약

두 회귀 테스트는 모듈 전역을 직접 조작합니다. 이 결합은 코드가 아니라 테스트가 만든 것이지만, 항목이 「기존 두 회귀 테스트가 그대로 통과」를 요구하므로 설계가 이것을 수용해야 합니다.

**`monkeypatch.setattr` 로 바꾸는 것** — 호출 시점에 모듈 전역에서 읽혀야 반영됩니다. 따라서 골격 함수의 **인자**로 받습니다.

| 이름 | runtime 쪽 | context 쪽 |
|---|---|---|
| 메모리 상한 | `_STOCK_MAP_MEMORY_MAX_ENTRIES` | `_RESULT_TEXT_MEMORY_MAX_ENTRIES` |
| 행 상한 | `_STOCK_MAP_SQLITE_MAX_ROWS` | `_RESULT_TEXT_SQLITE_MAX_ROWS` |
| 강제 프루닝 주기 | `_STOCK_MAP_SQLITE_PRUNE_FORCE_INTERVAL` | `_RESULT_TEXT_SQLITE_PRUNE_FORCE_INTERVAL` |
| sqlite_utils 심볼 | `connect_sqlite`, `run_sqlite_with_retry`, `sqlite_db_path_exists`, `prune_rows_by_updated_at_if_needed` | 같음 |

**직접 참조해 조작하는 가변 객체** — 같은 객체를 공유하면 됩니다. 골격 인스턴스가 소유하고 모듈 전역이 그 속성을 가리키는 별칭으로 둡니다. `set.clear()` 나 `OrderedDict.keys()` 가 양쪽에 그대로 반영됩니다.

| 이름 | runtime 쪽 | context 쪽 |
|---|---|---|
| 메모리 캐시 | `_STOCK_MAP_CACHE` | `_RESULT_TEXT_CACHE` |
| 조건 변수 | `_STOCK_MAP_SQLITE_READY_CONDITION` | `_RESULT_TEXT_SQLITE_READY_CONDITION` |
| 준비 완료 집합 | `_STOCK_MAP_SQLITE_READY` | `_RESULT_TEXT_SQLITE_READY` |
| 진행 중 집합 | `_STOCK_MAP_SQLITE_INIT_IN_PROGRESS` | `_RESULT_TEXT_SQLITE_INIT_IN_PROGRESS` |

**직접 호출하는 비공개 함수** — 이름과 시그니처가 남아야 합니다.

- `_ensure_stock_map_sqlite(db_path, logger)`
- `_ensure_result_text_sqlite_cache(db_path)`
- `_build_result_cache_key(path, *, dataset, ticker_padded)`

### 두 모듈에 남는 것

골격으로 옮기지 않고 각 모듈에 남기는 것은 서로 다른 부분입니다.

| 항목 | runtime_stock_map_cache | stock_context_cache |
|---|---|---|
| 테이블 이름 | `chatbot_stock_map_cache` | `chatbot_stock_context_cache` |
| 기본키 컬럼 | `source_path` | `cache_key` |
| 페이로드 컬럼 | `stock_map_json`, `ticker_map_json` | `dataset`, `ticker`, `payload_text` |
| 메모리 값 타입 | `tuple[tuple[int,int], dict, dict]` | `tuple[tuple[int,int], str]` |
| 캐시 키 구성 | 경로 정규화 하나 | `경로::dataset::ticker` 합성 |
| 메모리 조회 | 단일 키 | 다중 lookup 키 순회 후 정규 키로 승격 |
| 로거 | 공개 함수가 인자로 받음 | 모듈 상수 `LOGGER` |
| db 경로 계산 | `data_dir / "runtime_cache.db"` | `Path(normalize(data_dir)) / "runtime_cache.db"` |

`SELECT` 와 `INSERT ... ON CONFLICT` 문은 컬럼 구성이 다르므로 억지로 합치지 않습니다. 합치면 SQL 을 문자열로 조립하는 계층이 생겨 오히려 읽기 어려워집니다.

---

## 파일 구조

**신규**

- `services/sqlite_ready_gate.py` (약 170줄) — 2단 캐시 골격. 클래스 둘, 함수 둘, 예외 하나.
- `tests/services/test_sqlite_ready_gate_refactor.py` (약 150줄) — 골격 자체의 검사와 두 모듈의 동작 동등성 검사.

**수정**

- `chatbot/runtime_stock_map_cache.py` (484줄 → 약 330줄) — 골격 위임.
- `chatbot/stock_context_cache.py` (465줄 → 약 320줄) — 골격 위임.

**건드리지 않음**

- `services/sqlite_utils.py`
- `tests/chatbot/test_runtime_stock_map_cache_refactor.py`
- `tests/chatbot/test_stock_context_cache_refactor.py`
- `chatbot/runtime_setup_service.py`, `chatbot/stock_context.py` (공개 시그니처가 그대로이므로)

---

## Task 1: 공용 골격 모듈을 만든다

**파일:**
- 생성: `services/sqlite_ready_gate.py`
- 검사: `tests/services/test_sqlite_ready_gate_refactor.py`

**인터페이스:**
- 사용: `services.sqlite_utils` 의 `add_bounded_ready_key`, `normalize_sqlite_db_key`
- 제공:
  - `SqliteReadyGate(*, max_ready_entries: int = 2_048)` — 속성 `condition: threading.Condition`, `ready_keys: set[str]`, `in_progress_keys: set[str]`. 메서드 `invalidate(db_path_text: str) -> None`, `ensure(db_path_text: str, *, initialize: Callable[[], None], db_path_exists: Callable[[str], bool], run_with_retry: Callable[..., Any], retry_attempts: int, retry_delay_seconds: float, on_failure: Callable[[Exception], None]) -> bool`
  - `SeenKeyTracker(*, max_entries: int)` — 속성 `known_keys: OrderedDict[tuple[str, str], None]`. 메서드 `mark_seen(*, db_path_text: str, item_key: str) -> bool`, `discard_db(db_path_text: str) -> None`, `should_force_prune(interval: int) -> bool`, `clear() -> None`
  - `save_bounded_lru_entry(cache: OrderedDict, lock, key, value, *, max_entries: int) -> None`
  - `run_with_schema_recovery(operation, *, run_with_retry, retry_attempts, retry_delay_seconds, is_missing_table, recover)` — 성공하면 `operation` 의 반환값을 그대로 돌려주고, 복구 후 재시도에서도 실패하면 `SchemaRecoveryRetryError` 를 올린다
  - `SchemaRecoveryRetryError(Exception)`

- [ ] **1단계: 실패하는 검사를 쓴다**

`tests/services/test_sqlite_ready_gate_refactor.py` 를 만들고 다음을 넣습니다.

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sqlite_ready_gate 공용 골격 회귀 테스트

[CHAT-003] 에서 chatbot 의 두 캐시 모듈이 각자 갖고 있던 2단 캐시 골격을 이 모듈로
모았다. 준비 상태 단일 비행, LRU 상한, 신규 키 판정, 강제 프루닝 주기, 스키마 복구
재시도가 여기 한 곳에만 존재한다는 것을 고정한다.

근거: AUDIT-CHAT §2.1
"""

from __future__ import annotations

import os
import sys
import threading
import time
from collections import OrderedDict


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from services.sqlite_ready_gate import (  # noqa: E402
    SchemaRecoveryRetryError,
    SeenKeyTracker,
    SqliteReadyGate,
    run_with_schema_recovery,
    save_bounded_lru_entry,
)


def _run_immediately(operation, *, max_retries=0, retry_delay_seconds=0.0):
    """재시도 없이 한 번만 실행하는 run_with_retry 대역."""
    return operation()


def test_ready_gate_runs_initializer_once_under_concurrency(tmp_path):
    gate = SqliteReadyGate(max_ready_entries=8)
    db_path_text = str(tmp_path / "cache.db")
    call_count = 0
    call_lock = threading.Lock()

    def _initialize() -> None:
        nonlocal call_count
        with call_lock:
            call_count += 1
        # 두 번째 스레드가 대기 구간에 들어갈 시간을 준다.
        time.sleep(0.05)

    results: dict[str, bool] = {}

    def _worker(name: str) -> None:
        results[name] = gate.ensure(
            db_path_text,
            initialize=_initialize,
            db_path_exists=lambda _path: True,
            run_with_retry=_run_immediately,
            retry_attempts=0,
            retry_delay_seconds=0.0,
            on_failure=lambda _error: None,
        )

    threads = [threading.Thread(target=_worker, args=(f"t{i}",)) for i in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert all(results.values())
    assert call_count == 1
    assert gate.in_progress_keys == set()


def test_ready_gate_lets_waiter_retry_after_initializer_failure(tmp_path):
    gate = SqliteReadyGate(max_ready_entries=8)
    db_path_text = str(tmp_path / "cache.db")
    attempts = 0
    attempt_lock = threading.Lock()

    def _initialize() -> None:
        nonlocal attempts
        with attempt_lock:
            attempts += 1
            current = attempts
        time.sleep(0.05)
        if current == 1:
            raise RuntimeError("첫 초기화는 실패한다")

    results: dict[str, bool] = {}

    def _worker(name: str) -> None:
        results[name] = gate.ensure(
            db_path_text,
            initialize=_initialize,
            db_path_exists=lambda _path: True,
            run_with_retry=_run_immediately,
            retry_attempts=0,
            retry_delay_seconds=0.0,
            on_failure=lambda _error: None,
        )

    first = threading.Thread(target=_worker, args=("first",))
    first.start()
    time.sleep(0.01)
    second = threading.Thread(target=_worker, args=("second",))
    second.start()
    first.join()
    second.join()

    # 첫 초기화가 실패했으므로 뒤에 대기하던 쪽이 다시 초기화를 시도해야 한다.
    assert attempts == 2
    assert results["second"] is True
    assert gate.in_progress_keys == set()


def test_ready_gate_recovers_when_db_file_disappears(tmp_path):
    gate = SqliteReadyGate(max_ready_entries=8)
    db_path_text = str(tmp_path / "cache.db")
    exists = {"value": True}
    call_count = 0

    def _initialize() -> None:
        nonlocal call_count
        call_count += 1

    def _ensure() -> bool:
        return gate.ensure(
            db_path_text,
            initialize=_initialize,
            db_path_exists=lambda _path: exists["value"],
            run_with_retry=_run_immediately,
            retry_attempts=0,
            retry_delay_seconds=0.0,
            on_failure=lambda _error: None,
        )

    assert _ensure() is True
    assert call_count == 1

    # 준비 완료로 기록되어 있어도 파일이 사라졌으면 다시 만든다.
    assert _ensure() is True
    assert call_count == 1

    exists["value"] = False
    assert _ensure() is True
    assert call_count == 2


def test_ready_gate_invalidate_forces_reinitialization(tmp_path):
    gate = SqliteReadyGate(max_ready_entries=8)
    db_path_text = str(tmp_path / "cache.db")
    call_count = 0

    def _initialize() -> None:
        nonlocal call_count
        call_count += 1

    def _ensure() -> bool:
        return gate.ensure(
            db_path_text,
            initialize=_initialize,
            db_path_exists=lambda _path: True,
            run_with_retry=_run_immediately,
            retry_attempts=0,
            retry_delay_seconds=0.0,
            on_failure=lambda _error: None,
        )

    assert _ensure() is True
    gate.invalidate(db_path_text)
    assert _ensure() is True
    assert call_count == 2


def test_seen_key_tracker_reports_first_appearance_only(tmp_path):
    tracker = SeenKeyTracker(max_entries=8)
    db_path_text = str(tmp_path / "cache.db")

    assert tracker.mark_seen(db_path_text=db_path_text, item_key="a") is True
    assert tracker.mark_seen(db_path_text=db_path_text, item_key="a") is False
    assert tracker.mark_seen(db_path_text=db_path_text, item_key="b") is True


def test_seen_key_tracker_evicts_oldest_key_beyond_limit(tmp_path):
    tracker = SeenKeyTracker(max_entries=2)
    db_path_text = str(tmp_path / "cache.db")

    tracker.mark_seen(db_path_text=db_path_text, item_key="a")
    tracker.mark_seen(db_path_text=db_path_text, item_key="b")
    tracker.mark_seen(db_path_text=db_path_text, item_key="c")

    # a 가 밀려났으므로 다시 신규로 판정되어야 한다.
    assert tracker.mark_seen(db_path_text=db_path_text, item_key="a") is True
    assert len(tracker.known_keys) == 2


def test_seen_key_tracker_discard_db_drops_only_that_database(tmp_path):
    tracker = SeenKeyTracker(max_entries=8)
    first_db = str(tmp_path / "first.db")
    second_db = str(tmp_path / "second.db")

    tracker.mark_seen(db_path_text=first_db, item_key="a")
    tracker.mark_seen(db_path_text=second_db, item_key="a")
    tracker.discard_db(first_db)

    assert tracker.mark_seen(db_path_text=first_db, item_key="a") is True
    assert tracker.mark_seen(db_path_text=second_db, item_key="a") is False


def test_seen_key_tracker_forces_prune_on_interval():
    tracker = SeenKeyTracker(max_entries=8)

    results = [tracker.should_force_prune(3) for _ in range(6)]

    assert results == [False, False, True, False, False, True]


def test_seen_key_tracker_clear_resets_counter_and_keys(tmp_path):
    tracker = SeenKeyTracker(max_entries=8)
    db_path_text = str(tmp_path / "cache.db")

    tracker.mark_seen(db_path_text=db_path_text, item_key="a")
    tracker.should_force_prune(2)
    tracker.clear()

    assert tracker.known_keys == OrderedDict()
    # 카운터가 0 으로 돌아갔으므로 첫 호출은 다시 False 다.
    assert tracker.should_force_prune(2) is False


def test_save_bounded_lru_entry_evicts_oldest():
    cache: OrderedDict[str, int] = OrderedDict()
    lock = threading.Lock()

    for index, key in enumerate(("a", "b", "c")):
        save_bounded_lru_entry(cache, lock, key, index, max_entries=2)

    assert list(cache.keys()) == ["b", "c"]


def test_save_bounded_lru_entry_treats_non_positive_limit_as_one():
    cache: OrderedDict[str, int] = OrderedDict()
    lock = threading.Lock()

    save_bounded_lru_entry(cache, lock, "a", 1, max_entries=0)
    save_bounded_lru_entry(cache, lock, "b", 2, max_entries=0)

    assert list(cache.keys()) == ["b"]


def test_run_with_schema_recovery_returns_value_without_recovery():
    recover_calls = 0

    def _recover() -> bool:
        nonlocal recover_calls
        recover_calls += 1
        return True

    result = run_with_schema_recovery(
        lambda: "ok",
        run_with_retry=_run_immediately,
        retry_attempts=0,
        retry_delay_seconds=0.0,
        is_missing_table=lambda _error: False,
        recover=_recover,
    )

    assert result == "ok"
    assert recover_calls == 0


def test_run_with_schema_recovery_retries_after_recovering_schema():
    attempts = 0

    def _operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("no such table: x")
        return "ok"

    result = run_with_schema_recovery(
        _operation,
        run_with_retry=_run_immediately,
        retry_attempts=0,
        retry_delay_seconds=0.0,
        is_missing_table=lambda _error: True,
        recover=lambda: True,
    )

    assert result == "ok"
    assert attempts == 2


def test_run_with_schema_recovery_raises_original_error_when_not_missing_table():
    def _operation() -> str:
        raise RuntimeError("database is locked")

    try:
        run_with_schema_recovery(
            _operation,
            run_with_retry=_run_immediately,
            retry_attempts=0,
            retry_delay_seconds=0.0,
            is_missing_table=lambda _error: False,
            recover=lambda: True,
        )
    except SchemaRecoveryRetryError:  # pragma: no cover - 실패 시에만 도달한다
        raise AssertionError("복구 대상이 아닌 오류는 원본 그대로 올라와야 한다")
    except RuntimeError as error:
        assert "database is locked" in str(error)
    else:  # pragma: no cover - 실패 시에만 도달한다
        raise AssertionError("예외가 올라오지 않았다")


def test_run_with_schema_recovery_raises_marker_when_retry_also_fails():
    def _operation() -> str:
        raise RuntimeError("no such table: x")

    try:
        run_with_schema_recovery(
            _operation,
            run_with_retry=_run_immediately,
            retry_attempts=0,
            retry_delay_seconds=0.0,
            is_missing_table=lambda _error: True,
            recover=lambda: True,
        )
    except SchemaRecoveryRetryError as error:
        # 호출자가 로그 문구를 나누어 쓸 수 있도록 원인을 붙여 올린다.
        assert isinstance(error.__cause__, RuntimeError)
    else:  # pragma: no cover - 실패 시에만 도달한다
        raise AssertionError("SchemaRecoveryRetryError 가 올라오지 않았다")


def test_run_with_schema_recovery_raises_original_error_when_recovery_fails():
    def _operation() -> str:
        raise RuntimeError("no such table: x")

    try:
        run_with_schema_recovery(
            _operation,
            run_with_retry=_run_immediately,
            retry_attempts=0,
            retry_delay_seconds=0.0,
            is_missing_table=lambda _error: True,
            recover=lambda: False,
        )
    except SchemaRecoveryRetryError:  # pragma: no cover - 실패 시에만 도달한다
        raise AssertionError("복구가 실패하면 원본 오류가 올라와야 한다")
    except RuntimeError as error:
        assert "no such table" in str(error)
    else:  # pragma: no cover - 실패 시에만 도달한다
        raise AssertionError("예외가 올라오지 않았다")
```

- [ ] **2단계: 검사가 실패하는 것을 확인한다**

실행: `source venv/bin/activate && pytest tests/services/test_sqlite_ready_gate_refactor.py -q`
기대: `ModuleNotFoundError: No module named 'services.sqlite_ready_gate'` 로 수집 단계에서 실패합니다.

- [ ] **3단계: 골격 모듈을 만든다**

`services/sqlite_ready_gate.py` 를 다음 내용으로 만듭니다.

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQLite 2단 캐시(메모리 + SQLite)의 공용 골격.

chatbot 의 두 캐시 모듈이 각자 갖고 있던 준비 상태 단일 비행, LRU 상한, 신규 키 판정,
강제 프루닝 주기, 스키마 복구 재시도를 여기 한 곳으로 모았다. 테이블 이름과 SQL, 그리고
페이로드 직렬화는 호출하는 모듈에 남는다.

상한값과 sqlite_utils 함수를 인자로 받는 이유가 있다. 호출하는 모듈의 회귀 테스트가
그 모듈의 전역을 monkeypatch 하므로, 골격이 자기 이름공간에서 조회하면 그 패치가 닿지
않는다. 호출 시점에 넘겨받아야 두 모듈의 기존 검사가 그대로 성립한다.
"""

from __future__ import annotations

import logging
import threading
from collections import OrderedDict
from typing import Any, Callable

from services.sqlite_utils import add_bounded_ready_key, normalize_sqlite_db_key


logger = logging.getLogger(__name__)


class SchemaRecoveryRetryError(Exception):
    """스키마를 복구한 뒤 다시 시도했는데도 실패했다.

    호출자가 「복구 전 실패」와 「복구 후 실패」에 서로 다른 로그를 남길 수 있도록
    구분해서 올린다. 원인이 되는 예외는 `__cause__` 에 붙는다.
    """


class SqliteReadyGate:
    """DB 파일 하나의 스키마 준비를 단일 비행으로 보장한다.

    여러 스레드가 동시에 들어와도 초기화는 한 번만 돈다. 나머지는 조건 변수에서
    기다렸다가 결과를 물려받는다. 초기화가 실패하면 기다리던 쪽이 다시 시도한다.
    """

    def __init__(self, *, max_ready_entries: int = 2_048) -> None:
        self.lock = threading.Lock()
        self.condition = threading.Condition(self.lock)
        self.ready_keys: set[str] = set()
        self.in_progress_keys: set[str] = set()
        self._max_ready_entries = max_ready_entries

    def invalidate(self, db_path_text: str) -> None:
        db_key = normalize_sqlite_db_key(db_path_text)
        with self.lock:
            self.ready_keys.discard(db_key)

    def ensure(
        self,
        db_path_text: str,
        *,
        initialize: Callable[[], None],
        db_path_exists: Callable[[str], bool],
        run_with_retry: Callable[..., Any],
        retry_attempts: int,
        retry_delay_seconds: float,
        on_failure: Callable[[Exception], None],
    ) -> bool:
        db_key = normalize_sqlite_db_key(db_path_text)
        with self.condition:
            if db_key in self.ready_keys:
                if db_path_exists(db_path_text):
                    return True
                self.ready_keys.discard(db_key)

            while db_key in self.in_progress_keys:
                self.condition.wait()
                if db_key in self.ready_keys:
                    if db_path_exists(db_path_text):
                        return True
                    self.ready_keys.discard(db_key)

            self.in_progress_keys.add(db_key)

        initialization_succeeded = False
        try:
            run_with_retry(
                initialize,
                max_retries=retry_attempts,
                retry_delay_seconds=retry_delay_seconds,
            )
            initialization_succeeded = True
            return True
        except Exception as error:
            on_failure(error)
            return False
        finally:
            with self.condition:
                self.in_progress_keys.discard(db_key)
                if initialization_succeeded:
                    add_bounded_ready_key(
                        self.ready_keys,
                        db_key,
                        max_entries=self._max_ready_entries,
                    )
                else:
                    self.ready_keys.discard(db_key)
                self.condition.notify_all()


class SeenKeyTracker:
    """(DB, 항목) 조합의 첫 등장과 강제 프루닝 주기를 함께 판정한다.

    프루닝은 매번 돌리기에는 비싸다. 그래서 두 조건에서만 돌린다. 처음 보는 키를
    저장할 때와, 저장 횟수가 정해진 주기에 도달할 때다.
    """

    def __init__(self, *, max_entries: int) -> None:
        self.known_keys: OrderedDict[tuple[str, str], None] = OrderedDict()
        self._lock = threading.Lock()
        self._max_entries = max_entries
        self._counter_lock = threading.Lock()
        self._save_counter = 0

    def mark_seen(self, *, db_path_text: str, item_key: str) -> bool:
        """처음 보는 조합이면 True 를 돌려준다. 그때 프루닝을 돌리면 된다."""
        tracker_key = (normalize_sqlite_db_key(db_path_text), str(item_key))
        with self._lock:
            if tracker_key in self.known_keys:
                self.known_keys.move_to_end(tracker_key)
                return False

            self.known_keys[tracker_key] = None
            self.known_keys.move_to_end(tracker_key)
            normalized_max_entries = max(1, int(self._max_entries))
            while len(self.known_keys) > normalized_max_entries:
                self.known_keys.popitem(last=False)
            return True

    def discard_db(self, db_path_text: str) -> None:
        db_key = normalize_sqlite_db_key(db_path_text)
        with self._lock:
            stale_keys = [key for key in self.known_keys if key[0] == db_key]
            for tracker_key in stale_keys:
                self.known_keys.pop(tracker_key, None)

    def should_force_prune(self, interval: int) -> bool:
        with self._counter_lock:
            self._save_counter += 1
            normalized_interval = max(1, int(interval))
            return (self._save_counter % normalized_interval) == 0

    def clear(self) -> None:
        with self._lock:
            self.known_keys.clear()
        with self._counter_lock:
            self._save_counter = 0


def save_bounded_lru_entry(
    cache: OrderedDict,
    lock: Any,
    key: Any,
    value: Any,
    *,
    max_entries: int,
) -> None:
    """가장 오래 쓰지 않은 항목부터 밀어내며 상한을 지킨다."""
    normalized_max_entries = max(1, int(max_entries))
    with lock:
        cache[key] = value
        cache.move_to_end(key)
        while len(cache) > normalized_max_entries:
            cache.popitem(last=False)


def run_with_schema_recovery(
    operation: Callable[[], Any],
    *,
    run_with_retry: Callable[..., Any],
    retry_attempts: int,
    retry_delay_seconds: float,
    is_missing_table: Callable[[Exception], bool],
    recover: Callable[[], bool],
) -> Any:
    """테이블이 없어서 실패하면 스키마를 되살리고 한 번 더 시도한다.

    복구 대상이 아니거나 복구 자체가 실패하면 원래 예외를 그대로 올린다. 복구한 뒤의
    재시도까지 실패하면 SchemaRecoveryRetryError 로 바꿔 올려서, 호출자가 두 경우에
    다른 로그를 남길 수 있게 한다.
    """

    def _attempt() -> Any:
        return run_with_retry(
            operation,
            max_retries=retry_attempts,
            retry_delay_seconds=retry_delay_seconds,
        )

    try:
        return _attempt()
    except Exception as error:
        if not is_missing_table(error) or not recover():
            raise
        try:
            return _attempt()
        except Exception as retry_error:
            raise SchemaRecoveryRetryError(str(retry_error)) from retry_error
```

- [ ] **4단계: 검사가 통과하는 것을 확인한다**

실행: `source venv/bin/activate && pytest tests/services/test_sqlite_ready_gate_refactor.py -q`
기대: 16건 모두 PASS 입니다.

- [ ] **5단계: 기존 검사가 그대로인지 확인한다**

실행: `source venv/bin/activate && pytest tests/chatbot -q`
기대: 아직 두 캐시 모듈을 고치지 않았으므로 종전 그대로 통과합니다. 이 단계는 골격 추가가 기존 동작을 건드리지 않았음을 확인하는 것입니다.

---

## Task 2: `runtime_stock_map_cache` 를 골격 위로 옮긴다

**파일:**
- 수정: `chatbot/runtime_stock_map_cache.py`
- 검사: `tests/chatbot/test_runtime_stock_map_cache_refactor.py` (고치지 않고 그대로 돌립니다)

**인터페이스:**
- 사용: Task 1 의 `SqliteReadyGate`, `SeenKeyTracker`, `save_bounded_lru_entry`, `run_with_schema_recovery`, `SchemaRecoveryRetryError`
- 제공: 공개 함수 다섯 개가 그대로 남습니다. `file_signature`, `load_stock_map_cache`, `save_stock_map_cache`, `build_stock_maps`, `clear_stock_map_cache`. 비공개 `_ensure_stock_map_sqlite(db_path, logger)` 도 이름과 시그니처를 유지합니다.

- [ ] **1단계: 상태 선언부를 골격 인스턴스로 바꾼다**

`chatbot/runtime_stock_map_cache.py:32-59` 의 상태 선언을 다음으로 교체합니다. 모듈 전역이 골격 인스턴스의 속성을 가리키는 별칭이 되므로, 회귀 테스트가 `_STOCK_MAP_SQLITE_READY.clear()` 를 부르면 게이트 안의 집합이 함께 비워집니다.

```python
from services.sqlite_ready_gate import (
    SchemaRecoveryRetryError,
    SeenKeyTracker,
    SqliteReadyGate,
    run_with_schema_recovery,
    save_bounded_lru_entry,
)


_STOCK_MAP_CACHE_LOCK = threading.Lock()
_STOCK_MAP_CACHE: OrderedDict[
    str,
    tuple[tuple[int, int], dict[str, str], dict[str, str]],
] = OrderedDict()
_STOCK_MAP_MEMORY_MAX_ENTRIES = 256
_STOCK_MAP_SQLITE_MAX_ROWS = 128
_STOCK_MAP_SQLITE_TIMEOUT_SECONDS = 30
_STOCK_MAP_SQLITE_RETRY_ATTEMPTS = 2
_STOCK_MAP_SQLITE_RETRY_DELAY_SECONDS = 0.03
_STOCK_MAP_SQLITE_PRUNE_FORCE_INTERVAL = 64

_STOCK_MAP_READY_GATE = SqliteReadyGate(max_ready_entries=2_048)
_STOCK_MAP_SEEN_TRACKER = SeenKeyTracker(max_entries=4_096)

# 회귀 테스트가 모듈 전역으로 이 셋을 직접 조작한다. 같은 객체를 가리키는 별칭이므로
# 테스트가 clear() 를 불러도 게이트가 함께 비워진다.
_STOCK_MAP_SQLITE_READY_CONDITION = _STOCK_MAP_READY_GATE.condition
_STOCK_MAP_SQLITE_READY = _STOCK_MAP_READY_GATE.ready_keys
_STOCK_MAP_SQLITE_INIT_IN_PROGRESS = _STOCK_MAP_READY_GATE.in_progress_keys

_STOCK_MAP_SQLITE_INIT_PRAGMAS = build_sqlite_pragmas(
    busy_timeout_ms=_STOCK_MAP_SQLITE_TIMEOUT_SECONDS * 1000,
)
_STOCK_MAP_SQLITE_SESSION_PRAGMAS = build_sqlite_pragmas(
    busy_timeout_ms=_STOCK_MAP_SQLITE_TIMEOUT_SECONDS * 1000,
    base_pragmas=("PRAGMA temp_store=MEMORY", "PRAGMA cache_size=-4000"),
)
```

`services.sqlite_utils` 에서 가져오던 `add_bounded_ready_key` 는 이제 골격이 쓰므로 이 모듈의 import 목록에서 뺍니다. `connect_sqlite`, `build_sqlite_in_placeholders`, `build_sqlite_order_case_sql`, `build_sqlite_pragmas`, `is_sqlite_missing_table_error`, `normalize_sqlite_db_key`, `prune_rows_by_updated_at_if_needed`, `run_sqlite_with_retry`, `sqlite_db_path_exists` 는 그대로 둡니다. 뒤의 넷은 회귀 테스트가 이 모듈의 이름공간에서 monkeypatch 하므로 반드시 남아야 합니다.

- [ ] **2단계: 무효화와 준비 함수를 위임으로 바꾼다**

`chatbot/runtime_stock_map_cache.py:100-188` 의 세 함수를 다음으로 교체합니다.

```python
def _invalidate_stock_map_sqlite_ready(db_path: Path) -> None:
    db_path_text = str(db_path)
    _STOCK_MAP_READY_GATE.invalidate(db_path_text)
    _STOCK_MAP_SEEN_TRACKER.discard_db(db_path_text)


def _is_missing_table_error(error: Exception) -> bool:
    return is_sqlite_missing_table_error(error, table_names="chatbot_stock_map_cache")


def _recover_stock_map_sqlite_schema(db_path: Path, logger: Any) -> bool:
    _invalidate_stock_map_sqlite_ready(db_path)
    return _ensure_stock_map_sqlite(db_path, logger)


def _create_stock_map_schema(db_path_text: str) -> None:
    with connect_sqlite(
        db_path_text,
        timeout_seconds=_STOCK_MAP_SQLITE_TIMEOUT_SECONDS,
        pragmas=_STOCK_MAP_SQLITE_INIT_PRAGMAS,
    ) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chatbot_stock_map_cache (
                source_path TEXT PRIMARY KEY,
                mtime_ns INTEGER NOT NULL,
                size INTEGER NOT NULL,
                stock_map_json TEXT NOT NULL,
                ticker_map_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_chatbot_stock_map_cache_updated_at
            ON chatbot_stock_map_cache(updated_at DESC)
            """
        )
        conn.commit()


def _ensure_stock_map_sqlite(db_path: Path, logger: Any) -> bool:
    db_path_text = str(db_path)
    return _STOCK_MAP_READY_GATE.ensure(
        db_path_text,
        initialize=lambda: _create_stock_map_schema(db_path_text),
        db_path_exists=sqlite_db_path_exists,
        run_with_retry=run_sqlite_with_retry,
        retry_attempts=_STOCK_MAP_SQLITE_RETRY_ATTEMPTS,
        retry_delay_seconds=_STOCK_MAP_SQLITE_RETRY_DELAY_SECONDS,
        on_failure=lambda error: logger.debug(
            "Failed to initialize stock map sqlite cache: %s", error
        ),
    )
```

`sqlite_db_path_exists` 와 `run_sqlite_with_retry` 를 인자로 넘기는 것이 핵심입니다. 이 모듈의 전역을 읽어 넘기므로 회귀 테스트의 monkeypatch 가 그대로 닿습니다.

- [ ] **3단계: 메모리 저장과 프루닝 판정을 위임으로 바꾼다**

`chatbot/runtime_stock_map_cache.py:190-230` 의 세 함수를 다음으로 교체합니다.

```python
def _save_stock_map_memory_entry(
    cache_key: str,
    signature: tuple[int, int],
    stock_map: dict[str, str],
    ticker_map: dict[str, str],
) -> None:
    save_bounded_lru_entry(
        _STOCK_MAP_CACHE,
        _STOCK_MAP_CACHE_LOCK,
        cache_key,
        (signature, dict(stock_map), dict(ticker_map)),
        max_entries=_STOCK_MAP_MEMORY_MAX_ENTRIES,
    )
```

`_mark_stock_map_sqlite_source_path_seen` 과 `_should_force_stock_map_sqlite_prune` 은 지웁니다. 부르는 자리인 `_save_stock_map_to_sqlite` 가 트래커를 직접 씁니다.

- [ ] **4단계: 조회와 저장의 복구 흐름을 위임으로 바꾼다**

`_load_stock_map_from_sqlite` 의 `try/except` 블록(원본 279-298줄)을 다음으로 교체합니다. `_query_row` 정의는 그대로 둡니다.

```python
    try:
        row = run_with_schema_recovery(
            _query_row,
            run_with_retry=run_sqlite_with_retry,
            retry_attempts=_STOCK_MAP_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_STOCK_MAP_SQLITE_RETRY_DELAY_SECONDS,
            is_missing_table=_is_missing_table_error,
            recover=lambda: _recover_stock_map_sqlite_schema(db_path, logger),
        )
    except SchemaRecoveryRetryError as error:
        logger.debug("Failed to load stock map sqlite cache after schema recovery: %s", error)
        return None
    except Exception as error:
        logger.debug("Failed to load stock map sqlite cache: %s", error)
        return None
```

`_save_stock_map_to_sqlite` 에서는 프루닝 판정 부분(원본 338-344줄)을 다음으로 바꿉니다.

```python
    normalized_max_rows = max(1, int(_STOCK_MAP_SQLITE_MAX_ROWS))
    should_prune_after_upsert = _STOCK_MAP_SEEN_TRACKER.mark_seen(
        db_path_text=db_path_text,
        item_key=source_path_key,
    ) or _STOCK_MAP_SEEN_TRACKER.should_force_prune(
        _STOCK_MAP_SQLITE_PRUNE_FORCE_INTERVAL
    )
```

`or` 의 단축 평가가 여기서 문제가 됩니다. 처음 보는 키일 때 `should_force_prune` 이 호출되지 않아 저장 카운터가 올라가지 않습니다. 원본은 두 함수를 모두 부른 뒤 `or` 로 합칩니다. 그 동작을 그대로 지키려면 두 값을 각각 받아야 합니다.

```python
    normalized_max_rows = max(1, int(_STOCK_MAP_SQLITE_MAX_ROWS))
    should_prune_for_new_path = _STOCK_MAP_SEEN_TRACKER.mark_seen(
        db_path_text=db_path_text,
        item_key=source_path_key,
    )
    should_force_prune = _STOCK_MAP_SEEN_TRACKER.should_force_prune(
        _STOCK_MAP_SQLITE_PRUNE_FORCE_INTERVAL
    )
    should_prune_after_upsert = should_prune_for_new_path or should_force_prune
```

그리고 저장 쪽 `try/except` 블록(원본 388-405줄)을 다음으로 교체합니다.

```python
    try:
        run_with_schema_recovery(
            _upsert_stock_map,
            run_with_retry=run_sqlite_with_retry,
            retry_attempts=_STOCK_MAP_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_STOCK_MAP_SQLITE_RETRY_DELAY_SECONDS,
            is_missing_table=_is_missing_table_error,
            recover=lambda: _recover_stock_map_sqlite_schema(db_path, logger),
        )
    except SchemaRecoveryRetryError as error:
        logger.debug("Failed to save stock map sqlite cache after schema recovery: %s", error)
    except Exception as error:
        logger.debug("Failed to save stock map sqlite cache: %s", error)
```

- [ ] **5단계: `clear_stock_map_cache` 를 위임으로 바꾼다**

```python
def clear_stock_map_cache() -> None:
    with _STOCK_MAP_CACHE_LOCK:
        _STOCK_MAP_CACHE.clear()
    _STOCK_MAP_SEEN_TRACKER.clear()
```

원본에 있던 `global _STOCK_MAP_SQLITE_SAVE_COUNTER` 와 카운터 초기화는 트래커가 맡으므로 사라집니다.

- [ ] **6단계: 기존 회귀 검사가 그대로 통과하는지 확인한다**

실행: `source venv/bin/activate && pytest tests/chatbot/test_runtime_stock_map_cache_refactor.py -q`
기대: 14건 모두 PASS 입니다. 테스트 파일은 한 줄도 고치지 않습니다. 하나라도 실패하면 monkeypatch 대상이 골격 안으로 숨은 것이므로, 그 값을 인자로 되돌립니다.

---

## Task 3: `stock_context_cache` 를 골격 위로 옮긴다

**파일:**
- 수정: `chatbot/stock_context_cache.py`
- 검사: `tests/chatbot/test_stock_context_cache_refactor.py` (고치지 않고 그대로 돌립니다)

**인터페이스:**
- 사용: Task 1 의 `SqliteReadyGate`, `SeenKeyTracker`, `save_bounded_lru_entry`, `run_with_schema_recovery`, `SchemaRecoveryRetryError`
- 제공: 공개 함수 셋이 그대로 남습니다. `load_cached_result_text`, `save_cached_result_text`, `clear_result_text_cache`. 비공개 `_ensure_result_text_sqlite_cache(db_path)` 와 `_build_result_cache_key(path, *, dataset, ticker_padded)` 도 이름과 시그니처를 유지합니다.

- [ ] **1단계: 상태 선언부를 골격 인스턴스로 바꾼다**

`chatbot/stock_context_cache.py:33-57` 의 상태 선언을 다음으로 교체합니다.

```python
from services.sqlite_ready_gate import (
    SchemaRecoveryRetryError,
    SeenKeyTracker,
    SqliteReadyGate,
    run_with_schema_recovery,
    save_bounded_lru_entry,
)


LOGGER = logging.getLogger(__name__)

_RESULT_TEXT_CACHE_LOCK = Lock()
_RESULT_TEXT_CACHE: OrderedDict[str, tuple[tuple[int, int], str]] = OrderedDict()
_RESULT_TEXT_MEMORY_MAX_ENTRIES = 2048
_RESULT_TEXT_SQLITE_MAX_ROWS = 1024
_RESULT_TEXT_SQLITE_PRUNE_FORCE_INTERVAL = 64
_RESULT_TEXT_SQLITE_TIMEOUT_SECONDS = 30
_RESULT_TEXT_SQLITE_RETRY_ATTEMPTS = 2
_RESULT_TEXT_SQLITE_RETRY_DELAY_SECONDS = 0.03

_RESULT_TEXT_READY_GATE = SqliteReadyGate(max_ready_entries=2_048)
_RESULT_TEXT_SEEN_TRACKER = SeenKeyTracker(max_entries=8_192)

# 회귀 테스트가 모듈 전역으로 이 셋을 직접 조작한다. 같은 객체를 가리키는 별칭이다.
_RESULT_TEXT_SQLITE_READY_CONDITION = _RESULT_TEXT_READY_GATE.condition
_RESULT_TEXT_SQLITE_READY = _RESULT_TEXT_READY_GATE.ready_keys
_RESULT_TEXT_SQLITE_INIT_IN_PROGRESS = _RESULT_TEXT_READY_GATE.in_progress_keys

_RESULT_TEXT_SQLITE_INIT_PRAGMAS = build_sqlite_pragmas(
    busy_timeout_ms=_RESULT_TEXT_SQLITE_TIMEOUT_SECONDS * 1000,
)
_RESULT_TEXT_SQLITE_SESSION_PRAGMAS = build_sqlite_pragmas(
    busy_timeout_ms=_RESULT_TEXT_SQLITE_TIMEOUT_SECONDS * 1000,
    base_pragmas=("PRAGMA temp_store=MEMORY", "PRAGMA cache_size=-4000"),
)
```

`add_bounded_ready_key` 를 import 목록에서 뺍니다. 원본에 있던 `_RESULT_TEXT_SQLITE_LOCK`, `_RESULT_TEXT_SQLITE_KNOWN_KEYS`, `_RESULT_TEXT_SQLITE_KNOWN_KEYS_LOCK`, `_RESULT_TEXT_SQLITE_KNOWN_KEYS_MAX_ENTRIES`, `_RESULT_TEXT_SQLITE_READY_MAX_ENTRIES`, `_RESULT_TEXT_SQLITE_SAVE_COUNTER`, `_RESULT_TEXT_SQLITE_SAVE_COUNTER_LOCK` 은 골격이 맡으므로 지웁니다. 회귀 테스트가 이 일곱 개를 참조하지 않는 것을 확인했습니다.

- [ ] **2단계: 무효화와 준비 함수를 위임으로 바꾼다**

`chatbot/stock_context_cache.py:91-179` 의 네 함수를 다음으로 교체합니다.

```python
def _invalidate_result_text_sqlite_ready(db_path: Path) -> None:
    db_path_text = str(db_path)
    _RESULT_TEXT_READY_GATE.invalidate(db_path_text)
    _RESULT_TEXT_SEEN_TRACKER.discard_db(db_path_text)


def _is_missing_table_error(error: Exception) -> bool:
    return is_sqlite_missing_table_error(error, table_names="chatbot_stock_context_cache")


def _recover_result_text_sqlite_schema(db_path: Path) -> bool:
    _invalidate_result_text_sqlite_ready(db_path)
    return _ensure_result_text_sqlite_cache(db_path)


def _create_result_text_schema(db_path_text: str) -> None:
    with connect_sqlite(
        db_path_text,
        timeout_seconds=_RESULT_TEXT_SQLITE_TIMEOUT_SECONDS,
        pragmas=_RESULT_TEXT_SQLITE_INIT_PRAGMAS,
    ) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chatbot_stock_context_cache (
                cache_key TEXT PRIMARY KEY,
                dataset TEXT NOT NULL,
                ticker TEXT NOT NULL,
                mtime_ns INTEGER NOT NULL,
                size INTEGER NOT NULL,
                payload_text TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_chatbot_stock_context_cache_updated_at
            ON chatbot_stock_context_cache(updated_at DESC)
            """
        )
        conn.commit()


def _ensure_result_text_sqlite_cache(db_path: Path) -> bool:
    db_path_text = str(db_path)
    return _RESULT_TEXT_READY_GATE.ensure(
        db_path_text,
        initialize=lambda: _create_result_text_schema(db_path_text),
        db_path_exists=sqlite_db_path_exists,
        run_with_retry=run_sqlite_with_retry,
        retry_attempts=_RESULT_TEXT_SQLITE_RETRY_ATTEMPTS,
        retry_delay_seconds=_RESULT_TEXT_SQLITE_RETRY_DELAY_SECONDS,
        on_failure=lambda error: LOGGER.debug(
            "Failed to initialize stock context sqlite cache (%s): %s", db_path, error
        ),
    )
```

- [ ] **3단계: 메모리 저장과 프루닝 판정을 위임으로 바꾼다**

`chatbot/stock_context_cache.py:182-216` 의 세 함수를 다음으로 교체합니다.

```python
def _save_result_text_memory_entry(cache_key: str, signature: tuple[int, int], payload_text: str) -> None:
    save_bounded_lru_entry(
        _RESULT_TEXT_CACHE,
        _RESULT_TEXT_CACHE_LOCK,
        cache_key,
        (signature, payload_text),
        max_entries=_RESULT_TEXT_MEMORY_MAX_ENTRIES,
    )
```

`_mark_result_text_sqlite_cache_key_seen` 과 `_should_force_result_text_sqlite_prune` 은 지웁니다.

- [ ] **4단계: 조회와 저장의 복구 흐름을 위임으로 바꾼다**

`_load_result_text_from_sqlite` 의 `try/except` 블록(원본 265-284줄)을 다음으로 교체합니다.

```python
    try:
        row = run_with_schema_recovery(
            _query_row,
            run_with_retry=run_sqlite_with_retry,
            retry_attempts=_RESULT_TEXT_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_RESULT_TEXT_SQLITE_RETRY_DELAY_SECONDS,
            is_missing_table=_is_missing_table_error,
            recover=lambda: _recover_result_text_sqlite_schema(db_path),
        )
    except SchemaRecoveryRetryError as exc:
        LOGGER.debug("Failed to load stock context sqlite cache after schema recovery (%s): %s", cache_key, exc)
        return None
    except Exception as exc:
        LOGGER.debug("Failed to load stock context sqlite cache (%s): %s", cache_key, exc)
        return None
```

`_save_result_text_to_sqlite` 의 프루닝 판정(원본 310-316줄)을 다음으로 바꿉니다. 두 판정을 모두 실행해야 저장 카운터가 원본과 같은 속도로 올라갑니다.

```python
    normalized_max_rows = max(1, int(_RESULT_TEXT_SQLITE_MAX_ROWS))
    should_prune_for_new_key = _RESULT_TEXT_SEEN_TRACKER.mark_seen(
        db_path_text=db_path_text,
        item_key=cache_key,
    )
    should_force_prune = _RESULT_TEXT_SEEN_TRACKER.should_force_prune(
        _RESULT_TEXT_SQLITE_PRUNE_FORCE_INTERVAL
    )
    should_prune_after_upsert = should_prune_for_new_key or should_force_prune
```

저장 쪽 `try/except` 블록(원본 363-384줄)을 다음으로 교체합니다.

```python
    try:
        run_with_schema_recovery(
            _upsert_payload_text,
            run_with_retry=run_sqlite_with_retry,
            retry_attempts=_RESULT_TEXT_SQLITE_RETRY_ATTEMPTS,
            retry_delay_seconds=_RESULT_TEXT_SQLITE_RETRY_DELAY_SECONDS,
            is_missing_table=_is_missing_table_error,
            recover=lambda: _recover_result_text_sqlite_schema(db_path),
        )
    except SchemaRecoveryRetryError as exc:
        LOGGER.debug(
            "Failed to save stock context sqlite cache after schema recovery (%s): %s",
            cache_key,
            exc,
        )
    except Exception as exc:
        LOGGER.debug("Failed to save stock context sqlite cache (%s): %s", cache_key, exc)
```

- [ ] **5단계: `clear_result_text_cache` 를 위임으로 바꾼다**

```python
def clear_result_text_cache() -> None:
    with _RESULT_TEXT_CACHE_LOCK:
        _RESULT_TEXT_CACHE.clear()
    _RESULT_TEXT_SEEN_TRACKER.clear()
```

- [ ] **6단계: 기존 회귀 검사가 그대로 통과하는지 확인한다**

실행: `source venv/bin/activate && pytest tests/chatbot/test_stock_context_cache_refactor.py -q`
기대: 15건 모두 PASS 입니다.

- [ ] **7단계: 챗봇 전체 검사를 돌린다**

실행: `source venv/bin/activate && pytest tests/chatbot -q`
기대: 전부 PASS 입니다. `tests/chatbot/test_stock_context.py` 가 `load_cached_result_text` 를 간접적으로 쓰므로 공개 시그니처가 유지되었는지 여기서 함께 드러납니다.

---

## Task 4: 두 모듈의 동작이 실제로 같아졌는지 고정한다

**파일:**
- 수정: `tests/services/test_sqlite_ready_gate_refactor.py` (Task 1 에서 만든 파일에 덧붙입니다)

**인터페이스:**
- 사용: Task 2 와 Task 3 이 옮긴 `chatbot.runtime_stock_map_cache` 와 `chatbot.stock_context_cache`
- 제공: 없습니다. 이 Task 는 검사만 더합니다.

항목의 마지막 체크박스가 「스키마 복구와 프루닝 동작이 양쪽에서 동일한지 검증하는 테스트 추가」입니다. Task 1 의 검사는 골격 자체를 검사하고, 여기서는 **두 모듈이 그 골격을 같은 방식으로 쓰는지**를 검사합니다. 골격을 공유해도 한쪽만 인자를 잘못 넘기면 동작이 갈리기 때문입니다.

- [ ] **1단계: 실패하는 검사를 쓴다**

`tests/services/test_sqlite_ready_gate_refactor.py` 끝에 다음을 덧붙입니다.

```python
import sqlite3  # noqa: E402

import chatbot.runtime_stock_map_cache as runtime_stock_map_cache  # noqa: E402
import chatbot.stock_context_cache as stock_context_cache  # noqa: E402


def _reset_both_caches() -> None:
    runtime_stock_map_cache.clear_stock_map_cache()
    stock_context_cache.clear_result_text_cache()
    with runtime_stock_map_cache._STOCK_MAP_SQLITE_READY_CONDITION:
        runtime_stock_map_cache._STOCK_MAP_SQLITE_READY.clear()
        runtime_stock_map_cache._STOCK_MAP_SQLITE_INIT_IN_PROGRESS.clear()
    with stock_context_cache._RESULT_TEXT_SQLITE_READY_CONDITION:
        stock_context_cache._RESULT_TEXT_SQLITE_READY.clear()
        stock_context_cache._RESULT_TEXT_SQLITE_INIT_IN_PROGRESS.clear()


def _logger_stub():
    import types

    return types.SimpleNamespace(debug=lambda *_args, **_kwargs: None)


def test_both_modules_share_one_ready_gate_implementation():
    # 두 모듈의 준비 상태 별칭이 각자의 게이트 인스턴스를 가리켜야 한다. 같은 게이트를
    # 공유하면 한 테이블이 준비됐다는 이유로 다른 테이블도 준비된 것으로 잘못 판정한다.
    assert (
        runtime_stock_map_cache._STOCK_MAP_READY_GATE
        is not stock_context_cache._RESULT_TEXT_READY_GATE
    )
    assert (
        runtime_stock_map_cache._STOCK_MAP_SQLITE_READY
        is runtime_stock_map_cache._STOCK_MAP_READY_GATE.ready_keys
    )
    assert (
        stock_context_cache._RESULT_TEXT_SQLITE_READY
        is stock_context_cache._RESULT_TEXT_READY_GATE.ready_keys
    )


def test_both_modules_recover_when_their_table_is_dropped(tmp_path):
    _reset_both_caches()
    data_dir = tmp_path
    source_path = tmp_path / "stocks.csv"
    source_path.write_text("name,ticker\n", encoding="utf-8")
    signature = (1, 1)
    logger = _logger_stub()

    runtime_stock_map_cache.save_stock_map_cache(
        data_dir=data_dir,
        source_path=source_path,
        signature=signature,
        stock_map={"삼성전자": "005930"},
        ticker_map={"005930": "삼성전자"},
        logger=logger,
    )
    stock_context_cache.save_cached_result_text(
        data_dir=data_dir,
        path=source_path,
        dataset="jongga",
        ticker_padded="005930",
        signature=signature,
        payload_text="본문",
    )

    # 두 테이블을 모두 지우고 메모리 캐시도 비운다. SQLite 경로만 남는다.
    db_path = data_dir / "runtime_cache.db"
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("DROP TABLE chatbot_stock_map_cache")
        conn.execute("DROP TABLE chatbot_stock_context_cache")
        conn.commit()
    _reset_both_caches()

    # 테이블이 없으므로 조회는 None 이지만, 그 과정에서 스키마가 되살아나야 한다.
    assert (
        runtime_stock_map_cache.load_stock_map_cache(
            data_dir=data_dir,
            source_path=source_path,
            signature=signature,
            logger=logger,
        )
        is None
    )
    assert (
        stock_context_cache.load_cached_result_text(
            data_dir=data_dir,
            path=source_path,
            dataset="jongga",
            ticker_padded="005930",
            signature=signature,
        )
        is None
    )

    with sqlite3.connect(str(db_path)) as conn:
        table_names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert "chatbot_stock_map_cache" in table_names
    assert "chatbot_stock_context_cache" in table_names


def test_both_modules_prune_on_the_same_schedule(monkeypatch, tmp_path):
    _reset_both_caches()
    data_dir = tmp_path
    source_path = tmp_path / "stocks.csv"
    source_path.write_text("name,ticker\n", encoding="utf-8")
    logger = _logger_stub()

    # 같은 주기를 주면 같은 저장 횟수에서 프루닝이 돌아야 한다.
    monkeypatch.setattr(runtime_stock_map_cache, "_STOCK_MAP_SQLITE_PRUNE_FORCE_INTERVAL", 3)
    monkeypatch.setattr(stock_context_cache, "_RESULT_TEXT_SQLITE_PRUNE_FORCE_INTERVAL", 3)

    stock_map_prunes: list[int] = []
    result_text_prunes: list[int] = []

    def _make_tracer(bucket):
        def _traced(cursor, *, table_name, max_rows):
            bucket.append(max_rows)

        return _traced

    monkeypatch.setattr(
        runtime_stock_map_cache,
        "prune_rows_by_updated_at_if_needed",
        _make_tracer(stock_map_prunes),
    )
    monkeypatch.setattr(
        stock_context_cache,
        "prune_rows_by_updated_at_if_needed",
        _make_tracer(result_text_prunes),
    )

    # 같은 키로 다섯 번 저장한다. 첫 저장은 신규 키라 프루닝하고, 그다음은 주기가
    # 채워지는 세 번째 저장에서 프루닝한다. 두 모듈이 같아야 한다.
    for index in range(5):
        runtime_stock_map_cache.save_stock_map_cache(
            data_dir=data_dir,
            source_path=source_path,
            signature=(index, index),
            stock_map={"삼성전자": "005930"},
            ticker_map={"005930": "삼성전자"},
            logger=logger,
        )
        stock_context_cache.save_cached_result_text(
            data_dir=data_dir,
            path=source_path,
            dataset="jongga",
            ticker_padded="005930",
            signature=(index, index),
            payload_text=f"본문 {index}",
        )

    assert len(stock_map_prunes) == len(result_text_prunes) == 2
```

- [ ] **2단계: 검사가 통과하는 것을 확인한다**

실행: `source venv/bin/activate && pytest tests/services/test_sqlite_ready_gate_refactor.py -q`
기대: 19건 모두 PASS 입니다.

`test_both_modules_prune_on_the_same_schedule` 이 실패하면 두 모듈의 프루닝 판정 순서가 갈린 것입니다. Task 2 의 4단계와 Task 3 의 4단계에서 `mark_seen` 과 `should_force_prune` 을 **둘 다 호출한 뒤** `or` 로 합쳤는지 확인합니다. 단축 평가로 하나를 건너뛰면 저장 카운터가 다른 속도로 올라갑니다.

- [ ] **3단계: 전체 검사를 돌린다**

실행: `source venv/bin/activate && pytest`
기대: 기존 1,641건에 새 19건이 더해져 전부 PASS 입니다.

---

## 자체 점검

**1. 항목 체크박스 대응**

| 체크박스 | 대응하는 Task |
|---|---|
| 두 모듈의 실제 차이를 목록으로 확정 | 이 문서의 「두 모듈에 남는 것」 표 |
| 2단 캐시 골격을 한 곳으로 모으고 차이 부분만 주입받도록 정리 | Task 1·2·3 |
| 두 모듈의 공개 함수 시그니처 유지 | Task 2 와 Task 3 의 「인터페이스」 절, Task 3 의 7단계 |
| 기존 두 회귀 테스트가 그대로 통과하는지 확인 | Task 2 의 6단계, Task 3 의 6단계 |
| 스키마 복구와 프루닝 동작이 양쪽에서 동일한지 검증하는 테스트 추가 | Task 4 |

**2. 자리 표시자 점검**

「TBD」, 「적절한 오류 처리를 더한다」, 「Task N 과 비슷하게」 같은 문구가 없습니다. 모든 코드 단계에 실제 코드가 들어 있습니다.

**3. 이름 일관성**

Task 1 이 정의한 `SqliteReadyGate.ensure`, `SeenKeyTracker.mark_seen`, `SeenKeyTracker.should_force_prune`, `SeenKeyTracker.discard_db`, `SeenKeyTracker.clear`, `save_bounded_lru_entry`, `run_with_schema_recovery`, `SchemaRecoveryRetryError` 를 Task 2·3·4 가 같은 이름과 같은 인자로 씁니다. 인스턴스 이름 `_STOCK_MAP_READY_GATE`, `_STOCK_MAP_SEEN_TRACKER`, `_RESULT_TEXT_READY_GATE`, `_RESULT_TEXT_SEEN_TRACKER` 도 Task 2·3 에서 정의한 대로 Task 4 가 참조합니다.

**4. 빠뜨리기 쉬운 자리**

- `add_bounded_ready_key` 를 두 캐시 모듈의 import 목록에서 빼되, `connect_sqlite`·`run_sqlite_with_retry`·`sqlite_db_path_exists`·`prune_rows_by_updated_at_if_needed` 는 반드시 남깁니다. 회귀 테스트가 이 넷을 각 모듈의 이름공간에서 monkeypatch 합니다.
- `stock_context_cache` 의 `_resolve_runtime_cache_db_path` 는 `data_dir` 를 먼저 정규화한 뒤 파일명을 붙입니다. `runtime_stock_map_cache` 의 `_stock_map_cache_db_path` 는 정규화하지 않습니다. 이 차이를 통일하지 않습니다. 통일하면 이미 저장된 DB 의 키와 어긋날 수 있고, 이번 항목의 범위도 아닙니다.
- `SqliteReadyGate` 인스턴스를 두 모듈이 **따로** 만듭니다. 같은 `runtime_cache.db` 파일을 쓰지만 테이블이 다르므로, 게이트를 공유하면 한 테이블이 준비됐다는 이유로 다른 테이블도 준비된 것으로 잘못 판정합니다. Task 4 의 첫 검사가 이것을 고정합니다.

## 후속 항목

이번에 옮기지 않은 아홉 개 모듈은 사이클 마감에서 `docs/dev-cycle/TODO.md` 에 새 항목으로 올립니다. 같은 골격을 쓰는 것을 확인했으므로, 이 계획의 Task 2 와 같은 방식으로 하나씩 옮길 수 있습니다.
