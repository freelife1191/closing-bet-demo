import os
import sys
import pandas as pd
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.routes.kr_market import load_csv_file, get_data_path

def debug_vcp_stats():
    print("Debugging VCP Stats Calculation...")
    
    # 1. Load Data
    vcp_df = load_csv_file('signals_log.csv')
    print(f"Loaded {len(vcp_df)} signals from signals_log.csv")
    
    # 2. Load Prices
    price_file = get_data_path('daily_prices.csv')
    df_prices_full = pd.read_csv(price_file, usecols=['date', 'ticker', 'close', 'high', 'low'], dtype={'ticker': str})
    df_prices_full['ticker'] = df_prices_full['ticker'].str.zfill(6)
    
    # Create Price Map
    latest_prices = df_prices_full.sort_values('date').groupby('ticker').tail(1)
    price_map = latest_prices.set_index('ticker')['close'].to_dict()
    print(f"Loaded price map for {len(price_map)} tickers")
    
    # 3. Simulate Calculation
    total_v = 0
    wins_v = 0
    total_ret_v = 0.0
    
    skipped_reasons = {}

    for _, row in vcp_df.iterrows():
        ticker = str(row.get('ticker', '')).zfill(6)
        entry_price = float(row.get('entry_price', 0))
        signal_date = str(row.get('signal_date', ''))
        
        if entry_price <= 0:
            skipped_reasons['invalid_entry'] = skipped_reasons.get('invalid_entry', 0) + 1
            print(f"Skipping {ticker}: Invalid entry price {entry_price}")
            continue
            
        if not signal_date:
             skipped_reasons['no_date'] = skipped_reasons.get('no_date', 0) + 1
             continue

        current_price = price_map.get(ticker, 0)
        
        if current_price == 0:
            skipped_reasons['no_price'] = skipped_reasons.get('no_price', 0) + 1
            # Print first few missing tickers
            if skipped_reasons['no_price'] <= 5:
                print(f"Skipping {ticker}: No current price in price_map")
            continue
            
        # Calc Return
        # Fallback logic from calculate_scenario_return
        # We simulate the exact logic
        sim_ret = ((current_price - entry_price) / entry_price) * 100
        
        # Check high/low if exists
        # Simplified for debug
        subset = df_prices_full[
            (df_prices_full['ticker'] == ticker) & 
            (df_prices_full['date'] > signal_date)
        ]
        
        outcome = "HOLD"
        final_ret = sim_ret
        
        if not subset.empty:
            for _, day in subset.iterrows():
                if day['low'] <= entry_price * 0.95:
                    final_ret = -5.0
                    outcome = "LOSS"
                    break
                if day['high'] >= entry_price * 1.15:
                    final_ret = 15.0
                    outcome = "WIN"
                    break
        
        total_v += 1
        total_ret_v += final_ret
        if final_ret > 0: wins_v += 1
        
        print(f"Signal: {ticker} ({signal_date}) | Entry: {entry_price} | Curr: {current_price} | Ret: {final_ret:.2f}% ({outcome})")

    print("\n--- Summary ---")
    print(f"Total Processed: {total_v}")
    print(f"Wins: {wins_v}")
    if total_v > 0:
        print(f"Win Rate: {(wins_v/total_v)*100:.1f}%")
        print(f"Avg Return: {total_ret_v/total_v:.1f}%")
    
    print("\n--- Skipped ---")
    print(skipped_reasons)

if __name__ == "__main__":
    debug_vcp_stats()
