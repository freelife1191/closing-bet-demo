#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PaperTradingService 단위 테스트
"""

from __future__ import annotations

import sqlite3
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import services.paper_trading as paper_trading_module
from services.paper_trading import PaperTradingService
import services.paper_trading_history_mixin as paper_trading_history_mixin
from services.paper_trading_constants import (
    INITIAL_CASH_KRW,
    MAX_DEPOSIT_PER_REQUEST_KRW,
    MAX_TOTAL_DEPOSIT_KRW,
)


class _FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, headers=None, timeout=0):
        self.calls.append((url, headers, timeout))
        if self.responses:
            return self.responses.pop(0)
        return _FakeResponse(500, {}, "no-response")


def _build_service():
    db_name = f"paper_trading_test_{uuid.uuid4().hex}.db"
    return PaperTradingService(db_name=db_name, auto_start_sync=False)


def _cleanup_service(service: PaperTradingService):
    service.is_running = False
    db_file = Path(service.db_path)
    if db_file.exists():
        db_file.unlink()


def _insert_portfolio_row(service: PaperTradingService, ticker: str, name: str):
    with service.get_context() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO portfolio (ticker, name, avg_price, quantity, total_cost, last_updated)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (ticker, name, 10000, 1, 10000, "2026-01-01T00:00:00"),
        )
        conn.commit()


def test_refresh_price_cache_once_returns_short_sleep_when_portfolio_empty():
    service = _build_service()
    try:
        sleep_seconds = service._refresh_price_cache_once(
            session=_FakeSession([]),
            yf_module=None,
            pykrx_stock=None,
        )
        assert sleep_seconds == service.EMPTY_PORTFOLIO_SLEEP_SEC
        assert service.price_cache == {}
    finally:
        _cleanup_service(service)


def test_refresh_price_cache_once_chains_providers_only_for_missing_tickers(monkeypatch):
    service = _build_service()
    try:
        _insert_portfolio_row(service, "005930", "삼성전자")
        _insert_portfolio_row(service, "000660", "SK하이닉스")

        calls = []

        def fake_toss(_session, tickers):
            calls.append(("toss", tuple(tickers)))
            return {"005930": 71000}

        def fake_naver(_session, tickers):
            calls.append(("naver", tuple(tickers)))
            return {"000660": 123000}

        def fake_yf(_yf_module, tickers):
            calls.append(("yf", tuple(tickers)))
            return {}

        def fake_pykrx(_pykrx_stock, tickers):
            calls.append(("pykrx", tuple(tickers)))
            return {}

        monkeypatch.setattr(service, "_fetch_prices_toss", fake_toss)
        monkeypatch.setattr(service, "_fetch_prices_naver", fake_naver)
        monkeypatch.setattr(service, "_fetch_prices_yfinance", fake_yf)
        monkeypatch.setattr(service, "_fetch_prices_pykrx", fake_pykrx)

        sleep_seconds = service._refresh_price_cache_once(
            session=_FakeSession([]),
            yf_module=object(),
            pykrx_stock=object(),
        )

        assert sleep_seconds == service.UPDATE_INTERVAL_SEC
        assert service.price_cache["005930"] == 71000
        assert service.price_cache["000660"] == 123000
        assert calls[0][0] == "toss"
        assert set(calls[0][1]) == {"005930", "000660"}
        assert calls[1] == ("naver", ("000660",))
        assert len(calls) == 2
    finally:
        _cleanup_service(service)


def test_fetch_prices_toss_parses_bulk_response():
    service = _build_service()
    try:
        session = _FakeSession(
            [
                _FakeResponse(
                    200,
                    {
                        "result": [
                            {"code": "A005930", "close": 70200},
                            {"code": "A000660", "close": 121000},
                        ]
                    },
                )
            ]
        )

        prices = service._fetch_prices_toss(session, ["005930", "000660"])

        assert prices == {"005930": 70200, "000660": 121000}
        assert len(session.calls) == 1
        assert "productCodes=A005930,A000660" in session.calls[0][0]
    finally:
        _cleanup_service(service)


def test_fetch_prices_toss_normalizes_and_deduplicates_input_tickers():
    service = _build_service()
    try:
        session = _FakeSession(
            [
                _FakeResponse(
                    200,
                    {"result": [{"code": "A005930", "close": 70200}]},
                )
            ]
        )

        prices = service._fetch_prices_toss(session, ["5930", "005930"])

        assert prices == {"005930": 70200}
        assert len(session.calls) == 1
        assert "productCodes=A005930" in session.calls[0][0]
    finally:
        _cleanup_service(service)


def test_start_background_sync_skips_when_lock_not_acquired(monkeypatch):
    service = _build_service()
    try:
        monkeypatch.setattr(service, "_acquire_sync_loop_lock", lambda: False)
        service.start_background_sync()
        assert service.is_running is False
        assert service.bg_thread is None
    finally:
        _cleanup_service(service)


def test_update_prices_loop_resets_state_and_releases_lock(monkeypatch):
    service = _build_service()
    try:
        released = {"called": False}

        monkeypatch.setattr("services.paper_trading.run_price_update_loop_impl", lambda **_kwargs: None)
        monkeypatch.setattr(
            service,
            "_release_sync_loop_lock",
            lambda: released.__setitem__("called", True),
        )
        service.is_running = True
        service.bg_thread = object()

        service._update_prices_loop()

        assert service.is_running is False
        assert service.bg_thread is None
        assert released["called"] is True
    finally:
        _cleanup_service(service)


def test_get_portfolio_valuation_waits_for_initial_sync_on_each_call(monkeypatch):
    service = _build_service()
    try:
        _insert_portfolio_row(service, "005930", "삼성전자")

        sleep_calls = {"count": 0}

        class _FakeThread:
            @staticmethod
            def is_alive():
                return True

        def fake_sleep(_seconds):
            sleep_calls["count"] += 1

        monkeypatch.setattr("services.paper_trading.time.sleep", fake_sleep)
        service.bg_thread = _FakeThread()
        service.price_cache = {}

        first = service.get_portfolio_valuation()
        second = service.get_portfolio_valuation()

        assert first["holdings"][0]["is_stale"] is True
        assert second["holdings"][0]["is_stale"] is True
        assert sleep_calls["count"] == service.INITIAL_SYNC_WAIT_TRIES * 2
    finally:
        _cleanup_service(service)


def test_deposit_cash_updates_balance_and_total_deposit():
    service = _build_service()
    try:
        before = service.get_balance()
        result = service.deposit_cash(1_000_000)
        after = service.get_balance()

        assert result["status"] == "success"
        assert int(after - before) == 1_000_000

        with service.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT total_deposit FROM balance WHERE id = 1")
            row = cursor.fetchone()
            assert row is not None
            assert int(row[0]) == 1_000_000
    finally:
        _cleanup_service(service)


def test_deposit_cash_rejects_amount_over_per_request_limit():
    service = _build_service()
    try:
        before = service.get_balance()
        result = service.deposit_cash(MAX_DEPOSIT_PER_REQUEST_KRW + 1)
        after = service.get_balance()

        assert result["status"] == "error"
        assert "per request limit exceeded" in result["message"]
        assert int(after) == int(before)
    finally:
        _cleanup_service(service)


def test_deposit_cash_rejects_when_total_deposit_limit_exceeded():
    service = _build_service()
    try:
        with service.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE balance SET cash = ?, total_deposit = ? WHERE id = 1",
                (INITIAL_CASH_KRW + MAX_TOTAL_DEPOSIT_KRW, MAX_TOTAL_DEPOSIT_KRW),
            )
            conn.commit()

        result = service.deposit_cash(1)
        assert result["status"] == "error"
        assert "Total deposit limit exceeded" in result["message"]

        with service.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT cash, total_deposit FROM balance WHERE id = 1")
            row = cursor.fetchone()
            assert row is not None
            assert int(row[0]) == INITIAL_CASH_KRW + MAX_TOTAL_DEPOSIT_KRW
            assert int(row[1]) == MAX_TOTAL_DEPOSIT_KRW
    finally:
        _cleanup_service(service)


def test_update_balance_uses_single_connection_without_get_balance_call(monkeypatch):
    service = _build_service()
    try:
        monkeypatch.setattr(
            service,
            "get_balance",
            lambda: (_ for _ in ()).throw(AssertionError("get_balance should not be called")),
        )

        new_balance = service.update_balance(5000, operation="add")
        assert int(new_balance) == 100_005_000

        with service.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT cash FROM balance WHERE id = 1")
            row = cursor.fetchone()
            assert row is not None
            assert int(row[0]) == 100_005_000
    finally:
        _cleanup_service(service)


def test_update_balance_uses_in_place_sql_arithmetic_update(monkeypatch):
    service = _build_service()
    try:
        traced_sql: list[str] = []
        original_get_context = service.get_context

        def _traced_get_context():
            conn = original_get_context()
            conn.set_trace_callback(lambda sql: traced_sql.append(str(sql)))
            return conn

        monkeypatch.setattr(service, "get_context", _traced_get_context)

        added_balance = service.update_balance(5000, operation="add")
        subtracted_balance = service.update_balance(2000, operation="subtract")

        assert int(added_balance) == 100_005_000
        assert int(subtracted_balance) == 100_003_000
        assert any("UPDATE balance SET cash = cash + 5000" in sql for sql in traced_sql)
        assert any("UPDATE balance SET cash = cash - 2000" in sql for sql in traced_sql)
        assert not any("UPDATE balance SET cash = ?" in sql for sql in traced_sql)
        if sqlite3.sqlite_version_info >= (3, 35, 0):
            assert any("RETURNING cash" in sql for sql in traced_sql)
            assert not any("SELECT cash FROM balance WHERE id = 1" in sql for sql in traced_sql)
    finally:
        _cleanup_service(service)


def test_buy_and_sell_stock_updates_portfolio_and_trade_log():
    service = _build_service()
    try:
        buy_result = service.buy_stock("005930", "삼성전자", 1000, 10)
        assert buy_result["status"] == "success"

        portfolio_after_buy = service.get_portfolio()
        assert len(portfolio_after_buy["holdings"]) == 1
        assert portfolio_after_buy["holdings"][0]["ticker"] == "005930"
        assert portfolio_after_buy["holdings"][0]["quantity"] == 10

        sell_result = service.sell_stock("005930", 1100, 4)
        assert sell_result["status"] == "success"

        portfolio_after_sell = service.get_portfolio()
        assert len(portfolio_after_sell["holdings"]) == 1
        assert portfolio_after_sell["holdings"][0]["quantity"] == 6

        trade_history = service.get_trade_history(limit=10)["trades"]
        assert len(trade_history) == 2
        assert trade_history[0]["action"] == "SELL"
        assert trade_history[1]["action"] == "BUY"
    finally:
        _cleanup_service(service)


def test_buy_stock_does_not_call_get_balance_for_cash_check(monkeypatch):
    service = _build_service()
    try:
        monkeypatch.setattr(
            service,
            "get_balance",
            lambda: (_ for _ in ()).throw(AssertionError("get_balance should not be called")),
        )

        result = service.buy_stock("005930", "삼성전자", 1000, 1)

        assert result["status"] == "success"
    finally:
        _cleanup_service(service)


def test_buy_stock_preserves_input_ticker_for_portfolio_and_trade_log():
    service = _build_service()
    try:
        result = service.buy_stock("5930", "삼성전자", 1_000, 1)
        assert result["status"] == "success"

        with service.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM portfolio WHERE ticker = ?", ("5930",))
            raw_count = int(cursor.fetchone()[0])
            cursor.execute("SELECT COUNT(*) FROM portfolio WHERE ticker = ?", ("005930",))
            normalized_count = int(cursor.fetchone()[0])
            cursor.execute(
                "SELECT ticker FROM trade_log WHERE action = 'BUY' ORDER BY id DESC LIMIT 1"
            )
            trade_ticker_row = cursor.fetchone()

        assert raw_count == 1
        assert normalized_count == 0
        assert trade_ticker_row is not None
        assert str(trade_ticker_row[0]) == "5930"
    finally:
        _cleanup_service(service)


def test_buy_stock_insufficient_funds_updates_memory_cache_only():
    service = _build_service()
    try:
        result = service.buy_stock("005930", "삼성전자", 100_000_000, 2)
        assert result["status"] == "error"
        assert "잔고 부족" in result["message"]
        assert "보유" in result["message"]

        with service.cache_lock:
            assert service.price_cache.get("005930") == 100_000_000

        with service.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM price_cache WHERE ticker = ?", ("005930",))
            row_count = int(cursor.fetchone()[0])

        assert row_count == 0
    finally:
        _cleanup_service(service)


def test_buy_stock_insufficient_funds_uses_single_balance_snapshot_statement(monkeypatch):
    service = _build_service()
    try:
        traced_sql: list[str] = []
        original_get_context = service.get_context

        def _traced_get_context():
            conn = original_get_context()
            conn.set_trace_callback(lambda sql: traced_sql.append(str(sql)))
            return conn

        monkeypatch.setattr(service, "get_context", _traced_get_context)
        result = service.buy_stock("005930", "삼성전자", 100_000_000, 2)

        assert result["status"] == "error"
        assert "잔고 부족" in result["message"]
        assert "보유" in result["message"]
        if sqlite3.sqlite_version_info >= (3, 35, 0):
            assert any(
                "UPDATE balance SET cash = cash - 200000000" in sql and "RETURNING cash" in sql
                for sql in traced_sql
            )
            # 잔고 부족 메시지 생성을 위해 실패 경로에서는 현재 잔고 조회가 1회 필요하다.
            assert any("SELECT cash FROM balance WHERE id = 1" in sql for sql in traced_sql)
    finally:
        _cleanup_service(service)


def test_buy_stock_success_path_skips_balance_select(monkeypatch):
    service = _build_service()
    try:
        original_get_context = service.get_context
        traced_sql: list[str] = []

        def _traced_get_context():
            conn = original_get_context()
            conn.set_trace_callback(lambda sql: traced_sql.append(str(sql)))
            return conn

        monkeypatch.setattr(service, "get_context", _traced_get_context)

        result = service.buy_stock("005930", "삼성전자", 1_000, 1)
        assert result["status"] == "success"
        assert not any("SELECT cash FROM balance WHERE id = 1" in sql for sql in traced_sql)
    finally:
        _cleanup_service(service)


def test_buy_stock_rejects_non_positive_or_non_numeric_price():
    service = _build_service()
    try:
        zero_price_result = service.buy_stock("005930", "삼성전자", 0, 1)
        assert zero_price_result["status"] == "error"
        assert "Price must be a positive number" in zero_price_result["message"]

        invalid_price_result = service.buy_stock("005930", "삼성전자", "bad-price", 1)
        assert invalid_price_result["status"] == "error"
        assert "Price must be a positive number" in invalid_price_result["message"]
    finally:
        _cleanup_service(service)


def test_buy_stock_uses_sqlite_upsert_without_portfolio_select(monkeypatch):
    service = _build_service()
    try:
        monkeypatch.setattr(
            service,
            "_select_portfolio_position_by_ticker",
            lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("portfolio select should not run")),
        )

        first = service.buy_stock("005930", "삼성전자", 1_000, 1)
        second = service.buy_stock("005930", "삼성전자", 2_000, 2)
        assert first["status"] == "success"
        assert second["status"] == "success"

        with service.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT quantity, total_cost, avg_price FROM portfolio WHERE ticker = ?", ("005930",))
            row = cursor.fetchone()

        assert row is not None
        assert int(row[0]) == 3
        assert int(row[1]) == 5_000
        assert float(row[2]) == (5_000 / 3)
    finally:
        _cleanup_service(service)


def test_buy_stocks_bulk_updates_portfolio_and_trade_log_with_single_request():
    service = _build_service()
    try:
        result = service.buy_stocks_bulk(
            [
                {"ticker": "005930", "name": "삼성전자", "price": 1_000, "quantity": 10},
                {"ticker": "000660", "name": "SK하이닉스", "price": 2_000, "quantity": 5},
            ]
        )

        assert result["status"] == "success"
        assert result["summary"]["total"] == 2
        assert result["summary"]["success"] == 2
        assert result["summary"]["failed"] == 0
        assert len(result["results"]) == 2

        portfolio = service.get_portfolio()
        tickers = {holding["ticker"] for holding in portfolio["holdings"]}
        assert tickers == {"005930", "000660"}

        with service.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM trade_log WHERE action = 'BUY'")
            buy_count = int(cursor.fetchone()[0])
            cursor.execute("SELECT cash FROM balance WHERE id = 1")
            cash = int(cursor.fetchone()[0])

        assert buy_count == 2
        assert cash == 100_000_000 - (1_000 * 10) - (2_000 * 5)
    finally:
        _cleanup_service(service)


def test_buy_stocks_bulk_reports_invalid_orders_and_insufficient_funds():
    service = _build_service()
    try:
        result = service.buy_stocks_bulk(
            [
                {"ticker": "005930", "name": "삼성전자", "price": "bad", "quantity": 10},
                {"ticker": "000660", "name": "SK하이닉스", "price": 1_000, "quantity": 10},
                {"ticker": "035420", "name": "NAVER", "price": 100_000_000, "quantity": 2},
            ]
        )

        assert result["status"] == "success"
        assert result["summary"]["total"] == 3
        assert result["summary"]["success"] == 1
        assert result["summary"]["failed"] == 2
        assert any("Missing or invalid order fields" in row["message"] for row in result["results"])
        assert any("잔고 부족" in row["message"] for row in result["results"] if row["status"] == "error")

        with service.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM trade_log WHERE action = 'BUY'")
            buy_count = int(cursor.fetchone()[0])
            cursor.execute("SELECT COUNT(*) FROM portfolio WHERE ticker = ?", ("000660",))
            holding_count = int(cursor.fetchone()[0])

        assert buy_count == 1
        assert holding_count == 1
    finally:
        _cleanup_service(service)


def test_buy_stocks_bulk_preserves_input_ticker_for_trade_log():
    service = _build_service()
    try:
        result = service.buy_stocks_bulk(
            [
                {"ticker": "5930", "name": "삼성전자", "price": 1_000, "quantity": 1},
            ]
        )
        assert result["status"] == "success"

        with service.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM portfolio WHERE ticker = ?", ("5930",))
            raw_count = int(cursor.fetchone()[0])
            cursor.execute("SELECT COUNT(*) FROM portfolio WHERE ticker = ?", ("005930",))
            normalized_count = int(cursor.fetchone()[0])
            cursor.execute(
                "SELECT ticker FROM trade_log WHERE action = 'BUY' ORDER BY id DESC LIMIT 1"
            )
            trade_ticker_row = cursor.fetchone()

        assert raw_count == 1
        assert normalized_count == 0
        assert trade_ticker_row is not None
        assert str(trade_ticker_row[0]) == "5930"
    finally:
        _cleanup_service(service)


def test_buy_stocks_bulk_accumulates_duplicate_ticker_orders():
    service = _build_service()
    try:
        result = service.buy_stocks_bulk(
            [
                {"ticker": "005930", "name": "삼성전자", "price": 1_000, "quantity": 2},
                {"ticker": "005930", "name": "삼성전자", "price": 2_000, "quantity": 3},
            ]
        )
        assert result["status"] == "success"
        assert result["summary"]["success"] == 2

        portfolio = service.get_portfolio()
        assert len(portfolio["holdings"]) == 1
        assert int(portfolio["holdings"][0]["quantity"]) == 5
        assert float(portfolio["holdings"][0]["avg_price"]) == 1_600.0

        with service.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM trade_log WHERE action = 'BUY'")
            trade_count = int(cursor.fetchone()[0])
        assert trade_count == 2
    finally:
        _cleanup_service(service)


def test_buy_stocks_bulk_error_summary_includes_valid_orders_when_db_operation_fails(monkeypatch):
    service = _build_service()
    try:
        monkeypatch.setattr(
            service,
            "_execute_db_operation_with_schema_retry",
            lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("forced-db-error")),
        )

        result = service.buy_stocks_bulk(
            [
                {"ticker": "005930", "name": "삼성전자", "price": "bad", "quantity": 1},
                {"ticker": "000660", "name": "SK하이닉스", "price": 1_000, "quantity": 1},
            ]
        )

        assert result["status"] == "error"
        assert result["summary"]["total"] == 2
        assert result["summary"]["success"] == 0
        assert result["summary"]["failed"] == 2
        assert len(result["results"]) == 2
    finally:
        _cleanup_service(service)


def test_buy_stocks_bulk_skips_portfolio_lookup_when_no_order_is_affordable(monkeypatch):
    service = _build_service()
    try:
        monkeypatch.setattr(
            service,
            "_load_portfolio_positions_map_for_tickers",
            lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("portfolio lookup should be skipped")),
        )

        result = service.buy_stocks_bulk(
            [
                {"ticker": "005930", "name": "삼성전자", "price": 100_000_000, "quantity": 2},
                {"ticker": "000660", "name": "SK하이닉스", "price": 100_000_000, "quantity": 2},
            ]
        )

        assert result["status"] == "error"
        assert result["summary"]["success"] == 0
        assert result["summary"]["failed"] == 2
    finally:
        _cleanup_service(service)


def test_buy_stocks_bulk_skips_write_context_when_no_order_is_affordable(monkeypatch):
    service = _build_service()
    try:
        monkeypatch.setattr(
            service,
            "get_context",
            lambda: (_ for _ in ()).throw(AssertionError("write context should be skipped")),
        )

        result = service.buy_stocks_bulk(
            [
                {"ticker": "005930", "name": "삼성전자", "price": 100_000_000, "quantity": 2},
                {"ticker": "000660", "name": "SK하이닉스", "price": 100_000_000, "quantity": 2},
            ]
        )

        assert result["status"] == "error"
        assert result["summary"]["success"] == 0
        assert result["summary"]["failed"] == 2
    finally:
        _cleanup_service(service)


def test_buy_stocks_bulk_uses_sqlite_upsert_without_portfolio_preload(monkeypatch):
    service = _build_service()
    try:
        _insert_portfolio_row(service, "005930", "삼성전자")
        monkeypatch.setattr(
            service,
            "_load_portfolio_positions_map_for_tickers",
            lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("preload lookup should not run")),
        )

        result = service.buy_stocks_bulk(
            [
                {"ticker": "005930", "name": "삼성전자", "price": 2_000, "quantity": 2},
            ]
        )

        assert result["status"] == "success"
        assert result["summary"]["success"] == 1

        with service.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT quantity, total_cost, avg_price FROM portfolio WHERE ticker = ?",
                ("005930",),
            )
            row = cursor.fetchone()

        assert row is not None
        assert int(row[0]) == 3
        assert int(row[1]) == 14_000
        assert float(row[2]) == (14_000 / 3)
    finally:
        _cleanup_service(service)


def test_buy_stocks_bulk_single_order_uses_buy_stock_fast_path_without_read_context(monkeypatch):
    service = _build_service()
    try:
        monkeypatch.setattr(
            service,
            "get_read_context",
            lambda: (_ for _ in ()).throw(AssertionError("single-order bulk should not use read context")),
        )
        result = service.buy_stocks_bulk(
            [
                {"ticker": "005930", "name": "삼성전자", "price": 1_000, "quantity": 1},
            ]
        )

        assert result["status"] == "success"
        assert result["summary"]["total"] == 1
        assert result["summary"]["success"] == 1
        assert result["summary"]["failed"] == 0
    finally:
        _cleanup_service(service)


def test_load_portfolio_positions_map_for_tickers_handles_large_lookup_set():
    service = _build_service()
    try:
        large_tickers = [str(index).zfill(6) for index in range(1, 1300)]
        with service.get_context() as conn:
            cursor = conn.cursor()
            positions = service._load_portfolio_positions_map_for_tickers(
                cursor=cursor,
                tickers=large_tickers,
            )
        assert positions == {}
    finally:
        _cleanup_service(service)


def test_sell_stock_requires_exact_ticker_match():
    service = _build_service()
    try:
        with service.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO portfolio (ticker, name, avg_price, quantity, total_cost, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("5930", "삼성전자", 1_000, 1, 1_000, "2026-01-01T00:00:00"),
            )
            conn.commit()

        result = service.sell_stock("005930", 1_100, 1)
        assert result["status"] == "error"

        with service.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM portfolio WHERE ticker = ?", ("5930",))
            remaining_positions = int(cursor.fetchone()[0])
            cursor.execute(
                "SELECT ticker FROM trade_log WHERE action = 'SELL' ORDER BY id DESC LIMIT 1"
            )
            trade_ticker_row = cursor.fetchone()

        assert remaining_positions == 1
        assert trade_ticker_row is None
    finally:
        _cleanup_service(service)


def test_reset_account_clears_positions_and_restores_cash():
    service = _build_service()
    try:
        service.buy_stock("005930", "삼성전자", 1000, 2)
        assert len(service.get_portfolio()["holdings"]) == 1

        assert service.reset_account() is True

        portfolio = service.get_portfolio()
        assert portfolio["holdings"] == []
        assert int(portfolio["cash"]) == 100_000_000
    finally:
        _cleanup_service(service)


def test_get_portfolio_preserves_legacy_ticker_format():
    service = _build_service()
    try:
        with service.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO portfolio (ticker, name, avg_price, quantity, total_cost, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("5930", "삼성전자", 1_000, 2, 2_000, "2026-01-01T00:00:00"),
            )
            conn.commit()

        portfolio = service.get_portfolio()
        assert len(portfolio["holdings"]) == 1
        assert portfolio["holdings"][0]["ticker"] == "5930"
    finally:
        _cleanup_service(service)


def test_sell_stock_insufficient_quantity_does_not_overwrite_price_cache():
    service = _build_service()
    try:
        buy_result = service.buy_stock("005930", "삼성전자", 1_000, 1)
        assert buy_result["status"] == "success"

        with service.cache_lock:
            assert service.price_cache.get("005930") == 1_000

        sell_result = service.sell_stock("005930", 1_200, 2)
        assert sell_result["status"] == "error"

        with service.cache_lock:
            assert service.price_cache.get("005930") == 1_000

        with service.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT price FROM price_cache WHERE ticker = ?", ("005930",))
            row = cursor.fetchone()

        assert row is not None
        assert int(row[0]) == 1_000
    finally:
        _cleanup_service(service)


def test_sell_stock_rejects_non_positive_or_non_numeric_price():
    service = _build_service()
    try:
        _insert_portfolio_row(service, "005930", "삼성전자")

        zero_price_result = service.sell_stock("005930", 0, 1)
        assert zero_price_result["status"] == "error"
        assert "Price must be a positive number" in zero_price_result["message"]

        invalid_price_result = service.sell_stock("005930", "bad-price", 1)
        assert invalid_price_result["status"] == "error"
        assert "Price must be a positive number" in invalid_price_result["message"]
    finally:
        _cleanup_service(service)


def test_get_portfolio_valuation_ignores_normalized_cache_for_legacy_ticker():
    service = _build_service()
    try:
        with service.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO portfolio (ticker, name, avg_price, quantity, total_cost, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("5930", "삼성전자", 1_000, 3, 3_000, "2026-01-01T00:00:00"),
            )
            conn.commit()

        with service.cache_lock:
            service.price_cache["005930"] = 7_000

        valuation = service.get_portfolio_valuation()
        assert len(valuation["holdings"]) == 1
        assert valuation["holdings"][0]["ticker"] == "5930"
        assert valuation["holdings"][0]["current_price"] == 1_000
        assert valuation["holdings"][0]["is_stale"] is True
        assert valuation["total_stock_value"] == 3_000
    finally:
        _cleanup_service(service)


def test_get_trade_history_normalizes_invalid_limit_and_caps_upper_bound():
    service = _build_service()
    try:
        with service.get_context() as conn:
            cursor = conn.cursor()
            rows = [
                (
                    "BUY",
                    "005930",
                    "삼성전자",
                    1000,
                    1,
                    f"2026-02-22T00:00:{i % 60:02d}",
                    0,
                    0,
                )
                for i in range(600)
            ]
            cursor.executemany(
                """
                INSERT INTO trade_log (action, ticker, name, price, quantity, timestamp, profit, profit_rate)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            conn.commit()

        invalid_limit_payload = service.get_trade_history(limit="bad-limit")
        assert len(invalid_limit_payload["trades"]) == 50

        capped_limit_payload = service.get_trade_history(limit=999999)
        assert len(capped_limit_payload["trades"]) == 500
    finally:
        _cleanup_service(service)


