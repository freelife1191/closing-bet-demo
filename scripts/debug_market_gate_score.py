
import sys
import os
import pandas as pd
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.market_gate import MarketGate

def debug_score():
    mg = MarketGate()
    print(" Analyzing Market Gate Score...")
    
    # Analyze for today (or latest available)
    result = mg.analyze()
    
    print("\n--- Market Gate Score Breakdown ---")
    print(f"Date: {result.get('dataset_date')}")
    print(f"Total Score: {result.get('total_score')}")
    print(f"Status: {result.get('status')} ({result.get('label')})")
    
    details = result.get('details', {})
    print("\n[Detailed Breakdown]")
    print(f"1. Trend (MA20 > MA60): {details.get('trend_score')} / 25")
    print(f"   - MA20: {details.get('ma20')}")
    print(f"   - MA60: {details.get('ma60')}")
    
    print(f"2. RSI (50 <= RSI <= 70): {details.get('rsi_score')} / 25")
    print(f"   - RSI Value: {details.get('rsi_val')}")
    
    print(f"3. MACD (MACD > Signal): {details.get('macd_score')} / 20")
    print(f"   - MACD Value: {details.get('macd_val')}")
    
    print(f"4. Volume (Vol > MA20): {details.get('vol_score')} / 15")
    
    print(f"5. RS Score (vs Benchmark): {details.get('rs_score')} / 15")
    
    print("\n[Reference Data]")
    print(f"USD/KRW: {result.get('usd_krw')}")
    print(f"Sectors Changes: {[s['name'] + ': ' + str(s['change_pct']) + '%' for s in result.get('sectors', [])]}")

if __name__ == "__main__":
    debug_score()
