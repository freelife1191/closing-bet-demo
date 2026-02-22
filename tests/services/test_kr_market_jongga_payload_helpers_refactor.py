#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Jongga Payload Helpers 리팩토링 회귀 테스트
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time
import types

import services.kr_market_jongga_payload_helpers as payload_helpers
from services.sqlite_utils import connect_sqlite


def _logger_stub():
    return types.SimpleNamespace(
        info=lambda *_args, **_kwargs: None,
        warning=lambda *_args, **_kwargs: None,
    )


def _reset_recent_jongga_state() -> None:
    payload_helpers._RECENT_JONGGA_PAYLOAD_CACHE.clear()
    with payload_helpers._RECENT_JONGGA_SQLITE_READY_CONDITION:
        payload_helpers._RECENT_JONGGA_SQLITE_READY.clear()
        payload_helpers._RECENT_JONGGA_SQLITE_INIT_IN_PROGRESS.clear()
    with payload_helpers._RECENT_JONGGA_SQLITE_KNOWN_KEYS_LOCK:
        payload_helpers._RECENT_JONGGA_SQLITE_KNOWN_KEYS.clear()
    with payload_helpers._RECENT_JONGGA_SQLITE_SAVE_COUNTER_LOCK:
        payload_helpers._RECENT_JONGGA_SQLITE_SAVE_COUNTER = 0


def test_find_recent_valid_jongga_payload_reuses_cache_when_files_unchanged(monkeypatch, tmp_path):
    payload_helpers._RECENT_JONGGA_PAYLOAD_CACHE.clear()
    payload_helpers._RECENT_JONGGA_SQLITE_READY.clear()
    result_path = tmp_path / "jongga_v2_results_20260220.json"
    result_path.write_text("{}", encoding="utf-8")
    calls = {"count": 0}

    original_loader = payload_helpers.load_json_from_path

    def _counted_loader(file_path, logger):
        calls["count"] += 1
        return original_loader(file_path, logger)

    monkeypatch.setattr(payload_helpers, "load_json_from_path", _counted_loader)

    # 파일 내용을 dict로 강제 주입해 유효 payload를 만들기 위해 loader만 대체
    monkeypatch.setattr(
        payload_helpers,
        "load_json_from_path",
        lambda file_path, logger: (
            calls.__setitem__("count", calls["count"] + 1)
            or {"date": "2026-02-20", "signals": [{"ticker": "000001"}]}
        ),
    )

    first = payload_helpers.find_recent_valid_jongga_payload(
        data_dir=str(tmp_path),
        recalculate_jongga_grades=lambda _payload: False,
        logger=_logger_stub(),
    )
    second = payload_helpers.find_recent_valid_jongga_payload(
        data_dir=str(tmp_path),
        recalculate_jongga_grades=lambda _payload: False,
        logger=_logger_stub(),
    )

    assert first is not None and second is not None
    assert calls["count"] == 1


def test_find_recent_valid_jongga_payload_invalidates_cache_when_file_changes(monkeypatch, tmp_path):
    payload_helpers._RECENT_JONGGA_PAYLOAD_CACHE.clear()
    payload_helpers._RECENT_JONGGA_SQLITE_READY.clear()
    result_path = tmp_path / "jongga_v2_results_20260220.json"
    result_path.write_text("{}", encoding="utf-8")
    calls = {"count": 0}

    monkeypatch.setattr(
        payload_helpers,
        "load_json_from_path",
        lambda file_path, logger: (
            calls.__setitem__("count", calls["count"] + 1)
            or {"date": "2026-02-20", "signals": [{"ticker": "000001"}]}
        ),
    )

    _ = payload_helpers.find_recent_valid_jongga_payload(
        data_dir=str(tmp_path),
        recalculate_jongga_grades=lambda _payload: False,
        logger=_logger_stub(),
    )
    assert calls["count"] == 1

    updated_mtime = result_path.stat().st_mtime + 2
    os.utime(result_path, (updated_mtime, updated_mtime))

    _ = payload_helpers.find_recent_valid_jongga_payload(
        data_dir=str(tmp_path),
        recalculate_jongga_grades=lambda _payload: False,
        logger=_logger_stub(),
    )
    assert calls["count"] == 2