def test_get_asset_history_normalizes_invalid_limit_and_caps_upper_bound():
    service = _build_service()
    try:
        with service.get_context() as conn:
            cursor = conn.cursor()
            base = datetime(2024, 1, 1)
            rows = []
            for i in range(600):
                day = (base + timedelta(days=i)).strftime("%Y-%m-%d")
                rows.append(
                    (
                        day,
                        100_000_000 + i,
                        50_000_000 + i,
                        50_000_000,
                        f"{day}T15:30:00",
                    )
                )
            cursor.executemany(
                """
                INSERT INTO asset_history (date, total_asset, cash, stock_value, timestamp)
                VALUES (?, ?, ?, ?, ?)
                """,
                rows,
            )
            conn.commit()

        invalid_limit_history = service.get_asset_history(limit="bad-limit")
        assert len(invalid_limit_history) == 30

        capped_limit_history = service.get_asset_history(limit=999999)
        assert len(capped_limit_history) == 500
    finally:
        _cleanup_service(service)


def test_record_asset_history_skips_duplicate_daily_snapshot_writes(monkeypatch):
    service = _build_service()
    try:
        base = datetime(2026, 2, 22, 9, 0, 0)
        now_sequence = [
            base,
            base + timedelta(seconds=1),
            base + timedelta(seconds=2),
            base + timedelta(seconds=3),
            base + timedelta(seconds=4),
            base + timedelta(seconds=5),
            base + timedelta(seconds=6),
            base + timedelta(seconds=7),
        ]

        class _FakeDateTime:
            @classmethod
            def now(cls):
                return now_sequence.pop(0)

        monkeypatch.setattr(paper_trading_history_mixin, "datetime", _FakeDateTime)

        service.record_asset_history(current_stock_value=0)
        with service.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT timestamp, stock_value FROM asset_history WHERE date = ?", ("2026-02-22",))
            first_timestamp, first_stock_value = cursor.fetchone()

        service.record_asset_history(current_stock_value=0)
        with service.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT timestamp, stock_value FROM asset_history WHERE date = ?", ("2026-02-22",))
            second_timestamp, second_stock_value = cursor.fetchone()

        assert first_stock_value == second_stock_value == 0
        assert first_timestamp == second_timestamp

        service.record_asset_history(current_stock_value=10_000)
        with service.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT timestamp, stock_value FROM asset_history WHERE date = ?", ("2026-02-22",))
            third_timestamp, third_stock_value = cursor.fetchone()

        assert third_stock_value == 10_000
        assert third_timestamp != second_timestamp
    finally:
        _cleanup_service(service)


