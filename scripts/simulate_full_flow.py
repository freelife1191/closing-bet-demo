
import asyncio
import sys
import os
from datetime import date
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.config import config
from engine.generator import SignalGenerator

# 로깅 설정 (콘솔 출력)
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("engine")
logger.setLevel(logging.INFO)

async def run_simulation():
    print("=== Full Analysis Simulation (2026-02-10) ===")
    print(f"Config: USE_TOSS_DATA={config.USE_TOSS_DATA}")
    print(f"Config: Min Vol Ratio (Global=2.0, S=5, A=3, B=2)")
    
    # Target Date: 2026-02-10 (User's Current Date)
    target_date = date(2026, 2, 10)
    
    async with SignalGenerator(config) as generator:
        # KOSDAQ만 우선 테스트 (유진로봇 확인용)
        # markets=['KOSPI', 'KOSDAQ']
        signals = await generator.generate(
            target_date=target_date,
            markets=['KOSDAQ'], 
            top_n=50 # 상위 50개만 샘플링하여 속도 확보
        )
        
        print(f"\n=== Simulation Results: {len(signals)} Signals Generated ===")
        
        found_yujin = False
        
        for signal in signals:
            # Signal 객체에는 stock 속성이 없고 필드들이 평탄화되어 있음
            code = signal.stock_code
            name = signal.stock_name
            score = signal.score
            score_detail = signal.score_details
            
            print(f"\n[{signal.grade.value}급] {name} ({code})")
            print(f"  - Value: {signal.trading_value:,.0f} (KRW)")
            # current_price 필드가 float일 수 있으므로 int 변환 시도
            print(f"  - Close: {int(signal.current_price):,} ({signal.change_pct}%)")
            print(f"  - Vol Ratio: {score_detail.get('volume_ratio')}x")
            print(f"  - Score: {score.total} (News={score.news}, Vol={score.volume}, Chart={score.chart}, Bonus={score_detail.get('bonus_score')})")
            
            if code == '056080':
                found_yujin = True
                print("  ==> TARGET FOUND: 유진로봇")
                
                # Validation
                if signal.grade.value == 'A' and score_detail.get('volume_ratio') >= 3.0:
                    print("  ==> VALIDATION: PASS (Grade A, Ratio >= 3.0)")
                else:
                    print(f"  ==> VALIDATION: WARNING (Grade {signal.grade.value})")

        if not found_yujin:
            print("\nWARNING: 유진로봇(056080) Not Found in Signals!")
            print("Possible reasons: Dropped by logic, or not in Top 50 Gainers.")

if __name__ == "__main__":
    asyncio.run(run_simulation())
