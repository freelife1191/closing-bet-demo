#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
스크리너 - VCP 패턴 및 수급 분석
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import logging
import os

from engine.market_gate import MarketGate
from engine.data_sources import fetch_stock_price
from engine.toss_collector import TossCollector # [NEW] Toss Collector 연동

logger = logging.getLogger(__name__)

# Base directory for data files
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@dataclass
class VCPResult:
    """VCP 패턴 감지 결과"""
    ticker: str
    name: str
    vcp_score: float
    contraction_ratio: float
    is_vcp: bool
    date: str
    entry_price: float
    pattern_desc: str = ""


@dataclass
class ScreenerResult:
    """스크리닝 결과"""
    ticker: str
    name: str
    score: float
    foreign_net_5d: int
    inst_net_5d: int
    market: str
    entry_price: float
    change_pct: float
    market_status: str = "UNKNOWN" # Market Gate Status


class SmartMoneyScreener:
    """스마트 머니 스크리너"""

    def __init__(self, target_date: str = None):
        """
        Args:
            target_date: (Optional) 특정 날짜 기준 분석 (YYYY-MM-DD 형식, 테스트용)
        """
        self.contraction_threshold = 0.7  # 70% 이하 축소 시 VCP 인정
        self.lookback_days = 60
        self.market_gate = MarketGate()
        self.toss_collector = TossCollector() # [NEW] Toss Collector 초기화
        self.target_date = target_date
        
        # Data Cache
        self.stocks_df = None
        self.prices_df = None
        self.inst_df = None

    def _load_data(self):
        """데이터 파일 로드"""
        try:
            stocks_path = os.path.join(BASE_DIR, 'data', 'korean_stocks_list.csv')
            prices_path = os.path.join(BASE_DIR, 'data', 'daily_prices.csv')
            inst_path = os.path.join(BASE_DIR, 'data', 'all_institutional_trend_data.csv')

            if os.path.exists(stocks_path):
                self.stocks_df = pd.read_csv(stocks_path)
            
            if os.path.exists(prices_path):
                self.prices_df = pd.read_csv(prices_path, dtype={'ticker': str})
                self.prices_df['date'] = pd.to_datetime(self.prices_df['date'])
                
            if os.path.exists(inst_path):
                self.inst_df = pd.read_csv(inst_path, dtype={'ticker': str})
                self.inst_df['date'] = pd.to_datetime(self.inst_df['date'])
                
        except Exception as e:
            logger.error(f"데이터 로드 실패: {e}")

    def run_screening(self, max_stocks: int = 50) -> pd.DataFrame:
        """스크리닝 실행"""
        try:
            # Load Data First
            self._load_data()
            if self.stocks_df is None or self.prices_df is None or self.inst_df is None:
                logger.error("필수 데이터 파일이 누락되었습니다.")
                return pd.DataFrame()

            # Market Gate 확인
            gate_status = self.market_gate.analyze()
            logger.info(f"=== Market Gate Status: {gate_status['status']} (Open: {gate_status['is_gate_open']}) ===")
            if not gate_status['is_gate_open']:
                logger.warning(f"⚠️ 시장 경보: {gate_status['gate_reason']} - 보수적 접근 필요")

            # [개선] 수급 우수 종목을 우선 분석하도록 사전 정렬
            # 1. 최근 5일 수급 데이터 집계
            if self.inst_df is not None and not self.inst_df.empty:
                # Target date 기준 필터링
                inst_copy = self.inst_df.copy()
                if self.target_date:
                    target_dt = pd.to_datetime(self.target_date)
                    inst_copy = inst_copy[inst_copy['date'] <= target_dt]
                
                # 티커별 최근 5일 수급 합계 계산
                inst_copy = inst_copy.sort_values('date')
                
                # 컬럼명 확인 및 fallback
                f_col = 'foreign_buy' if 'foreign_buy' in inst_copy.columns else 'foreign_net_buy'
                i_col = 'inst_buy' if 'inst_buy' in inst_copy.columns else 'inst_net_buy'
                
                if f_col in inst_copy.columns and i_col in inst_copy.columns:
                    # 티커별 최근 5일 데이터만 추출 후 합계
                    recent_supply = inst_copy.groupby('ticker').tail(5).groupby('ticker').agg({
                        f_col: 'sum',
                        i_col: 'sum'
                    }).reset_index()
                    recent_supply['total_supply'] = recent_supply[f_col] + recent_supply[i_col]
                    recent_supply = recent_supply.sort_values('total_supply', ascending=False)
                    
                    # 상위 수급 종목 순서로 stocks_df 재정렬
                    top_tickers = recent_supply['ticker'].tolist()
                    self.stocks_df['ticker'] = self.stocks_df['ticker'].astype(str).str.zfill(6)
                    
                    # 수급 순서에 맞게 정렬 (수급 데이터 없는 종목은 뒤로)
                    supply_order = {t: i for i, t in enumerate(top_tickers)}
                    self.stocks_df['supply_rank'] = self.stocks_df['ticker'].map(supply_order).fillna(999999)
                    self.stocks_df = self.stocks_df.sort_values('supply_rank')
                    
                    logger.info(f"[Screener] 수급 우선 정렬 완료: 상위 종목 {len(top_tickers)}개")

            # 결과 저장 리스트
            results = []
            
            count = 0
            for _, stock_row in self.stocks_df.iterrows():
                if count >= max_stocks: 
                    break
                    
                stock_dict = {
                    'ticker': str(stock_row['ticker']).zfill(6),
                    'name': stock_row['name'],
                    'market': stock_row.get('market', 'UNKNOWN')
                }
                
                try:
                    result = self._analyze_stock(stock_dict)
                    if result and result['score'] > 60:  # 60점 이상만 포함
                        result['market_status'] = gate_status['status']
                        results.append(result)
                        
                    count += 1
                    
                except Exception as e:
                    continue

            # DataFrame으로 변환
            df = pd.DataFrame(results)
            if not df.empty:
                df = df.sort_values('score', ascending=False)

            return df

        except Exception as e:
            logger.error(f"스크리닝 실패: {e}")
            return pd.DataFrame()

    def _analyze_stock(self, stock: Dict) -> Optional[Dict]:
        """개별 종목 분석"""
        try:
            ticker = stock['ticker']

            # 가격 데이터 필터링 (메모리상)
            # Optimize: slicing boolean index is fast enough for small datasets, but for millions of rows it might be slow.
            # Assuming daily_prices.csv isn't infinitely large.
            
            stock_prices = self.prices_df[self.prices_df['ticker'] == ticker].copy()
            if len(stock_prices) < 20: 
                return None
                
            stock_prices = stock_prices.sort_values('date')
            
            # If target_date is set, filter up to that date
            if self.target_date:
                target_dt = pd.to_datetime(self.target_date)
                stock_prices = stock_prices[stock_prices['date'] <= target_dt]
                if stock_prices.empty: return None
            else:
                # [최적화] 실시간 개별 가격 수집 로직 제거 (성능 및 일관성 저하 방지)
                # 이제 스크리너는 로드된 prices_df (CSV 기반) 데이터만 사용합니다.
                # 실시간 업데이트는 init_data.py에서 일괄(Bulk)로 수행되어야 합니다.
                pass

            # VCP 패턴 감지
            vcp_result = self._detect_vcp_pattern(stock_prices, stock)

            # 수급 점수 계산 (Foreign + Inst)
            supply_result = self._calculate_supply_score(ticker)
            supply_score_raw = supply_result['score'] # Max 70 (Foreign 40 + Inst 30)
            
            # 거래량 비율 점수 (Max 20)
            volume = stock_prices['volume']
            current_vol = volume.iloc[-1] if not volume.empty else 0
            avg_vol = volume.tail(20).mean()
            vol_ratio = current_vol / avg_vol if avg_vol > 0 else 1.0
            
            vol_score = 0
            if vol_ratio > 3.0: vol_score = 20
            elif vol_ratio > 2.0: vol_score = 15
            elif vol_ratio > 1.0: vol_score = 10
            
            # VCP 점수 (Max 10)
            # vcp_result.vcp_score is 0-100. Scale to 0-10.
            # If is_vcp is true, it means score >= 50.
            vcp_score_final = min(round(vcp_result.vcp_score / 10), 10)
            
            # Total Score = Supply(Max 70) + Vol(Max 20) + VCP(Max 10) = 100
            total_score = supply_score_raw + vol_score + vcp_score_final

            return {
                'ticker': ticker,
                'name': stock['name'],
                'score': total_score,
                'foreign_net_5d': supply_result.get('foreign_5d', 0),
                'inst_net_5d': supply_result.get('inst_5d', 0),
                'market': stock['market'],
                'entry_price': vcp_result.entry_price,
                'current_price': stock_prices.iloc[-1]['close'] if not stock_prices.empty else 0, # Added current_price
                'change_pct': 0 if len(stock_prices) == 0 else (stock_prices.iloc[-1]['close'] - stock_prices.iloc[0]['close']) / stock_prices.iloc[0]['close'] * 100,
                'market_status': 'UNKNOWN',
                'contraction_ratio': vcp_result.contraction_ratio
            }

        except Exception as e:
            # logger.warning(f"{stock['ticker']} 분석 중 에러: {e}")
            return None

    def _detect_vcp_pattern(self, df: pd.DataFrame, stock: Dict) -> VCPResult:
        """VCP 패턴 감지 (ATR & Range Contraction & Near High)"""
        try:
            if len(df) < 60: 
                return VCPResult(stock['ticker'], stock['name'], 0, 1.0, False, str(df.iloc[-1]['date']), 0, "Not enough data")

            # 1. Price Near Recent High (Constraint)
            high_60d = df['high'].tail(60).max()
            current_close = df.iloc[-1]['close']
            
            if current_close < high_60d * 0.85:
                 return VCPResult(stock['ticker'], stock['name'], 0, 1.0, False, str(df.iloc[-1]['date']), 0, "Price too low vs 60d High")

            # 2. ATR (Volatility) Check
            df = df.copy()
            df['prev_close'] = df['close'].shift(1)
            df['tr1'] = df['high'] - df['low']
            df['tr2'] = abs(df['high'] - df['prev_close'])
            df['tr3'] = abs(df['low'] - df['prev_close'])
            df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
            
            atr_20 = df['tr'].tail(20).mean()
            atr_5 = df['tr'].tail(5).mean()
            
            vol_contracting = atr_5 < atr_20
            
            # 3. Range Contraction Ratio
            daily_range = df['high'] - df['low']
            avg_range_20 = daily_range.tail(20).mean()
            recent_range_5 = daily_range.tail(5).mean()
            
            # Avoid division by zero
            contraction_ratio = recent_range_5 / avg_range_20 if avg_range_20 > 0.0001 else 1.0
            
            # 4. Volume Contraction
            volume = df['volume']
            recent_vol = volume.tail(5).mean()
            avg_vol = volume.tail(20).mean()
            vol_ratio = recent_vol / avg_vol if avg_vol > 0 else 1.0
            
            # 5. MA Alignment
            ma5 = df['close'].tail(5).mean()
            ma20 = df['close'].tail(20).mean()
            
            score = 0
            
            # A. Volatility Score
            if contraction_ratio < 0.5: score += 40
            elif contraction_ratio < 0.6: score += 30
            elif contraction_ratio < 0.7: score += 15
            
            # B. Volume Score
            if vol_ratio < 0.5: score += 30
            elif vol_ratio < 0.7: score += 20
            elif vol_ratio < 0.9: score += 10
            
            # C. MA Score
            if current_close > ma5 > ma20: score += 30
            elif current_close > ma20: score += 15
            
            is_vcp = (contraction_ratio <= 0.7) and vol_contracting and (score >= 50)
            
            entry_price = high_60d
            
            desc = []
            if not vol_contracting: desc.append("ATR Expansion")
            if contraction_ratio > 0.7: desc.append(f"Range Ratio {contraction_ratio:.2f} > 0.7")
            if score < 50: desc.append(f"Low Score {score}")
            
            pattern_desc = ", ".join(desc) if not is_vcp else "VCP Confirmed"

            return VCPResult(
                ticker=stock['ticker'],
                name=stock['name'],
                vcp_score=float(score),
                contraction_ratio=round(contraction_ratio, 2),
                is_vcp=is_vcp,
                date=df.iloc[-1]['date'].strftime('%Y-%m-%d'),
                entry_price=entry_price,
                pattern_desc=pattern_desc
            )

        except Exception as e:
            return VCPResult(stock['ticker'], stock['name'], 0, 1.0, False, "", 0)

    def _calculate_supply_score(self, ticker: str) -> Dict:
        """수급 점수 계산 (Toss API 기반)"""
        try:
            # 1. Toss API를 통해 실시간 수급 조회 (최근 5일)
            # 종목 코드는 6자리 문자열 가정
            trend_data = self.toss_collector.get_investor_trend(ticker, days=5)
            
            if not trend_data:
                # Fallback to CSV if API fails (기존 로직 유지)
                return self._calculate_supply_score_csv(ticker)

            foreign_5d = trend_data.get('foreign', 0)
            inst_5d = trend_data.get('institution', 0)
            details = trend_data.get('details', []) # 일별 상세 데이터

            score = 0
            
            # Foreign Score (Max 25)
            if foreign_5d > 50_000_000_000: score += 25  # 500억
            elif foreign_5d > 20_000_000_000: score += 15 # 200억
            elif foreign_5d > 0: score += 10
            
            # Inst Score (Max 20)
            if inst_5d > 50_000_000_000: score += 20     # 500억
            elif inst_5d > 20_000_000_000: score += 10    # 200억
            elif inst_5d > 0: score += 5
            
            # Consecutive Foreign Buying (Max 15)
            consecutive_f = 0
            if details:
                # details[0] is latest based on verification
                for d in details:
                    if d.get('netForeignerBuyVolume', 0) > 0:
                        consecutive_f += 1
                    else:
                        break
            score += min(consecutive_f * 3, 15)

            # Consecutive Inst Buying (Max 10)
            consecutive_i = 0
            if details:
                for d in details:
                    if d.get('netInstitutionBuyVolume', 0) > 0:
                        consecutive_i += 1
                    else:
                        break
            score += min(consecutive_i * 2, 10)
            
            return {
                'score': score, 
                'foreign_5d': int(foreign_5d), 
                'inst_5d': int(inst_5d)
            }
            
        except Exception as e:
            # logger.warning(f"Toss 수급 조회 실패 ({ticker}): {e}")
            return self._calculate_supply_score_csv(ticker)

    def _calculate_supply_score_csv(self, ticker: str) -> Dict:
        """수급 점수 계산 (CSV Fallback - 기존 로직 이동)"""
        try:
            if self.inst_df is None:
                return {'score': 0}
                
            ticker_inst = self.inst_df[self.inst_df['ticker'] == ticker]
            if ticker_inst.empty or len(ticker_inst) < 5:
                return {'score': 0}
            
            ticker_inst = ticker_inst.sort_values('date')
            
            # If target_date is set
            if self.target_date:
                 ticker_inst = ticker_inst[ticker_inst['date'] <= self.target_date]
            
            if len(ticker_inst) < 5: return {'score': 0}

            recent = ticker_inst.tail(5)
            
            # Data columns might vary slightly, check standard names from debug_vcp.py
            # Assuming 'foreign_buy', 'inst_buy' columns exist (net buying)
            
            # Check column existence fallback
            f_col = 'foreign_net_buy' if 'foreign_net_buy' in recent.columns else 'foreign_buy'
            i_col = 'inst_net_buy' if 'inst_net_buy' in recent.columns else 'inst_buy'
            
            if f_col not in recent.columns: f_col = 'foreign' # Try another guess if needed
            if i_col not in recent.columns: i_col = 'institutional'

            foreign_5d = recent[f_col].sum() if f_col in recent.columns else 0
            inst_5d = recent[i_col].sum() if i_col in recent.columns else 0
            
            score = 0
            
            # Foreign Score (Max 25)
            if foreign_5d > 50_000_000_000: score += 25  # 500억
            elif foreign_5d > 20_000_000_000: score += 15 # 200억
            elif foreign_5d > 0: score += 10
            
            # Inst Score (Max 20)
            if inst_5d > 50_000_000_000: score += 20     # 500억
            elif inst_5d > 20_000_000_000: score += 10    # 200억
            elif inst_5d > 0: score += 5
            
            # Consecutive Foreign Buying (Max 15)
            consecutive_f = 0
            if f_col in recent.columns:
                for val in reversed(recent[f_col].values):
                    if val > 0: consecutive_f += 1
                    else: break
            score += min(consecutive_f * 3, 15)

            # Consecutive Inst Buying (Max 10)
            consecutive_i = 0
            if i_col in recent.columns:
                for val in reversed(recent[i_col].values):
                    if val > 0: consecutive_i += 1
                    else: break
            score += min(consecutive_i * 2, 10) # 2 points per day, max 10
            
            return {
                'score': score, 
                'foreign_5d': int(foreign_5d), 
                'inst_5d': int(inst_5d)
            }
            
        except Exception as e:
            # logger.warning(f"수급 점수 계산 실패 ({ticker}): {e}")
            return {'score': 0}
    
    def generate_signals(self, results: pd.DataFrame) -> List[Dict]:
        """시그널 생성"""
        try:
            if results.empty:
                return []

            # 상위 20개 종목
            top_stocks = results.head(20)

            signals = []
            for _, row in top_stocks.iterrows():
                signal = {
                    'ticker': row['ticker'].zfill(6),
                    'name': row['name'],
                    'signal_date': self.target_date if self.target_date else datetime.now().strftime('%Y-%m-%d'),
                    'entry_price': row['entry_price'],
                    'status': 'OPEN',
                    'score': row['score'],
                    'foreign_5d': row['foreign_net_5d'],
                    'inst_5d': row['inst_net_5d'],
                    'market': row['market'],
                    'change_pct': row['change_pct'],
                    'contraction_ratio': row.get('contraction_ratio', 0)
                }
                signals.append(signal)

            return signals

        except Exception as e:
            logger.error(f"시그널 생성 실패: {e}")
            return []
