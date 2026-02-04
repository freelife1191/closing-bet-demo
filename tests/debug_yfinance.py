
import yfinance as yf
import pandas as pd

def test_fetch():
    ticker_map = {
        'sp500': '^GSPC', 
        'nasdaq': '^IXIC',
        'kospi': '^KS11', 
        'kosdaq': '^KQ11'
    }
    symbols = list(ticker_map.values())
    print(f"Downloading symbols: {symbols}")
    
    try:
        data = yf.download(symbols, period='1mo', progress=False)
        print("\nData Columns:")
        print(data.columns)
        print("\nData Head:")
        print(data.head())
        
        print("\nChecking individual symbols:")
        for name, symbol in ticker_map.items():
            print(f"\n--- {name} ({symbol}) ---")
            try:
                if isinstance(data.columns, pd.MultiIndex):
                    if symbol in data['Close'].columns:
                        series = data['Close'][symbol].dropna()
                        print(f"Found in MultiIndex. Last value: {series.iloc[-1]}")
                        
                        # Test timezone removal
                        try:
                            print(f"Index TZ info: {series.index.tz}")
                            series.index = series.index.tz_localize(None)
                            print("tz_localize(None) successful")
                        except Exception as e:
                            print(f"tz_localize(None) failed: {e}")
                            
                    else:
                        print("Not found in MultiIndex['Close']")
                else:
                    # If single level, maybe it is just the columns?
                    if symbol in data.columns:
                         # This part in original code was: series = data['Close'].dropna() which looks wrong if multiple symbols
                         # But wait, if multiple symbols request results in single level, it usually means flattened.
                         # Let's inspect data.columns again.
                         pass
                    print(f"Columns are: {data.columns}")
            except Exception as e:
                print(f"Error extracting: {e}")

    except Exception as e:
        print(f"Download failed: {e}")

    print("\n\n=== Testing Single Ticker Scenario ===")
    try:
        # Only KOSPI
        symbols = ['^KS11']
        data = yf.download(symbols, period='1mo', progress=False)
        print("\nData Columns (Single):")
        print(data.columns)
        
        symbol = '^KS11'
        if isinstance(data.columns, pd.MultiIndex):
            print("Is MultiIndex")
        else:
             print("Is NOT MultiIndex")
             if symbol in data.columns:
                 print(f"Symbol {symbol} found in columns")
             else:
                 print(f"Symbol {symbol} NOT found in columns: {data.columns}")
                 
    except Exception as e:
        print(f"Single download failed: {e}")

if __name__ == "__main__":
    test_fetch()