def test_find_recent_valid_jongga_payload_returns_cloned_payload(monkeypatch, tmp_path):
    payload_helpers._RECENT_JONGGA_PAYLOAD_CACHE.clear()
    payload_helpers._RECENT_JONGGA_SQLITE_READY.clear()
    (tmp_path / "jongga_v2_results_20260220.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        payload_helpers,
        "load_json_from_path",
        lambda file_path, logger: {
            "date": "2026-02-20",
            "signals": [{"ticker": "000001", "grade": "A"}],
        },
    )

    first = payload_helpers.find_recent_valid_jongga_payload(
        data_dir=str(tmp_path),
        recalculate_jongga_grades=lambda _payload: False,
        logger=_logger_stub(),
    )
    assert first is not None
    first["signals"][0]["grade"] = "Z"

    second = payload_helpers.find_recent_valid_jongga_payload(
        data_dir=str(tmp_path),
        recalculate_jongga_grades=lambda _payload: False,
        logger=_logger_stub(),
    )
    assert second is not None
    assert second["signals"][0]["grade"] == "A"


def test_find_recent_valid_jongga_payload_memory_cache_is_bounded_lru(monkeypatch, tmp_path):
    payload_helpers._RECENT_JONGGA_PAYLOAD_CACHE.clear()
    payload_helpers._RECENT_JONGGA_SQLITE_READY.clear()
    monkeypatch.setattr(payload_helpers, "_RECENT_JONGGA_PAYLOAD_CACHE_MAX_ENTRIES", 2)

    data_dirs = [tmp_path / f"dataset_{idx}" for idx in range(3)]
    for data_dir in data_dirs:
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "jongga_v2_results_20260220.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        payload_helpers,
        "load_json_from_path",
        lambda file_path, logger: {
            "date": "2026-02-20",
            "signals": [{"ticker": os.path.basename(os.path.dirname(file_path))}],
        },
    )

    payload_helpers.find_recent_valid_jongga_payload(
        data_dir=str(data_dirs[0]),
        recalculate_jongga_grades=lambda _payload: False,
        logger=_logger_stub(),
    )
    payload_helpers.find_recent_valid_jongga_payload(
        data_dir=str(data_dirs[1]),
        recalculate_jongga_grades=lambda _payload: False,
        logger=_logger_stub(),
    )
    payload_helpers.find_recent_valid_jongga_payload(
        data_dir=str(data_dirs[0]),
        recalculate_jongga_grades=lambda _payload: False,
        logger=_logger_stub(),
    )
    payload_helpers.find_recent_valid_jongga_payload(
        data_dir=str(data_dirs[2]),
        recalculate_jongga_grades=lambda _payload: False,
        logger=_logger_stub(),
    )

    with payload_helpers._RECENT_JONGGA_PAYLOAD_CACHE_LOCK:
        cached_keys = list(payload_helpers._RECENT_JONGGA_PAYLOAD_CACHE.keys())

    assert len(cached_keys) == 2
    assert os.path.abspath(str(data_dirs[0])) in cached_keys
    assert os.path.abspath(str(data_dirs[2])) in cached_keys
    assert os.path.abspath(str(data_dirs[1])) not in cached_keys


def test_find_recent_valid_jongga_payload_uses_sqlite_cache_after_memory_clear(monkeypatch, tmp_path):
    payload_helpers._RECENT_JONGGA_PAYLOAD_CACHE.clear()
    payload_helpers._RECENT_JONGGA_SQLITE_READY.clear()
    (tmp_path / "jongga_v2_results_20260220.json").write_text("{}", encoding="utf-8")

    first = payload_helpers.find_recent_valid_jongga_payload(
        data_dir=str(tmp_path),
        recalculate_jongga_grades=lambda _payload: False,
        logger=_logger_stub(),
    )
    assert first is None

    monkeypatch.setattr(
        payload_helpers,
        "load_json_from_path",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("loader should not run")),
    )
    payload_helpers._RECENT_JONGGA_PAYLOAD_CACHE.clear()

    # 유효 payload를 sqlite 캐시에 넣기 위해 한 번 실제 payload 생성
    monkeypatch.setattr(
        payload_helpers,
        "load_json_from_path",
        lambda file_path, logger: {
            "date": "2026-02-20",
            "signals": [{"ticker": "000001"}],
        },
    )
    _ = payload_helpers.find_recent_valid_jongga_payload(
        data_dir=str(tmp_path),
        recalculate_jongga_grades=lambda _payload: False,
        logger=_logger_stub(),
    )

    payload_helpers._RECENT_JONGGA_PAYLOAD_CACHE.clear()
    monkeypatch.setattr(
        payload_helpers,
        "load_json_from_path",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("loader should not run")),
    )
    second = payload_helpers.find_recent_valid_jongga_payload(
        data_dir=str(tmp_path),
        recalculate_jongga_grades=lambda _payload: False,
        logger=_logger_stub(),
    )

    assert second is not None
    assert second["signals"][0]["ticker"] == "000001"


