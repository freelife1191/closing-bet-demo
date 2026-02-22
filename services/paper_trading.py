#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Paper Trading Service (Mock Investment)
- Manages user's virtual portfolio and trade history.
- Uses SQLite for persistence.
"""

import logging
import os
import sqlite3
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, TypeVar

from services.paper_trading_db_setup import init_db as init_db_impl
from services.paper_trading_history_mixin import PaperTradingHistoryMixin
from services.paper_trading_price_fetchers import (
    fetch_prices_naver as fetch_prices_naver_impl,
    fetch_prices_pykrx as fetch_prices_pykrx_impl,
    fetch_prices_toss as fetch_prices_toss_impl,
    fetch_prices_yfinance as fetch_prices_yfinance_impl,
)
from services.paper_trading_trade_account_mixin import PaperTradingTradeAccountMixin
from services.paper_trading_sync_service import (
    refresh_price_cache_once as refresh_price_cache_once_impl,
    run_price_update_loop as run_price_update_loop_impl,
)
from services.paper_trading_valuation_helpers import (
    build_dummy_asset_history as build_dummy_asset_history_impl,
    build_valuated_holding as build_valuated_holding_impl,
    calculate_stock_value_from_rows as calculate_stock_value_from_rows_impl,
)
from services.paper_trading_valuation_service import (
    get_portfolio_valuation as get_portfolio_valuation_impl,
)
from services.sqlite_utils import build_sqlite_pragmas, connect_sqlite

logger = logging.getLogger(__name__)
_T = TypeVar("_T")


class PaperTradingService(PaperTradingTradeAccountMixin, PaperTradingHistoryMixin):
    UPDATE_INTERVAL_SEC = 60
    EMPTY_PORTFOLIO_SLEEP_SEC = 10
    TOSS_CHUNK_SIZE = 50
    TOSS_RETRY_COUNT = 3
    NAVER_THROTTLE_SEC = 0.2
    INITIAL_SYNC_WAIT_TRIES = 50
    INITIAL_SYNC_WAIT_SEC = 0.1
    SQLITE_BUSY_TIMEOUT_MS = 30_000
    PRICE_CACHE_WARMUP_LIMIT = 5_000
    _RECOVERABLE_TABLE_NAMES = (
        "portfolio",
        "trade_log",
        "asset_history",
        "balance",
        "price_cache",
    )
    SQLITE_SESSION_PRAGMAS = build_sqlite_pragmas(
        busy_timeout_ms=SQLITE_BUSY_TIMEOUT_MS,
        include_foreign_keys=True,
        base_pragmas=("PRAGMA temp_store=MEMORY", "PRAGMA cache_size=-8000"),
    )

    def __init__(self, db_name='paper_trading.db', auto_start_sync=True):
        # Root path logic
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.db_path = os.path.join(base_dir, 'data', db_name)

        # Cache for real-time prices
        self.price_cache = {}
        self.cache_lock = threading.Lock()
        self.last_update = None
        self.is_running = False
        self.bg_thread = None
        self._initial_sync_wait_done = False
        self._price_cache_schema_ready = False

        self._price_cache_schema_ready = self._init_db()
        if not self._price_cache_schema_ready:
            self._ensure_price_cache_table(force_recheck=True)
        self._load_price_cache_from_db()

        # [Optimization] Auto-start background sync on initialization
        if auto_start_sync:
            self.start_background_sync()

    def _init_db(self, force_recheck: bool = False) -> bool:
        """Initialize SQLite database tables"""
        return bool(
            init_db_impl(
                db_path=self.db_path,
                logger=logger,
                force_recheck=force_recheck,
            )
        )

    def get_context(self):
        """Helper to get db connection"""
        timeout_seconds = max(1, self.SQLITE_BUSY_TIMEOUT_MS // 1000)
        return connect_sqlite(
            self.db_path,
            timeout_seconds=timeout_seconds,
            pragmas=self.SQLITE_SESSION_PRAGMAS,
        )

    @staticmethod
    def _is_missing_table_error(error: Exception, *, table_names: tuple[str, ...]) -> bool:
        if not isinstance(error, sqlite3.OperationalError):
            return False
        message = str(error).lower()
        if "no such table" not in message:
            return False
        return any(table_name.lower() in message for table_name in table_names)

    @classmethod
    def _is_missing_price_cache_table_error(cls, error: Exception) -> bool:
        return cls._is_missing_table_error(error, table_names=("price_cache",))

    @classmethod
    def _is_missing_paper_trading_table_error(cls, error: Exception) -> bool:
        return cls._is_missing_table_error(error, table_names=cls._RECOVERABLE_TABLE_NAMES)

    @staticmethod
    def _create_price_cache_schema(cursor: sqlite3.Cursor) -> None:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS price_cache (
                ticker TEXT PRIMARY KEY,
                price INTEGER NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_price_cache_updated_at
            ON price_cache(updated_at DESC)
            """
        )

    def _ensure_price_cache_table(self, force_recheck: bool = False) -> bool:
        if self._price_cache_schema_ready and not force_recheck:
            return True
        try:
            with self.get_context() as conn:
                cursor = conn.cursor()
                self._create_price_cache_schema(cursor)
                conn.commit()
            self._price_cache_schema_ready = True
            return True
        except Exception as error:
            self._price_cache_schema_ready = False
            logger.warning(f"Failed to ensure price cache table: {error}")
            return False

    def _recover_paper_trading_schema(self) -> bool:
        self._price_cache_schema_ready = False
        recovered = self._init_db(force_recheck=True)
        if not recovered:
            recovered = self._ensure_price_cache_table(force_recheck=True)
        if recovered:
            self._price_cache_schema_ready = True
        return recovered

    def _execute_db_operation_with_schema_retry(
        self,
        operation: Callable[[], _T],
        *,
        _retried: bool = False,
    ) -> _T:
        try:
            return operation()
        except Exception as error:
            if (not _retried) and self._is_missing_paper_trading_table_error(error):
                if self._recover_paper_trading_schema():
                    return self._execute_db_operation_with_schema_retry(
                        operation,
                        _retried=True,
                    )
            raise

    def _load_price_cache_from_db(self, *, _retried: bool = False) -> None:
        """SQLite에 저장된 최신 가격 캐시를 메모리로 워밍업한다."""
        try:
            with self.get_context() as conn:
                cursor = conn.cursor()
                if not self._price_cache_schema_ready:
                    self._create_price_cache_schema(cursor)
                    conn.commit()
                    self._price_cache_schema_ready = True
                has_holdings_row = cursor.execute(
                    """
                    SELECT 1
                    FROM portfolio
                    LIMIT 1
                    """
                ).fetchone()
                if has_holdings_row is not None:
                    cursor.execute(
                        """
                        SELECT pc.ticker, pc.price
                        FROM price_cache pc
                        INNER JOIN portfolio p ON p.ticker = pc.ticker
                        ORDER BY pc.updated_at DESC
                        LIMIT ?
                        """,
                        (self.PRICE_CACHE_WARMUP_LIMIT,),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT ticker, price
                        FROM price_cache
                        ORDER BY updated_at DESC
                        LIMIT ?
                        """,
                        (self.PRICE_CACHE_WARMUP_LIMIT,),
                    )
                rows = cursor.fetchall()
        except Exception as error:
            self._price_cache_schema_ready = False
            if (not _retried) and self._is_missing_paper_trading_table_error(error):
                if self._recover_paper_trading_schema():
                    self._load_price_cache_from_db(_retried=True)
                    return
            logger.warning(f"Failed to warm up price cache from SQLite: {error}")
            return

        warmed_cache: Dict[str, int] = {}
        for ticker, price in rows:
            ticker_key = str(ticker).zfill(6)
            try:
                price_int = int(float(price))
            except (TypeError, ValueError):
                continue
            if price_int <= 0:
                continue
            warmed_cache[ticker_key] = price_int

        if not warmed_cache:
            return

        with self.cache_lock:
            self.price_cache.update(warmed_cache)

    def _persist_price_cache(self, prices: Dict[str, int], *, _retried: bool = False) -> None:
        """가격 캐시를 SQLite에 upsert하여 재시작 시 재사용한다."""
        if not prices:
            return

        updated_at = datetime.now().isoformat()
        upsert_rows: list[tuple[str, int, str]] = []
        for ticker, price in prices.items():
            ticker_key = str(ticker).zfill(6)
            try:
                price_int = int(float(price))
            except (TypeError, ValueError):
                continue
            if price_int <= 0:
                continue
            upsert_rows.append((ticker_key, price_int, updated_at))

        if not upsert_rows:
            return

        try:
            with self.get_context() as conn:
                cursor = conn.cursor()
                if not self._price_cache_schema_ready:
                    self._create_price_cache_schema(cursor)
                    self._price_cache_schema_ready = True
                cursor.executemany(
                    """
                    INSERT INTO price_cache (ticker, price, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(ticker) DO UPDATE SET
                        price = excluded.price,
                        updated_at = excluded.updated_at
                    """,
                    upsert_rows,
                )
                conn.commit()
        except Exception as error:
            self._price_cache_schema_ready = False
            if (not _retried) and self._is_missing_paper_trading_table_error(error):
                if self._recover_paper_trading_schema():
                    self._persist_price_cache(prices, _retried=True)
                    return
            logger.warning(f"Failed to persist price cache into SQLite: {error}")

    def start_background_sync(self):
        """Start background price sync thread"""
        if self.is_running:
            return

        self.is_running = True
        self.bg_thread = threading.Thread(target=self._update_prices_loop, daemon=True)
        self.bg_thread.start()
        logger.info("PaperTrading Price Sync Started")

    def _get_portfolio_tickers(self) -> list[str]:
        with self.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ticker FROM portfolio")
            return [row[0] for row in cursor.fetchall()]

    def _fetch_prices_toss(self, session: Any, tickers: list[str]) -> Dict[str, int]:
        """Toss API에서 여러 종목 가격을 한 번에 조회한다."""
        return fetch_prices_toss_impl(
            session=session,
            tickers=tickers,
            chunk_size=self.TOSS_CHUNK_SIZE,
            retry_count=self.TOSS_RETRY_COUNT,
            logger=logger,
        )

    def _fetch_prices_naver(self, session: Any, tickers: list[str]) -> Dict[str, int]:
        """Naver API에서 개별 종목 가격을 조회한다."""
        return fetch_prices_naver_impl(
            session=session,
            tickers=tickers,
            throttle_sec=self.NAVER_THROTTLE_SEC,
            logger=logger,
        )

    def _fetch_prices_yfinance(self, yf_module: Any, tickers: list[str]) -> Dict[str, int]:
        """yfinance에서 종가를 조회한다."""
        return fetch_prices_yfinance_impl(
            yf_module=yf_module,
            tickers=tickers,
            logger=logger,
        )

    def _fetch_prices_pykrx(self, pykrx_stock: Any, tickers: list[str]) -> Dict[str, int]:
        """pykrx에서 종가를 조회한다."""
        return fetch_prices_pykrx_impl(
            pykrx_stock=pykrx_stock,
            tickers=tickers,
            logger=logger,
        )

    def _refresh_price_cache_once(
        self,
        *,
        session: Any,
        yf_module: Any,
        pykrx_stock: Any,
    ) -> int:
        """
        포트폴리오 종목의 최신 가격을 한 번 갱신한다.

        Returns:
            다음 루프까지 대기할 초(second).
        """
        tickers = self._get_portfolio_tickers()
        resolved_prices, sleep_seconds = refresh_price_cache_once_impl(
            tickers=tickers,
            session=session,
            yf_module=yf_module,
            pykrx_stock=pykrx_stock,
            fetch_prices_toss_fn=self._fetch_prices_toss,
            fetch_prices_naver_fn=self._fetch_prices_naver,
            fetch_prices_yfinance_fn=self._fetch_prices_yfinance,
            fetch_prices_pykrx_fn=self._fetch_prices_pykrx,
            update_interval_sec=self.UPDATE_INTERVAL_SEC,
            empty_portfolio_sleep_sec=self.EMPTY_PORTFOLIO_SLEEP_SEC,
            logger=logger,
        )

        changed_prices: Dict[str, int] = {}
        with self.cache_lock:
            if resolved_prices:
                changed_prices = {
                    ticker: price
                    for ticker, price in resolved_prices.items()
                    if self.price_cache.get(ticker) != price
                }
                self.price_cache.update(resolved_prices)
            self.last_update = datetime.now()

        if changed_prices:
            self._persist_price_cache(changed_prices)

        return sleep_seconds

    def _update_prices_loop(self):
        """Background loop to fetch prices"""
        run_price_update_loop_impl(
            is_running_fn=lambda: self.is_running,
            refresh_price_cache_once_fn=lambda session, yf_module, pykrx_stock: self._refresh_price_cache_once(
                session=session,
                yf_module=yf_module,
                pykrx_stock=pykrx_stock,
            ),
            update_interval_sec=self.UPDATE_INTERVAL_SEC,
            logger=logger,
        )

    def _wait_for_initial_price_sync(
        self,
        holdings: list[dict],
        current_prices: Dict[str, int],
    ) -> Dict[str, int]:
        """초기 캐시가 비어있을 때 1회만 짧게 동기화를 대기한다."""
        should_wait_for_initial_sync = (
            not current_prices
            and bool(holdings)
            and self.bg_thread is not None
            and self.bg_thread.is_alive()
            and not self._initial_sync_wait_done
        )
        if not should_wait_for_initial_sync:
            return current_prices

        logger.info("Portfolio Valuation: Waiting for initial price sync...")
        wait_started_at = time.monotonic()
        minimum_wait_seconds = 0.8
        target_tickers = {
            str(holding.get("ticker")).zfill(6)
            for holding in holdings
            if holding.get("ticker")
        }

        for _ in range(self.INITIAL_SYNC_WAIT_TRIES):
            time.sleep(self.INITIAL_SYNC_WAIT_SEC)
            with self.cache_lock:
                if not self.price_cache:
                    continue
                if target_tickers and not target_tickers.issubset(self.price_cache.keys()):
                    continue
                if (time.monotonic() - wait_started_at) < minimum_wait_seconds:
                    continue

                current_prices = self.price_cache.copy()
                break
        self._initial_sync_wait_done = True
        if current_prices:
            logger.info("Portfolio Valuation: Synced successfully waited.")
        return current_prices

    @staticmethod
    def _build_valuated_holding(
        holding: dict,
        current_prices: Dict[str, int],
    ) -> tuple[dict, int]:
        """단일 보유 종목 평가값을 계산한다."""
        return build_valuated_holding_impl(holding, current_prices)

    @staticmethod
    def _calculate_stock_value_from_rows(
        portfolio_rows: list[dict],
        current_prices: Dict[str, int],
    ) -> int:
        """포트폴리오 행 기준 현재 주식 평가금액 합계를 계산한다."""
        return calculate_stock_value_from_rows_impl(portfolio_rows, current_prices)

    @staticmethod
    def _build_dummy_asset_history(
        *,
        current_total: float,
        current_cash: float,
        current_stock_val: float,
    ) -> list[dict]:
        """차트 최소 포인트 보장을 위한 더미 히스토리 생성."""
        return build_dummy_asset_history_impl(
            current_total=current_total,
            current_cash=current_cash,
            current_stock_val=current_stock_val,
        )

    def get_portfolio_valuation(self):
        """Get portfolio with cached prices (Fast)"""
        return get_portfolio_valuation_impl(
            get_context_fn=self.get_context,
            cache_lock=self.cache_lock,
            price_cache=self.price_cache,
            wait_for_initial_price_sync_fn=self._wait_for_initial_price_sync,
            build_valuated_holding_fn=self._build_valuated_holding,
            record_asset_history_fn=self.record_asset_history,
            record_asset_history_with_cash_fn=getattr(self, "record_asset_history_with_cash", None),
            run_db_operation_with_schema_retry_fn=self._execute_db_operation_with_schema_retry,
            last_update=self.last_update,
            logger=logger,
        )


_paper_trading_instance: PaperTradingService | None = None
_paper_trading_singleton_lock = threading.Lock()


def get_paper_trading_service() -> PaperTradingService:
    """전역 PaperTradingService 싱글톤을 지연 생성한다."""
    global _paper_trading_instance
    if _paper_trading_instance is not None:
        return _paper_trading_instance

    with _paper_trading_singleton_lock:
        if _paper_trading_instance is None:
            _paper_trading_instance = PaperTradingService()
    return _paper_trading_instance


class _PaperTradingProxy:
    """기존 전역 인스턴스 호환을 위한 지연 위임 프록시."""

    def __getattr__(self, item: str):
        return getattr(get_paper_trading_service(), item)


paper_trading = _PaperTradingProxy()
