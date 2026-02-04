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

            # 결과 저장 리스트
            results = []
            
            # Analyze stocks
            # If max_stocks is small, we might just be testing, but for production we iterate all
            # Here we iterate stocks_df
            
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
                    if result and result['score'] > 50:
                        result['market_status'] = gate_status['status']
                        results.append(result)
                        
                    count += 1 # Only count actual analyzed stocks (or should we count attempts? Logic kept simple)
                    
                except Exception as e:
                    # logger.warning(f"{stock_dict['ticker']} 분석 실패: {e}")
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

            # VCP 패턴 감지
            vcp_result = self._detect_vcp_pattern(stock_prices, stock)

            # 수급 점수 계산
            supply_result = self._calculate_supply_score(ticker)
            supply_score = supply_result['score']
            
            # 종합 점수
            total_score = vcp_result.vcp_score * 0.6 + supply_score * 0.4

            return {
                'ticker': ticker,
                'name': stock['name'],
                'score': total_score,
                'foreign_net_5d': supply_result.get('foreign_5d', 0),
                'inst_net_5d': supply_result.get('inst_5d', 0),
                'market': stock['market'],
                'entry_price': vcp_result.entry_price,
                'change_pct': 0 if len(stock_prices) == 0 else (stock_prices.iloc[-1]['close'] - stock_prices.iloc[0]['close']) / stock_prices.iloc[0]['close'] * 100,
                'market_status': 'UNKNOWN',
                'contraction_ratio': vcp_result.contraction_ratio
            }

        except Exception as e:
            # logger.warning(f"{stock['ticker']} 분석 중 에러: {e}")
            return None

    def _detect_vcp_pattern(self, df: pd.DataFrame, stock: Dict) -> VCPResult:
        """VCP 패턴 감지 (Real Logic)"""
        try:
            if len(df) < 20:
                return VCPResult(stock['ticker'], stock['name'], 0, 1.0, False, "", 0)

            # Volatility Contraction
            # Range = High - Low
            high = df['high']
            low = df['low']
            close = df['close']
            
            daily_range = high - low
            
            recent_range = daily_range.tail(5).mean()
            avg_range = daily_range.tail(20).mean()
            
            contraction_ratio = recent_range / avg_range if avg_range > 0 else 1.0
            
            # Volume Contraction
            volume = df['volume']
            recent_vol = volume.tail(5).mean()
            avg_vol = volume.tail(20).mean()
            vol_ratio = recent_vol / avg_vol if avg_vol > 0 else 1.0
            
            # MA Alignment
            ma5 = close.tail(5).mean()
            ma20 = close.tail(20).mean()
            current_price = close.iloc[-1]
            
            score = 0
            
            # 1. Volatility Score (Max 40)
            if contraction_ratio < 0.5: score += 40
            elif contraction_ratio < 0.7: score += 30
            elif contraction_ratio < 0.9: score += 15
            
            # 2. Volume Score (Max 30)
            if vol_ratio < 0.5: score += 30
            elif vol_ratio < 0.7: score += 20
            elif vol_ratio < 0.9: score += 10
            
            # 3. MA Score (Max 30)
            if current_price > ma5 > ma20: score += 30
            elif current_price > ma20: score += 15
            
            is_vcp = score >= 50 # Threshold
            
            return VCPResult(
                ticker=stock['ticker'],
                name=stock['name'],
                vcp_score=float(score),
                contraction_ratio=round(contraction_ratio, 2),
                is_vcp=is_vcp,
                date=df.iloc[-1]['date'].strftime('%Y-%m-%d'),
                entry_price=current_price
            )

        except Exception as e:
            return VCPResult(stock['ticker'], stock['name'], 0, 1.0, False, "", 0)

    def _calculate_supply_score(self, ticker: str) -> Dict:
        """수급 점수 계산 (0-100)"""
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
            
            # Foreign Score
            if foreign_5d > 1_000_000_000: score += 40
            elif foreign_5d > 500_000_000: score += 25
            elif foreign_5d > 0: score += 10
            
            # Inst Score
            if inst_5d > 500_000_000: score += 30
            elif inst_5d > 200_000_000: score += 20
            elif inst_5d > 0: score += 10
            
            # Consecutive Foreign Buying
            consecutive = 0
            if f_col in recent.columns:
                for val in reversed(recent[f_col].values):
                    if val > 0: consecutive += 1
                    else: break
            score += min(consecutive * 6, 30)
            
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
