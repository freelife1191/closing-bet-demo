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
    def get_balance(self):
        """Get current cash balance"""
        with self.get_context() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT cash FROM balance WHERE id = 1')
            row = cursor.fetchone()
            return row[0] if row else 0

    def deposit_cash(self, amount):
        """Deposit cash (Charging)"""
        if amount <= 0:
            return {'status': 'error', 'message': 'Amount must be positive'}

        try:
            with self.get_context() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'UPDATE balance SET cash = cash + ?, total_deposit = total_deposit + ? WHERE id = 1',
                    (amount, amount),
                )
                conn.commit()
            return {'status': 'success', 'message': f'Deposited {amount:,} KRW'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    def update_balance(self, amount, operation='add'):
        """Update cash balance"""
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

    def buy_stock(self, ticker, name, price, quantity):
        """Execute Buy Order"""
        if quantity <= 0:
            return {'status': 'error', 'message': 'Quantity must be positive'}

        # [User Request] Trust Client Price
        # 사용자가 보고 매수한 가격(프론트엔드 가격)을 그대로 체결 가격으로 사용합니다.
        # 서버에서 다시 조회하면 소스/시간 차이로 가격이 달라져 혼란을 줄 수 있음.
        execution_price = price

        # [Sync Cache] Update cache with the executed price so Portfolio Current Price matches
        with self.cache_lock:
            self.price_cache[ticker] = int(execution_price)
            self.last_update = datetime.now()

        total_cost = int(execution_price * quantity)  # 정수로 처리

        try:
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
                cursor.execute(
                    'SELECT avg_price, quantity, total_cost FROM portfolio WHERE ticker = ?',
                    (ticker,),
                )
                row = cursor.fetchone()

                if row:
                    # Update existing position
                    old_avg, old_qty, old_cost = row
                    new_qty = old_qty + quantity
                    new_total_cost = old_cost + total_cost
                    new_avg = new_total_cost / new_qty

                    cursor.execute(
                        '''
                        UPDATE portfolio
                        SET avg_price = ?, quantity = ?, total_cost = ?, last_updated = ?
                        WHERE ticker = ?
                    ''',
                        (new_avg, new_qty, new_total_cost, datetime.now().isoformat(), ticker),
                    )
                else:
                    # Create new position
                    cursor.execute(
                        '''
                        INSERT INTO portfolio (ticker, name, avg_price, quantity, total_cost, last_updated)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''',
                        (ticker, name, execution_price, quantity, total_cost, datetime.now().isoformat()),
                    )

                # 2. Log Trade
                cursor.execute(
                    '''
                    INSERT INTO trade_log (action, ticker, name, price, quantity, timestamp, profit, profit_rate)
                    VALUES (?, ?, ?, ?, ?, ?, 0, 0)
                ''',
                    ('BUY', ticker, name, execution_price, quantity, datetime.now().isoformat()),
                )

                # 3. Deduct Cash
                cursor.execute('UPDATE balance SET cash = cash - ? WHERE id = 1', (total_cost,))

                conn.commit()

            if hasattr(self, "_persist_price_cache"):
                self._persist_price_cache({ticker: int(execution_price)})
            return {'status': 'success', 'message': f'{name} {quantity}주 매수 완료'}

        except Exception as e:
            logger.error(f"Buy failed: {e}")
            return {'status': 'error', 'message': str(e)}

    def sell_stock(self, ticker, price, quantity):
        """Execute Sell Order"""
        if quantity <= 0:
            return {'status': 'error', 'message': 'Quantity must be positive'}

        try:
            with self.get_context() as conn:
                cursor = conn.cursor()

                # 1. Check Portfolio
                cursor.execute(
                    'SELECT name, avg_price, quantity, total_cost FROM portfolio WHERE ticker = ?',
                    (ticker,),
                )
                row = cursor.fetchone()

                if not row or row[2] < quantity:
                    return {'status': 'error', 'message': 'Not enough shares to sell'}

                name, avg_price, current_qty, _current_total_cost = row

                # [User Request] Trust Client Price
                execution_price = price

                # [Sync Cache] Update cache immediately
                with self.cache_lock:
                    self.price_cache[ticker] = int(execution_price)
                    self.last_update = datetime.now()

                # 2. Update/Remove Portfolio
                remaining_qty = current_qty - quantity

                if remaining_qty == 0:
                    cursor.execute('DELETE FROM portfolio WHERE ticker = ?', (ticker,))
                else:
                    new_total_cost = avg_price * remaining_qty
                    cursor.execute(
                        '''
                        UPDATE portfolio
                        SET quantity = ?, total_cost = ?, last_updated = ?
                        WHERE ticker = ?
                    ''',
                        (remaining_qty, new_total_cost, datetime.now().isoformat(), ticker),
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
                    ('SELL', ticker, name, execution_price, quantity, datetime.now().isoformat(), profit, profit_rate),
                )

                # 4. Add Cash
                cursor.execute('UPDATE balance SET cash = cash + ? WHERE id = 1', (total_proceeds,))

                conn.commit()

            if hasattr(self, "_persist_price_cache"):
                self._persist_price_cache({ticker: int(execution_price)})
            return {'status': 'success', 'message': f'{name} {quantity}주 매도 완료'}

        except Exception as e:
            logger.error(f"Sell failed: {e}")
            return {'status': 'error', 'message': str(e)}

    def get_portfolio(self):
        """Get all holdings"""
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

    def reset_account(self):
        """Reset everything to default"""
        try:
            with self.get_context() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM portfolio')
                cursor.execute('DELETE FROM trade_log')
                cursor.execute('DELETE FROM asset_history')  # 히스토리도 초기화
                cursor.execute('DELETE FROM price_cache')
                cursor.execute('UPDATE balance SET cash = 100000000, total_deposit = 0 WHERE id = 1')
                conn.commit()
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
