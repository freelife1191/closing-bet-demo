import requests
import json
import time

def test_toss_api():
    # Test tickers (from user logs)
    # The logs showed 'A024880', 'A044490', 'A098070', etc.
    # The service expects "A" prefix for the URL query.
    
    tickers = ['056080']
    toss_codes = [f"A{t}" for t in tickers]
    
    codes_str = ",".join(toss_codes)
    url = f"https://wts-info-api.tossinvest.com/api/v3/stock-prices/details?productCodes={codes_str}"
    
    print(f"Testing URL: {url}")
    
    try:
        start_time = time.time()
        res = requests.get(url, timeout=10)
        duration = time.time() - start_time
        
        print(f"Status Code: {res.status_code}")
        print(f"Time Taken: {duration:.2f}s")
        
        if res.status_code == 200:
            data = res.json()
            # print(json.dumps(data, indent=2, ensure_ascii=False))
            
            results = data.get('result', [])
            print(f"Total Results: {len(results)}")
            
            for item in results:
                raw_code = item.get('code', '')
                code = raw_code[1:] if raw_code.startswith('A') else raw_code
                name = item.get('name', 'Unknown')
                close = item.get('close')
                volume = item.get('volume')
                value = item.get('value')
                
                print(f"Code: {raw_code} -> {code} | Name: {name}")
                print(f"  Close: {close}")
                print(f"  Volume: {volume}")
                print(f"  Value: {value} (단위: 원?)")
                if value:
                     print(f"  Value(억): {value // 100_000_000} 억")
                
                if close is None or close == 0:
                     print("  WARNING: Invalid price!")
        else:
            print("Error Response:", res.text)
            
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_toss_api()
