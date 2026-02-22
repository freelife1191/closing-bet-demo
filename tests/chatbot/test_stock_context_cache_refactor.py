#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stock_context_cache 리팩토링 회귀 테스트
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import chatbot.stock_context_cache as stock_context_cache


def _reset_cache_state() -> None:
    stock_context_cache.clear_result_text_cache()
    with stock_context_cache._RESULT_TEXT_SQLITE_LOCK:
        stock_context_cache._RESULT_TEXT_SQLITE_READY.clear()


def test_save_cached_result_text_evicts_oldest_memory_entry(monkeypatch, tmp_path: Path):
    _reset_cache_state()
    monkeypatch.setattr(stock_context_cache, "_RESULT_TEXT_MEMORY_MAX_ENTRIES", 2)

    source_path = tmp_path / "daily_prices.csv"
    signature = (1, 2)

    stock_context_cache.save_cached_result_text(
        data_dir=tmp_path,
        path=source_path,
        dataset="stock_history",
        ticker_padded="000001",
        signature=signature,
        payload_text="first",
    )
    stock_context_cache.save_cached_result_text(
        data_dir=tmp_path,
        path=source_path,
        dataset="stock_history",
        ticker_padded="000002",
        signature=signature,
        payload_text="second",
    )
    stock_context_cache.save_cached_result_text(
        data_dir=tmp_path,
        path=source_path,
        dataset="stock_history",
        ticker_padded="000003",
        signature=signature,
        payload_text="third",
    )

    cache_keys = list(stock_context_cache._RESULT_TEXT_CACHE.keys())
    assert len(cache_keys) == 2
    assert all("000001" not in key for key in cache_keys)
    assert any("000002" in key for key in cache_keys)
    assert any("000003" in key for key in cache_keys)


def test_save_cached_result_text_non_positive_memory_limit_keeps_latest_only(monkeypatch, tmp_path: Path):
    _reset_cache_state()
    monkeypatch.setattr(stock_context_cache, "_RESULT_TEXT_MEMORY_MAX_ENTRIES", 0)

    source_path = tmp_path / "daily_prices.csv"
    signature = (3, 4)

    stock_context_cache.save_cached_result_text(
        data_dir=tmp_path,
        path=source_path,
        dataset="signal_history",
        ticker_padded="000001",
        signature=signature,
        payload_text="alpha",
    )
    stock_context_cache.save_cached_result_text(
        data_dir=tmp_path,
        path=source_path,
        dataset="signal_history",
        ticker_padded="000002",
        signature=signature,
        payload_text="beta",
    )

    cache_keys = list(stock_context_cache._RESULT_TEXT_CACHE.keys())
    assert len(cache_keys) == 1
    assert "000002" in cache_keys[0]


def test_stock_context_cache_recovers_when_sqlite_table_missing(tmp_path: Path):
    _reset_cache_state()

    source_path = tmp_path / "daily_prices.csv"
    first_signature = (1, 10)
    second_signature = (2, 20)

    stock_context_cache.save_cached_result_text(
        data_dir=tmp_path,
        path=source_path,
        dataset="stock_history",
        ticker_padded="000001",
        signature=first_signature,
        payload_text="first payload",
    )

    db_path = tmp_path / "runtime_cache.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("DROP TABLE chatbot_stock_context_cache")
        conn.commit()

    stock_context_cache.save_cached_result_text(
        data_dir=tmp_path,
        path=source_path,
        dataset="stock_history",
        ticker_padded="000002",
        signature=second_signature,
        payload_text="second payload",
    )
    stock_context_cache.clear_result_text_cache()

    loaded = stock_context_cache.load_cached_result_text(
        data_dir=tmp_path,
        path=source_path,
        dataset="stock_history",
        ticker_padded="000002",
        signature=second_signature,
    )
    assert loaded == "second payload"

    with sqlite3.connect(db_path) as conn:
        row_count = int(conn.execute("SELECT COUNT(*) FROM chatbot_stock_context_cache").fetchone()[0])
    assert row_count >= 1


def test_save_cached_result_text_skips_delete_when_rows_within_limit(monkeypatch, tmp_path: Path):
    _reset_cache_state()
    monkeypatch.setattr(stock_context_cache, "_RESULT_TEXT_SQLITE_MAX_ROWS", 16)

    traced_sql: list[str] = []
    original_connect = stock_context_cache.connect_sqlite

    def _traced_connect(*args, **kwargs):
        conn = original_connect(*args, **kwargs)
        conn.set_trace_callback(traced_sql.append)
        return conn

    monkeypatch.setattr(stock_context_cache, "connect_sqlite", _traced_connect)

    source_path = tmp_path / "daily_prices.csv"
    stock_context_cache.save_cached_result_text(
        data_dir=tmp_path,
        path=source_path,
        dataset="stock_history",
        ticker_padded="005930",
        signature=(10, 20),
        payload_text="cached payload",
    )

    assert not any("DELETE FROM chatbot_stock_context_cache" in sql for sql in traced_sql)


def test_load_cached_result_text_retries_on_transient_sqlite_lock(monkeypatch, tmp_path: Path):
    _reset_cache_state()

    source_path = tmp_path / "daily_prices.csv"
    signature = (10, 20)
    stock_context_cache.save_cached_result_text(
        data_dir=tmp_path,
        path=source_path,
        dataset="stock_history",
        ticker_padded="005930",
        signature=signature,
        payload_text="cached payload",
    )
    stock_context_cache.clear_result_text_cache()

    original_connect = stock_context_cache.connect_sqlite
    failure_state = {"failed": False}

    def _flaky_connect(*args, **kwargs):
        if not failure_state["failed"]:
            failure_state["failed"] = True
            raise sqlite3.OperationalError("database is locked")
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(stock_context_cache, "connect_sqlite", _flaky_connect)
    loaded = stock_context_cache.load_cached_result_text(
        data_dir=tmp_path,
        path=source_path,
        dataset="stock_history",
        ticker_padded="005930",
        signature=signature,
    )

    assert failure_state["failed"] is True
    assert loaded == "cached payload"


def test_ensure_result_text_sqlite_cache_retries_on_transient_lock(monkeypatch, tmp_path: Path):
    _reset_cache_state()
    db_path = tmp_path / "runtime_cache.db"

    original_connect = stock_context_cache.connect_sqlite
    failure_state = {"count": 0}

    def _flaky_connect(*args, **kwargs):
        if failure_state["count"] == 0:
            failure_state["count"] += 1
            raise sqlite3.OperationalError("database is locked")
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(stock_context_cache, "connect_sqlite", _flaky_connect)

    assert stock_context_cache._ensure_result_text_sqlite_cache(db_path) is True
    assert failure_state["count"] == 1