def test_find_recent_valid_jongga_payload_reuses_alias_memory_cache_without_sqlite_query(monkeypatch, tmp_path):
    _reset_recent_jongga_state()
    monkeypatch.chdir(tmp_path)
    (tmp_path / "jongga_v2_results_20260220.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        payload_helpers,
        "load_json_from_path",
        lambda *_args, **_kwargs: {
            "date": "2026-02-20",
            "signals": [{"ticker": "000001"}],
        },
    )
    first = payload_helpers.find_recent_valid_jongga_payload(
        data_dir=".",
        recalculate_jongga_grades=lambda _payload: False,
        logger=_logger_stub(),
    )
    assert first is not None

    monkeypatch.setattr(
        payload_helpers,
        "connect_sqlite",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("should reuse jongga alias memory cache")
        ),
    )
    monkeypatch.setattr(
        payload_helpers,
        "load_json_from_path",
        lambda *_a, **_k: (_ for _ in ()).throw(
            AssertionError("loader should not run when alias memory cache is warm")
        ),
    )
    second = payload_helpers.find_recent_valid_jongga_payload(
        data_dir=str(tmp_path),
        recalculate_jongga_grades=lambda _payload: False,
        logger=_logger_stub(),
    )
    assert second is not None
    assert second["signals"][0]["ticker"] == "000001"


def test_find_recent_valid_jongga_payload_reads_legacy_sqlite_cache_key(monkeypatch, tmp_path):
    _reset_recent_jongga_state()
    monkeypatch.chdir(tmp_path)
    (tmp_path / "jongga_v2_results_20260220.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        payload_helpers,
        "load_json_from_path",
        lambda *_args, **_kwargs: {
            "date": "2026-02-20",
            "signals": [{"ticker": "000001"}],
        },
    )
    first = payload_helpers.find_recent_valid_jongga_payload(
        data_dir=".",
        recalculate_jongga_grades=lambda _payload: False,
        logger=_logger_stub(),
    )
    assert first is not None

    db_path = tmp_path / "runtime_cache.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE jongga_recent_valid_payload_cache
            SET cache_key = ?
            WHERE cache_key = ?
            """,
            (".", payload_helpers._normalize_recent_payload_cache_key(str(tmp_path))),
        )
        conn.commit()

    payload_helpers._RECENT_JONGGA_PAYLOAD_CACHE.clear()
    monkeypatch.setattr(
        payload_helpers,
        "load_json_from_path",
        lambda *_a, **_k: (_ for _ in ()).throw(
            AssertionError("should load jongga payload from legacy sqlite cache key")
        ),
    )
    second = payload_helpers.find_recent_valid_jongga_payload(
        data_dir=str(tmp_path),
        recalculate_jongga_grades=lambda _payload: False,
        logger=_logger_stub(),
    )
    assert second is not None
    assert second["signals"][0]["ticker"] == "000001"


def test_find_recent_valid_jongga_payload_legacy_lookup_runs_single_select_query(monkeypatch, tmp_path):
    _reset_recent_jongga_state()
    monkeypatch.chdir(tmp_path)
    (tmp_path / "jongga_v2_results_20260220.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        payload_helpers,
        "load_json_from_path",
        lambda *_args, **_kwargs: {
            "date": "2026-02-20",
            "signals": [{"ticker": "000001"}],
        },
    )
    first = payload_helpers.find_recent_valid_jongga_payload(
        data_dir=".",
        recalculate_jongga_grades=lambda _payload: False,
        logger=_logger_stub(),
    )
    assert first is not None

    db_path = tmp_path / "runtime_cache.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE jongga_recent_valid_payload_cache
            SET cache_key = ?
            WHERE cache_key = ?
            """,
            (".", payload_helpers._normalize_recent_payload_cache_key(str(tmp_path))),
        )
        conn.commit()

    payload_helpers._RECENT_JONGGA_PAYLOAD_CACHE.clear()
    monkeypatch.setattr(
        payload_helpers,
        "load_json_from_path",
        lambda *_a, **_k: (_ for _ in ()).throw(
            AssertionError("should load jongga payload from legacy sqlite cache key")
        ),
    )

    traced_sql: list[str] = []
    original_connect = payload_helpers.connect_sqlite

    def _traced_connect(*args, **kwargs):
        conn = original_connect(*args, **kwargs)
        conn.set_trace_callback(traced_sql.append)
        return conn

    monkeypatch.setattr(payload_helpers, "connect_sqlite", _traced_connect)

    second = payload_helpers.find_recent_valid_jongga_payload(
        data_dir=str(tmp_path),
        recalculate_jongga_grades=lambda _payload: False,
        logger=_logger_stub(),
    )

    select_count = sum(
        1
        for sql in traced_sql
        if "select payload_json" in sql.lower()
        and "from jongga_recent_valid_payload_cache" in sql.lower()
    )
    assert second is not None
    assert second["signals"][0]["ticker"] == "000001"
    assert select_count == 1


