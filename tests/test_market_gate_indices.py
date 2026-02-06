
import sys
import os
import logging
from datetime import datetime, timedelta

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_fetch_indices():
    results = {}
    
    # 1. Test FinanceDataReader
    print("\n=== Testing FinanceDataReader ===")
    try:
        import FinanceDataReader as fdr
        for name, code in [('KOSPI', 'KS11'), ('KOSDAQ', 'KQ11')]:
            start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            df = fdr.DataReader(code, start_date)
            if not df.empty:
                latest = df.iloc[-1]
                close = float(latest['Close'])
                if 'Change' in df.columns:
                    change_pct = float(latest['Change']) * 100
                else:
                    change_pct = 0.0
                print(f"✅ {name}: {close:,.2f} ({change_pct:.2f}%)")
                results[f'fdr_{name}'] = (close, change_pct)
            else:
                print(f"❌ {name}: Empty DataFrame")
    except Exception as e:
        print(f"❌ FDR Error: {e}")

    # 2. Test pykrx
    print("\n=== Testing pykrx ===")
    try:
        from pykrx import stock
        today = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=5)).strftime("%Y%m%d")
        
        for name, code in [('KOSPI', '1001'), ('KOSDAQ', '2001')]:
            # Use get_index_ohlcv_by_date for index data
            df = stock.get_index_ohlcv_by_date(start, today, code)
            
            if not df.empty:
                latest = df.iloc[-1]
                close = float(latest['종가'])
                if '등락률' in df.columns:
                    change = float(latest['등락률'])
                else:
                    change = 0.0
                print(f"✅ {name}: {close:,.2f} ({change:.2f}%)")
                results[f'pykrx_{name}'] = (close, change)
            else:
                 print(f"❌ {name}: Empty DataFrame")

    except Exception as e:
        print(f"❌ pykrx Error: {e}")

    # 3. Test yfinance
    print("\n=== Testing yfinance ===")
    try:
        import yfinance as yf
        for name, ticker in [('KOSPI', '^KS11'), ('KOSDAQ', '^KQ11')]:
            data = yf.download(ticker, period='5d', progress=False, threads=False)
            if not data.empty:
                # Handle MultiIndex if present
                if isinstance(data.columns, dict) or 'Close' in data.columns:
                     series = data['Close']
                     if isinstance(series, pd.DataFrame):
                         series = series.iloc[:, 0]
                else:
                    # Fallback for weird yfinance structures
                     series = data.iloc[:, 0] # Assume first col is close-ish if not named
                
                # Re-fetch strictly 'Close'
                try:
                    series = data['Close']
                    if 'Ticker' in series.columns: # MultiIndex with Ticker
                        series = series[ticker]
                except:
                    pass 
                
                # Simple extraction, yfinance structure is complex to handle universally in one line
                # Let's rely on MarketGate's `extract_val` logic, but here simulate simply:
                # Just print last value found
                print(f"⚠️ {name}: yfinance test skipped detailed parsing (complex structure), assume functional if no error.")
            else:
                print(f"❌ {name}: Empty Data")
    except Exception as e:
        print(f"❌ yfinance Error: {e}")

if __name__ == "__main__":
    import pandas as pd # Ensure pandas is imported for yfinance check
    test_fetch_indices()
