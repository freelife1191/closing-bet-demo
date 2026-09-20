#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQLite 2단 캐시(메모리 + SQLite)의 공용 골격.

chatbot 의 두 캐시 모듈이 각자 갖고 있던 준비 상태 단일 비행, LRU 상한, 신규 키 판정,
강제 프루닝 주기, 스키마 복구 재시도를 여기 한 곳으로 모았다. 테이블 이름과 SQL, 그리고
페이로드 직렬화는 호출하는 모듈에 남는다.

일부 값을 호출 시점에 인자로 받는 이유가 있다. 호출하는 모듈의 회귀 테스트가 그 모듈의
전역을 monkeypatch 하므로, 골격이 자기 이름공간에서 조회하면 그 패치가 닿지 않는다.
메모리 상한, 프루닝 주기, sqlite_utils 함수 넷이 여기 해당한다. 반대로 준비 기록과 추적
키의 상한은 검사가 건드리지 않으므로 생성자에서 한 번만 받는다.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Any, Callable

from services.sqlite_utils import add_bounded_ready_key, normalize_sqlite_db_key


class SchemaRecoveryRetryError(Exception):
    """스키마를 복구한 뒤 다시 시도했는데도 실패했다.

    메시지 앞에 복구를 거쳤다는 표시를 달아 올린다. 호출자는 예외를 한 갈래로 잡아
    로그에 남기기만 하면 「복구 전 실패」와 「복구 후 실패」가 그대로 구분된다.
    원인이 되는 예외는 `__cause__` 에 붙는다.

    이 예외가 sqlite3.OperationalError 같은 원래 타입을 가린다. 호출부를
    `except sqlite3.OperationalError` 로 좁히면 복구 후 실패만 빠져나가므로,
    잡을 때는 `except Exception` 으로 두어야 한다.
    """


class SqliteReadyGate:
    """DB 파일 하나의 스키마 준비를 단일 비행으로 보장한다.

    여러 스레드가 동시에 들어와도 초기화는 한 번만 돈다. 나머지는 조건 변수에서
    기다렸다가 결과를 물려받는다. 초기화가 실패하면 기다리던 쪽이 다시 시도한다.

    같은 DB 파일이라도 테이블이 다르면 게이트를 따로 두어야 한다. 한 테이블이
    준비되었다는 이유로 다른 테이블도 준비된 것으로 판정하면 안 되기 때문이다.
    """

    def __init__(self, *, max_ready_entries: int = 2_048) -> None:
        # 재진입 불가한 Lock 을 쓴다. RLock 이면 락을 쥔 채로 ensure() 를 부르는
        # 코드가 조용히 통과하면서 초기화 내내 다른 스레드를 막는다. Lock 이면
        # 그 자리에서 교착으로 드러난다.
        self.lock = threading.Lock()
        self.condition = threading.Condition(self.lock)
        self.ready_keys: set[str] = set()
        self.in_progress_keys: set[str] = set()
        self._max_ready_entries = max_ready_entries

    def invalidate(self, db_path_text: str) -> None:
        db_key = normalize_sqlite_db_key(db_path_text)
        with self.condition:
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
        force_recheck: bool = False,
        max_ready_entries: int | None = None,
    ) -> bool:
        db_key = normalize_sqlite_db_key(db_path_text)
        with self.condition:
            if force_recheck:
                self.ready_keys.discard(db_key)
            elif db_key in self.ready_keys:
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
                        max_entries=(self._max_ready_entries if max_ready_entries is None else max_ready_entries),
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
    key: Any,
    value: Any,
    *,
    max_entries: int,
) -> None:
    """가장 오래 쓰지 않은 항목부터 밀어내며 상한을 지킨다.

    락은 잡지 않는다. 호출자가 이미 락을 쥔 채 캐시를 여러 번 만지는 자리가 있어서,
    여기서 잡으면 그 자리에서는 부를 수 없고 같은 로직이 인라인으로 남는다.
    services/kr_market_data_cache_core.py 의 _set_bounded_lru_cache_entry 도 같은
    이유로 락을 밖에 둔다.
    """
    cache[key] = value
    cache.move_to_end(key)
    normalized_max_entries = max(1, int(max_entries))
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
    재시도까지 실패하면 SchemaRecoveryRetryError 로 바꿔 올린다. 그 메시지가 복구를
    거쳤다는 사실을 담으므로 호출자는 예외를 한 갈래로만 잡으면 된다.
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
            raise SchemaRecoveryRetryError(
                f"schema recovery retry failed: {retry_error}"
            ) from retry_error
