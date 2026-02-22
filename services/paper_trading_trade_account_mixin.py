#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Paper Trading 거래/계좌 처리 믹스인.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime

logger = logging.getLogger(__name__)


class PaperTradingTradeAccountMixin:
    @staticmethod
    def _normalize_ticker(ticker: str) -> str:
        return str(ticker).zfill(6)

    @classmethod
    def _ticker_lookup_candidates(cls, ticker: str) -> tuple[str, ...]:
        normalized_ticker = cls._normalize_ticker(ticker)
        raw_ticker = str(ticker)
        candidates: list[str] = [normalized_ticker]
        if raw_ticker and raw_ticker not in candidates:
            candidates.append(raw_ticker)

        unpadded_ticker = normalized_ticker.lstrip("0")
        if unpadded_ticker and unpadded_ticker not in candidates:
            candidates.append(unpadded_ticker)
        return tuple(candidates)

    @classmethod
    def _select_portfolio_position_by_ticker(
        cls,
        *,
        cursor: sqlite3.Cursor,
        ticker: str,
    ):
        lookup_candidates = cls._ticker_lookup_candidates(ticker)
        if len(lookup_candidates) == 1:
            cursor.execute(
                """
                SELECT ticker, name, avg_price, quantity, total_cost
                FROM portfolio
                WHERE ticker = ?
                LIMIT 1
                """,
                (lookup_candidates[0],),
            )
        else:
            placeholders = ", ".join("?" for _ in lookup_candidates)
            case_clauses = " ".join(
                f"WHEN ? THEN {rank}"
                for rank, _candidate in enumerate(lookup_candidates)
            )
            cursor.execute(
                f"""
                SELECT ticker, name, avg_price, quantity, total_cost
                FROM portfolio 
                WHERE ticker IN ({placeholders})
                ORDER BY CASE ticker
                    {case_clauses}
                    ELSE {len(lookup_candidates)}
                END
                LIMIT 1
                """,
                (*lookup_candidates, *lookup_candidates),
            )
        return cursor.fetchone()

    def get_balance(self):
        """Get current cash balance"""
        def _operation():
            with self.get_context() as conn:
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
                cursor.execute('SELECT cash FROM balance WHERE id = 1')
                row = cursor.fetchone()
                current = row[0] if row else 0
                if operation == 'subtract':
                    new_balance = current - amount
                else:
                    new_balance = current + amount

                cursor.execute('UPDATE balance SET cash = ? WHERE id = 1', (new_balance,))
                conn.commit()
                return new_balance

        return self._execute_db_operation_with_schema_retry(_operation)

    def buy_stock(self, ticker, name, price, quantity):
        """Execute Buy Order"""
        if quantity <= 0:
            return {'status': 'error', 'message': 'Quantity must be positive'}

        # [User Request] Trust Client Price
        # 사용자가 보고 매수한 가격(프론트엔드 가격)을 그대로 체결 가격으로 사용합니다.
        # 서버에서 다시 조회하면 소스/시간 차이로 가격이 달라져 혼란을 줄 수 있음.
        execution_price = price

        ticker_key = self._normalize_ticker(ticker)

        total_cost = int(execution_price * quantity)  # 정수로 처리

        try:
            def _operation():
                with self.get_context() as conn:
                    cursor = conn.cursor()

                    cursor.execute('SELECT cash FROM balance WHERE id = 1')
                    balance_row = cursor.fetchone()
                    current_cash = balance_row[0] if balance_row else 0
                    if current_cash < total_cost:
                        return {
                            'status': 'error',
                            'message': f'잔고 부족 (필요: {total_cost:,}원, 보유: {int(current_cash):,}원)',
                        }

                    # 1. Update Portfolio
                    row = self._select_portfolio_position_by_ticker(
                        cursor=cursor,
                        ticker=ticker,
                    )

                    if row:
                        # Update existing position
                        db_ticker, _db_name, old_avg, old_qty, old_cost = row
                        new_qty = old_qty + quantity
                        new_total_cost = old_cost + total_cost
                        new_avg = new_total_cost / new_qty

                        cursor.execute(
                            '''
                            UPDATE portfolio
                            SET avg_price = ?, quantity = ?, total_cost = ?, last_updated = ?
                            WHERE ticker = ?
                        ''',
                            (new_avg, new_qty, new_total_cost, datetime.now().isoformat(), db_ticker),
                        )
                    else:
                        # Create new position
                        cursor.execute(
                            '''
                            INSERT INTO portfolio (ticker, name, avg_price, quantity, total_cost, last_updated)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''',
                            (ticker_key, name, execution_price, quantity, total_cost, datetime.now().isoformat()),
                        )

                    # 2. Log Trade
                    cursor.execute(
                        '''
                        INSERT INTO trade_log (action, ticker, name, price, quantity, timestamp, profit, profit_rate)
                        VALUES (?, ?, ?, ?, ?, ?, 0, 0)
                    ''',
                        ('BUY', ticker_key, name, execution_price, quantity, datetime.now().isoformat()),
                    )

                    # 3. Deduct Cash
                    cursor.execute('UPDATE balance SET cash = cash - ? WHERE id = 1', (total_cost,))

                    conn.commit()
                return {'status': 'success', 'message': f'{name} {quantity}주 매수 완료'}

            result = self._execute_db_operation_with_schema_retry(_operation)

            if result.get("status") == "success":
                # [Sync Cache] DB 트랜잭션 성공 후에만 캐시를 반영한다.
                with self.cache_lock:
                    self.price_cache[ticker_key] = int(execution_price)
                    self.last_update = datetime.now()
                if hasattr(self, "_persist_price_cache"):
                    self._persist_price_cache({ticker_key: int(execution_price)})
            return result

        except Exception as e:
            logger.error(f"Buy failed: {e}")
            return {'status': 'error', 'message': str(e)}

    def sell_stock(self, ticker, price, quantity):
        """Execute Sell Order"""
        if quantity <= 0:
            return {'status': 'error', 'message': 'Quantity must be positive'}

        try:
            # [User Request] Trust Client Price
            execution_price = price
            ticker_key = self._normalize_ticker(ticker)

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

                    conn.commit()
                return {'status': 'success', 'message': f'{name} {quantity}주 매도 완료'}

            result = self._execute_db_operation_with_schema_retry(_operation)

            if result.get("status") == "success":
                # [Sync Cache] DB 트랜잭션 성공 후에만 캐시를 반영한다.
                with self.cache_lock:
                    self.price_cache[ticker_key] = int(execution_price)
                    self.last_update = datetime.now()
                if hasattr(self, "_persist_price_cache"):
                    self._persist_price_cache({ticker_key: int(execution_price)})
            return result

        except Exception as e:
            logger.error(f"Sell failed: {e}")
            return {'status': 'error', 'message': str(e)}

    def get_portfolio(self):
        """Get all holdings"""
        def _operation():
            with self.get_context() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute(
                    '''
                    SELECT ticker, name, avg_price, quantity, total_cost, last_updated
                    FROM portfolio
                    '''
                )
                holdings = [dict(row) for row in cursor.fetchall()]
                for holding in holdings:
                    holding["ticker"] = self._normalize_ticker(holding.get("ticker", ""))

                cursor.execute('SELECT cash, total_deposit FROM balance WHERE id = 1')
                balance_row = cursor.fetchone()
                cash = balance_row['cash'] if balance_row else 0
                total_deposit = (
                    balance_row['total_deposit']
                    if balance_row and 'total_deposit' in balance_row.keys()
                    else 0
                )

                # Initial Principal is 100,000,000. Total Principal = 100M + Deposits
                total_principal = 100000000 + total_deposit

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
                    cursor.execute('UPDATE balance SET cash = 100000000, total_deposit = 0 WHERE id = 1')
                    conn.commit()
                return True

            self._execute_db_operation_with_schema_retry(_operation)
            with self.cache_lock:
                self.price_cache.clear()
                self.last_update = None
            if hasattr(self, "_last_asset_history_snapshot"):
                self._last_asset_history_snapshot = None
            return True
        except Exception as error:
            logger.error(f"Failed to reset paper trading account: {error}")
            return False

    def get_trade_history(self, limit=50):
        """Get trade history"""
        def _operation():
            with self.get_context() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    SELECT id, action, ticker, name, price, quantity, timestamp, profit, profit_rate
                    FROM trade_log
                    ORDER BY timestamp DESC
                    LIMIT ?
                ''',
                    (limit,),
                )
                trades = [dict(row) for row in cursor.fetchall()]
                return {'trades': trades}

        return self._execute_db_operation_with_schema_retry(_operation)
