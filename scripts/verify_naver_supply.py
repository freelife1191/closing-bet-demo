
import requests
from bs4 import BeautifulSoup
import re

def check_naver_supply_live(ticker="005930"):
    print(f"=== Testing Naver Finance Crawling for {ticker} ===")
    
    url = f"https://finance.naver.com/item/frgn.naver?code={ticker}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    
    # API 방식 시도 (Mobile API)
    print("\n--- Testing Naver Mobile API ---")
    try:
        # https://m.stock.naver.com/api/stock/005930/investor/trend?pageSize=5
        m_url = f"https://m.stock.naver.com/api/stock/{ticker}/investor/trend?pageSize=5"
        res_m = requests.get(m_url, headers=headers)
        data = res_m.json()
        
        if data:
            if isinstance(data, list):
                print(f"Data Count: {len(data)}")
                for item in data[:2]: # 상위 2개만 출력
                    print(f"Date: {item.get('bizdate') or item.get('date')}")
                    print(f"Foreign Net: {item.get('frgn_pure_buy_quant')}") # 필드명 추정 필요
                    print(f"Inst Net: {item.get('orgn_pure_buy_quant')}")
                    print(f"Item: {item}")
            else:
                print(f"Response: {data}")
        else:
            print("No data from Mobile API")
    except Exception as e:
         print(f"Mobile API failed: {e}")

    try:
        # res = requests.get(url, headers=headers)
        # ... HTML parsing logic skipped for now ...
        pass


    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_naver_supply_live()
