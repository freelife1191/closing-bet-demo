
from pykrx import stock
import pandas as pd

def check_kospi_and_investors():
    date = "20260210"
    ticker = "056080"
    
    print(f"=== {date} KOSPI 거래대금 상위 5개 ===")
    try:
        df = stock.get_market_ohlcv_by_ticker(date, market="KOSPI")
        df_sorted = df.sort_values(by="거래대금", ascending=False)
        for t, r in df_sorted.head(5).iterrows():
            name = stock.get_market_ticker_name(t)
            print(f"{name}: {r['거래대금']//100000000} 억")
            
        # 9000억 이상 있는지
        high_val = df_sorted[df_sorted['거래대금'] >= 900_000_000_000]
        if not high_val.empty:
            print("\n[KOSPI 9000억 이상]")
            for t, r in high_val.iterrows():
                name = stock.get_market_ticker_name(t)
                print(f"{name}: {r['거래대금']//100000000} 억")
    except: pass

    print(f"\n=== 유진로봇({ticker}) 투자자별 매매동향 ===")
    try:
        # 투자자별 순매수 (종목별)
        # get_market_net_purchases_of_equities_by_ticker(date, date, ticker)
        inv_df = stock.get_market_net_purchases_of_equities_by_ticker(date, date, ticker)
        print(inv_df)
        
    except Exception as e:
        print(f"투자자 조회 실패: {e}")

if __name__ == "__main__":
    check_kospi_and_investors()
