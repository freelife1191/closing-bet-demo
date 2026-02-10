
import requests
from bs4 import BeautifulSoup

def check_naver_finance():
    code = "056080"
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    print(f"=== 네이버 금융 유진로봇({code}) 조회 ===")
    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 거래량
        vol_el = soup.select_one('#_quant')
        if vol_el:
            print(f"거래량: {vol_el.text}")
            
        # 거래대금
        # 네이버 금융 메인에는 거래대금이 '백만' 단위로 나올 수 있음
        # 'div.rate_info > table.no_info' 등 확인 필요
        
        # 거래대금은 보통 '호가' 탭이나 '시세' 탭에 정확히 나옴.
        # 메인 페이지의 '거래대금'을 찾아보자.
        # div.curs or table.no_info
        
        # <span id="_amount">373,504</span>  (단위: 백만) -> 3735억
        amount_el = soup.select_one('#_amount')
        if amount_el:
            amount_million = amount_el.text.replace(',', '')
            print(f"거래대금(백만): {amount_million}")
            print(f"환산(억): {int(amount_million) // 100} 억")
            
    except Exception as e:
        print(f"네이버 금융 조회 실패: {e}")

if __name__ == "__main__":
    check_naver_finance()
