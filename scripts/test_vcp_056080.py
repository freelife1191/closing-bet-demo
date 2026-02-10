
import sys
import os
import pandas as pd
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.screener import SmartMoneyScreener

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_vcp_056080():
    screener = SmartMoneyScreener()
    screener._load_data()
    
    # Manually create stock dict for 056080
    stock = {
        'ticker': '056080',
        'name': '유진로봇',
        'market': 'KOSDAQ'
    }
    
    print(">>> 056080 (유진로봇) VCP 분석 시작")
    result = screener._analyze_stock(stock)
    
    if result:
        print(f"\n[Result] Score: {result['score']}")
        print(f"[Result] Current Price: {result.get('current_price')}")
        print(f"[Result] Change Pct: {result.get('change_pct')}")
        print(f"[Result] Contraction Ratio: {result.get('contraction_ratio')}")
        print(f"[Result] Market Status: {result.get('market_status')}")
    else:
        print("\n[Result] Analysis Failed (Returned None)")

if __name__ == "__main__":
    test_vcp_056080()
