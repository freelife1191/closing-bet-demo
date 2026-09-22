# `[FE-045]` 서버에 저장한 개인정보를 사용자가 실제로 지울 수 있게 한다 — 구현 계획

> **For agentic workers:** 이 저장소는 `.claude/skills/dev-cycle/SKILL.md` 의 절차를 따릅니다.
> 계획의 단계는 그 절차의 `[2] 구현과 리뷰` 안에서 순서대로 수행하며, 단계마다 커밋하지 않고
> `[3] 검증` 의 첫 커밋에서 한 번에 남깁니다. 체크박스는 진행 표시용입니다.

**목표:** 설정 모달의 「계정 삭제」가 브라우저 저장소만 비우고 로그아웃하던 것을, 로그인한
사용자 본인의 서버 기록(챗봇 세션·메시지·메모리, 모의투자 계좌, 무료 사용량·충전 기록)을 실제로
지운 뒤에만 로그아웃하도록 바꾼다. 실패하면 지워지지 않았다고 알린다.

**접근:** Flask 에 `DELETE /api/kr/user/data` 하나를 두고, 신원은 `before_request` 가 서명 헤더에서
확정한 `g.user_email` 만 쓴다. 저장소마다 이미 있는 소유자 단위 삭제(`HistoryManager.clear_for_owner`,
`clear_memories_in_sqlite`, 모의투자 `reset_account` 의 형태)를 재사용하거나 그 옆에 같은 모양으로
한 함수씩 더한다. 세 저장소는 파일이 달라 한 트랜잭션으로 묶을 수 없으므로, 앞이 실패해도 뒤를
계속 지워 남는 기록을 최소로 하고 하나라도 실패하면 500 으로 돌려준다. 화면은 200 을 받은 뒤에만
`localStorage`·`sessionStorage` 를 비우고 `signOut` 한다.

**기술 스택:** Flask 3, SQLite(`connect_sqlite`), Next.js 16.3.5 App Router 클라이언트 컴포넌트,
`fetchAPI`, pytest, vitest 4

**설계 근거:** `docs/dev-cycle/TODO.md` 의 `[FE-045]` 항목과 2026-09-22 대화 설계. 사용자가
AskUserQuestion 에서 「INFRA-077 승인, 끝나면 FE-045」를 선택해 이 bounded 설계를 승인했다.

**조사 정정:** TODO 근거의 「`usage.db` 의 `usage_log`」는 틀렸다. 무료 사용량과 충전 기록은
`data/user_quota.json`(`app/routes/kr_market.py` 의 `QUOTA_FILE`) 에 이메일 키와
`recharge_day:<이메일>` 키로 있다. 이메일을 기본 키로 가진 SQLite 테이블은 둘 더 있는데,
`services/usage_tracker.py` 의 `usage_log` 와 `engine/services/usage_tracker.py` 의 `api_usage` 는 어떤
운영 코드도 import 하지 않는 유물이다(`grep -rln usage_tracker` 결과가 두 모듈 자신·테스트 넷·증거
스크립트 하나뿐). 둘 다 `data/usage.db` 에 있고 로컬에서는 두 테이블 모두 행 0 이다(읽기 전용 확인).
운영 서버의 행 수는 이 기기에서 확인할 수 없어 운영자 확인 항목 `[INFRA-079]` 로 백로그에 둔다.
두 파일은 이 계획의 범위 밖이며 건드리지 않는다.

## 전역 제약

- 신원은 `g.user_email` 하나다. 쿼리·본문·`X-User-Email` 같은 클라이언트 값을 소유자로 읽지
  않는다. 관리자가 남의 기록을 지우는 인자를 두지 않는다.
- 위험 경로: `services/paper_trading_trade_account_mixin.py` 는 tier-rules §2 「모의투자 계좌와
  거래」다. 티어는 T3 이고 그 파일의 변경은 `delete_account` 한 메서드와 `reset_account` 가
  공유하는 스냅샷 정리 헬퍼 추출로 한정한다. 스키마(`paper_trading_db_setup.py`)는 건드리지 않는다.
- `chatbot/storage_sqlite_common.py` 와 `services/sqlite_utils.py` 는 건드리지 않는다.
- `frontend/src/app` 의 변경은 `SettingsModal.tsx` 의 클릭 핸들러·문구와 `(legal)/privacy/page.tsx`
  의 문구뿐이다. 라우트 핸들러를 만들지 않는다. `/api/kr/user/data` 는 `next.config.js` 의 rewrite 가
  Flask 로 넘기고 `proxy.ts` 가 `DELETE` 도 메서드·경로와 함께 서명한다(`proxy.ts:82-88`).
- 호출은 `fetchAPI` 로 한다. 맨 `fetch(` 를 늘리지 않는다.
- 활동 로그 파일(`logs/user_activity.log*`)은 이 경로가 지우지 않는다. 30일 자동 삭제만 문구로
  안내한다. `[FE-046]` 의 범위다.
- `data/` 원본을 테스트가 읽거나 쓰지 않는다. 모든 검사는 `tmp_path` 다.
- 익명 서버 기록(`X-Session-Id` 키)은 이 항목의 범위가 아니다. 계획 초판은 「익명의 「초기화」는 종전처럼
  브라우저 저장소만 비운다」고 적었으나, 코드 리뷰가 두 진입점(프로필 탭 「계정 삭제」는 로그인, Danger Zone
  「초기화 및 삭제」는 관리자)이 모두 익명에게 보이지 않음을 확인해 그 갈래를 두지 않는다. 항상 서버 삭제를
  먼저 시도하고, 세션이 만료됐으면 401 사유가 그대로 뜬다.
- 기존 테스트 관례를 따른다. Flask 라우트 검사는 `Flask(__name__)` 에 블루프린트를 붙이고
  `before_request` 로 `g.user_email` 을 심는다(`tests/app/test_kr_market_quota_http_routes_refactor.py`).
  vitest 는 대상 파일 옆 `*.test.tsx` 다.
