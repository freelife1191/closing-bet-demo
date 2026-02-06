
import sys
import os
import logging
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.toss_collector import TossCollector

# Setup logging
logging.basicConfig(level=logging.INFO)

def check_toss_supply_live():
    print("=== Testing Toss Securities API (Supply Data) ===")
    collector = TossCollector()
    
    # 삼성전자 (005930) 테스트
    ticker = "005930"
    print(f"Fetch supply for {ticker} (Samsung Electronics)...")
    
    # 최근 5일 데이터 조회
    trend = collector.get_investor_trend(ticker, days=5)
    
    if trend:
        print("\n✅ Toss Investor Trend Fetched:")
        print(trend)
        
        # 상세 데이터 구조 확인 (body 내용) -> get_investor_trend 수정 필요할 수도 있음
        # 하지만 일단 합계가 나오는지 확인
        print(f"Foreign Net Buy: {trend.get('foreign')}")
        print(f"Institution Net Buy: {trend.get('institution')}")
        
    else:
        print("\n❌ Fetch Failed (None returned)")

    # 상세 API 직접 호출해보기 (당일 데이터 있는지 확인용)
    print("\n--- Direct API Call (1 Day) ---")
    toss_code = f"A{ticker}"
    url = f"https://wts-info-api.tossinvest.com/api/v1/stock-infos/trade/trend/trading-trend?productCode={toss_code}&size=5"
    try:
        import requests
        res = requests.get(url, headers={
            'Referer': 'https://tossinvest.com/',
            'Origin': 'https://tossinvest.com'
        })
        data = res.json()
        
        # 결과값에서 날짜 확인
        # body 리스트의 첫 번째가 최신인지, 마지막이 최신인지 확인
        if 'result' in data and 'body' in data['result']:
            body = data['result']['body']
            print(f"Data count: {len(body)}")
            if body:
                latest = body[-1] # 보통 시계열은 마지막이 최신
                print(f"Latest Object: {latest}")
                # Toss API 필드명 추정: date, tradeDate, baseDate 등
                print(f"Latest Date Field (date): {latest.get('date')}")
                print(f"Latest Date Field (tradeDate): {latest.get('tradeDate')}")
                print(f"Latest Date Field (baseDate): {latest.get('baseDate')}")
                
                print(f"Latest Foreign: {latest.get('netForeignerBuyVolume')}")
                print(f"Latest Inst: {latest.get('netInstitutionBuyVolume')}")
        else:
             print("Invalid response structure")
             
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    check_toss_supply_live()
