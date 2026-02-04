from pykrx import stock
from datetime import datetime
import pandas as pd

target_date = "20260204"
print(f"Target Date: {target_date}")

try:
    # 1. 외국인 순매수 (전 종목)
    df_foreign = stock.get_market_net_purchases_of_equities_by_ticker(target_date, target_date, "ALL", "외국인")
    print(f"Foreign Data count: {len(df_foreign)}")
    if not df_foreign.empty:
        print("Foreign Sample:")
        print(df_foreign.head())
    
    # 2. 기관 순매수 (전 종목)
    df_inst = stock.get_market_net_purchases_of_equities_by_ticker(target_date, target_date, "ALL", "기관합계")
    print(f"Institutional Data count: {len(df_inst)}")
    if not df_inst.empty:
        print("Institutional Sample:")
        print(df_inst.head())

    # 3. KOSDAQ 특정 종목 (티로보틱스 117730) 확인
    ticker = "117730"
    if ticker in df_foreign.index:
        print(f"\nTicker {ticker} (티로보틱스) Foreign: {df_foreign.loc[ticker, '순매수거래대금']}")
    if ticker in df_inst.index:
        print(f"Ticker {ticker} (티로보틱스) Inst: {df_inst.loc[ticker, '순매수거래대금']}")

except Exception as e:
    print(f"Error: {e}")