- 다중 워커 한계: `clear_for_owner` 는 SQLite 에 삭제 표식을 남기지 않는다. `_mark_session_deleted`
  (`chatbot/storage.py:365`)는 프로세스 안의 장부에만 적고, 델타 경로(`storage_sqlite_history.py:622`)는
  평범한 `DELETE FROM chatbot_sessions` 를 실행한다. 다른 워커가 보통 되살리지 않는 이유는 접근 때마다
  파일 서명을 비교해 재적재하기 때문이다(`chatbot/storage.py:177-186`). 되살아나는 갈래는 델타 저장이
  실패해 전체 동기화 폴백(`chatbot/storage.py:158-162`)으로 떨어진 워커가 그 사이 재적재하지 못한 낡은
  사본을 upsert 할 때다. `[CHAT-033]` 은 그 폴백의 삭제 절만 없애므로 upsert 갈래는 그대로 남는다. 이
  계획은 그 결함을 고치지 않고 `[CHAT-033]` 의 범위에 그 갈래를 추가해 두며, QA 문서와 아카이브 메모에
  한계로 적는다.

## 파일 구조

| 파일 | 역할 | 변경 |
|---|---|---|
| `services/paper_trading_trade_account_mixin.py` | 모의투자 계좌 연산 | `delete_account` 추가, 스냅샷 정리 헬퍼 추출 |
| `chatbot/storage_memory_manager.py` | 챗봇 메모리 | `delete_owner` 추가(SQLite 성패를 돌려줌) |
| `services/kr_market_quota_runtime_service.py` | 사용량 파일 연산 | `delete_user_usage` 추가 |
| `app/routes/kr_market_user_data_routes.py` | 새 라우트 모듈 | `delete_user_data` 순수 함수 + `register_user_data_routes` |
| `app/routes/kr_market.py` | 블루프린트 조립 | `delete_user_usage` 래퍼, 등록 호출 |
| `frontend/src/app/components/SettingsModal.tsx` | 설정 모달 | `performResetData` 서버 삭제 선행, 문구 |
| `frontend/src/app/(legal)/privacy/page.tsx` | 개인정보처리방침 | 보관 기간 두 셀과 삭제 안내 한 문장 |
| `tests/services/test_paper_trading_owner_isolation.py` | 기존 | `delete_account` 검사 1건 추가 |
| `tests/chatbot/test_memory_owner_access.py` | 기존 | `delete_owner` 검사 1건 추가 |
| `tests/services/test_kr_market_quota_runtime_service_refactor.py` | 신규 | `delete_user_usage` 검사 2건 |
| `tests/app/test_kr_market_user_data_routes.py` | 신규 | 라우트 검사 5건(익명 거부, 소유자 일치, 부분 실패, 세션 0건, 챗봇 생성 실패) |
| `frontend/src/app/components/SettingsModal.account-delete.test.tsx` | 신규 | 실패·성공 경로 2건 |

---

### Task 1: 모의투자 `delete_account`

**Files:**
- Modify: `services/paper_trading_trade_account_mixin.py:321-334` (`reset_account` 아래)
- Test: `tests/services/test_paper_trading_owner_isolation.py` (끝에 추가)

**Interfaces:**
- Consumes: `self._validate_owner_id`, `self.get_context`, `self._execute_db_operation_with_schema_retry`
  (모두 기존)
- Produces: `PaperTradingService.delete_account(*, owner_id: str) -> bool`. 네 테이블
  (`portfolio`, `trade_log`, `asset_history`, `balance`)에서 그 소유자 행을 지운다. Task 4 가 부른다.

- [ ] **Step 1: 실패하는 검사를 쓴다**

```python
def test_delete_account_removes_only_that_owner_from_every_table(tmp_path):
    """계정 삭제는 reset 과 달리 balance 행까지 지우고 다른 소유자는 남긴다([FE-045])."""
    service = _service(tmp_path)
    for owner in (ALICE, BOB):
        assert service.buy_stock("005930", "삼성전자", 1_000, 1, owner_id=owner)["status"] == "success"
        service.record_asset_history(1_000, owner_id=owner)

    assert service.delete_account(owner_id=ALICE) is True

    with service.get_read_context() as conn:
        for table in ("balance", "portfolio", "trade_log", "asset_history"):
            owners = {row[0] for row in conn.execute(f"SELECT owner_id FROM {table}")}
            assert owners == {BOB}, table
    # 다시 접근하면 새 계좌다. 이전 잔고가 되살아나지 않는다.
    assert service.get_balance(owner_id=ALICE) == INITIAL_CASH_KRW
```

- [ ] **Step 2: 실패를 확인한다**

Run: `source venv/bin/activate && pytest -q tests/services/test_paper_trading_owner_isolation.py -k delete_account`
Expected: FAIL, `AttributeError: 'PaperTradingService' object has no attribute 'delete_account'`

- [ ] **Step 3: 구현한다**

`reset_account` 의 스냅샷 정리 세 줄을 헬퍼로 빼고 두 메서드가 같이 쓴다.

```python
    def _forget_asset_history_snapshot(self, owner_id: str) -> None:
        snapshot = getattr(self, "_last_asset_history_snapshot", None)
        if isinstance(snapshot, dict) and snapshot.get("owner_id") == owner_id:
            self._last_asset_history_snapshot = None

    def reset_account(self, *, owner_id: str) -> bool:
        owner_id = self._validate_owner_id(owner_id)
        def operation() -> None:
            with self.get_context() as conn:
                cursor = conn.cursor()
                self._ensure_owner_balance(cursor, owner_id)
                for table in ("portfolio", "trade_log", "asset_history"):
                    cursor.execute(f"DELETE FROM {table} WHERE owner_id = ?", (owner_id,))
                cursor.execute("UPDATE balance SET cash=?, total_deposit=0 WHERE owner_id=?", (INITIAL_CASH_KRW, owner_id))
                conn.commit()
        self._execute_db_operation_with_schema_retry(operation)
        self._forget_asset_history_snapshot(owner_id)
        return True

    def delete_account(self, *, owner_id: str) -> bool:
        """계정 삭제. reset_account 와 달리 balance 행도 남기지 않는다([FE-045]).

        다음 접근이 _ensure_owner 로 새 계좌를 만들므로 삭제 뒤 조회는 초기 잔고를 돌려준다.
        """
        owner_id = self._validate_owner_id(owner_id)
        def operation() -> None:
            with self.get_context() as conn:
                cursor = conn.cursor()
                for table in ("portfolio", "trade_log", "asset_history", "balance"):
                    cursor.execute(f"DELETE FROM {table} WHERE owner_id = ?", (owner_id,))
                conn.commit()
        self._execute_db_operation_with_schema_retry(operation)
        self._forget_asset_history_snapshot(owner_id)
        return True
```

- [ ] **Step 4: 통과를 확인한다**

Run: `pytest -q tests/services/test_paper_trading_owner_isolation.py tests/test_paper_trading_service.py`
Expected: PASS (기존 검사 포함)