def test_record_asset_history_with_cash_skips_write_context_for_duplicate_snapshot(monkeypatch):
    service = _build_service()
    try:
        fixed_now = datetime(2026, 2, 22, 9, 0, 0)

        class _FakeDateTime:
            @classmethod
            def now(cls):
                return fixed_now

        monkeypatch.setattr(paper_trading_history_mixin, "datetime", _FakeDateTime)
        service._set_last_asset_history_snapshot(
            date="2026-02-22",
            total_asset=100_000_000,
            cash=100_000_000,
            stock_value=0,
        )

        original_get_context = service.get_context
        write_context_calls = {"count": 0}

        def _traced_get_context():
            write_context_calls["count"] += 1
            return original_get_context()

        monkeypatch.setattr(service, "get_context", _traced_get_context)

        service.record_asset_history_with_cash(
            cash=100_000_000,
            current_stock_value=0,
        )

        assert write_context_calls["count"] == 0
        with original_get_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM asset_history")
            row_count = int(cursor.fetchone()[0])
        assert row_count == 0
    finally:
        _cleanup_service(service)


def test_record_asset_history_skips_write_context_for_duplicate_snapshot(monkeypatch):
    service = _build_service()
    try:
        fixed_now = datetime(2026, 2, 22, 9, 0, 0)
        original_get_context = service.get_context

        class _FakeDateTime:
            @classmethod
            def now(cls):
                return fixed_now

        monkeypatch.setattr(paper_trading_history_mixin, "datetime", _FakeDateTime)
        service._set_last_asset_history_snapshot(
            date="2026-02-22",
            total_asset=100_000_000,
            cash=100_000_000,
            stock_value=0,
        )

        monkeypatch.setattr(
            service,
            "get_context",
            lambda: (_ for _ in ()).throw(AssertionError("get_context should be skipped on duplicate snapshot")),
        )

        service.record_asset_history(current_stock_value=0)

        with original_get_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM asset_history")
            row_count = int(cursor.fetchone()[0])
        assert row_count == 0
    finally:
        _cleanup_service(service)


