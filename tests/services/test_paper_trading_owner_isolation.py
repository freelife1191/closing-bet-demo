#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""INFRA-060 계정 소유자 격리 회귀 테스트."""

from __future__ import annotations

import sqlite3
import threading

import pytest

import services.paper_trading_db_setup as db_setup
from services.paper_trading import PaperTradingService
from services.paper_trading_constants import INITIAL_CASH_KRW


ALICE = "alice@example.test"
BOB = "bob@example.test"


def _service(tmp_path) -> PaperTradingService:
    return PaperTradingService(db_path=str(tmp_path / "paper-trading.sqlite3"), auto_start_sync=False)


def test_accounts_are_isolated_for_same_ticker_and_all_history(tmp_path):
    service = _service(tmp_path)

    assert service.deposit_cash(1_000, owner_id=ALICE)["status"] == "success"
    assert service.get_balance(owner_id=ALICE) == INITIAL_CASH_KRW + 1_000
    assert service.get_balance(owner_id=BOB) == INITIAL_CASH_KRW
    assert service.buy_stock("005930", "삼성전자", 1_000, 2, owner_id=ALICE)["status"] == "success"
    assert service.buy_stock("005930", "삼성전자", 2_000, 1, owner_id=BOB)["status"] == "success"

    assert service.get_portfolio(owner_id=ALICE)["holdings"][0]["quantity"] == 2
    assert service.get_portfolio(owner_id=BOB)["holdings"][0]["quantity"] == 1
    assert len(service.get_trade_history(owner_id=ALICE)["trades"]) == 1
    assert len(service.get_trade_history(owner_id=BOB)["trades"]) == 1
    service.record_asset_history(2_000, owner_id=ALICE)
    service.record_asset_history(2_000, owner_id=BOB)
    assert service.get_asset_history(owner_id=ALICE)
    assert service.get_asset_history(owner_id=BOB)


def test_owner_is_required_and_legacy_owner_is_denied(tmp_path):
    service = _service(tmp_path)

    with pytest.raises(TypeError):
        service.get_balance()
    with pytest.raises(ValueError):
        service.get_balance(owner_id="")
    with pytest.raises(ValueError):
        service.get_balance(owner_id="__legacy_unassigned__")