---

### Task 2: 챗봇 메모리 `delete_owner`

**Files:**
- Modify: `chatbot/storage_memory_manager.py:231-243` (`clear` 아래)
- Test: `tests/chatbot/test_memory_owner_access.py` (끝에 추가)

**Interfaces:**
- Consumes: `self._reload`, `clear_memories_in_sqlite(db_path, logger, *, owner_id)`,
  `self._write_legacy_memory_snapshot(memories, *, allow_uncommitted)` (모두 기존)
- Produces: `MemoryManager.delete_owner(owner_id: str) -> bool`. `clear` 와 같은 일을 하되 SQLite
  삭제의 성패를 그대로 돌려준다. `clear` 는 채팅 명령 `/clear all` 이 문자열을 기대하므로 그대로 둔다.
  세션 쪽은 기존 `HistoryManager.clear_for_owner(owner_id) -> int` 를 그대로 쓴다(`chatbot/storage.py:348`).
  레거시 JSON 스냅샷도 결과적으로 덮인다. `clear_for_owner` 는 삭제 장부가 비지 않으면 스냅샷을 강제로
  다시 쓰고(`chatbot/storage.py:164-168`), `delete_owner` 는 `_write_legacy_memory_snapshot` 을 부른다.
  `_load` 는 SQLite 가 빌 때만 레거시로 떨어진다(`chatbot/storage.py:125-137`).

- [ ] **Step 1: 실패하는 검사를 쓴다**

```python
def test_delete_owner_removes_profile_too_and_keeps_other_owners(monkeypatch, tmp_path: Path):
    """계정 삭제는 user_profile 까지 지우고 다른 소유자와 공용 행은 남긴다([FE-045])."""
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)
    manager = chatbot_core.MemoryManager("u1")
    manager.add("risk", "aggressive", owner_id="alice@example.test")
    update_user_profile(manager, "앨리스", "리서치", "alice@example.test")
    manager.add("risk", "conservative", owner_id="bob@example.test")
    manager.add("interest", "종가베팅")  # 공용

    assert manager.delete_owner("alice@example.test") is True

    with sqlite3.connect(resolve_chatbot_storage_db_path(tmp_path)) as conn:
        owners = sorted({row[0] for row in conn.execute("SELECT owner_id FROM chatbot_memories")})
    assert owners == ["", "bob@example.test"]
    assert manager.view("alice@example.test") == {}
    assert manager.delete_owner("") is False
```

`update_user_profile` 과 `sqlite3`, `resolve_chatbot_storage_db_path` 는 이 파일이 이미 import 한다.
`manager.view` 가 `dict` 가 아니라 다른 형태를 돌려주면 그 형태의 「비어 있음」으로 단언을 맞춘다.

- [ ] **Step 2: 실패를 확인한다**

Run: `pytest -q tests/chatbot/test_memory_owner_access.py -k delete_owner`
Expected: FAIL, `AttributeError: ... has no attribute 'delete_owner'`

- [ ] **Step 3: 구현한다**

```python
    def delete_owner(self, owner_id: str) -> bool:
        """한 소유자의 메모리를 프로필까지 지우고 SQLite 삭제의 성패를 돌려준다([FE-045]).

        clear 와 달리 소유자를 모르면 공용으로 떨어지지 않고 거절한다. 계정 삭제가 공용
        캐시를 지워서는 안 된다.
        """
        if not owner_id:
            return False
        self._reload()
        self.memories.pop(owner_id, None)
        deleted = clear_memories_in_sqlite(self.db_path, logger=logger, owner_id=owner_id)
        if not deleted:
            logger.error("SQLite memory delete failed for owner; legacy snapshot only")
        self._write_legacy_memory_snapshot(self.memories, allow_uncommitted=not deleted)
        return deleted
```

- [ ] **Step 4: 통과를 확인한다**

Run: `pytest -q tests/chatbot/test_memory_owner_access.py tests/chatbot/test_storage_memory_batch.py`
Expected: PASS

---

### Task 3: 사용량 `delete_user_usage`

**Files:**
- Modify: `services/kr_market_quota_runtime_service.py` (`recharge_user_usage` 아래)
- Modify: `app/routes/kr_market.py:254-275` 근처 (`increment_user_usage` 아래에 래퍼)
- Test: `tests/services/test_kr_market_quota_runtime_service_refactor.py` (신규)

**Interfaces:**
- Consumes: `RECHARGE_DAY_PREFIX`, `load_quota_data_unlocked`, `save_quota_data_unlocked` (기존)
- Produces: `delete_user_usage(*, usage_key, quota_lock, load_quota_data_unlocked,
  save_quota_data_unlocked, load_json_file, atomic_write_text, quota_file_path) -> bool` 와
  `app/routes/kr_market.py` 의 `delete_user_usage(email) -> bool`. Task 4 가 후자를 주입받는다.

