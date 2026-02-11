
import sys
import os
import logging

# Add current directory to sys.path
sys.path.append(os.getcwd())

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("reproduce")

try:
    from scripts import init_data
    print("Successfully imported init_data")
except ImportError as e:
    print(f"Failed to import init_data: {e}")
    sys.exit(1)

def main():
    print("=== Starting Reproduction Script ===")
    
    # 1. Test Korean Stocks List Creation
    print("\n[Step 1] Creating Korean Stocks List...")
    try:
        result = init_data.create_korean_stocks_list()
        print(f"Result: {result}")
        if os.path.exists("data/korean_stocks_list.csv"):
             print("SUCCESS: data/korean_stocks_list.csv created.")
        else:
             print("FAILURE: data/korean_stocks_list.csv NOT created.")
    except Exception as e:
        print(f"EXCEPTION in create_korean_stocks_list: {e}")
        import traceback
        traceback.print_exc()

    # 2. Test Daily Prices Creation
    print("\n[Step 2] Creating Daily Prices...")
    try:
        # Using a specific date or None for today. 
        # Using None to match typical usage in generator.py
        result = init_data.create_daily_prices(target_date=None, force=True) 
        print(f"Result: {result}")
        if os.path.exists("data/daily_prices.csv"):
             print("SUCCESS: data/daily_prices.csv created.")
        else:
             print("FAILURE: data/daily_prices.csv NOT created.")
    except Exception as e:
        print(f"EXCEPTION in create_daily_prices: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
