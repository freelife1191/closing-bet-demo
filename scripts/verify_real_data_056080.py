
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.scorer import Scorer
from engine.models import StockData, ChartData, SupplyData, ScoreDetail, Grade
from engine.config import SignalConfig

def test_real_data():
    print("=== 유진로봇(056080) 실제 데이터 기반 검증 ===")
    
    config = SignalConfig()
    scorer = Scorer(config)
    
    # 2026-02-10 유진로봇 실제 데이터
    # 종가: 45,700원 (+21.7%)
    # 거래대금: 3,735억
    # 거래량: 8,322,414
    # 전일 거래량: 5,399,760 (비율 1.54)
    stock = StockData(
        code="056080",
        name="유진로봇",
        market="KOSDAQ",
        sector="로봇",
        close=45700,
        change_pct=21.7,
        trading_value=373_500_000_000,
        volume=8322414,
        marcap=400_000_000_000 # 시총 대략
    )
    
    # 수급: 외인/기관 매수 가정 (실제 데이터 확인 필요하지만 일단 양매수 가정)
    supply = SupplyData(
        foreign_buy_5d=100, # 양수
        inst_buy_5d=100     # 양수
    )
    
    charts = ChartData(
        dates=[], opens=[], highs=[], lows=[], closes=[], volumes=[]
    )
    # 차트 데이터 (간략화)
    # 거래량 비율 계산을 위해 volumes 채움
    # 오늘: 832만, 어제: 539만, 그전평균: 539만이라고 가정
    charts.volumes = [5399760] * 19 + [8322414] 
    
    # 1. 점수 계산 (calculate 메서드 호출)
    # 뉴스 없음, LLM 없음
    score, checklist, details = scorer.calculate(
        stock=stock,
        charts=charts,
        news=[], # 뉴스 없음
        supply=supply,
        llm_result=None
    )
    
    print(f"\n[점수 계산 결과]")
    print(f"총점: {score.total}")
    print(f"  - 뉴스: {score.news}")
    print(f"  - 거래대금: {score.volume}")
    print(f"  - 차트: {score.chart}")
    print(f"  - 캔들: {score.candle}")
    print(f"  - 기간조정: {score.timing}")
    print(f"  - 수급: {score.supply}")
    print(f"  - 보너스: {details['bonus_score']}")
    print(f"거래량 비율: {details['volume_ratio']}")
    
    # 2. 등급 판정
    grade = scorer.determine_grade(stock, score, details, supply, charts, allow_no_news=True)
    
    print(f"\n[등급 판정 결과]")
    if grade:
        print(f"등급: {grade}")
        print("✅ PASS: 필터링 통과")
    else:
        print("❌ FAIL: 등급 없음 (필터링됨)")
        # 원인 분석
        if stock.trading_value < 500_000_000_000:
            print("  -> 거래대금 500억 미만 ... 통과 (3735억)")
        if details['volume_ratio'] < 2.0:
            if stock.trading_value >= 200_000_000_000:
                print(f"  -> 거래량비율 {details['volume_ratio']} (조건 완화 1.0 적용됨) ... 통과해야 함")
            else:
                print(f"  -> 거래량비율 {details['volume_ratio']} < 2.0 ... 탈락 원인")
        if score.total < 8:
             print(f"  -> 총점 미달 ({score.total} < 8)")


if __name__ == "__main__":
    test_real_data()
