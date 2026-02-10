
import sys
import os
import time
import threading
import json
import logging
from datetime import datetime

# Path setup
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock shared state
class MockShared:
    STOP_REQUESTED = False

import engine.shared
engine.shared.STOP_REQUESTED = False

from scripts import init_data
from app.routes import common

# Mock logging to avoid file spam
def mock_log(msg, level="INFO"):
    print(f"[{level}] {msg}")

init_data.log = mock_log
common.logger = logging.getLogger("mock")
common.logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
common.logger.addHandler(handler)

import logging

def test_yfinance_stop():
    print(">>> Testing yfinance stop responsiveness...")
    
    # Start a thread that pretends to be the background update
    # referencing the real init_data.fetch_prices_yfinance logic (mocked inputs)
    
    # We will trigger STOP after 2 seconds
    def trigger_stop():
        time.sleep(2)
        print("\n>>> TRIGGERING STOP REQUEST via API...")
        engine.shared.STOP_REQUESTED = True
        
    t = threading.Thread(target=trigger_stop)
    t.start()
    
    start_time = time.time()
    
    # Create dummy stocks file for yfinance to loop over
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
    stock_list_path = os.path.join(data_dir, 'korean_stocks_list.csv')
    
    # If not exists, create dummy
    if not os.path.exists(stock_list_path):
        with open(stock_list_path, 'w') as f:
            f.write("ticker,name,market\n")
            for i in range(100):
                f.write(f"000{i:03d},TestStock{i},KOSPI\n")
    
    # Call fetch_prices_yfinance with a long date range to force looping
    # Mock stock.get_market_ohlcv to fail so it falls back to yfinance?
    # Actually we can call fetch_prices_yfinance directly.
    
    from datetime import datetime, timedelta
    
    # Need existing_df empty
    import pandas as pd
    existing_df = pd.DataFrame()
    file_path = "temp_daily_prices.csv"
    
    start_date = datetime.now() - timedelta(days=50) # Enough for loop
    end_date = datetime.now()
    
    print(">>> Calling fetch_prices_yfinance directly...")
    result = init_data.fetch_prices_yfinance(start_date, end_date, existing_df, file_path)
    
    end_time = time.time()
    duration = end_time - start_time
    
    print(f"\n>>> Function returned: {result}")
    print(f">>> Duration: {duration:.2f} seconds")
    
    if duration < 10 and result is False: 
        print(">>> SUCCESS: Stopped quickly!")
    elif duration > 10:
        print(">>> FAIL: Took too long, stop check failed? (Or loop finished)")
    else:
        print(">>> RESULT: " + str(result))

    if os.path.exists(file_path):
        os.remove(file_path)

if __name__ == "__main__":
    test_yfinance_stop()
