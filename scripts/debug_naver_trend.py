import requests
import json

def check_naver_trend(ticker):
    print(f"\n[Naver Trend] Checking {ticker}...")
    
    # 후보 2: Trend (모바일 매매동향) - 200 OK였음
    url2 = f"https://m.stock.naver.com/api/stock/{str(ticker).zfill(6)}/trend"
    
    headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json, text/plain, */*'}
    
    for i, url in enumerate([url2]):
        print(f"Trying URL {i+1}: {url}")
        try:
            res = requests.get(url, headers=headers, timeout=5)
            print(f"Status: {res.status_code}")
            if res.status_code == 200:
                try:
                    data = res.json()
                    print("JSON Parsed Successfully!")
                    print(json.dumps(data, indent=2, ensure_ascii=False)[:500])
                except:
                    print("Not JSON. Content snippet:")
                    print(res.text[:500])
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    check_naver_trend('005930') # Samsung
    check_naver_trend('035720') # Kakao
