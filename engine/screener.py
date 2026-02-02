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

from engine.market_gate import MarketGate

logger = logging.getLogger(__name__)


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
        self.target_date = target_date  # 테스트용 날짜 지정

    def run_screening(self, max_stocks: int = 50) -> pd.DataFrame:
        """스크리닝 실행"""
        try:
            # Market Gate 확인
            gate_status = self.market_gate.analyze()
            logger.info(f"=== Market Gate Status: {gate_status['status']} (Open: {gate_status['is_gate_open']}) ===")
            if not gate_status['is_gate_open']:
                logger.warning(f"⚠️ 시장 경보: {gate_status['gate_reason']} - 보수적 접근 필요")

            # 종목 리스트 로드
            stock_list = self._load_stock_list()

            # 결과 저장 리스트
            results = []

            for i, stock in enumerate(stock_list[:max_stocks]):
                try:
                    result = self._analyze_stock(stock)
                    if result and result['score'] > 50:
                        result['market_status'] = gate_status['status']
                        results.append(result)
                except Exception as e:
                    logger.warning(f"{stock['ticker']} 분석 실패: {e}")
                    continue

            # DataFrame으로 변환
            df = pd.DataFrame(results)
            if not df.empty:
                df = df.sort_values('score', ascending=False)

            return df

        except Exception as e:
            logger.error(f"스크리닝 실패: {e}")
            return pd.DataFrame()

    def _load_stock_list(self) -> List[Dict]:
        """종목 리스트 로드"""
        try:
            # 실제로는 pykrx에서 로드
            # 여기서는 샘플 데이터 반환
            return [
                {'ticker': '005930', 'name': '삼성전자', 'market': 'KOSPI'},
                {'ticker': '000270', 'name': '기아', 'market': 'KOSPI'},
                {'ticker': '035420', 'name': 'NAVER', 'market': 'KOSPI'},
                {'ticker': '005380', 'name': '현대차', 'market': 'KOSPI'},
                {'ticker': '068270', 'name': '셀트리온', 'market': 'KOSDAQ'},
            ]
        except Exception as e:
            logger.error(f"종목 리스트 로드 실패: {e}")
            return []

    def _analyze_stock(self, stock: Dict) -> Optional[Dict]:
        """개별 종목 분석"""
        try:
            ticker = stock['ticker']

            # 가격 데이터 로드
            price_data = self._load_price_data(ticker)
            if price_data is None or len(price_data) < 60:
                return None

            # VCP 패턴 감지
            vcp_result = self._detect_vcp_pattern(price_data, stock)

            # 수급 점수 계산
            supply_score = self._calculate_supply_score(ticker)

            # 종합 점수
            total_score = vcp_result.vcp_score * 0.4 + supply_score * 0.6

            return {
                'ticker': ticker,
                'name': stock['name'],
                'score': total_score,
                'foreign_net_5d': supply_score,
                'inst_net_5d': int(supply_score * 0.5),
                'market': stock['market'],
                'entry_price': vcp_result.entry_price,
                'change_pct': (vcp_result.entry_price / price_data.iloc[-60]['close'] - 1) * 100,
                'market_status': 'UNKNOWN' # Will be updated in run_screening
            }

        except Exception as e:
            logger.warning(f"{stock['ticker']} 분석 중 에러: {e}")
            return None

    def _load_price_data(self, ticker: str) -> Optional[pd.DataFrame]:
        """가격 데이터 로드"""
        try:
            # 실제로는 CSV나 pykrx에서 로드
            # 여기서는 샘플 데이터 반환
            dates = pd.date_range(end=datetime.now(), periods=60, freq='D')

            # 랜덤 시계열 데이터 생성
            base_price = np.random.randint(50000, 150000)
            returns = np.random.normal(0.001, 0.02, 60)
            prices = base_price * (1 + returns).cumprod()

            # 고가/저가/시가/종가 생성
            df = pd.DataFrame({
                'date': dates,
                'open': prices * np.random.uniform(0.98, 1.0, 60),
                'high': prices * np.random.uniform(1.0, 1.05, 60),
                'low': prices * np.random.uniform(0.95, 1.0, 60),
                'close': prices,
                'volume': np.random.randint(100000, 10000000, 60)
            })

            return df

        except Exception as e:
            logger.error(f"가격 데이터 로드 실패 ({ticker}): {e}")
            return None

    def _detect_vcp_pattern(self, df: pd.DataFrame, stock: Dict) -> VCPResult:
        """VCP 패턴 감지"""
        try:
            # ATR 계산
            high = df['high'].values
            low = df['low'].values
            close = df['close'].values

            tr = np.maximum(high - low,
                          np.maximum(np.abs(high - np.roll(close, 1)),
                                    np.abs(low - np.roll(close, 1))))
            atr = pd.Series(tr).rolling(14).mean()

            # 최근 30일 ATR 변화
            recent_atr = atr.iloc[-30:]
            atr_contraction = (recent_atr.iloc[-1] / recent_atr.iloc[0]) if recent_atr.iloc[0] > 0 else 1.0

            # 고가-저가 범위 축소 비율
            recent_high = high[-30:].max()
            recent_low = low[-30:].min()
            price_range = (recent_high - recent_low) / recent_low
            avg_range = (high[:-30].max() - low[:-30].min()) / low[:-30].min()
            range_contraction = price_range / avg_range if avg_range > 0 else 1.0

            # 현재가가 고점 근처인지 확인 (92% 이상)
            current_price = close[-1]
            recent_high_price = close[-30:].max()
            price_near_high = current_price >= recent_high_price * 0.92
            
            # 상승 추세 확인 (시작가 대비 98% 이상)
            price_start = close[-30]
            is_uptrend = current_price > price_start * 0.98

            # BLUEPRINT VCP 점수 계산 (0-20점)
            vcp_score = 0.0
            
            # 축소 비율이 낮을수록 고점수
            if range_contraction <= 0.3:
                vcp_score += 10.0
            elif range_contraction <= 0.5:
                vcp_score += 7.0
            elif range_contraction <= 0.7:
                vcp_score += 4.0
            
            # 고점 근처 보너스
            if price_near_high:
                vcp_score += 5.0
            
            # 상승 추세 보너스
            if is_uptrend:
                vcp_score += 5.0

            entry_price = current_price
            is_vcp = vcp_score > 10  # 10점 이상이면 VCP 인정

            return VCPResult(
                ticker=stock['ticker'],
                name=stock['name'],
                vcp_score=vcp_score,
                contraction_ratio=range_contraction,
                is_vcp=is_vcp,
                date=self.target_date if self.target_date else datetime.now().strftime('%Y-%m-%d'),
                entry_price=entry_price
            )

        except Exception as e:
            logger.error(f"VCP 패턴 감지 실패: {e}")
            return VCPResult(
                ticker=stock['ticker'],
                name=stock['name'],
                vcp_score=0,
                contraction_ratio=1.0,
                is_vcp=False,
                date=datetime.now().strftime('%Y-%m-%d'),
                entry_price=0
            )

    def _calculate_supply_score(self, ticker: str) -> float:
        """수급 점수 계산 (0-100)"""
        try:
            # 실제로는 CSV에서 로드
            # 여기서는 랜덤 점수 반환
            import random
            return random.uniform(30, 90)
        except Exception as e:
            logger.warning(f"수급 점수 계산 실패 ({ticker}): {e}")
            return 50.0

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
                    'change_pct': row['change_pct']
                }
                signals.append(signal)

            return signals

        except Exception as e:
            logger.error(f"시그널 생성 실패: {e}")
            return []
