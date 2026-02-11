
import asyncio
import logging
import sys
import os
import pandas as pd

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_collector")

# Add current directory to sys.path
sys.path.append(os.getcwd())

from engine.collectors.krx import KRXCollector
from engine.config import config

async def verify_logic():
    print("=== Verifying KRXCollector Logic ===")
    
    collector = KRXCollector(config)
    
    # 1. Check Files
    print("\n[Step 1] Checking Data Files...")
    daily_path = os.path.join("data", "daily_prices.csv")
    stocks_path = os.path.join("data", "korean_stocks_list.csv")
    
    if os.path.exists(daily_path):
        df = pd.read_csv(daily_path)
        print(f"daily_prices.csv: {len(df)} rows")
        print(f"Sample tickers: {df['ticker'].head().tolist()}")
        print(f"Date range: {df['date'].min()} ~ {df['date'].max()}")
    else:
        print("daily_prices.csv NOT FOUND")
        
    if os.path.exists(stocks_path):
        stocks_df = pd.read_csv(stocks_path)
        print(f"korean_stocks_list.csv: {len(stocks_df)} rows")
        print(f"Sample tickers: {stocks_df['ticker'].head().tolist()}")
    else:
        print("korean_stocks_list.csv NOT FOUND")

    # 2. Test get_top_gainers (KOSPI)
    print("\n[Step 2] Testing get_top_gainers('KOSPI')...")
    targets = ["20260211", "2026-02-11"]
    
    for t_date in targets:
        print(f"\nTesting with date: {t_date}")
        try:
            results = await collector.get_top_gainers("KOSPI", 10, target_date=t_date)
            print(f"Result count: {len(results)}")
            for s in results[:3]:
                print(f" - {s.name} ({s.code}): {s.change_pct}%")
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

    # 3. Test Fallback Logic Explicitly
    print("\n[Step 3] Testing _load_from_local_csv explicitly...")
    try:
        results = collector._load_from_local_csv("KOSPI", 10, target_date="20260211")
        print(f"Fallback Result count: {len(results)}")
        for s in results[:3]:
            print(f" - {s.name} ({s.code}): {s.change_pct}%")
    except Exception as e:
        print(f"Error in fallback: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(verify_logic())
