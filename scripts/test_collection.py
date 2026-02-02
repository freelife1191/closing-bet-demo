
import sys
import os
import logging

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scripts.init_data import create_daily_prices, create_institutional_trend
# Configure logging
logging.basicConfig(level=logging.INFO)

print(">>> Testing Daily Prices Collection...")
try:
    create_daily_prices()
except Exception as e:
    print(f"!!! Daily Prices Failed: {e}")

print("\n>>> Testing Institutional Trend Collection...")
try:
    create_institutional_trend()
except Exception as e:
    print(f"!!! Institutional Trend Failed: {e}")
