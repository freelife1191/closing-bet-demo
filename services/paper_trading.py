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
import threading
import time
import pandas as pd
from datetime import datetime

logger = logging.getLogger(__name__)

class PaperTradingService:
    def __init__(self, db_name='paper_trading.db'):
        # Root path logic
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.db_path = os.path.join(base_dir, 'data', db_name)
        
        # Cache for real-time prices
        self.price_cache = {}
        self.cache_lock = threading.Lock()
        self.last_update = None
        self.is_running = False
        self.bg_thread = None
        
        self.is_running = False
        self.bg_thread = None
        
        self._init_db()
        
        # [Optimization] Auto-start background sync on initialization
        self.start_background_sync()

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
                    timestamp TEXT,
                    profit REAL DEFAULT 0,
                    profit_rate REAL DEFAULT 0
                )
            ''')
            
            # Migration: Add columns if not exists (for existing DB)
            try:
                cursor.execute('ALTER TABLE trade_log ADD COLUMN profit REAL DEFAULT 0')
            except Exception:
                pass # Already exists
                
            try:
                cursor.execute('ALTER TABLE trade_log ADD COLUMN profit_rate REAL DEFAULT 0')
            except Exception:
                pass # Already exists
            
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
                INSERT INTO trade_log (action, ticker, name, price, quantity, timestamp, profit, profit_rate)
                VALUES (?, ?, ?, ?, ?, ?, 0, 0)
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
            else:
                new_total_cost = avg_price * remaining_qty
                cursor.execute('''
                    UPDATE portfolio 
                    SET quantity = ?, total_cost = ?, last_updated = ?
                    WHERE ticker = ?
                ''', (remaining_qty, new_total_cost, datetime.now().isoformat(), ticker))
            
            # 3. Calculate Profit & Log Trade
            total_proceeds = int(price * quantity)
            cost_basis = int(avg_price * quantity)
            profit = total_proceeds - cost_basis
            profit_rate = (profit / cost_basis * 100) if cost_basis > 0 else 0
            
            cursor.execute('''
                INSERT INTO trade_log (action, ticker, name, price, quantity, timestamp, profit, profit_rate)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', ('SELL', ticker, name, price, quantity, datetime.now().isoformat(), profit, profit_rate))
            
            # 4. Add Cash
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

    def start_background_sync(self):
        """Start background price sync thread"""
        if self.is_running:
            return
            
        self.is_running = True
        self.bg_thread = threading.Thread(target=self._update_prices_loop, daemon=True)
        self.bg_thread.start()
        logger.info("PaperTrading Price Sync Started")

    def _update_prices_loop(self):
        """Background loop to fetch prices"""
        import yfinance as yf
        # Silence yfinance and related loggers
        logging.getLogger('yfinance').setLevel(logging.CRITICAL)
        logging.getLogger('peewee').setLevel(logging.CRITICAL)
        logging.getLogger('urllib3').setLevel(logging.ERROR)
        
        while self.is_running:
            try:
                # 1. Get all tickers from portfolio
                # ... (rest of logic) ...
                with self.get_context() as conn:
                    cursor = conn.cursor()
                    cursor.execute('SELECT ticker FROM portfolio')
                    tickers = [row[0] for row in cursor.fetchall()]
                
                if not tickers:
                    time.sleep(10)
                    continue

                new_prices = {}
                
                # 3. yfinance Fallback (Only for missing)
                missing_tickers = [t for t in tickers if t not in new_prices]
                if missing_tickers:
                    logger.info(f"Toss failed for {len(missing_tickers)} tickers. Trying yfinance...")
                    yf_tickers = [f"{t}.KS" for t in missing_tickers]
                    try:
                        # Use threads=False to prevent file handle leaks
                        df = yf.download(yf_tickers, period="1d", progress=False, threads=False)
                        
                        if not df.empty:
                            # Handle MultiIndex columns
                            try:
                                closes = df['Close']
                            except KeyError:
                                closes = df.xs('Close', axis=1, level=0, drop_level=True) if isinstance(df.columns, pd.MultiIndex) and 'Close' in df.columns.get_level_values(0) else df
                            
                            for t in missing_tickers:
                                ks_ticker = f"{t}.KS"
                                val = None
                                try:
                                    if isinstance(closes, pd.Series):
                                        val = closes.iloc[-1]
                                    elif ks_ticker in closes.columns:
                                        val = closes[ks_ticker].dropna().iloc[-1]
                                    
                                    if val is not None:
                                        new_prices[t] = int(float(val))
                                except Exception:
                                    pass
                    except Exception as e:
                        logger.error(f"PaperTrading YF Error: {e}")

                # 2. Try Toss Securities API first (Mobile/WTS) - Robust & Supports Bulk
                # Toss API is much faster (<0.1s) and supports KR stocks perfectly
                missing_tickers = [t for t in tickers if t not in new_prices]
                if missing_tickers:
                    logger.info(f"Using Toss Securities API for {len(missing_tickers)} tickers...")
                    import requests
                    
                    # Create mapping: padded(6) -> original_ticker_in_db
                    # This handles cases where DB has '5930' but API returns '005930'
                    ticker_map = {str(t).zfill(6): t for t in missing_tickers}

                    # Format tickers for Toss (A005930) - Ensure 6 digits
                    toss_codes = [f"A{str(t).zfill(6)}" for t in missing_tickers]
                    
                    # Split into chunks of 50 to avoid URL length limits
                    chunk_size = 50
                    for i in range(0, len(toss_codes), chunk_size):
                        chunk = toss_codes[i:i + chunk_size]
                        codes_str = ",".join(chunk)
                        
                        try:
                            url = f"https://wts-info-api.tossinvest.com/api/v3/stock-prices/details?productCodes={codes_str}"
                            headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
                            res = requests.get(url, headers=headers, timeout=5) # Fast timeout
                            
                            if res.status_code == 200:
                                data = res.json()
                                results = data.get('result', [])
                                
                                count = 0
                                for item in results:
                                    raw_code = item.get('code', '')
                                    # Robust 'A' removal
                                    clean_code = raw_code[1:] if raw_code.startswith('A') else raw_code
                                    
                                    # Map back to original ticker (DB format)
                                    original_t = ticker_map.get(clean_code)
                                    
                                    close = item.get('close')
                                    
                                    if original_t and close is not None:
                                        new_prices[original_t] = int(close)
                                        count += 1
                                logger.info(f"Toss API success: Fetched {count}/{len(chunk)} prices.")
                            else:
                                logger.warning(f"Toss API returned {res.status_code}: {res.text[:100]}")
                                        
                        except Exception as te:
                            logger.error(f"Toss API Error: {te}")

                # 4. Fallback to Naver Mobile API (User Request - Robust Realtime)
                missing_tickers = [t for t in tickers if t not in new_prices]
                if missing_tickers:
                    logger.info(f"Toss/YF failed. Using Naver Mobile API for {len(missing_tickers)} tickers...")
                    import requests
                    
                    for t in missing_tickers:
                        try:
                            # Naver Mobile JSON API
                            url = f"https://m.stock.naver.com/api/stock/{t}/basic"
                            headers = {'User-Agent': 'Mozilla/5.0'}
                            res = requests.get(url, headers=headers, timeout=3)
                            
                            if res.status_code == 200:
                                data = res.json()
                                if 'closePrice' in data:
                                    price_str = data['closePrice'].replace(',', '')
                                    new_prices[t] = int(price_str)
                                    logger.info(f"Naver API fetched {t}: {price_str}")
                                    continue
                        except Exception as ne:
                            logger.error(f"Naver API Error for {t}: {ne}")

                # 5. Final Fallback to pykrx (Historical Data / Market Close)
                still_missing = [t for t in missing_tickers if t not in new_prices]
                if still_missing:
                    try:
                        today_str = datetime.now().strftime("%Y%m%d")
                        for t in still_missing:
                            try:
                                # pykrx get_market_ohlcv returns dataframe
                                df = stock.get_market_ohlcv(today_str, today_str, t)
                                if not df.empty and '종가' in df.columns:
                                    price = df['종가'].iloc[-1]
                                    if price > 0:
                                        new_prices[t] = int(price)
                                else:
                                    # Try yesterday
                                    yesterday = (datetime.now() - pd.Timedelta(days=1)).strftime("%Y%m%d")
                                    df = stock.get_market_ohlcv(yesterday, yesterday, t)
                                    if not df.empty and '종가' in df.columns:
                                        price = df['종가'].iloc[-1]
                                        if price > 0:
                                            new_prices[t] = int(price)
                            except Exception:
                                pass
                    except Exception:
                        pass
                
                # 5. Update Cache safely
                with self.cache_lock:
                    self.price_cache.update(new_prices)
                    self.last_update = datetime.now()

            except Exception as e:
                logger.error(f"PaperTrading Loop Error: {e}")
            
            
            time.sleep(60) # Update every 60 seconds (Optimized from 30s)

    def get_portfolio_valuation(self):
        """Get portfolio with cached prices (Fast)"""
        with self.get_context() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM portfolio')
            holdings = [dict(row) for row in cursor.fetchall()]
            
            cursor.execute('SELECT cash FROM balance WHERE id = 1')
            balance_row = cursor.fetchone()
            cash = balance_row['cash'] if balance_row else 0

        updated_holdings = []
        total_stock_value = 0
        
        # Use Cached Prices
        with self.cache_lock:
            current_prices = self.price_cache.copy()

        # [Improvement] If cache is empty but we have holdings, wait briefly for background sync
        if not current_prices and holdings and self.bg_thread and self.bg_thread.is_alive():
            logger.info("Portfolio Valuation: Waiting for initial price sync...")
        if not current_prices and holdings and self.bg_thread and self.bg_thread.is_alive():
            logger.info("Portfolio Valuation: Waiting for initial price sync...")
            for _ in range(50): # Wait up to 5 seconds (0.1s * 50)
                time.sleep(0.1)
                with self.cache_lock:
                    if self.price_cache:
                        current_prices = self.price_cache.copy()
                        break
            if current_prices:
                logger.info("Portfolio Valuation: Synced successfully waited.")
            
        # Log cache status once in a while or if empty
        if not current_prices and holdings:
            logger.warning("Portfolio Valuation: Price cache is empty! Falling back to purchase price.")
        elif holdings:
             # Debug sampling (Sample first ticker)
             t1 = holdings[0]['ticker']
             in_cache = t1 in current_prices
             val = current_prices.get(t1)
             logger.info(f"Portfolio Valuation: Cache Size={len(current_prices)}, Holdings={len(holdings)}. Sample ({t1}): InCache={in_cache}, Val={val}")

        for holding in holdings:
            ticker = holding['ticker']
            avg_price = holding['avg_price']
            quantity = holding['quantity']
            
            # Use cached price if available, else avg_price (fallback)
            current_price = current_prices.get(ticker, avg_price)
            
            if ticker not in current_prices:
                logger.warning(f"Price Cache Miss for {ticker}. Cache Keys Sample: {list(current_prices.keys())[:5]}")
            
            market_value = int(current_price * quantity)
            total_stock_value += market_value
            
            profit_loss = market_value - (avg_price * quantity)
            profit_rate = 0
            if avg_price > 0:
                profit_rate = ((current_price - avg_price) / avg_price) * 100
                
            h_dict = dict(holding)
            h_dict['current_price'] = current_price
            h_dict['market_value'] = market_value
            h_dict['profit_loss'] = int(profit_loss)
            h_dict['profit_rate'] = round(profit_rate, 2)
            updated_holdings.append(h_dict)

        total_asset = cash + total_stock_value
        
        # Record history (Optimized: Record only if significant change or sufficient time passed?)
        # For now, simplistic record on view
        try:
            self.record_asset_history(total_stock_value)
        except Exception:
            pass

        return {
            'holdings': updated_holdings,
            'cash': cash,
            'total_asset_value': total_asset,
            'total_stock_value': total_stock_value,
            'total_profit': int(total_asset - 100000000),
            'total_profit_rate': round(((total_asset - 100000000) / 100000000 * 100), 2),
            'last_update': self.last_update.isoformat() if self.last_update else None
        }

    def record_asset_history(self, current_stock_value):
        """Record daily asset history snapshot"""
        try:
            cash = self.get_balance()
            total_asset = cash + current_stock_value
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
            ''', (today, total_asset, cash, current_stock_value, datetime.now().isoformat()))
            
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
            rows = [dict(row) for row in cursor.fetchall()]
            
            # [Fix] If history is scarce (< 2 points), return dummy data for chart rendering
            if len(rows) < 2:
                today = datetime.now()
                dummy_data = []
                for i in range(4, -1, -1): # Last 5 days
                    d = (today - timedelta(days=i)).strftime('%Y-%m-%d')
                    dummy_data.append({
                        'date': d,
                        'total_asset': 100000000, # Initial Balance
                        'cash': 100000000,
                        'stock_value': 0
                    })
                return dummy_data
                
            return rows

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
                SELECT id, action, ticker, name, price, quantity, timestamp, profit, profit_rate
                FROM trade_log
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (limit,))
            trades = [dict(row) for row in cursor.fetchall()]
            return {'trades': trades}

# Global Instance
paper_trading = PaperTradingService()

