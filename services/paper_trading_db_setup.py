#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PaperTrading SQLite 스키마/마이그레이션 초기화 유틸.
"""

from __future__ import annotations

import os
import sqlite3

from services.sqlite_utils import connect_sqlite

SQLITE_INIT_PRAGMAS = (
    "PRAGMA journal_mode=WAL",
    "PRAGMA synchronous=NORMAL",
    "PRAGMA temp_store=MEMORY",
    "PRAGMA busy_timeout=30000",
)


def is_duplicate_column_error(error: Exception) -> bool:
    """ALTER TABLE ADD COLUMN 중복 컬럼 예외인지 판별한다."""
    if not isinstance(error, sqlite3.OperationalError):
        return False
    return "duplicate column name" in str(error).lower()


def _apply_init_pragmas(cursor: sqlite3.Cursor, logger) -> None:
    for pragma_sql in SQLITE_INIT_PRAGMAS:
        try:
            cursor.execute(pragma_sql)
        except sqlite3.OperationalError as error:
            logger.warning(f"Failed to apply SQLite pragma ({pragma_sql}): {error}")


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


def init_db(*, db_path: str, logger) -> None:
    """Paper trading DB 초기화."""
    try:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        with connect_sqlite(db_path, timeout_seconds=30) as conn:
            cursor = conn.cursor()
            _apply_init_pragmas(cursor, logger)

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

            try:
                cursor.execute("ALTER TABLE trade_log ADD COLUMN profit REAL DEFAULT 0")
            except sqlite3.OperationalError as error:
                if not is_duplicate_column_error(error):
                    logger.error(f"Failed to migrate trade_log.profit: {error}")

            try:
                cursor.execute("ALTER TABLE trade_log ADD COLUMN profit_rate REAL DEFAULT 0")
            except sqlite3.OperationalError as error:
                if not is_duplicate_column_error(error):
                    logger.error(f"Failed to migrate trade_log.profit_rate: {error}")

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

            try:
                cursor.execute("ALTER TABLE balance ADD COLUMN total_deposit REAL DEFAULT 0")
            except sqlite3.OperationalError as error:
                if not is_duplicate_column_error(error):
                    logger.error(f"Failed to migrate balance.total_deposit: {error}")

            cursor.execute(
                "INSERT OR IGNORE INTO balance (id, cash, total_deposit) VALUES (1, 100000000, 0)"
            )
            _create_indexes(cursor)
            conn.commit()
    except Exception as error:
        logger.error(f"Failed to initialize paper trading db: {error}")
