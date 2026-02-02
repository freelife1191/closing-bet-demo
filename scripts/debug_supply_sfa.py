from pykrx import stock
import pandas as pd
from datetime import datetime, timedelta

# SFA반도체
code = "036540"
end_date = "20260130"
start_date = "20260120" # 넉넉하게 10일 전

print(f"--- Checking Supply Data for {code} ({start_date} ~ {end_date}) ---")

try:
    df = stock.get_market_trading_value_by_date(start_date, end_date, code)
    
    if df.empty:
        print("Data is empty!")
    else:
        print(f"Total Rows: {len(df)}")
        print(df.tail(10))
        
        last_5 = df.tail(5)
        print("\n--- Last 5 Days ---")
        print(last_5)
        
        foreign_col = '외국인합계' if '외국인합계' in df.columns else '외국인'
        inst_col = '기관합계' if '기관합계' in df.columns else '기관'
        
        f_sum = last_5[foreign_col].sum()
        i_sum = last_5[inst_col].sum()
        
        print(f"\n--- 5-Day Sum ---")
        print(f"Foreign ({foreign_col}): {f_sum:,.0f} ({f_sum/100000000:.2f}억)")
        print(f"Institutional ({inst_col}): {i_sum:,.0f} ({i_sum/100000000:.2f}억)")

except Exception as e:
    print(f"Error: {e}")