def test_record_asset_history_skips_noop_upsert_when_snapshot_cache_is_empty(monkeypatch):
    service = _build_service()
    try:
        fixed_now = datetime(2026, 2, 22, 9, 0, 0)
        original_get_context = service.get_context

        class _FakeDateTime:
            @classmethod
            def now(cls):
                return fixed_now

        monkeypatch.setattr(paper_trading_history_mixin, "datetime", _FakeDateTime)
        with service.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO asset_history (date, total_asset, cash, stock_value, timestamp)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET
                    total_asset = excluded.total_asset,
                    cash = excluded.cash,
                    stock_value = excluded.stock_value,
                    timestamp = excluded.timestamp
                """,
                ("2026-02-22", 100_000_000, 100_000_000, 0, "2026-02-22T09:00:00"),
            )
            conn.commit()

        if hasattr(service, "_last_asset_history_snapshot"):
            service._last_asset_history_snapshot = None

        service.record_asset_history(current_stock_value=0)

        with original_get_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT timestamp, stock_value FROM asset_history WHERE date = ?", ("2026-02-22",))
            row = cursor.fetchone()

        assert row is not None
        assert str(row[0]) == "2026-02-22T09:00:00"
        assert int(float(row[1])) == 0
    finally:
        _cleanup_service(service)


def test_paper_trading_db_keeps_only_required_history_indexes():
    service = _build_service()
    try:
        with service.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'index'
                  AND name IN (
                    'idx_trade_log_timestamp_id',
                    'idx_price_cache_updated_at'
                  )
                """
            )
            index_names = {row[0] for row in cursor.fetchall()}

        assert "idx_trade_log_timestamp_id" in index_names
        assert "idx_price_cache_updated_at" in index_names
        assert "idx_asset_history_timestamp" not in index_names
        assert "idx_trade_log_timestamp" not in index_names
        assert "idx_trade_log_ticker_timestamp" not in index_names
    finally:
        _cleanup_service(service)


