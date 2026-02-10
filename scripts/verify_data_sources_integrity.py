
import sys
import os
import json
import logging
from datetime import datetime, timedelta
import pandas as pd

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("VERIFY")

from engine.data_sources import fetch_stock_price, fetch_investor_trend_naver
# We need to test the fallback logic, so we might need to mock within the test or just test the aggregate result.
# To ensure "Naver works", we should try to call the Naver logic specifically. 
# Since fetch_stock_price is a chain, we can't easily isolate Naver without mocking Toss to fail.

def test_fetch_stock_price_toss():
    print(f"\n[{datetime.now().time()}] === Testing Toss API (via fetch_stock_price) ===")
    ticker = "005930" # Samsung Electronics
    try:
        # Toss is the first priority, so calling fetch_stock_price directly tests Toss first.
        data = fetch_stock_price(ticker)
        if data and data.get('source') == 'toss':
            print(f"✅ Toss API Success for {ticker}: {data}")
            return True
        else:
            print(f"⚠️ Toss API Return/Source mismatch: {data}")
            return False
    except Exception as e:
        print(f"❌ Toss API Failed: {e}")
        return False

def test_fetch_stock_price_naver():
    print(f"\n[{datetime.now().time()}] === Testing Naver API (Direct Request) ===")
    # We copy the logic from data_sources.py to test it in isolation
    import requests
    ticker = "005930"
    try:
        naver_url = f"https://m.stock.naver.com/api/stock/{str(ticker).zfill(6)}/basic"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(naver_url, headers=headers, timeout=5)
        
        if res.status_code == 200:
            data = res.json()
            print(f"✅ Naver API Response received")
            if 'closePrice' in data:
                price = data['closePrice']
                print(f"   -> closePrice: {price}")
                return True
            else:
                print(f"❌ Naver API missing 'closePrice' in response: {data.keys()}")
                return False
        else:
            print(f"❌ Naver API Status Code: {res.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Naver API Exception: {e}")
        return False

def test_fetch_investor_trend_naver():
    print(f"\n[{datetime.now().time()}] === Testing Naver Investor Trend API ===")
    ticker = "005930"
    try:
        # direct import test
        data = fetch_investor_trend_naver(ticker)
        if data and 'foreign' in data and 'institution' in data:
            print(f"✅ Naver Trend API Success for {ticker}: {data}")
            return True
        else:
            print(f"❌ Naver Trend API returned invalid data: {data}")
            return False
    except Exception as e:
        print(f"❌ Naver Trend API Exception: {e}")
        return False

def test_yfinance_download():
    print(f"\n[{datetime.now().time()}] === Testing yfinance Download ===")
    import yfinance as yf
    ticker = "005930.KS"
    try:
        # Test the exact call used in init_data: progress=False, threads=False
        df = yf.download(ticker, period="5d", progress=False, threads=False)
        if not df.empty:
            print(f"✅ yfinance Success for {ticker}: {len(df)} rows fetching")
            print(df.tail(2))
            return True
        else:
            print(f"❌ yfinance returned empty DataFrame")
            return False
    except Exception as e:
        print(f"❌ yfinance Exception: {e}")
        return False

def test_yfinance_fallback_function():
    print(f"\n[{datetime.now().time()}] === Testing init_data.fetch_prices_yfinance Logic ===")
    import scripts.init_data as init_data
    
    # Mocking shared_state to ensure it doesn't stop immediately
    class MockShared:
        STOP_REQUESTED = False
    init_data.shared_state = MockShared()
    
    # Create a dummy dataframe and call the function with a SINGLE ticker to test the logic
    # We need to temporarily force init_data to look at a dummy ticker list
    
    # 1. Create dummy stocks list
    original_base_dir = init_data.BASE_DIR
    dummy_stocks_path = os.path.join(original_base_dir, 'data', 'korean_stocks_list.csv')
    backup_path = dummy_stocks_path + ".bak"
    
    # Backup existing
    if os.path.exists(dummy_stocks_path):
        os.rename(dummy_stocks_path, backup_path)
        
    try:
        # Write dummy list
        pd.DataFrame([{'ticker': '005930', 'name': 'Samsung', 'market': 'KOSPI'}]).to_csv(dummy_stocks_path, index=False)
        
        # 2. Call function
        start_date = datetime.now() - timedelta(days=3)
        end_date = datetime.now()
        existing_df = pd.DataFrame()
        temp_output = "temp_yf_test.csv"
        
        print("   -> Calling fetch_prices_yfinance...")
        result = init_data.fetch_prices_yfinance(start_date, end_date, existing_df, temp_output)
        
        if result and os.path.exists(temp_output):
             df = pd.read_csv(temp_output)
             if not df.empty:
                 print(f"✅ fetch_prices_yfinance produced data: {len(df)} rows")
                 return True
             else:
                 print(f"❌ fetch_prices_yfinance produced empty file")
                 return False
        else:
            print(f"❌ fetch_prices_yfinance returned False or no file")
            return False
            
    except Exception as e:
        print(f"❌ fetch_prices_yfinance Exception: {e}")
        return False
    finally:
        # Cleanup
        if os.path.exists(backup_path):
            os.replace(backup_path, dummy_stocks_path)
        if os.path.exists("temp_yf_test.csv"):
            os.remove("temp_yf_test.csv")

if __name__ == "__main__":
    results = []
    results.append(test_fetch_stock_price_toss())
    results.append(test_fetch_stock_price_naver())
    results.append(test_fetch_investor_trend_naver())
    results.append(test_yfinance_download())
    results.append(test_yfinance_fallback_function())
    
    print("\n" + "="*30)
    if all(results):
        print("🎉 ALL DATA SOURCE TESTS PASSED")
    else:
        print("🔥 SOME TESTS FAILED - CHECK LOGS ABOVE")
