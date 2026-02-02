import sys
import os
import pandas as pd
import logging
from engine.market_gate import MarketGate

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TEST")

# Create a dummy empty CSV with headers
csv_path = 'test_empty_supply.csv'
with open(csv_path, 'w') as f:
    f.write("date,foreign_buy,inst_buy\n") # Header only

# Create dummy CSV with filterable data (if logic filtered it?)
# But there is no filtering in _load_supply_data, only sort.

def test_load():
    mg = MarketGate(data_dir='.')
    # Monkeypatch data_dir logic or just symlink?
    # Actually MarketGate(data_dir='.') uses current dir.
    # But it looks for 'all_institutional_trend_data.csv'.
    
    # Rename test file temporarily
    real_path = 'all_institutional_trend_data.csv'
    if os.path.exists(real_path):
        os.rename(real_path, real_path + '.bak')
    
    try:
        # Case 1: Header Only
        with open(real_path, 'w') as f:
            f.write("date,foreign_buy,inst_buy\n")
        
        print("Testing Case 1: Header Only CSV")
        result = mg._load_supply_data()
        print(f"Result 1: {result}")
        
        # Case 2: Completely Empty
        with open(real_path, 'w') as f:
            pass # Empty
        
        print("Testing Case 2: Zero Byte File")
        result = mg._load_supply_data()
        print(f"Result 2: {result}")
        
        # Case 3: One row
        with open(real_path, 'w') as f:
            f.write("date,foreign_buy,inst_buy\n2025-01-01,100,200\n")
        
        print("Testing Case 3: One Row")
        result = mg._load_supply_data()
        print(f"Result 3: {result}")

    except Exception as e:
        print(f"CRASHED: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        if os.path.exists(real_path):
            os.remove(real_path)
        if os.path.exists(real_path + '.bak'):
            os.rename(real_path + '.bak', real_path)

if __name__ == "__main__":
    test_load()
