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
import json
import math
import socket
import yfinance as yf
import time
import random
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError, as_completed
from datetime import datetime, timedelta, timezone

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

from numpy_json_encoder import NumpyEncoder
from engine.config import config, app_config
from engine.constants import SCREENING
from engine.collectors import EnhancedNewsCollector
from engine.llm_analyzer import LLMAnalyzer
from engine.pandas_utils_safe import safe_bool, safe_optional_float
from engine.vcp_ai_orchestration_helpers import VCP_AI_RECOMMENDATION_FIELDS
from services.kr_market_data_cache_core import atomic_write_text
from services.common_env_service import _env_file_lock as ai_analysis_lock
from services.kr_market_vcp_reanalysis_service import signals_log_lock, write_vcp_signals_csv_atomic

# =====================================================
# 주말/휴일 처리를 위한 유틸리티 함수
# =====================================================


def get_last_trading_date(reference_date=None, strict=False):
    """
    마지막 개장일 날짜를 반환합니다.
    - 주말(토/일)인 경우 금요일로 이동
    - 금요일이 휴일인 경우 pykrx를 통해 실제 마지막 개장일 확인
    
    Args:
        reference_date: 기준 날짜 (datetime 객체). None이면 오늘 날짜 사용.
        strict: True 면 지수로 개장일을 확인하지 못했을 때 주말 처리 날짜 대신 RuntimeError
    
    Returns:
        tuple: (last_trading_date_str, last_trading_date_obj)
               - last_trading_date_str: 'YYYYMMDD' 형식의 문자열
               - last_trading_date_obj: datetime 객체
    """
    if reference_date is None:
        reference_date = datetime.now()

    # 한국 정규장 마감(15:30 KST) + 데이터 갱신 마진 이전이면, 오늘이 거래일이어도
    # 종가 데이터가 없거나 불완전하므로 직전 거래일을 기준으로 잡는다.
    now_kst = datetime.now(timezone(timedelta(hours=9)))
    if reference_date.date() == now_kst.date() and now_kst.hour < 16:
        reference_date = reference_date - timedelta(days=1)

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
            log(f"개장일 미확인: pykrx 지수 데이터 없음 (기준 {target_date.strftime('%Y%m%d')}, 휴장일일 수 있음)", "WARNING")

    except ImportError:
        log("개장일 미확인: pykrx 미설치", "WARNING")
    except Exception as e:
        # [INFRA-106] 지수명 KeyError, KRX 미인증·점검 등. 공휴일을 거래일로 볼 수 있으므로 WARNING 으로 남긴다
        log(f"개장일 미확인: pykrx 지수 조회 실패 ({e})", "WARNING")

    if strict:
        raise RuntimeError("마지막 개장일을 확인하지 못했습니다")
    # 폴백: 주말 처리만 된 날짜 반환
    log(f"주말 처리 날짜로 진행합니다: {target_date.strftime('%Y%m%d')}", "WARNING")
    return target_date.strftime('%Y%m%d'), target_date


# =====================================================
# 실시간 시장 데이터 수집 함수
# =====================================================


def fetch_stock_price(ticker):
    """개별 종목 실시간 가격 수집"""
    import requests
    
    # 1. Try yfinance
    if YFINANCE_AVAILABLE:
        try:
            # 한국 종목은 .KS (KOSPI) 또는 .KQ (KOSDAQ) 접미사 필요
            yahoo_ticker = f"{ticker}.KS"
            
            # yfinance 에러 로그 억제 및 안전한 다운로드
            import logging as _logging
            yf_logger = _logging.getLogger('yfinance')
            original_level = yf_logger.level
            yf_logger.setLevel(_logging.CRITICAL)
            
            hist = pd.DataFrame()
            try:
                 hist = yf.download(yahoo_ticker, period='5d', progress=False, threads=False)
            except: pass
            finally:
                 yf_logger.setLevel(original_level)

            # 데이터 유효성 검사 (Close 컬럼 존재 여부)
            is_valid = False
            if not hist.empty:
                 if isinstance(hist.columns, pd.MultiIndex):
                      if 'Close' in hist.columns.get_level_values(0): is_valid = True
                 elif 'Close' in hist.columns:
                      is_valid = True
            
            if not is_valid:
                # KOSDAQ 시도
                yahoo_ticker = f"{ticker}.KQ"
                yf_logger.setLevel(_logging.CRITICAL)
                try:
                    hist = yf.download(yahoo_ticker, period='5d', progress=False, threads=False)
                except: pass
                finally:
                    yf_logger.setLevel(original_level)

            if not hist.empty:
                # Extract Close series safely
                close_series = None
                if isinstance(hist.columns, pd.MultiIndex):
                    try:
                        close_series = hist['Close']
                        if isinstance(close_series, pd.DataFrame): 
                            close_series = close_series.iloc[:, 0]
                    except:
                        # 최악의 경우 첫 번째 컬럼
                        close_series = hist.iloc[:, 0]
                elif 'Close' in hist.columns:
                    close_series = hist['Close']
                else:
                    close_series = hist.iloc[:, 0]
                
                # Ensure it is a Series
                if isinstance(close_series, pd.DataFrame):
                    close_series = close_series.iloc[:, 0]

                if not close_series.empty:
                    # 스칼라 값 변환 (.item() 사용)
                    def get_val(s, idx):
                        val = s.iloc[idx]
                        return val.item() if hasattr(val, 'item') else val

                    current = get_val(close_series, -1)
                    prev = get_val(close_series, -2) if len(close_series) > 1 else current
                    
                    change_pct = ((current - prev) / prev) * 100 if prev > 0 else 0
                    return {
                        'price': round(float(current), 0),
                        'change_pct': round(float(change_pct), 2),
                        'prev_close': round(float(prev), 0)
                    }
        except Exception as e:
            pass

    # 2. Try Toss Securities API (Fallback 1)
    try:
        toss_url = f"https://wts-info-api.tossinvest.com/api/v3/stock-prices/details?productCodes=A{str(ticker).zfill(6)}"
        res = requests.get(toss_url, timeout=3)
        if res.status_code == 200:
            result = res.json().get('result', [])
            if result:
                item = result[0]
                current = float(item.get('close', 0))
                prev = float(item.get('base', 0)) # base appears to be previous close
                
                if current > 0:
                    change_pct = ((current - prev) / prev) * 100 if prev > 0 else 0
                    return {
                        'price': round(current, 0),
                        'change_pct': round(change_pct, 2),
                        'prev_close': round(prev, 0)
                    }
    except Exception as e:
        # log(f"Toss API Fallback failed for {ticker}: {e}", "WARNING")
        pass

    # 3. Try Naver Securities API (Fallback 2)
    try:
        naver_url = f"https://m.stock.naver.com/api/stock/{str(ticker).zfill(6)}/basic"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(naver_url, headers=headers, timeout=3)
        if res.status_code == 200:
            data = res.json()
            if 'closePrice' in data:
                current = float(data['closePrice'].replace(',', ''))
                change_pct = float(data.get('fluctuationsRatio', 0))
                prev = float(data.get('compareToPreviousClosePrice', '0').replace(',', ''))
                
                # Naver 'compareToPreviousClosePrice' is the diff, not the price itself usually? 
                # Actually closer inspection of Naver API:
                # compareToPreviousClosePrice is the diff value. 
                # prev_close = current - diff (if up) or current + diff (if down)
                # But safer to calculate from percentage if available.
                # Let's derive prev from current and change_pct to be safe
                
                prev_calc = current / (1 + (change_pct / 100)) if change_pct != -100 else 0
                
                return {
                    'price': round(current, 0),
                    'change_pct': round(change_pct, 2),
                    'prev_close': round(prev_calc, 0)
                }
    except Exception as e:
        # log(f"Naver API Fallback failed for {ticker}: {e}", "WARNING")
        pass

    return None


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
    # File logging
    if level == "ERROR":
        logging.error(f"[init_data] {message}")
    elif level == "WARNING":
        logging.warning(f"[init_data] {message}")
    elif level == "SUCCESS":
        logging.info(f"[init_data] ✅ {message}")
    elif level == "DEBUG":
        logging.debug(f"[init_data] {message}")
    else:
        logging.info(f"[init_data] {message}")

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


