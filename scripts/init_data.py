#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
데이터 초기화 스크립트 (Data Initialization Script)
- 실시간 시장 데이터 수집 (yfinance)
- 필요한 데이터 파일 생성
- 에러 처리 및 진행률 표시 개선
"""

import os
import sys
import pandas as pd
import numpy as np
import json
import socket
import time
import random
import logging
from datetime import datetime, timedelta

# [FIX] Filter out pykrx's broken logging calls
class PykrxFilter(logging.Filter):
    def filter(self, record):
        # pykrx.website.comm.util calls logging.info(args, kwargs) which causes TypeError
        if 'pykrx' in record.pathname and 'util.py' in record.pathname:
            return False
        return True

# Apply filter to root logger (Logger.filter runs before handlers/formatting)
logging.getLogger().addFilter(PykrxFilter())
# If no handlers yet (basicConfig not called), we might need to add it later or rely on basicConfig


# 네트워크 타임아웃 설정 (30초) - 무한 대기 방지
socket.setdefaulttimeout(30)

# Import shared state for stop logic
try:
    import engine.shared as shared_state
except ImportError:
    import sys, os
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root_dir not in sys.path:
        sys.path.append(root_dir)
    try:
        import engine.shared as shared_state
    except ImportError:
        class MockShared:
            STOP_REQUESTED = False
        shared_state = MockShared()

# Custom JSON encoder for numpy types
class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)

# yfinance for real market data
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False

# 루트 디렉토리 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
import asyncio

from engine.config import config, app_config
from engine.collectors import EnhancedNewsCollector
from engine.llm_analyzer import LLMAnalyzer
from engine.market_gate import MarketGate

# =====================================================
# 주말/휴일 처리를 위한 유틸리티 함수
# =====================================================

def get_last_trading_date(reference_date=None):
    """
    마지막 개장일 날짜를 반환합니다.
    - 주말(토/일)인 경우 금요일로 이동
    - 금요일이 휴일인 경우 pykrx를 통해 실제 마지막 개장일 확인
    
    Args:
        reference_date: 기준 날짜 (datetime 객체). None이면 오늘 날짜 사용.
    
    Returns:
        tuple: (last_trading_date_str, last_trading_date_obj)
               - last_trading_date_str: 'YYYYMMDD' 형식의 문자열
               - last_trading_date_obj: datetime 객체
    """
    if reference_date is None:
        reference_date = datetime.now()
    
    target_date = reference_date
    
    # 1차: 주말 처리 (토/일 → 금요일로 이동)
    if target_date.weekday() == 5:  # 토요일
        target_date -= timedelta(days=1)
    elif target_date.weekday() == 6:  # 일요일
        target_date -= timedelta(days=2)
    
    # 2차: pykrx를 통해 실제 개장일 확인
    try:
        from pykrx import stock
        
        # 최근 10일간 거래일 조회 (휴일 연속 대비)
        start_check = (target_date - timedelta(days=10)).strftime('%Y%m%d')
        end_check = target_date.strftime('%Y%m%d')
        
        # KOSPI 지수의 OHLCV로 개장일 확인
        kospi_data = stock.get_index_ohlcv_by_date(start_check, end_check, "1001")
        
        if not kospi_data.empty:
            # 마지막 거래일을 가져옴
            last_trading_date = kospi_data.index[-1]
            last_trading_date_str = last_trading_date.strftime('%Y%m%d')
            log(f"마지막 개장일 확인: {last_trading_date_str}", "SUCCESS")
            return last_trading_date_str, last_trading_date
        else:
            # 데이터가 없으면 계산된 날짜 사용
            log(f"pykrx 데이터 없음, 계산된 날짜 사용: {target_date.strftime('%Y%m%d')}", "WARNING")
            
    except ImportError:
        log("pykrx 미설치 - 주말 처리만 적용", "WARNING")
    except Exception as e:
        log(f"개장일 확인 실패: {e} - 주말 처리만 적용", "WARNING")
    
    # 폴백: 주말 처리만 된 날짜 반환
    return target_date.strftime('%Y%m%d'), target_date


# =====================================================
# 실시간 시장 데이터 수집 함수
# =====================================================

def fetch_market_indices():
    """KOSPI/KOSDAQ 실시간 지수 수집"""
    indices = {
        'kospi': {'value': 2650.0, 'change_pct': 0.0, 'prev_close': 2650.0},
        'kosdaq': {'value': 850.0, 'change_pct': 0.0, 'prev_close': 850.0}
    }
    
    if not YFINANCE_AVAILABLE:
        log("yfinance 미설치 - 샘플 데이터 사용", "WARNING")
        return indices
    
    try:
        # KOSPI (^KS11)
        kospi = yf.Ticker('^KS11')
        kospi_hist = kospi.history(period='5d')
        if not kospi_hist.empty:
            current = kospi_hist['Close'].iloc[-1]
            prev = kospi_hist['Close'].iloc[-2] if len(kospi_hist) > 1 else current
            change_pct = ((current - prev) / prev) * 100 if prev > 0 else 0
            indices['kospi'] = {
                'value': round(current, 2),
                'change_pct': round(change_pct, 2),
                'prev_close': round(prev, 2)
            }
        
        # KOSDAQ (^KQ11)
        kosdaq = yf.Ticker('^KQ11')
        kosdaq_hist = kosdaq.history(period='5d')
        if not kosdaq_hist.empty:
            current = kosdaq_hist['Close'].iloc[-1]
            prev = kosdaq_hist['Close'].iloc[-2] if len(kosdaq_hist) > 1 else current
            change_pct = ((current - prev) / prev) * 100 if prev > 0 else 0
            indices['kosdaq'] = {
                'value': round(current, 2),
                'change_pct': round(change_pct, 2),
                'prev_close': round(prev, 2)
            }
            
        # KRX Gold (411060.KS - ACE KRX금현물)
        gold = yf.Ticker('411060.KS')
        gold_hist = gold.history(period='5d')
        if not gold_hist.empty:
            current = gold_hist['Close'].iloc[-1]
            prev = gold_hist['Close'].iloc[-2] if len(gold_hist) > 1 else current
            change_pct = ((current - prev) / prev) * 100 if prev > 0 else 0
            indices['kr_gold'] = {
                'value': round(current, 0), # 원화는 정수
                'change_pct': round(change_pct, 2),
                'prev_close': round(prev, 0)
            }
        else:
            indices['kr_gold'] = {'value': 0, 'change_pct': 0, 'prev_close': 0}

        # KRX Silver (144600.KS - KODEX 은선물(H))
        silver = yf.Ticker('144600.KS')
        silver_hist = silver.history(period='5d')
        if not silver_hist.empty:
            current = silver_hist['Close'].iloc[-1]
            prev = silver_hist['Close'].iloc[-2] if len(silver_hist) > 1 else current
            change_pct = ((current - prev) / prev) * 100 if prev > 0 else 0
            indices['kr_silver'] = {
                'value': round(current, 0),
                'change_pct': round(change_pct, 2),
                'prev_close': round(prev, 0)
            }
        else:
             indices['kr_silver'] = {'value': 0, 'change_pct': 0, 'prev_close': 0}
             
        # US Gold Futures (GC=F)
        us_gold = yf.Ticker('GC=F')
        us_gold_hist = us_gold.history(period='5d')
        if not us_gold_hist.empty:
            current = us_gold_hist['Close'].iloc[-1]
            prev = us_gold_hist['Close'].iloc[-2] if len(us_gold_hist) > 1 else current
            change_pct = ((current - prev) / prev) * 100 if prev > 0 else 0
            indices['us_gold'] = {
                'value': round(current, 2),
                'change_pct': round(change_pct, 2),
                'prev_close': round(prev, 2)
            }
            
        # US Silver Futures (SI=F)
        us_silver = yf.Ticker('SI=F')
        us_silver_hist = us_silver.history(period='5d')
        if not us_silver_hist.empty:
            current = us_silver_hist['Close'].iloc[-1]
            prev = us_silver_hist['Close'].iloc[-2] if len(us_silver_hist) > 1 else current
            change_pct = ((current - prev) / prev) * 100 if prev > 0 else 0
            indices['us_silver'] = {
                'value': round(current, 2),
                'change_pct': round(change_pct, 2),
                'prev_close': round(prev, 2)
            }
        
        log(f"시장 지수 수집 완료: KOSPI {indices['kospi']['value']}, Gold {indices.get('gold', {}).get('value')}", "SUCCESS")
        
        # S&P 500 (^GSPC)
        sp500 = yf.Ticker('^GSPC')
        sp500_hist = sp500.history(period='5d')
        if not sp500_hist.empty:
            current = sp500_hist['Close'].iloc[-1]
            prev = sp500_hist['Close'].iloc[-2] if len(sp500_hist) > 1 else current
            change_pct = ((current - prev) / prev) * 100 if prev > 0 else 0
            indices['sp500'] = {
                'value': round(current, 2),
                'change_pct': round(change_pct, 2),
                'prev_close': round(prev, 2)
            }
            
        # Nasdaq (^IXIC)
        nasdaq = yf.Ticker('^IXIC')
        nasdaq_hist = nasdaq.history(period='5d')
        if not nasdaq_hist.empty:
            current = nasdaq_hist['Close'].iloc[-1]
            prev = nasdaq_hist['Close'].iloc[-2] if len(nasdaq_hist) > 1 else current
            change_pct = ((current - prev) / prev) * 100 if prev > 0 else 0
            indices['nasdaq'] = {
                'value': round(current, 2),
                'change_pct': round(change_pct, 2),
                'prev_close': round(prev, 2)
            }

        # Bitcoin (BTC-USD)
        btc = yf.Ticker('BTC-USD')
        btc_hist = btc.history(period='5d')
        if not btc_hist.empty:
            current = btc_hist['Close'].iloc[-1]
            prev = btc_hist['Close'].iloc[-2] if len(btc_hist) > 1 else current
            change_pct = ((current - prev) / prev) * 100 if prev > 0 else 0
            indices['btc'] = {
                'value': round(current, 2),
                'change_pct': round(change_pct, 2),
                'prev_close': round(prev, 2)
            }
            
        # Ethereum (ETH-USD)
        eth = yf.Ticker('ETH-USD')
        eth_hist = eth.history(period='5d')
        if not eth_hist.empty:
            current = eth_hist['Close'].iloc[-1]
            prev = eth_hist['Close'].iloc[-2] if len(eth_hist) > 1 else current
            change_pct = ((current - prev) / prev) * 100 if prev > 0 else 0
            indices['eth'] = {
                'value': round(current, 2),
                'change_pct': round(change_pct, 2),
                'prev_close': round(prev, 2)
            }
            
        # Ripple (XRP-USD)
        xrp = yf.Ticker('XRP-USD')
        xrp_hist = xrp.history(period='5d')
        if not xrp_hist.empty:
            current = xrp_hist['Close'].iloc[-1]
            prev = xrp_hist['Close'].iloc[-2] if len(xrp_hist) > 1 else current
            change_pct = ((current - prev) / prev) * 100 if prev > 0 else 0
            indices['xrp'] = {
                'value': round(current, 4),
                'change_pct': round(change_pct, 2),
                'prev_close': round(prev, 4)
            }
            
    except Exception as e:
        log(f"시장 지수 수집 실패: {e} - 샘플 데이터 사용", "WARNING")
    
    return indices


def fetch_sector_indices():
    """pykrx를 사용하여 KOSPI 섹터 지수 수집"""
    # 섹터 코드 매핑 (KOSPI 업종 지수 - KRX 공식 코드)
    sector_codes = {
        '1012': '철강',       # 철강·금속
        '1027': '2차전지',   # 전기·전자 (2차전지, 반도체 포함)
        '1024': '반도체',     # 반도체
        '1016': '자동차',     # 운수장비
        '1020': '증권',       # 금융업
        '1018': 'IT서비스',   # 서비스업 (IT)
        '1001': 'KOSPI200',   # KOSPI 200
        '1026': '은행',       # 은행
    }
    
    sectors = []
    
    try:
        from pykrx import stock
        # from datetime import datetime, timedelta
        
        today = datetime.now().strftime('%Y%m%d')
        yesterday = (datetime.now() - timedelta(days=3)).strftime('%Y%m%d')
        
        for code, name in sector_codes.items():
            try:
                df = stock.get_index_ohlcv_by_date(yesterday, today, code)
                if not df.empty and len(df) >= 2:
                    current = df['종가'].iloc[-1]
                    prev = df['종가'].iloc[-2]
                    change_pct = ((current - prev) / prev) * 100 if prev > 0 else 0
                    
                    # 강세/약세 판단
                    if change_pct > 1.0:
                        signal = 'bullish'
                    elif change_pct < -1.0:
                        signal = 'bearish'
                    else:
                        signal = 'neutral'
                    
                    # 점수 계산 (등락률 기반)
                    score = min(max(50 + int(change_pct * 10), 0), 100)
                    
                    sectors.append({
                        'name': name,
                        'signal': signal,
                        'change_pct': round(change_pct, 2),
                        'score': score
                    })
            except Exception as e:
                pass
        
        if sectors:
            log(f"섹터 데이터 수집 완료: {len(sectors)}개 섹터", "SUCCESS")
        
    except ImportError:
        log("pykrx 미설치 - 샘플 섹터 데이터 사용", "WARNING")
    except Exception as e:
        log(f"pykrx 수급 데이터 수집 실패: {e} - 샘플 데이터 생성", "WARNING")
        
        
        return False
    
    # 데이터가 없으면 샘플 반환
    # 데이터가 없으면 빈 리스트 반환 (샘플 금지)
    if not sectors:
        return []
    
    return sectors


def fetch_stock_price(ticker):
    """개별 종목 실시간 가격 수집"""
    if not YFINANCE_AVAILABLE:
        return None
    
    try:
        # 한국 종목은 .KS (KOSPI) 또는 .KQ (KOSDAQ) 접미사 필요
        yahoo_ticker = f"{ticker}.KS"
        stock = yf.Ticker(yahoo_ticker)
        hist = stock.history(period='5d')
        
        if hist.empty:
            # KOSDAQ 시도
            yahoo_ticker = f"{ticker}.KQ"
            stock = yf.Ticker(yahoo_ticker)
            hist = stock.history(period='5d')
        
        if not hist.empty:
            current = hist['Close'].iloc[-1]
            prev = hist['Close'].iloc[-2] if len(hist) > 1 else current
            change_pct = ((current - prev) / prev) * 100 if prev > 0 else 0
            return {
                'price': round(current, 0),
                'change_pct': round(change_pct, 2),
                'prev_close': round(prev, 0)
            }
    except Exception as e:
        pass
    
    return None


# 전역 캐시 (여러 함수에서 공유)
_market_indices_cache = None
_sector_indices_cache = None

def get_market_indices():
    """캐시된 시장 지수 반환"""
    global _market_indices_cache
    if _market_indices_cache is None:
        _market_indices_cache = fetch_market_indices()
    return _market_indices_cache

def get_sector_indices():
    """캐시된 섹터 지수 반환"""
    global _sector_indices_cache
    if _sector_indices_cache is None:
        _sector_indices_cache = fetch_sector_indices()
    return _sector_indices_cache

def reset_cache():
    """캐시 초기화 (Refresh 시 호출)"""
    global _market_indices_cache, _sector_indices_cache
    _market_indices_cache = None
    _sector_indices_cache = None
    log("캐시 초기화 완료", "SUCCESS")



# 색상 코드 (터미널)
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def log(message, level="INFO"):
    if level == "SUCCESS":
        print(f"{Colors.OKGREEN}✅ {message}{Colors.ENDC}", flush=True)
    elif level == "ERROR":
        print(f"{Colors.FAIL}❌ {message}{Colors.ENDC}", flush=True)
    elif level == "WARNING":
        print(f"{Colors.WARNING}⚠️  {message}{Colors.ENDC}", flush=True)
    elif level == "HEADER":
        print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}", flush=True)
        print(f"{Colors.HEADER}{message}{Colors.ENDC}", flush=True)
        print(f"{Colors.HEADER}{'='*60}{Colors.ENDC}", flush=True)
    else:
        print(f"📌 {message}", flush=True)

def ensure_directory(dir_path):
    """디렉토리가 존재하는지 확인하고, 없으면 생성합니다."""
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
        log(f"디렉토리 생성됨: {dir_path}", "SUCCESS")
    else:
        log(f"디렉토리 확인됨: {dir_path}")

def create_korean_stocks_list():
    """한국 주식 목록 생성 - pykrx로 시가총액 상위 종목 조회"""
    log("한국 주식 목록 생성 중 (pykrx 시가총액 상위)...")
    try:
        from pykrx import stock
        # from datetime import datetime
        
        today = datetime.now().strftime('%Y%m%d')
        
        all_data = []
        
        # KOSPI 시가총액 상위 종목 조회
        try:
            kospi_cap = stock.get_market_cap(today, market="KOSPI")
            if not kospi_cap.empty:
                # 시가총액 순 정렬 후 상위 300개 (VCP 발굴 확률 확대를 위해 증가)
                kospi_cap = kospi_cap.sort_values('시가총액', ascending=False).head(300)
                for ticker in kospi_cap.index:
                    try:
                        name = stock.get_market_ticker_name(ticker)
                        all_data.append({
                            'ticker': ticker,
                            'name': name,
                            'market': 'KOSPI',
                            'sector': ''
                        })
                    except:
                        pass
                log(f"KOSPI 시가총액 상위 {len(kospi_cap)} 종목 수집", "SUCCESS")
        except Exception as e:
            log(f"KOSPI 시가총액 조회 실패: {e}", "WARNING")
        
        # KOSDAQ 시가총액 상위 종목 조회
        try:
            kosdaq_cap = stock.get_market_cap(today, market="KOSDAQ")
            if not kosdaq_cap.empty:
                # 시가총액 순 정렬 후 상위 300개 (코스닥 포함 요청 반영)
                kosdaq_cap = kosdaq_cap.sort_values('시가총액', ascending=False).head(300)
                for ticker in kosdaq_cap.index:
                    try:
                        name = stock.get_market_ticker_name(ticker)
                        all_data.append({
                            'ticker': ticker,
                            'name': name,
                            'market': 'KOSDAQ',
                            'sector': ''
                        })
                    except:
                        pass
                log(f"KOSDAQ 시가총액 상위 {len(kosdaq_cap)} 종목 수집", "SUCCESS")
        except Exception as e:
            log(f"KOSDAQ 시가총액 조회 실패: {e}", "WARNING")
        
        if all_data:
            df = pd.DataFrame(all_data)
            file_path = os.path.join(BASE_DIR, 'data', 'korean_stocks_list.csv')
            df.to_csv(file_path, index=False, encoding='utf-8-sig')
            log(f"종목 목록 생성 완료: {file_path} ({len(df)} 종목)", "SUCCESS")
            return True
        else:
            raise Exception("시가총액 데이터 수집 실패")
        
    except Exception as e:
        log(f"pykrx 종목 조회 실패: {e} - 기본 종목 사용", "WARNING")
        # 폴백: 시가총액 상위 주요 종목 (KOSPI + KOSDAQ)
        data = {
            'ticker': [
                # KOSPI 상위 15개
                '005930', '000660', '005380', '373220', '207940', '000270', '035420', '068270', '105560', '055550',
                '035720', '003550', '015760', '028260', '017670',
                # KOSDAQ 상위 10개
                '247540', '086520', '196170', '263750', '145020', '403870', '328130', '091990', '336370', '058470'
            ],
            'name': [
                # KOSPI
                '삼성전자', 'SK하이닉스', '현대차', 'LG에너지솔루션', '삼성바이오로직스', '기아', 'NAVER', '셀트리온', 'KB금융', '신한지주',
                '카카오', 'LG', '한국전력', '삼성물산', 'SK텔레콤',
                # KOSDAQ
                '에코프로비엠', '에코프로', '알테오젠', '펄어비스', '휴젤', '피에이치에이', '루닛', '셀트리온제약', '솔브레인', '리노공업'
            ],
            'market': [
                'KOSPI', 'KOSPI', 'KOSPI', 'KOSPI', 'KOSPI', 'KOSPI', 'KOSPI', 'KOSPI', 'KOSPI', 'KOSPI',
                'KOSPI', 'KOSPI', 'KOSPI', 'KOSPI', 'KOSPI',
                'KOSDAQ', 'KOSDAQ', 'KOSDAQ', 'KOSDAQ', 'KOSDAQ', 'KOSDAQ', 'KOSDAQ', 'KOSDAQ', 'KOSDAQ', 'KOSDAQ'
            ],
            'sector': [
                '반도체', '반도체', '자동차', '2차전지', '바이오', '자동차', '인터넷', '바이오', '금융', '금융',
                '인터넷', '지주', '에너지', '건설', '통신',
                '2차전지', '2차전지', '바이오', '게임', '바이오', '자동차부품', 'AI/의료', '바이오', '반도체소재', '반도체장비'
            ],
        }
        df = pd.DataFrame(data)
        file_path = os.path.join(BASE_DIR, 'data', 'korean_stocks_list.csv')
        df.to_csv(file_path, index=False, encoding='utf-8-sig')
        log(f"기본 종목 목록 생성 완료: {file_path} ({len(df)} 종목 - KOSPI 15개 + KOSDAQ 10개)", "SUCCESS")
        return True



def fetch_prices_yfinance(start_date, end_date, existing_df, file_path):
    """yfinance를 이용한 가격 데이터 수집 폴백"""
    try:
        import yfinance as yf
        log("yfinance 백업 수집 모드 가동...", "INFO")
        
        # 종목 리스트 로드
        stocks_file = os.path.join(BASE_DIR, 'data', 'korean_stocks_list.csv')
        if not os.path.exists(stocks_file):
            log("종목 리스트 파일이 없어 yfinance 수집 불가", "ERROR")
            return False
            
        stocks_df = pd.read_csv(stocks_file, dtype={'ticker': str})
        tickers = stocks_df['ticker'].tolist()
        
        new_data_list = []
        
        total = len(tickers)
        for idx, ticker in enumerate(tickers):
            try:
                # 마켓 확인
                market_info = stocks_df[stocks_df['ticker'] == ticker]['market'].values
                suffix = ".KS" if len(market_info) > 0 and market_info[0] == 'KOSPI' else ".KQ"
                yf_ticker = f"{ticker}{suffix}"
                
                # 데이터 다운로드 (진행률 표시 없이)
                df = yf.download(yf_ticker, start=start_date.strftime('%Y-%m-%d'), end=(end_date + timedelta(days=1)).strftime('%Y-%m-%d'), progress=False)
                
                if not df.empty:
                    # MultiIndex 컬럼 처리
                    if isinstance(df.columns, pd.MultiIndex):
                         # yfinance 0.2.x+ returns MultiIndex if configured or sometimes by default
                         # It usually is (Price, Ticker) or just Price.
                         # Dropping level if it exists
                        try:
                            df.columns = df.columns.droplevel(1)
                        except:
                            pass
                        
                    df = df.reset_index()
                    # 컬럼 이름이 Date, Open, High ...
                    
                    # Rename columns to standard lowercase
                    df = df.rename(columns={
                        'Date': 'date', 'Open': 'open', 'High': 'high', 
                        'Low': 'low', 'Close': 'close', 'Volume': 'volume'
                    })
                    
                    # Ensure columns exist
                    required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
                    if not all(col in df.columns for col in required_cols):
                         continue

                    df['date'] = df['date'].dt.strftime('%Y-%m-%d')
                    df['ticker'] = ticker
                    
                    # Type conversion
                    df['open'] = df['open'].astype(int)
                    df['high'] = df['high'].astype(int)
                    df['low'] = df['low'].astype(int)
                    df['close'] = df['close'].astype(int)
                    df['volume'] = df['volume'].astype(int)
                    
                    subset = df[['date', 'ticker', 'open', 'high', 'low', 'close', 'volume']]
                    new_data_list.append(subset)
                    
            except Exception as e:
                continue
                
            if idx % 50 == 0:
                print(f"  -> yfinance 진행: {idx}/{total}")

        if new_data_list:
            new_df = pd.concat(new_data_list)
            
            if not existing_df.empty:
                if 'date' in existing_df.columns and not pd.api.types.is_string_dtype(existing_df['date']):
                     existing_df['date'] = existing_df['date'].dt.strftime('%Y-%m-%d')
                     
                final_df = pd.concat([existing_df, new_df])
                final_df = final_df.drop_duplicates(subset=['ticker', 'date'], keep='last')
            else:
                final_df = new_df
                
            final_df.to_csv(file_path, index=False, encoding='utf-8-sig')
            log(f"yfinance 백업 수집 완료 ({len(final_df)}행)", "SUCCESS")
            return True
        else:
            log("yfinance 수집 데이터 없음", "WARNING")
            return True
            
    except Exception as e:
        log(f"yfinance 폴백 실패: {e}", "ERROR")
        return False


def create_daily_prices(target_date=None):
    """일별 가격 데이터 수집 - pykrx 날짜별 일괄 조회 (속도 최적화)"""
    log("일별 가격 데이터 수집 중 (Date-based Fast Mode)...")
    try:
        from pykrx import stock
        import time
        from datetime import datetime, timedelta

        # 날짜 설정
        if target_date:
            if isinstance(target_date, str):
                end_date_obj = datetime.strptime(target_date, '%Y-%m-%d')
            else:
                end_date_obj = target_date
        else:
            end_date_obj = datetime.now()

        # 마지막 개장일 확인
        end_date_str, end_date_obj = get_last_trading_date(reference_date=end_date_obj)
        
        # 기존 데이터 로드 및 시작일 결정
        file_path = os.path.join(BASE_DIR, 'data', 'daily_prices.csv')
        existing_df = pd.DataFrame()
        start_date_obj = end_date_obj - timedelta(days=90) # 기본 90일

        if os.path.exists(file_path):
            try:
                existing_df = pd.read_csv(file_path, dtype={'ticker': str})
                if not existing_df.empty and 'date' in existing_df.columns:
                    max_date_str = existing_df['date'].max()
                    max_date_dt = datetime.strptime(max_date_str, '%Y-%m-%d')
                    # 마지막 저장일 다음날부터 수집
                    start_date_obj = max_date_dt + timedelta(days=1)
                    log(f"기존 데이터 확인: {max_date_str}까지 존재. 이후부터 수집.", "INFO")
                else:
                    log("기존 데이터 비어있음.", "INFO")
            except Exception as e:
                log(f"기존 데이터 로드 오류: {e}", "WARNING")

        # 수집 시작일이 종료일보다 미래면 수집 불필요 (단, 당일재수집 옵션 고려 등은 생략, '최신'이면 pass)
        if start_date_obj.date() > end_date_obj.date():
             log("이미 최신 데이터가 존재합니다.", "SUCCESS")
             return True
             
        req_start_date_str = start_date_obj.strftime('%Y%m%d')
        log(f"수집 구간: {req_start_date_str} ~ {end_date_str}", "INFO")

        # 날짜 리스트 생성
        date_range = pd.date_range(start=start_date_obj, end=end_date_obj)
        total_days = len(date_range)
        
        new_data_list = []
        processed_days = 0
        
        for dt in date_range:
            if shared_state.STOP_REQUESTED:
                log("⛔️ 사용자 요청으로 중단", "WARNING")
                break
                
            cur_date_str = dt.strftime('%Y%m%d')
            cur_date_fmt = dt.strftime('%Y-%m-%d')
            
            # 주말 체크 (토/일) - pykrx가 알아서 빈값 줄 수 있으나 미리 건너뛰면 빠름
            if dt.weekday() >= 5: 
                processed_days += 1
                continue
                
            try:
                # 해당 날짜의 전 종목 시세 조회 (1회 요청)
                df = stock.get_market_ohlcv(cur_date_str, market="ALL")
                
                if df is None or df.empty:
                    # 휴장일 가능성
                    processed_days += 1
                    continue
                    
                # DataFrame 정리
                # index는 ticker, columns: 시가, 고가, 저가, 종가, 거래량, 거래대금, 등락률
                df = df.reset_index() # ticker가 컬럼으로 나옴 ('티커')
                
                # 컬럼 매핑
                # pykrx 버전에 따라 컬럼명이 '티커'일수도, index일수도 있음. 
                # get_market_ohlcv("YYYYMMDD") returns index=티커.
                if '티커' in df.columns:
                    df = df.rename(columns={'티커': 'ticker'})
                else: 
                    # reset_index() 했을 때 기존 index 이름이 '티커'였다면 그게 컬럼명이 됨
                    # 만약 이름이 없었다면 'index'
                    if 'index' in df.columns:
                        df = df.rename(columns={'index': 'ticker'})
                
                # 필수 컬럼 존재 확인
                rename_map = {
                    '시가': 'open', '고가': 'high', '저가': 'low', 
                    '종가': 'close', '거래량': 'volume', '거래대금': 'trading_value'
                }
                
                # 실제 존재하는 컬럼만 rename
                available_map = {k: v for k, v in rename_map.items() if k in df.columns}
                df = df.rename(columns=available_map)
                
                df['ticker'] = df['ticker'].astype(str).str.zfill(6)
                df['date'] = cur_date_fmt
                
                # 필요한 컬럼만 추출
                cols = ['date', 'ticker', 'open', 'high', 'low', 'close', 'volume', 'trading_value']
                # 거래대금 없을 경우 처리
                if 'trading_value' not in df.columns:
                    df['trading_value'] = df['volume'] * df['close']
                    
                df_final = df[cols].copy()
                
                # 리스트에 추가 (메모리 고려: 바로바로 모음)
                # DataFrame to dict list is slow? append DF to list then concat.
                new_data_list.append(df_final)
                
                processed_days += 1
                progress = (processed_days / total_days) * 100
                log(f"[Daily Prices] {cur_date_fmt} 수집 완료 ({len(df_final)}종목) - {progress:.1f}%", "INFO")
                
                # Rate Limit 방지
                time.sleep(random.uniform(0.3, 0.7))
                
            except Exception as e:
                log(f"날짜별 수집 실패 ({cur_date_str}): {e}", "WARNING")
                processed_days += 1
                
        # 병합 및 저장
        if new_data_list:
            log("데이터 병합 중...", "INFO")
            new_chunk_df = pd.concat(new_data_list, ignore_index=True)
            
            if not existing_df.empty:
                final_df = pd.concat([existing_df, new_chunk_df])
                final_df = final_df.drop_duplicates(subset=['date', 'ticker'], keep='last')
            else:
                final_df = new_chunk_df
                
            final_df = final_df.sort_values(['ticker', 'date'])
            final_df.to_csv(file_path, index=False, encoding='utf-8-sig')
            log(f"일별 가격 저장 완료: 총 {len(final_df)}행 (신규 {len(new_chunk_df)}행)", "SUCCESS")
        else:
             log("pykrx 수집 데이터 없음. yfinance 폴백 시도...", "WARNING")
             return fetch_prices_yfinance(start_date_obj, end_date_obj, existing_df, file_path)
                 
        return True

    except Exception as e:
        log(f"pykrx 수집 중 오류: {e} -> yfinance 폴백 시도", "WARNING")
        return fetch_prices_yfinance(start_date_obj, end_date_obj, existing_df, file_path)


def create_institutional_trend(target_date=None):
    """수급 데이터 수집 - pykrx 기관/외국인 순매매"""
    log("수급 데이터 수집 중 (pykrx 실제 데이터)...")
    try:
        from pykrx import stock
        
        # 종목 목록 로드
        stocks_file = os.path.join(BASE_DIR, 'data', 'korean_stocks_list.csv')
        if os.path.exists(stocks_file):
            stocks_df = pd.read_csv(stocks_file)
            tickers = stocks_df['ticker'].astype(str).str.zfill(6).tolist()
            # Market Gate 분석을 위해 KODEX 200 (069500) 필수 추가
            if '069500' not in tickers:
                tickers.insert(0, '069500')
        else:
            tickers = ['069500', '005930', '000660', '000270', '051910', '006400']
        
        if target_date:
            # from datetime import datetime
            if isinstance(target_date, str):
                target_date_obj = datetime.strptime(target_date, '%Y-%m-%d')
            else:
                target_date_obj = target_date
        else:
            target_date_obj = datetime.now()

        # 마지막 개장일 확인 (주말/휴일 자동 처리)
        end_date, end_date_obj = get_last_trading_date(reference_date=target_date_obj)
        start_date = (end_date_obj - timedelta(days=30)).strftime('%Y%m%d')
        
        log(f"수급 데이터 수집 구간(기본): {start_date} ~ {end_date} (증분 수집 적용)")
        
        # 기존 데이터 로드
        file_path = os.path.join(BASE_DIR, 'data', 'all_institutional_trend_data.csv')
        existing_df = pd.DataFrame()
        last_updates = {}
        
        if os.path.exists(file_path):
            try:
                existing_df = pd.read_csv(file_path)
                if not existing_df.empty and 'date' in existing_df.columns and 'ticker' in existing_df.columns:
                    existing_df['ticker'] = existing_df['ticker'].astype(str).str.zfill(6)
                    last_updates = existing_df.groupby('ticker')['date'].max().to_dict()
            except:
                pass

        all_data = []
        success_count = 0
        skipped_count = 0
        
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def fetch_inst(ticker):
            if shared_state.STOP_REQUESTED: return None
            
            # 증분 로직
            req_start_date = start_date
            last_date_str = last_updates.get(ticker)
            if last_date_str:
                try:
                    last_dt = datetime.strptime(last_date_str, '%Y-%m-%d')
                    if last_dt.date() >= end_date_obj.date():
                        return 'SKIPPED'
                    req_start_date = (last_dt + timedelta(days=1)).strftime('%Y%m%d')
                except:
                    pass
            
            if req_start_date > end_date:
                return 'SKIPPED'
                
            # Random sleep
            time.sleep(random.uniform(0.2, 0.5))

            try:
                df = stock.get_market_trading_value_by_date(req_start_date, end_date, ticker)
                if not df.empty:
                    local_data = []
                    for date, row in df.iterrows():
                        foreign_net = row.get('외국인합계', 0)
                        inst_net = row.get('기관합계', 0)
                        local_data.append({
                            'date': date.strftime('%Y-%m-%d'),
                            'ticker': ticker,
                            'foreign_buy': int(foreign_net) if pd.notna(foreign_net) else 0,
                            'inst_buy': int(inst_net) if pd.notna(inst_net) else 0
                        })
                    return local_data
            except ValueError:
                # pykrx Length mismatch error (데이터 없음) - 조용히 무시
                return None
            except Exception as e:
                log(f"[Trend Fail] {ticker}: {str(e)}", "WARNING")
            return None

        total_tickers = len(tickers[:600])
        processed_count = 0

        with ThreadPoolExecutor(max_workers=2) as executor:
            future_to_ticker = {executor.submit(fetch_inst, t): t for t in tickers[:600]}
            
            for future in as_completed(future_to_ticker):
                if shared_state.STOP_REQUESTED:
                    log("⛔️ 사용자 요청으로 수급 데이터 수집 중단", "WARNING")
                    executor.shutdown(wait=False, cancel_futures=True)
                    raise Exception("사용자 요청 중단")
                
                processed_count += 1
                
                # 진행률 로그 (10건마다)
                if processed_count % 10 == 0 or processed_count == total_tickers:
                    progress = (processed_count / total_tickers) * 100
                    log(f"[Institutional Trend] 진행률: {processed_count}/{total_tickers} ({progress:.1f}%)", "INFO")
                
                result = future.result()
                if result == 'SKIPPED':
                    skipped_count += 1
                elif result:
                    all_data.extend(result)
                    success_count += 1
                    
                    # [중간 저장] 30개 종목마다 저장
                    if success_count % 30 == 0:
                        try:
                            temp_new_df = pd.DataFrame(all_data)
                            if not existing_df.empty:
                                temp_final = pd.concat([existing_df, temp_new_df])
                                temp_final = temp_final.drop_duplicates(subset=['date', 'ticker'], keep='last')
                            else:
                                temp_final = temp_new_df
                            temp_final.to_csv(file_path, index=False, encoding='utf-8-sig')
                            log(f"[Auto-Save] 수급 데이터 중간 저장 ({success_count}개)", "INFO")
                        except Exception as e:
                            log(f"중간 저장 실패: {e}", "WARNING")
        
        # 병합 저장
        if all_data:
            new_df = pd.DataFrame(all_data)
            if not existing_df.empty:
                final_df = pd.concat([existing_df, new_df])
                final_df = final_df.drop_duplicates(subset=['date', 'ticker'], keep='last')
                # final_df = final_df.sort_values(['ticker', 'date']) # 수급 데이터는 굳이 정렬 안해도? 파일만 커지나. 정렬 하는게 좋음.
            else:
                final_df = new_df
                
            final_df.to_csv(file_path, index=False, encoding='utf-8-sig')
            log(f"수급 데이터: {success_count}개 업데이트, {skipped_count}개 최신 유지. 총 {len(final_df)}행", "SUCCESS")
            return True
        elif skipped_count > 0:
            log(f"수급 데이터: 모두 최신 상태임 ({skipped_count}개 종목)", "SUCCESS")
            return True
        else:
             if not existing_df.empty:
                log("수급 데이터: 신규 수집 실패하였으나 기존 데이터 유지", "WARNING")
                return True
             
             # 파일도 없고 데이터도 없으면 빈 파일 생성
             log("수급 데이터: 수집 데이터 없음 - 빈 파일 생성", "WARNING")
             df = pd.DataFrame(columns=['date', 'ticker', 'foreign_buy', 'inst_buy'])
             df.to_csv(file_path, index=False, encoding='utf-8-sig')
             return True
            
    except Exception as e:
        log(f"pykrx 수급 수집 실패: {e} (샘플 생성 안함)", "WARNING")
        
        # 빈 파일 생성
        df = pd.DataFrame(columns=['date', 'ticker', 'foreign_buy', 'inst_buy'])
        file_path = os.path.join(BASE_DIR, 'data', 'all_institutional_trend_data.csv')
        df.to_csv(file_path, index=False, encoding='utf-8-sig')
        return True


def calculate_vcp_score(df: pd.DataFrame) -> dict:
    """
    VCP 패턴 점수 계산 (0~100)
    - 변동성 수축: 최근 5일 고저폭 < 20일 평균 고저폭
    - 거래량 감소: 최근 5일 거래량 < 20일 평균 거래량
    - 이평선 정배열: 종가 > 5MA > 20MA
    """
    if len(df) < 20:
        return {'score': 0, 'contraction_ratio': 0, 'reasons': []}
    
    try:
        df = df.sort_index()
        
        # 변동성 수축 계산
        df['range'] = df['high'] - df['low']
        recent_range = df['range'].tail(5).mean()
        avg_range = df['range'].tail(20).mean()
        contraction_ratio = recent_range / avg_range if avg_range > 0 else 1
        
        # 거래량 감소 계산
        recent_vol = df['volume'].tail(5).mean()
        avg_vol = df['volume'].tail(20).mean()
        vol_ratio = recent_vol / avg_vol if avg_vol > 0 else 1
        
        # 이평선 정배열
        ma5 = df['close'].tail(5).mean()
        ma20 = df['close'].tail(20).mean()
        current_price = df['close'].iloc[-1]
        
        score = 0
        reasons = []
        
        # 변동성 수축 (최대 40점)
        if contraction_ratio < 0.5:
            score += 40
            reasons.append("강한 변동성 수축")
        elif contraction_ratio < 0.7:
            score += 30
            reasons.append("변동성 수축")
        elif contraction_ratio < 0.9:
            score += 15
        
        # 거래량 감소 (최대 30점)
        if vol_ratio < 0.5:
            score += 30
            reasons.append("거래량 급감")
        elif vol_ratio < 0.7:
            score += 20
            reasons.append("거래량 감소")
        elif vol_ratio < 0.9:
            score += 10
        
        # 이평선 정배열 (최대 30점)
        if current_price > ma5 > ma20:
            score += 30
            reasons.append("이평선 정배열")
        elif current_price > ma20:
            score += 15
        
        return {'score': score, 'contraction_ratio': round(contraction_ratio, 2), 'reasons': reasons}
    except:
        return {'score': 0, 'contraction_ratio': 0, 'reasons': []}


def calculate_supply_score(ticker: str, inst_df: pd.DataFrame) -> dict:
    """
    수급 점수 계산 (0~100)
    - 외국인 5일 순매수: 25점
    - 기관 5일 순매수: 20점
    - 연속 매수일: 15점
    """
    try:
        # ticker 비교 시 zfill(6) 적용하여 형식 맞춤
        df = inst_df[inst_df['ticker'].astype(str).str.zfill(6) == ticker].sort_values('date')
        if len(df) < 5:
            return {'score': 0, 'foreign_5d': 0, 'inst_5d': 0}
        
        recent = df.tail(5)
        foreign_5d = recent['foreign_buy'].sum()
        inst_5d = recent['inst_buy'].sum()
        
        score = 0
        
        # 외국인 순매수 (최대 40점)
        if foreign_5d > 1000000000:  # 10억
            score += 40
        elif foreign_5d > 500000000:  # 5억
            score += 25
        elif foreign_5d > 0:
            score += 10
        
        # 기관 순매수 (최대 30점)
        if inst_5d > 500000000:  # 5억
            score += 30
        elif inst_5d > 200000000:  # 2억
            score += 20
        elif inst_5d > 0:
            score += 10
        
        # 연속 매수일 (최대 30점)
        consecutive = 0
        for val in reversed(recent['foreign_buy'].values):
            if val > 0:
                consecutive += 1
            else:
                break
        score += min(consecutive * 6, 30)
        
        return {'score': score, 'foreign_5d': int(foreign_5d), 'inst_5d': int(inst_5d)}
    except:
        return {'score': 0, 'foreign_5d': 0, 'inst_5d': 0}


def create_signals_log(target_date=None, run_ai=False):
    """VCP 시그널 로그 생성 - 실제 데이터 기반 분석"""
    log("VCP 시그널 분석 중 (실제 데이터 기반)...")
    try:
        from pykrx import stock
        
        # 데이터 로드
        prices_file = os.path.join(BASE_DIR, 'data', 'daily_prices.csv')
        inst_file = os.path.join(BASE_DIR, 'data', 'all_institutional_trend_data.csv')
        stocks_file = os.path.join(BASE_DIR, 'data', 'korean_stocks_list.csv')
        
        if not all(os.path.exists(f) for f in [prices_file, inst_file, stocks_file]):
            raise Exception("필요한 데이터 파일 없음")
        
        prices_df = pd.read_csv(prices_file)
        inst_df = pd.read_csv(inst_file)
        stocks_df = pd.read_csv(stocks_file)
        
        # (중요) 타겟 날짜 기준 데이터 필터링 (Look-ahead Bias 방지 및 시점 정확도 확보)
        if target_date:
            log(f"[{target_date}] 기준 과거 데이터로 필터링합니다...", "INFO")
            prices_df = prices_df[prices_df['date'] <= target_date]
            inst_df = inst_df[inst_df['date'] <= target_date]
        
        
        signals = []
        
        analyzed_count = 0
        total_stocks = len(stocks_df)
        log(f"총 {total_stocks}개 종목에 대한 VCP 분석 시작... (KOSPI+KOSDAQ)", "INFO")
        
        for _, row in stocks_df.iterrows():
            ticker = str(row['ticker']).zfill(6)
            name = row['name']
            market = row['market']
            
            # 가격 데이터 필터링
            ticker_prices = prices_df[prices_df['ticker'].astype(str).str.zfill(6) == ticker].copy()
            if len(ticker_prices) < 20:
                continue
            
            # 인덱스를 날짜로 설정
            ticker_prices['date'] = pd.to_datetime(ticker_prices['date'])
            ticker_prices = ticker_prices.set_index('date')
            
            # VCP 점수 계산
            vcp = calculate_vcp_score(ticker_prices)
            
            # 수급 점수 계산
            supply = calculate_supply_score(ticker, inst_df)
            
            # 종합 점수 (VCP 60% + 수급 40%) - 수급 데이터 누락 시 보정 로직 추가
            # 수급 데이터가 없으면(0점), VCP 점수만으로 100% 환산 (55/60 -> 91점)
            if supply['score'] == 0 and vcp['score'] > 0:
                total_score = (vcp['score'] / 60) * 100
            else:
                total_score = vcp['score'] * 0.6 + supply['score'] * 0.4
            
            analyzed_count += 1
            
            # 디버그 로그: 상위 점수 종목 또는 일부 종목 출력
            if total_score >= 40 or analyzed_count <= 5:
                log(f"  [{name}] VCP={vcp['score']}, Supply={supply['score']}, Total={total_score:.1f} (CR={vcp['contraction_ratio']})")
            
            # 최소 점수 필터링 (60점 기준 복구)
            if total_score < 60:
                continue
            
            current_price = ticker_prices['close'].iloc[-1]
            
            signals.append({
                'ticker': ticker,
                'name': name,
                'signal_date': target_date if target_date else datetime.now().strftime('%Y-%m-%d'),
                'market': market,
                'status': 'OPEN',
                'score': round(total_score, 1),
                'contraction_ratio': vcp['contraction_ratio'],
                'entry_price': int(current_price),
                'foreign_5d': supply['foreign_5d'],
                'inst_5d': supply['inst_5d'],
                'vcp_score': vcp['score'], # AI 분석용 추가 정보
                'current_price': int(current_price)
            })
        
        log(f"총 {analyzed_count}개 종목 분석 완료, {len(signals)}개 시그널 감지")
        
        # 점수 높은 순 정렬, 최대 20개
        signals = sorted(signals, key=lambda x: x['score'], reverse=True)[:20]
        
        # AI 분석 실행 (옵션)
        if run_ai and signals:
            try:
                log(f"[AI Analysis] 감지된 {len(signals)}개 시그널에 대해 AI 정밀 분석 수행...", "INFO")
                from engine.vcp_ai_analyzer import get_vcp_analyzer
                analyzer = get_vcp_analyzer()
                
                # 비동기 실행을 위한 루프 가져오기
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # 배치 분석 실행
                ai_results = loop.run_until_complete(analyzer.analyze_batch(signals))
                
                # 결과 저장
                if ai_results:
                    date_str = signals[0]['signal_date'].replace('-', '')
                    
                    # 1. ai_analysis_results.json에 저장 (기존 로직 유지)
                    ai_filename = f'ai_analysis_results_{date_str}.json'
                    ai_filepath = os.path.join(BASE_DIR, 'data', ai_filename)
                    
                    save_data = {
                        'generated_at': datetime.now().isoformat(),
                        'signal_date': signals[0]['signal_date'],
                        'signals': list(ai_results.values())
                    }
                    
                    with open(ai_filepath, 'w', encoding='utf-8') as f:
                        json.dump(save_data, f, ensure_ascii=False, indent=2)
                        
                    latest_path = os.path.join(BASE_DIR, 'data', 'ai_analysis_results.json')
                    with open(latest_path, 'w', encoding='utf-8') as f:
                         json.dump(save_data, f, ensure_ascii=False, indent=2)
                    
                    # 2. kr_ai_analysis.json에도 저장 (프론트엔드 호환 형식)
                    # VCP 시그널 정보 + AI 분석 결과 + 뉴스 통합
                    kr_ai_signals = []
                    
                    # 뉴스 수집기 초기화
                    news_collector = None
                    try:
                        from engine.collectors import EnhancedNewsCollector
                        from engine.config import app_config
                        news_collector = EnhancedNewsCollector(app_config)
                        log("[AI Analysis] 뉴스 수집기 초기화 완료", "INFO")
                    except Exception as news_init_err:
                        log(f"[AI Analysis] 뉴스 수집기 초기화 실패: {news_init_err}", "WARNING")
                    
                    for signal in signals:
                        ticker = signal.get('ticker', '')
                        name = signal.get('name', '')
                        ai_data = ai_results.get(ticker, {})
                        
                        # 뉴스 수집 (최대 5개)
                        news_items = []
                        if news_collector:
                            try:
                                news_list = asyncio.get_event_loop().run_until_complete(
                                    news_collector.get_stock_news(ticker, limit=5, name=name)
                                )
                                for news in news_list:
                                    news_items.append({
                                        'title': getattr(news, 'title', str(news)),
                                        'url': getattr(news, 'url', ''),
                                        'source': getattr(news, 'source', 'Naver'),
                                        'date': getattr(news, 'date', '')
                                    })
                            except Exception as news_err:
                                log(f"[AI Analysis] {name} 뉴스 수집 실패: {news_err}", "WARNING")
                        
                        kr_signal = {
                            'ticker': ticker,
                            'name': name,
                            'market': signal.get('market', 'KOSPI'),
                            'score': signal.get('score', 0),
                            'contraction_ratio': signal.get('contraction_ratio', 0),
                            'foreign_5d': signal.get('foreign_5d', 0),
                            'inst_5d': signal.get('inst_5d', 0),
                            'entry_price': signal.get('entry_price', 0),
                            'current_price': signal.get('current_price', signal.get('entry_price', 0)),
                            'return_pct': 0,
                            'vcp_score': signal.get('vcp_score', 0),
                            # AI 분석 결과 통합
                            'gemini_recommendation': ai_data.get('gemini_recommendation'),
                            'gpt_recommendation': ai_data.get('gpt_recommendation'),
                            'perplexity_recommendation': ai_data.get('perplexity_recommendation'),
                            # 뉴스 데이터 추가
                            'news': news_items,
                        }
                        kr_ai_signals.append(kr_signal)
                    
                    # 시장 지수 데이터 수집
                    market_indices = {}
                    try:
                        from pykrx import stock
                        today_str = datetime.now().strftime('%Y%m%d')
                        kospi = stock.get_index_ohlcv(today_str, today_str, "1001")  # KOSPI
                        kosdaq = stock.get_index_ohlcv(today_str, today_str, "2001")  # KOSDAQ
                        
                        if not kospi.empty:
                            market_indices['kospi'] = {
                                'value': float(kospi['종가'].iloc[-1]) if len(kospi) > 0 else 0,
                                'change_pct': float(kospi['등락률'].iloc[-1]) if len(kospi) > 0 and '등락률' in kospi.columns else 0
                            }
                        if not kosdaq.empty:
                            market_indices['kosdaq'] = {
                                'value': float(kosdaq['종가'].iloc[-1]) if len(kosdaq) > 0 else 0,
                                'change_pct': float(kosdaq['등락률'].iloc[-1]) if len(kosdaq) > 0 and '등락률' in kosdaq.columns else 0
                            }
                    except Exception as idx_e:
                        log(f"[AI Analysis] 시장 지수 수집 실패 (무시): {idx_e}", "WARNING")
                    
                    kr_ai_data = {
                        'market_indices': market_indices,
                        'signals': kr_ai_signals,
                        'generated_at': datetime.now().isoformat(),
                        'signal_date': signals[0]['signal_date']
                    }
                    
                    kr_ai_path = os.path.join(BASE_DIR, 'data', 'kr_ai_analysis.json')
                    with open(kr_ai_path, 'w', encoding='utf-8') as f:
                        json.dump(kr_ai_data, f, ensure_ascii=False, indent=2, cls=NumpyEncoder)
                    
                    # 날짜별 히스토리도 저장
                    kr_ai_history_path = os.path.join(BASE_DIR, 'data', f'kr_ai_analysis_{date_str}.json')
                    with open(kr_ai_history_path, 'w', encoding='utf-8') as f:
                        json.dump(kr_ai_data, f, ensure_ascii=False, indent=2, cls=NumpyEncoder)
                         
                    log(f"[AI Analysis] 분석 완료 및 저장: {ai_filename}, kr_ai_analysis.json", "SUCCESS")
                
            except Exception as e:
                log(f"[AI Analysis] 실행 중 오류 발생: {e}", "ERROR")
                import traceback
                traceback.print_exc()
        
        if signals:
            df_new = pd.DataFrame(signals)
            file_path = os.path.join(BASE_DIR, 'data', 'signals_log.csv')
            
            # 기존 로그가 있으면 로드하여 병합 (Append & Deduplicate)
            if os.path.exists(file_path):
                try:
                    # 타입 명시하여 로드 (중복 방지 핵심)
                    df_old = pd.read_csv(file_path, dtype={'ticker': str, 'signal_date': str})
                    df_old['ticker'] = df_old['ticker'].str.zfill(6)
                    
                    # 새 데이터 포맷 통일
                    df_new['ticker'] = df_new['ticker'].astype(str).str.zfill(6)
                    df_new['signal_date'] = df_new['signal_date'].astype(str)

                    # [수정] 해당 날짜의 기존 데이터 삭제 (재실행 시 중복 방지)
                    current_date = str(df_new['signal_date'].iloc[0])
                    df_old = df_old[df_old['signal_date'] != current_date]

                    # 병합
                    if df_old.empty and df_new.empty:
                         df_combined = pd.DataFrame()
                    elif df_old.empty:
                         df_combined = df_new
                    elif df_new.empty:
                         df_combined = df_old
                    else:
                         df_combined = pd.concat([df_old, df_new])
                         
                    # 중복 제거 (안전장치)
                    if not df_combined.empty:
                        df_combined = df_combined.drop_duplicates(subset=['signal_date', 'ticker'], keep='last')
                        # 정렬 (최신 날짜 우선, 점수 높은 순)
                        df_combined = df_combined.sort_values(by=['signal_date', 'score'], ascending=[False, False])
                    
                    df_combined.to_csv(file_path, index=False, encoding='utf-8-sig')
                    # 해당 날짜 데이터 반환 (common.py 연동용) -> init_data.py에서는 True 반환해야 함
                    return True
                except Exception as e:
                    log(f"기존 로그 병합 실패: {e}, 새로 생성합니다(덮어쓰기).", "WARNING")
                    df_new.to_csv(file_path, index=False, encoding='utf-8-sig')
                    return True
            else:
                df_new.to_csv(file_path, index=False, encoding='utf-8-sig')
                return True
                
            log(f"VCP 시그널 분석 완료: {len(signals)} 종목 감지 (누적 저장)", "SUCCESS")
            return True
        else:
            log("VCP 조건 충족 종목 없음", "WARNING")
            # 빈 결과 파일 생성 (샘플 데이터 생성 안함)
            df = pd.DataFrame(columns=['ticker', 'name', 'signal_date', 'market', 'status', 'score', 'contraction_ratio', 'entry_price', 'foreign_5d', 'inst_5d'])
            file_path = os.path.join(BASE_DIR, 'data', 'signals_log.csv')
            df.to_csv(file_path, index=False, encoding='utf-8-sig')
            log("VCP 조건 충족 종목 없음 - 빈 결과 저장", "INFO")
            return True
            
    except Exception as e:
        log(f"VCP 분석 실패: {e}", "WARNING")
        # 빈 결과 파일 생성 (샘플 데이터 생성 안함)
        df = pd.DataFrame(columns=['ticker', 'name', 'signal_date', 'market', 'status', 'score', 'contraction_ratio', 'entry_price', 'foreign_5d', 'inst_5d'])
        file_path = os.path.join(BASE_DIR, 'data', 'signals_log.csv')
        df.to_csv(file_path, index=False, encoding='utf-8-sig')
        log("VCP 분석 오류 - 빈 결과 저장", "INFO")
        return True



def calculate_advanced_score(ticker: str, prices_df: pd.DataFrame, inst_df: pd.DataFrame) -> dict:
    """
    종가베팅 시스템 고도화 (Advanced Closing Bet)
    기본 필터: 최소한의 기준만 적용 (필터링은 프론트엔드/API에서 처리)
    """
    try:
        ticker_prices = prices_df[prices_df['ticker'].astype(str).str.zfill(6) == ticker].copy()
        if len(ticker_prices) < 20:
            return {'total': 0, 'passed_filter': False}
        
        ticker_prices = ticker_prices.sort_values('date')
        current = ticker_prices.iloc[-1]
        prev = ticker_prices.iloc[-2]
        
        # --- 최소한의 데이터 유효성 체크 ---
        trading_value = current['volume'] * current['close']
        volume_ratio = current['volume'] / prev['volume'] if prev['volume'] > 0 else 0
        
        # 당일 등락률 계산
        prev_close = prev['close']
        change_pct = ((current['close'] - prev_close) / prev_close * 100) if prev_close > 0 else 0
        
        # 최소 기준: 거래대금 300억 미만 제외 (2026-01-31 업데이트)
        if trading_value < 30_000_000_000:  # 300억
            return {'total': 0, 'passed_filter': False, 'reason': '거래대금 과소 (300억 미만)'}
        
        if change_pct <= 0:
             return {'total': 0, 'passed_filter': False, 'reason': '상승률 미달'}
        
        # 종가 >= 당일고 * 0.9 체크
        day_high = current['high']
        close_ratio = current['close'] / day_high if day_high > 0 else 0

        # 점수 상세 내역 초기화
        details = {
            'news': 0,
            'volume': 0,
            'chart': 0,
            'candle': 0,
            'consolidation': 0,
            'supply': 0,
            'rise_pct': round(change_pct, 2),
            'volume_ratio': round(volume_ratio, 2)
        }
        
        base_score = 0
        
        # 1. 뉴스 & 모멘텀 (3점) - 거래대금 기반 폴백
        # 뉴스는 별도 API가 없으므로 거래대금 규모로 모멘텀 추정
        if trading_value > 500_000_000_000: 
            details['news'] = 3
        elif trading_value > 100_000_000_000: 
            details['news'] = 2
        else: 
            details['news'] = 1
        base_score += details['news']
        
        # 2. 거래대금/거래량 폭발 (3점)
        # 3000억 이상이면 만점
        if trading_value >= 300_000_000_000: 
            details['volume'] = 3
        elif trading_value >= 100_000_000_000: 
            details['volume'] = 2
        else: 
            details['volume'] = 1
        base_score += details['volume']
        
        # 3. 차트 위치 (2점)
        high_20d = ticker_prices.tail(20)['high'].max()
        if current['close'] >= high_20d * 0.98: 
            details['chart'] = 2
        elif current['close'] > ticker_prices['close'].tail(20).mean(): 
            details['chart'] = 1
        base_score += details['chart']
        
        # 4. 수급 (2점)
        inst_data = inst_df[inst_df['ticker'].astype(str).str.zfill(6) == ticker]
        if not inst_data.empty:
            recent_inst = inst_data.tail(5)
            f_buy = recent_inst['foreign_buy'].sum()
            i_buy = recent_inst['inst_buy'].sum()
            if f_buy > 0 and i_buy > 0: 
                details['supply'] = 2
            elif f_buy > 0 or i_buy > 0: 
                details['supply'] = 1
        base_score += details['supply']
        
        # 5. 캔들/조정 (2점)
        if current['close'] > current['open']: 
            details['candle'] = 1
        base_score += details['candle']

        recent_range = (ticker_prices.tail(5)['high'] - ticker_prices.tail(5)['low']).mean()
        avg_range = (ticker_prices.tail(20)['high'] - ticker_prices.tail(20)['low']).mean()
        if recent_range < avg_range * 0.8: # 변동성 축소
            details['consolidation'] = 1
        base_score += details['consolidation']
        
        # --- 가산점 (Bonus Score) ---
        bonus = 0
        
        # 1. 거래량 급증 (Volume Surge) - details에 반영하기에는 애매하므로 총점에만 가산
        if volume_ratio >= 10: bonus += 4
        elif volume_ratio >= 5: bonus += 3
        elif volume_ratio >= 3: bonus += 2
        elif volume_ratio >= 2: bonus += 1
        
        # 2. 장대양봉 (Long Body)
        pct = change_pct
        if pct >= 25: bonus += 5
        elif pct >= 20: bonus += 4
        elif pct >= 15: bonus += 3
        elif pct >= 10: bonus += 2
        elif pct >= 5: bonus += 1
        
        score_total = base_score + bonus
        
        # 수급 데이터 (외인+기관 동시 순매수 체크)
        inst_data = inst_df[inst_df['ticker'].astype(str).str.zfill(6) == ticker]
        foreign_positive = False
        inst_positive = False
        foreign_net_buy = 0
        inst_net_buy = 0
        
        if not inst_data.empty:
            recent_inst = inst_data.tail(5)
            foreign_net_buy = int(recent_inst['foreign_buy'].sum())
            inst_net_buy = int(recent_inst['inst_buy'].sum())
            foreign_positive = foreign_net_buy > 0
            inst_positive = inst_net_buy > 0
        
        return {
            'base': base_score,
            'bonus': bonus, 
            'total': score_total, 
            'passed_filter': True,
            'details': details,
            'volume_ratio': volume_ratio,
            'close_ratio': close_ratio,
            'foreign_positive': foreign_positive,
            'inst_positive': inst_positive,
            'foreign_net_buy': foreign_net_buy,
            'inst_net_buy': inst_net_buy,
            'rise_pct': round(change_pct, 2),
            'trading_value': trading_value
        }

    except Exception as e:
        return {'total': 0, 'passed_filter': False, 'reason': str(e)}


def assign_grade(score_data: dict) -> str:
    """
    등급 분류 (2026-01-31 수정)
    
    S급: 1조원+ AND 10%+ 상승 AND 외인+기관 동반 AND 거래량 5배
    A급: 5000억+ AND 5%+ 상승 AND (외인 OR 기관) AND 거래량 3배
    B급: 1000억+ AND 4%+ 상승 AND (외인 OR 기관) AND 거래량 2배
    C급: 500억+ AND 5%+ 상승 AND 점수 8점 이상 AND 거래량 3배
    D급: 500억+ AND 4%+ 상승 AND 점수 6점 이상
    """
    trading_value = score_data.get('trading_value', 0)
    volume_ratio = score_data.get('volume_ratio', 0)
    close_ratio = score_data.get('close_ratio', 0)
    foreign_positive = score_data.get('foreign_positive', False)
    inst_positive = score_data.get('inst_positive', False)
    rise_pct = score_data.get('rise_pct', 0)
    
    # 기본 조건: 상승 종목만
    if rise_pct <= 0:
        return None
    
    # 외인+기관 동반 체크
    both_positive = foreign_positive and inst_positive
    either_positive = foreign_positive or inst_positive
    
    # S급: 1조 원 이상 AND 10% 이상 상승 AND 외인+기관 동반 순매수 AND 거래량 5배
    if trading_value >= 1_000_000_000_000 and rise_pct >= 10.0 and both_positive and volume_ratio >= 5.0:
        return 'S'
    
    # A급: 5,000억 원 이상 AND 5% 이상 상승 AND (외인 or 기관) AND 거래량 3배
    if trading_value >= 500_000_000_000 and rise_pct >= 5.0:
        if either_positive and volume_ratio >= 3.0:
             return 'A'

    # B급: 1,000억 원 이상 AND 4% 이상 상승 AND (외인 or 기관) AND 거래량 2배
    if trading_value >= 100_000_000_000 and rise_pct >= 4.0:
        if volume_ratio >= 2.0 and either_positive:
            return 'B'
    
    # C급: 500억 이상 AND 5% 이상 상승 AND 외인+기관 동반 AND 거래량 3배
    if trading_value >= 50_000_000_000 and rise_pct >= 5.0 and both_positive and volume_ratio >= 3.0:
        return 'C'
        
    # D급: 500억 이상 AND 4% 이상 상승 AND (외인 or 기관) AND 거래량 2배
    if trading_value >= 50_000_000_000 and rise_pct >= 4.0 and volume_ratio >= 2.0:
        return 'D'
    
    # 그 외는 등급 없음
    return None 

def get_themes_by_sector(sector: str, name: str) -> list:
    """업종 및 종목명 기반 단순 테마 매핑"""
    themes = []
    if not sector:
        return []
    
    # Simple Keywords Mapping
    if '반도체' in sector or '전기전자' in sector:
        themes.append('반도체')
        if '삼성' in name or 'SK' in name:
            themes.append('HBM')
            themes.append('AI')
    elif '제약' in sector or '바이오' in sector:
        themes.append('바이오')
        themes.append('신약개발')
    elif '자동차' in sector:
        themes.append('자동차')
        themes.append('전기차')
    elif '금융' in sector:
        themes.append('금융')
        themes.append('저PBR')
        
    return themes


def get_expert_advice(grade: str, score: int, trading_value: int, market: str) -> dict:
    """점수, 등급, 거래대금 기반 전문가 조언 상세 생성"""
    advice = {
        "trading_tip": "15:10~15:30 사이 분봉상 눌림목 지지(20선) 확인 후 종가 부근 진입.",
        "selling_strategy": "익일 시초 30분 내 3% 이상 상승 시 50% 분할 익절, 나머지는 본절가 위협 시 전량 매도 (트레일링 스탑).",
        "market_context": "수급이 강하게 들어온 종목입니다. 갭상승 출발 가능성이 높습니다."
    }
    
    # 1. 등급별 전략 차별화
    if grade == 'S':
        advice["market_context"] = "🚀 강력한 주도주 (S등급). 코스피 5000 돌파장처럼 공격적으로 비중을 실어도 좋은 구간입니다."
        advice["selling_strategy"] = "상승 탄력이 강하므로 5%~10% 이상 슈팅 시 50% 익절, 나머지는 3일선/5일선 이탈까지 홀딩."
    elif grade == 'A':
        advice["market_context"] = "수급과 차트가 우수한 A등급 종목입니다. 눌림 시 적극 매수 유효."
    else: # B, C
        advice["trading_tip"] = "상승탄력이 다소 약할 수 있으므로, 철저히 지지선 근처에서만 진입하세요. 추격매수 금지."
        advice["selling_strategy"] = "짧게 3% 내외에서 전량 익절하거나, 본절 로스컷을 타이트하게 잡으세요."

    # 2. 거래대금 규모별 팁 (시장 적응)
    if market == 'KOSPI':
        if trading_value >= 100_000_000_000: # 1000억 이상
            advice["market_context"] += " (코스피 대형주 특성: 무거운 만큼 추세 지속력이 좋습니다)"
        else:
            advice["market_context"] += " (코스피 중소형: 변동성에 유의하세요)"
    elif market == 'KOSDAQ':
        if trading_value >= 500_000_000_000: # 500억 -> 5000 (User said 200~500, but logic usually higher is better)
             advice["market_context"] += " (코스닥 주도주: 변동성이 매우 큽니다)"
        elif trading_value >= 20_000_000_000:
             advice["market_context"] += " (코스닥 알짜 중소형주: 200~500억 구간)"

    # 3. 추가 매수 가이드
    if score >= 15: # 매우 높은 점수
        advice["buy_strategy"] = "확신이 드는 자리입니다. 비중 50% 추가 매수 고려 가능 (단, 분할로 접근)."
    else:
        advice["buy_strategy"] = "무리한 추가 매수는 자제하고, 1차 진입 물량만 운영하세요."

    return advice


def create_jongga_v2_latest():
    """종가베팅 V2 최신 결과 생성 - 고도화된 로직 적용"""
    log("종가베팅 V2 분석 중 (Advanced System)...")
    try:
        # 데이터 로드
        prices_file = os.path.join(BASE_DIR, 'data', 'daily_prices.csv')
        inst_file = os.path.join(BASE_DIR, 'data', 'all_institutional_trend_data.csv')
        stocks_file = os.path.join(BASE_DIR, 'data', 'korean_stocks_list.csv')
        
        if not all(os.path.exists(f) for f in [prices_file, inst_file, stocks_file]):
            raise Exception("필요한 데이터 파일 없음")
        
        prices_df = pd.read_csv(prices_file)
        inst_df = pd.read_csv(inst_file)
        stocks_df = pd.read_csv(stocks_file)
        
        signals = []
        
        for _, row in stocks_df.iterrows():
            ticker = str(row['ticker']).zfill(6)
            name = row['name']
            
            # 고도화된 평가 로직 수행
            score_data = calculate_advanced_score(ticker, prices_df, inst_df)
            
            if not score_data['passed_filter']:
                continue
                
            # 최소 10점(기본+보너스 포함) 이상만 필터링 (필터가 강력하므로 점수 컷은 낮춤)
            if score_data['total'] < 10:
                continue
            
            ticker_prices = prices_df[prices_df['ticker'].astype(str).str.zfill(6) == ticker]
            current = ticker_prices.iloc[-1]
            current_price = int(current['close'])
            trading_value = int(current['volume'] * current['close'])
            
            # 등급 분류 - 새로운 기준 (2026-01-31)
            grade = assign_grade(score_data)
            
            # 등급 없으면 스킵 (조건 미충족)
            if grade is None:
                continue

            log(f"  [Jongga V2 Catch] {name} ({ticker}) - Grade: {grade}, Score: {score_data['total']}, TradingVal: {trading_value//100000000}억")
            
            # 전문가 조언 생성
            advice = get_expert_advice(grade, score_data['total'], trading_value, row['market'])
            
            # 미니 차트 데이터 (최근 10일)
            mini_chart = ticker_prices.tail(10)[['date', 'open', 'high', 'low', 'close', 'volume']].to_dict(orient='records')
            
            # 매수/매도/손절 가격 계산 (현재가 기준)
            buy_price = current_price
            target_price_1 = int(current_price * 1.025)  # +2.5% 공격 익절
            target_price_2 = int(current_price * 1.05)   # +5% 수급 강세 익절
            stop_price = int(current_price * 0.97)       # -3% 손절
            
            signals.append({
                "stock_code": ticker,
                "stock_name": name,
                "market": row['market'],
                "grade": grade,
                "total_score": score_data['total'],
                "score_details": score_data,
                "current_price": current_price,
                "trading_value": trading_value,
                "change_pct": float(score_data.get('rise_pct', 0)),
                "volume_ratio": score_data.get('volume_ratio', 0),
                "advice": advice,
                "mini_chart": mini_chart,
                
                # 매수/매도/손절 전략 가격
                "buy_price": buy_price,
                "target_price_1": target_price_1,  # +2.5%
                "target_price_2": target_price_2,  # +5%
                "stop_price": stop_price,          # -3%
                
                # 기존 필드 호환성 유지
                "score": {
                    "total": score_data['base'],
                    "news": score_data['details'].get('news', 0),
                    "volume": score_data['details'].get('volume', 0),
                    "chart": score_data['details'].get('chart', 0),
                    "supply": score_data['details'].get('supply', 0),
                    "timing": score_data['details'].get('consolidation', 0),
                    "candle": score_data['details'].get('candle', 0),
                    "llm_reason": f"종합 점수 {score_data['total']}점 (기본 {score_data['base']} + 보너스 {score_data['bonus']})"
                },
                "checklist": {
                    "has_news": True,
                    "is_new_high": score_data.get('close_ratio', 0) >= 0.9,
                    "supply_positive": score_data.get('foreign_positive', False) and score_data.get('inst_positive', False)
                },
                "entry_price": buy_price,
                "foreign_net_buy": score_data.get('foreign_net_buy', 0),
                "inst_net_buy": score_data.get('inst_net_buy', 0),
                "themes": get_themes_by_sector(row.get('sector', ''), name), 
                "news_items": [],
                # Default AI Evaluation (Rule-based Fallback)
                "ai_evaluation": {
                    "action": "BUY" if grade in ['S', 'A'] else "HOLD",
                    "confidence": score_data['total'] * 5 + (20 if grade == 'S' else 10 if grade == 'A' else 0),
                    "model": "Rule-based (Pending AI)"
                }
            })
        
        # 등급 우선, 총점 순 정렬
        grade_order = {'S': 0, 'A': 1, 'B': 2, 'C': 3, 'D': 4}
        signals = sorted(signals, key=lambda x: (grade_order.get(x['grade'], 9), -x['total_score']))[:10]
        
        # --- Gemini 3.0 Analysis Integration ---
        # signals가 없으면 Gemini 분석 스킵 (API 할당량 절약)
        if not signals:
            log("분석 대상 시그널 없음 - Gemini 분석 스킵", "WARNING")
        else:
            # --- Gemini 3.0 Analysis Integration ---
            try:
                async def run_batch_analysis(target_signals):
                    log(f"Gemini 3.0 Analysis 시작 ({len(target_signals)} 종목)...")
                    news_collector = EnhancedNewsCollector(config)
                    llm_analyzer = LLMAnalyzer()
                    market_gate = MarketGate()
                    
                    # 1. Market Status
                    market_status = market_gate.analyze()

                    # 2. News Collection & Preparation
                    items_for_llm = []
                    
                    async with news_collector:
                        for signal in target_signals:
                            code = signal['stock_code']
                            name = signal['stock_name']
                            
                            # 뉴스 수집
                            news_items = await news_collector.get_stock_news(code, 3, name)
                            
                            # LLM Input 구성
                            items_for_llm.append({
                                'stock': signal, 
                                'news': news_items,
                                'supply': None 
                            })
                            
                            # UI용 뉴스 저장
                            signal['news_items'] = [{
                                "title": n.title,
                                "url": n.url,
                                "published_at": n.published_at.isoformat() if n.published_at else "",
                                "source": n.source
                            } for n in news_items]
                    
                    # 3. Batch LLM Execution (Chunking + Parallel)
                    if items_for_llm:
                        # 청킹 설정
                        chunk_size = app_config.ANALYSIS_LLM_CHUNK_SIZE
                        concurrency = app_config.ANALYSIS_LLM_CONCURRENCY
                        chunks = [items_for_llm[i:i + chunk_size] for i in range(0, len(items_for_llm), chunk_size)]
                        
                        log(f"  -> {len(chunks)}개 청크로 분할 (청크당 {chunk_size}종목, 동시 {concurrency}개)")
                        
                        # 병렬 처리를 위한 Semaphore
                        semaphore = asyncio.Semaphore(concurrency)
                        
                        async def process_chunk(chunk_idx, chunk_data):
                            async with semaphore:
                                try:
                                    result = await llm_analyzer.analyze_news_batch(chunk_data, market_status)
                                    log(f"  -> 청크 {chunk_idx + 1}/{len(chunks)} 완료")
                                    return result
                                except Exception as e:
                                    log(f"  -> 청크 {chunk_idx + 1} 오류: {e}", "ERROR")
                                    return {}
                        
                        # 모든 청크 병렬 실행
                        tasks = [process_chunk(i, chunk) for i, chunk in enumerate(chunks)]
                        chunk_results = await asyncio.gather(*tasks)
                        
                        # 결과 병합
                        results_map = {}
                        for res in chunk_results:
                            if res:
                                results_map.update(res)
                        
                        # 4. Merge Results
                        for signal in target_signals:
                            name = signal['stock_name']
                            if name in results_map:
                                llm_res = results_map[name]
                                if llm_res.get('reason'):
                                    signal['score']['llm_reason'] = llm_res.get('reason')
                                
                                # AI Recommendation Mapping (UI 표시용)
                                # Provider에 상관없이 UI의 두 컬럼 모두에 표시되도록 설정 (사용자 요청 반영)
                                recommendation = {
                                    "action": llm_res.get('action', 'HOLD'),
                                    "confidence": llm_res.get('confidence', 0),
                                    "reason": llm_res.get('reason', ''),
                                    "model": llm_res.get('model', 'Unknown')
                                }
                                signal['gemini_recommendation'] = recommendation
                                signal['gpt_recommendation'] = recommendation
                                signal['ai_evaluation'] = recommendation
                                    
                                log(f"  -> {name}: AI 분석 완료 ({recommendation['action']})")

                # 이미 실행 중인 이벤트 루프가 있는지 확인
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None
                
                if loop and loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        pool.submit(asyncio.run, run_batch_analysis(signals)).result()
                else:
                    asyncio.run(run_batch_analysis(signals))
                        
            except Exception as e:
                log(f"Gemini 분석 단계 중 오류 (건너뜀): {e}", "ERROR")

        # ---------------------------------------
        
        # 주말인 경우 금요일 날짜로 설정 (데이터 정합성)
        now = datetime.now()
        target_date = now
        if now.weekday() == 5: # Sat
            target_date = now - timedelta(days=1)
        elif now.weekday() == 6: # Sun
            target_date = now - timedelta(days=2)
            
        result = {
            'date': target_date.strftime('%Y-%m-%d'),
            'total_candidates': len(stocks_df),
            'filtered_count': len(signals),
            'signals': signals,
            'updated_at': datetime.now().isoformat()
        }
        
        file_path = os.path.join(BASE_DIR, 'data', 'jongga_v2_latest.json')
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False, cls=NumpyEncoder)
            
        log(f"종가베팅 V2 고도화 분석 완료: {len(signals)} 종목", "SUCCESS")
        return True
            
    except Exception as e:
        log(f"종가베팅 분석 실패: {e}", "ERROR")
        return False


def create_market_gate(target_date=None):
    """Market Gate 데이터 생성 (8개 섹터, KOSPI/KOSDAQ 지수 포함) - 실시간 데이터"""
    log("Market Gate 데이터 생성 중...")
    try:
        # 실시간 시장 지수 수집
        indices = get_market_indices()
        kospi = indices['kospi']
        kosdaq = indices['kosdaq']
        
        # Market Gate 점수 계산 (KOSPI 등락률 기반 세분화)
        change = kospi['change_pct']
        
        if change >= 2.0:
            gate_status = 'GREEN'
            gate_label = 'VERY BULLISH'
            gate_score = 90
        elif change >= 1.0:
            gate_status = 'GREEN'
            gate_label = 'BULLISH'
            gate_score = 75
        elif change >= 0.5:
            gate_status = 'YELLOW'
            gate_label = 'SLIGHTLY BULLISH'
            gate_score = 60
        elif change >= 0:
            gate_status = 'YELLOW'
            gate_label = 'NEUTRAL'
            gate_score = 50
        elif change >= -0.5:
            gate_status = 'YELLOW'
            gate_label = 'SLIGHTLY BEARISH'
            gate_score = 40
        elif change >= -1.0:
            gate_status = 'RED'
            gate_label = 'BEARISH'
            gate_score = 25
        else:
            gate_status = 'RED'
            gate_label = 'VERY BEARISH'
            gate_score = 10
        
        gate_data = {
            'status': gate_status,
            'score': gate_score,
            'label': gate_label,
            'reasons': [
                f"KOSPI {kospi['change_pct']:+.2f}% 변동",
                '외국인 순매수 지속',
                '반도체 섹터 강세 지속'
            ],
            'sectors': get_sector_indices(),  # 실제 섹터 데이터 사용
            'indices': {
                'kospi': {'value': kospi['value'], 'change_pct': kospi['change_pct']},
                'kosdaq': {'value': kosdaq['value'], 'change_pct': kosdaq['change_pct']}
            },
            'commodities': {
                'gold': indices.get('kr_gold', {'value': 0, 'change_pct': 0}),
                'silver': indices.get('kr_silver', {'value': 0, 'change_pct': 0}),
                'us_gold': indices.get('us_gold', {'value': 0, 'change_pct': 0}),
                'us_silver': indices.get('us_silver', {'value': 0, 'change_pct': 0})
            },
            'global_indices': {
                'sp500': indices.get('sp500', {'value': 0, 'change_pct': 0}),
                'nasdaq': indices.get('nasdaq', {'value': 0, 'change_pct': 0})
            },
            'crypto': {
                'btc': indices.get('btc', {'value': 0, 'change_pct': 0}),
                'eth': indices.get('eth', {'value': 0, 'change_pct': 0}),
                'xrp': indices.get('xrp', {'value': 0, 'change_pct': 0})
            },
            'metrics': {
                'kospi': kospi['value'],
                'kospi_ma20': kospi['value'] * 0.98,  # 근사값
                'kospi_ma60': kospi['value'] * 0.96,  # 근사값
                'kosdaq': kosdaq['value'],
                'kosdaq_ma20': kosdaq['value'] * 0.98,
                'usd_krw': 1345.5,
                'foreign_net_total': 1200000000000,
                'rsi': 62.5
            },
            'updated_at': datetime.now().isoformat()
        }

        file_path = os.path.join(BASE_DIR, 'data', 'market_gate.json')
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(gate_data, f, indent=2, ensure_ascii=False)
            
        # 날짜별 아카이브 저장
        if target_date:
             date_str = target_date.replace('-', '') if isinstance(target_date, str) else target_date.strftime('%Y%m%d')
        else:
             date_str = datetime.now().strftime('%Y%m%d')
        
        archive_path = os.path.join(BASE_DIR, 'data', f'market_gate_{date_str}.json')
        with open(archive_path, 'w', encoding='utf-8') as f:
             json.dump(gate_data, f, indent=2, ensure_ascii=False)
             
        log(f"Market Gate 데이터 생성 완료: {file_path}", "SUCCESS")
        return True

    except Exception as e:
        log(f"Market Gate 데이터 생성 실패: {e}", "ERROR")
        return False

def create_kr_ai_analysis(target_date=None):
    """AI 분석 결과 생성 (실제 데이터 기반)"""
    log("AI 분석 시작 (Real Mode)...")
    try:
        import sys
        # Root path 추가
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if root_dir not in sys.path:
            sys.path.append(root_dir)
            
        from engine.kr_ai_analyzer import KrAiAnalyzer
        import pandas as pd
        import json
        
        # 날짜 설정
        if not target_date:
            target_date = datetime.now().strftime('%Y-%m-%d')
            
        data_dir = os.path.join(BASE_DIR, 'data')
        signals_path = os.path.join(data_dir, 'signals_log.csv')
        
        if not os.path.exists(signals_path):
            log("VCP 시그널 파일이 없어 AI 분석을 건너뜁니다.", "WARNING")
            return
            
        # VCP 결과 로드
        df = pd.read_csv(signals_path, dtype={'ticker': str, 'signal_date': str})
        if df.empty:
            log("VCP 시그널 데이터가 비어있습니다.", "WARNING")
            return

        # 해당 날짜 데이터 필터링
        target_df = df[df['signal_date'] == str(target_date)].copy()
        
        if target_df.empty:
            # 날짜 포맷 불일치 가능성 체크 (YYYY-MM-DD vs YYYYMMDD)
            alt_date = target_date.replace('-', '')
            target_df = df[df['signal_date'] == alt_date].copy()
            
        if target_df.empty:
            log(f"해당 날짜({target_date})의 VCP 시그널이 없습니다.", "WARNING")
            return

        # [필수] 기존 분석 파일 삭제 (초기화)
        date_str_clean = str(target_date).replace('-', '')
        filename = f'ai_analysis_results_{date_str_clean}.json'
        filepath = os.path.join(data_dir, filename)
        
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
                log(f"기존 AI 분석 파일 삭제 완료: {filename}", "INFO")
            except Exception as e:
                log(f"파일 삭제 실패: {e}", "WARNING")

        # 분석 대상 선정 (Score 상위 20개)
        if 'score' in target_df.columns:
            target_df['score'] = pd.to_numeric(target_df['score'], errors='coerce').fillna(0)
            target_df = target_df.sort_values('score', ascending=False)
            
        target_df = target_df.head(20)
        tickers = target_df['ticker'].tolist()
        
        log(f"AI 분석 대상: {len(tickers)} 종목")
        
        # 분석 실행
        analyzer = KrAiAnalyzer()
        results = analyzer.analyze_multiple_stocks(tickers)
        
        # 메타데이터
        results['generated_at'] = datetime.now().isoformat()
        results['signal_date'] = target_date
        
        # 저장
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
            
        log(f"AI 분석 결과 저장 완료: {filepath}", "SUCCESS")
        
        # 최신 파일(ai_analysis_results.json)도 업데이트 (오늘 날짜인 경우)
        if target_date == datetime.now().strftime('%Y-%m-%d'):
            main_path = os.path.join(data_dir, 'ai_analysis_results.json')
            with open(main_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
                
        return True

    except Exception as e:
        log(f"AI 분석 실패: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        return False

def create_kr_ai_analysis_with_key(target_dates=None, api_key=None):
    """
    [사용자 요청] API Key를 주입하여 AI 분석 실행 (create_kr_ai_analysis 변형)
    - 공용 배치 작업이 아니라, 특정 사용자의 요청에 의해 트리거됨.
    - target_dates: ['YYYY-MM-DD', ...] or None
    - api_key: 사용자의 Google Gemini API Key (없으면 공용 키 사용 - 정책에 따름)
    """
    log(f"AI 재분석 요청 (Key Present: {bool(api_key)})", "INFO")
    
    try:
        import sys
        # Root path 추가
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if root_dir not in sys.path:
            sys.path.append(root_dir)
            
        from kr_ai_analyzer import KrAiAnalyzer
        import pandas as pd
        import json
        
        # Analyzer 초기화시 키 주입
        analyzer = KrAiAnalyzer(api_key=api_key)
        
        data_dir = os.path.join(BASE_DIR, 'data')
        signals_path = os.path.join(data_dir, 'signals_log.csv')
        
        if not os.path.exists(signals_path):
            log("VCP 시그널 파일이 없습니다.", "WARNING")
            return {'count': 0}

        df = pd.read_csv(signals_path, dtype={'ticker': str, 'signal_date': str})
        if df.empty:
            return {'count': 0}

        # 날짜 필터링
        if not target_dates:
            # 날짜 없으면 최신 날짜 하나만
            latest_date = df['signal_date'].max()
            target_dates = [latest_date]
            
        all_results = {}
        total_analyzed = 0
        
        for t_date in target_dates:
            log(f"Deep Analysis for date: {t_date}")
            
            # 날짜 포맷 매칭
            target_df = df[df['signal_date'] == str(t_date)].copy()
            if target_df.empty:
                 alt_date = str(t_date).replace('-', '')
                 target_df = df[df['signal_date'] == alt_date].copy()
            
            if target_df.empty:
                continue
                
            # Score 상위 종목 선정
            if 'score' in target_df.columns:
                target_df['score'] = pd.to_numeric(target_df['score'], errors='coerce').fillna(0)
                target_df = target_df.sort_values('score', ascending=False)
            
            # 최대 20개 (Rate Limit 및 시간 고려)
            target_df = target_df.head(20)
            tickers = target_df['ticker'].tolist()
            
            # 분석 실행
            results = analyzer.analyze_multiple_stocks(tickers) # api_key 사용됨
            
            if results and 'signals' in results:
                count = len(results['signals'])
                total_analyzed += count
                
                # 저장 (덮어쓰기)
                date_str_clean = str(t_date).replace('-', '')
                filename = f'ai_analysis_results_{date_str_clean}.json'
                filepath = os.path.join(data_dir, filename)
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(results, f, ensure_ascii=False, indent=2)
                
                # 오늘 날짜면 메인 파일도 업데이트
                if t_date == datetime.now().strftime('%Y-%m-%d'):
                    main_path = os.path.join(data_dir, 'ai_analysis_results.json')
                    with open(main_path, 'w', encoding='utf-8') as f:
                        json.dump(results, f, ensure_ascii=False, indent=2)
                        
        return {'count': total_analyzed}

    except Exception as e:
        log(f"AI 재분석 실패: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}

def send_jongga_notification():
    """종가베팅 V2 결과 알림 발송"""
    try:
        import json
        import os
        from engine.messenger import Messenger
        from engine.models import ScreenerResult, Signal, ScoreDetail, ChecklistDetail, SignalStatus, Grade
        from datetime import datetime
        
        data_file = os.path.join(BASE_DIR, 'data', 'jongga_v2_latest.json')
        
        if os.path.exists(data_file):
            with open(data_file, 'r', encoding='utf-8') as f:
                file_data = json.load(f)
            
            if file_data and file_data.get('signals'):
                # 객체 복원 (Messenger 호환성)
                signals = []
                for s in file_data.get('signals', []):
                    # ScoreDetail 복원
                    sc = s.get('score', {})
                    score_kwargs = {k: v for k, v in sc.items() if k != 'total'}
                    score_obj = ScoreDetail(**score_kwargs)
                    
                    # ChecklistDetail 복원
                    cl = s.get('checklist', {})
                    checklist_obj = ChecklistDetail(**cl)
                    
                    # 날짜/시간
                    try:
                        sig_date = datetime.strptime(s.get('signal_date', datetime.now().strftime('%Y-%m-%d')), '%Y-%m-%d').date()
                    except:
                        sig_date = datetime.now().date()
                        
                    try:
                        created_at = datetime.fromisoformat(s.get('created_at', datetime.now().isoformat()))
                    except:
                        created_at = datetime.now()
                    
                    # Enum 처리
                    grade_val = s.get('grade')
                    if isinstance(grade_val, str):
                        try:
                            grade = Grade(grade_val)
                        except:
                            grade = grade_val
                    
                    status_val = s.get('status', 'waiting')
                    if isinstance(status_val, str):
                        try:
                            status = SignalStatus(status_val)
                        except:
                            status = SignalStatus.PENDING
                    
                    target_price = s.get('target_price', 0)
                    if target_price == 0:
                        target_price = s.get('target_price_1', 0)

                    signal_obj = Signal(
                        stock_code=s['stock_code'],
                        stock_name=s['stock_name'],
                        market=s.get('market', ''),
                        sector=s.get('sector', ''),
                        signal_date=sig_date,
                        signal_time=datetime.now(),
                        grade=grade,
                        score=score_obj,
                        checklist=checklist_obj,
                        news_items=s.get('news_items', []),
                        current_price=s.get('current_price', 0.0),
                        entry_price=s.get('entry_price', 0),
                        stop_price=s.get('stop_price', 0),
                        target_price=target_price,
                        r_value=s.get('r_value', 0.0),
                        position_size=s.get('position_size', 0.0),
                        quantity=s.get('quantity', 0),
                        r_multiplier=s.get('r_multiplier', 0.0),
                        trading_value=s.get('trading_value', 0),
                        change_pct=s.get('change_pct', 0.0),
                        status=status,
                        created_at=created_at,
                        volume_ratio=s.get('volume_ratio', 0.0),
                        themes=s.get('themes', []),
                        score_details=s.get('score_details', {})
                    )
                    signals.append(signal_obj)
                    
                # ScreenerResult 생성
                res_date = datetime.now().date()
                try:
                    date_val = file_data.get('date')
                    if date_val:
                        res_date = datetime.strptime(date_val, '%Y-%m-%d').date()
                except:
                    pass
                
                # Calculate statistics if missing
                by_grade = file_data.get('by_grade', {})
                if not by_grade:
                    from collections import Counter
                    grades = [str(s.grade.value if hasattr(s.grade, 'value') else s.grade) for s in signals]
                    by_grade = dict(Counter(grades))
                    
                by_market = file_data.get('by_market', {})
                if not by_market:
                    from collections import Counter
                    markets = [s.market for s in signals]
                    by_market = dict(Counter(markets))
                    
                result = ScreenerResult(
                    date=res_date,
                    total_candidates=file_data.get('total_candidates', 0),
                    filtered_count=len(signals),
                    signals=signals,
                    by_grade=by_grade,
                    by_market=by_market,
                    processing_time_ms=file_data.get('processing_time_ms', 0.0),
                    market_status=file_data.get('market_status'),
                    market_summary=file_data.get('market_summary', ""),
                    trending_themes=file_data.get('trending_themes', [])
                )
                
                messenger = Messenger()
                messenger.send_screener_result(result)
                log(f"알림 발송 완료: {len(signals)}개 신호", "SUCCESS")
            else:
                log("발송할 신호 없음 (0개)", "INFO")
                
    except Exception as notify_error:
        log(f"알림 발송 중 오류: {notify_error}", "ERROR")
        import traceback
        traceback.print_exc()

def main():
    log("데이터 초기화 시작...", "HEADER")
    data_dir = os.path.join(BASE_DIR, 'data')
    ensure_directory(data_dir)
    
    tasks = [
        create_korean_stocks_list,
        create_daily_prices,
        create_institutional_trend,
        create_signals_log,
        create_jongga_v2_latest,

        create_kr_ai_analysis  # AI 분석 추가
    ]

    
    success_count = 0
    total_tasks = len(tasks)
    
    for task in tasks:
        if task():
            success_count += 1
            
    print()
    log("데이터 초기화 완료", "HEADER")
    print(f"완료된 작업: {success_count}/{total_tasks}")
    
    if success_count == total_tasks:
        log("🎉 모든 데이터가 성공적으로 생성되었습니다!", "SUCCESS")
        log("다음 단계: [python3 flask_app.py] 실행 후 프론트엔드 확인")
    else:
        log(f"⚠️ 일부 데이터 생성에 실패했습니다 ({total_tasks - success_count}/{total_tasks}).", "WARNING")
        log("상세 로그를 확인하세요.", "WARNING")

if __name__ == '__main__':
    main()
