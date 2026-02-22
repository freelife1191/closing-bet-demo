#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
runtime_stock_map_cache 리팩토링 회귀 테스트
"""

from __future__ import annotations

import os
import sqlite3
import sys
import threading
import time
import types
from pathlib import Path


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import chatbot.runtime_stock_map_cache as runtime_stock_map_cache


def _logger_stub():
    return types.SimpleNamespace(debug=lambda *_args, **_kwargs: None)


def _reset_cache_state() -> None:
    runtime_stock_map_cache.clear_stock_map_cache()
    with runtime_stock_map_cache._STOCK_MAP_SQLITE_READY_CONDITION:
        runtime_stock_map_cache._STOCK_MAP_SQLITE_READY.clear()
        runtime_stock_map_cache._STOCK_MAP_SQLITE_INIT_IN_PROGRESS.clear()


def test_save_stock_map_cache_evicts_oldest_memory_entry(monkeypatch, tmp_path: Path):
    _reset_cache_state()
    monkeypatch.setattr(runtime_stock_map_cache, "_STOCK_MAP_MEMORY_MAX_ENTRIES", 2)
    logger = _logger_stub()

    source_paths = [
        tmp_path / "stocks_1.csv",
        tmp_path / "stocks_2.csv",
        tmp_path / "stocks_3.csv",
    ]
    signatures = [(1, 10), (2, 20), (3, 30)]

    for index, source_path in enumerate(source_paths):
        runtime_stock_map_cache.save_stock_map_cache(
            data_dir=tmp_path,
            source_path=source_path,
            signature=signatures[index],
            stock_map={f"종목{index + 1}": f"{index + 1:06d}"},
            ticker_map={f"{index + 1:06d}": f"종목{index + 1}"},
            logger=logger,
        )

    cache_keys = list(runtime_stock_map_cache._STOCK_MAP_CACHE.keys())
    assert len(cache_keys) == 2
    assert str(source_paths[0].resolve()) not in cache_keys
    assert str(source_paths[1].resolve()) in cache_keys
    assert str(source_paths[2].resolve()) in cache_keys


def test_save_stock_map_cache_keeps_recently_used_entry_on_eviction(monkeypatch, tmp_path: Path):
    _reset_cache_state()
    monkeypatch.setattr(runtime_stock_map_cache, "_STOCK_MAP_MEMORY_MAX_ENTRIES", 2)
    logger = _logger_stub()

    first_path = tmp_path / "stocks_first.csv"
    second_path = tmp_path / "stocks_second.csv"
    third_path = tmp_path / "stocks_third.csv"

    runtime_stock_map_cache.save_stock_map_cache(
        data_dir=tmp_path,
        source_path=first_path,
        signature=(1, 10),
        stock_map={"종목1": "000001"},
        ticker_map={"000001": "종목1"},
        logger=logger,
    )
    runtime_stock_map_cache.save_stock_map_cache(
        data_dir=tmp_path,
        source_path=second_path,
        signature=(2, 20),
        stock_map={"종목2": "000002"},
        ticker_map={"000002": "종목2"},
        logger=logger,
    )

    loaded = runtime_stock_map_cache.load_stock_map_cache(
        data_dir=tmp_path,
        source_path=first_path,
        signature=(1, 10),
        logger=logger,
    )
    assert loaded is not None

    runtime_stock_map_cache.save_stock_map_cache(
        data_dir=tmp_path,
        source_path=third_path,
        signature=(3, 30),
        stock_map={"종목3": "000003"},
        ticker_map={"000003": "종목3"},
        logger=logger,
    )

    cache_keys = list(runtime_stock_map_cache._STOCK_MAP_CACHE.keys())
    assert len(cache_keys) == 2
    assert str(first_path.resolve()) in cache_keys
    assert str(second_path.resolve()) not in cache_keys
    assert str(third_path.resolve()) in cache_keys


def test_save_stock_map_cache_non_positive_memory_limit_keeps_latest_only(monkeypatch, tmp_path: Path):
    _reset_cache_state()
    monkeypatch.setattr(runtime_stock_map_cache, "_STOCK_MAP_MEMORY_MAX_ENTRIES", 0)
    logger = _logger_stub()

    first_path = tmp_path / "stocks_first.csv"
    second_path = tmp_path / "stocks_second.csv"

    runtime_stock_map_cache.save_stock_map_cache(
        data_dir=tmp_path,
        source_path=first_path,
        signature=(10, 100),
        stock_map={"삼성전자": "005930"},
        ticker_map={"005930": "삼성전자"},
        logger=logger,
    )
    runtime_stock_map_cache.save_stock_map_cache(
        data_dir=tmp_path,
        source_path=second_path,
        signature=(20, 200),
        stock_map={"하이닉스": "000660"},
        ticker_map={"000660": "하이닉스"},
        logger=logger,
    )

    cache_keys = list(runtime_stock_map_cache._STOCK_MAP_CACHE.keys())
    assert len(cache_keys) == 1
    assert cache_keys[0] == str(second_path.resolve())


def test_stock_map_cache_recovers_when_sqlite_table_missing(tmp_path: Path):
    _reset_cache_state()
    logger = _logger_stub()

    first_path = tmp_path / "stocks_first.csv"
    second_path = tmp_path / "stocks_second.csv"

    runtime_stock_map_cache.save_stock_map_cache(
        data_dir=tmp_path,
        source_path=first_path,
        signature=(1, 10),
        stock_map={"삼성전자": "005930"},
        ticker_map={"005930": "삼성전자"},
        logger=logger,
    )

    db_path = tmp_path / "runtime_cache.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("DROP TABLE chatbot_stock_map_cache")
        conn.commit()

    runtime_stock_map_cache.save_stock_map_cache(
        data_dir=tmp_path,
        source_path=second_path,
        signature=(2, 20),
        stock_map={"하이닉스": "000660"},
        ticker_map={"000660": "하이닉스"},
        logger=logger,
    )
    runtime_stock_map_cache.clear_stock_map_cache()

    loaded = runtime_stock_map_cache.load_stock_map_cache(
        data_dir=tmp_path,
        source_path=second_path,
        signature=(2, 20),
        logger=logger,
    )
    assert loaded is not None
    stock_map, ticker_map = loaded
    assert stock_map["하이닉스"] == "000660"
    assert ticker_map["000660"] == "하이닉스"

    with sqlite3.connect(db_path) as conn:
        row_count = int(conn.execute("SELECT COUNT(*) FROM chatbot_stock_map_cache").fetchone()[0])
    assert row_count >= 1


def test_save_stock_map_cache_skips_delete_when_rows_within_limit(monkeypatch, tmp_path: Path):
    _reset_cache_state()
    logger = _logger_stub()
    monkeypatch.setattr(runtime_stock_map_cache, "_STOCK_MAP_SQLITE_MAX_ROWS", 16)

    traced_sql: list[str] = []
    original_connect = runtime_stock_map_cache.connect_sqlite

    def _traced_connect(*args, **kwargs):
        conn = original_connect(*args, **kwargs)
        conn.set_trace_callback(traced_sql.append)
        return conn

    monkeypatch.setattr(runtime_stock_map_cache, "connect_sqlite", _traced_connect)

    source_path = tmp_path / "stocks_single.csv"
    runtime_stock_map_cache.save_stock_map_cache(
        data_dir=tmp_path,
        source_path=source_path,
        signature=(10, 20),
        stock_map={"삼성전자": "005930"},
        ticker_map={"005930": "삼성전자"},
        logger=logger,
    )

    assert not any("DELETE FROM chatbot_stock_map_cache" in sql for sql in traced_sql)


def test_save_stock_map_cache_runs_prune_once_for_repeated_same_path(monkeypatch, tmp_path: Path):
    _reset_cache_state()
    logger = _logger_stub()

    prune_calls = {"count": 0}
    original_prune = runtime_stock_map_cache.prune_rows_by_updated_at_if_needed

    def _traced_prune(*args, **kwargs):
        prune_calls["count"] += 1
        return original_prune(*args, **kwargs)

    monkeypatch.setattr(runtime_stock_map_cache, "prune_rows_by_updated_at_if_needed", _traced_prune)

    source_path = tmp_path / "stocks_repeat.csv"
    runtime_stock_map_cache.save_stock_map_cache(
        data_dir=tmp_path,
        source_path=source_path,
        signature=(10, 20),
        stock_map={"삼성전자": "005930"},
        ticker_map={"005930": "삼성전자"},
        logger=logger,
    )
    runtime_stock_map_cache.save_stock_map_cache(
        data_dir=tmp_path,
        source_path=source_path,
        signature=(11, 21),
        stock_map={"삼성전자": "005930"},
        ticker_map={"005930": "삼성전자"},
        logger=logger,
    )

    assert prune_calls["count"] == 1


def test_save_stock_map_cache_forces_periodic_prune_for_same_path(monkeypatch, tmp_path: Path):
    _reset_cache_state()
    logger = _logger_stub()
    monkeypatch.setattr(runtime_stock_map_cache, "_STOCK_MAP_SQLITE_PRUNE_FORCE_INTERVAL", 2)

    prune_calls = {"count": 0}
    original_prune = runtime_stock_map_cache.prune_rows_by_updated_at_if_needed

    def _traced_prune(*args, **kwargs):
        prune_calls["count"] += 1
        return original_prune(*args, **kwargs)

    monkeypatch.setattr(runtime_stock_map_cache, "prune_rows_by_updated_at_if_needed", _traced_prune)

    source_path = tmp_path / "stocks_force.csv"
    runtime_stock_map_cache.save_stock_map_cache(
        data_dir=tmp_path,
        source_path=source_path,
        signature=(20, 30),
        stock_map={"하이닉스": "000660"},
        ticker_map={"000660": "하이닉스"},
        logger=logger,
    )
    runtime_stock_map_cache.save_stock_map_cache(
        data_dir=tmp_path,
        source_path=source_path,
        signature=(21, 31),
        stock_map={"하이닉스": "000660"},
        ticker_map={"000660": "하이닉스"},
        logger=logger,
    )

    assert prune_calls["count"] == 2


def test_load_stock_map_cache_retries_on_transient_sqlite_lock(monkeypatch, tmp_path: Path):
    _reset_cache_state()
    logger = _logger_stub()
    source_path = tmp_path / "stocks_retry.csv"
    signature = (10, 20)

    runtime_stock_map_cache.save_stock_map_cache(
        data_dir=tmp_path,
        source_path=source_path,
        signature=signature,
        stock_map={"삼성전자": "005930"},
        ticker_map={"005930": "삼성전자"},
        logger=logger,
    )
    runtime_stock_map_cache.clear_stock_map_cache()

    original_connect = runtime_stock_map_cache.connect_sqlite
    failure_state = {"failed": False}

    def _flaky_connect(*args, **kwargs):
        if not failure_state["failed"]:
            failure_state["failed"] = True
            raise sqlite3.OperationalError("database is locked")
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(runtime_stock_map_cache, "connect_sqlite", _flaky_connect)
    loaded = runtime_stock_map_cache.load_stock_map_cache(
        data_dir=tmp_path,
        source_path=source_path,
        signature=signature,
        logger=logger,
    )

    assert failure_state["failed"] is True
    assert loaded is not None
    stock_map, ticker_map = loaded
    assert stock_map["삼성전자"] == "005930"
    assert ticker_map["005930"] == "삼성전자"


def test_load_stock_map_cache_uses_read_only_connection(monkeypatch, tmp_path: Path):
    _reset_cache_state()
    logger = _logger_stub()
    source_path = tmp_path / "stocks_read_only.csv"
    signature = (10, 20)

    runtime_stock_map_cache.save_stock_map_cache(
        data_dir=tmp_path,
        source_path=source_path,
        signature=signature,
        stock_map={"삼성전자": "005930"},
        ticker_map={"005930": "삼성전자"},
        logger=logger,
    )
    runtime_stock_map_cache.clear_stock_map_cache()

    read_only_flags: list[bool] = []
    original_connect = runtime_stock_map_cache.connect_sqlite

    def _traced_connect(*args, **kwargs):
        if "read_only" in kwargs:
            read_only_flags.append(bool(kwargs["read_only"]))
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(runtime_stock_map_cache, "connect_sqlite", _traced_connect)

    loaded = runtime_stock_map_cache.load_stock_map_cache(
        data_dir=tmp_path,
        source_path=source_path,
        signature=signature,
        logger=logger,
    )

    assert loaded is not None
    stock_map, ticker_map = loaded
    assert stock_map["삼성전자"] == "005930"
    assert ticker_map["005930"] == "삼성전자"
    assert True in read_only_flags


def test_load_stock_map_cache_reuses_alias_memory_path_without_sqlite_query(
    monkeypatch, tmp_path: Path
):
    _reset_cache_state()
    logger = _logger_stub()
    monkeypatch.chdir(tmp_path)

    relative_source_path = Path("stocks_alias.csv")
    absolute_source_path = (tmp_path / "stocks_alias.csv").resolve()
    signature = (10, 20)

    runtime_stock_map_cache.save_stock_map_cache(
        data_dir=tmp_path,
        source_path=relative_source_path,
        signature=signature,
        stock_map={"삼성전자": "005930"},
        ticker_map={"005930": "삼성전자"},
        logger=logger,
    )

    monkeypatch.setattr(
        runtime_stock_map_cache,
        "connect_sqlite",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("should reuse alias memory cache key")
        ),
    )

    loaded = runtime_stock_map_cache.load_stock_map_cache(
        data_dir=tmp_path,
        source_path=absolute_source_path,
        signature=signature,
        logger=logger,
    )

    assert loaded is not None
    stock_map, ticker_map = loaded
    assert stock_map["삼성전자"] == "005930"
    assert ticker_map["005930"] == "삼성전자"


def test_load_stock_map_cache_reads_legacy_sqlite_source_path_key(
    monkeypatch, tmp_path: Path
):
    _reset_cache_state()
    logger = _logger_stub()
    monkeypatch.chdir(tmp_path)

    relative_source_path = Path("stocks_legacy.csv")
    absolute_source_path = (tmp_path / "stocks_legacy.csv").resolve()
    signature = (30, 40)

    runtime_stock_map_cache.save_stock_map_cache(
        data_dir=tmp_path,
        source_path=relative_source_path,
        signature=signature,
        stock_map={"하이닉스": "000660"},
        ticker_map={"000660": "하이닉스"},
        logger=logger,
    )

    db_path = tmp_path / "runtime_cache.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE chatbot_stock_map_cache
            SET source_path = ?
            WHERE source_path = ?
            """,
            ("stocks_legacy.csv", str(absolute_source_path)),
        )
        conn.commit()

    runtime_stock_map_cache.clear_stock_map_cache()
    loaded = runtime_stock_map_cache.load_stock_map_cache(
        data_dir=tmp_path,
        source_path=absolute_source_path,
        signature=signature,
        logger=logger,
    )

    assert loaded is not None
    stock_map, ticker_map = loaded
    assert stock_map["하이닉스"] == "000660"
    assert ticker_map["000660"] == "하이닉스"


