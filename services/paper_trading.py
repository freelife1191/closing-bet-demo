#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Paper Trading Service (Mock Investment)
- Manages user's virtual portfolio and trade history.
- Uses SQLite for persistence.
"""

import os
import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class PaperTradingService:
    def __init__(self, db_name='paper_trading.db'):
        # Root path logic
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.db_path = os.path.join(base_dir, 'data', db_name)
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database tables"""
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Portfolio Table (Current Holdings)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS portfolio (
                    ticker TEXT PRIMARY KEY,
                    name TEXT,
                    avg_price REAL,
                    quantity INTEGER,
                    total_cost REAL,
                    last_updated TEXT
                )
            ''')
            
            # Trade Log Table (History)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trade_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT,  -- 'BUY' or 'SELL'
                    ticker TEXT,
                    name TEXT,
                    price REAL,
                    quantity INTEGER,
                    timestamp TEXT
                )
            ''')
            
            # Asset History Table (For Charting)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS asset_history (
                    date TEXT PRIMARY KEY,
                    total_asset REAL,
                    cash REAL,
                    stock_value REAL,
                    timestamp TEXT
                )
            ''')
            
            # Balance Table (Cash)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS balance (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    cash REAL DEFAULT 100000000  -- Default 100M KRW
                )
            ''')
            # Initialize balance if not exists
            cursor.execute('INSERT OR IGNORE INTO balance (id, cash) VALUES (1, 100000000)')
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to initialize paper trading db: {e}")

    def get_context(self):
        """Helper to get db connection"""
        return sqlite3.connect(self.db_path)

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
            conn = self.get_context()
            cursor = conn.cursor()
            cursor.execute('UPDATE balance SET cash = cash + ? WHERE id = 1', (amount,))
            conn.commit()
            conn.close()
            return {'status': 'success', 'message': f'Deposited {amount:,} KRW'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    def update_balance(self, amount, operation='add'):
        """Update cash balance"""
        with self.get_context() as conn:
            cursor = conn.cursor()
            current = self.get_balance()
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
            
        total_cost = int(price * quantity) # 정수로 처리
        current_cash = self.get_balance()
        
        if current_cash < total_cost:
            return {
                'status': 'error', 
                'message': f'잔고 부족 (필요: {total_cost:,}원, 보유: {int(current_cash):,}원)'
            }

        try:
            conn = self.get_context()
            cursor = conn.cursor()
            
            # 1. Update Portfolio
            cursor.execute('SELECT avg_price, quantity, total_cost FROM portfolio WHERE ticker = ?', (ticker,))
            row = cursor.fetchone()
            
            if row:
                # Update existing position
                old_avg, old_qty, old_cost = row
                new_qty = old_qty + quantity
                new_total_cost = old_cost + total_cost
                new_avg = new_total_cost / new_qty
                
                cursor.execute('''
                    UPDATE portfolio 
                    SET avg_price = ?, quantity = ?, total_cost = ?, last_updated = ?
                    WHERE ticker = ?
                ''', (new_avg, new_qty, new_total_cost, datetime.now().isoformat(), ticker))
            else:
                # Create new position
                cursor.execute('''
                    INSERT INTO portfolio (ticker, name, avg_price, quantity, total_cost, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (ticker, name, price, quantity, total_cost, datetime.now().isoformat()))
            
            # 2. Log Trade
            cursor.execute('''
                INSERT INTO trade_log (action, ticker, name, price, quantity, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', ('BUY', ticker, name, price, quantity, datetime.now().isoformat()))
            
            # 3. Deduct Cash
            cursor.execute('UPDATE balance SET cash = cash - ? WHERE id = 1', (total_cost,))
            
            conn.commit()
            conn.close()
            return {'status': 'success', 'message': f'{name} {quantity}주 매수 완료'}
            
        except Exception as e:
            logger.error(f"Buy failed: {e}")
            return {'status': 'error', 'message': str(e)}

    def sell_stock(self, ticker, price, quantity):
        """Execute Sell Order"""
        if quantity <= 0:
            return {'status': 'error', 'message': 'Quantity must be positive'}

        try:
            conn = self.get_context()
            cursor = conn.cursor()
            
            # 1. Check Portfolio
            cursor.execute('SELECT name, avg_price, quantity, total_cost FROM portfolio WHERE ticker = ?', (ticker,))
            row = cursor.fetchone()
            
            if not row or row[2] < quantity:
                conn.close()
                return {'status': 'error', 'message': 'Not enough shares to sell'}
            
            name, avg_price, current_qty, current_total_cost = row
            
            # 2. Update/Remove Portfolio
            remaining_qty = current_qty - quantity
            
            if remaining_qty == 0:
                cursor.execute('DELETE FROM portfolio WHERE ticker = ?', (ticker,))
                # 전량 매도 시에는 해당 종목 평가 손익 확정 로직이 필요할 수 있으나 여기선 생략
            else:
                # FIFO / Avg Cost Logic: 
                # When selling, cost basis reduces proportionally.
                # Remaining Total Cost = Avg Price * Remaining Qty
                new_total_cost = avg_price * remaining_qty
                cursor.execute('''
                    UPDATE portfolio 
                    SET quantity = ?, total_cost = ?, last_updated = ?
                    WHERE ticker = ?
                ''', (remaining_qty, new_total_cost, datetime.now().isoformat(), ticker))
            
            # 3. Log Trade
            cursor.execute('''
                INSERT INTO trade_log (action, ticker, name, price, quantity, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', ('SELL', ticker, name, price, quantity, datetime.now().isoformat()))
            
            # 4. Add Cash
            total_proceeds = int(price * quantity)
            cursor.execute('UPDATE balance SET cash = cash + ? WHERE id = 1', (total_proceeds,))
            
            conn.commit()
            conn.close()
            return {'status': 'success', 'message': f'{name} {quantity}주 매도 완료'}
            
        except Exception as e:
            logger.error(f"Sell failed: {e}")
            return {'status': 'error', 'message': str(e)}

    def get_portfolio(self):
        """Get all holdings"""
        with self.get_context() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM portfolio')
            holdings = [dict(row) for row in cursor.fetchall()]
            
            cursor.execute('SELECT cash FROM balance WHERE id = 1')
            balance_row = cursor.fetchone()
            cash = balance_row['cash'] if balance_row else 0
            
            return {
                'holdings': holdings,
                'cash': cash,
                'total_asset_value': cash  # Will need to add holdings value in API layer
            }

    def record_asset_history(self, stock_value):
        """Record daily asset history snapshot"""
        try:
            cash = self.get_balance()
            total_asset = cash + stock_value
            today = datetime.now().strftime('%Y-%m-%d')
            
            conn = self.get_context()
            cursor = conn.cursor()
            
            # 하루에 하나의 기록만 남김 (UPDATE or INSERT)
            cursor.execute('''
                INSERT INTO asset_history (date, total_asset, cash, stock_value, timestamp)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET
                    total_asset = excluded.total_asset,
                    cash = excluded.cash,
                    stock_value = excluded.stock_value,
                    timestamp = excluded.timestamp
            ''', (today, total_asset, cash, stock_value, datetime.now().isoformat()))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to record asset history: {e}")

    def get_asset_history(self, limit=30):
        """Get asset history for chart"""
        with self.get_context() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT date, total_asset, cash, stock_value 
                FROM asset_history 
                ORDER BY date ASC 
                LIMIT ?
            ''', (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def reset_account(self):
        """Reset everything to default"""
        try:
            conn = self.get_context()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM portfolio')
            cursor.execute('DELETE FROM trade_log')
            cursor.execute('DELETE FROM asset_history') # 히스토리도 초기화
            cursor.execute('UPDATE balance SET cash = 100000000 WHERE id = 1')
            conn.commit()
            conn.close()
            return True
        except Exception:
            return False

    def get_trade_history(self, limit=50):
        """Get trade history"""
        with self.get_context() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, action, ticker, name, price, quantity, timestamp
                FROM trade_log
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (limit,))
            trades = [dict(row) for row in cursor.fetchall()]
            return {'trades': trades}

# Global Instance
paper_trading = PaperTradingService()