def test_find_recent_valid_jongga_payload_sqlite_load_uses_read_only_connection(monkeypatch, tmp_path):
    payload_helpers._RECENT_JONGGA_PAYLOAD_CACHE.clear()
    payload_helpers._RECENT_JONGGA_SQLITE_READY.clear()
    (tmp_path / "jongga_v2_results_20260220.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        payload_helpers,
        "load_json_from_path",
        lambda *_args, **_kwargs: {
            "date": "2026-02-20",
            "signals": [{"ticker": "000001"}],
        },
    )
    first = payload_helpers.find_recent_valid_jongga_payload(
        data_dir=str(tmp_path),
        recalculate_jongga_grades=lambda _payload: False,
        logger=_logger_stub(),
    )
    assert first is not None

    payload_helpers._RECENT_JONGGA_PAYLOAD_CACHE.clear()
    monkeypatch.setattr(
        payload_helpers,
        "load_json_from_path",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("loader should not run")),
    )

    read_only_flags: list[bool] = []
    original_connect = payload_helpers.connect_sqlite

    def _traced_connect(*args, **kwargs):
        if "read_only" in kwargs:
            read_only_flags.append(bool(kwargs["read_only"]))
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(payload_helpers, "connect_sqlite", _traced_connect)

    loaded = payload_helpers.find_recent_valid_jongga_payload(
        data_dir=str(tmp_path),
        recalculate_jongga_grades=lambda _payload: False,
        logger=_logger_stub(),
    )

    assert loaded is not None
    assert loaded["signals"][0]["ticker"] == "000001"
    assert True in read_only_flags


def test_find_recent_valid_jongga_payload_prunes_sqlite_rows(monkeypatch, tmp_path):
    payload_helpers._RECENT_JONGGA_PAYLOAD_CACHE.clear()
    payload_helpers._RECENT_JONGGA_SQLITE_READY.clear()
    monkeypatch.setattr(payload_helpers, "_RECENT_JONGGA_SQLITE_MAX_ROWS", 2)
    result_path = tmp_path / "jongga_v2_results_20260220.json"
    result_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        payload_helpers,
        "load_json_from_path",
        lambda file_path, logger: {
            "date": "2026-02-20",
            "signals": [{"ticker": "000001"}],
        },
    )

    for i in range(4):
        updated_mtime = result_path.stat().st_mtime + 2 + i
        os.utime(result_path, (updated_mtime, updated_mtime))
        _ = payload_helpers.find_recent_valid_jongga_payload(
            data_dir=str(tmp_path),
            recalculate_jongga_grades=lambda _payload: False,
            logger=_logger_stub(),
        )
        payload_helpers._RECENT_JONGGA_PAYLOAD_CACHE.clear()

    with connect_sqlite(str(tmp_path / "runtime_cache.db")) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM jongga_recent_valid_payload_cache")
        row_count = int(cursor.fetchone()[0])

    assert row_count == 2


