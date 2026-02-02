#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Market Gate (시장 상태 분석)
PART 1 (Macro) & PART 7 (Technical) 통합 분석
"""
import logging
import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional, Any
import yfinance as yf

# Config Import
try:
    from engine.config import MarketGateConfig
except ImportError:
    # Fallback if running standalone
    from dataclasses import dataclass
    @dataclass
    class MarketGateConfig:
        usd_krw_safe: float = 1350.0
        usd_krw_warning: float = 1400.0
        usd_krw_danger: float = 1450.0
        kospi_ma_short: int = 20
        kospi_ma_long: int = 60
        foreign_net_buy_threshold: int = 500_000_000_000

logger = logging.getLogger(__name__)

class MarketGate:
    """시장 상태 분석기 (신호등) - KODEX 200 + 환율 + 수급"""

    def __init__(self, data_dir: str = 'data'):
        self.data_dir = data_dir
        self.kodex_ticker = '069500' # KODEX 200
        self.config = MarketGateConfig()

    def analyze(self, target_date: str = None) -> Dict[str, Any]:
        """시장 상태 분석 실행 (target_date: YYYY-MM-DD)"""
        try:
            # 1. 기술적 지표 (KODEX 200)
            df = self._load_price_data(target_date)
            if df.empty:
                return self._default_result("가격 데이터 부족")
            
            df = self._calculate_indicators(df)
            current_tech = df.iloc[-1]
            
            # 2. 거시 지표 (환율)
            usd_krw = self._get_usd_krw()
            
            # 3. 수급 지표 (외인/기관)
            supply_data = self._load_supply_data()
            
            # --- 점수 산출 (Total 100) ---
            
            # PART 7: 기술적 지표 (70점 만점 조정)
            score_trend = self._score_trend(current_tech)      # 25점
            score_rsi = self._score_rsi(current_tech)          # 25점
            score_macd = self._score_macd(current_tech)        # 20점 -> 10점 조정
            score_vol = self._score_volume(current_tech)       # 15점 -> 10점 조정
            
            tech_score = score_trend + score_rsi + min(score_macd, 10) + min(score_vol, 10)
            
            # PART 1: 거시/수급 지표 (30점 + Alpha penalty)
            # 환율 점수 (기본 15점, 위험 시 페널티)
            macro_score, macro_status = self._score_macro(usd_krw)
            
            # 수급 점수 (기본 15점)
            supply_score = self._score_supply(supply_data)
            
            total_score = tech_score + macro_score + supply_score
            
            # Gate Open 여부 판단 
            # 1. 총점 60점 이상
            # 2. 환율이 Danger 수준이면 무조건 False
            is_open = total_score >= 60
            if macro_status == "DANGER":
                is_open = False
                gate_reason = "환율 위험 수준 (Gate Closed)"
            elif total_score < 60:
                gate_reason = f"점수 미달 ({total_score}/60)"
            else:
                gate_reason = "시장 양호"

            # 상태 메시지
            if total_score >= 80 and macro_status == "SAFE":
                status = "강세장 (Strong Bull)"
                color = "GREEN"
            elif is_open:
                status = "중립/강세 (Neutral/Bull)"
                color = "YELLOW"
            else:
                status = "약세장/위험 (Bear/Danger)"
                color = "RED"

            # 4. 글로벌 데이터 (지수, 원자재, 크립토)
            global_data = self._get_global_data(target_date)
            sector_data = self._get_sector_data(target_date)

            # KOSPI/KOSDAQ 실제 지수 사용 (없으면 ETF 값 Fallback)
            real_kospi = global_data.get('indices', {}).get('kospi', {})
            kospi_close = real_kospi.get('value', float(current_tech['close']))
            kospi_change = real_kospi.get('change_pct', float(current_tech['change_pct']))

            return {
                "timestamp": datetime.now().isoformat(),
                "kospi_close": kospi_close,
                "kospi_change": kospi_change,
                "kosdaq_close": global_data.get('indices', {}).get('kosdaq', {}).get('value', 0),
                "kosdaq_change_pct": global_data.get('indices', {}).get('kosdaq', {}).get('change_pct', 0),
                "usd_krw": usd_krw,
                "total_score": total_score,
                "is_gate_open": is_open,
                "gate_reason": gate_reason,
                "status": status,
                "color": color,
                "dataset_date": str(current_tech['date']),
                "details": {
                    "tech_score": tech_score,
                    "macro_score": macro_score,
                    "supply_score": supply_score,
                    "trend_score": score_trend,
                    "rsi_score": score_rsi,
                    "rsi_val": round(float(current_tech['rsi']), 2),
                    "macd_val": round(float(current_tech['macd']), 2),
                    "ma20": float(current_tech['ma20']),
                    "ma60": float(current_tech['ma60']),
                    "macro_status": macro_status
                },
                "indices": global_data.get('indices', {}),
                "commodities": global_data.get('commodities', {}),
                "crypto": global_data.get('crypto', {}),
                "sectors": [
                    {
                        "name": k,
                        "change_pct": v,
                        "signal": "Bullish" if v > 0.5 else "Bearish" if v < -0.5 else "Neutral"
                    }
                    for k, v in sector_data.items()
                ]
            }

        except Exception as e:
            logger.error(f"Market Gate 분석 실패: {e}")
            return self._default_result(str(e))

    def _get_global_data(self, target_date: str = None) -> dict:
        """yfinance를 이용한 글로벌 데이터 수집"""
        try:
            import yfinance as yf
            import pandas as pd
            import math
            
            ticker_map = {
                'sp500': '^GSPC', 
                'nasdaq': '^IXIC',
                'kospi': '^KS11', # KOSPI 지수
                'kosdaq': '^KQ11', # KOSDAQ 지수
                'us_gold': 'GC=F',
                'us_silver': 'SI=F',
                'btc': 'BTC-USD',
                'eth': 'ETH-USD',
                'xrp': 'XRP-USD'
            }
            
            symbols = list(set(ticker_map.values()))
            
            # 날짜 설정
            end_date = None
            if target_date:
                # from datetime import timedelta (Used module level)
                dt = datetime.strptime(target_date, '%Y-%m-%d')
                end_date = (dt + timedelta(days=1)).strftime('%Y-%m-%d')
                
            try:
                # threads=False로 설정하여 Flask 환경에서의 잠재적 이슈 방지
                data = yf.download(symbols, period='1mo' if not end_date else None, end=end_date, progress=False, threads=False)
            except Exception as e:
                logger.error(f"yfinance download failed: {e}")
                return {}

            if data.empty:
                logger.warning("yfinance returned empty data")
                return {}
                
            result = {'indices': {}, 'commodities': {}, 'crypto': {}}
            
            # Helper to safely extract latest value
            def extract_val(symbol):
                try:
                    series = None
                    # MultiIndex handling
                    if isinstance(data.columns, pd.MultiIndex):
                        if symbol in data['Close'].columns:
                            series = data['Close'][symbol].dropna()
                        else:
                            return 0.0, 0.0
                    elif symbol in data.columns: # Flattened columns case
                         series = data[symbol].dropna()
                    else:
                        return 0.0, 0.0

                    if series is None or series.empty:
                        return 0.0, 0.0
                    
                    # Timezone handling: using tz_localize(None) strictly
                    try:
                        if series.index.tz is not None:
                            series.index = series.index.tz_localize(None)
                    except:
                        pass
                    
                    if target_date:
                        target_ts = pd.to_datetime(target_date)
                        series = series[series.index <= target_ts]
                        
                    if len(series) < 2:
                        if len(series) == 1: 
                            val = float(series.iloc[-1])
                            return (0.0 if math.isnan(val) else val), 0.0
                        return 0.0, 0.0
                        
                    latest = float(series.iloc[-1])
                    prev = float(series.iloc[-2])
                    
                    if math.isnan(latest): latest = 0.0
                    if math.isnan(prev) or prev == 0: 
                        change = 0.0
                    else:
                        change = ((latest - prev) / prev) * 100
                        
                    return latest, change
                except Exception as e:
                    logger.debug(f"Error extracting {symbol}: {e}")
                    return 0.0, 0.0

            # 인덱스
            # 1. Global Indices (yfinance)
            for key in ['sp500', 'nasdaq']:
                v, c = extract_val(ticker_map[key])
                result['indices'][key] = {'value': v, 'change_pct': c}

            # 2. Korean Indices (pykrx)
            try:
                from pykrx import stock
                from datetime import datetime
                today = datetime.now().strftime("%Y%m%d")
                
                # KOSPI (1001), KOSDAQ (2001)
                for key, ticker in [('kospi', '1001'), ('kosdaq', '2001')]:
                    try:
                        # 최근 5일치 가져와서 최신값 사용
                        start_date = (datetime.now() - pd.Timedelta(days=5)).strftime("%Y%m%d")
                        df = stock.get_index_ohlcv_by_date(start_date, today, ticker)
                        
                        if not df.empty:
                            latest = df.iloc[-1]
                            close_val = float(latest['종가'])
                            
                            # 등락률 계산
                            if '등락률' in df.columns:
                                change_pct = float(latest['등락률'])
                            else:
                                if len(df) >= 2:
                                    prev = float(df.iloc[-2]['종가'])
                                    change_pct = ((close_val - prev) / prev) * 100
                                else:
                                    change_pct = 0.0
                                    
                            result['indices'][key] = {'value': close_val, 'change_pct': change_pct}
                        else:
                            # Fallback to yfinance
                            v, c = extract_val(ticker_map[key])
                            result['indices'][key] = {'value': v, 'change_pct': c}
                            
                    except Exception as e:
                        logger.error(f"pykrx fetch failed for {key}: {e}")
                        # Fallback
                        v, c = extract_val(ticker_map[key])
                        result['indices'][key] = {'value': v, 'change_pct': c}

            except ImportError:
                 # pykrx 없으면 yfinance fallback
                 for key in ['kospi', 'kosdaq']:
                    v, c = extract_val(ticker_map[key])
                    result['indices'][key] = {'value': v, 'change_pct': c}
            
            # 원자재 (US) & 크립토
            for key in ['us_gold', 'us_silver']:
                v, c = extract_val(ticker_map[key])
                result['commodities'][key] = {'value': v, 'change_pct': c}

            # 원자재 (KRX) - ETF 사용
            # KRX 금: 411060 (ACE KRX금현물), KRX 은: 144600 (KODEX 은선물(H))
            try:
                from pykrx import stock
                krx_commodities = {
                    'gold': '411060',  # ACE KRX금현물
                    'silver': '144600' # KODEX 은선물(H)
                }
                
                # 오늘 날짜 (장 마감 전이면 전일 데이터일 수 있음)
                today_str = datetime.now().strftime("%Y%m%d")
                start_str = (datetime.now() - timedelta(days=5)).strftime("%Y%m%d")

                for key, ticker in krx_commodities.items():
                    try:
                        df = stock.get_market_ohlcv_by_date(start_str, today_str, ticker)
                        if not df.empty:
                            latest = df.iloc[-1]
                            val = float(latest['종가'])
                            
                            # 등락률
                            if '등락률' in df.columns:
                                chg = float(latest['등락률'])
                            else:
                                if len(df) >= 2:
                                    prev = float(df.iloc[-2]['종가'])
                                    chg = ((val - prev) / prev) * 100
                                else:
                                    chg = 0.0
                                    
                            result['commodities'][key] = {'value': val, 'change_pct': chg}
                        else:
                            # pykrx 데이터 없으면 yfinance ETF 조회 시도 (ACE KRX금현물: 411060.KS, KODEX 은선물(H): 144600.KS)
                            yf_ticker = f"{ticker}.KS"
                            try:
                                # 이미 다운로드된 data에 없을 수 있으므로 개별 Ticker로 간단히 조회
                                yf_stock = yf.Ticker(yf_ticker)
                                yf_hist = yf_stock.history(period='2d')
                                if not yf_hist.empty:
                                    latest_val = float(yf_hist['Close'].iloc[-1])
                                    prev_val = float(yf_hist['Close'].iloc[-2]) if len(yf_hist) >= 2 else latest_val
                                    yf_chg = ((latest_val - prev_val) / prev_val) * 100 if prev_val > 0 else 0.0
                                    result['commodities'][key] = {'value': latest_val, 'change_pct': yf_chg}
                                else:
                                    result['commodities'][key] = {'value': 0.0, 'change_pct': 0.0}
                            except:
                                result['commodities'][key] = {'value': 0.0, 'change_pct': 0.0}
                    except Exception as e:
                        logger.warning(f"KRX commodity fetch failed ({key}): {e}")
                        result['commodities'][key] = {'value': 0.0, 'change_pct': 0.0}

            except ImportError:
                 logger.warning("pykrx not installed, skipping KRX commodities")
                 result['commodities']['gold'] = {'value': 0.0, 'change_pct': 0.0}
                 result['commodities']['silver'] = {'value': 0.0, 'change_pct': 0.0}
                
            for key in ['btc', 'eth', 'xrp']:
                v, c = extract_val(ticker_map[key])
                result['crypto'][key] = {'value': v, 'change_pct': c}
            
            return result
            
        except Exception as e:
            logger.error(f"Global data processing error: {e}")
            return {}

    def _get_sector_data(self, target_date: str = None) -> dict:
        """주요 섹터 ETF 등락률 수집 (pykrx 사용)"""
        try:
            from pykrx import stock
            from datetime import datetime
            import pandas as pd
            
            # 주요 섹터 ETF (KODEX/TIGER)
            # pykrx는 6자리 종목코드 사용
            sectors = {
                '반도체': '091160',      # KODEX 반도체
                '2차전지': '305720',     # TIGER 2차전지테마
                '자동차': '091180',      # KODEX 자동차
                '헬스케어': '266420',    # KODEX 헬스케어
                'IT': '139260',          # TIGER 200 IT
                '은행': '091170',        # KODEX 은행
                '철강': '139240',        # TIGER 200 철강소재
                '증권': '102970',        # KODEX 증권
                'KOSPI 200': '069500'    # KODEX 200 (지수 대용)
            }
            
            today = datetime.now().strftime("%Y%m%d")
            # 최근 5일 데이터 조회 (안전하게)
            start_date = (datetime.now() - timedelta(days=5)).strftime("%Y%m%d")
            
            result = {}
            
            for name, ticker in sectors.items():
                try:
                    # pykrx OHLCV 조회
                    df = stock.get_market_ohlcv_by_date(start_date, today, ticker)
                    
                    if df.empty:
                        result[name] = 0.0
                        continue
                        
                    latest = df.iloc[-1]
                    
                    # 등락률 확인
                    if '등락률' in df.columns:
                        change_pct = float(latest['등락률'])
                    else:
                        # 수동 계산
                        if len(df) >= 2:
                            curr_close = float(latest['종가'])
                            prev_close = float(df.iloc[-2]['종가'])
                            change_pct = ((curr_close - prev_close) / prev_close) * 100
                        else:
                            change_pct = 0.0
                            
                    result[name] = round(change_pct, 2)
                    
                except Exception as e:
                    logger.warning(f"Sector data fetch failed ({name}): {e}")
                    result[name] = 0.0
                    
            return result
            
        except Exception as e:
            logger.warning(f"Sector data error: {e}")
            return {}



    def _load_price_data(self, target_date: str = None) -> pd.DataFrame:
        """KODEX 200 데이터 로드 및 날짜 필터링"""
        filepath = os.path.join(self.data_dir, 'daily_prices.csv')
        if not os.path.exists(filepath):
            logger.warning(f"데이터 파일 없음: {filepath}")
            return pd.DataFrame()
            
        try:
            df = pd.read_csv(filepath)
            df['ticker'] = df['ticker'].astype(str).str.zfill(6)
            df = df[df['ticker'] == self.kodex_ticker].copy()
            
            if df.empty:
                return pd.DataFrame()
                
            df = df.sort_values('date')
            
            # 날짜 필터링
            if target_date:
                df = df[df['date'] <= target_date]
                if df.empty:
                    logger.warning(f"{target_date} 이전 데이터가 없습니다.")
                    return pd.DataFrame()
            
            return df
        except Exception as e:
            logger.error(f"CSV 로드 실패: {e}")
            return pd.DataFrame()

    def save_analysis(self, result: Dict, target_date: str = None) -> str:
        """분석 결과 JSON 저장"""
        import json
        
        # 날짜 포맷팅 (YYYYMMDD)을 result['dataset_date'] 기반으로 할 수도 있음
        if target_date:
            date_str = target_date.replace('-', '')
        elif 'dataset_date' in result:
             # dataset_date가 YYYY-MM-DD 형식이면
             try:
                 date_str = result['dataset_date'].replace('-', '')
             except:
                 date_str = datetime.now().strftime('%Y%m%d')
        else:
            date_str = datetime.now().strftime('%Y%m%d')
            
        # 1. 날짜별 파일 저장
        filename = f'market_gate_{date_str}.json'
        filepath = os.path.join(self.data_dir, filename)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            logger.info(f"Market Gate 저장 완료: {filepath}")
        except Exception as e:
            logger.error(f"Market Gate 저장 실패: {e}")
            return ""
            
        # 2. 최신 파일(market_gate.json) 갱신 (오늘 날짜이거나 target_date가 없을 때)
        is_today = target_date == datetime.now().strftime('%Y-%m-%d')
        if not target_date or is_today:
            latest_path = os.path.join(self.data_dir, 'market_gate.json')
            try:
                with open(latest_path, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.error(f"최신 Market Gate 갱신 실패: {e}")
                
        return filepath

    def _get_usd_krw(self) -> float:
        """환율 조회 (yfinance) - 실패 시 1350(SAFE) 반환"""
        try:
            # 주말에는 환율 시장이 닫혀있으므로 기본값 반환 (불필요한 API 호출 방지)
            now = datetime.now()
            if now.weekday() >= 5:  # 토,일
                logger.debug("주말 - 환율 기본값 사용 (1350원)")
                return 1350.0
            
            # yfinance 에러 로그 임시 억제
            import logging as _logging
            yf_logger = _logging.getLogger('yfinance')
            original_level = yf_logger.level
            yf_logger.setLevel(_logging.CRITICAL)
            
            try:
                ticker = "USDKRW=X"
                data = yf.Ticker(ticker)
                hist = data.history(period="1d")
                if not hist.empty:
                    rate = hist['Close'].iloc[-1]
                    logger.info(f"현재 환율: {rate:.2f} 원")
                    return rate
            finally:
                yf_logger.setLevel(original_level)
                
            return 1350.0
        except Exception as e:
            logger.warning(f"환율 조회 실패 (기본값 사용): {e}")
            return 1350.0

    def _load_supply_data(self) -> Dict:
        """최근 수급 데이터 로드"""
        filepath = os.path.join(self.data_dir, 'all_institutional_trend_data.csv')
        if not os.path.exists(filepath):
            return {}
        
        try:
            df = pd.read_csv(filepath)
            
            if df.empty:
                logger.warning(f"수급 데이터 파일이 비어있습니다: {filepath}")
                return {}

            df = df.sort_values('date')
            latest = df.iloc[-1]
            return {
                "foreign_buy": latest.get('foreign_buy', 0),
                "inst_buy": latest.get('inst_buy', 0)
            }
        except Exception as e:
            logger.error(f"수급 데이터 로드 실패: {e}")
            return {}

    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """기술적 지표 계산"""
        close = df['close']
        
        # EMA
        df['ma20'] = close.ewm(span=self.config.kospi_ma_short, adjust=False).mean()
        df['ma60'] = close.ewm(span=self.config.kospi_ma_long, adjust=False).mean()
        
        # RSI (14)
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # MACD
        exp1 = close.ewm(span=12, adjust=False).mean()
        exp2 = close.ewm(span=26, adjust=False).mean()
        df['macd'] = exp1 - exp2
        df['signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        
        # Volume MA
        df['vol_ma20'] = df['volume'].rolling(window=20).mean()
        
        if 'change_pct' not in df.columns:
            df['change_pct'] = close.pct_change() * 100
            
        return df.fillna(0)

    def _score_trend(self, row) -> int:
        """추세 점수 (25점): 정배열"""
        if row['ma20'] > row['ma60']:
            return 25
        return 0

    def _score_rsi(self, row) -> int:
        """RSI 점수 (25점): 50-70 구간"""
        rsi = row['rsi']
        if 50 <= rsi <= 70:
            return 25
        elif rsi > 70: # 과매수
            return 10
        elif rsi < 30: # 과매도
            return 15
        return 5

    def _score_macd(self, row) -> int:
        """MACD 점수 (10점): 골든크로스"""
        if row['macd'] > row['signal']:
            return 10
        return 0

    def _score_volume(self, row) -> int:
        """거래량 점수 (10점): 20일 평균 상회"""
        if row['vol_ma20'] > 0 and row['volume'] > row['vol_ma20']:
            return 10
        return 0

    def _score_macro(self, usd_krw: float) -> Tuple[int, str]:
        """환율 점수 및 상태 (15점 + Penalty)"""
        status = "SAFE"
        score = 15
        
        if usd_krw >= self.config.usd_krw_danger:
            status = "DANGER"
            score = -20 # 페널티
        elif usd_krw >= self.config.usd_krw_warning:
            status = "WARNING"
            score = 0
            
        return score, status

    def _score_supply(self, data: Dict) -> int:
        """수급 점수 (15점)"""
        if not data:
            return 0
            
        f_buy = data.get('foreign_buy', 0)
        # i_buy = data.get('inst_buy', 0)
        
        score = 0
        if f_buy > 0:
            score += 10
        if f_buy > self.config.foreign_net_buy_threshold: # 대량 매수
            score += 5
            
        return min(score, 15)

    def _default_result(self, msg: str) -> Dict[str, Any]:
        """기본 응답"""
        return {
            "timestamp": datetime.now().isoformat(),
            "total_score": 50,
            "is_gate_open": True, 
            "gate_reason": "데이터 부족 (Default Open)",
            "status": "분석 대기 (Neutral)",
            "color": "YELLOW",
            "message": msg,
            "dataset_date": "",
            "details": {}
        }
