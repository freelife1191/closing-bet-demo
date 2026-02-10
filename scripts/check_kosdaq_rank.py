
from pykrx import stock
import pandas as pd

def check_kosdaq_top_trading_value():
    date = "20260210"
    print(f"=== {date} KOSDAQ 거래대금 상위 10개 종목 ===")
    
    try:
        df = stock.get_market_ohlcv_by_ticker(date, market="KOSDAQ")
        df_sorted = df.sort_values(by="거래대금", ascending=False)
        
        top10 = df_sorted.head(10)
        for ticker, row in top10.iterrows():
            name = stock.get_market_ticker_name(ticker)
            val = row['거래대금']
            print(f"{name} ({ticker}): {val:,} 원 ({val//100000000} 억)")
            
        print("\n=== 거래대금 9000억 이상 종목 검색 ===")
        high_val_df = df_sorted[df_sorted['거래대금'] >= 900_000_000_000]
        if high_val_df.empty:
            print("거래대금 9000억 이상 종목 없음.")
        else:
            for ticker, row in high_val_df.iterrows():
                name = stock.get_market_ticker_name(ticker)
                print(f"발견 -> {name} ({ticker}): {row['거래대금']:,} 원")

    except Exception as e:
        print(f"조회 실패: {e}")

if __name__ == "__main__":
    check_kosdaq_top_trading_value()
