from pykrx import stock
import pandas as pd
from datetime import datetime, timedelta

# SFA반도체
code = "036540"
date_str = "20260130"

print(f"--- Checking Market Data for {date_str} ---")
try:
    df = stock.get_market_ohlcv_by_ticker(date_str, market="KOSDAQ")
    if code in df.index:
        row = df.loc[code]
        print(f"Stock: SFA반도체 ({code})")
        print(f"Close: {row['종가']}")
        print(f"Change: {row['등락률']}")
        print(f"Volume: {row['거래량']}")
        print(f"Trading Value: {row['거래대금']}")
        print(f"Market Cap: {row['시가총액']}")
    else:
        print(f"Code {code} not found in KOSDAQ data for {date_str}")
except Exception as e:
    print(f"Error getting ticker data: {e}")

print(f"\n--- Checking Chart Data (Volume Ratio) ---")
try:
    # 30일치 조회
    start_date = "20260101"
    end_date = "20260130"
    df = stock.get_market_ohlcv_by_date(start_date, end_date, code)
    print(df.tail(5))
    
    # 거래량 배수 계산 직접 해보기
    volumes = df['거래량'].tolist()
    if len(volumes) >= 5:
        today_vol = volumes[-1]
        lookback = min(20, len(volumes) - 1)
        avg_vol = sum(volumes[-lookback-1:-1]) / lookback
        ratio = round(today_vol / avg_vol, 2)
        print(f"\nCalculated Volume Ratio: {ratio} (Today: {today_vol}, Avg: {avg_vol:.0f})")
except Exception as e:
    print(f"Error getting chart data: {e}")