def _normalize_trend_date_token(value):
    """수급 상세 응답의 날짜 토큰을 YYYY-MM-DD 문자열로 정규화한다."""
    token = str(value or "").strip()
    if not token:
        return None

    if len(token) >= 10:
        token = token[:10]

    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(token, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _collect_toss_trend_rows_for_ticker(ticker: str, expected_latest_dt: datetime) -> list[dict]:
    """Toss 최신 5거래일 상세를 date/ticker/foreign_buy/inst_buy 행으로 변환한다."""
    try:
        from engine.toss_collector import TossCollector

        trend_payload = TossCollector().get_investor_trend(ticker, days=5) or {}
    except Exception as error:
        log(f"[Supply Trend][Toss] {ticker} 조회 실패: {error}", "DEBUG")
        return []

    details = trend_payload.get("details", [])
    if not isinstance(details, list):
        return []

    rows = []
    for item in details:
        if not isinstance(item, dict):
            continue

        normalized_date = _normalize_trend_date_token(
            item.get("baseDate") or item.get("tradeDate") or item.get("date")
        )
        if not normalized_date:
            continue

        try:
            row_dt = datetime.strptime(normalized_date, "%Y-%m-%d")
        except ValueError:
            continue

        if row_dt.date() > expected_latest_dt.date():
            continue

        # [INFRA-095] 빈 종가·순매수 수량을 0 으로 채우지 않고 그 행을 버린다. 실제 0 수량은 저장한다
        try:
            close = float(item["close"])
            foreign_volume = float(item["netForeignerBuyVolume"])
            institution_volume = float(item["netInstitutionBuyVolume"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (close > 0 and math.isfinite(close) and math.isfinite(foreign_volume) and math.isfinite(institution_volume)):
            continue
        rows.append(
            {
                "date": normalized_date,
                "ticker": str(ticker).zfill(6),
                "foreign_buy": int(foreign_volume * close),
                "inst_buy": int(institution_volume * close),
                "source": "toss",
            }
        )

    return rows


def _backfill_institutional_trend_from_toss(
    *,
    tickers_set: set[str],
    file_path: str,
    expected_latest_dt: datetime,
) -> bool:
    """
    pykrx 수급 배치 응답이 비었을 때 Toss 최신 5거래일 상세로 CSV를 백필한다.

    Toss는 과거 arbitrary 날짜 조회가 불가능하므로, 요청 기준일 이하 최신 5거래일만 채운다.
    """
    tickers = sorted(str(ticker).zfill(6) for ticker in tickers_set if str(ticker).strip())
    if not tickers:
        return False

    collected_rows: list[dict] = []
    max_workers = max(1, min(8, len(tickers)))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_collect_toss_trend_rows_for_ticker, ticker, expected_latest_dt): ticker
            for ticker in tickers
        }
        total = len(futures)
        for index, future in enumerate(as_completed(futures), start=1):
            ticker = futures[future]
            try:
                ticker_rows = future.result()
            except Exception as error:
                log(f"[Supply Trend][Toss] {ticker} 백필 실패: {error}", "DEBUG")
                continue

            if ticker_rows:
                collected_rows.extend(ticker_rows)

            if index % 200 == 0 or index == total:
                log(f"[Supply Trend][Toss] {index}/{total} 종목 처리", "DEBUG")

    if not collected_rows:
        return False

    # [INFRA-093] 근사값은 빈 칸만 채운다. pykrx 로 저장된 정확한 순매수거래대금을 덮지 않는다
    final_df = _merge_save_csv(pd.DataFrame(collected_rows), file_path, keep="first")

    latest_backfilled_dt = pd.to_datetime(final_df["date"], errors="coerce").max()
    if pd.isna(latest_backfilled_dt):
        return False

    log(
        f"수급 데이터 업데이트 완료 (Toss 백필): 총 {len(final_df)}행",
        "WARNING",
    )
    return latest_backfilled_dt.date() >= expected_latest_dt.date()


def _write_vcp_signals_latest_payload(
    *,
    target_date: str | None,
    signals: list[dict] | None,
) -> None:
    payload = {
        "date": str(target_date or datetime.now().strftime("%Y-%m-%d")),
        "generated_at": datetime.now().isoformat(),
        "total_candidates": len(signals or []),
        "filtered_count": len(signals or []),
        "signals": signals or [],
    }
    latest_path = os.path.join(BASE_DIR, "data", "vcp_signals_latest.json")
    atomic_write_text(latest_path, json.dumps(payload, ensure_ascii=False, indent=2, cls=NumpyEncoder))

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
            kospi_cap = kospi_cap.sort_values('시가총액', ascending=False).head(1000)
            for ticker in kospi_cap.index:
                try:
                    name = stock.get_market_ticker_name(ticker)
                    all_data.append({'ticker': ticker, 'name': name, 'market': 'KOSPI', 'sector': ''})
                except: pass
            log(f"KOSPI 시가총액 상위 {len(kospi_cap)} 종목 수집", "SUCCESS")
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
            kosdaq_cap = kosdaq_cap.sort_values('시가총액', ascending=False).head(1000)
            for ticker in kosdaq_cap.index:
                try:
                    name = stock.get_market_ticker_name(ticker)
                    all_data.append({'ticker': ticker, 'name': name, 'market': 'KOSDAQ', 'sector': ''})
                except: pass
            log(f"KOSDAQ 시가총액 상위 {len(kosdaq_cap)} 종목 수집", "SUCCESS")
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


def _chunk_items(items, chunk_size):
    """리스트를 chunk_size 단위로 나눈다."""
    safe_chunk_size = max(1, int(chunk_size or 1))
    for idx in range(0, len(items), safe_chunk_size):
        yield items[idx: idx + safe_chunk_size]


def _extract_yfinance_ohlcv(raw_df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """yfinance download 결과에서 특정 심볼의 OHLCV를 표준 컬럼으로 정규화한다."""
    if raw_df is None or raw_df.empty:
        return pd.DataFrame()

    target_df = raw_df
    if isinstance(raw_df.columns, pd.MultiIndex):
        level0_values = raw_df.columns.get_level_values(0)
        level1_values = raw_df.columns.get_level_values(1)
        if symbol in level0_values:
            target_df = raw_df[symbol].copy()
        elif symbol in level1_values:
            target_df = raw_df.xs(symbol, axis=1, level=1, drop_level=True).copy()
        else:
            return pd.DataFrame()
    else:
        target_df = raw_df.copy()

    rename_map = {}
    for col in target_df.columns:
        normalized = str(col).strip().lower()
        if normalized in {"open", "high", "low", "close", "volume"}:
            rename_map[col] = normalized
        elif normalized == "adj close":
            rename_map[col] = "adj_close"
    target_df = target_df.rename(columns=rename_map)

    required_cols = ["open", "high", "low", "close", "volume"]
    if not all(col in target_df.columns for col in required_cols):
        return pd.DataFrame()

    normalized_df = target_df[required_cols].copy()

    if not isinstance(normalized_df.index, pd.DatetimeIndex):
        normalized_df.index = pd.to_datetime(normalized_df.index, errors="coerce")
    normalized_df = normalized_df[~normalized_df.index.isna()]
    if normalized_df.empty:
        return pd.DataFrame()

    for col in required_cols:
        normalized_df[col] = pd.to_numeric(normalized_df[col], errors="coerce")
    normalized_df = normalized_df.dropna(subset=required_cols)
    if normalized_df.empty:
        return pd.DataFrame()

    normalized_df[required_cols] = normalized_df[required_cols].astype(int)
    return normalized_df


def _append_yfinance_rows(new_data_list: list, ticker: str, normalized_df: pd.DataFrame) -> int:
    """정규화된 OHLCV DataFrame을 최종 저장 포맷으로 변환해 리스트에 추가한다."""
    if normalized_df is None or normalized_df.empty:
        return 0

    subset = normalized_df.reset_index()
    date_col = subset.columns[0]
    subset = subset.rename(columns={date_col: "date"})
    subset["date"] = pd.to_datetime(subset["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    subset = subset.dropna(subset=["date"])
    if subset.empty:
        return 0

    subset["ticker"] = str(ticker).zfill(6)
    subset = subset[["date", "ticker", "open", "high", "low", "close", "volume"]]
    new_data_list.append(subset)
    return len(subset)


def _download_yfinance_with_timeout(
    yf_module,
    symbols,
    *,
    start: str,
    end: str,
    use_threads: bool,
    request_timeout: int,
    call_timeout_seconds: int,
    group_by: str | None = None,
) -> pd.DataFrame:
    """yfinance 호출 자체를 별도 스레드로 실행해 하드 타임아웃을 보장한다."""

    def _run_download():
        kwargs = {
            "start": start,
            "end": end,
            "progress": False,
            "threads": bool(use_threads),
            "timeout": request_timeout,
        }
        if group_by:
            kwargs["group_by"] = group_by
        return yf_module.download(symbols, **kwargs)

    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(_run_download)
    try:
        return future.result(timeout=call_timeout_seconds)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def fetch_prices_yfinance(
    start_date,
    end_date,
    file_path,
    chunk_size=100,
    request_timeout=8,
    use_threads=True,
    call_timeout_seconds=20,
    max_runtime_seconds=300,
):
    """yfinance를 이용한 가격 데이터 수집 폴백 (배치 다운로드 + 타임아웃)."""
    try:
        if start_date.date() > end_date.date():
            log(
                f"yfinance 수집: 시작일({start_date.strftime('%Y-%m-%d')})이 종료일({end_date.strftime('%Y-%m-%d')})보다 미래입니다. (최신 상태)",
                "SUCCESS",
            )
            return True

        import yfinance as yf

        log("yfinance 백업 수집 모드 가동...", "DEBUG")
        stocks_file = os.path.join(BASE_DIR, "data", "korean_stocks_list.csv")
        if not os.path.exists(stocks_file):
            log("종목 리스트 파일이 없어 yfinance 수집 불가", "ERROR")
            return False

        stocks_df = pd.read_csv(stocks_file, dtype={"ticker": str})
        if stocks_df.empty or "ticker" not in stocks_df.columns:
            log("종목 리스트가 비어 있어 yfinance 수집을 건너뜁니다.", "WARNING")
            return True

        stocks_df["ticker"] = stocks_df["ticker"].astype(str).str.zfill(6)
        market_by_ticker = (
            stocks_df.set_index("ticker")["market"].to_dict()
            if "market" in stocks_df.columns
            else {}
        )

        ticker_symbols = []
        for ticker in stocks_df["ticker"].tolist():
            market = str(market_by_ticker.get(ticker, "KOSPI")).upper()
            suffix = ".KS" if market == "KOSPI" else ".KQ"
            ticker_symbols.append((ticker, f"{ticker}{suffix}"))

        safe_chunk_size = max(1, int(chunk_size or 100))
        safe_timeout = max(1, int(request_timeout or 8))
        safe_call_timeout = max(safe_timeout + 2, int(call_timeout_seconds or 20))
        safe_max_runtime = max(1, int(max_runtime_seconds or 300))
        total = len(ticker_symbols)
        total_chunks = (total + safe_chunk_size - 1) // safe_chunk_size
        if total == 0:
            log("yfinance 수집 대상 종목이 없습니다.", "WARNING")
            return True

        download_start = start_date.strftime("%Y-%m-%d")
        download_end = (end_date + timedelta(days=1)).strftime("%Y-%m-%d")
        process_start_ts = time.time()
        processed_tickers = 0
        collected_rows = 0
        new_data_list = []
        runtime_exceeded = False

        for chunk_index, chunk in enumerate(_chunk_items(ticker_symbols, safe_chunk_size), start=1):
            if shared_state.STOP_REQUESTED:
                log("⛔️ 사용자 요청으로 yfinance 수집을 중단합니다.", "WARNING")
                break

            elapsed_before_chunk = time.time() - process_start_ts
            if elapsed_before_chunk > safe_max_runtime:
                runtime_exceeded = True
                log(
                    f"yfinance 백업 수집 최대 실행시간 초과({safe_max_runtime}s). "
                    f"중단 시점: {processed_tickers}/{total}",
                    "ERROR",
                )
                break

            symbols = [item[1] for item in chunk]
            batch_df = pd.DataFrame()
            try:
                batch_df = _download_yfinance_with_timeout(
                    yf,
                    symbols if len(symbols) > 1 else symbols[0],
                    start=download_start,
                    end=download_end,
                    use_threads=bool(use_threads),
                    request_timeout=safe_timeout,
                    call_timeout_seconds=safe_call_timeout,
                    group_by="ticker",
                )
            except FuturesTimeoutError:
                log(
                    f"yfinance 배치 다운로드 타임아웃(chunk {chunk_index}/{total_chunks}, "
                    f"size={len(symbols)}, {safe_call_timeout}s). 개별 재시도합니다.",
                    "WARNING",
                )
            except Exception as batch_error:
                log(
                    f"yfinance 배치 다운로드 실패(chunk {chunk_index}/{total_chunks}, size={len(symbols)}): {batch_error}. 개별 재시도합니다.",
                    "WARNING",
                )

            chunk_rows = 0
            for ticker, symbol in chunk:
                normalized = _extract_yfinance_ohlcv(batch_df, symbol)
                chunk_rows += _append_yfinance_rows(new_data_list, ticker, normalized)

            if chunk_rows == 0 and len(chunk) > 1:
                for ticker, symbol in chunk:
                    try:
                        single_df = _download_yfinance_with_timeout(
                            yf,
                            symbol,
                            start=download_start,
                            end=download_end,
                            use_threads=False,
                            request_timeout=safe_timeout,
                            call_timeout_seconds=safe_call_timeout,
                        )
                        normalized = _extract_yfinance_ohlcv(single_df, symbol)
                        chunk_rows += _append_yfinance_rows(new_data_list, ticker, normalized)
                    except FuturesTimeoutError:
                        continue
                    except Exception:
                        continue

            processed_tickers += len(chunk)
            collected_rows += chunk_rows
            elapsed = max(0.001, time.time() - process_start_ts)
            speed = processed_tickers / elapsed
            remain = max(0, total - processed_tickers)
            eta_seconds = int(remain / speed) if speed > 0 else -1
            eta_text = f"{eta_seconds}s" if eta_seconds >= 0 else "계산중"
            progress_pct = (processed_tickers / total) * 100
            log(
                f"yfinance 진행: {processed_tickers}/{total} ({progress_pct:.1f}%) "
                f"- chunk {chunk_index}/{total_chunks}, 누적행 {collected_rows}, ETA {eta_text}",
                "INFO",
            )

        if runtime_exceeded:
            return False

        if new_data_list:
            final_df = _merge_save_csv(pd.concat(new_data_list, ignore_index=True), file_path)
            log(f"yfinance 백업 수집 완료 ({len(final_df)}행)", "SUCCESS")
            return True

        log("yfinance 수집 데이터 없음", "WARNING")
        return True

    except Exception as e:
        log(f"yfinance 폴백 실패: {e}", "ERROR")
        return False


def _should_abort_daily_pykrx_bulk_fetch(error: Exception) -> bool:
    """pykrx 전종목 일괄 조회 오류 중 즉시 폴백이 필요한 패턴인지 판별."""
    if isinstance(error, json.JSONDecodeError):
        return True

    message = str(error or "").strip().lower()
    if not message:
        return False

    known_error_signatures = [
        "none of [index(['시가', '고가', '저가', '종가']",
        "expecting value: line 1 column 1",
        "logout",
    ]
    return any(signature in message for signature in known_error_signatures)


def _all_zero_close_dates(df: pd.DataFrame) -> list[str]:
    """종가가 전 종목 0 인 날짜. pykrx 는 평일 휴장일에 이런 행을 돌려준다([INFRA-090])."""
    if df.empty or "date" not in df.columns or "close" not in df.columns:
        return []
    zero = pd.to_numeric(df["close"], errors="coerce").fillna(0).eq(0).groupby(df["date"]).all()
    return [str(d) for d in zero[zero].index]


def _merge_save_csv(new_df: pd.DataFrame, file_path: str, keep: str = "last") -> pd.DataFrame:
    """새 행을 (date, ticker) 기준으로 파일에 병합해 원자적으로 저장하고, 저장한 전체 프레임을 돌려준다.

    daily_prices.csv([INFRA-091])와 all_institutional_trend_data.csv([INFRA-092])가 함께 쓴다.
    0원 날짜 제거는 close 열이 있는 가격 파일에만 적용된다.

    병합 기준은 실행 시작 때 읽은 값이 아니라 잠금 안에서 다시 읽은 파일이다. 수집하는 몇 분
    사이에 17:00 스케줄러와 「Refresh VCP」가 겹쳐 저장해도 앞 실행의 행이 유실되지 않는다.
    잠금은 병합과 저장 구간만 잡고 네트워크 수집 동안에는 잡지 않는다. 읽는 쪽은 os.replace
    로 교체된 온전한 파일만 보므로 잠그지 않는다.

    빈 파일(0바이트)은 잃을 행이 없어 비어 있는 것으로 본다. 그 밖의 읽기 오류는 그대로 올려
    저장을 포기한다. 읽지 못한 이력을 새 행만으로 덮지 않기 위해서다.

    keep="first" 이면 파일에 이미 있는 (date, ticker) 가 이긴다. Toss 백필은 이 값으로
    빈 칸만 채워 pykrx 의 정확한 순매수거래대금을 근사값으로 덮지 않는다([INFRA-093]).
    """
    with signals_log_lock(file_path):
        existing_df = pd.DataFrame()
        if os.path.exists(file_path):
            try:
                existing_df = pd.read_csv(file_path, dtype={"ticker": str})
            except pd.errors.EmptyDataError:
                pass
            zero_dates = _all_zero_close_dates(existing_df)
            if zero_dates:
                existing_df = existing_df[~existing_df["date"].isin(zero_dates)]

        final_df = pd.concat([existing_df, new_df]) if not existing_df.empty else new_df
        final_df = final_df.drop_duplicates(subset=["date", "ticker"], keep=keep)
        final_df = final_df.sort_values(["ticker", "date"])
        # 기존 utf-8-sig 저장 형식을 유지한다
        atomic_write_text(file_path, "\ufeff" + final_df.to_csv(index=False))
    return final_df


def create_daily_prices(target_date=None, force=False, lookback_days=5):
    """
    일별 가격 데이터 수집 - pykrx 날짜별 일괄 조회 (속도 최적화)
    Args:
        target_date: 기준 날짜 (기본: 오늘)
        force: 강제 업데이트 여부
        lookback_days: 강제 업데이트 시 재수집할 기간 (기본: 5일)
    """
    log("일별 가격 데이터 수집 중 (Date-based Fast Mode)...", "DEBUG")
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
                existing_df = pd.read_csv(file_path, dtype={'ticker': str})
                zero_dates = _all_zero_close_dates(existing_df)
                if zero_dates:
                    log(f"전 종목 종가 0 인 저장 날짜 {zero_dates} 를 제외합니다. 다음 저장 때 파일에서 빠집니다.", "WARNING")
                    existing_df = existing_df[~existing_df['date'].isin(zero_dates)]
                if not existing_df.empty and 'date' in existing_df.columns:
                    max_date_str = existing_df['date'].max()
                    
                    # (중요) 종목 수 체크 - 새로 추가된 종목이 있을 수 있음
                    # 현재 등록된 종목 수(600개)와 마지막 날짜의 데이터 개수 비게
                    stocks_file = os.path.join(BASE_DIR, 'data', 'korean_stocks_list.csv')
                    total_stocks_count = int(SCREENING.VCP_SCREENING_DEFAULT_MAX_STOCKS)
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
        log(f"수집 구간: {req_start_date_str} ~ {end_date_str}", "DEBUG")

        # 날짜 리스트 생성
        date_range = pd.date_range(start=start_date_obj, end=end_date_obj)
        total_days = len(date_range)
        
        new_data_list = []
        processed_days = 0
        pykrx_bulk_fetch_unavailable = False
        zero_close_days = 0  # 전 종목 종가 0 으로 건너뛴 평일(휴장일)
        missed_days = 0  # 빈 결과나 예외로 자료를 못 받은 평일

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

            # [Optimization] 이미 수집된 데이터는 건너뛰기 (과거 데이터인 경우만)
            # 오늘 날짜는 장중 변동 가능하므로 항상 수집
            if not existing_df.empty and 'date' in existing_df.columns:
                if cur_date_fmt in existing_df['date'].values:
                     # 오늘이 아니면 Skip
                    if dt.date() < datetime.now().date():
                         log(f"  -> {cur_date_fmt} 데이터 존재 (Skip)", "DEBUG")
                         processed_days += 1
                         continue
                
            try:
                # 해당 날짜의 전 종목 시세 조회 (1회 요청)
                df = stock.get_market_ohlcv(cur_date_str, market="ALL")
                
                if df is None or df.empty:
                    # 휴장일 가능성
                    missed_days += 1
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

                if _all_zero_close_dates(df):
                    log(f"[Daily Prices] {cur_date_fmt} 전 종목 종가 0, 저장 생략 (휴장일 추정)", "INFO")
                    zero_close_days += 1
                    processed_days += 1
                    continue

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
                log(f"[Daily Prices] {cur_date_fmt} 수집 완료 ({len(df_final)}종목) - {progress:.1f}%", "DEBUG")
                
                # Rate Limit 방지
                time.sleep(random.uniform(0.05, 0.1))
                
            except Exception as e:
                if _should_abort_daily_pykrx_bulk_fetch(e):
                    pykrx_bulk_fetch_unavailable = True
                    log(
                        f"pykrx 전종목 시세 수집 불가 감지 ({cur_date_str}): {e}. yfinance 폴백으로 전환합니다.",
                        "WARNING",
                    )
                    break
                log(f"날짜별 수집 실패 ({cur_date_str}): {e}", "WARNING")
                missed_days += 1
                processed_days += 1

        if pykrx_bulk_fetch_unavailable:
            return fetch_prices_yfinance(start_date_obj, end_date_obj, file_path)
                
        # 병합 및 저장
        if new_data_list:
            log("데이터 병합 중...", "DEBUG")
            new_chunk_df = pd.concat(new_data_list, ignore_index=True)
            try:
                final_df = _merge_save_csv(new_chunk_df, file_path)
            except Exception as e:
                # 저장 실패는 수집 실패가 아니다. 아래 except 로 흘리면 yfinance 로 최대 300초
                # 다시 수집한 뒤 같은 저장에서 또 실패한다([INFRA-091] 리뷰)
                log(f"일별 가격 저장 실패, 기존 파일 유지: {e}", "ERROR")
                return False
            log(f"일별 가격 저장 완료: 총 {len(final_df)}행 (신규 {len(new_chunk_df)}행)", "DEBUG")
        else:
             if start_date_obj.date() > end_date_obj.date():
                 log("pykrx 수집 데이터 없음 (이미 최신).", "SUCCESS")
                 return True

             # 구간의 평일이 전부 휴장일이면 폴백하지 않는다. yfinance 는 직전 거래일 봉을
             # 일부 종목만 돌려줘 그 날짜를 덮어쓴다([INFRA-088] 3차)
             if zero_close_days and not missed_days and not shared_state.STOP_REQUESTED:
                 log(f"수집 구간의 평일 {zero_close_days}일이 모두 휴장일입니다. 저장할 자료가 없습니다.", "SUCCESS")
                 return True

             log("pykrx 수집 데이터 없음. yfinance 폴백 시도...", "DEBUG")
             return fetch_prices_yfinance(start_date_obj, end_date_obj, file_path)
                 
        return True

    except Exception as e:
        log(f"pykrx 수집 중 오류: {e} -> yfinance 폴백 시도", "WARNING")
        return fetch_prices_yfinance(start_date_obj, end_date_obj, file_path)


def create_institutional_trend(target_date=None, force=False, lookback_days=7):
    """
    수급 데이터 수집 - pykrx 기관/외국인 순매매 (Optimized)
    Args:
        target_date: 기준 날짜
        force: 강제 업데이트 여부
        lookback_days: 강제 업데이트 시 재수집할 기간 (기본: 7일). force 와 무관하게 Toss 근사·부분 날짜를
            다시 받는 창으로도 쓴다([INFRA-094])
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
                log(f"기존 수급 데이터 로드 실패 (저장 때 다시 읽지 못하면 기존 파일을 두고 중단): {e}", "WARNING")

        # [INFRA-094] 창 안의 Toss 근사 날짜와 종목이 모자란 날짜는 pykrx 로 다시 받는다
        # ponytail: lookback_days 창 밖의 근사·부분 날짜는 남는다. 먼 과거 복구가 필요하면 재수집 범위를 넓힌다.
        # pykrx 가 주지 않는 종목(ETF 등)의 Toss 행도 창을 벗어날 때까지 그 날짜를 매 실행 다시 묻게 한다(날짜당 호출 2회)
        refetch_dates = set()
        if not existing_df.empty and 'date' in existing_df.columns:
            window_start = (end_date_obj - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
            in_window = existing_df[existing_df['date'].between(window_start, end_date_obj.strftime('%Y-%m-%d'))]
            counts = in_window.groupby('date').size()
            refetch_dates = set(counts[counts < len(tickers_set) * 0.8].index)
            if 'source' in in_window.columns:
                refetch_dates |= set(in_window.loc[in_window['source'] == 'toss', 'date'])
        if refetch_dates:
            log(f"수급 데이터: 근사·부분 날짜 {len(refetch_dates)}개를 다시 수집합니다: {sorted(refetch_dates)}", "WARNING")
            start_date_obj = min(start_date_obj, datetime.strptime(min(refetch_dates)[:10], '%Y-%m-%d'))

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
                if cur_date_fmt in existing_df['date'].values and cur_date_fmt not in refetch_dates:
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
                
                # [INFRA-095] 한쪽 프레임에만 있거나 값이 비면 결측이다. 0 으로 채우지 않고 저장하지 않는다.
                # 다시 받는 날짜([INFRA-094])도 같은 교집합이라 한쪽 누락이 기존 값을 지우지 않는다.
                # 순매수거래대금 열이 없으면 KeyError 로 아래 except 가 그 날짜를 저장 없이 건너뛴다
                target_intersect = set(df_foreign.index) & set(df_inst.index) & tickers_set
                if df_foreign.empty != df_inst.empty:
                    log(f"[Supply Trend] {cur_date_fmt} 한쪽 투자자 프레임만 비어 저장 생략", "WARNING")

                for ticker in target_intersect:
                    f_val = df_foreign.loc[ticker, '순매수거래대금']
                    i_val = df_inst.loc[ticker, '순매수거래대금']
                    if pd.isna(f_val) or pd.isna(i_val):
                        continue
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
            final_df = _merge_save_csv(pd.DataFrame(new_data_list), file_path)
            log(f"수급 데이터 업데이트 완료: 총 {len(final_df)}행 (신규 {len(new_data_list)}행)", "DEBUG")
            # [INFRA-094] 과거 날짜만 다시 받고 최신일이 비었으면 아래 Toss 백필·stale 판정으로 넘긴다
            latest_saved_dt = pd.to_datetime(final_df["date"], errors="coerce").max()
            if pd.notna(latest_saved_dt) and latest_saved_dt.date() >= end_date_obj.date():
                return True
            existing_df = final_df

        expected_latest_dt = end_date_obj
        latest_existing_dt = None

        if not existing_df.empty and "date" in existing_df.columns:
            latest_existing_dt = pd.to_datetime(
                existing_df["date"], errors="coerce"
            ).max()
            if pd.isna(latest_existing_dt):
                latest_existing_dt = None

        needs_backfill = latest_existing_dt is None or latest_existing_dt.date() < expected_latest_dt.date()
        if needs_backfill and shared_state.STOP_REQUESTED:
            log("⛔️ 사용자 요청으로 중단되어 수급 Toss 백필을 건너뜁니다", "WARNING")
            return False

        if latest_existing_dt is None:
            if _backfill_institutional_trend_from_toss(
                tickers_set=tickers_set,
                file_path=file_path,
                expected_latest_dt=expected_latest_dt,
            ):
                return True
            log(
                "수급 데이터: 신규 수집 데이터가 없고 기존 데이터의 최신 날짜도 확인할 수 없습니다.",
                "ERROR",
            )
            return False

        if latest_existing_dt.date() < expected_latest_dt.date():
            if _backfill_institutional_trend_from_toss(
                tickers_set=tickers_set,
                file_path=file_path,
                expected_latest_dt=expected_latest_dt,
            ):
                return True
            log(
                f"수급 데이터 stale 감지: latest={latest_existing_dt.strftime('%Y-%m-%d')}, "
                f"expected>={expected_latest_dt.strftime('%Y-%m-%d')}",
                "ERROR",
            )
            return False

        log("수급 데이터: 신규 수집된 데이터가 없습니다.", "SUCCESS")
        return True

    except Exception as e:
        log(f"수급 데이터 수집 중 치명적 오류: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        return False


# signals_log.csv 의 열 목록. 시그널이 없을 때와 예외로 끝났을 때 만드는 빈 파일이 같은
# 열을 갖도록 한 곳에 둔다([VCP-028]).
_SIGNALS_LOG_COLUMNS = [
    'ticker', 'name', 'signal_date', 'market', 'status', 'score', 'grade', 'contraction_ratio',
    'entry_price', 'foreign_5d', 'inst_5d', 'foreign_1d', 'inst_1d', 'vcp_score', 'is_vcp',
    'current_price', 'ai_action', 'ai_confidence', 'ai_reason', 'return_pct', 'exit_price',
    'exit_date', 'hold_days',
]


def _read_signals_log(file_path: str) -> pd.DataFrame:
    """누적 로그를 읽는다. 0바이트·BOM 만 든 파일은 기존 로그가 없는 것으로 본다([VCP-030])."""
    try:
        return pd.read_csv(file_path, dtype={'ticker': str, 'signal_date': str})
    except pd.errors.EmptyDataError:
        log(f"{file_path} 가 비어 있어 기존 로그 없이 이어갑니다.", "WARNING")
        return pd.DataFrame(columns=_SIGNALS_LOG_COLUMNS)


def create_signals_log(target_date=None, run_ai=True, max_stocks=None, signal_limit=None):
    """VCP 시그널 로그 생성 - Using SmartMoneyScreener (engine.screener)"""
    log("VCP 시그널 분석 중 (SmartMoneyScreener)...")
    try:
        from engine.screener import SmartMoneyScreener

        def _grade_from_score(score: float) -> str:
            vcp_min_score = float(SCREENING.VCP_MIN_SCORE)
            if score >= 85:
                return "S"
            if score >= 75:
                return "A"
            if score >= vcp_min_score:
                return "B"
            if score >= (vcp_min_score - 10):
                return "C"
            return "D"

        def _optional_int(value):
            # [VCP-050] 결측은 None(빈 칸)이다. 값은 정수로 둬야 결측이 없는 날 기존 행이 `123.0` 표기로 바뀌지 않는다
            number = safe_optional_float(value)
            return None if number is None else int(number)

        resolved_max_stocks = int(SCREENING.VCP_SCREENING_DEFAULT_MAX_STOCKS)
        if max_stocks is not None:
            try:
                parsed_max_stocks = int(max_stocks)
                if parsed_max_stocks > 0:
                    resolved_max_stocks = parsed_max_stocks
            except (TypeError, ValueError):
                resolved_max_stocks = int(SCREENING.VCP_SCREENING_DEFAULT_MAX_STOCKS)

        resolved_signal_limit = int(SCREENING.VCP_SIGNALS_TO_SHOW)
        if signal_limit is not None:
            try:
                parsed_signal_limit = int(signal_limit)
                if parsed_signal_limit > 0:
                    resolved_signal_limit = parsed_signal_limit
            except (TypeError, ValueError):
                resolved_signal_limit = int(SCREENING.VCP_SIGNALS_TO_SHOW)

        # 스크리너 실행 (KOSPI+KOSDAQ 전체 분석)
        screener = SmartMoneyScreener(target_date=target_date)
        df_result = screener.run_screening(max_stocks=resolved_max_stocks)
        
        signals = []
        if not df_result.empty:
            for row in df_result.itertuples(index=False):
                row_vcp_score = float(getattr(row, "vcp_score", 0) or 0)
                row_is_vcp = safe_bool(getattr(row, "is_vcp", False))
                if not row_is_vcp:
                    # run_screening 이 이미 걸러내므로 정상 경로에서는 도달하지 않는다.
                    continue

                signals.append({
                    'ticker': str(getattr(row, 'ticker', '')),
                    'name': str(getattr(row, 'name', '')),
                    'signal_date': target_date if target_date else datetime.now().strftime('%Y-%m-%d'),
                    'market': str(getattr(row, 'market', '')),
                    'status': 'OPEN',
                    'score': round(float(getattr(row, 'score', 0) or 0), 1),
                    'grade': _grade_from_score(float(getattr(row, 'score', 0) or 0)),
                    'contraction_ratio': float(getattr(row, 'contraction_ratio', 0) or 0),
                    'entry_price': int(float(getattr(row, 'entry_price', 0) or 0)),
                    'foreign_5d': _optional_int(getattr(row, 'foreign_net_5d', None)),
                    'inst_5d': _optional_int(getattr(row, 'inst_net_5d', None)),
                    'foreign_1d': safe_optional_float(getattr(row, 'foreign_net_1d', None)),
                    'inst_1d': safe_optional_float(getattr(row, 'inst_net_1d', None)),
                    'vcp_score': int(row_vcp_score),
                    'is_vcp': row_is_vcp,
                    'current_price': int(float(getattr(row, 'entry_price', 0) or 0)) # Approximation or need fetch
                })

        log(f"총 {len(signals)}개 시그널 감지")
        
        # 점수 높은 순 정렬 (상위 N개 제한)
        signals = sorted(signals, key=lambda x: x['score'], reverse=True)[:resolved_signal_limit]
        
        # AI 분석 실행 (옵션)
        if run_ai and signals:
            loop = None
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
                    
                    ai_filename = f'ai_analysis_results_{date_str}.json'
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
                            'foreign_1d': signal.get('foreign_1d'),
                            'inst_1d': signal.get('inst_1d'),
                            'entry_price': entry_p,
                            'current_price': curr_p,
                            'return_pct': ret_p,
                            'vcp_score': signal.get('vcp_score', 0),
                            # AI 분석 결과 통합
                            # 뉴스 데이터 추가
                            'news': news_items,
                        }
                        kr_signal.update({
                            field: ai_data.get(field)
                            for field in VCP_AI_RECOMMENDATION_FIELDS
                        })
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
                    
                    from services.common_update_ai_analysis_service import _write_ai_analysis_files
                    written_count = _write_ai_analysis_files(
                        data_dir=os.path.join(BASE_DIR, 'data'),
                        analysis_date=signals[0]['signal_date'], results=kr_ai_data,
                    )

                    if written_count:
                        log(f"[AI Analysis] 분석 완료 및 저장: {ai_filename} ({written_count}종목)", "SUCCESS")
                    else:
                        log("[AI Analysis] 유효 추천 없음: 기존 캐시 유지", "WARNING")
                
            except Exception as e:
                log(f"[AI Analysis] 실행 중 오류 발생: {e}", "ERROR")
                import traceback
                traceback.print_exc()
            finally:
                if loop is not None:
                    loop.close()
                    asyncio.set_event_loop(None)

        


        # AI 판정을 CSV 행에 병합한다. 고르는 규칙은 실패 재분석과 같은 함수 하나다([VCP-040])
        if run_ai and signals and 'ai_results' in locals() and ai_results:
            try:
                # 지연 import: app 패키지는 이 분기에 들어올 때 적재한다(_write_ai_analysis_files 도 같다)
                from app.routes.kr_market_vcp_signal_helpers import _extract_vcp_ai_recommendation

                for signal in signals:
                    if signal['ticker'] in ai_results:
                        _, signal['ai_action'], signal['ai_confidence'], signal['ai_reason'] = (
                            _extract_vcp_ai_recommendation(ai_results, signal['ticker'])
                        )
            except Exception as e:
                log(f"AI 결과 병합 중 오류: {e}", "WARNING")

        if signals:
            df_new = pd.DataFrame(signals)
            file_path = os.path.join(BASE_DIR, 'data', 'signals_log.csv')
            _write_vcp_signals_latest_payload(
                target_date=str(df_new['signal_date'].iloc[0]) if 'signal_date' in df_new.columns and not df_new.empty else target_date,
                signals=signals,
            )
            
            # 기존 로그가 있으면 로드하여 병합 (Append & Deduplicate)
            # 읽기·병합·교체를 다른 쓰기 경로와 직렬화한다([VCP-035])
            with signals_log_lock(file_path):
                if os.path.exists(file_path):
                    try:
                        # 타입 명시하여 로드 (중복 방지 핵심)
                        df_old = _read_signals_log(file_path)
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
                    
                        write_vcp_signals_csv_atomic(df_combined, file_path)
                    except Exception as e:
                        # 기존 로그를 버리지 않는다([VCP-029]). 오늘 자 시그널은 CSV 에 남지 않으므로
                        # 실패로 돌려주고, 파일은 운영자가 이 경고를 보고 손본다.
                        log(f"기존 로그 병합 실패: {e}. {file_path} 를 보존하고 오늘 자 결과를 저장하지 않습니다. 파일을 고친 뒤 다시 실행하십시오.", "WARNING")
                        return False
                else:
                    write_vcp_signals_csv_atomic(df_new, file_path)

            log(f"VCP 시그널 분석 완료: {len(signals)} 종목 감지 (누적 저장)", "SUCCESS")
            return True
        else:
            log("VCP 조건 충족 종목 없음", "WARNING")
            file_path = os.path.join(BASE_DIR, 'data', 'signals_log.csv')
            current_date = str(target_date or datetime.now().strftime('%Y-%m-%d'))
            cleaned = True
            with signals_log_lock(file_path):
                if os.path.exists(file_path):
                    try:
                        existing_df = _read_signals_log(file_path)
                        if 'signal_date' in existing_df.columns:
                            existing_df = existing_df[existing_df['signal_date'].astype(str) != current_date]
                        write_vcp_signals_csv_atomic(existing_df, file_path)
                    except Exception as e:
                        # 기존 로그를 버리지 않는다([VCP-029]). 오늘 자 옛 행을 걷어내지 못했으므로 실패로 돌려준다.
                        log(f"기존 VCP 로그 정리 실패: {e}. {file_path} 를 보존합니다. 파일을 고친 뒤 다시 실행하십시오.", "WARNING")
                        cleaned = False
                else:
                    write_vcp_signals_csv_atomic(pd.DataFrame(columns=_SIGNALS_LOG_COLUMNS), file_path)
            _write_vcp_signals_latest_payload(
                target_date=target_date,
                signals=[],
            )
            if cleaned:
                log("VCP 조건 충족 종목 없음 - 빈 결과 저장", "INFO")
            return cleaned
            
    except Exception as e:
        log(f"VCP 분석 실패: {e}", "WARNING")
        # 누적 로그는 건드리지 않는다. 예외 한 번에 지난 날짜의 행까지 지우면 화면의
        # 최신 저장분 대체와 히스토리가 함께 사라진다([VCP-028]). 파일이 없을 때만
        # 「시그널 없음」 갈래와 같은 23개 열의 빈 파일을 만든다.
        file_path = os.path.join(BASE_DIR, 'data', 'signals_log.csv')
        # 확인과 생성 사이에 다른 경로가 파일을 만들 수 있다([VCP-035]). 잠금을 열지 못한 예외가
        # 이 갈래를 다시 지나면 실패는 False 라는 계약이 깨지므로 여기서 받는다
        try:
            with signals_log_lock(file_path):
                if not os.path.exists(file_path):
                    write_vcp_signals_csv_atomic(pd.DataFrame(columns=_SIGNALS_LOG_COLUMNS), file_path)
        except OSError as lock_error:
            log(f"빈 VCP 로그 준비 실패: {lock_error}", "WARNING")
        # 최신 파일 저장이 실패해 이 갈래로 왔다면 여기서도 다시 실패한다([VCP-058])
        try:
            _write_vcp_signals_latest_payload(
                target_date=target_date,
                signals=[],
            )
        except OSError as latest_error:
            log(f"빈 VCP 최신 결과 저장 실패: {latest_error}", "WARNING")
            return False
        log("VCP 분석 오류 - 기존 로그 보존, 빈 최신 결과 저장", "INFO")
        return False


def create_jongga_v2_latest():
    """종가베팅 V2 최신 결과 생성 - Using Central SignalGenerator"""
    log("종가베팅 V2 분석 중 (SignalGenerator)...")
    try:
        from engine.generator import run_screener
        import asyncio

        # run_screener 가 일자·최신 파일을 원자적으로 저장한다. 여기서 다시 쓰지 않는다.
        result = asyncio.run(run_screener())

        if result:
            log(f"종가베팅 V2 분석 완료: {len(result.signals)} 종목 (SignalGenerator)", "SUCCESS")
            return True
        else:
            log("종가베팅 분석 결과 없음 (None returned)", "WARNING")
            return False

    except Exception as e:
        log(f"종가베팅 분석 실패: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        return False


def create_kr_ai_analysis(target_date=None):
    """현행 VCP 엔진으로 저장 시그널을 분석한다."""
    from services.common_update_ai_analysis_service import run_ai_analysis_step

    return run_ai_analysis_step(
        target_date=target_date, selected_items=["AI Analysis"], vcp_df=None,
        update_item_status=lambda item, status: log(f"{item}: {status}"),
        shared_state=shared_state, logger=logging.getLogger(__name__),
        data_dir=os.path.join(BASE_DIR, "data"),
    )


def create_kr_ai_analysis_with_key(target_dates=None, api_key=None):
    """종료된 개인 키 모의 분석 진입점. 키와 파일을 사용하지 않는다."""
    log("구형 개인 키 분석은 종료되었습니다. VCP 재분석 기능을 사용하세요.", "WARNING")
    return {"count": 0, "error": "LEGACY_ANALYSIS_RETIRED"}


def send_jongga_notification():
    """종가베팅 V2 결과 알림 발송"""
    data_dir = os.path.join(BASE_DIR, 'data')
    guard_key = None
    guard_claimed = False
    guard_marked = False
    try:
        import json
        from engine.messenger import Messenger
        from engine.models import ScreenerResult, Signal, ScoreDetail, ChecklistDetail, SignalStatus, Grade
        from datetime import datetime
        from services.jongga_notification_guard_service import (
            claim_jongga_notification_send,
            mark_jongga_notification_sent,
        )
        
        data_file = os.path.join(data_dir, 'jongga_v2_latest.json')
        
        if os.path.exists(data_file):
            with open(data_file, 'r', encoding='utf-8') as f:
                file_data = json.load(f)
            
            raw_signals = file_data.get('signals', []) if file_data else []
            notification_type = "daily"

            messenger = Messenger()
            if getattr(getattr(messenger, "config", None), "disabled", False):
                log("종가베팅 알림 비활성화 상태 - 발송 생략", "INFO")
                return

            guard_claimed, guard_key = claim_jongga_notification_send(
                data_dir=data_dir,
                date_str=file_data.get('date') if file_data else None,
                signals=raw_signals,
                notification_type=notification_type,
            )
            if not guard_claimed:
                log(f"중복 종가베팅 알림 생략: {guard_key}", "INFO")
                return

            if raw_signals:
                # 객체 복원 (Messenger 호환성)
                signals = []
                for i, s in enumerate(raw_signals):
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
                
                messenger.send_screener_result(result)
                mark_jongga_notification_sent(data_dir, guard_key)
                guard_marked = True
                log(f"알림 발송 완료: {len(signals)}개 신호", "SUCCESS")
            else:
                messenger.send_custom_message(
                    title="종가베팅 신호 없음",
                    message="오늘은 발송할 종가베팅 신호가 없습니다. (0개)",
                    channels=None,
                )
                mark_jongga_notification_sent(data_dir, guard_key)
                guard_marked = True
                log("발송할 신호 없음 (0개)", "INFO")
                
    except Exception as notify_error:
        if guard_claimed and guard_key and not guard_marked:
            try:
                from services.jongga_notification_guard_service import release_jongga_notification_claim

                release_jongga_notification_claim(data_dir, guard_key)
            except Exception:
                pass
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
        
        # 최신 가격 데이터 로드 (pykrx 사용)
        from pykrx import stock
        import time

        updated_count = 0
        
        # 유니크 티커 목록
        tickers = df['ticker'].unique()
        
        current_prices = {}
        log(f"총 {len(tickers)}개 종목의 현재가 조회 중...")
        
        for ticker in tickers:
            try:
                price_found = False
                current_price = 0
                
                # 1. pykrx 시도
                try:
                    df_price = stock.get_market_ohlcv(today_str, today_str, ticker)
                    if not df_price.empty:
                        current_price = int(df_price['종가'].iloc[-1])
                        if current_price > 0:
                            current_prices[ticker] = current_price
                            price_found = True
                except:
                    pass
                
                # 2. yfinance 폴백 (fetch_stock_price 사용)
                if not price_found:
                    data = fetch_stock_price(ticker)
                    if data and 'price' in data:
                        current_price = int(data['price'])
                        if current_price > 0:
                            current_prices[ticker] = current_price
                            price_found = True
                            # log(f"  -> {ticker} yfinance 폴백 성공: {current_price}", "INFO")

                time.sleep(0.01) # Rate limiting
            except Exception as e:
                # log(f"{ticker} 가격 조회 실패: {e}", "WARNING")
                pass
        
        log(f"{len(current_prices)}개 종목 현재가 확보 완료. 업데이트 적용 중...")
        
        # 시세 조회는 잠금 밖에서 한다. 그동안 다른 경로가 쓴 행을 지우지 않도록 잠금 안에서
        # 다시 읽고 티커 기준으로 적용한다([VCP-035])
        with signals_log_lock(file_path):
            df = pd.read_csv(file_path, dtype={'ticker': str})
            for idx, row in df.iterrows():
                ticker = row['ticker']
                # 청산 행의 현재가·수익률은 청산 시점의 실현값이다([VCP-051])
                if ticker in current_prices and row.get('status') != 'CLOSED':
                    current_p = current_prices[ticker]
                    entry_p = row['entry_price']
                
                    df.at[idx, 'current_price'] = current_p
                    if entry_p > 0:
                        ret = ((current_p - entry_p) / entry_p) * 100
                        df.at[idx, 'return_pct'] = round(ret, 2)
                
                    updated_count += 1

            write_vcp_signals_csv_atomic(df, file_path)
        log(f"VCP 시그널 가격 업데이트 완료: {updated_count}건 갱신", "SUCCESS")
        
        # kr_ai_analysis.json도 동기화 (선택 사항)
        update_kr_ai_analysis_prices(current_prices)
        
    except Exception as e:
        log(f"가격 업데이트 실패: {e}", "ERROR")

def update_kr_ai_analysis_prices(price_map):
    """kr_ai_analysis.json 파일의 가격 정보도 업데이트"""
    try:
        kr_ai_path = os.path.join(BASE_DIR, 'data', 'kr_ai_analysis.json')
        # AI 판정 병합(_write_ai_analysis_files)과 같은 잠금이다. 잠금 밖에서 읽으면 그 사이 병합한 판정을 지운다([VCP-052])
        with ai_analysis_lock(kr_ai_path):
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
                atomic_write_text(kr_ai_path, json.dumps(data, ensure_ascii=False, indent=2, cls=NumpyEncoder))
                log("kr_ai_analysis.json 가격 동기화 완료", "INFO")

    except Exception as e:
        log(f"AI 분석 파일 가격 동기화 실패: {e}", "WARNING")

if __name__ == '__main__':
    # run_screener 는 cwd 기준 data/ 에 쓰고 알림(스케줄러)은 BASE_DIR 기준으로 읽으므로 루트에서 돈다. 모듈 수준에 두면 import 하는 쪽 cwd 가 바뀐다 [INFRA-086]
    os.chdir(BASE_DIR)
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
            log("전체 데이터 초기화 완료!", "SUCCESS")
    else:
        main()
