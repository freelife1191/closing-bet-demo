import yfinance as yf

tickers = ["004560.KS", "038460.KQ", "084670.KS"] # Hyundai BNG Steel, BioSmart, Dongyang Express
print(f"Fetching info for {tickers}...")

for t in tickers:
    try:
        info = yf.Ticker(t).info
        print(f"\n--- {t} ---")
        print(f"Sector: {info.get('sector', 'N/A')}")
        print(f"Industry: {info.get('industry', 'N/A')}")
    except Exception as e:
        print(f"Error {t}: {e}")
