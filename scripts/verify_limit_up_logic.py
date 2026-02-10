
import sys
import os
from datetime import datetime

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.scorer import Scorer
from engine.models import StockData, ChartData, SupplyData, ScoreDetail, Grade
from engine.config import SignalConfig

def test_limit_up_logic():
    print("=== 상한가(30%) 종목 필터링 로직 검증 시작 ===")
    
    # 1. 설정 및 Scorer 초기화
    config = SignalConfig()
    scorer = Scorer(config)
    
    # 2. 가상의 상한가 종목 데이터 생성
    # - 거래대금: 1조원 (S급 조건 충족)
    # - 등락률: 30.0% (상한가)
    # - 점수: 15점 (S급 조건 충족)
    stock = StockData(
        code="056080",
        name="유진로봇(TEST)",
        market="KOSDAQ",
        sector="로봇",
        close=13000,
        change_pct=30.0, # 상한가
        trading_value=1_000_000_000_000, # 1조원
        volume=10_000_000,
        marcap=500_000_000_000
    )
    
    # 점수 객체 (S급 요건: 거래대금 1조 + 점수 15점 이상)
    score = ScoreDetail()
    score.total = 15 
    score.news = 3
    score.volume = 3
    score.chart = 2
    score.candle = 1
    score.timing = 1
    score.supply = 2
    # 보너스 점수 등 포함하여 15점 가정
    
    score_details = {
        'volume_ratio': 5.0 # 거래량 배수 충족
    }
    
    supply = SupplyData(
        foreign_buy_5d=100,
        inst_buy_5d=100
    )
    
    charts = ChartData(
        dates=[], opens=[], highs=[], lows=[], closes=[], volumes=[]
    )
    
    # 3. 등급 판정 실행 (상한가 테스트)
    print(f"\n[입력 데이터 1 - 상한가]")
    print(f"종목명: {stock.name}")
    print(f"등락률: {stock.change_pct}%")
    print(f"거래대금: {stock.trading_value//100000000}억")
    
    grade = scorer.determine_grade(stock, score, score_details, supply, charts, allow_no_news=True)
    
    print(f"\n[판정 결과 1]")
    if grade:
        print(f"등급: {grade}")
        if str(grade) == "Grade.S" or grade == Grade.S:
             print("✅ PASS: 상한가 종목이 정상적으로 S급으로 판정되었습니다.")
        else:
             print(f"⚠️ WARNING: 시그널은 발생했으나 등급이 예상(S)과 다릅니다. ({grade})")
    else:
        print("❌ FAIL: 상한가 종목이 필터링되었습니다.")

    # 4. 추가 검증: 대량 거래 터진 미동 거래목 (거래량 비율 1.2배)
    print(f"\n[입력 데이터 2 - 대량거래 & 낮은 거래량비율]")
    stock2 = StockData(
        code="005930",
        name="삼성전자(TEST)",
        market="KOSPI",
        sector="반도체",
        close=80000,
        change_pct=5.0,
        trading_value=300_000_000_000, # 3000억 (2000억 이상)
        volume=5000000,
        marcap=500_000_000_000_000
    )
    score_details2 = {
        'volume_ratio': 1.2 # 2.0 미만이지만 통과해야 함
    }
    
    grade2 = scorer.determine_grade(stock2, score, score_details2, supply, charts, allow_no_news=True)
    
    print(f"종목명: {stock2.name}")
    print(f"거래대금: {stock2.trading_value//100000000}억")
    print(f"거래량비율: {score_details2['volume_ratio']}")
    
    print(f"\n[판정 결과 2]")
    if grade2:
        print(f"등급: {grade2}")
        print("✅ PASS: 대량거래 종목이 낮은 거래량 비율(1.2)에도 필터링되지 않았습니다.")
    else:
        print("❌ FAIL: 대량거래 종목이 필터링되었습니다. (거래량 비율 조건 완화 실패)")

if __name__ == "__main__":
    test_limit_up_logic()
