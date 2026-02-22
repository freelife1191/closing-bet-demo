#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PaperTrading DB setup 리팩토링 테스트
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time
import types

import services.paper_trading_db_setup as db_setup
from services.paper_trading_db_setup import init_db


def _logger_stub():
    return types.SimpleNamespace(
        warning=lambda *_args, **_kwargs: None,
        error=lambda *_args, **_kwargs: None,
    )


def test_init_db_creates_required_tables_and_indexes(tmp_path):
    db_path = tmp_path / "cache" / "nested" / "paper_trading.db"

    assert init_db(db_path=str(db_path), logger=_logger_stub()) is True

    assert db_path.exists()
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='price_cache'"
        )
        assert cursor.fetchone() is not None

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='trade_log'"
        )
        assert cursor.fetchone() is not None

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_price_cache_updated_at'"
        )
        assert cursor.fetchone() is not None


def test_init_db_accepts_filename_only_path(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    local_db_path = "paper_trading_local.db"

    assert init_db(db_path=local_db_path, logger=_logger_stub()) is True

    with sqlite3.connect(local_db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='price_cache'"
        )
        assert cursor.fetchone() is not None


def test_init_db_skips_redundant_reinitialization(monkeypatch, tmp_path):
    db_path = tmp_path / "paper_trading_cached.db"
    with db_setup.DB_INIT_READY_LOCK:
        db_setup.DB_INIT_READY_PATHS.clear()

    assert init_db(db_path=str(db_path), logger=_logger_stub()) is True

    monkeypatch.setattr(
        db_setup,
        "connect_sqlite",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("connect_sqlite should not be called when schema is ready")
        ),
    )

    assert init_db(db_path=str(db_path), logger=_logger_stub()) is True


def test_init_db_force_recheck_bypasses_ready_cache(monkeypatch, tmp_path):
    db_path = tmp_path / "paper_trading_force.db"
    with db_setup.DB_INIT_READY_LOCK:
        db_setup.DB_INIT_READY_PATHS.clear()

    assert init_db(db_path=str(db_path), logger=_logger_stub()) is True

    original_connect = db_setup.connect_sqlite
    connect_calls = {"count": 0}

    def _counted_connect(*args, **kwargs):
        connect_calls["count"] += 1
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(db_setup, "connect_sqlite", _counted_connect)

    assert init_db(db_path=str(db_path), logger=_logger_stub(), force_recheck=True) is True
    assert connect_calls["count"] == 1


def test_init_db_uses_shared_sqlite_init_pragmas(monkeypatch, tmp_path):
    db_path = tmp_path / "paper_trading_pragmas.db"
    with db_setup.DB_INIT_READY_LOCK:
        db_setup.DB_INIT_READY_PATHS.clear()

    captured: dict[str, tuple[str, ...] | None] = {"pragmas": None}
    original_connect = db_setup.connect_sqlite

    def _captured_connect(*args, **kwargs):
        captured["pragmas"] = tuple(kwargs.get("pragmas") or ())
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(db_setup, "connect_sqlite", _captured_connect)

    assert init_db(db_path=str(db_path), logger=_logger_stub()) is True
    assert captured["pragmas"] == db_setup.SQLITE_INIT_PRAGMAS


def test_init_db_ready_cache_uses_normalized_db_key(monkeypatch, tmp_path):
    with db_setup.DB_INIT_READY_LOCK:
        db_setup.DB_INIT_READY_PATHS.clear()
    monkeypatch.chdir(tmp_path)

    connect_calls = {"count": 0}
    original_connect = db_setup.connect_sqlite

    def _counted_connect(*args, **kwargs):
        connect_calls["count"] += 1
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(db_setup, "connect_sqlite", _counted_connect)

    relative_db_path = "./paper_trading_norm.db"
    absolute_db_path = str((tmp_path / "paper_trading_norm.db").resolve())

    assert init_db(db_path=relative_db_path, logger=_logger_stub()) is True
    assert init_db(db_path=absolute_db_path, logger=_logger_stub()) is True

    assert connect_calls["count"] == 1
    assert os.path.exists(absolute_db_path)


def test_init_db_deduplicates_concurrent_initialization(monkeypatch, tmp_path):
    db_path = tmp_path / "paper_trading_concurrent.db"
    with db_setup.DB_INIT_READY_LOCK:
        db_setup.DB_INIT_READY_PATHS.clear()
        db_setup.DB_INIT_IN_PROGRESS_PATHS.clear()

    original_connect = db_setup.connect_sqlite
    connect_calls = {"count": 0}
    first_connect_entered = threading.Event()
    connect_calls_lock = threading.Lock()

    def _slow_counted_connect(*args, **kwargs):
        with connect_calls_lock:
            connect_calls["count"] += 1
            call_index = connect_calls["count"]
        if call_index == 1:
            first_connect_entered.set()
            time.sleep(0.05)
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(db_setup, "connect_sqlite", _slow_counted_connect)

    first_result: list[bool] = []
    second_result: list[bool] = []

    thread_first = threading.Thread(
        target=lambda: first_result.append(init_db(db_path=str(db_path), logger=_logger_stub()))
    )
    thread_first.start()
    assert first_connect_entered.wait(timeout=1.0)

    thread_second = threading.Thread(
        target=lambda: second_result.append(init_db(db_path=str(db_path), logger=_logger_stub()))
    )
    thread_second.start()

    thread_first.join(timeout=2.0)
    thread_second.join(timeout=2.0)

    assert first_result == [True]
    assert second_result == [True]
    assert connect_calls["count"] == 1