def test_find_recent_valid_jongga_payload_creates_sqlite_parent_dir_when_missing(monkeypatch, tmp_path):
    payload_helpers._RECENT_JONGGA_PAYLOAD_CACHE.clear()
    payload_helpers._RECENT_JONGGA_SQLITE_READY.clear()

    (tmp_path / "jongga_v2_results_20260220.json").write_text("{}", encoding="utf-8")
    db_path = tmp_path / "cache" / "nested" / "runtime_cache.db"

    monkeypatch.setattr(payload_helpers, "_runtime_cache_db_path", lambda _data_dir: str(db_path))
    monkeypatch.setattr(
        payload_helpers,
        "load_json_from_path",
        lambda *_args, **_kwargs: {
            "date": "2026-02-20",
            "signals": [{"ticker": "000001"}],
        },
    )

    loaded = payload_helpers.find_recent_valid_jongga_payload(
        data_dir=str(tmp_path),
        recalculate_jongga_grades=lambda _payload: False,
        logger=_logger_stub(),
    )

    assert loaded is not None
    assert db_path.exists()

    with connect_sqlite(str(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM jongga_recent_valid_payload_cache")
        row_count = int(cursor.fetchone()[0])
    assert row_count >= 1


def test_find_recent_valid_jongga_payload_recovers_when_sqlite_table_missing(monkeypatch, tmp_path):
    payload_helpers._RECENT_JONGGA_PAYLOAD_CACHE.clear()
    payload_helpers._RECENT_JONGGA_SQLITE_READY.clear()

    (tmp_path / "jongga_v2_results_20260220.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        payload_helpers,
        "load_json_from_path",
        lambda *_args, **_kwargs: {
            "date": "2026-02-20",
            "signals": [{"ticker": "000001"}],
        },
    )

    first = payload_helpers.find_recent_valid_jongga_payload(
        data_dir=str(tmp_path),
        recalculate_jongga_grades=lambda _payload: False,
        logger=_logger_stub(),
    )
    assert first is not None

    db_path = tmp_path / "runtime_cache.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("DROP TABLE jongga_recent_valid_payload_cache")
        conn.commit()

    payload_helpers._RECENT_JONGGA_PAYLOAD_CACHE.clear()
    second = payload_helpers.find_recent_valid_jongga_payload(
        data_dir=str(tmp_path),
        recalculate_jongga_grades=lambda _payload: False,
        logger=_logger_stub(),
    )
    assert second is not None
    assert second["signals"][0]["ticker"] == "000001"

    with sqlite3.connect(db_path) as conn:
        row_count = int(conn.execute("SELECT COUNT(*) FROM jongga_recent_valid_payload_cache").fetchone()[0])
    assert row_count >= 1


def test_find_recent_valid_jongga_payload_skips_delete_when_rows_within_limit(monkeypatch, tmp_path):
    payload_helpers._RECENT_JONGGA_PAYLOAD_CACHE.clear()
    payload_helpers._RECENT_JONGGA_SQLITE_READY.clear()
    monkeypatch.setattr(payload_helpers, "_RECENT_JONGGA_SQLITE_MAX_ROWS", 16)

    (tmp_path / "jongga_v2_results_20260220.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        payload_helpers,
        "load_json_from_path",
        lambda *_args, **_kwargs: {
            "date": "2026-02-20",
            "signals": [{"ticker": "000001"}],
        },
    )

    traced_sql: list[str] = []
    original_connect = payload_helpers.connect_sqlite

    def _traced_connect(*args, **kwargs):
        conn = original_connect(*args, **kwargs)
        conn.set_trace_callback(traced_sql.append)
        return conn

    monkeypatch.setattr(payload_helpers, "connect_sqlite", _traced_connect)

    loaded = payload_helpers.find_recent_valid_jongga_payload(
        data_dir=str(tmp_path),
        recalculate_jongga_grades=lambda _payload: False,
        logger=_logger_stub(),
    )

    assert loaded is not None
    assert not any("DELETE FROM jongga_recent_valid_payload_cache" in sql for sql in traced_sql)


def test_recent_jongga_sqlite_repeated_snapshot_key_prunes_once(monkeypatch, tmp_path):
    _reset_recent_jongga_state()
    monkeypatch.setattr(payload_helpers, "_RECENT_JONGGA_SQLITE_PRUNE_FORCE_INTERVAL", 10_000)
    prune_calls = {"count": 0}
    original_prune = payload_helpers.prune_rows_by_updated_at_if_needed

    def _counted_prune(*args, **kwargs):
        prune_calls["count"] += 1
        return original_prune(*args, **kwargs)

    monkeypatch.setattr(payload_helpers, "prune_rows_by_updated_at_if_needed", _counted_prune)

    payload_helpers._save_recent_payload_to_sqlite(
        data_dir=str(tmp_path),
        cache_key="dataset-a",
        signature=(1, 10),
        payload={"date": "2026-02-20", "signals": [{"ticker": "000001"}]},
        logger=_logger_stub(),
    )
    payload_helpers._save_recent_payload_to_sqlite(
        data_dir=str(tmp_path),
        cache_key="dataset-a",
        signature=(1, 10),
        payload={"date": "2026-02-21", "signals": [{"ticker": "000001"}]},
        logger=_logger_stub(),
    )

    assert prune_calls["count"] == 1


def test_recent_jongga_sqlite_forces_prune_on_configured_interval(monkeypatch, tmp_path):
    _reset_recent_jongga_state()
    monkeypatch.setattr(payload_helpers, "_RECENT_JONGGA_SQLITE_PRUNE_FORCE_INTERVAL", 2)
    prune_calls = {"count": 0}
    original_prune = payload_helpers.prune_rows_by_updated_at_if_needed

    def _counted_prune(*args, **kwargs):
        prune_calls["count"] += 1
        return original_prune(*args, **kwargs)

    monkeypatch.setattr(payload_helpers, "prune_rows_by_updated_at_if_needed", _counted_prune)

    payload_helpers._save_recent_payload_to_sqlite(
        data_dir=str(tmp_path),
        cache_key="dataset-b",
        signature=(1, 10),
        payload={"date": "2026-02-20", "signals": [{"ticker": "000001"}]},
        logger=_logger_stub(),
    )
    payload_helpers._save_recent_payload_to_sqlite(
        data_dir=str(tmp_path),
        cache_key="dataset-b",
        signature=(1, 10),
        payload={"date": "2026-02-21", "signals": [{"ticker": "000001"}]},
        logger=_logger_stub(),
    )

    assert prune_calls["count"] == 2


def test_recent_jongga_sqlite_ready_uses_normalized_db_key(monkeypatch, tmp_path):
    payload_helpers._RECENT_JONGGA_PAYLOAD_CACHE.clear()
    payload_helpers._RECENT_JONGGA_SQLITE_READY.clear()
    monkeypatch.chdir(tmp_path)

    connect_calls = {"count": 0}
    original_connect = payload_helpers.connect_sqlite

    def _counted_connect(*args, **kwargs):
        connect_calls["count"] += 1
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(payload_helpers, "connect_sqlite", _counted_connect)

    assert payload_helpers._ensure_recent_payload_sqlite(str(tmp_path), _logger_stub()) is True
    assert payload_helpers._ensure_recent_payload_sqlite(".", _logger_stub()) is True

    assert connect_calls["count"] == 1


def test_recent_jongga_sqlite_init_is_single_flight_under_concurrency(monkeypatch, tmp_path):
    payload_helpers._RECENT_JONGGA_PAYLOAD_CACHE.clear()
    with payload_helpers._RECENT_JONGGA_SQLITE_READY_CONDITION:
        payload_helpers._RECENT_JONGGA_SQLITE_READY.clear()
        payload_helpers._RECENT_JONGGA_SQLITE_INIT_IN_PROGRESS.clear()

    monkeypatch.setattr(payload_helpers, "sqlite_db_path_exists", lambda _path: True)

    entered_event = threading.Event()
    release_event = threading.Event()
    run_calls = {"count": 0}

    def _run_once(_operation, *, max_retries, retry_delay_seconds):
        run_calls["count"] += 1
        if run_calls["count"] == 1:
            entered_event.set()
            assert release_event.wait(timeout=2.0)
        return None

    monkeypatch.setattr(payload_helpers, "run_sqlite_with_retry", _run_once)

    results: dict[str, bool] = {}

    def _worker(name: str) -> None:
        results[name] = bool(payload_helpers._ensure_recent_payload_sqlite(str(tmp_path), _logger_stub()))

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


def test_recent_jongga_sqlite_waiter_retries_after_initializer_failure(monkeypatch, tmp_path):
    payload_helpers._RECENT_JONGGA_PAYLOAD_CACHE.clear()
    with payload_helpers._RECENT_JONGGA_SQLITE_READY_CONDITION:
        payload_helpers._RECENT_JONGGA_SQLITE_READY.clear()
        payload_helpers._RECENT_JONGGA_SQLITE_INIT_IN_PROGRESS.clear()

    monkeypatch.setattr(payload_helpers, "sqlite_db_path_exists", lambda _path: True)

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

    monkeypatch.setattr(payload_helpers, "run_sqlite_with_retry", _fail_then_succeed)

    results: dict[str, bool] = {}

    def _worker(name: str) -> None:
        results[name] = bool(payload_helpers._ensure_recent_payload_sqlite(str(tmp_path), _logger_stub()))

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
