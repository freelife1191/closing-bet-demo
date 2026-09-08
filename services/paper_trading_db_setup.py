#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Paper Trading SQLite 스키마와 소유자 분리 마이그레이션."""

from __future__ import annotations

import sqlite3
import threading

from services.paper_trading_constants import LEGACY_UNASSIGNED_OWNER_ID
from services.sqlite_utils import (
    add_bounded_ready_key,
    build_sqlite_pragmas,
    connect_sqlite,
    normalize_sqlite_db_key,
    run_sqlite_with_retry,
    sqlite_db_path_exists,
)

SQLITE_BUSY_TIMEOUT_MS = 30_000
SQLITE_INIT_PRAGMAS = build_sqlite_pragmas(busy_timeout_ms=SQLITE_BUSY_TIMEOUT_MS)
SQLITE_RETRY_ATTEMPTS = 2
SQLITE_RETRY_DELAY_SECONDS = 0.03
DB_INIT_READY_LOCK = threading.Lock()
DB_INIT_READY_CONDITION = threading.Condition(DB_INIT_READY_LOCK)
DB_INIT_READY_PATHS: set[str] = set()
DB_INIT_READY_MAX_ENTRIES = 2_048
DB_INIT_IN_PROGRESS_PATHS: set[str] = set()

_ACCOUNT_TABLES = ("portfolio", "trade_log", "asset_history", "balance")


def _table_exists(cursor: sqlite3.Cursor, table_name: str) -> bool:
    return cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table_name,)
    ).fetchone() is not None


def _columns(cursor: sqlite3.Cursor, table_name: str) -> set[str]:
    return {str(row[1]) for row in cursor.execute(f"PRAGMA table_info({table_name})")}


def _owner_schema_ready(cursor: sqlite3.Cursor) -> bool:
    if not all(_table_exists(cursor, table) and "owner_id" in _columns(cursor, table) for table in _ACCOUNT_TABLES):
        return False
    primary_keys = {
        table: [str(row[1]) for row in cursor.execute(f"PRAGMA table_info({table})") if int(row[5]) > 0]
        for table in _ACCOUNT_TABLES
    }
    return (
        primary_keys["balance"] == ["owner_id"]
        and primary_keys["portfolio"] == ["owner_id", "ticker"]
        and primary_keys["asset_history"] == ["owner_id", "date"]
    )


def _create_account_tables(cursor: sqlite3.Cursor) -> None:
    cursor.execute("""CREATE TABLE IF NOT EXISTS balance (
        owner_id TEXT PRIMARY KEY, cash REAL NOT NULL, total_deposit REAL NOT NULL DEFAULT 0)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS portfolio (
        owner_id TEXT NOT NULL, ticker TEXT NOT NULL, name TEXT, avg_price REAL,
        quantity INTEGER, total_cost REAL, last_updated TEXT,
        PRIMARY KEY (owner_id, ticker))""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS trade_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT, owner_id TEXT NOT NULL, action TEXT,
        ticker TEXT, name TEXT, price REAL, quantity INTEGER, timestamp TEXT,
        profit REAL DEFAULT 0, profit_rate REAL DEFAULT 0)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS asset_history (
        owner_id TEXT NOT NULL, date TEXT NOT NULL, total_asset REAL, cash REAL,
        stock_value REAL, timestamp TEXT, PRIMARY KEY (owner_id, date))""")


