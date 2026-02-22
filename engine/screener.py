#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
스크리너 - VCP 패턴 및 수급 분석
"""
import pandas as pd
from typing import List, Dict, Optional
from dataclasses import dataclass
import logging
import os

from engine.market_gate import MarketGate
from engine.toss_collector import TossCollector # [NEW] Toss Collector 연동
from engine.screener_data_loader import (
    load_inst_frame,
    load_prices_frame,
    load_stocks_frame,
)
from engine.screener_scoring_helpers import (
    build_ticker_index,
    calculate_volume_score,
    scale_vcp_score,
    score_supply_from_csv,
    score_supply_from_toss_trend,
)
from engine.screener_runtime_helpers import (
    build_stock_candidate,
    prioritize_stocks_by_supply,
)
from engine.screener_result_builders import (
    build_screening_result,
    build_signal_item,
)
from engine.screener_supply_helpers import (
    calculate_supply_score_from_csv as calculate_supply_score_from_csv_impl,
    calculate_supply_score_with_toss as calculate_supply_score_with_toss_impl,
)

logger = logging.getLogger(__name__)

# Base directory for data files
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _file_signature(path: str) -> tuple[int, int] | None:
    try:
        stat = os.stat(path)
    except OSError:
        return None
    return int(stat.st_mtime_ns), int(stat.st_size)


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
    foreign_net_1d: int = 0
    inst_net_1d: int = 0


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
        try:
            self._target_datetime = pd.to_datetime(target_date) if target_date else None
        except Exception:
            self._target_datetime = None
        
        # Data Cache
        self.stocks_df = None
        self.prices_df = None
        self.inst_df = None
        self._prices_by_ticker: dict[str, pd.DataFrame] = {}
        self._prices_by_ticker_target: dict[str, pd.DataFrame] = {}
        self._inst_by_ticker: dict[str, pd.DataFrame] = {}
        self._data_mtimes: dict[str, tuple[int, int]] = {}

    @staticmethod
    def _build_ticker_index(df: pd.DataFrame | None) -> dict[str, pd.DataFrame]:
        """ticker별 시계열 인덱스를 생성한다."""
        return build_ticker_index(df)

    def _load_stocks_frame(self, stocks_path: str) -> pd.DataFrame:
        return load_stocks_frame(
            stocks_path,
            read_csv=pd.read_csv,
            logger=logger,
        )

    def _load_prices_frame(self, prices_path: str) -> pd.DataFrame:
        return load_prices_frame(
            prices_path,
            read_csv=pd.read_csv,
            logger=logger,
        )

    def _load_inst_frame(self, inst_path: str) -> pd.DataFrame:
        return load_inst_frame(
            inst_path,
            read_csv=pd.read_csv,
            logger=logger,
        )

    def _load_data(self):
        """데이터 파일 로드 (누락 시 자동 생성)"""
        stocks_path = os.path.join(BASE_DIR, 'data', 'korean_stocks_list.csv')
        prices_path = os.path.join(BASE_DIR, 'data', 'daily_prices.csv')
        inst_path = os.path.join(BASE_DIR, 'data', 'all_institutional_trend_data.csv')
        has_inst_file = os.path.exists(inst_path)

        # 1. Check & Generate Stocks List
        if not os.path.exists(stocks_path):
            logger.warning(" Stocks list missing. Attempting to generate...")
            try:
                from scripts.init_data import create_korean_stocks_list
                create_korean_stocks_list()
            except Exception as e:
                logger.error(f"Failed to generate stocks list: {e}")

        # 2. Check & Generate Daily Prices
        if not os.path.exists(prices_path):
            logger.warning(" Daily prices missing. Attempting to generate...")
            try:
                from scripts.init_data import create_daily_prices
                # 기본 90일치 데이터 생성
                create_daily_prices(lookback_days=90)
            except Exception as e:
                logger.error(f"Failed to generate daily prices: {e}")

        # 3. Load Data
        try:
            new_mtimes = {}
            for path in (stocks_path, prices_path, inst_path):
                signature = _file_signature(path)
                if signature is not None:
                    new_mtimes[path] = signature

            all_loaded = (
                self.stocks_df is not None
                and self.prices_df is not None
                and (self.inst_df is not None or not has_inst_file)
            )
            if all_loaded and new_mtimes == self._data_mtimes:
                return

            self.stocks_df = self._load_stocks_frame(stocks_path)
            self.prices_df = self._load_prices_frame(prices_path)
            self.inst_df = self._load_inst_frame(inst_path)

            self._prices_by_ticker = self._build_ticker_index(self.prices_df)
            if self._target_datetime is not None:
                target_prices_df = self.prices_df
                if isinstance(target_prices_df, pd.DataFrame) and not target_prices_df.empty and "date" in target_prices_df.columns:
                    target_prices_df = target_prices_df[target_prices_df["date"] <= self._target_datetime]
                self._prices_by_ticker_target = self._build_ticker_index(target_prices_df)
            else:
                self._prices_by_ticker_target = self._prices_by_ticker
            self._inst_by_ticker = self._build_ticker_index(self.inst_df)
            self._data_mtimes = new_mtimes
                
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
            prioritized_stocks = prioritize_stocks_by_supply(
                stocks_df=self.stocks_df,
                inst_df=self.inst_df,
                target_date=self.target_date,
                logger=logger,
            )

            # 결과 저장 리스트
            results = []
            
            count = 0
            for stock_row in prioritized_stocks.itertuples(index=False):
                if count >= max_stocks: 
                    break
                    
                stock_dict = build_stock_candidate(stock_row)
                
                try:
                    result = self._analyze_stock(stock_dict)
                    if result and result['score'] > 60:  # 60점 이상만 포함
                        result['market_status'] = gate_status['status']
                        results.append(result)
                        
                    count += 1
                    
                except Exception as e:
                    logger.debug(
                        "종목 분석 스킵 ticker=%s: %s",
                        stock_dict.get("ticker"),
                        e,
                        exc_info=True,
                    )
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
            price_index = self._prices_by_ticker_target if self._target_datetime is not None else self._prices_by_ticker
            stock_prices = price_index.get(ticker)
            if stock_prices is None or len(stock_prices) < 20:
                return None

            # VCP 패턴 감지
            vcp_result = self._detect_vcp_pattern(stock_prices, stock)

            # 수급 점수 계산 (Foreign + Inst)
            supply_result = self._calculate_supply_score(ticker)
            supply_score_raw = supply_result['score'] # Max 70 (Foreign 40 + Inst 30)
            
            # 거래량 비율 점수 (Max 20)
            volume = stock_prices['volume']
            vol_score, _vol_ratio = calculate_volume_score(volume)
            
            # VCP 점수 (Max 10)
            # vcp_result.vcp_score is 0-100. Scale to 0-10.
            # If is_vcp is true, it means score >= 50.
            vcp_score_final = scale_vcp_score(vcp_result.vcp_score)
            
            # Total Score = Supply(Max 70) + Vol(Max 20) + VCP(Max 10) = 100
            total_score = supply_score_raw + vol_score + vcp_score_final

            first_close = float(stock_prices.iloc[0]["close"]) if len(stock_prices) > 0 else 0.0
            last_close = float(stock_prices.iloc[-1]["close"]) if len(stock_prices) > 0 else 0.0
            return build_screening_result(
                stock=stock,
                total_score=total_score,
                supply_result=supply_result,
                entry_price=vcp_result.entry_price,
                contraction_ratio=vcp_result.contraction_ratio,
                vcp_score=vcp_score_final,
                first_close=first_close,
                last_close=last_close,
            )

        except Exception as e:
            logger.debug(
                "%s 분석 중 에러: %s",
                stock.get("ticker", "unknown"),
                e,
                exc_info=True,
            )
            return None

    def _detect_vcp_pattern(self, df: pd.DataFrame, stock: Dict) -> VCPResult:
        """VCP 패턴 감지 (Shared Logic)"""
        try:
            from engine.vcp import detect_vcp_pattern
            return detect_vcp_pattern(df, stock['ticker'], stock['name'])
        except Exception as e:
            return VCPResult(stock['ticker'], stock['name'], 0, 1.0, False, str(df.iloc[-1]['date']) if not df.empty else "", 0, f"Error: {e}")

    def _calculate_supply_score(self, ticker: str) -> Dict:
        """수급 점수 계산 (Toss API 기반)"""
        return calculate_supply_score_with_toss_impl(
            ticker=ticker,
            toss_collector=self.toss_collector,
            fallback_fn=self._calculate_supply_score_csv,
            score_supply_from_toss_trend_fn=score_supply_from_toss_trend,
        )

    def _calculate_supply_score_csv(self, ticker: str) -> Dict:
        """수급 점수 계산 (CSV Fallback - 기존 로직 이동)"""
        return calculate_supply_score_from_csv_impl(
            ticker=ticker,
            inst_by_ticker=self._inst_by_ticker,
            target_datetime=self._target_datetime,
            score_supply_from_csv_fn=score_supply_from_csv,
        )
    
    def generate_signals(self, results: pd.DataFrame) -> List[Dict]:
        """시그널 생성"""
        try:
            if results.empty:
                return []

            # 상위 20개 종목
            top_stocks = results.head(20)

            signals = []
            for row in top_stocks.itertuples(index=False):
                signals.append(build_signal_item(row, self.target_date))

            return signals

        except Exception as e:
            logger.error(f"시그널 생성 실패: {e}")
            return []
