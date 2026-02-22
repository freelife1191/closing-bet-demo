#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PaperTrading DB setup 리팩토링 테스트
"""

from __future__ import annotations

import sqlite3
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