def test_ensure_stock_map_sqlite_retries_on_transient_lock(monkeypatch, tmp_path: Path):
    _reset_cache_state()
    logger = _logger_stub()
    db_path = tmp_path / "runtime_cache.db"

    original_connect = runtime_stock_map_cache.connect_sqlite
    failure_state = {"count": 0}

    def _flaky_connect(*args, **kwargs):
        if failure_state["count"] == 0:
            failure_state["count"] += 1
            raise sqlite3.OperationalError("database is locked")
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(runtime_stock_map_cache, "connect_sqlite", _flaky_connect)

    assert runtime_stock_map_cache._ensure_stock_map_sqlite(db_path, logger) is True
    assert failure_state["count"] == 1


def test_ensure_stock_map_sqlite_single_flight_under_concurrency(monkeypatch, tmp_path: Path):
    _reset_cache_state()
    logger = _logger_stub()
    db_path = tmp_path / "runtime_cache.db"

    monkeypatch.setattr(runtime_stock_map_cache, "sqlite_db_path_exists", lambda _path: True)

    entered_event = threading.Event()
    release_event = threading.Event()
    run_calls = {"count": 0}

    def _run_once(_operation, *, max_retries, retry_delay_seconds):
        run_calls["count"] += 1
        if run_calls["count"] == 1:
            entered_event.set()
            assert release_event.wait(timeout=2.0)
        return None

    monkeypatch.setattr(runtime_stock_map_cache, "run_sqlite_with_retry", _run_once)

    results: dict[str, bool] = {}

    def _worker(name: str) -> None:
        results[name] = bool(runtime_stock_map_cache._ensure_stock_map_sqlite(db_path, logger))

    first_thread = threading.Thread(target=_worker, args=("first",))
    second_thread = threading.Thread(target=_worker, args=("second",))

    first_thread.start()
    assert entered_event.wait(timeout=2.0)
    second_thread.start()
    time.sleep(0.05)
    assert run_calls["count"] == 1

    release_event.set()
    first_thread.join(timeout=2.0)
    second_thread.join(timeout=2.0)

    assert first_thread.is_alive() is False
    assert second_thread.is_alive() is False
    assert run_calls["count"] == 1
    assert results == {"first": True, "second": True}


