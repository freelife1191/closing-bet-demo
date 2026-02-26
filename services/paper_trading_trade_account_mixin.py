#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Paper Trading 거래/계좌 처리 믹스인.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime

from services.paper_trading_constants import (
    DEFAULT_TRADE_HISTORY_LIMIT,
    INITIAL_CASH_KRW,
    MAX_HISTORY_LIMIT,
)
from services.sqlite_utils import prune_rows_by_updated_at_if_needed

logger = logging.getLogger(__name__)


class PaperTradingTradeAccountMixin:
    _SQLITE_SUPPORTS_RETURNING = sqlite3.sqlite_version_info >= (3, 35, 0)

    @staticmethod
    def _try_subtract_balance_with_snapshot(
        *,
        cursor: sqlite3.Cursor,
        amount: int,
    ) -> tuple[bool, int]:
        """
        잔고 차감 시도와 현재 잔고 스냅샷 조회를 최대 1개 SQL 문장으로 처리한다.

        Returns:
            (applied, cash_snapshot)
            - applied=True: 차감 성공
            - applied=False: 잔고 부족 (cash_snapshot=현재 보유 현금)
        """
        if PaperTradingTradeAccountMixin._SQLITE_SUPPORTS_RETURNING:
            try:
                cursor.execute(
                    'UPDATE balance SET cash = cash - ? WHERE id = 1 AND cash >= ? RETURNING cash',
                    (amount, amount),
                )
                row = cursor.fetchone()
                if row:
                    return True, int(row[0]) if row[0] is not None else 0
                cursor.execute('SELECT cash FROM balance WHERE id = 1')
                balance_row = cursor.fetchone()
                current_cash = int(balance_row[0]) if balance_row else 0
                return False, current_cash
            except sqlite3.OperationalError as error:
                # 일부 환경에서 RETURNING 지원이 비활성화된 경우 fallback
                if "returning" not in str(error).lower():
                    raise

        cursor.execute(
            'UPDATE balance SET cash = cash - ? WHERE id = 1 AND cash >= ?',
            (amount, amount),
        )
        if cursor.rowcount > 0:
            return True, 0

        cursor.execute('SELECT cash FROM balance WHERE id = 1')
        row = cursor.fetchone()
        current_cash = int(row[0]) if row else 0
        return False, current_cash

    @staticmethod
    def _update_balance_with_sqlite_returning(
        *,
        cursor: sqlite3.Cursor,
        amount: float,
        operation: str,
    ) -> float:
        """SQLite RETURNING을 우선 사용해 잔고 갱신 후 값을 즉시 반환한다."""
        if operation == 'subtract':
            returning_sql = 'UPDATE balance SET cash = cash - ? WHERE id = 1 RETURNING cash'
            fallback_sql = 'UPDATE balance SET cash = cash - ? WHERE id = 1'
        else:
            returning_sql = 'UPDATE balance SET cash = cash + ? WHERE id = 1 RETURNING cash'
            fallback_sql = 'UPDATE balance SET cash = cash + ? WHERE id = 1'

        if PaperTradingTradeAccountMixin._SQLITE_SUPPORTS_RETURNING:
            try:
                cursor.execute(returning_sql, (amount,))
                row = cursor.fetchone()
                return row[0] if row else 0
            except sqlite3.OperationalError as error:
                # SQLite 3.35 미만/RETURNING 비지원 build fallback
                if "returning" not in str(error).lower():
                    raise

        cursor.execute(fallback_sql, (amount,))
        cursor.execute('SELECT cash FROM balance WHERE id = 1')
        row = cursor.fetchone()
        return row[0] if row else 0

    def _persist_price_cache_with_cursor(
        self,
        *,
        cursor: sqlite3.Cursor,
        prices: dict[str, int],
        updated_at: str | None = None,
    ) -> None:
        """
        기존 거래 트랜잭션 안에서 price_cache를 함께 upsert한다.

        buy/sell 후 별도 write 트랜잭션을 열지 않아도 되어 SQLite write 락 경합을 줄인다.
        """
        if not prices:
            return

        row_timestamp = str(updated_at) if updated_at is not None else datetime.now().isoformat()
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

            upsert_rows.append((ticker_key, price_int, row_timestamp))
            should_prune_for_new_ticker = (
                self._mark_price_cache_ticker_seen(ticker_key) or should_prune_for_new_ticker
            )

        if not upsert_rows:
            return

        max_rows = max(1, int(getattr(self, "PRICE_CACHE_MAX_ROWS", len(upsert_rows))))
        should_prune_for_new_ticker = (
            should_prune_for_new_ticker
            and self._should_prune_price_cache_for_new_ticker(max_rows=max_rows)
        )
        should_force_prune = self._should_force_price_cache_prune()
        should_prune_after_upsert = should_prune_for_new_ticker or should_force_prune

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

    @staticmethod
    def _normalize_trade_history_limit(limit: object, *, default: int) -> int:
        try:
            parsed = int(float(limit))
        except (TypeError, ValueError):
            parsed = int(default)
        return min(max(parsed, 1), int(MAX_HISTORY_LIMIT))

    @staticmethod
    def _normalize_ticker(ticker: str) -> str:
        return str(ticker).zfill(6)

    @classmethod
    def _ticker_lookup_candidates(cls, ticker: str) -> tuple[str, ...]:
        raw_ticker = str(ticker).strip()
        normalized_ticker = cls._normalize_ticker(raw_ticker)
        if normalized_ticker == raw_ticker:
            return (raw_ticker,)
        return (raw_ticker, normalized_ticker)

    @classmethod
    def _select_portfolio_position_by_ticker(
        cls,
        *,
        cursor: sqlite3.Cursor,
        ticker: str,
    ):
        lookup_candidates = cls._ticker_lookup_candidates(ticker)
        if len(lookup_candidates) == 1:
            candidate = lookup_candidates[0]
            cursor.execute(
                """
                SELECT ticker, name, avg_price, quantity, total_cost
                FROM portfolio
                WHERE ticker = ?
                LIMIT 1
                """,
                (candidate,),
            )
            return cursor.fetchone()

        first_candidate, second_candidate = lookup_candidates[0], lookup_candidates[1]
        cursor.execute(
            """
            SELECT ticker, name, avg_price, quantity, total_cost
            FROM portfolio
            WHERE ticker IN (?, ?)
            ORDER BY CASE ticker
                WHEN ? THEN 0
                WHEN ? THEN 1
                ELSE 2
            END
            LIMIT 1
            """,
            (
                first_candidate,
                second_candidate,
                first_candidate,
                second_candidate,
            ),
        )
        return cursor.fetchone()

    @classmethod
    def _load_portfolio_positions_map_for_tickers(
        cls,
        *,
        cursor: sqlite3.Cursor,
        tickers: list[str],
    ) -> dict[str, tuple]:
        lookup_candidates: set[str] = set()
        for ticker in tickers:
            for candidate in cls._ticker_lookup_candidates(ticker):
                lookup_candidates.add(candidate)

        if not lookup_candidates:
            return {}

        ordered_candidates = sorted(lookup_candidates)
        # SQLite 바인딩 변수 한도(기본 999)를 넘지 않도록 청크 조회한다.
        chunk_size = 900
        positions_map: dict[str, tuple] = {}

        for start in range(0, len(ordered_candidates), chunk_size):
            chunk = ordered_candidates[start:start + chunk_size]
            placeholders = ", ".join("?" for _ in chunk)
            cursor.execute(
                f"""
                SELECT ticker, name, avg_price, quantity, total_cost
                FROM portfolio
                WHERE ticker IN ({placeholders})
                """,
                tuple(chunk),
            )
            rows = cursor.fetchall()
            for row in rows:
                positions_map[str(row[0])] = row

        return positions_map

    @classmethod
    def _select_portfolio_position_from_map(
        cls,
        *,
        portfolio_positions_map: dict[str, tuple],
        ticker: str,
    ):
        for candidate in cls._ticker_lookup_candidates(ticker):
            row = portfolio_positions_map.get(candidate)
            if row:
                return row
        return None

    @staticmethod
    def _normalize_buy_price(raw_price: object) -> float | None:
        try:
            execution_price = float(raw_price)
        except (TypeError, ValueError):
            return None
        if execution_price <= 0:
            return None
        return execution_price

    @staticmethod
    def _normalize_buy_quantity(raw_quantity: object) -> int | None:
        try:
            quantity = int(float(raw_quantity))
        except (TypeError, ValueError):
            return None
        if quantity <= 0:
            return None
        return quantity

    @staticmethod
    def _build_buy_trade_log_row(
        *,
        ticker: str,
        name: str,
        execution_price: float,
        quantity: int,
        timestamp: str | None = None,
    ) -> tuple[str, str, str, float, int, str, float, float]:
        return (
            "BUY",
            str(ticker),
            str(name),
            float(execution_price),
            int(quantity),
            str(timestamp) if timestamp is not None else datetime.now().isoformat(),
            0.0,
            0.0,
        )

    @classmethod
    def _apply_buy_order_to_db(
        cls,
        *,
        cursor: sqlite3.Cursor,
        ticker: str,
        name: str,
        execution_price: float,
        quantity: int,
        total_cost: int,
    ) -> None:
        ticker_key = str(ticker)
        timestamp = datetime.now().isoformat()
        cursor.execute(
            """
            INSERT INTO portfolio (ticker, name, avg_price, quantity, total_cost, last_updated)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET
                name = excluded.name,
                quantity = portfolio.quantity + excluded.quantity,
                total_cost = portfolio.total_cost + excluded.total_cost,
                avg_price = (portfolio.total_cost + excluded.total_cost) / (portfolio.quantity + excluded.quantity),
                last_updated = excluded.last_updated
            """,
            (ticker_key, name, execution_price, quantity, total_cost, timestamp),
        )

        trade_log_row = cls._build_buy_trade_log_row(
            ticker=ticker_key,
            name=name,
            execution_price=execution_price,
            quantity=quantity,
            timestamp=timestamp,
        )
        cursor.execute(
            """
            INSERT INTO trade_log (action, ticker, name, price, quantity, timestamp, profit, profit_rate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            trade_log_row,
        )

    @classmethod
    def _apply_aggregated_buy_orders_to_portfolio(
        cls,
        *,
        cursor: sqlite3.Cursor,
        aggregated_orders_by_ticker: dict[str, dict[str, int | str]],
        timestamp: str | None = None,
    ) -> None:
        if not aggregated_orders_by_ticker:
            return

        batch_timestamp = str(timestamp) if timestamp is not None else datetime.now().isoformat()
        upsert_rows: list[tuple[str, str, float, int, int, str]] = []

        for ticker_key, aggregate in aggregated_orders_by_ticker.items():
            name = str(aggregate["name"])
            quantity = int(aggregate["quantity"])
            total_cost = int(aggregate["total_cost"])
            if quantity <= 0 or total_cost <= 0:
                continue

            avg_price = float(total_cost) / float(quantity)
            upsert_rows.append((ticker_key, name, avg_price, quantity, total_cost, batch_timestamp))

        if not upsert_rows:
            return

        cursor.executemany(
            """
            INSERT INTO portfolio (ticker, name, avg_price, quantity, total_cost, last_updated)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET
                name = excluded.name,
                quantity = portfolio.quantity + excluded.quantity,
                total_cost = portfolio.total_cost + excluded.total_cost,
                avg_price = (portfolio.total_cost + excluded.total_cost) / (portfolio.quantity + excluded.quantity),
                last_updated = excluded.last_updated
            """,
            upsert_rows,
        )

    def get_balance(self):
        """Get current cash balance"""
        def _operation():
            with self.get_read_context() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT cash FROM balance WHERE id = 1')
                row = cursor.fetchone()
                return row[0] if row else 0

        return self._execute_db_operation_with_schema_retry(_operation)

    def deposit_cash(self, amount):
        """Deposit cash (Charging)"""
        if amount <= 0:
            return {'status': 'error', 'message': 'Amount must be positive'}

        try:
            def _operation():
                with self.get_context() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        'UPDATE balance SET cash = cash + ?, total_deposit = total_deposit + ? WHERE id = 1',
                        (amount, amount),
                    )
                    conn.commit()
                return {'status': 'success', 'message': f'Deposited {amount:,} KRW'}

            return self._execute_db_operation_with_schema_retry(_operation)
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    def update_balance(self, amount, operation='add'):
        """Update cash balance"""
        def _operation():
            with self.get_context() as conn:
                cursor = conn.cursor()
                new_cash = self._update_balance_with_sqlite_returning(
                    cursor=cursor,
                    amount=amount,
                    operation=operation,
                )
                conn.commit()
                return new_cash

        return self._execute_db_operation_with_schema_retry(_operation)

    def buy_stock(self, ticker, name, price, quantity):
        """Execute Buy Order"""
        normalized_quantity = self._normalize_buy_quantity(quantity)
        if normalized_quantity is None:
            return {'status': 'error', 'message': 'Quantity must be positive'}

        execution_price = self._normalize_buy_price(price)
        if execution_price is None:
            return {'status': 'error', 'message': 'Price must be a positive number'}

        # [User Request] Trust Client Price
        # 사용자가 보고 매수한 가격(프론트엔드 가격)을 그대로 체결 가격으로 사용합니다.
        # 서버에서 다시 조회하면 소스/시간 차이로 가격이 달라져 혼란을 줄 수 있음.
        ticker_key = str(ticker)
        # main 동작과 동일하게 체결 시도 시점에 즉시 캐시를 반영한다.
        with self.cache_lock:
            self.price_cache[ticker_key] = int(execution_price)
            self.last_update = datetime.now()

        total_cost = int(execution_price * normalized_quantity)  # 정수로 처리

        try:
            def _operation():
                with self.get_context() as conn:
                    cursor = conn.cursor()
                    if total_cost <= 0:
                        return {
                            'status': 'error',
                            'message': 'Price must be a positive number',
                        }

                    balance_updated, current_cash = self._try_subtract_balance_with_snapshot(
                        cursor=cursor,
                        amount=total_cost,
                    )
                    if not balance_updated:
                        return {
                            'status': 'error',
                            'message': f'잔고 부족 (필요: {total_cost:,}원, 보유: {int(current_cash):,}원)',
                        }

                    self._apply_buy_order_to_db(
                        cursor=cursor,
                        ticker=ticker_key,
                        name=name,
                        execution_price=execution_price,
                        quantity=normalized_quantity,
                        total_cost=total_cost,
                    )
                    self._persist_price_cache_with_cursor(
                        cursor=cursor,
                        prices={ticker_key: int(execution_price)},
                    )
                    conn.commit()
                return {'status': 'success', 'message': f'{name} {normalized_quantity}주 매수 완료'}

            result = self._execute_db_operation_with_schema_retry(_operation)
            return result

        except Exception as e:
            logger.error(f"Buy failed: {e}")
            return {'status': 'error', 'message': str(e)}

    def buy_stocks_bulk(self, orders):
        """여러 종목 매수를 단일 SQLite 트랜잭션으로 처리한다."""
        if not isinstance(orders, list) or not orders:
            return {
                "status": "error",
                "message": "No orders provided",
                "summary": {"total": 0, "success": 0, "failed": 0},
                "results": [],
            }

        normalized_orders: list[dict[str, object]] = []
        pre_validation_results: list[dict[str, str]] = []
        pending_cache_updates: dict[str, int] = {}

        for item in orders:
            if not isinstance(item, dict):
                pre_validation_results.append(
                    {
                        "ticker": "",
                        "name": "",
                        "status": "error",
                        "message": "Invalid order payload",
                    }
                )
                continue

            ticker = str(item.get("ticker", "")).strip()
            name = str(item.get("name", "")).strip()
            execution_price = self._normalize_buy_price(item.get("price"))
            quantity = self._normalize_buy_quantity(item.get("quantity"))

            if not ticker or not name or execution_price is None or quantity is None:
                pre_validation_results.append(
                    {
                        "ticker": ticker,
                        "name": name,
                        "status": "error",
                        "message": "Missing or invalid order fields",
                    }
                )
                continue

            ticker_key = str(ticker)
            pending_cache_updates[ticker_key] = int(execution_price)

            total_cost = int(execution_price * quantity)
            if total_cost <= 0:
                pre_validation_results.append(
                    {
                        "ticker": ticker_key,
                        "name": name,
                        "status": "error",
                        "message": "Price must be a positive number",
                    }
                )
                continue

            normalized_orders.append(
                {
                    "ticker": ticker_key,
                    "name": name,
                    "price": execution_price,
                    "quantity": quantity,
                    "total_cost": total_cost,
                }
            )

        # 주문 1건 단일 케이스는 buy_stock 경로를 재사용해
        # read/write 컨텍스트 왕복을 줄이고 SQLite 트랜잭션 수를 최소화한다.
        if len(normalized_orders) == 1 and not pre_validation_results:
            only_order = normalized_orders[0]
            single_result = self.buy_stock(
                only_order["ticker"],
                only_order["name"],
                only_order["price"],
                only_order["quantity"],
            )
            result_status = str(single_result.get("status", "error"))
            result_message = str(single_result.get("message", "Unknown error"))
            result_row = {
                "ticker": str(only_order["ticker"]),
                "name": str(only_order["name"]),
                "status": result_status,
                "message": result_message,
            }
            success_count = 1 if result_status == "success" else 0
            failed_count = 1 - success_count
            summary_message = "일괄 매수 완료 (성공 1건, 실패 0건)"
            if success_count == 0:
                summary_message = "일괄 매수 실패 (성공 0건, 실패 1건)"
            return {
                "status": "success" if success_count > 0 else "error",
                "message": summary_message,
                "summary": {
                    "total": 1,
                    "success": success_count,
                    "failed": failed_count,
                },
                "results": [result_row],
            }

        if pending_cache_updates:
            with self.cache_lock:
                self.price_cache.update(pending_cache_updates)
                self.last_update = datetime.now()

        db_results: list[dict[str, str]] = []

        if normalized_orders:
            try:
                def _operation():
                    local_results: list[dict[str, str]] = []
                    aggregated_orders_by_ticker: dict[str, dict[str, int | str]] = {}
                    pending_trade_log_rows: list[tuple[str, str, str, float, int, str, float, float]] = []
                    successful_prices: dict[str, int] = {}
                    with self.get_read_context() as read_conn:
                        read_cursor = read_conn.cursor()
                        read_cursor.execute("SELECT cash FROM balance WHERE id = 1")
                        balance_row = read_cursor.fetchone()
                        current_cash = int(balance_row[0]) if balance_row else 0

                    initial_cash = current_cash
                    batch_timestamp = datetime.now().isoformat()

                    for order in normalized_orders:
                        ticker_key = str(order["ticker"])
                        name = str(order["name"])
                        execution_price = float(order["price"])
                        quantity = int(order["quantity"])
                        total_cost = int(order["total_cost"])

                        if current_cash < total_cost:
                            local_results.append(
                                {
                                    "ticker": ticker_key,
                                    "name": name,
                                    "status": "error",
                                    "message": f"잔고 부족 (필요: {total_cost:,}원, 보유: {int(current_cash):,}원)",
                                }
                            )
                            continue

                        current_cash -= total_cost
                        successful_prices[ticker_key] = int(execution_price)
                        local_results.append(
                            {
                                "ticker": ticker_key,
                                "name": name,
                                "status": "success",
                                "message": f"{name} {quantity}주 매수 완료",
                            }
                        )

                        aggregate_row = aggregated_orders_by_ticker.setdefault(
                            ticker_key,
                            {"name": name, "quantity": 0, "total_cost": 0},
                        )
                        aggregate_row["name"] = name
                        aggregate_row["quantity"] = int(aggregate_row["quantity"]) + quantity
                        aggregate_row["total_cost"] = int(aggregate_row["total_cost"]) + total_cost

                        pending_trade_log_rows.append(
                            self._build_buy_trade_log_row(
                                ticker=ticker_key,
                                name=name,
                                execution_price=execution_price,
                                quantity=quantity,
                                timestamp=batch_timestamp,
                            )
                        )

                    if not aggregated_orders_by_ticker:
                        return local_results

                    with self.get_context() as conn:
                        cursor = conn.cursor()
                        spent_cash = initial_cash - current_cash
                        if spent_cash > 0:
                            cursor.execute(
                                "UPDATE balance SET cash = cash - ? WHERE id = 1 AND cash >= ?",
                                (spent_cash, spent_cash),
                            )
                            if cursor.rowcount == 0:
                                raise RuntimeError("잔고 동기화 충돌이 발생했습니다. 잠시 후 다시 시도해 주세요.")

                        self._apply_aggregated_buy_orders_to_portfolio(
                            cursor=cursor,
                            aggregated_orders_by_ticker=aggregated_orders_by_ticker,
                            timestamp=batch_timestamp,
                        )

                        if pending_trade_log_rows:
                            cursor.executemany(
                                """
                                INSERT INTO trade_log (action, ticker, name, price, quantity, timestamp, profit, profit_rate)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                pending_trade_log_rows,
                            )
                        if successful_prices:
                            self._persist_price_cache_with_cursor(
                                cursor=cursor,
                                prices=successful_prices,
                                updated_at=batch_timestamp,
                            )
                        conn.commit()
                    return local_results

                operation_result = self._execute_db_operation_with_schema_retry(_operation)
                db_results = operation_result
            except Exception as error:
                logger.error(f"Bulk buy failed: {error}")
                failed_orders = [
                    {
                        "ticker": str(item.get("ticker", "")),
                        "name": str(item.get("name", "")),
                        "status": "error",
                        "message": str(error),
                    }
                    for item in normalized_orders
                ]
                merged_results = [*pre_validation_results, *failed_orders]
                return {
                    "status": "error",
                    "message": str(error),
                    "summary": {
                        "total": len(merged_results),
                        "success": 0,
                        "failed": len(merged_results),
                    },
                    "results": merged_results,
                }

        merged_results = [*pre_validation_results, *db_results]
        success_count = sum(1 for item in merged_results if item.get("status") == "success")
        failed_count = sum(1 for item in merged_results if item.get("status") != "success")
        total_count = len(merged_results)

        status = "success" if success_count > 0 else "error"
        summary_message = f"일괄 매수 완료 (성공 {success_count}건, 실패 {failed_count}건)"
        if success_count == 0 and total_count > 0:
            summary_message = f"일괄 매수 실패 (성공 0건, 실패 {failed_count}건)"

        return {
            "status": status,
            "message": summary_message,
            "summary": {
                "total": total_count,
                "success": success_count,
                "failed": failed_count,
            },
            "results": merged_results,
        }

    def sell_stock(self, ticker, price, quantity):
        """Execute Sell Order"""
        if quantity <= 0:
            return {'status': 'error', 'message': 'Quantity must be positive'}

        try:
            try:
                execution_price = float(price)
            except (TypeError, ValueError):
                return {'status': 'error', 'message': 'Price must be a positive number'}
            if execution_price <= 0:
                return {'status': 'error', 'message': 'Price must be a positive number'}
            # [User Request] Trust Client Price
            ticker_key = str(ticker)

            def _operation():
                with self.get_context() as conn:
                    cursor = conn.cursor()

                    # 1. Check Portfolio
                    row = self._select_portfolio_position_by_ticker(
                        cursor=cursor,
                        ticker=ticker,
                    )

                    if not row or row[3] < quantity:
                        return {'status': 'error', 'message': 'Not enough shares to sell'}

                    db_ticker, name, avg_price, current_qty, _current_total_cost = row
                    # main 동작과 동일하게 실제 매도 처리 직전에 캐시를 즉시 반영한다.
                    with self.cache_lock:
                        self.price_cache[ticker_key] = int(execution_price)
                        self.last_update = datetime.now()

                    # 2. Update/Remove Portfolio
                    remaining_qty = current_qty - quantity

                    if remaining_qty == 0:
                        cursor.execute('DELETE FROM portfolio WHERE ticker = ?', (db_ticker,))
                    else:
                        new_total_cost = avg_price * remaining_qty
                        cursor.execute(
                            '''
                            UPDATE portfolio
                            SET quantity = ?, total_cost = ?, last_updated = ?
                            WHERE ticker = ?
                        ''',
                            (remaining_qty, new_total_cost, datetime.now().isoformat(), db_ticker),
                        )

                    # 3. Calculate Profit & Log Trade
                    total_proceeds = int(execution_price * quantity)
                    cost_basis = int(avg_price * quantity)
                    profit = total_proceeds - cost_basis
                    profit_rate = (profit / cost_basis * 100) if cost_basis > 0 else 0

                    cursor.execute(
                        '''
                        INSERT INTO trade_log (action, ticker, name, price, quantity, timestamp, profit, profit_rate)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''',
                        (
                            'SELL',
                            ticker_key,
                            name,
                            execution_price,
                            quantity,
                            datetime.now().isoformat(),
                            profit,
                            profit_rate,
                        ),
                    )

                    # 4. Add Cash
                    cursor.execute('UPDATE balance SET cash = cash + ? WHERE id = 1', (total_proceeds,))
                    self._persist_price_cache_with_cursor(
                        cursor=cursor,
                        prices={ticker_key: int(execution_price)},
                    )

                    conn.commit()
                return {'status': 'success', 'message': f'{name} {quantity}주 매도 완료'}

            result = self._execute_db_operation_with_schema_retry(_operation)
            return result

        except Exception as e:
            logger.error(f"Sell failed: {e}")
            return {'status': 'error', 'message': str(e)}

    def get_portfolio(self):
        """Get all holdings"""
        def _operation():
            with self.get_read_context() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    '''
                    SELECT
                        p.ticker,
                        p.name,
                        p.avg_price,
                        p.quantity,
                        p.total_cost,
                        p.last_updated,
                        b.cash AS cash,
                        b.total_deposit AS total_deposit
                    FROM balance b
                    LEFT JOIN portfolio p ON 1 = 1
                    WHERE b.id = 1
                    '''
                )
                rows = cursor.fetchall()
                if rows:
                    first_row = rows[0]
                    cash = first_row[6] if first_row[6] is not None else 0
                    total_deposit = first_row[7] if first_row[7] is not None else 0
                else:
                    cash = 0
                    total_deposit = 0

                holdings = [
                    {
                        'ticker': row[0],
                        'name': row[1],
                        'avg_price': row[2],
                        'quantity': row[3],
                        'total_cost': row[4],
                        'last_updated': row[5],
                    }
                    for row in rows
                    if row[0] is not None
                ]

                # Initial Principal is 100,000,000. Total Principal = 100M + Deposits
                total_principal = INITIAL_CASH_KRW + total_deposit

                return {
                    'holdings': holdings,
                    'cash': cash,
                    'total_asset_value': cash,  # Will need to add holdings value in API layer
                    'total_principal': total_principal,
                }

        return self._execute_db_operation_with_schema_retry(_operation)

    def reset_account(self):
        """Reset everything to default"""
        try:
            def _operation():
                with self.get_context() as conn:
                    cursor = conn.cursor()
                    cursor.execute('DELETE FROM portfolio')
                    cursor.execute('DELETE FROM trade_log')
                    cursor.execute('DELETE FROM asset_history')  # 히스토리도 초기화
                    cursor.execute('DELETE FROM price_cache')
                    cursor.execute(
                        'UPDATE balance SET cash = ?, total_deposit = 0 WHERE id = 1',
                        (INITIAL_CASH_KRW,),
                    )
                    conn.commit()
                return True

            self._execute_db_operation_with_schema_retry(_operation)
            with self.cache_lock:
                self.price_cache.clear()
                self.last_update = None
            if hasattr(self, "_reset_price_cache_prune_state"):
                self._reset_price_cache_prune_state()
            if hasattr(self, "_last_asset_history_snapshot"):
                self._last_asset_history_snapshot = None
            return True
        except Exception as error:
            logger.error(f"Failed to reset paper trading account: {error}")
            return False

    def get_trade_history(self, limit=DEFAULT_TRADE_HISTORY_LIMIT):
        """Get trade history"""
        normalized_limit = self._normalize_trade_history_limit(
            limit,
            default=DEFAULT_TRADE_HISTORY_LIMIT,
        )

        def _operation():
            with self.get_read_context() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    SELECT id, action, ticker, name, price, quantity, timestamp, profit, profit_rate
                    FROM trade_log
                    ORDER BY timestamp DESC, id DESC
                    LIMIT ?
                ''',
                    (normalized_limit,),
                )
                trades = [
                    {
                        'id': row[0],
                        'action': row[1],
                        'ticker': row[2],
                        'name': row[3],
                        'price': row[4],
                        'quantity': row[5],
                        'timestamp': row[6],
                        'profit': row[7],
                        'profit_rate': row[8],
                    }
                    for row in cursor.fetchall()
                ]
                return {'trades': trades}

        return self._execute_db_operation_with_schema_retry(_operation)
