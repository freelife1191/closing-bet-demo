import os
import sys
import pandas as pd
import logging
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.screener import SmartMoneyScreener

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def test_vcp_screening():
    print("="*60)
    print("VCP Signals Screener Verification Test")
    print("="*60)
    
    screener = SmartMoneyScreener() # Uses today's date
    
    print(f"Base Date: {datetime.now().strftime('%Y-%m-%d')}")
    print("Phase 1: Loading Data and Checking Market Gate...")
    
    # Run screening with a reasonable number of stocks to check, 
    # but since filtering happens inside, we scan more to find hits.
    # The screener inside analyzes stocks serially. 
    # Let's inspect the `_analyze_stock` method behavior by monkey-patching or just trusting the result.
    # For verification, we want to see WHY stocks fail if count is low.
    
    # Note: `run_screening` inside screener.py limits to max_stocks stocks if passed. 
    # Default is 50, which might be too small if VCP is rare.
    # Let's increase max_stocks for test or analyze specific known candidates if we knew them.
    # Since we don't know which ones are VCP, let's scan 300 stocks to be safe.
    
    MAX_STOCKS = 300 
    print(f"Scanning first {MAX_STOCKS} stocks...")
    
    try:
        results = screener.run_screening(max_stocks=MAX_STOCKS)
        
        if results.empty:
            print("\n❌ No signals found in the scanned batch.")
        else:
            print(f"\n✅ Signals found: {len(results)}")
            
            print("\n[Detected VCP Signals]")
            for _, row in results.iterrows():
                print(f"[{row['ticker']}] {row['name']}")
                print(f"  Score: {row['score']:.1f} (VCP Metric: {row.get('contraction_ratio', 0):.2f})")
                print(f"  Supply: Foreign {row['foreign_net_5d']:,} / Inst {row['inst_net_5d']:,}")
                print(f"  Entry: {row['entry_price']:,} KRW")
                print("-" * 40)
                
    except Exception as e:
        print(f"\n❌ Error during screening: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_vcp_screening()