def test_ensure_stock_map_sqlite_waiter_retries_after_initializer_failure(monkeypatch, tmp_path: Path):
    _reset_cache_state()
    logger = _logger_stub()
    db_path = tmp_path / "runtime_cache.db"

    monkeypatch.setattr(runtime_stock_map_cache, "sqlite_db_path_exists", lambda _path: True)

    entered_event = threading.Event()
    release_event = threading.Event()
    run_calls = {"count": 0}

    def _fail_then_succeed(_operation, *, max_retries, retry_delay_seconds):
        run_calls["count"] += 1
        if run_calls["count"] == 1:
            entered_event.set()
            assert release_event.wait(timeout=2.0)
            raise sqlite3.OperationalError("forced init failure")
        return None

    monkeypatch.setattr(runtime_stock_map_cache, "run_sqlite_with_retry", _fail_then_succeed)

    results: dict[str, bool] = {}

    def _worker(name: str) -> None:
        results[name] = bool(runtime_stock_map_cache._ensure_stock_map_sqlite(db_path, logger))

    first_thread = threading.Thread(target=_worker, args=("first",))
    second_thread = threading.Thread(target=_worker, args=("second",))

    first_thread.start()
    assert entered_event.wait(timeout=2.0)
    second_thread.start()
    time.sleep(0.05)
    assert run_calls["count"] == 1

    release_event.set()
    first_thread.join(timeout=2.0)
    second_thread.join(timeout=2.0)

    assert first_thread.is_alive() is False
    assert second_thread.is_alive() is False
    assert run_calls["count"] == 2
    assert results.get("first") is False
    assert results.get("second") is True