def test_paper_trading_db_creates_portfolio_normalized_ticker_index():
    service = _build_service()
    try:
        with service.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT 1
                FROM sqlite_master
                WHERE type = 'index'
                  AND name = 'idx_portfolio_normalized_ticker'
                """
            )
            row = cursor.fetchone()

        assert row is not None
    finally:
        _cleanup_service(service)


def test_paper_trading_db_creates_portfolio_last_updated_index():
    service = _build_service()
    try:
        with service.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT 1
                FROM sqlite_master
                WHERE type = 'index'
                  AND name = 'idx_portfolio_last_updated'
                """
            )
            row = cursor.fetchone()

        assert row is not None
    finally:
        _cleanup_service(service)


def test_get_portfolio_tickers_uses_normalized_ticker_expression_index():
    service = _build_service()
    try:
        with service.get_context() as conn:
            cursor = conn.cursor()
            rows = [
                (
                    str(index),
                    f"종목{index}",
                    1_000,
                    1,
                    1_000,
                    "2026-01-01T00:00:00",
                )
                for index in range(1, 1300)
            ]
            rows.extend(
                [
                    ("5930", "삼성전자", 1_000, 1, 1_000, "2026-01-01T00:00:00"),
                    ("005930", "삼성전자", 1_000, 1, 1_000, "2026-01-01T00:00:00"),
                ]
            )
            cursor.executemany(
                """
                INSERT INTO portfolio (ticker, name, avg_price, quantity, total_cost, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            cursor.execute(
                """
                EXPLAIN QUERY PLAN
                SELECT DISTINCT
                    CASE
                        WHEN length(ticker) >= 6 THEN ticker
                        ELSE substr('000000' || ticker, -6)
                    END AS normalized_ticker
                FROM portfolio
                WHERE ticker IS NOT NULL
                """
            )
            plan_rows = [str(row) for row in cursor.fetchall()]
            conn.commit()

        assert any("idx_portfolio_normalized_ticker" in row for row in plan_rows)

        normalized_tickers = service._get_portfolio_tickers()
        assert normalized_tickers.count("005930") == 1
    finally:
        _cleanup_service(service)


def test_get_trade_history_orders_by_id_when_timestamp_is_identical():
    service = _build_service()
    try:
        with service.get_context() as conn:
            cursor = conn.cursor()
            rows = [
                ("BUY", "005930", "삼성전자", 1000, 1, "2026-02-22T09:00:00", 0, 0),
                ("BUY", "000660", "SK하이닉스", 2000, 1, "2026-02-22T09:00:00", 0, 0),
            ]
            cursor.executemany(
                """
                INSERT INTO trade_log (action, ticker, name, price, quantity, timestamp, profit, profit_rate)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            conn.commit()

        history = service.get_trade_history(limit=2)["trades"]
        assert len(history) == 2
        assert history[0]["ticker"] == "000660"
        assert history[1]["ticker"] == "005930"
    finally:
        _cleanup_service(service)


def test_get_context_applies_sqlite_busy_timeout():
    service = _build_service()
    try:
        with service.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA busy_timeout")
            timeout_ms = int(cursor.fetchone()[0])

        assert timeout_ms == service.SQLITE_BUSY_TIMEOUT_MS
    finally:
        _cleanup_service(service)


def test_get_context_closes_connection_after_context_exit():
    service = _build_service()
    try:
        conn = service.get_context()
        with conn as active_conn:
            active_conn.execute("SELECT 1")

        try:
            conn.execute("SELECT 1")
            assert False, "connection should be closed after context exit"
        except sqlite3.ProgrammingError:
            pass
    finally:
        _cleanup_service(service)


def test_get_read_context_applies_busy_timeout_and_read_only(monkeypatch):
    service = _build_service()
    try:
        read_only_flags: list[bool] = []
        original_connect = paper_trading_module.connect_sqlite

        def _traced_connect(*args, **kwargs):
            if "read_only" in kwargs:
                read_only_flags.append(bool(kwargs["read_only"]))
            return original_connect(*args, **kwargs)

        monkeypatch.setattr(paper_trading_module, "connect_sqlite", _traced_connect)

        with service.get_read_context() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA busy_timeout")
            timeout_ms = int(cursor.fetchone()[0])
            cursor.execute("SELECT 1")
            assert int(cursor.fetchone()[0]) == 1

        assert timeout_ms == service.SQLITE_BUSY_TIMEOUT_MS
        assert True in read_only_flags
    finally:
        _cleanup_service(service)


def test_read_methods_use_read_context_without_get_context(monkeypatch):
    service = _build_service()
    try:
        monkeypatch.setattr(
            service,
            "get_context",
            lambda: (_ for _ in ()).throw(AssertionError("get_context should not be used for read methods")),
        )
        monkeypatch.setattr(service, "record_asset_history_with_cash", lambda **_kwargs: None)
        monkeypatch.setattr(service, "record_asset_history", lambda *_args, **_kwargs: None)

        assert service._get_portfolio_tickers() == []
        assert isinstance(service.get_balance(), (int, float))

        portfolio = service.get_portfolio()
        assert isinstance(portfolio, dict)
        assert "holdings" in portfolio

        history_payload = service.get_trade_history(limit=5)
        assert isinstance(history_payload, dict)
        assert "trades" in history_payload

        asset_history = service.get_asset_history(limit=5)
        assert isinstance(asset_history, list)
        assert len(asset_history) >= 2

        valuation = service.get_portfolio_valuation()
        assert isinstance(valuation, dict)
        assert "holdings" in valuation
    finally:
        _cleanup_service(service)


def test_constructor_skips_price_cache_ensure_when_db_init_succeeds(monkeypatch):
    ensure_calls: list[bool] = []
    db_name = f"paper_trading_test_{uuid.uuid4().hex}.db"

    monkeypatch.setattr(PaperTradingService, "_init_db", lambda self: True)
    monkeypatch.setattr(PaperTradingService, "_load_price_cache_from_db", lambda self: None)

    def _fake_ensure(self, force_recheck: bool = False):
        ensure_calls.append(bool(force_recheck))
        return True

    monkeypatch.setattr(PaperTradingService, "_ensure_price_cache_table", _fake_ensure)

    service = PaperTradingService(db_name=db_name, auto_start_sync=False)
    try:
        assert service._price_cache_schema_ready is True
        assert ensure_calls == []
    finally:
        _cleanup_service(service)


def test_constructor_ensures_price_cache_when_db_init_fails(monkeypatch):
    ensure_calls: list[bool] = []
    db_name = f"paper_trading_test_{uuid.uuid4().hex}.db"

    monkeypatch.setattr(PaperTradingService, "_init_db", lambda self: False)
    monkeypatch.setattr(PaperTradingService, "_load_price_cache_from_db", lambda self: None)

    def _fake_ensure(self, force_recheck: bool = False):
        ensure_calls.append(bool(force_recheck))
        self._price_cache_schema_ready = True
        return True

    monkeypatch.setattr(PaperTradingService, "_ensure_price_cache_table", _fake_ensure)

    service = PaperTradingService(db_name=db_name, auto_start_sync=False)
    try:
        assert ensure_calls == [True]
    finally:
        _cleanup_service(service)


def test_ensure_price_cache_table_deduplicates_concurrent_initialization(monkeypatch):
    service = _build_service()
    try:
        with service._price_cache_schema_condition:
            service._price_cache_schema_ready = False
            service._price_cache_schema_init_in_progress = False

        original_get_context = service.get_context
        get_context_calls = {"count": 0}
        calls_lock = threading.Lock()
        first_entered = threading.Event()

        def _slow_counted_get_context():
            with calls_lock:
                get_context_calls["count"] += 1
                call_index = get_context_calls["count"]
            if call_index == 1:
                first_entered.set()
                time.sleep(0.05)
            return original_get_context()

        monkeypatch.setattr(service, "get_context", _slow_counted_get_context)

        first_result: list[bool] = []
        second_result: list[bool] = []

        thread_first = threading.Thread(
            target=lambda: first_result.append(service._ensure_price_cache_table())
        )
        thread_second = threading.Thread(
            target=lambda: second_result.append(service._ensure_price_cache_table())
        )

        thread_first.start()
        assert first_entered.wait(timeout=1.0)
        thread_second.start()

        thread_first.join(timeout=2.0)
        thread_second.join(timeout=2.0)

        assert thread_first.is_alive() is False
        assert thread_second.is_alive() is False
        assert first_result == [True]
        assert second_result == [True]
        assert get_context_calls["count"] == 1
    finally:
        _cleanup_service(service)


def test_load_price_cache_from_db_avoids_write_connection_when_schema_ready(monkeypatch):
    service = _build_service()
    try:
        with service.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO price_cache (ticker, price, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(ticker) DO UPDATE SET
                    price = excluded.price,
                    updated_at = excluded.updated_at
                """,
                ("005930", 70_500, "2026-02-22T00:00:00"),
            )
            conn.commit()

        with service.cache_lock:
            service.price_cache.clear()

        monkeypatch.setattr(service, "_ensure_price_cache_table", lambda *args, **kwargs: True)
        monkeypatch.setattr(
            service,
            "get_context",
            lambda: (_ for _ in ()).throw(AssertionError("load warmup should not use write context")),
        )

        service._load_price_cache_from_db()

        with service.cache_lock:
            assert service.price_cache.get("005930") == 70_500
    finally:
        _cleanup_service(service)


def test_persist_price_cache_skips_write_when_schema_ensure_fails(monkeypatch):
    service = _build_service()
    try:
        monkeypatch.setattr(service, "_ensure_price_cache_table", lambda *args, **kwargs: False)
        monkeypatch.setattr(
            service,
            "get_context",
            lambda: (_ for _ in ()).throw(AssertionError("write context should not be used")),
        )

        service._persist_price_cache({"005930": 70_500})
    finally:
        _cleanup_service(service)


def test_get_asset_history_dummy_path_does_not_call_get_balance(monkeypatch):
    service = _build_service()
    try:
        monkeypatch.setattr(
            service,
            "get_balance",
            lambda: (_ for _ in ()).throw(AssertionError("get_balance should not be called")),
        )

        history = service.get_asset_history(limit=30)

        assert len(history) >= 2
        assert "total_asset" in history[0]
    finally:
        _cleanup_service(service)


def test_get_asset_history_uses_today_single_snapshot_without_extra_queries(monkeypatch):
    service = _build_service()
    try:
        class _FakeDateTime:
            @classmethod
            def now(cls):
                return datetime(2026, 2, 22, 9, 0, 0)

        monkeypatch.setattr(paper_trading_history_mixin, "datetime", _FakeDateTime)
        with service.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO asset_history (date, total_asset, cash, stock_value, timestamp)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET
                    total_asset = excluded.total_asset,
                    cash = excluded.cash,
                    stock_value = excluded.stock_value,
                    timestamp = excluded.timestamp
                """,
                ("2026-02-22", 100_500_000, 100_000_000, 500_000, "2026-02-22T09:00:00"),
            )
            conn.commit()

        monkeypatch.setattr(
            service,
            "_calculate_stock_value_from_rows",
            lambda *_a, **_k: (_ for _ in ()).throw(
                AssertionError("portfolio fallback query path should not run")
            ),
        )

        traced_sql: list[str] = []
        original_get_read_context = service.get_read_context

        def _traced_read_context():
            conn = original_get_read_context()
            conn.set_trace_callback(lambda sql: traced_sql.append(str(sql)))
            return conn

        monkeypatch.setattr(service, "get_read_context", _traced_read_context)
        history = service.get_asset_history(limit=30)

        assert len(history) >= 2
        assert any("FROM asset_history" in sql for sql in traced_sql)
        assert not any("SELECT cash FROM balance WHERE id = 1" in sql for sql in traced_sql)
        assert not any("FROM portfolio" in sql for sql in traced_sql)
    finally:
        _cleanup_service(service)


def test_get_asset_history_low_history_fallback_uses_single_join_query(monkeypatch):
    service = _build_service()
    try:
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        with service.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO asset_history (date, total_asset, cash, stock_value, timestamp)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET
                    total_asset = excluded.total_asset,
                    cash = excluded.cash,
                    stock_value = excluded.stock_value,
                    timestamp = excluded.timestamp
                """,
                (yesterday, 100_000_000, 100_000_000, 0, f"{yesterday}T09:00:00"),
            )
            cursor.execute(
                """
                INSERT INTO portfolio (ticker, name, avg_price, quantity, total_cost, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker) DO UPDATE SET
                    name = excluded.name,
                    avg_price = excluded.avg_price,
                    quantity = excluded.quantity,
                    total_cost = excluded.total_cost,
                    last_updated = excluded.last_updated
                """,
                ("005930", "삼성전자", 70_000, 1, 70_000, f"{yesterday}T09:00:00"),
            )
            conn.commit()

        traced_sql: list[str] = []
        original_get_read_context = service.get_read_context

        def _traced_read_context():
            conn = original_get_read_context()
            conn.set_trace_callback(lambda sql: traced_sql.append(str(sql)))
            return conn

        monkeypatch.setattr(service, "get_read_context", _traced_read_context)
        history = service.get_asset_history(limit=30)

        assert len(history) >= 2
        assert any("FROM balance b" in sql for sql in traced_sql)
        assert any("SELECT COALESCE(SUM(p.quantity * p.avg_price), 0)" in sql for sql in traced_sql)
        assert not any("LEFT JOIN portfolio p ON 1 = 1" in sql for sql in traced_sql)
        assert not any("SELECT cash FROM balance WHERE id = 1" in sql for sql in traced_sql)
        assert not any("SELECT quantity, avg_price, ticker FROM portfolio" in sql for sql in traced_sql)
    finally:
        _cleanup_service(service)


def test_refresh_price_cache_once_persists_prices_to_sqlite(monkeypatch):
    service = _build_service()
    try:
        _insert_portfolio_row(service, "005930", "삼성전자")

        monkeypatch.setattr(service, "_fetch_prices_toss", lambda _session, _tickers: {"005930": 70500})
        monkeypatch.setattr(
            service,
            "_fetch_prices_naver",
            lambda *_args: (_ for _ in ()).throw(AssertionError("naver should not be called")),
        )

        sleep_seconds = service._refresh_price_cache_once(
            session=_FakeSession([]),
            yf_module=None,
            pykrx_stock=None,
        )

        assert sleep_seconds == service.UPDATE_INTERVAL_SEC
        with service.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT price FROM price_cache WHERE ticker = ?", ("005930",))
            row = cursor.fetchone()

        assert row is not None
        assert int(row[0]) == 70500
    finally:
        _cleanup_service(service)


def test_persist_price_cache_recreates_missing_table():
    service = _build_service()
    try:
        with service.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute("DROP TABLE IF EXISTS price_cache")
            conn.commit()

        service._persist_price_cache({"005930": 70500})

        with service.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT price FROM price_cache WHERE ticker = ?", ("005930",))
            row = cursor.fetchone()

        assert row is not None
        assert int(row[0]) == 70500
    finally:
        _cleanup_service(service)


def test_persist_price_cache_prunes_rows_to_configured_max(monkeypatch):
    service = _build_service()
    try:
        monkeypatch.setattr(service, "PRICE_CACHE_MAX_ROWS", 3)

        service._persist_price_cache(
            {
                "000001": 10_000,
                "000002": 10_100,
                "000003": 10_200,
            }
        )
        time.sleep(0.01)
        service._persist_price_cache(
            {
                "000004": 10_300,
                "000005": 10_400,
            }
        )

        with service.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ticker FROM price_cache")
            tickers = {str(row[0]) for row in cursor.fetchall()}
            cursor.execute("SELECT COUNT(*) FROM price_cache")
            row_count = int(cursor.fetchone()[0])

        assert row_count == 3
        assert "000004" in tickers
        assert "000005" in tickers
    finally:
        _cleanup_service(service)


def test_persist_price_cache_keeps_max_rows_on_sequential_upserts(monkeypatch):
    service = _build_service()
    try:
        monkeypatch.setattr(service, "PRICE_CACHE_MAX_ROWS", 3)
        service._persist_price_cache({"000001": 10_000, "000002": 10_100, "000003": 10_200})
        time.sleep(0.01)
        service._persist_price_cache({"000004": 10_300})

        with service.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ticker FROM price_cache")
            tickers = {str(row[0]) for row in cursor.fetchall()}
            cursor.execute("SELECT COUNT(*) FROM price_cache")
            row_count = int(cursor.fetchone()[0])

        assert row_count == 3
        assert "000004" in tickers
    finally:
        _cleanup_service(service)


def test_persist_price_cache_repeated_ticker_skips_prune_when_within_max_rows(monkeypatch):
    service = _build_service()
    try:
        service._reset_price_cache_prune_state()
        monkeypatch.setattr(service, "PRICE_CACHE_PRUNE_FORCE_INTERVAL", 10_000)
        prune_calls = {"count": 0}
        original_prune = paper_trading_module.prune_rows_by_updated_at_if_needed

        def _counted_prune(*args, **kwargs):
            prune_calls["count"] += 1
            return original_prune(*args, **kwargs)

        monkeypatch.setattr(paper_trading_module, "prune_rows_by_updated_at_if_needed", _counted_prune)

        service._persist_price_cache({"005930": 70_500})
        service._persist_price_cache({"005930": 70_600})

        assert prune_calls["count"] == 0
    finally:
        _cleanup_service(service)


def test_persist_price_cache_forces_prune_on_configured_interval(monkeypatch):
    service = _build_service()
    try:
        service._reset_price_cache_prune_state()
        monkeypatch.setattr(service, "PRICE_CACHE_PRUNE_FORCE_INTERVAL", 2)
        prune_calls = {"count": 0}
        original_prune = paper_trading_module.prune_rows_by_updated_at_if_needed

        def _counted_prune(*args, **kwargs):
            prune_calls["count"] += 1
            return original_prune(*args, **kwargs)

        monkeypatch.setattr(paper_trading_module, "prune_rows_by_updated_at_if_needed", _counted_prune)

        service._persist_price_cache({"005930": 70_500})
        service._persist_price_cache({"005930": 70_600})

        assert prune_calls["count"] == 1
    finally:
        _cleanup_service(service)


def test_refresh_price_cache_once_skips_sqlite_write_when_price_unchanged(monkeypatch):
    service = _build_service()
    try:
        _insert_portfolio_row(service, "005930", "삼성전자")
        with service.cache_lock:
            service.price_cache["005930"] = 70500

        monkeypatch.setattr(service, "_fetch_prices_toss", lambda _session, _tickers: {"005930": 70500})
        persisted_payloads: list[dict[str, int]] = []
        monkeypatch.setattr(
            service,
            "_persist_price_cache",
            lambda prices: persisted_payloads.append(dict(prices)),
        )

        sleep_seconds = service._refresh_price_cache_once(
            session=_FakeSession([]),
            yf_module=None,
            pykrx_stock=None,
        )

        assert sleep_seconds == service.UPDATE_INTERVAL_SEC
        assert persisted_payloads == []
    finally:
        _cleanup_service(service)


def test_service_warms_up_price_cache_from_sqlite_on_restart():
    db_name = f"paper_trading_test_{uuid.uuid4().hex}.db"
    first_service = PaperTradingService(db_name=db_name, auto_start_sync=False)
    second_service = None
    try:
        first_service._persist_price_cache({"005930": 70900, "000660": 123400})

        second_service = PaperTradingService(db_name=db_name, auto_start_sync=False)

        assert second_service.price_cache.get("005930") == 70900
        assert second_service.price_cache.get("000660") == 123400
    finally:
        if second_service is not None:
            _cleanup_service(second_service)
        _cleanup_service(first_service)


def test_service_warms_up_price_cache_for_active_holdings_first():
    db_name = f"paper_trading_test_{uuid.uuid4().hex}.db"
    first_service = PaperTradingService(db_name=db_name, auto_start_sync=False)
    second_service = None
    try:
        first_service._persist_price_cache({"005930": 70900, "000660": 123400})
        _insert_portfolio_row(first_service, "005930", "삼성전자")

        second_service = PaperTradingService(db_name=db_name, auto_start_sync=False)

        assert second_service.price_cache.get("005930") == 70900
        assert "000660" not in second_service.price_cache
    finally:
        if second_service is not None:
            _cleanup_service(second_service)
        _cleanup_service(first_service)


def test_service_warms_up_price_cache_for_legacy_ticker_using_normalized_lookup():
    db_name = f"paper_trading_test_{uuid.uuid4().hex}.db"
    first_service = PaperTradingService(db_name=db_name, auto_start_sync=False)
    second_service = None
    try:
        first_service._persist_price_cache({"005930": 70900})
        _insert_portfolio_row(first_service, "5930", "삼성전자")

        second_service = PaperTradingService(db_name=db_name, auto_start_sync=False)

        assert second_service.price_cache.get("005930") == 70900
    finally:
        if second_service is not None:
            _cleanup_service(second_service)
        _cleanup_service(first_service)


def test_service_warmup_uses_single_portfolio_ticker_query(monkeypatch):
    service = _build_service()
    try:
        service._persist_price_cache({"005930": 70900})
        traced_sql: list[str] = []
        original_get_read_context = service.get_read_context

        def _traced_read_context():
            conn = original_get_read_context()
            conn.set_trace_callback(traced_sql.append)
            return conn

        monkeypatch.setattr(service, "get_read_context", _traced_read_context)
        service._load_price_cache_from_db()

        portfolio_selects = [sql for sql in traced_sql if "FROM portfolio" in sql]
        assert not any("SELECT COUNT(*) FROM portfolio" in sql for sql in traced_sql)
        assert not any("SELECT 1" in sql and "FROM portfolio" in sql for sql in traced_sql)
        assert len(portfolio_selects) == 1
        assert any("SELECT ticker" in sql and "FROM portfolio" in sql for sql in traced_sql)
        assert any("LIMIT 901" in sql and "FROM portfolio" in sql for sql in traced_sql)
    finally:
        _cleanup_service(service)


def test_service_warmup_uses_in_query_without_sort_for_small_portfolio(monkeypatch):
    service = _build_service()
    try:
        service._persist_price_cache({"005930": 70900, "000660": 123400})
        _insert_portfolio_row(service, "005930", "삼성전자")
        traced_sql: list[str] = []
        original_get_read_context = service.get_read_context

        def _traced_read_context():
            conn = original_get_read_context()
            conn.set_trace_callback(traced_sql.append)
            return conn

        monkeypatch.setattr(service, "get_read_context", _traced_read_context)
        service._load_price_cache_from_db()

        in_queries = [sql for sql in traced_sql if "FROM price_cache" in sql and "WHERE ticker IN" in sql]
        assert len(in_queries) >= 1
        assert not any("ORDER BY" in sql for sql in in_queries)
        assert not any("LIMIT" in sql for sql in in_queries)
    finally:
        _cleanup_service(service)


def test_service_warmup_uses_limited_subquery_path_for_large_portfolio(monkeypatch):
    service = _build_service()
    try:
        with service.get_context() as conn:
            cursor = conn.cursor()
            portfolio_rows = [
                (
                    str(index).zfill(6),
                    f"종목{index}",
                    1000,
                    1,
                    1000,
                    "2026-01-01T00:00:00",
                )
                for index in range(1, 903)
            ]
            cursor.executemany(
                """
                INSERT INTO portfolio (ticker, name, avg_price, quantity, total_cost, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                portfolio_rows,
            )
            conn.commit()

        traced_sql: list[str] = []
        original_get_read_context = service.get_read_context

        def _traced_read_context():
            conn = original_get_read_context()
            conn.set_trace_callback(traced_sql.append)
            return conn

        monkeypatch.setattr(service, "get_read_context", _traced_read_context)
        service._load_price_cache_from_db()

        assert any("FROM portfolio" in sql and "LIMIT 901" in sql for sql in traced_sql)
        assert any(
            "FROM price_cache" in sql
            and "WHERE ticker IN" in sql
            and "FROM portfolio" in sql
            and "LIMIT 901" in sql
            and "ORDER BY last_updated DESC" in sql
            for sql in traced_sql
        )
        assert not any("INNER JOIN portfolio" in sql for sql in traced_sql)
    finally:
        _cleanup_service(service)


def test_load_price_cache_from_db_uses_read_context_when_schema_ready(monkeypatch):
    service = _build_service()
    try:
        service._persist_price_cache({"005930": 70900})
        service.price_cache.clear()
        service._price_cache_schema_ready = True

        monkeypatch.setattr(
            service,
            "get_context",
            lambda: (_ for _ in ()).throw(
                AssertionError("get_context should not be used for warmup reads when schema is ready")
            ),
        )

        service._load_price_cache_from_db()
        assert service.price_cache.get("005930") == 70900
    finally:
        _cleanup_service(service)


def test_get_portfolio_tickers_recovers_when_portfolio_table_missing():
    service = _build_service()
    try:
        with service.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute("DROP TABLE IF EXISTS portfolio")
            conn.commit()

        tickers = service._get_portfolio_tickers()
        assert tickers == []

        with service.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM portfolio")
            row_count = int(cursor.fetchone()[0])
        assert row_count == 0
    finally:
        _cleanup_service(service)


def test_get_portfolio_tickers_returns_normalized_unique_values():
    service = _build_service()
    try:
        with service.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO portfolio (ticker, name, avg_price, quantity, total_cost, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker) DO UPDATE SET
                    name = excluded.name,
                    avg_price = excluded.avg_price,
                    quantity = excluded.quantity,
                    total_cost = excluded.total_cost,
                    last_updated = excluded.last_updated
                """,
                ("5930", "삼성전자", 70_000, 1, 70_000, "2026-02-22T09:00:00"),
            )
            conn.commit()

        tickers = service._get_portfolio_tickers()
        assert tickers == ["005930"]
    finally:
        _cleanup_service(service)


def test_get_portfolio_tickers_deduplicates_raw_and_normalized_rows_in_sql():
    service = _build_service()
    try:
        with service.get_context() as conn:
            cursor = conn.cursor()
            cursor.executemany(
                """
                INSERT INTO portfolio (ticker, name, avg_price, quantity, total_cost, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    ("5930", "삼성전자", 70_000, 1, 70_000, "2026-02-22T09:00:00"),
                    ("005930", "삼성전자", 71_000, 1, 71_000, "2026-02-22T09:01:00"),
                ],
            )
            conn.commit()

        tickers = service._get_portfolio_tickers()
        assert tickers == ["005930"]
    finally:
        _cleanup_service(service)


