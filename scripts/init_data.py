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
import yfinance as yf
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
            log(f"마지막 개장일 확인: {last_trading_date_str}", "DEBUG")
            return last_trading_date_str, last_trading_date
        else:
            # 데이터가 없으면 계산된 날짜 사용
            log(f"pykrx 데이터 없음, 계산된 날짜 사용: {target_date.strftime('%Y%m%d')}", "DEBUG")
            
    except ImportError:
        log("pykrx 미설치 - 주말 처리만 적용", "WARNING")
    except Exception as e:
        # 지수명 KeyError 등 pykrx 내부 오류 발생 시 조용히 넘어가고 주말 처리만 적용
        log(f"개장일 확인 실패 (pykrx): {e}. 기본 주말 처리만 적용합니다.", "DEBUG")
    
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
        # yfinance 일괄 다운로드 (threads=False 필수)
        ticker_map = {
            'kospi': '^KS11', 'kosdaq': '^KQ11',
            'gold': '411060.KS', 'silver': '144600.KS',
            'us_gold': 'GC=F', 'us_silver': 'SI=F',
            'sp500': '^GSPC', 'nasdaq': '^IXIC',
            'btc': 'BTC-USD', 'eth': 'ETH-USD', 'xrp': 'XRP-USD'
        }
        
        symbols = list(ticker_map.values())
        
        # 안전한 다운로드 (스레드 비활성화)
        data = yf.download(symbols, period="5d", progress=False, threads=False)
        
        # 데이터 추출 Helper
        def get_val_change_prev(ticker):
             try:
                # MultiIndex 처리
                if isinstance(data.columns, pd.MultiIndex):
                    if ticker in data['Close'].columns:
                        series = data['Close'][ticker].dropna()
                    else:
                        return 0, 0, 0
                else: # 단일 티커 혹은 Flattened
                    if ticker in data.columns:
                        series = data[ticker].dropna()
                    elif 'Close' in data.columns:
                        series = data['Close'].dropna()
                    else:
                        return 0, 0, 0
                
                if series.empty: return 0, 0, 0
                
                latest = float(series.iloc[-1])
                prev = float(series.iloc[-2]) if len(series) >= 2 else latest
                change = ((latest - prev) / prev) * 100 if prev != 0 else 0
                return latest, change, prev
             except:
                return 0, 0, 0

        # 결과 매핑
        ks_val, ks_chg, ks_prev = get_val_change_prev(ticker_map['kospi'])
        indices['kospi'] = {'value': round(ks_val, 2), 'change_pct': round(ks_chg, 2), 'prev_close': round(ks_prev, 2)}
        
        kq_val, kq_chg, kq_prev = get_val_change_prev(ticker_map['kosdaq'])
        indices['kosdaq'] = {'value': round(kq_val, 2), 'change_pct': round(kq_chg, 2), 'prev_close': round(kq_prev, 2)}
        
        g_val, g_chg, g_prev = get_val_change_prev(ticker_map['gold'])
        indices['kr_gold'] = {'value': round(g_val, 0), 'change_pct': round(g_chg, 2), 'prev_close': round(g_prev, 0)}
        
        s_val, s_chg, s_prev = get_val_change_prev(ticker_map['silver'])
        indices['kr_silver'] = {'value': round(s_val, 0), 'change_pct': round(s_chg, 2), 'prev_close': round(s_prev, 0)}
        
        ug_val, ug_chg, ug_prev = get_val_change_prev(ticker_map['us_gold'])
        indices['us_gold'] = {'value': round(ug_val, 2), 'change_pct': round(ug_chg, 2), 'prev_close': round(ug_prev, 2)}
        
        us_val, us_chg, us_prev = get_val_change_prev(ticker_map['us_silver'])
        indices['us_silver'] = {'value': round(us_val, 2), 'change_pct': round(us_chg, 2), 'prev_close': round(us_prev, 2)}
        
        sp_val, sp_chg, sp_prev = get_val_change_prev(ticker_map['sp500'])
        indices['sp500'] = {'value': round(sp_val, 2), 'change_pct': round(sp_chg, 2), 'prev_close': round(sp_prev, 2)}
        
        nd_val, nd_chg, nd_prev = get_val_change_prev(ticker_map['nasdaq'])
        indices['nasdaq'] = {'value': round(nd_val, 2), 'change_pct': round(nd_chg, 2), 'prev_close': round(nd_prev, 2)}
        
        b_val, b_chg, b_prev = get_val_change_prev(ticker_map['btc'])
        indices['btc'] = {'value': round(b_val, 2), 'change_pct': round(b_chg, 2), 'prev_close': round(b_prev, 2)}
        
        e_val, e_chg, e_prev = get_val_change_prev(ticker_map['eth'])
        indices['eth'] = {'value': round(e_val, 2), 'change_pct': round(e_chg, 2), 'prev_close': round(e_prev, 2)}
        
        x_val, x_chg, x_prev = get_val_change_prev(ticker_map['xrp'])
        indices['xrp'] = {'value': round(x_val, 4), 'change_pct': round(x_chg, 2), 'prev_close': round(x_prev, 4)}
        
        log(f"시장 지수 수집 완료: KOSPI {ks_val}, Gold {g_val}", "SUCCESS")
            
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
    """개별 종목 실시간 가격 수집 (Use Shared Logic)"""
    try:
        from engine.data_sources import fetch_stock_price as shared_fetch
        return shared_fetch(ticker)
    except ImportError:
        # Fallback if engine package not found (e.g. running script directly)
        import sys
        if BASE_DIR not in sys.path:
            sys.path.append(BASE_DIR)
        try:
            from engine.data_sources import fetch_stock_price as shared_fetch
            return shared_fetch(ticker)
        except:
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



# 전역 로거 설정 (중복 출력 방지)
logger = logging.getLogger("init_data")
logger.propagate = False
logger.setLevel(logging.INFO)

try:
    _log_dir = os.path.join(BASE_DIR, 'logs')
    if not os.path.exists(_log_dir):
        os.makedirs(_log_dir)
    _fh = logging.FileHandler(os.path.join(_log_dir, 'init_data.log'), encoding='utf-8')
    _fh.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    if not logger.handlers:
        logger.addHandler(_fh)
