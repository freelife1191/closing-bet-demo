#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PaperTradingService 단위 테스트
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from services.paper_trading import PaperTradingService
import services.paper_trading_history_mixin as paper_trading_history_mixin


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


def test_get_portfolio_valuation_waits_only_once_for_initial_sync(monkeypatch):
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
        assert sleep_calls["count"] == service.INITIAL_SYNC_WAIT_TRIES
        assert service._initial_sync_wait_done is True
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


def test_paper_trading_db_has_indexes_for_history_queries():
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
                    'idx_trade_log_timestamp',
                    'idx_trade_log_ticker_timestamp',
                    'idx_asset_history_timestamp',
                    'idx_price_cache_updated_at'
                  )
                """
            )
            index_names = {row[0] for row in cursor.fetchall()}

        assert "idx_trade_log_timestamp" in index_names
        assert "idx_trade_log_ticker_timestamp" in index_names
        assert "idx_asset_history_timestamp" in index_names
        assert "idx_price_cache_updated_at" in index_names
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


def test_record_asset_history_uses_single_context_without_get_balance(monkeypatch):
    service = _build_service()
    try:
        monkeypatch.setattr(
            service,
            "get_balance",
            lambda: (_ for _ in ()).throw(AssertionError("get_balance should not be called")),
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
