from pykrx import stock
from datetime import datetime
import pandas as pd

target_date = "20260203"
print(f"Target Date: {target_date}")

try:
    # 1. 외국인 순매수 (전 종목)
    df_foreign = stock.get_market_net_purchases_of_equities_by_ticker(target_date, target_date, "ALL", "외국인")
    print(f"Foreign Data count: {len(df_foreign)}")
    
    # 2. 기관 순매수 (전 종목)
    df_inst = stock.get_market_net_purchases_of_equities_by_ticker(target_date, target_date, "ALL", "기관합계")
    print(f"Institutional Data count: {len(df_inst)}")

except Exception as e:
    print(f"Error: {e}")
