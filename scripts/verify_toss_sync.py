
import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.config import config
from engine.models import StockData
from engine.generator import SignalGenerator

async def verify_sync():
    print("=== Toss Data Sync Verification ===")
    
    # 1. Config 확인
    print(f"USE_TOSS_DATA: {config.USE_TOSS_DATA}")
    
    # 2. Mock Candidate 생성 (유진로봇, KRX 데이터 기준)
    # KRX 기준: 3735억 (45700원)
    stock = StockData(
        code='056080',
        name='유진로봇',
        market='KOSDAQ',
        sector='로봇',
        close=45700,
        change_pct=21.0,
        trading_value=373_500_000_000,
        volume=8_300_000,
        marcap=1_700_000_000_000,
        high_52w=0,
        low_52w=0
    )
    
    candidates = [stock]
    print(f"Before Sync: {stock.name} Value={stock.trading_value:,} w (KRX)")
    
    # 3. Generator 내부 로직 시뮬레이션
    # SignalGenerator 인스턴스 생성 (리소스 초기화 없이 로직만 테스트)
    gen = SignalGenerator(config=config)
    
    # 동기화 로직 복사/실행 (Generator 내부 로직과 동일하게)
    try:
        from engine.toss_collector import TossCollector
        toss_collector = TossCollector(config)
        
        codes = [s.code for s in candidates]
        print(f"Fetching Toss data for: {codes}")
        
        toss_data_map = toss_collector.get_prices_batch(codes)
        
        if stock.code in toss_data_map:
            t_data = toss_data_map[stock.code]
            print(f"Toss Data Retrieved: Value={t_data.get('trading_value'):,} w")
            
            # Update Logics
            new_close = t_data.get('current')
            new_val = t_data.get('trading_value')
            new_vol = t_data.get('volume')
            new_rate = t_data.get('change_pct')
            
            if new_close and new_val:
                stock.close = int(new_close)
                stock.trading_value = float(new_val)
                stock.volume = int(new_vol)
                stock.change_pct = float(new_rate)
                print("Update Applied.")
            else:
                print("Update Skipped (Invalid Data).")
        else:
            print("No Data from Toss.")
            
    except Exception as e:
        print(f"Sync Failed: {e}")
        
    # 4. 검증
    print(f"After Sync:  {stock.name} Value={stock.trading_value:,} w")
    
    if stock.trading_value > 500_000_000_000:
        print("RESULT: PASS (Value > 5000억)")
    else:
        print("RESULT: FAIL (Value < 5000억)")

if __name__ == "__main__":
    asyncio.run(verify_sync())
