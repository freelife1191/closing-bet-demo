#!/usr/bin/env python3
"""
Debug: Why volume_ratio is < 1? Let's check raw data for Samsung Electronics.
"""
import os
import sys
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
prices_file = os.path.join(BASE_DIR, 'data', 'daily_prices.csv')

df = pd.read_csv(prices_file)
df['ticker'] = df['ticker'].astype(str).str.zfill(6)

# Samsung Electronics
samsung = df[df['ticker'] == '005930'].sort_values('date').tail(10)
print("Samsung Electronics (005930) - Last 10 Days:")
print(samsung[['date', 'open', 'high', 'low', 'close', 'volume']].to_string(index=False))

# Calculate volume ratio for last 2 days
if len(samsung) >= 2:
    today = samsung.iloc[-1]
    yesterday = samsung.iloc[-2]
    vol_ratio = today['volume'] / yesterday['volume'] if yesterday['volume'] > 0 else 0
    print(f"\nToday's volume: {today['volume']:,.0f}")
    print(f"Yesterday's volume: {yesterday['volume']:,.0f}")
    print(f"Volume Ratio: {vol_ratio:.2f}")
    
    # Check if volume looks correct for a strong market day
    print(f"\nAnalysis: Volume ratio {vol_ratio:.2f}x -> This is LOWER than yesterday.")
    print("If today is a strong (+11%) day, we expect volume to be HIGHER, not lower.")
    print("Possible issue: pykrx data might be incomplete (장중 데이터 vs 마감 데이터)")
