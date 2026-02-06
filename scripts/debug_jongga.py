#!/usr/bin/env python3
"""
Deep Debug Script for Jongga V2 & VCP Signal Issues
"""
import os
import sys
import pandas as pd
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

def main():
    print("=" * 60)
    print("Deep Debug: Jongga V2 & VCP Signal Analysis")
    print("=" * 60)
    
    # 1. Check Data Files
    prices_file = os.path.join(BASE_DIR, 'data', 'daily_prices.csv')
    inst_file = os.path.join(BASE_DIR, 'data', 'all_institutional_trend_data.csv')
    stocks_file = os.path.join(BASE_DIR, 'data', 'korean_stocks_list.csv')
    
    print("\n[1] Data Files Check:")
    for f in [prices_file, inst_file, stocks_file]:
        if os.path.exists(f):
            size = os.path.getsize(f)
            print(f"  ✅ {os.path.basename(f)}: {size:,} bytes")
        else:
            print(f"  ❌ {os.path.basename(f)}: NOT FOUND")
    
    # 2. Check Prices Data
    print("\n[2] Daily Prices Data Analysis:")
    if os.path.exists(prices_file):
        prices_df = pd.read_csv(prices_file)
        print(f"  - Total rows: {len(prices_df):,}")
        print(f"  - Date range: {prices_df['date'].min()} ~ {prices_df['date'].max()}")
        print(f"  - Unique tickers: {prices_df['ticker'].nunique()}")
        
        # Latest date data
        latest_date = prices_df['date'].max()
        latest_data = prices_df[prices_df['date'] == latest_date]
        print(f"\n  [Latest Date: {latest_date}]")
        print(f"  - Stocks with data: {len(latest_data)}")
        
        # Check for price changes (rise_pct)
        if len(latest_data) > 0:
            # Get previous day
            dates = sorted(prices_df['date'].unique())
            if len(dates) >= 2:
                prev_date = dates[-2]
                print(f"  - Previous date: {prev_date}")
                
                # Calculate rise_pct for each stock
                results = []
                for ticker in latest_data['ticker'].unique():
                    ticker_data = prices_df[prices_df['ticker'] == ticker].sort_values('date')
                    if len(ticker_data) < 2:
                        continue
                    
                    current = ticker_data.iloc[-1]
                    prev = ticker_data.iloc[-2]
                    
                    if prev['close'] > 0:
                        rise_pct = ((current['close'] - prev['close']) / prev['close']) * 100
                        trading_value = current['volume'] * current['close']
                        volume_ratio = current['volume'] / prev['volume'] if prev['volume'] > 0 else 0
                        
                        results.append({
                            'ticker': ticker,
                            'rise_pct': round(rise_pct, 2),
                            'trading_value_M': int(trading_value / 1_000_000),
                            'volume_ratio': round(volume_ratio, 2),
                            'close': int(current['close'])
                        })
                
                # Sort by rise_pct
                results = sorted(results, key=lambda x: x['rise_pct'], reverse=True)[:20]
                
                print(f"\n  [Top 20 Rising Stocks on {latest_date}]")
                print(f"  {'Ticker':<8} {'Rise%':>8} {'TradVal(M)':>12} {'VolRatio':>10} {'Close':>10}")
                print(f"  {'-'*8} {'-'*8} {'-'*12} {'-'*10} {'-'*10}")
                for r in results:
                    print(f"  {r['ticker']:<8} {r['rise_pct']:>8.2f}% {r['trading_value_M']:>12,} {r['volume_ratio']:>10.2f} {r['close']:>10,}")
                
                # Check D-grade eligibility
                print(f"\n  [D-Grade Eligibility Check (500억+, 4%+, vol_ratio >= 2)]")
                d_eligible = [r for r in results if r['trading_value_M'] >= 50000 and r['rise_pct'] >= 4.0 and r['volume_ratio'] >= 2.0]
                if d_eligible:
                    for r in d_eligible:
                        print(f"  ✅ {r['ticker']}: {r['rise_pct']:.2f}%, {r['trading_value_M']/1000:.0f}억, vol_ratio={r['volume_ratio']:.2f}")
                else:
                    print("  ❌ No stocks meet D-grade criteria!")
                    
                    # Relaxed check
                    print(f"\n  [Relaxed Check (300억+, 3%+, vol_ratio >= 1.5)]")
                    relaxed = [r for r in results if r['trading_value_M'] >= 35000 and r['rise_pct'] >= 3.0 and r['volume_ratio'] >= 1.5]
                    if relaxed:
                        for r in relaxed:
                            print(f"  ⚠️ {r['ticker']}: {r['rise_pct']:.2f}%, {r['trading_value_M']/1000:.0f}억, vol_ratio={r['volume_ratio']:.2f}")
                    else:
                        print("  ❌ No stocks meet relaxed criteria either!")
    
    # 3. Check Stocks List
    print("\n[3] Stock List Analysis:")
    if os.path.exists(stocks_file):
        stocks_df = pd.read_csv(stocks_file)
        print(f"  - Total stocks in list: {len(stocks_df)}")
        print(f"  - KOSPI: {len(stocks_df[stocks_df['market'] == 'KOSPI'])}")
        print(f"  - KOSDAQ: {len(stocks_df[stocks_df['market'] == 'KOSDAQ'])}")
        print(f"  - Sample tickers: {stocks_df['ticker'].head(10).tolist()}")
    
    # 4. Check Jongga V2 Latest
    print("\n[4] Jongga V2 Latest Check:")
    jongga_file = os.path.join(BASE_DIR, 'data', 'jongga_v2_latest.json')
    if os.path.exists(jongga_file):
        import json
        with open(jongga_file, 'r') as f:
            jongga = json.load(f)
        print(f"  - Date: {jongga.get('date')}")
        print(f"  - Total Candidates: {jongga.get('total_candidates')}")
        print(f"  - Filtered Count: {jongga.get('filtered_count')}")
        print(f"  - Signals: {len(jongga.get('signals', []))}")
    else:
        print("  ❌ jongga_v2_latest.json NOT FOUND")
    
    print("\n" + "=" * 60)
    print("Debug Complete")
    print("=" * 60)

if __name__ == "__main__":
    main()
