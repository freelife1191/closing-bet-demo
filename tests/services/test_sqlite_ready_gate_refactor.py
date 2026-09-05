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
        # 다른 스레드가 대기 구간에 들어갈 시간을 준다.
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


def test_ready_gate_reports_initialization_failure_to_on_failure(tmp_path):
    gate = SqliteReadyGate(max_ready_entries=8)
    db_path_text = str(tmp_path / "cache.db")
    reported: list[str] = []

    def _initialize() -> None:
        raise RuntimeError("초기화가 실패한다")

    result = gate.ensure(
        db_path_text,
        initialize=_initialize,
        db_path_exists=lambda _path: True,
        run_with_retry=_run_immediately,
        retry_attempts=0,
        retry_delay_seconds=0.0,
        on_failure=lambda error: reported.append(str(error)),
    )

    # 실패를 알리지 않으면 스키마 초기화가 왜 안 됐는지 운영 로그에 아무것도 남지 않는다.
    # 원본에서는 이 자리가 logger.debug 직접 호출이었다.
    assert result is False
    assert reported == ["초기화가 실패한다"]
    assert gate.ready_keys == set()


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

    # 준비 완료로 기록된 상태에서는 다시 만들지 않는다.
    assert _ensure() is True
    assert call_count == 1

    # 파일이 사라졌으면 기록이 있어도 다시 만든다.
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

    for index, key in enumerate(("a", "b", "c")):
        save_bounded_lru_entry(cache, key, index, max_entries=2)

    assert list(cache.keys()) == ["b", "c"]


def test_save_bounded_lru_entry_keeps_recently_used_entry():
    cache: OrderedDict[str, int] = OrderedDict()

    save_bounded_lru_entry(cache, "a", 1, max_entries=2)
    save_bounded_lru_entry(cache, "b", 2, max_entries=2)
    # a 를 다시 쓰면 맨 뒤로 가므로 다음 밀려나는 것은 b 다.
    save_bounded_lru_entry(cache, "a", 3, max_entries=2)
    save_bounded_lru_entry(cache, "c", 4, max_entries=2)

    assert list(cache.keys()) == ["a", "c"]


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
        # 호출자는 예외를 한 갈래로 잡으므로 「복구 후 실패」라는 사실은 메시지가 진다.
        assert "schema recovery retry failed" in str(error)
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


# ── 두 모듈이 골격을 같은 방식으로 쓰는지 ────────────────────────────────────
#
# 위의 검사들은 골격 자체를 본다. 아래는 chatbot 의 두 캐시 모듈이 그 골격에 같은
# 인자를 넘기는지를 본다. 골격을 공유해도 한쪽만 인자를 잘못 넘기면 동작이 갈린다.

import sqlite3  # noqa: E402
import types  # noqa: E402

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
    return types.SimpleNamespace(debug=lambda *_args, **_kwargs: None)


def test_both_modules_keep_separate_ready_gates():
    # 두 모듈은 같은 runtime_cache.db 를 쓰지만 테이블이 다르다. 게이트를 공유하면
    # 한 테이블이 준비됐다는 이유로 다른 테이블도 준비된 것으로 잘못 판정한다.
    assert (
        runtime_stock_map_cache._STOCK_MAP_READY_GATE
        is not stock_context_cache._RESULT_TEXT_READY_GATE
    )
    # 모듈 전역이 게이트의 객체를 그대로 가리켜야 회귀 테스트의 clear() 가 닿는다.
    assert (
        runtime_stock_map_cache._STOCK_MAP_SQLITE_READY
        is runtime_stock_map_cache._STOCK_MAP_READY_GATE.ready_keys
    )
    assert (
        runtime_stock_map_cache._STOCK_MAP_SQLITE_INIT_IN_PROGRESS
        is runtime_stock_map_cache._STOCK_MAP_READY_GATE.in_progress_keys
    )
    assert (
        stock_context_cache._RESULT_TEXT_SQLITE_READY
        is stock_context_cache._RESULT_TEXT_READY_GATE.ready_keys
    )
    assert (
        stock_context_cache._RESULT_TEXT_SQLITE_INIT_IN_PROGRESS
        is stock_context_cache._RESULT_TEXT_READY_GATE.in_progress_keys
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

    # 두 모듈이 실제로 쓰는 경로를 각각 구한다. db 경로 계산이 서로 다르기 때문이다.
    map_db_path = runtime_stock_map_cache._stock_map_cache_db_path(data_dir)
    context_db_path = stock_context_cache._resolve_runtime_cache_db_path(data_dir)

    conn = sqlite3.connect(str(map_db_path))
    try:
        conn.execute("DROP TABLE chatbot_stock_map_cache")
        conn.commit()
    finally:
        conn.close()

    conn = sqlite3.connect(str(context_db_path))
    try:
        conn.execute("DROP TABLE chatbot_stock_context_cache")
        conn.commit()
    finally:
        conn.close()

    _reset_both_caches()

    # 테이블이 없으므로 조회 결과는 None 이지만, 그 과정에서 스키마가 되살아나야 한다.
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

    def _table_names(db_path) -> set[str]:
        conn = sqlite3.connect(str(db_path))
        try:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        finally:
            conn.close()
        return {row[0] for row in rows}

    assert "chatbot_stock_map_cache" in _table_names(map_db_path)
    assert "chatbot_stock_context_cache" in _table_names(context_db_path)


def test_both_modules_prune_on_the_same_schedule(monkeypatch, tmp_path):
    _reset_both_caches()
    data_dir = tmp_path
    source_path = tmp_path / "stocks.csv"
    source_path.write_text("name,ticker\n", encoding="utf-8")
    logger = _logger_stub()

    # 같은 주기를 주면 같은 저장 횟수에서 프루닝이 돌아야 한다.
    monkeypatch.setattr(runtime_stock_map_cache, "_STOCK_MAP_SQLITE_PRUNE_FORCE_INTERVAL", 3)
    monkeypatch.setattr(stock_context_cache, "_RESULT_TEXT_SQLITE_PRUNE_FORCE_INTERVAL", 3)

    # 프루닝이 몇 번 돌았는지가 아니라 「몇 번째 저장에서」 돌았는지를 본다. 횟수만
    # 세면 mark_seen 과 should_force_prune 을 or 로 묶어 단축 평가에 맡기는 퇴행을
    # 잡지 못한다. 주기 3, 저장 5회에서는 옳은 구현이 [1, 3] 을, 퇴행한 구현이
    # [1, 4] 를 내는데 개수는 둘 다 2 이기 때문이다.
    save_round = {"value": 0}
    stock_map_prune_rounds: list[int] = []
    result_text_prune_rounds: list[int] = []

    def _make_tracer(bucket):
        def _traced(cursor, *, table_name, max_rows):
            bucket.append(save_round["value"])

        return _traced

    monkeypatch.setattr(
        runtime_stock_map_cache,
        "prune_rows_by_updated_at_if_needed",
        _make_tracer(stock_map_prune_rounds),
    )
    monkeypatch.setattr(
        stock_context_cache,
        "prune_rows_by_updated_at_if_needed",
        _make_tracer(result_text_prune_rounds),
    )

    # 같은 키로 다섯 번 저장한다. 첫 저장은 신규 키라 프루닝하고, 그다음은 저장 횟수가
    # 주기를 채우는 세 번째에서 프루닝한다. 두 모듈이 같은 자리에서 돌아야 한다.
    for index in range(5):
        save_round["value"] = index + 1
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

    assert stock_map_prune_rounds == [1, 3]
    assert result_text_prune_rounds == [1, 3]
