#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PaperTrading SQLite 스키마/마이그레이션 초기화 유틸.
"""

from __future__ import annotations

import os
import sqlite3
import threading

from services.sqlite_utils import build_sqlite_pragmas, connect_sqlite

SQLITE_BUSY_TIMEOUT_MS = 30_000
SQLITE_INIT_PRAGMAS = build_sqlite_pragmas(
    busy_timeout_ms=SQLITE_BUSY_TIMEOUT_MS,
)
DB_INIT_READY_LOCK = threading.Lock()
DB_INIT_READY_PATHS: set[str] = set()


def is_duplicate_column_error(error: Exception) -> bool:
    """ALTER TABLE ADD COLUMN 중복 컬럼 예외인지 판별한다."""
    if not isinstance(error, sqlite3.OperationalError):
        return False
    return "duplicate column name" in str(error).lower()


def _create_indexes(cursor: sqlite3.Cursor) -> None:
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_trade_log_timestamp
        ON trade_log(timestamp DESC)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_trade_log_ticker_timestamp
        ON trade_log(ticker, timestamp DESC)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_asset_history_timestamp
        ON asset_history(timestamp DESC)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_price_cache_updated_at
        ON price_cache(updated_at DESC)
        """
    )


def _normalize_db_key(path: str) -> str:
    try:
        return os.path.realpath(os.path.expanduser(path))
    except Exception:
        return path


def _load_table_columns(cursor: sqlite3.Cursor, table_name: str) -> set[str]:
    rows = cursor.execute(f"PRAGMA table_info({table_name})").fetchall()
    columns: set[str] = set()
    for row in rows:
        if len(row) < 2:
            continue
        columns.add(str(row[1]))
    return columns


def _ensure_trade_log_columns(cursor: sqlite3.Cursor, logger) -> None:
    columns = _load_table_columns(cursor, "trade_log")

    if "profit" not in columns:
        try:
            cursor.execute("ALTER TABLE trade_log ADD COLUMN profit REAL DEFAULT 0")
        except sqlite3.OperationalError as error:
            if not is_duplicate_column_error(error):
                logger.error(f"Failed to migrate trade_log.profit: {error}")

    if "profit_rate" not in columns:
        try:
            cursor.execute("ALTER TABLE trade_log ADD COLUMN profit_rate REAL DEFAULT 0")
        except sqlite3.OperationalError as error:
            if not is_duplicate_column_error(error):
                logger.error(f"Failed to migrate trade_log.profit_rate: {error}")


def _ensure_balance_columns(cursor: sqlite3.Cursor, logger) -> None:
    columns = _load_table_columns(cursor, "balance")
    if "total_deposit" in columns:
        return

    try:
        cursor.execute("ALTER TABLE balance ADD COLUMN total_deposit REAL DEFAULT 0")
    except sqlite3.OperationalError as error:
        if not is_duplicate_column_error(error):
            logger.error(f"Failed to migrate balance.total_deposit: {error}")


def init_db(*, db_path: str, logger, force_recheck: bool = False) -> bool:
    """Paper trading DB 초기화."""
    db_key = _normalize_db_key(db_path)
    with DB_INIT_READY_LOCK:
        if not force_recheck and db_key in DB_INIT_READY_PATHS:
            if os.path.exists(db_path):
                return True
            DB_INIT_READY_PATHS.discard(db_key)

    try:
        with connect_sqlite(
            db_path,
            timeout_seconds=30,
            pragmas=SQLITE_INIT_PRAGMAS,
        ) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS portfolio (
                    ticker TEXT PRIMARY KEY,
                    name TEXT,
                    avg_price REAL,
                    quantity INTEGER,
                    total_cost REAL,
                    last_updated TEXT
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS trade_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT,
                    ticker TEXT,
                    name TEXT,
                    price REAL,
                    quantity INTEGER,
                    timestamp TEXT,
                    profit REAL DEFAULT 0,
                    profit_rate REAL DEFAULT 0
                )
                """
            )

            _ensure_trade_log_columns(cursor, logger)

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS asset_history (
                    date TEXT PRIMARY KEY,
                    total_asset REAL,
                    cash REAL,
                    stock_value REAL,
                    timestamp TEXT
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS balance (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    cash REAL DEFAULT 100000000,
                    total_deposit REAL DEFAULT 0
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS price_cache (
                    ticker TEXT PRIMARY KEY,
                    price INTEGER NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

            _ensure_balance_columns(cursor, logger)

            cursor.execute(
                "INSERT OR IGNORE INTO balance (id, cash, total_deposit) VALUES (1, 100000000, 0)"
            )
            _create_indexes(cursor)
            conn.commit()
        with DB_INIT_READY_LOCK:
            DB_INIT_READY_PATHS.add(db_key)
        return True
    except Exception as error:
        with DB_INIT_READY_LOCK:
            DB_INIT_READY_PATHS.discard(db_key)
        logger.error(f"Failed to initialize paper trading db: {error}")
        return False
