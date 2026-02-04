import yfinance as yf
import sys

tickers = ['005380.KS', '452260.KS', '45226K.KS', '0452260.KS', '005930.KS']
print(f"Testing yfinance for: {tickers}")

try:
    df = yf.download(tickers, period="1d", progress=False, threads=False)
    print("\nDownload Result DataFrame:")
    print(df)
    
    if not df.empty:
        print("\nColumns:", df.columns)
        
        # Test extraction logic
        print("\nExtraction Test:")
        
        # Check if MultiIndex
        is_multi = isinstance(df.columns, tuple) or (hasattr(df.columns, 'nlevels') and df.columns.nlevels > 1)
        print(f"Is MultiIndex: {is_multi}")
        
        if is_multi:
             try:
                closes = df['Close']
                print("\n'Close' level:")
                print(closes)
             except KeyError:
                print("'Close' key not found in top level")
        else:
             print("\nFlat columns or single level")
             if 'Close' in df.columns:
                 print(df['Close'])
             else:
                 print(df)

except Exception as e:
    print(f"Error: {e}")
