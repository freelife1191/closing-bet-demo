
import sys
import os
import pandas as pd
from datetime import datetime, timedelta

# Add root to path
sys.path.append(os.getcwd())

from engine.screener import SmartMoneyScreener

class MockVCPResult:
    def __init__(self, score, is_vcp):
        self.vcp_score = score
        self.is_vcp = is_vcp
        self.entry_price = 10000
        self.contraction_ratio = 0.5

def verify_screener_logic():
    print("\n[Verifying Smart Money Screener 100pt Logic]")
    screener = SmartMoneyScreener()
    
    # Mock Data
    dates = pd.date_range(end=datetime.today(), periods=30, freq='D')
    
    # 1. Price Data for Volume Ratio
    # Avg Vol = 1000. Current Vol = 3500 (Ratio 3.5 -> Score 20)
    data_price = pd.DataFrame({
        'date': dates, 
        'ticker': '005930', 
        'close': 10000, 
        'high': 10500, 
        'low': 9500, 
        'volume': 1000
    })
    data_price.loc[29, 'volume'] = 3500 
    
    screener.prices_df = data_price
    
    # 2. Supply Data for Foreign/Inst
    # Foreign: Net Buy 600亿 (25pt) + 5 days consecutive (15pt) -> 40pt
    # Inst: Net Buy 300亿 (10pt) + 3 days consecutive (6pt) -> 16pt
    
    inst_data = []
    for i in range(30):
        row = {
            'date': dates[i].strftime('%Y-%m-%d'),
            'ticker': '005930',
            'foreign_net_buy': 0,
            'inst_net_buy': 0
        }
        # Last 5 days
        if i >= 25:
            row['foreign_net_buy'] = 120_00_000_000 # 120亿 * 5 = 600亿
            if i >= 27: # Last 3 days
                row['inst_net_buy'] = 100_00_000_000 # 100亿 * 3 = 300亿
        
        inst_data.append(row)
        
    screener.inst_df = pd.DataFrame(inst_data)
    
    # Mock VCP detection to return known score
    # We want VCP Score 100 -> Scaled to 10
    screener._detect_vcp_pattern = lambda df, stock: MockVCPResult(100, True)
    
    # Run Analysis
    stock_info = {'ticker': '005930', 'name': 'Samsung', 'market': 'KOSPI'}
    result = screener._analyze_stock(stock_info)
    
    if not result:
        print("❌ Analysis returned None")
        return

    print(f"Total Score: {result['score']}")
    
    # Expected:
    # Foreign: 25 (Net > 500亿) + 15 (5 days consec) = 40
    # Inst: 10 (Net > 200亿) + 6 (3 days consec) = 16
    # Vol Ratio: 20 (Ratio 3.5 > 3.0)
    # VCP: 10 (100 scaled to 10)
    # Total = 40 + 16 + 20 + 10 = 86
    
    expected = 86
    if result['score'] == expected:
        print(f"✅ Logic Verified! Score: {result['score']} (Expected {expected})")
    else:
        print(f"❌ Logic Mismatch! Score: {result['score']} (Expected {expected})")
        print("Breakdown checks needed if failed.")

if __name__ == "__main__":
    verify_screener_logic()