def _create_indexes(cursor: sqlite3.Cursor) -> None:
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trade_log_timestamp_id ON trade_log(timestamp DESC, id DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_portfolio_owner_updated ON portfolio(owner_id, last_updated DESC, ticker ASC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_portfolio_normalized_ticker ON portfolio(CASE WHEN length(ticker) >= 6 THEN ticker ELSE substr('000000' || ticker, -6) END)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_portfolio_last_updated ON portfolio(last_updated DESC, ticker ASC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trade_log_owner_timestamp ON trade_log(owner_id, timestamp DESC, id DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_asset_history_owner_date ON asset_history(owner_id, date DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_price_cache_updated_at ON price_cache(updated_at DESC)")


def _migrate_account_tables(cursor: sqlite3.Cursor) -> None:
    if _owner_schema_ready(cursor):
        return
    existing = [table for table in _ACCOUNT_TABLES if _table_exists(cursor, table)]
    scoped = [table for table in existing if "owner_id" in _columns(cursor, table)]
    if scoped:
        if len(scoped) != len(existing):
            raise RuntimeError("Refusing to mix scoped and legacy paper-trading tables")
        for table in scoped:
            if table == "balance":
                expected_key = ["owner_id"]
            elif table == "portfolio":
                expected_key = ["owner_id", "ticker"]
            elif table == "asset_history":
                expected_key = ["owner_id", "date"]
            else:
                continue
            actual_key = [str(row[1]) for row in cursor.execute(f"PRAGMA table_info({table})") if int(row[5]) > 0]
            if actual_key != expected_key:
                raise RuntimeError(f"Refusing to migrate malformed scoped table: {table}")
        _create_account_tables(cursor)
        return
    legacy_tables: list[tuple[str, str]] = []
    for table in _ACCOUNT_TABLES:
        if _table_exists(cursor, table):
            legacy_name = f"__infra060_old_{table}"
            cursor.execute(f"DROP TABLE IF EXISTS {legacy_name}")
            cursor.execute(f"ALTER TABLE {table} RENAME TO {legacy_name}")
            legacy_tables.append((table, legacy_name))
    _create_account_tables(cursor)
    for table, legacy_name in legacy_tables:
        columns = _columns(cursor, legacy_name)
        if table == "balance":
            total_deposit = "COALESCE(total_deposit, 0)" if "total_deposit" in columns else "0"
            cursor.execute(
                f"INSERT INTO balance(owner_id, cash, total_deposit) SELECT ?, COALESCE(cash, 0), {total_deposit} FROM {legacy_name} LIMIT 1",
                (LEGACY_UNASSIGNED_OWNER_ID,),
            )
        elif table == "portfolio":
            cursor.execute(
                f"INSERT INTO portfolio(owner_id, ticker, name, avg_price, quantity, total_cost, last_updated) SELECT ?, ticker, name, avg_price, quantity, COALESCE(total_cost, avg_price * quantity), last_updated FROM {legacy_name}",
                (LEGACY_UNASSIGNED_OWNER_ID,),
            )
        elif table == "trade_log":
            profit = "profit" if "profit" in columns else "0"
            profit_rate = "profit_rate" if "profit_rate" in columns else "0"
            cursor.execute(
                f"INSERT INTO trade_log(id, owner_id, action, ticker, name, price, quantity, timestamp, profit, profit_rate) SELECT id, ?, action, ticker, name, price, quantity, timestamp, {profit}, {profit_rate} FROM {legacy_name}",
                (LEGACY_UNASSIGNED_OWNER_ID,),
            )
        else:
            cursor.execute(
                f"INSERT INTO asset_history(owner_id, date, total_asset, cash, stock_value, timestamp) SELECT ?, date, total_asset, cash, stock_value, timestamp FROM {legacy_name}",
                (LEGACY_UNASSIGNED_OWNER_ID,),
            )
        cursor.execute(f"DROP TABLE {legacy_name}")


def _migrate_price_cache(cursor: sqlite3.Cursor) -> None:
    cursor.execute("CREATE TABLE IF NOT EXISTS paper_trading_schema_migrations (name TEXT PRIMARY KEY)")
    migrated = cursor.execute(
        "SELECT 1 FROM paper_trading_schema_migrations WHERE name = 'infra060_owner_isolation'"
    ).fetchone()
    if migrated:
        cursor.execute("CREATE TABLE IF NOT EXISTS price_cache (ticker TEXT PRIMARY KEY, price INTEGER NOT NULL, updated_at TEXT NOT NULL)")
        return
    if _table_exists(cursor, "price_cache"):
        cursor.execute("ALTER TABLE price_cache RENAME TO legacy_price_cache")
        cursor.execute("DROP INDEX IF EXISTS idx_price_cache_updated_at")
    cursor.execute("CREATE TABLE IF NOT EXISTS price_cache (ticker TEXT PRIMARY KEY, price INTEGER NOT NULL, updated_at TEXT NOT NULL)")
    cursor.execute("INSERT INTO paper_trading_schema_migrations(name) VALUES ('infra060_owner_isolation')")


def init_db(*, db_path: str, logger, force_recheck: bool = False) -> bool:
    """단일 IMMEDIATE 트랜잭션으로 owner 스키마와 빈 활성 가격 캐시를 준비한다."""
    db_key = normalize_sqlite_db_key(db_path)
    with DB_INIT_READY_CONDITION:
        if force_recheck:
            DB_INIT_READY_PATHS.discard(db_key)
        elif db_key in DB_INIT_READY_PATHS and sqlite_db_path_exists(db_path):
            return True
        while db_key in DB_INIT_IN_PROGRESS_PATHS:
            DB_INIT_READY_CONDITION.wait()
            if db_key in DB_INIT_READY_PATHS and sqlite_db_path_exists(db_path):
                return True
        DB_INIT_IN_PROGRESS_PATHS.add(db_key)

    succeeded = False
    def _initialize() -> None:
        with connect_sqlite(db_path, timeout_seconds=30, pragmas=SQLITE_INIT_PRAGMAS) as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE")
            try:
                _migrate_account_tables(cursor)
                _migrate_price_cache(cursor)
                _create_indexes(cursor)
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    try:
        run_sqlite_with_retry(_initialize, max_retries=SQLITE_RETRY_ATTEMPTS, retry_delay_seconds=SQLITE_RETRY_DELAY_SECONDS)
        succeeded = True
        return True
    except Exception as error:
        logger.error(f"Failed to initialize paper trading db: {error}")
        return False
    finally:
        with DB_INIT_READY_CONDITION:
            DB_INIT_IN_PROGRESS_PATHS.discard(db_key)
            if succeeded:
                add_bounded_ready_key(DB_INIT_READY_PATHS, db_key, max_entries=DB_INIT_READY_MAX_ENTRIES)
            else:
                DB_INIT_READY_PATHS.discard(db_key)
            DB_INIT_READY_CONDITION.notify_all()
