
import FinanceDataReader as fdr

def test_fdr_variants():
    # KOSPI is usually KS11
    symbols = ['KS11', 'KOSPI', 'KRX:1001', 'KRX:KOSPI']
    for sym in symbols:
        try:
            df = fdr.DataReader(sym)
            if not df.empty:
                 print(f"FDR [{sym}]: {df.iloc[-1]['Close']}")
            else:
                 print(f"FDR [{sym}]: Empty")
        except Exception as e:
            print(f"FDR [{sym}]: Error {e}")

if __name__ == "__main__":
    test_fdr_variants()
