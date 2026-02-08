
import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Add root to path
sys.path.append(os.getcwd())

from engine.screener import SmartMoneyScreener

def verify_vcp_logic():
    print("\n[Verifying VCP Detection Logic]")
    screener = SmartMoneyScreener()
    
    # 1. Mock Data: VCP Pattern Case
    # - 60 days of data
    # - Recent High at 10000
    # - Current Price around 9500 (Inside 15%)
    # - Volatility Contracting (ATR decreases)
    # - Range Contracting (Ratio < 0.7)
    
    dates = pd.date_range(end=datetime.today(), periods=60, freq='D')
    
    # Base pattern
    close = [10000] * 60
    high = [10200] * 60
    low = [9800] * 60
    volume = [2000] * 60
    
    # Create Contraction
    # Past 40 days: High Volatility (Range 800)
    for i in range(40):
        high[i] = 10400
        low[i] = 9600
        
    # Days 40-55: Medium Volatility (Range 400)
    for i in range(40, 55):
        high[i] = 10200
        low[i] = 9800
        close[i] = 10000
        volume[i] = 2000 # High Volume Base

    # Days 55-60: Extreme Contraction (Range 50)
    # Recent Range 50 / Avg Range (mix of 400 and 50) ~ 0.2
    # Days 55-60: Extreme Contraction (Range 50)
    # Recent Range 50 / Avg Range (mix of 400 and 50) ~ 0.2
    # Volume Dry Up: 500 / 2000 ~ 0.25 (Score 30)
    for i in range(55, 60):
        high[i] = 10150
        low[i] = 10050 
        close[i] = 10100 # Close > old 10000 avg (MA20)
        volume[i] = 500
        
    # Ensure MA Alignment on Last Day (Close > MA5 > MA20)
    # MA20 approx (15*10000 + 5*10100)/20 = 10025
    # MA5 approx 10100
    # Close 10150 > 10100 > 10025 -> Perfect Alignment (Score 30)
    close[59] = 10150
        
    # Set Recent High (at index 30) to 10500 to satisfy "Near High" check
    high[30] = 10500 
    
    # Ensure current close is near high_60d (10500)
    # 10000 > 10500 * 0.85 (8925) -> OK 
    
    df_vcp = pd.DataFrame({
        'date': dates,
        'ticker': '005930',
        'close': close,
        'high': high,
        'low': low,
        'volume': volume
    })
    
    stock_info = {'ticker': '005930', 'name': 'VCP Test Stock', 'market': 'KOSPI'}
    
    # Run Test 1: Perfect VCP
    print("\n--- Test 1: Perfect VCP Pattern ---")
    result = screener._detect_vcp_pattern(df_vcp, stock_info)
    print(f"Is VCP: {result.is_vcp}")
    print(f"Score: {result.vcp_score}")
    print(f"Contraction Ratio: {result.contraction_ratio}")
    print(f"Entry Price: {result.entry_price}")
    
    if result.is_vcp and result.contraction_ratio < 0.7:
        print("✅ Test 1 Passed")
    else:
        print("❌ Test 1 Failed")

    # Run Test 2: Price too low (Deep Correction)
    print("\n--- Test 2: Price too low (Deep Correction) ---")
    df_low = df_vcp.copy()
    # Recent High is 10500. 15% drop is ~8925. Set price to 8000.
    df_low.loc[59, 'close'] = 8000 
    
    result = screener._detect_vcp_pattern(df_low, stock_info)
    print(f"Is VCP: {result.is_vcp}")
    print(f"Reason: {result.pattern_desc}")
    
    if not result.is_vcp and "Price too low" in result.pattern_desc:
        print("✅ Test 2 Passed")
    else:
        print("❌ Test 2 Failed")

    # Run Test 3: Volatility Expansion (Failed VCP)
    print("\n--- Test 3: Volatility Expansion (ATR Increasing) ---")
    df_exp = df_vcp.copy()
    # Recent 5 days huge range
    for i in range(55, 60):
        df_exp.loc[i, 'high'] = 11000
        df_exp.loc[i, 'low'] = 9000 # Range 2000
        
    result = screener._detect_vcp_pattern(df_exp, stock_info)
    print(f"Is VCP: {result.is_vcp}")
    print(f"Contraction Ratio: {result.contraction_ratio}")
    
    # Contraction Ratio > 1.0 -> Fail
    if not result.is_vcp:
        print("✅ Test 3 Passed")
    else:
        print("❌ Test 3 Failed")

if __name__ == "__main__":
    verify_vcp_logic()
