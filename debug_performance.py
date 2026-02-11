
import os
import json
import glob
import pandas as pd
from datetime import datetime

DATA_DIR = 'data'

def load_json_file(filename):
    filepath = os.path.join(DATA_DIR, filename)
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def load_csv_file(filename):
    filepath = os.path.join(DATA_DIR, filename)
    if os.path.exists(filepath):
        return pd.read_csv(filepath, low_memory=False)
    return pd.DataFrame()

def debug_performance():
    print("--- Debugging Cumulative Performance ---")
    
    # 1. Files
    pattern = os.path.join(DATA_DIR, 'jongga_v2_results_*.json')
    files = glob.glob(pattern)
    files.sort(reverse=True)
    print(f"Found {len(files)} result files: {files}")

    trades = []

    # 2. Prices
    price_df = pd.DataFrame()
    loaded_df = load_csv_file('daily_prices.csv')
    if not loaded_df.empty:
        loaded_df['ticker'] = loaded_df['ticker'].astype(str).str.zfill(6)
        loaded_df['date'] = pd.to_datetime(loaded_df['date'])
        loaded_df = loaded_df.sort_values('date')
        loaded_df.set_index('date', inplace=True)
        price_df = loaded_df
        print(f"Loaded prices: {len(price_df)} rows. Max date: {price_df.index.max()}")
    else:
        print("Prices empty")

    # 3. Process
    for filepath in files:
        filename = os.path.basename(filepath)
        print(f"\nProcessing {filename}...")
        
        data = load_json_file(filename)
        if not data or 'signals' not in data:
            continue
        
        file_date_str = filename.split('_')[-1].replace('.json', '')
        try:
            stats_date = datetime.strptime(file_date_str, '%Y%m%d').strftime('%Y-%m-%d')
        except:
            stats_date = data.get('date', '')
        
        print(f"  Stats Date: {stats_date}")
        
        for sig in data['signals']:
            ticker = str(sig.get('stock_code', '')).zfill(6)
            entry = sig.get('entry_price', 0)
            target = sig.get('target_price', 0)
            stop = sig.get('stop_price', 0)
            
            # Recalculate Logic in Code
            target = entry * 1.09
            stop = entry * 0.95

            print(f"    Signal: {ticker}, Entry: {entry}, Target: {target}, Stop: {stop}")
            
            outcome = 'OPEN'
            roi = 0.0
            
            if not price_df.empty:
                stock_prices = price_df[price_df['ticker'] == ticker]
                if not stock_prices.empty:
                    sig_ts = pd.Timestamp(stats_date)
                    period_prices = stock_prices[stock_prices.index > sig_ts]
                    
                    print(f"      Signal TS: {sig_ts}")
                    print(f"      Stock Prices Max Date: {stock_prices.index.max()}")
                    print(f"      Period Prices Len: {len(period_prices)}")
                    
                    if not period_prices.empty:
                        print(f"      First Period Price: {period_prices.iloc[0].name} Open: {period_prices.iloc[0]['open']} High: {period_prices.iloc[0]['high']}")

                    hit_target = period_prices[period_prices['high'] >= target]
                    hit_stop = period_prices[period_prices['low'] <= stop]
                    
                    first_win_date = hit_target.index[0] if not hit_target.empty else None
                    first_loss_date = hit_stop.index[0] if not hit_stop.empty else None

                    if first_win_date and first_loss_date:
                        if first_win_date <= first_loss_date:
                            outcome = 'WIN'
                            roi = 9.0
                        else:
                            outcome = 'LOSS'
                            roi = -5.0
                    elif first_win_date:
                        outcome = 'WIN'
                        roi = 9.0
                    elif first_loss_date:
                        outcome = 'LOSS'
                        roi = -5.0
                    else:
                        outcome = 'OPEN'
            
            print(f"      -> Outcome: {outcome}, ROI: {roi}")
            
            trades.append({'outcome': outcome, 'roi': roi})

    # Stats
    wins = sum(1 for t in trades if t['outcome'] == 'WIN')
    losses = sum(1 for t in trades if t['outcome'] == 'LOSS')
    closed_trades = wins + losses
    win_rate = (wins / closed_trades * 100) if closed_trades > 0 else 0.0
    
    print(f"\nFinal Stats:")
    print(f"  Trades: {len(trades)}")
    print(f"  Wins: {wins}")
    print(f"  Losses: {losses}")
    print(f"  Closed: {closed_trades}")
    print(f"  Win Rate: {win_rate}%")

if __name__ == "__main__":
    debug_performance()
