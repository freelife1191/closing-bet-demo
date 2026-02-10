
from pykrx import stock
from datetime import datetime, timedelta
import pandas as pd

def check_volume_ratio():
    code = "056080" # 유진로봇
    target_date_str = "20260210"
    target_date = datetime.strptime(target_date_str, "%Y%m%d")
    
    # 1. Get 20 days data before today
    # Fetch enough days to ensure 20 trading days
    start_date = (target_date - timedelta(days=40)).strftime("%Y%m%d")
    end_date = (target_date - timedelta(days=1)).strftime("%Y%m%d")
    
    print(f"Fetching data from {start_date} to {end_date} for {code}...")
    
    df = stock.get_market_ohlcv_by_date(start_date, end_date, code)
    
    if df.empty:
        print("No data found.")
        return

    # Last 20 rows
    last_20 = df.tail(20)
    print(f"Found {len(last_20)} trading days.")
    
    avg_vol = last_20['거래량'].mean()
    print(f"20-day Average Volume (KRX): {avg_vol:,.0f}")
    
    # 2. Compare with KRX Today
    # KRX Today (from previous checks)
    krx_today_vol = 8_322_414 # From verify log
    krx_ratio = krx_today_vol / avg_vol
    print(f"KRX Today Volume: {krx_today_vol:,.0f}")
    print(f"KRX Ratio: {krx_ratio:.2f}x")
    
    # 3. Compare with Toss Today
    toss_today_vol = 21_526_307 # From verify log
    toss_ratio = toss_today_vol / avg_vol
    print(f"Toss Today Volume: {toss_today_vol:,.0f}")
    print(f"Toss Ratio: {toss_ratio:.2f}x")
    
    if toss_ratio >= 2.0:
        print("CONCLUSION: Toss Volume Ratio is > 2.0 (Double confirmed)")
    else:
        print("CONCLUSION: Toss Volume Ratio is < 2.0")

if __name__ == "__main__":
    check_volume_ratio()
