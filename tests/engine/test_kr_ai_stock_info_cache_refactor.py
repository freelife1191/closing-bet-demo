#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR AI stock info cache 리팩토링 테스트
"""

from __future__ import annotations

import os
import sqlite3
import types

import engine.kr_ai_stock_info_cache as stock_info_cache
from services.sqlite_utils import connect_sqlite


def _logger_stub():
    return types.SimpleNamespace(debug=lambda *_args, **_kwargs: None)


def _reset_stock_info_cache_state() -> None:
    stock_info_cache.clear_stock_info_cache()
    with stock_info_cache._STOCK_INFO_SQLITE_READY_LOCK:
        stock_info_cache._STOCK_INFO_SQLITE_READY.clear()


def test_save_and_load_cached_stock_info_creates_sqlite_parent_dir_when_missing(tmp_path):
    _reset_stock_info_cache_state()
    signals_file = str(tmp_path / "signals_log.csv")
    db_path = tmp_path / "cache" / "nested" / "runtime_cache.db"
    signature = (100, 200)
    payload = {
        "ticker": "005930",
        "name": "삼성전자",
        "score": 88.0,
    }

    stock_info_cache.save_cached_stock_info(
        signals_file=signals_file,
        ticker="005930",
        signature=signature,
        payload=payload,
        logger=_logger_stub(),
        resolve_db_path_fn=lambda _signals_file: str(db_path),
    )
    stock_info_cache.clear_stock_info_cache()

    loaded = stock_info_cache.load_cached_stock_info(
        signals_file=signals_file,
        ticker="005930",
        signature=signature,
        logger=_logger_stub(),
        resolve_db_path_fn=lambda _signals_file: str(db_path),
    )

    assert db_path.exists()
    assert loaded is not None
    assert loaded["name"] == "삼성전자"

    with connect_sqlite(str(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM kr_ai_stock_info_cache")
        row_count = int(cursor.fetchone()[0])
    assert row_count >= 1


def test_save_cached_stock_info_prunes_sqlite_rows(tmp_path, monkeypatch):
    _reset_stock_info_cache_state()
    monkeypatch.setattr(stock_info_cache, "_STOCK_INFO_SQLITE_MAX_ROWS", 2)

    signals_file = str(tmp_path / "signals_log.csv")
    db_path = tmp_path / "runtime_cache.db"
    logger = _logger_stub()

    for i in range(4):
        stock_info_cache.save_cached_stock_info(
            signals_file=signals_file,
            ticker=f"{i + 1:06d}",
            signature=(i + 1, i + 10),
            payload={"ticker": f"{i + 1:06d}"},
            logger=logger,
            resolve_db_path_fn=lambda _signals_file: str(db_path),
        )

    with connect_sqlite(str(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM kr_ai_stock_info_cache")
        row_count = int(cursor.fetchone()[0])

    assert row_count == 2


def test_save_cached_stock_info_non_positive_max_rows_keeps_latest_entry(tmp_path, monkeypatch):
    _reset_stock_info_cache_state()
    monkeypatch.setattr(stock_info_cache, "_STOCK_INFO_SQLITE_MAX_ROWS", 0)

    signals_file = str(tmp_path / "signals_log.csv")
    db_path = tmp_path / "runtime_cache.db"
    logger = _logger_stub()

    stock_info_cache.save_cached_stock_info(
        signals_file=signals_file,
        ticker="005930",
        signature=(1, 10),
        payload={"ticker": "005930"},
        logger=logger,
        resolve_db_path_fn=lambda _signals_file: str(db_path),
    )
    stock_info_cache.save_cached_stock_info(
        signals_file=signals_file,
        ticker="000660",
        signature=(2, 20),
        payload={"ticker": "000660"},
        logger=logger,
        resolve_db_path_fn=lambda _signals_file: str(db_path),
    )

    with connect_sqlite(str(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM kr_ai_stock_info_cache")
        row_count = int(cursor.fetchone()[0])

    assert row_count == 1


def test_save_cached_stock_info_recovers_when_table_missing_with_ready_state(tmp_path):
    _reset_stock_info_cache_state()
    signals_file = str(tmp_path / "signals_log.csv")
    db_path = tmp_path / "runtime_cache.db"
    logger = _logger_stub()

    stock_info_cache.save_cached_stock_info(
        signals_file=signals_file,
        ticker="005930",
        signature=(1, 10),
        payload={"ticker": "005930"},
        logger=logger,
        resolve_db_path_fn=lambda _signals_file: str(db_path),
    )

    with connect_sqlite(str(db_path)) as conn:
        conn.execute("DROP TABLE kr_ai_stock_info_cache")
        conn.commit()

    stock_info_cache.save_cached_stock_info(
        signals_file=signals_file,
        ticker="000660",
        signature=(2, 20),
        payload={"ticker": "000660"},
        logger=logger,
        resolve_db_path_fn=lambda _signals_file: str(db_path),
    )
    stock_info_cache.clear_stock_info_cache()

    loaded = stock_info_cache.load_cached_stock_info(
        signals_file=signals_file,
        ticker="000660",
        signature=(2, 20),
        logger=logger,
        resolve_db_path_fn=lambda _signals_file: str(db_path),
    )
    assert loaded is not None
    assert loaded["ticker"] == "000660"

    with connect_sqlite(str(db_path)) as conn:
        row_count = int(conn.execute("SELECT COUNT(*) FROM kr_ai_stock_info_cache").fetchone()[0])
    assert row_count >= 1


def test_save_cached_stock_info_skips_delete_when_rows_within_limit(tmp_path, monkeypatch):
    _reset_stock_info_cache_state()
    monkeypatch.setattr(stock_info_cache, "_STOCK_INFO_SQLITE_MAX_ROWS", 16)
    db_path = tmp_path / "runtime_cache.db"

    traced_sql: list[str] = []
    original_connect = stock_info_cache.connect_sqlite

    def _traced_connect(*args, **kwargs):
        conn = original_connect(*args, **kwargs)
        conn.set_trace_callback(traced_sql.append)
        return conn

    monkeypatch.setattr(stock_info_cache, "connect_sqlite", _traced_connect)

    stock_info_cache.save_cached_stock_info(
        signals_file=str(tmp_path / "signals_log.csv"),
        ticker="005930",
        signature=(10, 20),
        payload={"ticker": "005930"},
        logger=_logger_stub(),
        resolve_db_path_fn=lambda _signals_file: str(db_path),
    )

    assert not any("DELETE FROM kr_ai_stock_info_cache" in sql for sql in traced_sql)


def test_stock_info_sqlite_ready_cache_uses_normalized_db_key(monkeypatch, tmp_path):
    _reset_stock_info_cache_state()
    db_path = tmp_path / "runtime_cache.db"
    connect_calls = {"count": 0}
    original_connect = stock_info_cache.connect_sqlite

    def _counted_connect(*args, **kwargs):
        connect_calls["count"] += 1
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(stock_info_cache, "connect_sqlite", _counted_connect)

    assert stock_info_cache._ensure_stock_info_sqlite(str(db_path), _logger_stub()) is True

    monkeypatch.chdir(tmp_path)
    relative_db_path = os.path.relpath(str(db_path), str(tmp_path))
    assert stock_info_cache._ensure_stock_info_sqlite(relative_db_path, _logger_stub()) is True

    assert connect_calls["count"] == 1


def test_stock_info_sqlite_schema_init_retries_on_transient_lock(monkeypatch, tmp_path):
    _reset_stock_info_cache_state()
    db_path = tmp_path / "runtime_cache.db"

    original_connect = stock_info_cache.connect_sqlite
    failure_state = {"count": 0}

    def _flaky_connect(*args, **kwargs):
        if failure_state["count"] == 0:
            failure_state["count"] += 1
            raise sqlite3.OperationalError("database is locked")
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(stock_info_cache, "connect_sqlite", _flaky_connect)

    assert stock_info_cache._ensure_stock_info_sqlite(str(db_path), _logger_stub()) is True
    assert failure_state["count"] == 1
