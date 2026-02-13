import requests
import json

def check_toss_trend(code, days=5):
    toss_code = f"A{code}"
    url = f"https://wts-info-api.tossinvest.com/api/v1/stock-infos/trade/trend/trading-trend?productCode={toss_code}&size={days}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Accept': 'application/json',
        'Referer': 'https://tossinvest.com/',
        'Origin': 'https://tossinvest.com'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        print(json.dumps(data, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_toss_trend("009830")