def test_get_portfolio_tickers_uses_sql_distinct_normalization_query(monkeypatch):
    service = _build_service()
    try:
        _insert_portfolio_row(service, "5930", "삼성전자")
        traced_sql: list[str] = []
        original_get_read_context = service.get_read_context

        def _traced_read_context():
            conn = original_get_read_context()
            conn.set_trace_callback(lambda sql: traced_sql.append(str(sql)))
            return conn

        monkeypatch.setattr(service, "get_read_context", _traced_read_context)
        tickers = service._get_portfolio_tickers()

        assert tickers == ["005930"]
        assert any("SELECT DISTINCT" in sql and "FROM portfolio" in sql for sql in traced_sql)
        assert any("substr('000000' || ticker, -6)" in sql for sql in traced_sql)
    finally:
        _cleanup_service(service)


def test_buy_stock_recovers_when_trade_log_table_missing():
    service = _build_service()
    try:
        with service.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute("DROP TABLE IF EXISTS trade_log")
            conn.commit()

        result = service.buy_stock("005930", "삼성전자", 1000, 1)
        assert result["status"] == "success"

        with service.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM trade_log")
            trade_count = int(cursor.fetchone()[0])
            cursor.execute("SELECT COUNT(*) FROM portfolio WHERE ticker = ?", ("005930",))
            holding_count = int(cursor.fetchone()[0])

        assert trade_count == 1
        assert holding_count == 1
    finally:
        _cleanup_service(service)


