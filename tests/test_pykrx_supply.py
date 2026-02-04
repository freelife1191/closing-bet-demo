import pandas as pd
from pykrx import stock
from datetime import datetime
import os

def test_fetch():
    target_date = "20260203"
    print(f"Testing fetch for {target_date} (KOSDAQ/Neuromeca)...")
    
    # 1. 외국인 순매수 (전 종목)
    try:
        df_foreign = stock.get_market_net_purchases_of_equities_by_ticker(target_date, target_date, "ALL", "외국인")
        print(f"Total tickers returned (Foreign): {len(df_foreign)}")
        
        if "348340" in df_foreign.index:
            print(f"Neuromeca (348340) found in Foreign list! Value: {df_foreign.loc['348340', '순매수거래대금']}")
        else:
            print("ERROR: Neuromeca NOT found in Foreign ALL list.")
            
        # Try KOSDAQ specifically
        df_kosdaq = stock.get_market_net_purchases_of_equities_by_ticker(target_date, target_date, "KOSDAQ", "외국인")
        if "348340" in df_kosdaq.index:
            print(f"Neuromeca found in KOSDAQ specifically. Value: {df_kosdaq.loc['348340', '순매수거래대금']}")

    except Exception as e:
        print(f"Error during fetch: {e}")

if __name__ == "__main__":
    test_fetch()
