
import yfinance as yf
from pykrx import stock
import FinanceDataReader as fdr
from datetime import datetime

def test_fixed_date():
    target_date = "2025-02-06"
    print(f"Testing for FIXED DATE: {target_date}")
    
    # 1. yfinance
    try:
        df_yf = yf.download('^KS11', start="2025-02-05", end="2025-02-07", progress=False)
        if not df_yf.empty:
            print(f"yfinance (^KS11) on {target_date}: {df_yf.iloc[-1]['Close']}")
        else:
            print(f"yfinance (^KS11) on {target_date}: Empty")
    except Exception as e:
        print(f"yfinance Error: {e}")

    # 2. FDR
    try:
        df_fdr = fdr.DataReader('KS11', "2025-02-05", "2025-02-07")
        if not df_fdr.empty:
            print(f"FDR (KS11) on {target_date}: {df_fdr.iloc[-1]['Close']}")
        else:
            print(f"FDR (KS11) on {target_date}: Empty")
    except Exception as e:
        print(f"FDR Error: {e}")

    # 3. pykrx
    try:
        df_pykrx = stock.get_index_ohlcv_by_date("20250205", "20250207", "1001")
        if not df_pykrx.empty:
            print(f"pykrx (1001) on {target_date}: {df_pykrx.iloc[-1]['종가']}")
        else:
            print(f"pykrx (1001) on {target_date}: Empty")
    except Exception as e:
        print(f"pykrx Error: {e}")

if __name__ == "__main__":
    test_fixed_date()
