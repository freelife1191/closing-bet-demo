#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Cumulative Cache 단위 테스트
"""

from __future__ import annotations

import logging

import sqlite3

from services import kr_market_cumulative_cache as cumulative_cache
from services.sqlite_utils import connect_sqlite


def _reset_cache_state() -> None:
    cumulative_cache.clear_cumulative_cache()
    cumulative_cache._CUMULATIVE_SQLITE_READY.clear()


def test_save_cached_cumulative_payload_prunes_sqlite_rows(tmp_path, monkeypatch):
    _reset_cache_state()
    monkeypatch.setattr(
        cumulative_cache,
        "_CUMULATIVE_CACHE_DB_PATH",
        str(tmp_path / "runtime_cache.db"),
    )
    monkeypatch.setattr(cumulative_cache, "_CUMULATIVE_SQLITE_MAX_ROWS", 2)

    logger = logging.getLogger("test-cumulative-sqlite-prune")
    for idx in range(5):
        cumulative_cache.save_cached_cumulative_payload(
            signature=(("seed", idx),),
            payload={"kpi": {"count": idx}, "trades": [{"id": idx}]},
            logger=logger,
        )

    with connect_sqlite(str(tmp_path / "runtime_cache.db")) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM cumulative_performance_cache")
        row_count = int(cursor.fetchone()[0])

    assert row_count == 2


def test_get_cached_cumulative_payload_uses_sqlite_after_memory_clear(tmp_path, monkeypatch):
    _reset_cache_state()
    monkeypatch.setattr(
        cumulative_cache,
        "_CUMULATIVE_CACHE_DB_PATH",
        str(tmp_path / "runtime_cache.db"),
    )
    cumulative_cache._CUMULATIVE_SQLITE_READY.clear()

    signature = (("seed", 1),)
    expected = {"kpi": {"count": 1}, "trades": [{"id": "a"}]}
    logger = logging.getLogger("test-cumulative-sqlite-reuse")

    cumulative_cache.save_cached_cumulative_payload(
        signature=signature,
        payload=expected,
        logger=logger,
    )
    cumulative_cache.clear_cumulative_cache()

    loaded = cumulative_cache.get_cached_cumulative_payload(
        signature=signature,
        logger=logger,
    )
    assert loaded == expected


def test_save_cached_cumulative_payload_evicts_oldest_memory_entry(monkeypatch):
    _reset_cache_state()
    monkeypatch.setattr(cumulative_cache, "_CUMULATIVE_MEMORY_MAX_ENTRIES", 2)

    logger = logging.getLogger("test-cumulative-memory-lru")
    cumulative_cache.save_cached_cumulative_payload(
        signature=(("seed", 1),),
        payload={"kpi": {"count": 1}, "trades": [{"id": 1}]},
        logger=logger,
    )
    cumulative_cache.save_cached_cumulative_payload(
        signature=(("seed", 2),),
        payload={"kpi": {"count": 2}, "trades": [{"id": 2}]},
        logger=logger,
    )
    cumulative_cache.save_cached_cumulative_payload(
        signature=(("seed", 3),),
        payload={"kpi": {"count": 3}, "trades": [{"id": 3}]},
        logger=logger,
    )

    cache_keys = set(cumulative_cache._CUMULATIVE_CACHE.keys())
    assert cache_keys == {(("seed", 2),), (("seed", 3),)}


def test_cumulative_cache_supports_sqlite_db_path_without_parent_dir(tmp_path, monkeypatch):
    _reset_cache_state()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cumulative_cache, "_CUMULATIVE_CACHE_DB_PATH", "runtime_cache.db")
    cumulative_cache._CUMULATIVE_SQLITE_READY.clear()

    signature = (("seed", 9),)
    payload = {"kpi": {"count": 9}, "trades": [{"id": "z"}]}
    logger = logging.getLogger("test-cumulative-sqlite-no-parent")

    cumulative_cache.save_cached_cumulative_payload(
        signature=signature,
        payload=payload,
        logger=logger,
    )
    cumulative_cache.clear_cumulative_cache()

    loaded = cumulative_cache.get_cached_cumulative_payload(
        signature=signature,
        logger=logger,
    )
    assert loaded == payload


def test_cumulative_cache_recovers_when_sqlite_table_missing(tmp_path, monkeypatch):
    _reset_cache_state()
    monkeypatch.setattr(
        cumulative_cache,
        "_CUMULATIVE_CACHE_DB_PATH",
        str(tmp_path / "runtime_cache.db"),
    )
    logger = logging.getLogger("test-cumulative-sqlite-recover")

    first_signature = (("seed", 1),)
    first_payload = {"kpi": {"count": 1}, "trades": [{"id": 1}]}
    cumulative_cache.save_cached_cumulative_payload(
        signature=first_signature,
        payload=first_payload,
        logger=logger,
    )

    db_path = tmp_path / "runtime_cache.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("DROP TABLE cumulative_performance_cache")
        conn.commit()

    second_signature = (("seed", 2),)
    second_payload = {"kpi": {"count": 2}, "trades": [{"id": 2}]}
    cumulative_cache.save_cached_cumulative_payload(
        signature=second_signature,
        payload=second_payload,
        logger=logger,
    )
    cumulative_cache.clear_cumulative_cache()

    loaded = cumulative_cache.get_cached_cumulative_payload(
        signature=second_signature,
        logger=logger,
    )
    assert loaded == second_payload

    with sqlite3.connect(db_path) as conn:
        row_count = int(conn.execute("SELECT COUNT(*) FROM cumulative_performance_cache").fetchone()[0])
    assert row_count >= 1


def test_cumulative_cache_skips_delete_when_rows_within_limit(tmp_path, monkeypatch):
    _reset_cache_state()
    db_path = tmp_path / "runtime_cache.db"
    monkeypatch.setattr(cumulative_cache, "_CUMULATIVE_CACHE_DB_PATH", str(db_path))
    monkeypatch.setattr(cumulative_cache, "_CUMULATIVE_SQLITE_MAX_ROWS", 16)

    traced_sql: list[str] = []
    original_connect = cumulative_cache.connect_sqlite

    def _traced_connect(*args, **kwargs):
        conn = original_connect(*args, **kwargs)
        conn.set_trace_callback(traced_sql.append)
        return conn

    monkeypatch.setattr(cumulative_cache, "connect_sqlite", _traced_connect)

    cumulative_cache.save_cached_cumulative_payload(
        signature=(("seed", 42),),
        payload={"kpi": {"count": 42}, "trades": [{"id": 42}]},
        logger=logging.getLogger("test-cumulative-skip-delete"),
    )

    assert not any("DELETE FROM cumulative_performance_cache" in sql for sql in traced_sql)
    assert not any("SELECT COUNT(*) FROM cumulative_performance_cache" in sql for sql in traced_sql)
