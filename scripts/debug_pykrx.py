from pykrx import stock
from datetime import datetime
import pandas as pd

today = datetime.now().strftime('%Y%m%d')
print(f"Fetching market cap for {today}...")

try:
    df = stock.get_market_cap(today, market="KOSPI")
    print("\n--- DataFrame Head ---")
    print(df.head())
    print("\n--- DataFrame Columns ---")
    print(df.columns)
    print("\n--- DataFrame Index ---")
    print(df.index.name)
except Exception as e:
    print(f"Error fetching KOSPI: {e}")

try:
    # Try fetching previous business day if today is empty (which happens if today is holiday/weekend)
    # But today is Tuesday 2026-02-03, should be open.
    # Unless 2026-02-03 is a holiday?
    # Let's try a specific known valid date.
    test_date = "20260130" # Friday?
    print(f"\nFetching market cap for {test_date} (Test Date)...")
    df_test = stock.get_market_cap(test_date, market="KOSPI")
    print(df_test.head())
    print(df_test.columns)
except Exception as e:
    print(f"Error fetching Test Date: {e}")
