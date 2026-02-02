import yfinance as yf
from pykrx import stock
from datetime import datetime
import pandas as pd

def check_data():
    print("--- yfinance data ---")
    symbols = ['GC=F', 'SI=F', '^GSPC', '^IXIC', '^KS11', '^KQ11']
    data = yf.download(symbols, period='5d', progress=False)
    if not data.empty:
        print("Columns:", data.columns)
        print("Latest Data (Close):")
        print(data['Close'].iloc[-1])
    else:
        print("yfinance data is empty")

    print("\n--- pykrx data ---")
    krx_commodities = {
        'gold': '411060',  # ACE KRX금현물
        'silver': '144600' # KODEX 은선물(H)
    }
    today = datetime.now().strftime("%Y%m%d")
    start = "20260101"
    for name, ticker in krx_commodities.items():
        df = stock.get_market_ohlcv_by_date(start, today, ticker)
        if not df.empty:
            print(f"{name} ({ticker}): {df['종가'].iloc[-1]} (Change: {df['등락률'].iloc[-1]}%)")
        else:
            print(f"{name} ({ticker}): No data")

if __name__ == "__main__":
    check_data()