def test_get_portfolio_recovers_when_balance_table_missing():
    service = _build_service()
    try:
        with service.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute("DROP TABLE IF EXISTS balance")
            conn.commit()

        portfolio = service.get_portfolio()
        assert isinstance(portfolio, dict)
        assert "cash" in portfolio
        assert int(portfolio["cash"]) == 100_000_000

        with service.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM balance WHERE id = 1")
            balance_rows = int(cursor.fetchone()[0])

        assert balance_rows == 1
    finally:
        _cleanup_service(service)


def test_get_asset_history_recovers_when_asset_history_table_missing():
    service = _build_service()
    try:
        with service.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute("DROP TABLE IF EXISTS asset_history")
            conn.commit()

        history = service.get_asset_history(limit=10)
        assert isinstance(history, list)
        assert len(history) >= 2

        with service.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='asset_history'"
            )
            table_row = cursor.fetchone()

        assert table_row is not None
    finally:
        _cleanup_service(service)


def test_record_asset_history_uses_single_context_without_get_balance(monkeypatch):
    service = _build_service()
    try:
        monkeypatch.setattr(
            service,
            "get_balance",
            lambda: (_ for _ in ()).throw(AssertionError("get_balance should not be called")),
        )
        monkeypatch.setattr(
            service,
            "get_read_context",
            lambda: (_ for _ in ()).throw(
                AssertionError("record_asset_history changed path should not use read context")
            ),
        )

        service.record_asset_history(current_stock_value=0)

        with service.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM asset_history")
            row = cursor.fetchone()

        assert row is not None
        assert int(row[0]) == 1
    finally:
        _cleanup_service(service)


