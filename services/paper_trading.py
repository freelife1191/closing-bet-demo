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
from collections import OrderedDict
from datetime import datetime
from typing import Any, Callable, Dict, TypeVar

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX 환경 방어
    fcntl = None

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
from services.sqlite_utils import (
    build_sqlite_in_placeholders,
    build_sqlite_pragmas,
    connect_sqlite,
    is_sqlite_missing_table_error,
    prune_rows_by_updated_at_if_needed,
    run_sqlite_with_retry,
)

logger = logging.getLogger(__name__)
_T = TypeVar("_T")


class PaperTradingService(PaperTradingTradeAccountMixin, PaperTradingHistoryMixin):
    UPDATE_INTERVAL_SEC = 60
    EMPTY_PORTFOLIO_SLEEP_SEC = 10
    TOSS_CHUNK_SIZE = 50
    TOSS_RETRY_COUNT = 3
    TOSS_REQUEST_TIMEOUT_SEC = 8.0
    TOSS_RETRY_BASE_DELAY_SEC = 1.0
    TOSS_RETRY_MAX_DELAY_SEC = 8.0
    NAVER_THROTTLE_SEC = 0.2
    INITIAL_SYNC_WAIT_TRIES = 50
    INITIAL_SYNC_WAIT_SEC = 0.1
    SQLITE_BUSY_TIMEOUT_MS = 30_000
    SQLITE_RETRY_ATTEMPTS = 2
    SQLITE_RETRY_DELAY_SECONDS = 0.03
    PRICE_CACHE_WARMUP_LIMIT = 5_000
    PRICE_CACHE_WARMUP_IN_QUERY_MAX_TICKERS = 900
    PRICE_CACHE_WARMUP_PORTFOLIO_SAMPLE_LIMIT = PRICE_CACHE_WARMUP_IN_QUERY_MAX_TICKERS + 1
    PRICE_CACHE_MAX_ROWS = PRICE_CACHE_WARMUP_LIMIT
    PRICE_CACHE_PRUNE_FORCE_INTERVAL = 64
    PRICE_CACHE_KNOWN_TICKERS_MAX_ENTRIES = 8_192
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
        self._price_cache_schema_lock = threading.Lock()
        self._price_cache_schema_condition = threading.Condition(self._price_cache_schema_lock)
        self._price_cache_schema_init_in_progress = False
        self._price_cache_schema_ready = False
        self._price_cache_prune_lock = threading.Lock()
        self._price_cache_known_tickers: OrderedDict[str, None] = OrderedDict()
        self._price_cache_save_counter = 0
        self._sync_loop_lock_path = os.path.join(os.path.dirname(self.db_path), "paper_trading_sync.lock")
        self._sync_loop_lock_handle: Any | None = None
        self._sync_loop_lock_owned = False

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

    def get_read_context(self):
        """조회 전용 SQLite 연결을 반환한다."""
        timeout_seconds = max(1, self.SQLITE_BUSY_TIMEOUT_MS // 1000)
        return connect_sqlite(
            self.db_path,
            timeout_seconds=timeout_seconds,
            pragmas=self.SQLITE_SESSION_PRAGMAS,
            read_only=True,
        )

    @staticmethod
    def _is_missing_table_error(error: Exception, *, table_names: tuple[str, ...]) -> bool:
        return is_sqlite_missing_table_error(error, table_names=table_names)

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
        with self._price_cache_schema_condition:
            if force_recheck:
                self._price_cache_schema_ready = False
            elif self._price_cache_schema_ready:
                return True

            while self._price_cache_schema_init_in_progress:
                self._price_cache_schema_condition.wait()
                if force_recheck:
                    self._price_cache_schema_ready = False
                    continue
                if self._price_cache_schema_ready:
                    return True

            self._price_cache_schema_init_in_progress = True

        def _ensure_schema() -> None:
            with self.get_context() as conn:
                cursor = conn.cursor()
                self._create_price_cache_schema(cursor)
                conn.commit()

        initialization_succeeded = False
        try:
            run_sqlite_with_retry(
                _ensure_schema,
                max_retries=self.SQLITE_RETRY_ATTEMPTS,
                retry_delay_seconds=self.SQLITE_RETRY_DELAY_SECONDS,
            )
            initialization_succeeded = True
            return True
        except Exception as error:
            logger.warning(f"Failed to ensure price cache table: {error}")
            return False
        finally:
            with self._price_cache_schema_condition:
                self._price_cache_schema_init_in_progress = False
                self._price_cache_schema_ready = bool(initialization_succeeded)
                self._price_cache_schema_condition.notify_all()

    def _recover_paper_trading_schema(self) -> bool:
        with self._price_cache_schema_condition:
            self._price_cache_schema_ready = False
        self._reset_price_cache_prune_state()
        recovered = self._init_db(force_recheck=True)
        if not recovered:
            recovered = self._ensure_price_cache_table(force_recheck=True)
        if recovered:
            with self._price_cache_schema_condition:
                self._price_cache_schema_ready = True
        return recovered

    def _reset_price_cache_prune_state(self) -> None:
        with self._price_cache_prune_lock:
            self._price_cache_known_tickers.clear()
            self._price_cache_save_counter = 0

    def _mark_price_cache_ticker_seen(self, ticker: str) -> bool:
        ticker_key = str(ticker).zfill(6)
        with self._price_cache_prune_lock:
            if ticker_key in self._price_cache_known_tickers:
                self._price_cache_known_tickers.move_to_end(ticker_key)
                return False

            self._price_cache_known_tickers[ticker_key] = None
            self._price_cache_known_tickers.move_to_end(ticker_key)
            normalized_max_entries = max(1, int(self.PRICE_CACHE_KNOWN_TICKERS_MAX_ENTRIES))
            while len(self._price_cache_known_tickers) > normalized_max_entries:
                self._price_cache_known_tickers.popitem(last=False)
            return True

    def _should_force_price_cache_prune(self) -> bool:
        with self._price_cache_prune_lock:
            self._price_cache_save_counter += 1
            normalized_interval = max(1, int(self.PRICE_CACHE_PRUNE_FORCE_INTERVAL))
            return (self._price_cache_save_counter % normalized_interval) == 0

    def _should_prune_price_cache_for_new_ticker(self, *, max_rows: int) -> bool:
        """신규 티커 유입 시 현재 추적 개수가 최대치 초과일 때만 prune이 필요하다."""
        normalized_max_rows = max(1, int(max_rows))
        with self._price_cache_prune_lock:
            return len(self._price_cache_known_tickers) > normalized_max_rows

    @staticmethod
    def _build_price_cache_lookup_candidates(tickers: list[str]) -> list[str]:
        """price_cache 조회용 raw/정규화 ticker 후보를 중복 없이 생성한다."""
        lookup_candidates: list[str] = []
        seen_candidates: set[str] = set()
        for ticker in tickers:
            raw_ticker = str(ticker)
            if not raw_ticker:
                continue
            normalized_ticker = raw_ticker.zfill(6)
            for candidate in (raw_ticker, normalized_ticker):
                if candidate in seen_candidates:
                    continue
                seen_candidates.add(candidate)
                lookup_candidates.append(candidate)
        return lookup_candidates

    def _execute_db_operation_with_schema_retry(
        self,
        operation: Callable[[], _T],
        *,
        _retried: bool = False,
    ) -> _T:
        try:
            return run_sqlite_with_retry(
                operation,
                max_retries=self.SQLITE_RETRY_ATTEMPTS,
                retry_delay_seconds=self.SQLITE_RETRY_DELAY_SECONDS,
            )
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
        if not self._ensure_price_cache_table():
            return

        def _load_rows() -> list[tuple[str, int]]:
            with self.get_read_context() as conn:
                cursor = conn.cursor()
                holding_rows = cursor.execute(
                    """
                    SELECT ticker
                    FROM portfolio
                    ORDER BY last_updated DESC, ticker ASC
                    LIMIT ?
                    """,
                    (self.PRICE_CACHE_WARMUP_PORTFOLIO_SAMPLE_LIMIT,),
                ).fetchall()
                if holding_rows:
                    # 포트폴리오가 큰 경우 전체 ticker를 파이썬 메모리로 가져오지 않고
                    # 곧바로 JOIN 경로를 사용해 워밍업 조회 비용을 제한한다.
                    if len(holding_rows) <= self.PRICE_CACHE_WARMUP_IN_QUERY_MAX_TICKERS:
                        holding_tickers = [
                            str(row[0])
                            for row in holding_rows
                            if row and row[0] is not None
                        ]
                        if holding_tickers:
                            # 보유 종목 수가 일반적인 범위일 때는 ticker IN 조회가 전체 조인 스캔보다 효율적이다.
                            # legacy/raw ticker와 zfill 정규화 ticker를 함께 조회해 warmup miss를 줄인다.
                            lookup_tickers = self._build_price_cache_lookup_candidates(holding_tickers)
                            if lookup_tickers:
                                rows: list[tuple[str, int]] = []
                                chunk_size = max(1, int(self.PRICE_CACHE_WARMUP_IN_QUERY_MAX_TICKERS))
                                for start in range(0, len(lookup_tickers), chunk_size):
                                    chunk = lookup_tickers[start:start + chunk_size]
                                    placeholders = build_sqlite_in_placeholders(chunk)
                                    query = f"""
                                        SELECT ticker, price
                                        FROM price_cache
                                        WHERE ticker IN ({placeholders})
                                    """
                                    cursor.execute(query, tuple(chunk))
                                    rows.extend(cursor.fetchall())
                                return rows
                            cursor.execute(
                                """
                                SELECT ticker, price
                                FROM price_cache
                                ORDER BY updated_at DESC
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
                    else:
                        cursor.execute(
                            """
                            SELECT ticker, price
                            FROM price_cache
                            WHERE ticker IN (
                                WITH sampled_portfolio AS (
                                    SELECT ticker
                                    FROM portfolio
                                    ORDER BY last_updated DESC, ticker ASC
                                    LIMIT ?
                                ),
                                lookup_tickers AS (
                                    SELECT ticker AS lookup_ticker
                                    FROM sampled_portfolio
                                    UNION ALL
                                    SELECT CASE
                                        WHEN length(ticker) >= 6 THEN ticker
                                        ELSE substr('000000' || ticker, -6)
                                    END AS lookup_ticker
                                    FROM sampled_portfolio
                                )
                                SELECT lookup_ticker
                                FROM lookup_tickers
                            )
                            """,
                            (self.PRICE_CACHE_WARMUP_PORTFOLIO_SAMPLE_LIMIT,),
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
                return cursor.fetchall()

        try:
            rows = run_sqlite_with_retry(
                _load_rows,
                max_retries=self.SQLITE_RETRY_ATTEMPTS,
                retry_delay_seconds=self.SQLITE_RETRY_DELAY_SECONDS,
            )
        except Exception as error:
            with self._price_cache_schema_condition:
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

        for warmed_ticker in warmed_cache:
            self._mark_price_cache_ticker_seen(warmed_ticker)

        with self.cache_lock:
            self.price_cache.update(warmed_cache)

    def _persist_price_cache(self, prices: Dict[str, int], *, _retried: bool = False) -> None:
        """가격 캐시를 SQLite에 upsert하여 재시작 시 재사용한다."""
        if not prices:
            return

        updated_at = datetime.now().isoformat()
        upsert_rows: list[tuple[str, int, str]] = []
        should_prune_for_new_ticker = False
        for ticker, price in prices.items():
            ticker_key = str(ticker).zfill(6)
            try:
                price_int = int(float(price))
            except (TypeError, ValueError):
                continue
            if price_int <= 0:
                continue
            upsert_rows.append((ticker_key, price_int, updated_at))
            should_prune_for_new_ticker = self._mark_price_cache_ticker_seen(ticker_key) or should_prune_for_new_ticker

        if not upsert_rows:
            return

        if not self._ensure_price_cache_table():
            return

        max_rows = max(1, int(self.PRICE_CACHE_MAX_ROWS))
        should_prune_for_new_ticker = (
            should_prune_for_new_ticker
            and self._should_prune_price_cache_for_new_ticker(max_rows=max_rows)
        )
        should_force_prune = self._should_force_price_cache_prune()
        should_prune_after_upsert = should_prune_for_new_ticker or should_force_prune

        def _upsert_rows() -> None:
            with self.get_context() as conn:
                cursor = conn.cursor()
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
                if should_prune_after_upsert:
                    prune_rows_by_updated_at_if_needed(
                        cursor,
                        table_name="price_cache",
                        max_rows=max_rows,
                    )
                conn.commit()

        try:
            run_sqlite_with_retry(
                _upsert_rows,
                max_retries=self.SQLITE_RETRY_ATTEMPTS,
                retry_delay_seconds=self.SQLITE_RETRY_DELAY_SECONDS,
            )
        except Exception as error:
            with self._price_cache_schema_condition:
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

        if not self._acquire_sync_loop_lock():
            return

        self.is_running = True
        try:
            self.bg_thread = threading.Thread(target=self._update_prices_loop, daemon=True)
            self.bg_thread.start()
            logger.info("PaperTrading Price Sync Started")
        except Exception:
            self.is_running = False
            self.bg_thread = None
            self._release_sync_loop_lock()
            raise

    def _acquire_sync_loop_lock(self) -> bool:
        """프로세스 간 가격 동기화 루프 중복 실행을 방지한다."""
        if self._sync_loop_lock_owned:
            return True
        if fcntl is None:
            return True

        os.makedirs(os.path.dirname(self._sync_loop_lock_path), exist_ok=True)
        try:
            lock_handle = open(self._sync_loop_lock_path, "a+", encoding="utf-8")
        except Exception as error:
            logger.warning(f"PaperTrading sync lock file open failed. Continue without lock: {error}")
            return True

        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            lock_handle.close()
            # 정상적인 중복 실행 방지 경로이므로 INFO 스팸을 피하기 위해 DEBUG로만 기록한다.
            logger.debug("PaperTrading Price Sync already active in another process. Skip this instance.")
            return False
        except OSError as error:
            lock_handle.close()
            logger.warning(f"PaperTrading sync lock acquisition failed. Continue without lock: {error}")
            return True

        self._sync_loop_lock_handle = lock_handle
        self._sync_loop_lock_owned = True
        return True

    def _release_sync_loop_lock(self) -> None:
        """보유 중인 프로세스 간 sync lock을 해제한다."""
        lock_handle = self._sync_loop_lock_handle
        self._sync_loop_lock_handle = None
        self._sync_loop_lock_owned = False

        if lock_handle is None or fcntl is None:
            return

        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        except Exception as error:
            logger.debug(f"PaperTrading sync lock unlock failed: {error}")

        try:
            lock_handle.close()
        except Exception as error:
            logger.debug(f"PaperTrading sync lock close failed: {error}")

    def _get_portfolio_tickers(self) -> list[str]:
        def _operation() -> list[str]:
            with self.get_read_context() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT DISTINCT
                        CASE
                            WHEN length(ticker) >= 6 THEN ticker
                            ELSE substr('000000' || ticker, -6)
                        END AS normalized_ticker
                    FROM portfolio
                    WHERE ticker IS NOT NULL
                    """
                )
                return [str(row[0]) for row in cursor.fetchall() if row and row[0] is not None]

        return self._execute_db_operation_with_schema_retry(_operation)

    def _fetch_prices_toss(self, session: Any, tickers: list[str]) -> Dict[str, int]:
        """Toss API에서 여러 종목 가격을 한 번에 조회한다."""
        return fetch_prices_toss_impl(
            session=session,
            tickers=tickers,
            chunk_size=self.TOSS_CHUNK_SIZE,
            retry_count=self.TOSS_RETRY_COUNT,
            request_timeout_sec=self.TOSS_REQUEST_TIMEOUT_SEC,
            retry_base_delay_sec=self.TOSS_RETRY_BASE_DELAY_SEC,
            retry_max_delay_sec=self.TOSS_RETRY_MAX_DELAY_SEC,
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
            tickers_already_normalized=True,
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
        try:
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
        finally:
            self.is_running = False
            self.bg_thread = None
            self._release_sync_loop_lock()

    def _wait_for_initial_price_sync(
        self,
        holdings: list[dict],
        current_prices: Dict[str, int],
    ) -> Dict[str, int]:
        """초기 캐시가 비어있을 때 짧게 동기화를 대기한다."""
        should_wait_for_initial_sync = (
            not current_prices
            and bool(holdings)
            and self.bg_thread is not None
            and self.bg_thread.is_alive()
        )
        if not should_wait_for_initial_sync:
            return current_prices

        logger.info("Portfolio Valuation: Waiting for initial price sync...")
        for _ in range(self.INITIAL_SYNC_WAIT_TRIES):
            time.sleep(self.INITIAL_SYNC_WAIT_SEC)
            with self.cache_lock:
                if self.price_cache:
                    current_prices = self.price_cache.copy()
                    break
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
            get_read_context_fn=self.get_read_context,
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
