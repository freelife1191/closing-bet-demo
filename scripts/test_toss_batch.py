import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.toss_collector import TossCollector
import json

def test_batch():
    collector = TossCollector()
    
    # 056080: 유진로봇 (9000억 이슈)
    # 005930: 삼성전자 (대형주)
    # 015760: 한화사이언스? (한국전력임 015760 -> 한국전력)
    target_codes = ['056080', '005930', '015760']
    
    print(f"Testing batch for: {target_codes}")
    
    try:
        results = collector.get_prices_batch(target_codes)
        
        print(f"Total results: {len(results)}")
        
        for code, data in results.items():
            print(f"[{code}] Current: {data['current']}, Value: {data['trading_value']:,} ({data['trading_value']//100000000}억)")
            
            if code == '056080':
                if data['trading_value'] > 500_000_000_000:
                    print("  -> PASS: Trading value > 500B confirmed.")
                else:
                    print(f"  -> FAIL: Trading value {data['trading_value']} < 500B")
                    
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_batch()
