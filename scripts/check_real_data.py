
import sys
import os
import requests
import json
import pandas as pd
import yfinance as yf
from datetime import datetime

# Add root dir to sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(root_dir)

def check_toss(ticker):
    print(f"\n[Toss] Checking {ticker}...")
    try:
        toss_url = f"https://wts-info-api.tossinvest.com/api/v3/stock-prices/details?productCodes=A{str(ticker).zfill(6)}"
        res = requests.get(toss_url, timeout=3)
        if res.status_code == 200:
            data = res.json().get('result', [])
            if data:
                item = data[0]
                print(f"Price: {item.get('close')}, Change: {item.get('changeRate')}%, Volume: {item.get('accTradeVolume')}")
                return True
            else:
                print("No result keys")
        else:
            print(f"Status Error: {res.status_code}")
    except Exception as e:
        print(f"Error: {e}")
    return False

def check_naver(ticker):
    print(f"\n[Naver] Checking {ticker}...")
    try:
        naver_url = f"https://m.stock.naver.com/api/stock/{str(ticker).zfill(6)}/basic"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(naver_url, headers=headers, timeout=3)
        if res.status_code == 200:
            data = res.json()
            if 'closePrice' in data:
                print(f"Price: {data.get('closePrice')}, Change: {data.get('fluctuationsRatio')}%, Volume: {data.get('accumulatedTradingVolume')}")
                return True
            else:
                print("No closePrice key")
        else:
            print(f"Status Error: {res.status_code}")
    except Exception as e:
        print(f"Error: {e}")
    return False

def check_yfinance(ticker):
    print(f"\n[yfinance] Checking {ticker}...")
    try:
        data = yf.download(f"{ticker}.KS", period='1d', progress=False)
        if data.empty:
            data = yf.download(f"{ticker}.KQ", period='1d', progress=False)
        
        if not data.empty:
            # MultiIndex 처리
            close = data['Close'].iloc[-1] if 'Close' in data.columns else 0
            if isinstance(close, pd.Series): close = close.iloc[0]
            print(f"Price: {float(close):.0f}")
            return True
        else:
            print("No data found")
    except Exception as e:
        print(f"Error: {e}")
    return False

if __name__ == "__main__":
    tickers = ['005930', '035720', '000660']
    for t in tickers:
        print(f"================ {t} Verification ================")
        t_ok = check_toss(t)
        n_ok = check_naver(t)
        y_ok = check_yfinance(t)
        
        if t_ok and n_ok and y_ok:
            print(f"✅ {t}: All sources passed!")
        else:
            print(f"❌ {t}: Some sources failed.")
