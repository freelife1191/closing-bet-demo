#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
runtime_stock_map_cache 리팩토링 회귀 테스트
"""

from __future__ import annotations

import os
import sqlite3
import sys
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
    with runtime_stock_map_cache._STOCK_MAP_SQLITE_READY_LOCK:
        runtime_stock_map_cache._STOCK_MAP_SQLITE_READY.clear()


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
