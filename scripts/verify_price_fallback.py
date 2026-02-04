
import sys
import os
import requests
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import init_data

def test_toss_fallback():
    print("\n[TEST 1] Testing Toss API Fallback (Simulating yfinance failure)...")
    
    # Force yfinance unavailable
    original_availability = init_data.YFINANCE_AVAILABLE
    init_data.YFINANCE_AVAILABLE = False
    
    try:
        # Samsung Electronics
        ticker = "005930"
        result = init_data.fetch_stock_price(ticker)
        
        if result and result.get('price') > 0:
            print(f"✅ Success! Got price via Toss (assumed): {result}")
        else:
            print(f"❌ Failed to get price. Result: {result}")
            
    finally:
        init_data.YFINANCE_AVAILABLE = original_availability

def test_naver_fallback():
    print("\n[TEST 2] Testing Naver API Fallback (Simulating yfinance & Toss failure)...")
    
    # Force yfinance unavailable
    original_availability = init_data.YFINANCE_AVAILABLE
    init_data.YFINANCE_AVAILABLE = False
    
    # Mock requests.get to fail for Toss but work for Naver
    original_get = requests.get
    
    def side_effect(*args, **kwargs):
        url = args[0]
        if "tossinvest" in url:
            print(f"   -> Intercepted Toss request to {url}, simulating failure.")
            raise Exception("Simulated Toss API Failure")
        return original_get(*args, **kwargs)
    
    with patch('requests.get', side_effect=side_effect):
        try:
            ticker = "005930"
            result = init_data.fetch_stock_price(ticker)
            
            if result and result.get('price') > 0:
                print(f"✅ Success! Got price via Naver (assumed): {result}")
            else:
                print(f"❌ Failed to get price via Naver. Result: {result}")
        except Exception as e:
             print(f"❌ Exception during test: {e}")

    init_data.YFINANCE_AVAILABLE = original_availability

if __name__ == "__main__":
    print("Starting Fallback Verification...")
    test_toss_fallback()
    test_naver_fallback()