def test_legacy_schema_and_price_cache_are_preserved_but_not_activated(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE balance (id INTEGER PRIMARY KEY, cash REAL, total_deposit REAL);
            INSERT INTO balance VALUES (1, 55, 4);
            CREATE TABLE portfolio (ticker TEXT PRIMARY KEY, name TEXT, avg_price REAL, quantity INTEGER, total_cost REAL, last_updated TEXT);
            INSERT INTO portfolio VALUES ('005930', '삼성전자', 50, 1, 50, '2026-09-08T00:00:00');
            CREATE TABLE trade_log (id INTEGER PRIMARY KEY, action TEXT, ticker TEXT, name TEXT, price REAL, quantity INTEGER, timestamp TEXT, profit REAL, profit_rate REAL);
            INSERT INTO trade_log VALUES (1, 'BUY', '005930', '삼성전자', 50, 1, '2026-09-08T00:00:00', 0, 0);
            CREATE TABLE asset_history (date TEXT PRIMARY KEY, total_asset REAL, cash REAL, stock_value REAL, timestamp TEXT);
            INSERT INTO asset_history VALUES ('2026-09-08', 55, 55, 0, '2026-09-08T00:00:00');
            CREATE TABLE price_cache (ticker TEXT PRIMARY KEY, price INTEGER, updated_at TEXT);
            INSERT INTO price_cache VALUES ('005930', 77777, '2026-09-08T00:00:00');
            """
        )

    service = PaperTradingService(db_path=str(path), auto_start_sync=False)
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT owner_id, cash FROM balance").fetchall() == [("__legacy_unassigned__", 55.0)]
        assert conn.execute("SELECT id FROM trade_log").fetchall() == [(1,)]
        assert conn.execute("SELECT price FROM legacy_price_cache WHERE ticker = '005930'").fetchone() == (77777,)
        assert conn.execute("SELECT * FROM price_cache").fetchall() == []
    assert service.price_cache == {}


def test_trade_prices_never_overwrite_shared_provider_cache(tmp_path):
    service = _service(tmp_path)
    service._persist_price_cache({"005930": 70_000})
    with service.cache_lock:
        service.price_cache["005930"] = 70_000

    assert service.buy_stock("005930", "삼성전자", 1_000, 1, owner_id=ALICE)["status"] == "success"
    assert service.sell_stock("005930", 2_000, 1, owner_id=ALICE)["status"] == "success"
    with service.cache_lock:
        assert service.price_cache["005930"] == 70_000
    with service.get_read_context() as conn:
        assert conn.execute("SELECT price FROM price_cache WHERE ticker = '005930'").fetchone() == (70_000,)


def test_concurrent_balance_debits_are_owner_scoped_and_atomic(tmp_path):
    service = _service(tmp_path)
    results: list[str] = []

    def buy() -> None:
        results.append(service.buy_stock("005930", "삼성전자", 60_000_000, 1, owner_id=ALICE)["status"])

    first = threading.Thread(target=buy)
    second = threading.Thread(target=buy)
    first.start()
    second.start()
    first.join()
    second.join()

    assert results.count("success") == 1
    assert service.get_balance(owner_id=ALICE) == 40_000_000
    assert service.get_balance(owner_id=BOB) == INITIAL_CASH_KRW


def test_reset_only_removes_the_callers_data_and_keeps_shared_price_cache(tmp_path):
    service = _service(tmp_path)
    service._persist_price_cache({"005930": 70_000})
    assert service.buy_stock("005930", "삼성전자", 1_000, 1, owner_id=ALICE)["status"] == "success"
    assert service.buy_stock("005930", "삼성전자", 1_000, 1, owner_id=BOB)["status"] == "success"

    assert service.reset_account(owner_id=ALICE) is True

    assert service.get_portfolio(owner_id=ALICE)["holdings"] == []
    assert len(service.get_portfolio(owner_id=BOB)["holdings"]) == 1
    with service.get_read_context() as conn:
        assert conn.execute("SELECT price FROM price_cache WHERE ticker = '005930'").fetchone() == (70_000,)


def test_provider_ticker_collection_excludes_legacy_positions(tmp_path):
    path = tmp_path / "legacy-tickers.sqlite3"
    service = PaperTradingService(db_path=str(path), auto_start_sync=False)
    with service.get_context() as conn:
        conn.execute(
            "INSERT INTO portfolio(owner_id, ticker, name, avg_price, quantity, total_cost, last_updated) VALUES (?, '005930', 'legacy', 1, 1, 1, 'now')",
            ("__legacy_unassigned__",),
        )
        conn.commit()
    assert service._get_portfolio_tickers() == []


def test_failed_migration_rolls_back_every_legacy_table(tmp_path, monkeypatch):
    path = tmp_path / "rollback.sqlite3"
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE balance (id INTEGER PRIMARY KEY, cash REAL, total_deposit REAL);
            CREATE TABLE portfolio (ticker TEXT PRIMARY KEY, name TEXT, avg_price REAL, quantity INTEGER, total_cost REAL, last_updated TEXT);
            CREATE TABLE trade_log (id INTEGER PRIMARY KEY, action TEXT, ticker TEXT, name TEXT, price REAL, quantity INTEGER, timestamp TEXT);
            CREATE TABLE asset_history (date TEXT PRIMARY KEY, total_asset REAL, cash REAL, stock_value REAL, timestamp TEXT);
            CREATE TABLE price_cache (ticker TEXT PRIMARY KEY, price INTEGER, updated_at TEXT);
            """
        )

    monkeypatch.setattr(db_setup, "_create_indexes", lambda _cursor: (_ for _ in ()).throw(RuntimeError("forced")))
    assert db_setup.init_db(db_path=str(path), logger=__import__("logging").getLogger(__name__), force_recheck=True) is False

    with sqlite3.connect(path) as conn:
        assert [row[1] for row in conn.execute("PRAGMA table_info(balance)")] == ["id", "cash", "total_deposit"]
        assert conn.execute("SELECT name FROM sqlite_master WHERE name = 'legacy_price_cache'").fetchone() is None


