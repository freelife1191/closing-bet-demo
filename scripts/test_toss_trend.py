
import sys
import os
import logging
from pprint import pprint

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.toss_collector import TossCollector
from engine.screener import SmartMoneyScreener

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_toss_trend():
    print(">>> Testing TossCollector.get_investor_trend...")
    collector = TossCollector()
    
    # Samsung Electronics (005930) for testing
    code = "005930" 
    trend = collector.get_investor_trend(code, days=5)
    
    if trend:
        print(f"\n[Toss Trend Data for {code}]")
        print(f"Foreign Net Buy (5d): {trend.get('foreign')}")
        print(f"Institution Net Buy (5d): {trend.get('institution')}")
        
        details = trend.get('details', [])
        print(f"Details Count: {len(details)}")
        if details:
            print("All Details (Order Verification):")
            for i, d in enumerate(details):
                print(f"[{i}] Date: {d.get('date', 'N/A')}, Foreign: {d.get('netForeignerBuyVolume')}, Inst: {d.get('netInstitutionBuyVolume')}")
    else:
        print("Failed to fetch trend data.")

    print("\n>>> Testing SmartMoneyScreener._calculate_supply_score...")
    screener = SmartMoneyScreener()
    # Mock data loading not needed for this specific test as we test logic
    
    score_result = screener._calculate_supply_score(code)
    print(f"\n[Supply Score Result for {code}]")
    pprint(score_result)

if __name__ == "__main__":
    test_toss_trend()
