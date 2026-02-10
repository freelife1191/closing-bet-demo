
from pykrx import stock

def find_9641():
    date = "20260210"
    print(f"=== {date} 거래대금 9000억 ~ 1조원 종목 검색 ===")
    
    found = False
    for market in ["KOSPI", "KOSDAQ"]:
        try:
            df = stock.get_market_ohlcv_by_ticker(date, market=market)
            # 9000억 ~ 10000억
            target = df[(df['거래대금'] >= 900_000_000_000) & (df['거래대금'] <= 1_100_000_000_000)]
            
            for ticker, row in target.iterrows():
                name = stock.get_market_ticker_name(ticker)
                val = row['거래대금']
                print(f"[{market}] {name} ({ticker}): {val:,} 원 ({val//100000000} 억)")
                found = True
        except:
            pass
            
    if not found:
        print("해당 구간(9000억~1.1조) 종목 없음.")

if __name__ == "__main__":
    find_9641()