def test_get_portfolio_valuation_prefers_record_asset_history_with_cash(monkeypatch):
    service = _build_service()
    try:
        captured: dict[str, int] = {}
        monkeypatch.setattr(
            service,
            "record_asset_history",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("record_asset_history should not be called")
            ),
        )

        def _record_with_cash(*, cash: int, current_stock_value: int):
            captured["cash"] = int(cash)
            captured["stock_value"] = int(current_stock_value)

        monkeypatch.setattr(service, "record_asset_history_with_cash", _record_with_cash)
        valuation = service.get_portfolio_valuation()

        assert captured["cash"] == int(valuation["cash"])
        assert captured["stock_value"] == int(valuation["total_stock_value"])
    finally:
        _cleanup_service(service)


def test_get_portfolio_valuation_loads_holdings_and_balance_with_single_query(monkeypatch):
    service = _build_service()
    try:
        _insert_portfolio_row(service, "005930", "삼성전자")
        traced_sql: list[str] = []
        original_get_read_context = service.get_read_context

        def _traced_read_context():
            conn = original_get_read_context()
            conn.set_trace_callback(lambda sql: traced_sql.append(str(sql)))
            return conn

        monkeypatch.setattr(service, "get_read_context", _traced_read_context)
        monkeypatch.setattr(service, "record_asset_history_with_cash", lambda **_kwargs: None)
        monkeypatch.setattr(service, "record_asset_history", lambda *_args, **_kwargs: None)

        valuation = service.get_portfolio_valuation()

        assert valuation["holdings"]
        combined_queries = [
            sql
            for sql in traced_sql
            if "FROM balance b" in sql and "LEFT JOIN portfolio p" in sql
        ]
        assert combined_queries
        assert not any(
            "SELECT cash, total_deposit FROM balance WHERE id = 1" in sql
            for sql in traced_sql
        )
    finally:
        _cleanup_service(service)


def test_get_portfolio_loads_holdings_and_balance_with_single_query(monkeypatch):
    service = _build_service()
    try:
        _insert_portfolio_row(service, "005930", "삼성전자")
        traced_sql: list[str] = []
        original_get_read_context = service.get_read_context

        def _traced_read_context():
            conn = original_get_read_context()
            conn.set_trace_callback(lambda sql: traced_sql.append(str(sql)))
            return conn

        monkeypatch.setattr(service, "get_read_context", _traced_read_context)
        portfolio = service.get_portfolio()

        assert portfolio["holdings"]
        combined_queries = [
            sql
            for sql in traced_sql
            if "FROM balance b" in sql and "LEFT JOIN portfolio p" in sql
        ]
        assert combined_queries
        assert not any(
            "SELECT cash, total_deposit FROM balance WHERE id = 1" in sql
            for sql in traced_sql
        )
    finally:
        _cleanup_service(service)


def test_reset_account_clears_price_cache_table_and_memory():
    service = _build_service()
    try:
        buy_result = service.buy_stock("005930", "삼성전자", 1000, 1)
        assert buy_result["status"] == "success"
        assert service.price_cache.get("005930") == 1000

        with service.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM price_cache")
            before_reset = int(cursor.fetchone()[0])

        assert before_reset >= 1
        assert service.reset_account() is True
        assert service.price_cache == {}

        with service.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM price_cache")
            after_reset = int(cursor.fetchone()[0])

        assert after_reset == 0
    finally:
        _cleanup_service(service)


def test_reset_account_resets_price_cache_prune_tracker_state():
    service = _build_service()
    try:
        service._persist_price_cache({"005930": 70_500})
        service._persist_price_cache({"000660": 123_400})

        with service._price_cache_prune_lock:
            assert len(service._price_cache_known_tickers) >= 2
            assert service._price_cache_save_counter >= 2

        assert service.reset_account() is True

        with service._price_cache_prune_lock:
            assert len(service._price_cache_known_tickers) == 0
            assert service._price_cache_save_counter == 0
    finally:
        _cleanup_service(service)