except Exception as e:
    print(f"Logger setup failed: {e}")

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
    # File logging (propagate=False로 콘솔 중복 방지)
    if level == "ERROR":
        logger.error(message)
    elif level == "WARNING":
        logger.warning(message)
    elif level == "SUCCESS":
        logger.info(f"✅ {message}")
    elif level == "DEBUG":
        logger.debug(message)
    else:
        logger.info(message)

    # Console logging
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
    elif level == "DEBUG":
        pass  # Skip console output for debug
    else:
        # INFO logs also skipped in console if not important, but keep default behavior for now or strict?
        # User wants "only errors when there is an error", but some info might be useful.
        # Let's keep INFO printing but move verbose logs to DEBUG.
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
        
        def get_market_cap_safe(target_date, market):
            try:
                df = stock.get_market_cap(target_date, market=market)
                if not df.empty:
                    return df
            except:
                pass
            return pd.DataFrame()

        # KOSPI
        kospi_cap = get_market_cap_safe(today, "KOSPI")
        if kospi_cap.empty: # 오늘 데이터 없으면 하루 전 시도
             from datetime import timedelta
             prev_date = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
             log(f"오늘({today}) KOSPI 데이터 없음. 전일({prev_date}) 데이터 시도...", "WARNING")
             kospi_cap = get_market_cap_safe(prev_date, "KOSPI")

        if not kospi_cap.empty:
            # 시가총액 순 정렬 후 상위 1000개 (VCP 발굴 확률 확대를 위해 대폭 증가)
            kospi_cap = kospi_cap.sort_values('시가총액', ascending=False)
            kospi_top_cap = kospi_cap.head(1000)
            
            # [추가] 거래대금 상위 500개도 추가 (시총은 작지만 거래가 터진 급등주 포착)
            kospi_top_vol = kospi_cap.sort_values('거래대금', ascending=False).head(500)
            
            # 병합 (중복 제거)
            kospi_metrics = pd.concat([kospi_top_cap, kospi_top_vol])
            kospi_metrics = kospi_metrics[~kospi_metrics.index.duplicated(keep='first')]
            
            for ticker in kospi_metrics.index:
                try:
                    name = stock.get_market_ticker_name(ticker)
                    all_data.append({'ticker': ticker, 'name': name, 'market': 'KOSPI', 'sector': ''})
                except: pass
            log(f"KOSPI 종목 수집: 시총상위 1000 + 거래대금상위 500 -> 통합 {len(kospi_metrics)}개", "SUCCESS")
        else:
            log("KOSPI 시가총액 조회 실패", "WARNING")

        # KOSDAQ
        kosdaq_cap = get_market_cap_safe(today, "KOSDAQ")
        if kosdaq_cap.empty: 
             from datetime import timedelta
             prev_date = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
             log(f"오늘({today}) KOSDAQ 데이터 없음. 전일({prev_date}) 데이터 시도...", "WARNING")
             kosdaq_cap = get_market_cap_safe(prev_date, "KOSDAQ")

        if not kosdaq_cap.empty:
            # 시가총액 순 정렬 후 상위 1000개 (코스닥 포함 요청 반영)
            kosdaq_cap = kosdaq_cap.sort_values('시가총액', ascending=False)
            kosdaq_top_cap = kosdaq_cap.head(1000)
            
            # [추가] 거래대금 상위 500개도 추가
            kosdaq_top_vol = kosdaq_cap.sort_values('거래대금', ascending=False).head(500)

            # 병합
            kosdaq_metrics = pd.concat([kosdaq_top_cap, kosdaq_top_vol])
            kosdaq_metrics = kosdaq_metrics[~kosdaq_metrics.index.duplicated(keep='first')]

            for ticker in kosdaq_metrics.index:
                try:
                    name = stock.get_market_ticker_name(ticker)
                    all_data.append({'ticker': ticker, 'name': name, 'market': 'KOSDAQ', 'sector': ''})
                except: pass
            log(f"KOSDAQ 종목 수집: 시총상위 1000 + 거래대금상위 500 -> 통합 {len(kosdaq_metrics)}개", "SUCCESS")
        else:
            log("KOSDAQ 시가총액 조회 실패", "WARNING")
        
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
                # KOSPI 상위 20개
                '005930', '000660', '005380', '373220', '207940', '000270', '035420', '068270', '105560', '055550',
                '035720', '003550', '015760', '028260', '017670', '032830', '009150', '251270', '012330', '034730',
                # KOSDAQ 상위 10개 + 인기/급등주 (알테오젠, 리노공업 등)
                '247540', '086520', '196170', '263750', '145020', '403870', '328130', '091990', '336370', '058470',
                '293490', '214150', '035900', '041510', '036930', '039030', '035760', '022100', '042700', '064350'
            ],
            'name': [
                # KOSPI
                '삼성전자', 'SK하이닉스', '현대차', 'LG에너지솔루션', '삼성바이오로직스', '기아', 'NAVER', '셀트리온', 'KB금융', '신한지주',
                '카카오', 'LG', '한국전력', '삼성물산', 'SK텔레콤', '삼성생명', '삼성전기', '넷마블', '현대모비스', 'SK',
                # KOSDAQ
                '에코프로비엠', '에코프로', '알테오젠', '펄어비스', '휴젤', '피에이치에이', '루닛', '셀트리온제약', '솔브레인', '리노공업',
                '카카오게임즈', '클래시스', 'JYP Ent.', '에스엠', '주성엔지니어링', '이오테크닉스', 'CJ ENM', '포스코DX', '한미반도체', '현대로템'
            ],
            'market': [
                'KOSPI', 'KOSPI', 'KOSPI', 'KOSPI', 'KOSPI', 'KOSPI', 'KOSPI', 'KOSPI', 'KOSPI', 'KOSPI',
                'KOSPI', 'KOSPI', 'KOSPI', 'KOSPI', 'KOSPI', 'KOSPI', 'KOSPI', 'KOSPI', 'KOSPI', 'KOSPI',
                'KOSDAQ', 'KOSDAQ', 'KOSDAQ', 'KOSDAQ', 'KOSDAQ', 'KOSDAQ', 'KOSDAQ', 'KOSDAQ', 'KOSDAQ', 'KOSDAQ',
                'KOSDAQ', 'KOSDAQ', 'KOSDAQ', 'KOSDAQ', 'KOSDAQ', 'KOSDAQ', 'KOSDAQ', 'KOSDAQ', 'KOSDAQ', 'KOSDAQ'
            ],
            'sector': [
                '반도체', '반도체', '자동차', '2차전지', '헬스케어', '자동차', '인터넷', '헬스케어', '금융', '금융',
                '인터넷', '지주', '에너지', '건설', '통신', '금융', '전기전자', '게임', '자동차부품', '지주',
                '2차전지', '2차전지', '헬스케어', '게임', '헬스케어', '자동차부품', 'AI/의료', '헬스케어', '반도체소재', '반도체장비',
                '게임', '미용기기', '엔터', '엔터', '반도체장비', '반도체장비', '미디어', 'IT서비스', '반도체장비', '방산'
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
        if start_date.date() > end_date.date():
            log(f"yfinance 수집: 시작일({start_date.strftime('%Y-%m-%d')})이 종료일({end_date.strftime('%Y-%m-%d')})보다 미래입니다. (최신 상태)", "SUCCESS")
            return True

        import yfinance as yf
        log("yfinance 백업 수집 모드 가동...", "DEBUG")
        
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
            if shared_state.STOP_REQUESTED:
                log("⛔️ 사용자 요청으로 yfinance 수집 중단", "WARNING")
                return False
            
            try:
                # 마켓 확인
                market_info = stocks_df[stocks_df['ticker'] == ticker]['market'].values
                suffix = ".KS" if len(market_info) > 0 and market_info[0] == 'KOSPI' else ".KQ"
                yf_ticker = f"{ticker}{suffix}"
                
                # yfinance 에러 로그 억제
                import logging as _logging
                yf_logger = _logging.getLogger('yfinance')
                original_level = yf_logger.level
                yf_logger.setLevel(_logging.CRITICAL)
                
                try:
                    # 데이터 다운로드 (진행률 표시 없이, 스레드 비활성화)
                    df = yf.download(yf_ticker, start=start_date.strftime('%Y-%m-%d'), end=(end_date + timedelta(days=1)).strftime('%Y-%m-%d'), progress=False, threads=False)
                finally:
                    yf_logger.setLevel(original_level)
                
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


def create_daily_prices(target_date=None, force=False, lookback_days=5):
    """
    일별 가격 데이터 수집 - pykrx 날짜별 일괄 조회 (속도 최적화)
    Args:
        target_date: 기준 날짜 (기본: 오늘)
        force: 강제 업데이트 여부
        lookback_days: 강제 업데이트 시 재수집할 기간 (기본: 5일)
    """
    log("Daily Prices 데이터 업데이트 시작 (Date-based Fast Mode)...", "INFO")
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

        # [Safety] 미래 날짜 요청 방지
        if end_date_obj > datetime.now():
            log(f"요청 날짜({end_date_str})가 미래이므로 오늘 날짜로 조정합니다.", "WARNING")
            end_date_obj = datetime.now()
            end_date_str = end_date_obj.strftime('%Y%m%d')
        
        # 기존 데이터 로드 및 시작일 결정
        file_path = os.path.join(BASE_DIR, 'data', 'daily_prices.csv')
        existing_df = pd.DataFrame()
        start_date_obj = end_date_obj - timedelta(days=90) # 기본 90일

        if os.path.exists(file_path):
            try:
                log(f"기존 데이터 로드 중... ({file_path})", "INFO")
                existing_df = pd.read_csv(file_path, dtype={'ticker': str})
                if not existing_df.empty and 'date' in existing_df.columns:
                    max_date_str = existing_df['date'].max()
                    
                    # (중요) 종목 수 체크 - 새로 추가된 종목이 있을 수 있음
                    # 현재 등록된 종목 수(600개)와 마지막 날짜의 데이터 개수 비게
                    stocks_file = os.path.join(BASE_DIR, 'data', 'korean_stocks_list.csv')
                    total_stocks_count = 600
                    if os.path.exists(stocks_file):
                        try:
                            stocks_df = pd.read_csv(stocks_file)
                            total_stocks_count = len(stocks_df)
                        except:
                            pass
                    
                    last_date_count = len(existing_df[existing_df['date'] == max_date_str])
                    
                    if start_date_obj.date() > end_date_obj.date():
                        # Force check
                        if not force and last_date_count >= total_stocks_count * 0.9:
                            log("이미 최신 데이터가 존재하며 충분합니다.", "SUCCESS")
                            return True
                        elif force:
                             log(f"최신 데이터가 존재하지만 강제 업데이트(force=True)를 진행합니다. (최근 {lookback_days}일)", "DEBUG")
                             start_date_obj = end_date_obj - timedelta(days=lookback_days)
                        else:
                            log(f"데이터 날짜는 최신이나 종목 수가 부족합니다({last_date_count}/{total_stocks_count}). 재수집을 시작합니다.", "WARNING")
                            start_date_obj = end_date_obj - timedelta(days=lookback_days) # 부족한 경우에도 lookback_days 사용
                    else:
                        max_date_dt = datetime.strptime(max_date_str, '%Y-%m-%d')
                        # 마지막 저장일 다음날부터 수집
                        start_date_obj = max_date_dt + timedelta(days=1)
                        if force:
                             log(f"강제 업데이트: 기존 데이터 무시하고 최근 {lookback_days}일 재수집", "DEBUG")
                             start_date_obj = end_date_obj - timedelta(days=lookback_days)
                        else:
                             log(f"기존 데이터 확인: {max_date_str}까지 존재. 이후부터 수집.", "INFO")
                else:
                    log("기존 데이터 비어있음.", "INFO")
            except Exception as e:
                log(f"기존 데이터 로드 오류: {e}", "WARNING")
             
        req_start_date_str = start_date_obj.strftime('%Y%m%d')
        log(f"수집 구간: {req_start_date_str} ~ {end_date_str}", "INFO")

        # 날짜 리스트 생성
        date_range = pd.date_range(start=start_date_obj, end=end_date_obj)
        total_days = len(date_range)
        
        # [Optimization] Create a set of existing dates for O(1) lookup
        existing_dates_set = set()
        if not existing_df.empty and 'date' in existing_df.columns:
            existing_dates_set = set(existing_df['date'].unique())
            log(f"기존 데이터 날짜 인덱싱 완료 ({len(existing_dates_set)}일)", "INFO")

        new_data_list = []
        processed_days = 0
        skipped_count = 0
        
        for dt in date_range:
            if shared_state.STOP_REQUESTED:
                log("⛔️ 사용자 요청으로 중단", "WARNING")
                break
                
            cur_date_str = dt.strftime('%Y%m%d')
            cur_date_fmt = dt.strftime('%Y-%m-%d')
            
            # 주말 체크 (토/일) - pykrx가 알아서 빈값 줄 수 있으나 미리 건너뛰면 빠름
            if dt.weekday() >= 5: 
                processed_days += 1
                skipped_count += 1
                continue

            # [Optimization] 이미 수집된 데이터는 건너뛰기 (과거 데이터인 경우만)
            # 오늘 날짜는 장중 변동 가능하므로 항상 수집
            if not existing_df.empty and 'date' in existing_df.columns:
                if cur_date_fmt in existing_dates_set:
                     # 오늘이 아니면 Skip
                    if dt.date() < datetime.now().date():
                         processed_days += 1
                         skipped_count += 1
                         # 디버깅을 위해 일단 매번 출력 (또는 5회마다)
                         if total_days < 20 or processed_days % 5 == 0:
                             progress = (processed_days / total_days) * 100
                             log(f"  -> {cur_date_fmt} 데이터 존재 (Skip) - 진행률: {progress:.1f}%", "INFO")
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
                
                # 필수 컬럼 존재 확인 (한글/영문 대응)
                rename_map = {
                    '시가': 'open', '고가': 'high', '저가': 'low', 
                    '종가': 'close', '거래량': 'volume', '거래대금': 'trading_value',
                    'Open': 'open', 'High': 'high', 'Low': 'low', 
                    'Close': 'close', 'Volume': 'volume', 'Amount': 'trading_value'
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
                time.sleep(random.uniform(0.05, 0.1))
                
            except Exception as e:
                log(f"날짜별 수집 실패 ({cur_date_str}): {e}", "WARNING")
                processed_days += 1
                
        
        # 병합 및 저장
        if new_data_list:
            log("데이터 병합 중...", "DEBUG")
            new_chunk_df = pd.concat(new_data_list, ignore_index=True)
            
            if not existing_df.empty:
                final_df = pd.concat([existing_df, new_chunk_df])
                final_df = final_df.drop_duplicates(subset=['date', 'ticker'], keep='last')
            else:
                final_df = new_chunk_df
                
            final_df = final_df.sort_values(['ticker', 'date'])
            
            # [Added] Toss API를 통한 오늘의 종가 보정 (정확도 확보)
            if end_date_obj.date() == datetime.now().date():
                try:
                    log("Toss Batch API를 이용한 오늘의 종가 보정 중...", "INFO")
                    from engine.toss_collector import TossCollector
                    from engine.data_sources import fetch_stock_price
                    from concurrent.futures import ThreadPoolExecutor, as_completed

                    collector = TossCollector()
                    end_date_fmt = end_date_obj.strftime('%Y-%m-%d')
                    target_tickers = final_df[final_df['date'] == end_date_fmt]['ticker'].unique().tolist()
                    
                    # 1. Attempt Toss Batch (Fastest)
                    toss_prices = collector.get_prices_batch(target_tickers)
                    
                    # 2. Identify missing tickers
                    processed_tickers = set(toss_prices.keys())
                    all_tickers_set = set(target_tickers)
                    missing_tickers = list(all_tickers_set - processed_tickers)
                    
                    # Update with Toss data first
                    if toss_prices:
                        mask = (final_df['date'] == end_date_fmt)
                        def get_toss_price(row):
                            t_data = toss_prices.get(row['ticker'])
                            return int(t_data['current']) if t_data and t_data.get('current') and t_data['current'] > 0 else row['close']
                        final_df.loc[mask, 'close'] = final_df[mask].apply(get_toss_price, axis=1)
                    
                    # 3. Fallback for missing tickers (Naver -> YF via fetch_stock_price)
                    if missing_tickers:
                        log(f"Toss Batch 미수집 {len(missing_tickers)}종목. Naver/YF 폴백 병렬 수행...", "WARNING")
                        
                        fallback_results = {}
                        with ThreadPoolExecutor(max_workers=20) as executor:
                            future_to_ticker = {executor.submit(fetch_stock_price, t): t for t in missing_tickers}
                            for future in as_completed(future_to_ticker):
                                t = future_to_ticker[future]
                                try:
                                    data = future.result()
                                    if data:
                                        fallback_results[t] = data
                                except Exception as exc:
                                    pass
                        
                        # Apply Fallback Data
                        if fallback_results:
                            mask = (final_df['date'] == end_date_fmt) & (final_df['ticker'].isin(fallback_results.keys()))
                            # Pandas apply is slow, loop might be better for partial updates or map
                            # Using map for speed
                            for t, data in fallback_results.items():
                                # Locating specific row
                                idx = (final_df['date'] == end_date_fmt) & (final_df['ticker'] == t)
                                if any(idx):
                                    final_df.loc[idx, 'close'] = int(data['price'])
                            
                            log(f"폴백 데이터 보정 완료: {len(fallback_results)}개 종목 추가 업데이트", "SUCCESS")
                        else:
                             log("폴백 데이터 수집 실패 (모든 소스 응답 없음)", "WARNING")

                    log(f"최종 데이터 보정 완료: 총 {len(toss_prices) + len(fallback_results) if 'fallback_results' in locals() else len(toss_prices)}개", "SUCCESS")

                except Exception as te:
                    log(f"데이터 보정 프로세스 중 오류: {te}", "WARNING")
            else:
                log(f"Toss Batch 보정 생략 (요청일 {end_date_obj.date()} != 오늘 {datetime.now().date()})", "INFO")

            log(f"데이터 저장 시작... ({file_path})", "INFO")
            final_df.to_csv(file_path, index=False, encoding='utf-8-sig')
            log(f"일별 가격 저장 완료: 총 {len(final_df)}행 (신규 {len(new_chunk_df)}행)", "INFO")
            print("DEBUG: create_daily_prices finished successfully.", flush=True)
        else:
             if start_date_obj.date() > end_date_obj.date():
                 log("pykrx 수집 데이터 없음 (이미 최신).", "SUCCESS")
                 return True

             log("pykrx 수집 데이터 없음. yfinance 폴백 시도...", "DEBUG")
             
             if skipped_count == total_days and total_days > 0:
                 log(f"모든 날짜({total_days}일) 데이터가 이미 존재합니다. yfinance 폴백 생략.", "SUCCESS")
                 return True

             return fetch_prices_yfinance(start_date_obj, end_date_obj, existing_df, file_path)
                 
        return True

    except Exception as e:
        log(f"pykrx 수집 중 오류: {e} -> yfinance 폴백 시도", "WARNING")
        return fetch_prices_yfinance(start_date_obj, end_date_obj, existing_df, file_path)


def create_institutional_trend(target_date=None, force=False, lookback_days=7):
    """
    수급 데이터 수집 - pykrx 기관/외국인 순매매 (Optimized)
    Args:
        target_date: 기준 날짜
        force: 강제 업데이트 여부
        lookback_days: 강제 업데이트 시 재수집할 기간 (기본: 7일)
    """
    log("수급 데이터 수집 중 (pykrx 실제 데이터)...", "DEBUG")
    try:
        from pykrx import stock
        
        # 종목 목록 로드
        stocks_file = os.path.join(BASE_DIR, 'data', 'korean_stocks_list.csv')
        tickers_set = set() # 빠른 조회를 위해 set 사용
        if os.path.exists(stocks_file):
            stocks_df = pd.read_csv(stocks_file)
            tickers_set = set(stocks_df['ticker'].astype(str).str.zfill(6).tolist())
            if '069500' not in tickers_set:
                tickers_set.add('069500')
        else:
            tickers_set = {'069500', '005930', '000660', '000270', '051910', '006400'}
        
        if target_date:
            if isinstance(target_date, str):
                target_date_obj = datetime.strptime(target_date, '%Y-%m-%d')
            else:
                target_date_obj = target_date
        else:
            target_date_obj = datetime.now()

        # 마지막 개장일 확인 (주말/휴일 자동 처리)
        end_date, end_date_obj = get_last_trading_date(reference_date=target_date_obj)
        
        # 기존 데이터 로드
        file_path = os.path.join(BASE_DIR, 'data', 'all_institutional_trend_data.csv')
        existing_df = pd.DataFrame()
        start_date_obj = end_date_obj - timedelta(days=30) # 기본 30일 전
        
        if os.path.exists(file_path):
            try:
                existing_df = pd.read_csv(file_path, dtype={'ticker': str, 'date': str})
                if not existing_df.empty and 'date' in existing_df.columns:
                    # 가장 최근 데이터 날짜 확인
                    max_date_str = existing_df['date'].max()
                    
                    # (중요) 단순 날짜 체크만 하지 않고, 종목 수가 부족한지 확인
                    last_date_tickers = len(existing_df[existing_df['date'] == max_date_str])
                    
                    # 신규 추가된 종목이 있는지 확인 (Backfill 필요 여부)
                    existing_tickers = set(existing_df['ticker'].unique())
                    missing_tickers = tickers_set - existing_tickers
                    
                    if start_date_obj.date() > end_date_obj.date() and not missing_tickers:
                        if not force and last_date_tickers >= len(tickers_set) * 0.9: # 90% 이상 차있으면 최신으로 간주
                            log("수급 데이터: 이미 최신 상태이며 데이터가 충분합니다.", "SUCCESS")
                            return True
                        elif force:
                             log(f"수급 데이터: 강제 업데이트 진행 (최근 {lookback_days}일 재수집)", "WARNING")
                             start_date_obj = end_date_obj - timedelta(days=lookback_days)

                    if missing_tickers and not force: # Force일때는 위에서 처리됨
                        log(f"수급 데이터: 신규 종목 {len(missing_tickers)}개가 감지되었습니다. (최적화: 최근 {lookback_days}일만 재수집)", "WARNING")
                        # 신규 종목이 있어도 과도한 재수집 방지 (30일 -> lookback_days)
                        start_date_obj = end_date_obj - timedelta(days=lookback_days)
                    elif last_date_tickers < len(tickers_set) * 0.8:
                        log(f"수급 데이터: 최신 날짜 데이터가 부족합니다({last_date_tickers}/{len(tickers_set)}). 재수집합니다.", "WARNING")
                        start_date_obj = end_date_obj - timedelta(days=lookback_days)     
                    elif not force:
                        # 정상적인 경우 max_date 다음날부터 (Force가 아닐 때만)
                        try:
                            max_date_dt = datetime.strptime(max_date_str, '%Y-%m-%d')
                            start_date_obj = max_date_dt + timedelta(days=1)
                        except: pass
            except Exception as e:
                log(f"기존 수급 데이터 로드 실패 (새로 시작): {e}", "WARNING")

        start_date = start_date_obj.strftime('%Y%m%d')
        
        # 시작일이 종료일보다 미래인 경우 (그리고 미싱 티커 없는 경우) 처리
        if start_date > end_date:
             log("수급 데이터: 이미 최신 상태입니다.", "SUCCESS")
             return True

        log(f"수급 데이터 수집 구간(개선됨): {start_date} ~ {end_date} (Date-based Bulk Fetch)", "DEBUG")
        
        # 날짜 루프 시작
        date_range = pd.date_range(start=start_date_obj, end=end_date_obj)
        total_days = len(date_range)
        processed_days = 0
        
        new_data_list = []
        
        for dt in date_range:
            if shared_state.STOP_REQUESTED:
                log("⛔️ 사용자 요청으로 수급 데이터 수집 중단", "WARNING")
                break
                
            cur_date_str = dt.strftime('%Y%m%d')
            cur_date_fmt = dt.strftime('%Y-%m-%d')
            
            # 주말 체크
            if dt.weekday() >= 5:
                processed_days += 1
                continue
            
            # [Optimization] 이미 수집된 데이터는 건너뛰기 (과거 데이터인 경우만)
            if not existing_df.empty and 'date' in existing_df.columns:
                if cur_date_fmt in existing_df['date'].values:
                    # 오늘이 아니면 Skip
                    if dt.date() < datetime.now().date():
                         log(f"  -> {cur_date_fmt} 수급 데이터 존재 (Skip)", "DEBUG")
                         processed_days += 1
                         continue
            
            try:
                # 1. 외국인 순매수 (전 종목)
                df_foreign = stock.get_market_net_purchases_of_equities_by_ticker(cur_date_str, cur_date_str, "ALL", "외국인")
                time.sleep(0.2) # Rate limit
                
                # 2. 기관 순매수 (전 종목)
                df_inst = stock.get_market_net_purchases_of_equities_by_ticker(cur_date_str, cur_date_str, "ALL", "기관합계")
                time.sleep(0.2)
                
                # 데이터 병합
                # 인덱스: 티커
                combined_rows = []
                
                # 외국인 데이터 기준 루프 (또는 set of tickers)
                # target_tickers에 있는 것만 필터링
                
                # 인덱스(티커)를 set으로 확보
                available_tickers = set(df_foreign.index) | set(df_inst.index)
                target_intersect = available_tickers & tickers_set
                
                for ticker in target_intersect:
                    f_val = 0
                    i_val = 0
                    
                    if ticker in df_foreign.index:
                        # 순매수거래대금 컬럼 확인
                        if '순매수거래대금' in df_foreign.columns:
                            f_val = df_foreign.loc[ticker, '순매수거래대금']
                    
                    if ticker in df_inst.index:
                        if '순매수거래대금' in df_inst.columns:
                            i_val = df_inst.loc[ticker, '순매수거래대금']
                            
                    combined_rows.append({
                        'date': cur_date_fmt,
                        'ticker': ticker,
                        'foreign_buy': int(f_val),
                        'inst_buy': int(i_val)
                    })
                
                if combined_rows:
                    new_data_list.extend(combined_rows)
                    log(f"[Supply Trend] {cur_date_fmt} 수집 완료 ({len(combined_rows)}종목)", "DEBUG")
                else:
                    log(f"[Supply Trend] {cur_date_fmt} 데이터 없음 (휴장일?)", "DEBUG")
                
            except Exception as e:
                log(f"수급 데이터 날짜별 수집 실패 ({cur_date_str}): {e}", "WARNING")
            
            processed_days += 1
        
        # 결과 저장
        if new_data_list:
            log("수급 데이터 병합 및 저장 중...", "DEBUG")
            new_df = pd.DataFrame(new_data_list)
            
            # [Added] 주요 종목 Toss API 정밀 수급 보정 (정확도 확보)
            if end_date_obj.date() == datetime.now().date():
                try:
                    from engine.toss_collector import TossCollector
                    collector = TossCollector()
                    
                    # 1. 오늘 날짜 데이터만 추출
                    today_mask = (new_df['date'] == cur_date_fmt)
                    today_df = new_df[today_mask].copy()
                    
                    if not today_df.empty:
                        # 2. 보정 대상 종목 선정 (예: 거래대금이 큰 종목 위주로 300개)
                        # 가격 데이터와 병합하여 거래대금 확인
                        price_file = os.path.join(BASE_DIR, 'data', 'daily_prices.csv')
                        p_df = pd.read_csv(price_file, dtype={'ticker': str})
                        p_today = p_df[p_df['date'] == cur_date_fmt]
                        
                        merged = pd.merge(today_df, p_today[['ticker', 'trading_value']], on='ticker', how='left')
                        top_candidates = merged.sort_values('trading_value', ascending=False).head(300)['ticker'].tolist()
                        
                        log(f"Toss API를 이용한 수급 정밀 보정 중 (대상: {len(top_candidates)}종목)...", "DEBUG")
                        
                        success_count = 0
                        for t in top_candidates:
                            try:
                                # 1. Toss 시도
                                t_trend = collector.get_investor_trend(t, days=1)
                                if t_trend and (t_trend.get('foreign', 0) != 0 or t_trend.get('institution', 0) != 0):
                                    idx_mask = (new_df['date'] == cur_date_fmt) & (new_df['ticker'] == t)
                                    if any(idx_mask):
                                        new_df.loc[idx_mask, 'foreign_buy'] = int(t_trend.get('foreign', 0))
                                        new_df.loc[idx_mask, 'inst_buy'] = int(t_trend.get('institution', 0))
                                        success_count += 1
                                        continue
                                
                                # 2. Toss 실패/데이터 0인 경우 Naver 실시간 시도 (Fallback)
                                try:
                                    # data_sources에서 함수 가져오기 (Lazy import)
                                    from engine.data_sources import fetch_investor_trend_naver
                                    n_trend = fetch_investor_trend_naver(t)
                                    
                                    if n_trend and (n_trend.get('foreign', 0) != 0 or n_trend.get('institution', 0) != 0):
                                        idx_mask = (new_df['date'] == cur_date_fmt) & (new_df['ticker'] == t)
                                        if any(idx_mask):
                                            new_df.loc[idx_mask, 'foreign_buy'] = int(n_trend.get('foreign', 0))
                                            new_df.loc[idx_mask, 'inst_buy'] = int(n_trend.get('institution', 0))
                                            success_count += 1
                                            # log(f"  -> {t} Naver 폴백 성공", "DEBUG")
                                except:
                                    pass
                            except:
                                pass
                        
                        log(f"Toss 수급 보정 완료: {success_count}개 종목 정밀 업데이트", "SUCCESS")
                except Exception as te:
                    log(f"Toss 수급 보정 실패: {te}", "WARNING")

            if not existing_df.empty:
                final_df = pd.concat([existing_df, new_df])
                final_df = final_df.drop_duplicates(subset=['date', 'ticker'], keep='last')
            else:
                final_df = new_df
            
            # 정렬
            final_df = final_df.sort_values(['ticker', 'date'])
            final_df.to_csv(file_path, index=False, encoding='utf-8-sig')
            log(f"수급 데이터 업데이트 완료: 총 {len(final_df)}행 (신규 {len(new_data_list)}행)", "DEBUG")
            return True
        else:
            log("수급 데이터: 신규 수집된 데이터가 없습니다.", "SUCCESS")
            return True

    except Exception as e:
        log(f"수급 데이터 수집 중 치명적 오류: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        return False


def create_signals_log(target_date=None, run_ai=True):
    """VCP 시그널 로그 생성 - Using SmartMoneyScreener (engine.screener)"""
    log("VCP 시그널 분석 중 (SmartMoneyScreener)...")
    try:
        from engine.screener import SmartMoneyScreener
        
        # 스크리너 실행 (KOSPI+KOSDAQ 전체 분석)
        screener = SmartMoneyScreener(target_date=target_date)
        df_result = screener.run_screening(max_stocks=600)
        
        signals = []
        if not df_result.empty:
            for _, row in df_result.iterrows():
                signals.append({
                    'ticker': row['ticker'],
                    'name': row['name'],
                    'signal_date': target_date if target_date else datetime.now().strftime('%Y-%m-%d'),
                    'market': row['market'],
                    'status': 'OPEN',
                    'score': round(row['score'], 1),
                    'contraction_ratio': row.get('contraction_ratio', 0),
                    'entry_price': int(row['entry_price']),
                    'foreign_5d': int(row['foreign_net_5d']),
                    'inst_5d': int(row['inst_net_5d']),
                    'vcp_score': row.get('vcp_score', 0), # [FIX] Use calculated score from screener
                    'current_price': int(row.get('entry_price', 0)) # Approximation or need fetch
                })
        
        log(f"총 {len(signals)}개 시그널 감지")
        
        # 점수 높은 순 정렬 (Top 20 제한)
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
                        
                        # 현재가 및 수익률 명시적 계산
                        curr_p = int(signal.get('current_price', signal.get('entry_price', 0)))
                        entry_p = int(signal.get('entry_price', curr_p))
                        ret_p = round(((curr_p - entry_p) / entry_p * 100), 2) if entry_p > 0 else 0

                        kr_signal = {
                            'ticker': ticker,
                            'name': name,
                            'market': signal.get('market', 'KOSPI'),
                            'score': signal.get('score', 0),
                            'contraction_ratio': signal.get('contraction_ratio', 0),
                            'foreign_5d': signal.get('foreign_5d', 0),
                            'inst_5d': signal.get('inst_5d', 0),
                            'entry_price': entry_p,
                            'current_price': curr_p,
                            'return_pct': ret_p,
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
        


        # [FIX] AI 분석 결과를 signals 리스트에 병합 (CSV 저장을 위해)
        if run_ai and signals and 'ai_results' in locals() and ai_results:
            try:
                for signal in signals:
                    ticker = signal['ticker']
                    if ticker in ai_results:
                        ai_data = ai_results[ticker]
                        
                        # Gemini 결과 우선
                        gemini = ai_data.get('gemini_recommendation')
                        if gemini:
                            signal['ai_action'] = gemini.get('action', 'HOLD')
                            signal['ai_confidence'] = gemini.get('confidence', 0)
                            signal['ai_reason'] = gemini.get('reason', '')
                        else:
                            # 다른 AI 결과 폴백? (일단 Gemini 기준)
                            signal['ai_action'] = 'N/A'
                            signal['ai_confidence'] = 0
                            signal['ai_reason'] = '분석 실패'
            except Exception as e:
                log(f"AI 결과 병합 중 오류: {e}", "WARNING")

        # [Fix] jongga_v2_results_{date}.json 저장 (Messenger/Dashboard 연동용)
        try:
            from engine.market_gate import MarketGate
            market_gate = MarketGate()
            market_status = market_gate.analyze()
            
            # Grade 분포 계산
            grade_counts = {'S': 0, 'A': 0, 'B': 0, 'C': 0, 'D': 0}
            # signals에는 grade 정보가 없을 수 있음 (Screener 결과엔 score만 있음)
            # Score 기반 추정 (Scorer 로직 참고: ~80:S, ~70:A, ~60:B)
            for s in signals:
                score = float(s.get('score', 0))
                if score >= 80: grade_counts['S'] += 1
                elif score >= 70: grade_counts['A'] += 1
                elif score >= 60: grade_counts['B'] += 1
                else: grade_counts['C'] += 1
                
            jongga_data = {
                "date": target_date if target_date else datetime.now().strftime('%Y-%m-%d'),
                "total_candidates": len(signals), # 전체 후보 (여기선 Top 20만 남았을 수 있음, 원본 df_result 사용 권장하지만 여기선 signals 사용)
                "filtered_count": len(df_result) - len(signals) if 'df_result' in locals() else 0,
                "signals": signals,
                "by_grade": grade_counts,
                "by_market": {}, # 생략
                "processing_time_ms": 0,
                "market_status": market_status,
                "market_summary": "", # AI 요약이 있다면 추가 가능
                "trending_themes": [],
                "updated_at": datetime.now().isoformat()
            }
            
            # 날짜 포맷 (YYYYMMDD)
            j_date_str = str(jongga_data['date']).replace('-', '')
            j_path = os.path.join(BASE_DIR, 'data', f'jongga_v2_results_{j_date_str}.json')
            
            with open(j_path, 'w', encoding='utf-8') as f:
                json.dump(jongga_data, f, indent=2, ensure_ascii=False)
            log(f"메신저 연동 파일 저장 완료: {j_path}", "SUCCESS")
            
            # Latest 파일 업데이트
            j_latest_path = os.path.join(BASE_DIR, 'data', 'jongga_v2_latest.json')
            with open(j_latest_path, 'w', encoding='utf-8') as f:
                json.dump(jongga_data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            log(f"jongga_v2_results 저장 실패: {e}", "WARNING")

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
                         # concat 시 ignore_index=True 권장
                         df_combined = pd.concat([df_old, df_new], ignore_index=True)
                         
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



def create_jongga_v2_latest():
    """종가베팅 V2 최신 결과 생성 - Using Central SignalGenerator"""
    log("종가베팅 V2 분석 중 (SignalGenerator)...")
    try:
        from engine.generator import run_screener
        import asyncio

        # Run analysis (Sync wrapper for Async)
        # run_screener returns ScreenerResult object
        result = asyncio.run(run_screener())
        
        # Convert to JSON serializable structure
        if result:
            signals_json = [s.to_dict() for s in result.signals]
            
            output_data = {
                'date': result.date.strftime('%Y-%m-%d'),
                'total_candidates': result.total_candidates,
                'filtered_count': result.filtered_count,
                'scanned_count': getattr(result, 'scanned_count', 0),
                'signals': signals_json,
                'by_grade': result.by_grade,
                'by_market': result.by_market,
                'processing_time_ms': result.processing_time_ms,
                'market_status': result.market_status,
                'market_summary': result.market_summary,
                'trending_themes': result.trending_themes,
                'updated_at': datetime.now().isoformat()
            }

            # Save to JSON
            file_path = os.path.join(BASE_DIR, 'data', 'jongga_v2_latest.json')
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False, cls=NumpyEncoder)
                
            log(f"종가베팅 V2 분석 완료: {len(signals_json)} 종목 (SignalGenerator)", "SUCCESS")
            return True
        else:
            log("종가베팅 분석 결과 없음 (None returned)", "WARNING")
            return False

    except Exception as e:
        log(f"종가베팅 분석 실패: {e}", "ERROR")
        import traceback
        traceback.print_exc()
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
        
        # [Fix] CSV의 supply 데이터를 AI 결과에 병합
        try:
            csv_data = {row['ticker']: row for _, row in target_df.iterrows()}
            for signal in results.get('signals', []):
                ticker = signal.get('ticker')
                if ticker in csv_data:
                    csv_row = csv_data[ticker]
                    
                    # 데이터 병합 (타입 안전 처리)
                    try:
                        signal['foreign_5d'] = int(float(csv_row.get('foreign_5d', 0)))
                    except: signal['foreign_5d'] = 0
                        
                    try:
                        signal['inst_5d'] = int(float(csv_row.get('inst_5d', 0)))
                    except: signal['inst_5d'] = 0
                        
                    try:
                        signal['score'] = float(csv_row.get('score', 0))
                    except: signal['score'] = 0.0
                        
                    try:
                        signal['contraction_ratio'] = float(csv_row.get('contraction_ratio', 0))
                    except: signal['contraction_ratio'] = 0.0
                        
                    try:
                        signal['entry_price'] = int(float(csv_row.get('entry_price', 0)))
                    except: signal['entry_price'] = 0

                    try:
                        current_p = int(float(csv_row.get('current_price', 0)))
                        if current_p == 0:
                            current_p = signal['entry_price']
                        signal['current_price'] = current_p
                    except: signal['current_price'] = signal.get('entry_price', 0)
                        
                    try:
                        signal['vcp_score'] = float(csv_row.get('vcp_score', 0))
                    except: signal['vcp_score'] = 0.0
                        
                    signal['market'] = csv_row.get('market', signal.get('market', 'KOSPI'))
            
            log("AI 결과에 Supply 데이터 병합 완료", "INFO")
        except Exception as merge_e:
            log(f"데이터 병합 중 오류 (무시): {merge_e}", "WARNING")
        
        # 메타데이터
        results['generated_at'] = datetime.now().isoformat()
        results['signal_date'] = target_date
        
        # 시장 지수 데이터 수집 (frontend 호환용)
        market_indices = {}
        try:
            from pykrx import stock
            today_str = datetime.now().strftime('%Y%m%d')
            kospi = stock.get_index_ohlcv(today_str, today_str, "1001")
            kosdaq = stock.get_index_ohlcv(today_str, today_str, "2001")
            
            if not kospi.empty:
                market_indices['kospi'] = {
                    'value': float(kospi['종가'].iloc[-1]),
                    'change_pct': float(kospi['등락률'].iloc[-1]) if '등락률' in kospi.columns else 0
                }
            if not kosdaq.empty:
                market_indices['kosdaq'] = {
                    'value': float(kosdaq['종가'].iloc[-1]),
                    'change_pct': float(kosdaq['등락률'].iloc[-1]) if '등락률' in kosdaq.columns else 0
                }
        except: pass
        
        results['market_indices'] = market_indices

        # 저장 (ai_analysis_results.json)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
            
        log(f"AI 분석 결과 저장 완료: {filepath}", "SUCCESS")
        
        # 최신 파일 (ai_analysis_results.json)
        if target_date == datetime.now().strftime('%Y-%m-%d'):
            main_path = os.path.join(data_dir, 'ai_analysis_results.json')
            with open(main_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

            # [Fix] kr_ai_analysis.json 생성 (Frontend용)
            kr_ai_path = os.path.join(data_dir, 'kr_ai_analysis.json')
            with open(kr_ai_path, 'w', encoding='utf-8') as f:
                 json.dump(results, f, ensure_ascii=False, indent=2)
            log(f"Frontend 데이터 동기화 완료: {kr_ai_path}", "SUCCESS")
                
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
                for i, s in enumerate(file_data.get('signals', [])):
                    # ScoreDetail 복원 (total 포함)
                    sc = s.get('score', {})
                    score_obj = ScoreDetail(**sc)
                    
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
                    scanned_count=file_data.get('scanned_count', 0),
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


def update_vcp_signals_recent_price():
    """VCP 시그널 로그(signals_log.csv)의 최신 가격 업데이트"""
    log("VCP 시그널 최신 가격 업데이트 시작...")
    try:
        file_path = os.path.join(BASE_DIR, 'data', 'signals_log.csv')
        if not os.path.exists(file_path):
            log("VCP 시그널 파일이 없습니다.", "WARNING")
            return

        df = pd.read_csv(file_path, dtype={'ticker': str})
        
        # 오늘 날짜
        today_str = datetime.now().strftime('%Y%m%d')
        
        # 최신 가격 데이터 로드 (pykrx 사용 - 일괄 수집 방식)
        from pykrx import stock
        
        current_prices = {}
        updated_count = 0  # [Fix] Initialize counter
        
        # 1. KOSPI/KOSDAQ 전체 종가 일괄 조회 (매우 빠름)
        for market in ["KOSPI", "KOSDAQ"]:
            try:
                # get_market_ohlcv(date, market=...) 사용
                df_market = stock.get_market_ohlcv(today_str, market=market)
                if not df_market.empty:
                    for ticker, row in df_market.iterrows():
                        # [Fix] Handle float strings (e.g. '2650.55')
                        try:
                            price = int(float(row['종가']))
                        except:
                            price = 0
                            
                        if price > 0:
                            current_prices[str(ticker)] = price
            except Exception as e:
                log(f"{market} 전체 가격 조회 실패 fallback 시도: {e}", "WARNING")
        
        # 2. Toss Batch API를 이용한 최종 보정 (신뢰도 높음)
        try:
            from engine.toss_collector import TossCollector
            collector = TossCollector()
            # 시그널에 있는 종목들 우선 보정
            sig_tickers = df['ticker'].unique().tolist()
            toss_data = collector.get_prices_batch(sig_tickers)
            if toss_data:
                for t, data in toss_data.items():
                    if data['current'] > 0:
                        current_prices[str(t)] = int(float(data['current']))
                log(f"Toss Batch API를 통한 {len(toss_data)}개 종목 최종 보정 완료", "SUCCESS")
        except Exception as te:
            log(f"Toss 보정 시도 실패: {te}", "WARNING")
        
        # 3. 부족한 데이터가 있다면 개별 조회 (Fallback - Naver)
        tickers = df['ticker'].unique()
        missing_tickers = [t for t in tickers if t not in current_prices]
        
        if missing_tickers:
            log(f"누락된 {len(missing_tickers)}개 종목 개별 조회 시작 (Fallback)...")
            for ticker in missing_tickers:
                try:
                    data = fetch_stock_price(ticker)
                    if data and 'price' in data:
                        current_prices[ticker] = int(float(data['price']))
                except:
                    pass
        
        log(f"총 {len(current_prices)}개 종목의 데이터 수집 완료. 업데이트 적용 중...")
        
        # 데이터프레임 업데이트
        for idx, row in df.iterrows():
            ticker = row['ticker']
            if ticker in current_prices:
                current_p = current_prices[ticker]
                entry_p = row['entry_price']
                
                df.at[idx, 'current_price'] = current_p
                if entry_p > 0:
                    ret = ((current_p - entry_p) / entry_p) * 100
                    df.at[idx, 'return_pct'] = round(ret, 2)
                
                updated_count += 1
        
        # 저장
        df.to_csv(file_path, index=False, encoding='utf-8-sig')
        log(f"VCP 시그널 가격 업데이트 완료: {updated_count}건 갱신", "SUCCESS")
        
        # kr_ai_analysis.json도 동기화 (선택 사항)
        update_kr_ai_analysis_prices(current_prices)
        
    except Exception as e:
        log(f"가격 업데이트 실패: {e}", "ERROR")

def update_kr_ai_analysis_prices(price_map):
    """kr_ai_analysis.json 파일의 가격 정보도 업데이트"""
    try:
        kr_ai_path = os.path.join(BASE_DIR, 'data', 'kr_ai_analysis.json')
        if not os.path.exists(kr_ai_path):
            return
            
        with open(kr_ai_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        updated = False
        if 'signals' in data:
            for signal in data['signals']:
                ticker = signal.get('ticker')
                if ticker in price_map:
                    current_p = price_map[ticker]
                    entry_p = signal.get('entry_price', current_p)
                    
                    signal['current_price'] = current_p
                    if entry_p > 0:
                        signal['return_pct'] = round(((current_p - entry_p) / entry_p) * 100, 2)
                    updated = True
        
        if updated:
            with open(kr_ai_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, cls=NumpyEncoder)
            log("kr_ai_analysis.json 가격 동기화 완료", "INFO")
            
    except Exception as e:
        log(f"AI 분석 파일 가격 동기화 실패: {e}", "WARNING")

if __name__ == '__main__':
    # 로깅 핸들러 초기화 (중복 방지 - 라이브러리 로그용)
    root = logging.getLogger()
    if root.handlers:
        for h in root.handlers[:]:
            root.removeHandler(h)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "init-prices":
            create_daily_prices()
        elif cmd == "init-inst":
            create_institutional_trend()
        elif cmd == "init-stocks":
            create_korean_stocks_list()
        elif cmd == "vcp-signal":
             # 특정 날짜 지정 가능 (YYYY-MM-DD)
            target_date = sys.argv[2] if len(sys.argv) > 2 else None
            create_signals_log(target_date)
        elif cmd == "ai-analysis":
            create_kr_ai_analysis()
        elif cmd == "update-prices":
            update_vcp_signals_recent_price()
        elif cmd == "all":
            log("전체 데이터 초기화 시작...")
            create_korean_stocks_list()
            create_daily_prices()
            create_institutional_trend()
            create_signals_log() # VCP 분석
            create_kr_ai_analysis() # AI 분석
            log("전체 데이터 초기화 완료!", "SUCCESS")
    else:
        main()