- [ ] **Step 1: 실패하는 검사를 쓴다**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[FE-045] 계정 삭제가 무료 사용량과 충전 날짜를 함께 지운다."""

import threading

from services.kr_market_quota_runtime_service import RECHARGE_DAY_PREFIX, delete_user_usage


def _make_store(initial: dict[str, int]):
    store = dict(initial)

    def load(**_kwargs):
        return dict(store)

    def save(quota_data, **_kwargs):
        store.clear()
        store.update(quota_data)

    return store, load, save


def _delete(store_fns, usage_key):
    _store, load, save = store_fns
    return delete_user_usage(
        usage_key=usage_key,
        quota_lock=threading.Lock(),
        load_quota_data_unlocked=load,
        save_quota_data_unlocked=save,
        load_json_file=lambda *_a, **_k: {},
        atomic_write_text=lambda *_a, **_k: None,
        quota_file_path="unused.json",
    )


def test_delete_removes_usage_and_recharge_day_but_keeps_others():
    store_fns = _make_store({
        "alice@example.test": 7,
        f"{RECHARGE_DAY_PREFIX}alice@example.test": 20260922,
        "bob@example.test": 3,
    })

    assert _delete(store_fns, "alice@example.test") is True

    assert store_fns[0] == {"bob@example.test": 3}


def test_delete_without_key_or_unknown_owner():
    store_fns = _make_store({"bob@example.test": 3})

    assert _delete(store_fns, None) is False
    assert _delete(store_fns, "nobody@example.test") is True
    assert store_fns[0] == {"bob@example.test": 3}
```

- [ ] **Step 2: 실패를 확인한다**

Run: `pytest -q tests/services/test_kr_market_quota_runtime_service_refactor.py`
Expected: FAIL, `ImportError: cannot import name 'delete_user_usage'`

- [ ] **Step 3: 구현한다**

`services/kr_market_quota_runtime_service.py` 끝에:

```python
def delete_user_usage(
    *,
    usage_key: str | None,
    quota_lock,
    load_quota_data_unlocked: Callable,
    save_quota_data_unlocked: Callable,
    load_json_file: Callable[[str], dict],
    atomic_write_text: Callable[[str, str], None],
    quota_file_path: str,
) -> bool:
    """사용량과 충전 날짜를 함께 지운다([FE-045]). 지울 것이 없어도 True 다."""
    if not usage_key:
        return False

    day_key = f"{RECHARGE_DAY_PREFIX}{usage_key}"
    with quota_lock:
        quota_data = load_quota_data_unlocked(load_json_file=load_json_file)
        if usage_key not in quota_data and day_key not in quota_data:
            return True
        quota_data.pop(usage_key, None)
        quota_data.pop(day_key, None)
        save_quota_data_unlocked(
            quota_data=quota_data,
            atomic_write_text=atomic_write_text,
            quota_file_path=quota_file_path,
        )
    return True
```

`app/routes/kr_market.py` 의 import 블록(24행 근처)에 `delete_user_usage as delete_user_usage_service`
를 더하고 `increment_user_usage` 아래에:

```python
def delete_user_usage(email):
    """계정 삭제가 부른다. 사용량과 충전 날짜를 함께 지운다([FE-045])."""
    return delete_user_usage_service(
        usage_key=email,
        quota_lock=_quota_lock,
        load_quota_data_unlocked=load_quota_data_unlocked_service,
        save_quota_data_unlocked=save_quota_data_unlocked_service,
        load_json_file=load_json_file,
        atomic_write_text=_atomic_write_text,
        quota_file_path=QUOTA_FILE,
    )
```

- [ ] **Step 4: 통과를 확인한다**

Run: `pytest -q tests/services/test_kr_market_quota_runtime_service_refactor.py tests/services/test_quota_recharge_daily_limit.py`
Expected: PASS

---

### Task 4: 라우트 `DELETE /api/kr/user/data`

**Files:**
- Create: `app/routes/kr_market_user_data_routes.py`
- Modify: `app/routes/kr_market.py` (import 두 줄, 등록 호출 한 블록, `_get_chatbot` 헬퍼)
- Test: `tests/app/test_kr_market_user_data_routes.py` (신규)

**Interfaces:**
- Consumes: Task 1 `paper_trading.delete_account(owner_id=)`, Task 2 `bot.memory.delete_owner(owner)`,
  기존 `bot.history.clear_for_owner(owner) -> int`, Task 3 `delete_user_usage(email) -> bool`,
  `app.routes.route_execution.execute_json_route`, `services.paper_trading.get_paper_trading_service`
- Produces: `delete_user_data(*, owner_id, get_chatbot_fn, get_paper_trading_fn, delete_user_usage_fn,
  logger) -> tuple[int, dict]` 와 `register_user_data_routes(kr_bp, *, logger, get_chatbot_fn,
  get_paper_trading_fn, delete_user_usage_fn)`. getter 는 각 단계 안에서 부른다. 인자로 먼저 평가하면
  `get_chatbot()` 의 지연 생성이 던지는 예외 하나가 나머지 저장소 삭제까지 막는다. 응답은 200 `{"status": "deleted", "deleted": {...}}`,
  401 `{"error": "로그인이 필요합니다."}`, 500 `{"error": "...", "deleted": {...}, "failed": [...]}`.

- [ ] **Step 1: 실패하는 검사를 쓴다**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[FE-045] 자기 기록 삭제 경로: 서명된 신원만 통과하고 세 저장소를 모두 부른다.

신원은 before_request 가 g.user_email 로 확정한다. 쿼리·본문의 owner_id 는 무시되어야 한다.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace

from flask import Blueprint, Flask, g

from app.routes.kr_market_user_data_routes import register_user_data_routes


class _Recorder:
    def __init__(self, *, fail: str | None = None) -> None:
        self.calls: list[tuple[str, str]] = []
        self.fail = fail

    def hit(self, name: str, owner: str, result):
        self.calls.append((name, owner))
        if self.fail == name:
            raise RuntimeError(name)
        return result


def _client(*, user_email: str | None, fail: str | None = None, session_count: int = 2):
    recorder = _Recorder(fail=fail)
    bot = SimpleNamespace(
        history=SimpleNamespace(clear_for_owner=lambda owner: recorder.hit("chat_sessions", owner, session_count)),
        memory=SimpleNamespace(delete_owner=lambda owner: recorder.hit("chat_memories", owner, True)),
    )
    paper = SimpleNamespace(delete_account=lambda *, owner_id: recorder.hit("paper_trading", owner_id, True))
    app = Flask(__name__)
    app.testing = True

    @app.before_request
    def _seed_identity():
        g.user_email = user_email

    bp = Blueprint("user_data_test", __name__)
    register_user_data_routes(
        bp,
        logger=logging.getLogger("test.user_data"),
        get_chatbot_fn=lambda: bot,
        get_paper_trading_fn=lambda: paper,
        delete_user_usage_fn=lambda owner: recorder.hit("usage", owner, True),
    )
    app.register_blueprint(bp, url_prefix="/api/kr")
    return app.test_client(), recorder


def test_anonymous_request_is_refused_before_any_store():
    client, recorder = _client(user_email=None)
    response = client.delete(
        "/api/kr/user/data?owner_id=victim@example.test",
        json={"owner_id": "victim@example.test"},
        headers={"X-User-Email": "victim@example.test"},
    )
    assert response.status_code == 401
    assert recorder.calls == []


def test_verified_owner_clears_every_store_with_its_own_email():
    client, recorder = _client(user_email="alice@example.test")
    response = client.delete("/api/kr/user/data", json={"owner_id": "victim@example.test"})
    assert response.status_code == 200
    assert response.get_json()["deleted"] == {
        "chat_sessions": 2, "chat_memories": True, "paper_trading": True, "usage": True,
    }
    assert recorder.calls == [
        (name, "alice@example.test")
        for name in ("chat_sessions", "chat_memories", "paper_trading", "usage")
    ]


def test_one_failing_store_still_clears_the_rest_and_reports_500():
    client, recorder = _client(user_email="alice@example.test", fail="paper_trading")
    response = client.delete("/api/kr/user/data")
    assert response.status_code == 500
    payload = response.get_json()
    assert payload["failed"] == ["paper_trading"]
    assert payload["deleted"] == {"chat_sessions": 2, "chat_memories": True, "usage": True}
    assert [name for name, _ in recorder.calls] == ["chat_sessions", "chat_memories", "paper_trading", "usage"]


def test_zero_sessions_is_a_success_not_a_failure():
    """clear_for_owner 의 0 건은 실패(False)가 아니다. `== False` 로 바꾸면 여기서 잡힌다."""
    client, _recorder = _client(user_email="alice@example.test", session_count=0)
    response = client.delete("/api/kr/user/data")
    assert response.status_code == 200
    assert response.get_json()["deleted"]["chat_sessions"] == 0


def test_chatbot_construction_failure_still_clears_the_other_stores():
    """get_chatbot() 의 지연 생성이 던져도 모의투자와 사용량은 지운다(계획 검토 B1)."""
    recorder = _Recorder()
    paper = SimpleNamespace(delete_account=lambda *, owner_id: recorder.hit("paper_trading", owner_id, True))
    app = Flask(__name__)
    app.testing = True

    @app.before_request
    def _seed_identity():
        g.user_email = "alice@example.test"

    def _broken_chatbot():
        raise RuntimeError("chatbot init failed")

    bp = Blueprint("user_data_broken_bot", __name__)
    register_user_data_routes(
        bp,
        logger=logging.getLogger("test.user_data"),
        get_chatbot_fn=_broken_chatbot,
        get_paper_trading_fn=lambda: paper,
        delete_user_usage_fn=lambda owner: recorder.hit("usage", owner, True),
    )
    app.register_blueprint(bp, url_prefix="/api/kr")
    response = app.test_client().delete("/api/kr/user/data")
    assert response.status_code == 500
    payload = response.get_json()
    assert payload["failed"] == ["chat_sessions", "chat_memories"]
    assert payload["deleted"] == {"paper_trading": True, "usage": True}
    assert [name for name, _ in recorder.calls] == ["paper_trading", "usage"]
```

- [ ] **Step 2: 실패를 확인한다**

Run: `pytest -q tests/app/test_kr_market_user_data_routes.py`
Expected: FAIL, `ModuleNotFoundError: No module named 'app.routes.kr_market_user_data_routes'`

- [ ] **Step 3: 구현한다**

`app/routes/kr_market_user_data_routes.py`:

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""로그인한 사용자가 서버에 남긴 자기 기록을 한 번에 지우는 경로([FE-045]).

신원은 before_request 가 서명 헤더에서 확정한 g.user_email 뿐이다. 관리자가 남을 지우는
인자는 두지 않는다. 세 저장소는 파일이 달라 한 트랜잭션으로 묶을 수 없으므로 앞이 실패해도
뒤를 계속 지우고, 하나라도 실패하면 500 으로 알려 화면이 로그아웃하지 않게 한다.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from flask import g, jsonify

from app.routes.route_execution import execute_json_route


def delete_user_data(
    *,
    owner_id: str,
    get_chatbot_fn: Callable[[], Any],
    get_paper_trading_fn: Callable[[], Any],
    delete_user_usage_fn: Callable[[str], bool],
    logger: logging.Logger,
) -> tuple[int, dict[str, Any]]:
    # getter 는 각 단계 안에서 부른다. 챗봇의 지연 생성이 던져도 다른 저장소는 계속 지운다.
    # 반환형: clear_for_owner 는 지운 건수(int, 0 도 성공), 나머지 셋은 bool 이다. 실패는
    # 예외 또는 False 뿐이다.
    steps = (
        ("chat_sessions", lambda: get_chatbot_fn().history.clear_for_owner(owner_id)),
        ("chat_memories", lambda: get_chatbot_fn().memory.delete_owner(owner_id)),
        ("paper_trading", lambda: get_paper_trading_fn().delete_account(owner_id=owner_id)),
        ("usage", lambda: delete_user_usage_fn(owner_id)),
    )
    deleted: dict[str, Any] = {}
    failed: list[str] = []
    for name, step in steps:
        try:
            result = step()
        except Exception as error:
            logger.error("User data delete failed at %s: %s", name, error)
            failed.append(name)
            continue
        if result is False:
            failed.append(name)
            continue
        deleted[name] = result
    if failed:
        return 500, {
            "error": "일부 기록을 지우지 못했습니다. 잠시 후 다시 시도해 주세요.",
            "deleted": deleted,
            "failed": failed,
        }
    return 200, {"status": "deleted", "deleted": deleted}


def register_user_data_routes(
    kr_bp: Any,
    *,
    logger: logging.Logger,
    get_chatbot_fn: Callable[[], Any],
    get_paper_trading_fn: Callable[[], Any],
    delete_user_usage_fn: Callable[[str], bool],
) -> None:
    @kr_bp.route("/user/data", methods=["DELETE"])
    def delete_my_data():
        def _handler():
            owner_id = g.get("user_email")
            if not owner_id:
                return jsonify({"error": "로그인이 필요합니다."}), 401
            status_code, payload = delete_user_data(
                owner_id=owner_id,
                get_chatbot_fn=get_chatbot_fn,
                get_paper_trading_fn=get_paper_trading_fn,
                delete_user_usage_fn=delete_user_usage_fn,
                logger=logger,
            )
            return jsonify(payload), status_code

        return execute_json_route(handler=_handler, logger=logger, error_label="Delete user data error")
```

`app/routes/kr_market.py`: import 에 `from app.routes.kr_market_user_data_routes import
register_user_data_routes` 와 `from services.paper_trading import get_paper_trading_service` 를 더하고,
`register_chatbot_and_quota_routes(...)` 호출 바로 뒤에:

```python
def _get_chatbot():
    # 다른 챗봇 라우트처럼 핸들러 안에서 늦게 만든다. 모듈 import 시점의 챗봇 초기화를 피한다.
    from chatbot import get_chatbot
    return get_chatbot()


register_user_data_routes(
    kr_bp,
    logger=logger,
    get_chatbot_fn=_get_chatbot,
    get_paper_trading_fn=get_paper_trading_service,
    delete_user_usage_fn=delete_user_usage,
)
```

`execute_json_route` 의 실제 시그니처는 `app/routes/route_execution.py` 에서 확인하고, 이름이
다르면 `kr_market_quota_http_routes.py:15` 와 같은 방식으로 import 한다.

- [ ] **Step 4: 통과를 확인한다**

Run: `pytest -q tests/app/test_kr_market_user_data_routes.py tests/app/test_kr_market_quota_http_routes_refactor.py tests/app/test_kr_market_route_integration.py`
Expected: PASS. 통합 검사가 앱 조립을 지나므로 `kr_market.py` 의 등록 오타가 여기서 잡힌다.

---

### Task 5: 설정 모달의 「계정 삭제」

**Files:**
- Modify: `frontend/src/app/components/SettingsModal.tsx:127-141` (`performResetData`),
  `:1059` (Danger Zone 설명), `:1108-1114` (확인 대화 문구, 첫 문장 1109행), import 한 줄
- Test: `frontend/src/app/components/SettingsModal.account-delete.test.tsx` (신규)

**Interfaces:**
- Consumes: `fetchAPI` (`@/lib/api`), `signOut` (`next-auth/react`), 기존 상태
  `isGoogleLoggedIn`·`setTestModal`·`setIsDeleteConfirmOpen`
- Produces: 확인 버튼 → 항상 `DELETE /api/kr/user/data` 먼저 → 성공 시 저장소 비우고
  `signOut({ callbackUrl: '/' })`, 실패 시 확인 대화를 닫고 `testModal` 에 「계정 삭제 실패」와
  서버 사유(세션 만료면 401 의 「로그인이 필요합니다.」). 익명 분기는 두지 않는다(전역 제약 참고).

- [ ] **Step 1: 실패하는 검사를 쓴다**

```tsx
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import SettingsModal from './SettingsModal';

const signOut = vi.hoisted(() => vi.fn());
const fetchAPI = vi.hoisted(() => vi.fn());

vi.mock('next-auth/react', () => ({
  useSession: () => ({
    data: { user: { name: '테스터', email: 'tester@example.com' } },
    status: 'authenticated',
  }),
  signIn: vi.fn(),
  signOut,
}));
vi.mock('next/navigation', () => ({ useRouter: () => ({ refresh: vi.fn(), push: vi.fn() }) }));
vi.mock('@/hooks/useAdmin', () => ({ useAdmin: () => ({ isAdmin: false, isLoading: false }) }));
vi.mock('@/lib/session', () => ({ getBrowserSessionId: () => 'delete-test' }));
vi.mock('@/lib/api', () => ({ fetchAPI }));

function mockServer(deleteResult: () => Promise<unknown>) {
  fetchAPI.mockImplementation(async (url: string) => {
    if (url === '/api/kr/user/data') return deleteResult();
    // useQuota 도 fetchAPI 를 쓴다. 사용량 조회는 실패로 두어 「사용량을 불러올 수 없습니다」
    // 상태가 되고 삭제 흐름과 무관하다. 한 번짜리 mock 은 그 조회가 먼저 소비한다.
    throw new Error('사용량 응답 없음');
  });
}

function clickConfirmDelete() {
  render(
    <SettingsModal
      isOpen
      onClose={() => {}}
      profile={{ name: '테스터', email: 'tester@example.com', persona: '' }}
      onSave={async () => {}}
    />
  );
  fireEvent.click(screen.getAllByRole('button', { name: '계정 삭제' })[0]);
  fireEvent.click(screen.getByRole('button', { name: '삭제 (복구 불가)' }));
}

describe('[FE-045] 계정 삭제는 서버 기록을 먼저 지운다', () => {
  beforeEach(() => {
    signOut.mockReset();
    fetchAPI.mockReset();
    localStorage.clear();
  });

  it('서버 삭제가 실패하면 로그아웃하지 않고 실패 사유를 보인다', async () => {
    mockServer(async () => {
      throw new Error('일부 기록을 지우지 못했습니다. 잠시 후 다시 시도해 주세요.');
    });
    localStorage.setItem('probe', '1');

    clickConfirmDelete();

    await waitFor(() => expect(screen.getByText('계정 삭제 실패')).toBeTruthy());
    expect(fetchAPI).toHaveBeenCalledWith('/api/kr/user/data', { method: 'DELETE', timeout: 30000 });
    expect(signOut).not.toHaveBeenCalled();
    expect(localStorage.getItem('probe')).toBe('1');
    expect(screen.getByText(/일부 기록을 지우지 못했습니다/)).toBeTruthy();
  });

  it('서버 삭제가 성공하면 브라우저 저장소를 비우고 로그아웃한다', async () => {
    mockServer(async () => ({ status: 'deleted' }));
    localStorage.setItem('probe', '1');

    clickConfirmDelete();

    await waitFor(() => expect(signOut).toHaveBeenCalledWith({ callbackUrl: '/' }));
    expect(localStorage.getItem('probe')).toBeNull();
  });
});
```

- [ ] **Step 2: 실패를 확인한다**

Run: `(cd frontend && npx vitest run src/app/components/SettingsModal.account-delete.test.tsx)`
Expected: 첫 검사 FAIL(`fetchAPI` 미호출·`signOut` 호출됨), 둘째는 우연히 통과할 수 있다. 첫 검사의
실패가 RED 근거다. 구현 중 발견: `useQuota` 가 `fetchAPI` 로 `/api/kr/user/quota` 를 먼저 부르므로
한 번짜리 mock(`mockRejectedValueOnce`)은 그 조회가 소비한다. 그래서 URL 로 가르는 `mockServer` 를
쓰고 `global.fetch` 모의(계획 검토 m1)는 `@/lib/api` 를 통째로 모의하는 이 검사에서는 닿지 않아 뺐다.

- [ ] **Step 3: 구현한다**

import 에 `import { fetchAPI } from '@/lib/api';` 를 더한다(`@/lib/session` import 옆).
`performResetData` 를 다음으로 바꾼다.

```tsx
  const performResetData = async () => {
    // 서버 기록을 먼저 지운다. 실패하면 로그아웃하지 않아야 사용자가 지워졌다고 믿지 않는다.
    // 두 진입점 모두 로그인(또는 관리자) 상태에서만 보이므로 로그인 여부로 가르지 않는다.
    // 세션이 그 사이 만료됐으면 서버가 401 을 돌려주고 그 사유가 그대로 뜬다.
    // try 는 서버 삭제만 감싼다. 뒤의 signOut 실패까지 「지워지지 않았다」로 알리면 그것이 거짓이다.
    try {
      // 세 저장소를 잇달아 지우는 동안 SQLite 재시도가 겹칠 수 있어 기본 10초보다 길게 둔다.
      await fetchAPI('/api/kr/user/data', { method: 'DELETE', timeout: 30000 });
    } catch (e) {
      console.error(e);
      setIsDeleteConfirmOpen(false);
      setTestModal({
        isOpen: true,
        type: 'danger',
        title: '계정 삭제 실패',
        content: `${e instanceof Error ? e.message : String(e)} 일부 기록은 이미 지워졌을 수 있고 로그아웃하지 않았습니다. 다시 시도하면 남은 기록을 지웁니다.`,
      });
      return;
    }
    localStorage.clear();
    sessionStorage.clear();
    try {
      await signOut({ callbackUrl: '/' });
    } catch (e) {
      console.error(e);
      // 기록은 이미 지워졌다. 로그아웃 요청만 실패했으므로 삭제 실패로 알리지 않고 그 사실만 알린다.
      setIsDeleting(false);
      setIsDeleteConfirmOpen(false);
      setTestModal({
        isOpen: true,
        type: 'default',
        title: '계정 삭제 완료',
        content: '서버 기록은 지워졌지만 로그아웃 요청이 실패했습니다. 페이지를 새로 고친 뒤 다시 로그아웃해 주세요.',
      });
    }
  };
```

심층 리뷰 반영으로 `isDeleting` 상태를 두어 서버 삭제가 도는 동안(`setIsDeleting(true)` … 실패 갈래에서
`false`) 확인 버튼을 `disabled` 로 두고 문구를 「삭제 중…」 으로 바꾼다. Danger Zone(관리자 전용)의 제목과
버튼은 「계정 삭제」 로 맞춘다. 검사 「요청이 도는 동안 확인 버튼이 비활성화되고 진행 문구를 보인다」 추가.

Danger Zone 설명(1058-1060행)을 다음으로 바꾼다.

```tsx
                          서버에 저장된 AI 상담 기록과 메모리, 모의투자 계좌, 무료 사용량 기록과 이 브라우저의 설정을 지우고 로그아웃합니다.
```

확인 대화 본문(1106-1112행)을 다음으로 바꾼다.

```tsx
          <p className="mb-2 font-bold text-white">정말로 계정을 삭제하시겠습니까?</p>
          <p className="text-sm text-gray-400">
            이 작업은 되돌릴 수 없습니다.<br />
            서버에 저장된 AI 상담 기록과 메모리(프로필 포함), 모의투자 계좌, 무료 사용량 기록이 지워지고 로그아웃됩니다.<br />
            다른 기기에 로그인이 남아 있으면 그 기기도 로그아웃해 주세요. 남은 세션이 화면을 열면 빈 모의투자 계좌가 다시 만들어집니다.<br />
            활동 로그 파일은 이 화면에서 지우지 않으며 30일이 지나면 자동으로 삭제됩니다.
          </p>
```

(위 두 코드 블록은 코드 리뷰·보안 리뷰 반영 뒤의 최종 판이다. 초판의 `if (isGoogleLoggedIn)` 분기와
「서버에 남은 기록은 지워지지 않았고」 문구는 폐기했다. 끝의 「코드 리뷰·보안 리뷰 반영」 절 참고.)

- [ ] **Step 4: 통과를 확인한다**

Run: `(cd frontend && npx vitest run src/app/components/)`
Expected: PASS. 기존 `SettingsModal.*.test.tsx` 가 같이 통과한다.

---

### Task 6: 개인정보처리방침 문구

**Files:**
- Modify: `frontend/src/app/(legal)/privacy/page.tsx:168-189`

문구 네 곳만 바꾼다. 검사는 만들지 않는다(문구 변경). 이 파일은 `metadata` 를 export 하는
서버 컴포넌트이고 `'use client'` 가 없다. 문구만 바뀌고 경계·데이터 조회·파일 배치는 그대로이므로
`frontend-skills.md` §2 의 표에서 「라우트 파일 배치, `layout` 과 `page`」 줄에 해당하고, 번들 문서
`01-app/01-getting-started/03-layouts-and-pages.md` 를 읽고 그렇게 판정한다(계획 검토 m4).

- [ ] **Step 1: 세 셀과 한 문장을 바꾼다**

「AI 상담 기록과 메모리」 셀:
```
이용자가 대화를 지우거나 설정의 「계정 삭제」로 직접 지우거나 운영자에게 삭제를 요청할 때까지
```
「모의투자 기록」 셀:
```
이용자가 설정의 「계정 삭제」로 직접 지우거나 운영자에게 삭제를 요청할 때까지. 계좌를 초기화하면 보유 종목과 매매 내역, 자산 이력은 그 시점에 지워집니다.
```
「이용량 기록」 셀:
```
이용자가 설정의 「계정 삭제」로 직접 지우거나 운영자에게 삭제를 요청할 때까지
```
표 아래 문단의 마지막 문장:
```
기록을 지우려면 설정의 「계정 삭제」를 쓰거나 아래 8항의 방법으로 삭제를 요청하시기 바랍니다.
```

- [ ] **Step 2: 타입 검사를 돌린다**

Run: `(cd frontend && npm run type-check)`
Expected: exit 0

---

### Task 7: 정적 검증과 QA 계획

- [ ] `source venv/bin/activate && pytest -q` → 실패 0 (기준 2615 통과 2 skip + 신규 7)
- [ ] `(cd frontend && npx vitest run)` → 실패 0 (기준 90 파일 670 통과 + 신규 2)
- [ ] `(cd frontend && npm run type-check)` → exit 0
- [ ] `(cd frontend && npm run lint)` → 오류 0, 새 경고 0(기존 184 는 그대로)
- [ ] `git diff --stat` 로 티어 재판정(위험 경로에 닿으므로 T3 고정)
- [ ] `docs/dev-cycle/qa/FE-045.md` 시나리오: 격리 사본(`closing-bet-verify` 의 구성, `[CHAT-036]` 의
  `qa_app.py` 가짜 Gemini 재사용, 비관리자 이메일의 NextAuth 세션 쿠키)에서
  S-1 대화 1건·모의 매수 1건·프로필 저장 뒤 설정 → 계정 삭제 → `/` 로 로그아웃. 사본
  `chatbot_storage.db` 의 세 테이블과 `user_quota.json` 에 그 이메일 행·키 0, `paper_trading.db` 는
  `portfolio`·`trade_log` 행 0 이고 `balance` 는 없거나 초기 잔고, `asset_history` 는 없거나 삭제
  시각 이후 항목만(회귀, required, browser). 뒤의 두 조건이 느슨한 이유는 `GET /api/portfolio` 가
  `get_balance` 로 잔고 행을 다시 만들고 자산 이력을 기록하기 때문이다(`CLAUDE.md` Important Notes 4,
  `common_portfolio_routes.py:93`). 로그아웃이 끝나기 전 대시보드 폴링 한 번이면 두 행이 되살아난다;
  S-2 같은 쿠키로 다시 열면 대화 목록 비고 모의투자 잔고 초기값·사용량 0(회귀, required, browser);
  S-3 익명 화면에는 「계정 삭제」 진입점이 없고 `DELETE /api/kr/user/data` 요청이 0건(인접, required, browser.
  계획 초판의 「브라우저 저장소만 비움」은 도달 불가로 확인되어 QA 문서에서 이렇게 바뀜);
  S-4 격리 Flask 에 신원 없는 `DELETE` → 401(인접, required, 하네스 curl);
  S-5 pytest·vitest 전체(회귀, required).
  `/_next/mcp` 두 관점을 함께 읽는다.

---

## 계획 검토 결과

`oh-my-claudecode:critic`(`fe045-critic`, 2026-09-22) 판정 `REVISE`. 반영: B1(getter 를 각 단계 안에서
부름, 챗봇 생성 실패 검사 추가), B2(다중 워커 한계 서술을 코드대로 고치고 upsert 갈래를 `[CHAT-033]`
범위에 추가), B3(`try` 는 서버 삭제만 감쌈), M1(`engine/services/usage_tracker.py` 의 `api_usage` 를
조사 정정에 추가, 로컬 두 테이블 행 0, 운영 서버 확인은 `[INFRA-079]`), M2(S-1 의 `balance`·
`asset_history` 기대값 완화와 이유), M3(세션 0건 검사 추가, 반환형 주석), m1(`global.fetch` 모의),
m2(줄 번호), m3(방침 세 번째 셀), m4(방침 페이지의 번들 문서 판정), 관찰의 `timeout: 30000`.
미반영: m5(`get_chatbot_fn` 주입 제거)는 B1 의 챗봇 생성 실패 검사가 그 주입으로 실패를 주입하므로
유지한다. 검사 파일 이름의 `_refactor` 접미사는 `tests/app/` 에 두 형태가 섞여 있어 그대로 둔다.
관찰로만 기록: 서명 재전송은 `[INFRA-062]` 가 nonce 저장소를 두지 않기로 한 기존 성질이며 삭제가
멱등이라 위험도 낮음.

## 코드 리뷰·보안 리뷰 반영

`closing-bet-reviewer`(`fe045-reviewer`) CHANGES_REQUIRED(medium 1·low 3·관찰 2), `oh-my-claudecode:security-reviewer`
(`fe045-security`) CHANGES_REQUIRED(중 1·중하 2·하 1·정보 1). 겹치는 핵심 두 건과 나머지를 다음과 같이 반영했다.

- 세션 저장 실패의 거짓 성공(양쪽 medium/중): `HistoryManager._save()` 가 성패를 `bool` 로 돌려주고,
  `clear_for_owner` 는 `_reload_sessions(force=True)` 로 SQLite 를 다시 읽은 뒤 저장이 실패하면 `RuntimeError`
  를 던진다. 강제 재적재는 직전 저장이 실패해 메모리에서만 사라진 세션을 다음 호출이 다시 찾게 한다.
  `/clear all` 명령(`chatbot/command_service.py`)은 그 예외를 잡아 경고를 돌려준다. 검사 2건 추가.
- 메모리 스냅샷 실패(양쪽 low/중하): `delete_owner` 가 `deleted and written` 을 돌려준다. 검사 1건 추가.
- 로그인 판정이 좁아 서버 호출이 생략되는 갈래(보안 중하)와 익명 갈래 도달 불가(코드 관찰): `if (isGoogleLoggedIn)`
  분기를 지우고 항상 서버 삭제를 먼저 시도한다. 만료된 세션은 401 사유가 뜬다.
- 실패 문구(코드 low): 「일부 기록은 이미 지워졌을 수 있고 로그아웃하지 않았습니다」로 부분 삭제를 인정한다.
- 다른 기기의 세션이 `GET /api/portfolio` 로 잔고 행을 되살리는 문제(보안 하): 확인 대화에 다른 기기 로그아웃
  안내 한 줄.
- 계획 Task 7 S-3 의 낡은 문구(코드 low): 위 전역 제약과 Task 7 을 고쳤다.
- 정보로만 기록: 레이트 리밋 부재는 저장소 전체의 성질, 이 `DELETE` 자체가 활동 로그에 이메일과 함께 남는 것은
  `[FE-046]` 범위.

## 심층 리뷰(T3) 반영

`oh-my-claudecode:critic`(`fe045-deep`, review 스킬 절차, scratchpad 재현 포함) `ACCEPT-WITH-RESERVATIONS`.
반영: (중하) 삭제 요청이 도는 동안 진행 표시가 없어 재클릭이 반복 요청을 만듦 → `isDeleting` 으로 버튼
비활성화와 「삭제 중…」, 검사 1건. (하) `signOut` 실패에 처리기가 없음 → 별도 `catch` 에서 「서버 기록은
지워졌지만 로그아웃 요청이 실패했습니다」 안내(처음의 `window.location.assign('/')` 은 Next lint 규칙
`no-location-assign-relative-destination` 에 걸려 안내 모달로 바꿈). (하) Danger Zone 제목·버튼의 옛 문구
「모든 설정 초기화」「초기화 및 삭제」 → 「계정 삭제」. 미반영: (하) SQLite 삭제가 커밋된 뒤 레거시 스냅샷
쓰기가 예외를 던지면 500 → 안전한 방향(지워졌는데 실패로 알림)이고 재시도가 멱등이라 그대로 둔다.
깨끗하다고 확인한 것: `_save()` 반환형 변경의 무회귀, 강제 재적재와 `_pending_*` 장부의 정합(재현),
`delete_owner` 의 스냅샷 주기 무관, `delete_account` 의 스키마 복구 재시도 안전성과 `price_cache` 미접촉,
`chatbot_messages` CASCADE, 라우트 분기 다섯 검사, 삭제 대상 범위, 다중 워커 서술.
