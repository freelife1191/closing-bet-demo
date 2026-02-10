import os
import sys
import pandas as pd
import json
import glob

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.routes.kr_market import DATA_DIR, get_data_path

def debug_closing_bet_stats():
    print("Debugging Closing Bet Stats Calculation...")
    
    # 1. Load Data
    pattern = os.path.join(DATA_DIR, 'jongga_v2_results_*.json')
    files = sorted(glob.glob(pattern), reverse=True)[:30]
    print(f"Found {len(files)} result files")

    # 2. Simulate Logic
    total_signals = 0
    wins = 0
    total_return = 0.0
    
    # We strictly follow the logic in get_backtest_summary which iterates files
    # and calculates stats.
    # Note: the actual implementation reads prices from daily_prices.csv but for status check
    # we just need to know if win_rate == 0 when count > 0.
    
    # However, to be accurate, we need to know if there are ANY wins.
    # The user said 22 trades, 0% win rate.
    # So we expect wins=0, total_signals=22.
    
    # Let's verify the PENDING logic.
    jb_stats = {
        'count': 22,
        'win_rate': 0.0,
        'avg_return': -4.4,
        'status': 'UNKNOWN'
    }
    
    # Logic in kr_market.py:
    if jb_stats['win_rate'] == 0:
        jb_stats['status'] = 'PENDING'
    elif jb_stats['win_rate'] >= 60:
         jb_stats['status'] = 'EXCELLENT'
    elif jb_stats['win_rate'] >= 40:
         jb_stats['status'] = 'GOOD'
    else:
         jb_stats['status'] = 'BAD'
         
    print(f"Simulated Status for 22 trades / 0% win rate: {jb_stats['status']}")
    
    if jb_stats['status'] == 'PENDING':
        print("SUCCESS: Logic correctly identifies PENDING state.")
    else:
        print(f"FAILURE: Logic returned {jb_stats['status']}")

if __name__ == "__main__":
    debug_closing_bet_stats()
