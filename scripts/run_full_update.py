
import sys
import os
import logging

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scripts.init_data import create_daily_prices, create_institutional_trend, create_jongga_v2_latest

# Configure logging
logging.basicConfig(level=logging.INFO)

print(">>> Starting Full Data Update...")

print("\n1. Collecting Institutional Trend...")
try:
    if create_institutional_trend():
        print("   -> Success")
    else:
        print("   -> Failed or No Data")
except Exception as e:
    print(f"   -> Error: {e}")

print("\n2. Collecting Daily Prices...")
try:
    if create_daily_prices():
        print("   -> Success")
    else:
        print("   -> Failed")
except Exception as e:
    print(f"   -> Error: {e}")

print("\n3. Generating Signals (Jongga V2)...")
try:
    result = create_jongga_v2_latest()
    print(f"   -> Result: {result}")
except Exception as e:
    print(f"   -> Error: {e}")

print("\n>>> Update Complete.")
