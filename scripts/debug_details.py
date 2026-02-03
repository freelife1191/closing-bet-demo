#!/usr/bin/env python3
"""
Debug Details: Check Themes, Supply Scores, and Advanced Score Calculation
"""
import os
import sys
import pandas as pd
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from scripts.init_data import calculate_advanced_score, get_themes_by_sector

def main():
    print("=" * 60)
    print("Debug Details: Themes & Supply")
    print("=" * 60)

    # Load Data
    prices_file = os.path.join(BASE_DIR, 'data', 'daily_prices.csv')
    inst_file = os.path.join(BASE_DIR, 'data', 'all_institutional_trend_data.csv')
    stocks_file = os.path.join(BASE_DIR, 'data', 'korean_stocks_list.csv')

    prices_df = pd.read_csv(prices_file)
    inst_df = pd.read_csv(inst_file)
    stocks_df = pd.read_csv(stocks_file)

    # Test Targets (known from previous run)
    targets = ['005930', '000660', '380550'] # Samsung, Hynix, Neurofit

    for ticker in targets:
        print(f"\n[Analysing {ticker}]")
        stock_info = stocks_df[stocks_df['ticker'].astype(str) == ticker]
        if stock_info.empty:
            print("  ❌ Not found in stocks list")
            continue
            
        row = stock_info.iloc[0]
        name = row['name']
        sector = row.get('sector', '')
        print(f"  Name: {name}")
        print(f"  Sector: {sector} (Type: {type(sector)})")
        
        # 1. Check Themes
        themes = get_themes_by_sector(sector, name)
        print(f"  ✅ Themes: {themes}")
        
        # 2. Check Advanced Score (Supply)
        score_data = calculate_advanced_score(ticker, prices_df, inst_df)
        print("  ✅ Score Data:")
        print(f"     - Total Score: {score_data['total']}")
        print(f"     - Foreign Net Buy: {score_data.get('foreign_net_buy')}")
        print(f"     - Inst Net Buy: {score_data.get('inst_net_buy')}")
        print(f"     - Supply Score: {score_data['details'].get('supply', 0)}")
        
        # Check raw supply data
        inst_ticker = inst_df[inst_df['ticker'].astype(str).str.zfill(6) == ticker]
        if not inst_ticker.empty:
            latest_inst = inst_ticker.sort_values('date').iloc[-1]
            print(f"  ✅ Raw Inst Data ({latest_inst['date']}):")
            print(f"     - Foreign: {latest_inst['foreign_net_buy']}")
            print(f"     - Inst: {latest_inst['org_net_buy']}")
        else:
            print("  ❌ No raw institutional data found")

if __name__ == "__main__":
    main()