def test_repeated_initialization_never_reclassifies_active_price_cache(tmp_path):
    path = tmp_path / "repeat.sqlite3"
    service = PaperTradingService(db_path=str(path), auto_start_sync=False)
    service._persist_price_cache({"005930": 70_000})

    assert db_setup.init_db(db_path=str(path), logger=__import__("logging").getLogger(__name__), force_recheck=True)
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT price FROM price_cache WHERE ticker='005930'").fetchone() == (70_000,)
        assert conn.execute("SELECT 1 FROM paper_trading_schema_migrations WHERE name='infra060_owner_isolation'").fetchone()


def test_partial_scoped_schema_recovery_preserves_each_owner(tmp_path):
    path = tmp_path / "partial.sqlite3"
    service = PaperTradingService(db_path=str(path), auto_start_sync=False)
    service.deposit_cash(1, owner_id=ALICE)
    service.deposit_cash(2, owner_id=BOB)
    with sqlite3.connect(path) as conn:
        conn.execute("DROP TABLE asset_history")

    assert db_setup.init_db(db_path=str(path), logger=__import__("logging").getLogger(__name__), force_recheck=True)
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT owner_id, cash FROM balance ORDER BY owner_id").fetchall() == [
            (ALICE, float(INITIAL_CASH_KRW + 1)),
            (BOB, float(INITIAL_CASH_KRW + 2)),
        ]
        assert "owner_id" in [row[1] for row in conn.execute("PRAGMA table_info(asset_history)")]


def test_migrated_active_price_cache_receives_its_own_index(tmp_path):
    path = tmp_path / "cache-index.sqlite3"
    with sqlite3.connect(path) as conn:
        conn.executescript("""
            CREATE TABLE portfolio (ticker TEXT PRIMARY KEY, name TEXT, avg_price REAL, quantity INTEGER, total_cost REAL, last_updated TEXT);
            CREATE TABLE trade_log (id INTEGER PRIMARY KEY, action TEXT, ticker TEXT, name TEXT, price REAL, quantity INTEGER, timestamp TEXT);
            CREATE TABLE asset_history (date TEXT PRIMARY KEY, total_asset REAL, cash REAL, stock_value REAL, timestamp TEXT);
            CREATE TABLE balance (id INTEGER PRIMARY KEY, cash REAL);
            CREATE TABLE price_cache (ticker TEXT PRIMARY KEY, price INTEGER, updated_at TEXT);
            CREATE INDEX idx_price_cache_updated_at ON price_cache(updated_at DESC);
        """)
    assert db_setup.init_db(db_path=str(path), logger=__import__("logging").getLogger(__name__), force_recheck=True)
    with sqlite3.connect(path) as conn:
        assert "idx_price_cache_updated_at" in {row[1] for row in conn.execute("PRAGMA index_list(price_cache)")}


@pytest.mark.parametrize("method_name", ["get_asset_history", "get_portfolio_valuation"])
def test_owner_reads_recover_when_balance_table_is_missing(tmp_path, method_name):
    service = _service(tmp_path)
    service.get_balance(owner_id=ALICE)
    with service.get_context() as conn:
        conn.execute("DROP TABLE balance")
        conn.commit()

    result = getattr(service, method_name)(owner_id=ALICE)

    if method_name == "get_asset_history":
        assert result[-1]["cash"] == INITIAL_CASH_KRW
    else:
        assert result["cash"] == INITIAL_CASH_KRW
