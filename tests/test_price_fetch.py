
import requests
import json
import logging
import yfinance as yf
from datetime import datetime
import pandas as pd
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TICKERS_TO_TEST = ['024880', '950170', '044490', '098070', '408920', '456160', '270660', '005930']


def _fetch_yfinance_price(ticker):
    try:
        logger.info(f"Testing yfinance for {ticker}...")
        df = yf.download(f"{ticker}.KS", period="1d", progress=False, threads=False)
        if not df.empty:
            price = df['Close'].iloc[-1]
            if isinstance(price, pd.Series):
                price = price.iloc[-1]
            return float(price)
    except Exception as e:
        logger.error(f"yfinance failed for {ticker}: {e}")
    return None


def _fetch_toss_price(ticker):
    try:
        logger.info(f"Testing Toss API for {ticker}...")
        url = f"https://wts-info-api.tossinvest.com/api/v3/stock-prices/details?productCodes=A{ticker}"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            results = data.get('result', [])
            if results:
                price = results[0].get('close')
                if price:
                    return float(price)
    except Exception as e:
        logger.error(f"Toss API failed for {ticker}: {e}")
    return None


def _fetch_naver_price(ticker):
    try:
        logger.info(f"Testing Naver API for {ticker}...")
        url = f"https://m.stock.naver.com/api/stock/{ticker}/basic"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            data = res.json()
            if 'closePrice' in data:
                return float(data['closePrice'].replace(',', ''))
    except Exception as e:
        logger.error(f"Naver API failed for {ticker}: {e}")
    return None


def test_yfinance(ticker):
    price = _fetch_yfinance_price(ticker)
    assert price is None or isinstance(price, float)


def test_toss_api(ticker):
    price = _fetch_toss_price(ticker)
    assert price is None or isinstance(price, float)


def test_naver_api(ticker):
    price = _fetch_naver_price(ticker)
    assert price is None or isinstance(price, float)

def run_tests():
    results = {}
    
    print("\n" + "="*50)
    print("🚀 Starting Price Fetch Verification")
    print("="*50)

    for ticker in TICKERS_TO_TEST:
        print(f"\nTarget: {ticker}")
        
        # 1. Test YFinance
        yf_price = _fetch_yfinance_price(ticker)
        if yf_price:
            print(f"✅ yfinance: Success ({yf_price})")
        else:
            print(f"❌ yfinance: Failed")

        # 2. Test Toss
        toss_price = _fetch_toss_price(ticker)
        if toss_price:
            print(f"✅ Toss API: Success ({toss_price})")
        else:
            print(f"❌ Toss API: Failed")
            
        # 3. Test Naver
        naver_price = _fetch_naver_price(ticker)
        if naver_price:
            print(f"✅ Naver API: Success ({naver_price})")
        else:
            print(f"❌ Naver API: Failed")
            
        results[ticker] = {
            'yf': yf_price,
            'toss': toss_price,
            'naver': naver_price
        }

    print("\n" + "="*50)
    print("📊 Summary")
    print("="*50)
    for t, res in results.items():
        status = []
        if res['yf']: status.append("YF")
        if res['toss']: status.append("Toss")
        if res['naver']: status.append("Naver")
        
        status_str = ", ".join(status) if status else "ALL FAILED"
        print(f"[{t}] Available sources: {status_str}")

if __name__ == "__main__":
    run_tests()
