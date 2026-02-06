
import FinanceDataReader as fdr
import yfinance as yf
from pykrx import stock
from datetime import datetime, timedelta
import pandas as pd

def diagnose():
    today_str = datetime.now().strftime("%Y%m%d")
    start_str = (datetime.now() - timedelta(days=10)).strftime("%Y%m%d")
    
    print(f"Current System Time: {datetime.now()}")
    
    # 1. KOSPI Comparison
    print("\n--- KOSPI Comparison ---")
    # pykrx
    try:
        df_pykrx = stock.get_index_ohlcv_by_date(start_str, today_str, "1001")
        if not df_pykrx.empty:
            print(f"pykrx (1001): {df_pykrx.iloc[-1]['종가']} (Date: {df_pykrx.index[-1]})")
        else:
            print("pykrx (1001): Empty")
    except Exception as e:
        print(f"pykrx Error: {e}")

    # FDR
    try:
        df_fdr = fdr.DataReader('KS11', datetime.now() - timedelta(days=10))
        if not df_fdr.empty:
            print(f"FDR (KS11): {df_fdr.iloc[-1]['Close']} (Date: {df_fdr.index[-1]})")
        else:
            print("FDR (KS11): Empty")
    except Exception as e:
        print(f"FDR Error: {e}")

    # yfinance
    try:
        df_yf = yf.download('^KS11', period='5d', progress=False)
        if not df_yf.empty:
            val = df_yf.iloc[-1]['Close']
            # handle multiindex if present
            if isinstance(val, (pd.Series, pd.DataFrame)): val = val.iloc[0]
            print(f"yfinance (^KS11): {val} (Date: {df_yf.index[-1]})")
    except Exception as e:
        print(f"yfinance Error: {e}")

    # 2. Bitcoin Comparison
    print("\n--- BTC Comparison ---")
    try:
        df_btc_fdr = fdr.DataReader('BTC/USD', datetime.now() - timedelta(days=5))
        if not df_btc_fdr.empty:
            print(f"FDR (BTC/USD): {df_btc_fdr.iloc[-1]['Close']} (Date: {df_btc_fdr.index[-1]})")
    except Exception as e:
        print(f"FDR BTC Error: {e}")

    try:
        df_btc_yf = yf.download('BTC-USD', period='5d', progress=False)
        if not df_btc_yf.empty:
            val = df_btc_yf.iloc[-1]['Close']
            if isinstance(val, (pd.Series, pd.DataFrame)): val = val.iloc[0]
            print(f"yfinance (BTC-USD): {val} (Date: {df_btc_yf.index[-1]})")
    except Exception as e:
        print(f"yfinance BTC Error: {e}")

if __name__ == "__main__":
    diagnose()
