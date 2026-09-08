#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""INFRA-060 모의투자 마이그레이션 안전성 회귀 테스트."""

from __future__ import annotations

import logging
import multiprocessing
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

import services.paper_trading_db_setup as db_setup
from services.paper_trading import PaperTradingService
from services.paper_trading_constants import (
    INITIAL_CASH_KRW,
    LEGACY_UNASSIGNED_OWNER_ID,
)


ALICE = "alice@example.test"
BOB = "bob@example.test"
LOGGER = logging.getLogger(__name__)


def _create_populated_legacy_database(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE balance (
                id INTEGER PRIMARY KEY,
                cash REAL,
                total_deposit REAL
            );
            INSERT INTO balance VALUES (1, 12345678, 345678);

            CREATE TABLE portfolio (
                ticker TEXT PRIMARY KEY,
                name TEXT,
                avg_price REAL,
                quantity INTEGER,
                total_cost REAL,
                last_updated TEXT
            );
            INSERT INTO portfolio VALUES
                ('005930', '삼성전자', 70000, 3, 210000, '2026-09-07T15:30:00'),
                ('000660', 'SK하이닉스', 120000, 2, 240000, '2026-09-08T15:30:00');

            CREATE TABLE trade_log (
                id INTEGER PRIMARY KEY,
                action TEXT,
                ticker TEXT,
                name TEXT,
                price REAL,
                quantity INTEGER,
                timestamp TEXT,
                profit REAL,
                profit_rate REAL
            );
            INSERT INTO trade_log VALUES
                (7, 'BUY', '005930', '삼성전자', 70000, 3, '2026-09-07T15:30:00', 0, 0),
                (9, 'SELL', '000660', 'SK하이닉스', 125000, 1, '2026-09-08T15:30:00', 5000, 4.1666667);

            CREATE TABLE asset_history (
                date TEXT PRIMARY KEY,
                total_asset REAL,
                cash REAL,
                stock_value REAL,
                timestamp TEXT
            );
            INSERT INTO asset_history VALUES
                ('2026-09-07', 12700000, 12250000, 450000, '2026-09-07T15:31:00'),
                ('2026-09-08', 12710000, 12260000, 450000, '2026-09-08T15:31:00');

            CREATE TABLE price_cache (
                ticker TEXT PRIMARY KEY,
                price INTEGER,
                updated_at TEXT
            );
            INSERT INTO price_cache VALUES
                ('005930', 77777, '2026-09-07T15:32:00'),
                ('000660', 133333, '2026-09-08T15:32:00');
            """
        )


def _database_snapshot(db_path: Path) -> tuple[list[tuple[Any, ...]], dict[str, list[tuple[Any, ...]]]]:
    with sqlite3.connect(db_path) as conn:
        schema = conn.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master ORDER BY type, name"
        ).fetchall()
        table_names = [
            str(row[1])
            for row in schema
            if row[0] == "table" and not str(row[1]).startswith("sqlite_")
        ]
        rows = {
            table_name: conn.execute(
                f'SELECT * FROM "{table_name}" ORDER BY rowid'
            ).fetchall()
            for table_name in table_names
        }
    return schema, rows


def _legacy_rows_after_migration(db_path: Path) -> dict[str, list[tuple[Any, ...]]]:
    with sqlite3.connect(db_path) as conn:
        return {
            "balance": conn.execute(
                "SELECT owner_id, cash, total_deposit FROM balance WHERE owner_id = ?",
                (LEGACY_UNASSIGNED_OWNER_ID,),
            ).fetchall(),
            "portfolio": conn.execute(
                "SELECT owner_id, ticker, name, avg_price, quantity, total_cost, last_updated "
                "FROM portfolio WHERE owner_id = ? ORDER BY ticker",
                (LEGACY_UNASSIGNED_OWNER_ID,),
            ).fetchall(),
            "trade_log": conn.execute(
                "SELECT id, owner_id, action, ticker, name, price, quantity, timestamp, profit, profit_rate "
                "FROM trade_log WHERE owner_id = ? ORDER BY id",
                (LEGACY_UNASSIGNED_OWNER_ID,),
            ).fetchall(),
            "asset_history": conn.execute(
                "SELECT owner_id, date, total_asset, cash, stock_value, timestamp "
                "FROM asset_history WHERE owner_id = ? ORDER BY date",
                (LEGACY_UNASSIGNED_OWNER_ID,),
            ).fetchall(),
            "legacy_price_cache": conn.execute(
                "SELECT ticker, price, updated_at FROM legacy_price_cache ORDER BY ticker"
            ).fetchall(),
        }


def _expected_migrated_legacy_rows() -> dict[str, list[tuple[Any, ...]]]:
    owner = LEGACY_UNASSIGNED_OWNER_ID
    return {
        "balance": [(owner, 12_345_678.0, 345_678.0)],
        "portfolio": [
            (owner, "000660", "SK하이닉스", 120_000.0, 2, 240_000.0, "2026-09-08T15:30:00"),
            (owner, "005930", "삼성전자", 70_000.0, 3, 210_000.0, "2026-09-07T15:30:00"),
        ],
        "trade_log": [
            (7, owner, "BUY", "005930", "삼성전자", 70_000.0, 3, "2026-09-07T15:30:00", 0.0, 0.0),
            (9, owner, "SELL", "000660", "SK하이닉스", 125_000.0, 1, "2026-09-08T15:30:00", 5_000.0, 4.1666667),
        ],
        "asset_history": [
            (owner, "2026-09-07", 12_700_000.0, 12_250_000.0, 450_000.0, "2026-09-07T15:31:00"),
            (owner, "2026-09-08", 12_710_000.0, 12_260_000.0, 450_000.0, "2026-09-08T15:31:00"),
        ],
        "legacy_price_cache": [
            ("000660", 133_333, "2026-09-08T15:32:00"),
            ("005930", 77_777, "2026-09-07T15:32:00"),
        ],
    }


def _initialize_in_spawned_process(
    db_path: str,
    ready_queue: Any,
    start_event: Any,
    result_queue: Any,
) -> None:
    ready_queue.put("ready")
    if not start_event.wait(timeout=10):
        result_queue.put((False, "start timeout"))
        return
    try:
        succeeded = db_setup.init_db(
            db_path=db_path,
            logger=logging.getLogger("infra060-process-migration"),
            force_recheck=True,
        )
        result_queue.put((succeeded, None))
    except BaseException as error:
        result_queue.put((False, repr(error)))


def _table_rows(db_path: Path, table_name: str) -> list[tuple[Any, ...]]:
    with sqlite3.connect(db_path) as conn:
        return conn.execute(
            f'SELECT * FROM "{table_name}" ORDER BY rowid'
        ).fetchall()


def test_late_migration_failure_restores_original_schema_and_every_legacy_row(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "late-failure.sqlite3"
    _create_populated_legacy_database(db_path)
    before = _database_snapshot(db_path)

    def fail_after_all_table_migrations(_cursor: sqlite3.Cursor) -> None:
        raise RuntimeError("forced late migration failure")

    monkeypatch.setattr(db_setup, "_create_indexes", fail_after_all_table_migrations)

    assert db_setup.init_db(
        db_path=str(db_path),
        logger=LOGGER,
        force_recheck=True,
    ) is False
    assert _database_snapshot(db_path) == before


def test_two_spawned_processes_migrate_the_same_legacy_database_once_without_loss(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "concurrent-processes.sqlite3"
    _create_populated_legacy_database(db_path)
    context = multiprocessing.get_context("spawn")
    ready_queue = context.Queue()
    result_queue = context.Queue()
    start_event = context.Event()
    processes = [
        context.Process(
            target=_initialize_in_spawned_process,
            args=(str(db_path), ready_queue, start_event, result_queue),
        )
        for _ in range(2)
    ]

    try:
        for process in processes:
            process.start()
        assert [ready_queue.get(timeout=10) for _ in processes] == ["ready", "ready"]
        start_event.set()
        for process in processes:
            process.join(timeout=15)
        assert all(process.is_alive() is False for process in processes)
        results = [result_queue.get(timeout=5) for _ in processes]
    finally:
        start_event.set()
        for process in processes:
            if process.is_alive():
                process.terminate()
            process.join(timeout=5)
        ready_queue.close()
        result_queue.close()
        ready_queue.join_thread()
        result_queue.join_thread()

    assert results == [(True, None), (True, None)]
    assert all(process.exitcode == 0 for process in processes)
    assert _legacy_rows_after_migration(db_path) == _expected_migrated_legacy_rows()
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT * FROM price_cache").fetchall() == []
        assert conn.execute(
            "SELECT COUNT(*) FROM paper_trading_schema_migrations "
            "WHERE name = 'infra060_owner_isolation'"
        ).fetchone() == (1,)


def test_repeated_forced_migration_keeps_legacy_rows_and_provider_price_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "repeated-force.sqlite3"
    _create_populated_legacy_database(db_path)
    service = PaperTradingService(db_path=str(db_path), auto_start_sync=False)
    assert service.buy_stock(
        "035720", "카카오", 50_000, 1, owner_id=ALICE
    )["status"] == "success"
    monkeypatch.setattr(
        service,
        "_fetch_prices_toss",
        lambda _session, tickers: {ticker: 88_800 for ticker in tickers},
    )
    monkeypatch.setattr(service, "_fetch_prices_naver", lambda _session, _tickers: {})
    service._refresh_price_cache_once(
        session=object(),
        yf_module=None,
        pykrx_stock=None,
    )
    legacy_before_rechecks = _legacy_rows_after_migration(db_path)

    assert service._init_db(force_recheck=True) is True
    assert service._init_db(force_recheck=True) is True

    assert _legacy_rows_after_migration(db_path) == legacy_before_rechecks
    assert legacy_before_rechecks == _expected_migrated_legacy_rows()
    with sqlite3.connect(db_path) as conn:
        assert conn.execute(
            "SELECT ticker, price FROM price_cache ORDER BY ticker"
        ).fetchall() == [("035720", 88_800)]
    restarted = PaperTradingService(db_path=str(db_path), auto_start_sync=False)
    assert restarted.price_cache == {"035720": 88_800}


def test_missing_scoped_table_recovery_preserves_all_remaining_owner_rows(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "single-missing-table.sqlite3"
    service = PaperTradingService(db_path=str(db_path), auto_start_sync=False)
    assert service.deposit_cash(1_111, owner_id=ALICE)["status"] == "success"
    assert service.deposit_cash(2_222, owner_id=BOB)["status"] == "success"
    assert service.buy_stock(
        "005930", "삼성전자", 1_000, 2, owner_id=ALICE
    )["status"] == "success"
    assert service.buy_stock(
        "005930", "삼성전자", 2_000, 3, owner_id=BOB
    )["status"] == "success"
    service.record_asset_history(2_000, owner_id=ALICE)
    service.record_asset_history(6_000, owner_id=BOB)
    remaining_before = {
        table_name: _table_rows(db_path, table_name)
        for table_name in ("balance", "portfolio", "trade_log", "price_cache")
    }

    with sqlite3.connect(db_path) as conn:
        conn.execute("DROP TABLE asset_history")

    recovered_history = service.get_asset_history(limit=10, owner_id=ALICE)

    assert isinstance(recovered_history, list)
    assert len(recovered_history) >= 2
    assert {
        table_name: _table_rows(db_path, table_name)
        for table_name in ("balance", "portfolio", "trade_log", "price_cache")
    } == remaining_before
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM asset_history").fetchone() == (0,)
        assert {
            row[0]
            for row in conn.execute("SELECT owner_id FROM balance ORDER BY owner_id")
        } == {ALICE, BOB}
        assert {
            row[0]
            for row in conn.execute("SELECT owner_id FROM portfolio ORDER BY owner_id")
        } == {ALICE, BOB}
        assert {
            row[0]
            for row in conn.execute("SELECT owner_id FROM trade_log ORDER BY owner_id")
        } == {ALICE, BOB}


def test_concurrent_valuations_record_same_day_snapshots_for_each_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "concurrent-valuations.sqlite3"
    service = PaperTradingService(db_path=str(db_path), auto_start_sync=False)
    assert service.buy_stock(
        "005930", "삼성전자", 1_000, 2, owner_id=ALICE
    )["status"] == "success"
    assert service.deposit_cash(10_000, owner_id=BOB)["status"] == "success"
    assert service.buy_stock(
        "005930", "삼성전자", 2_000, 1, owner_id=BOB
    )["status"] == "success"
    service._persist_price_cache({"005930": 3_000})
    with service.cache_lock:
        service.price_cache["005930"] = 3_000

    original_record = service.record_asset_history_with_cash
    record_barrier = threading.Barrier(2)

    def record_after_both_valuations_arrive(
        *,
        cash: float,
        current_stock_value: float,
        owner_id: str,
    ) -> None:
        record_barrier.wait(timeout=5)
        original_record(
            cash=cash,
            current_stock_value=current_stock_value,
            owner_id=owner_id,
        )

    monkeypatch.setattr(
        service,
        "record_asset_history_with_cash",
        record_after_both_valuations_arrive,
    )
    valuations: dict[str, dict[str, Any]] = {}
    errors: list[BaseException] = []

    def value_owner(owner_id: str) -> None:
        try:
            valuations[owner_id] = service.get_portfolio_valuation(owner_id=owner_id)
        except BaseException as error:
            errors.append(error)

    threads = [
        threading.Thread(target=value_owner, args=(owner_id,))
        for owner_id in (ALICE, BOB)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert all(thread.is_alive() is False for thread in threads)
    assert errors == []
    assert valuations[ALICE]["cash"] == INITIAL_CASH_KRW - 2_000
    assert valuations[ALICE]["total_stock_value"] == 6_000
    assert valuations[ALICE]["total_asset_value"] == INITIAL_CASH_KRW + 4_000
    assert valuations[BOB]["cash"] == INITIAL_CASH_KRW + 8_000
    assert valuations[BOB]["total_stock_value"] == 3_000
    assert valuations[BOB]["total_asset_value"] == INITIAL_CASH_KRW + 11_000

    today = datetime.now().strftime("%Y-%m-%d")
    with sqlite3.connect(db_path) as conn:
        assert conn.execute(
            "SELECT owner_id, date, total_asset, cash, stock_value "
            "FROM asset_history ORDER BY owner_id"
        ).fetchall() == [
            (ALICE, today, float(INITIAL_CASH_KRW + 4_000), float(INITIAL_CASH_KRW - 2_000), 6_000.0),
            (BOB, today, float(INITIAL_CASH_KRW + 11_000), float(INITIAL_CASH_KRW + 8_000), 3_000.0),
        ]
