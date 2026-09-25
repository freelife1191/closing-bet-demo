#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
스크리너 - VCP 패턴 및 수급 분석
"""
import pandas as pd
from typing import Iterator, List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime
import logging
import os

from engine.market_gate import MarketGate
from engine.pandas_utils_safe import safe_bool
from engine.screening_runtime import resolve_vcp_signals_to_show
from engine.toss_collector import TossCollector # [NEW] Toss Collector 연동
from engine.screener_data_loader import (
    load_inst_frame,
    load_prices_frame,
    load_stocks_frame,
)
from engine.screener_scoring_helpers import (
    MISSING_SUPPLY,
    build_ticker_index,
    calculate_volume_score,
    scale_vcp_score,
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
    calculate_supply_score_with_toss as calculate_supply_score_with_toss_impl,
)
from services.investor_trend_5day_service import (
    get_investor_trend_5day_for_ticker,
    get_investor_trends_5day_for_tickers,
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
            self._data_mtimes = new_mtimes

        except Exception as e:
            logger.error(f"데이터 로드 실패: {e}")

    def run_screening(self, max_stocks: int = 50) -> pd.DataFrame:
        """스크리닝 실행. 빈 프레임은 「조건 충족 종목 없음」만 뜻하고, 실패는 예외로 올린다([VCP-049]).

        호출자(create_signals_log)는 빈 결과를 받으면 그 날짜의 기존 시그널을 지운다. 실패를 빈 결과로
        돌려주면 저장된 시그널이 사라지므로, 예외를 올려 [VCP-028] 의 보존 갈래로 보낸다.
        """
        try:
            # Load Data First
            self._load_data()
            # 파일이 없으면 로더는 None 이 아니라 빈 프레임을 준다. 수급은 없어도 분석한다
            if any(frame is None or frame.empty for frame in (self.stocks_df, self.prices_df)) or self.inst_df is None:
                raise RuntimeError("필수 데이터(종목 목록·일별 가격)가 없거나 비어 있습니다.")

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

            # 결과 저장 리스트. 저장 조건은 VCP 패턴 통과뿐이고 합산 점수는 정렬에만 쓴다([VCP-032]).
            # 종전에는 score >= VCP_MIN_SCORE(60) 도 요구했는데, 수급(최대 70)+거래량(최대 20)+VCP(최대 10)
            # 구성에서 패턴 통과 종목이 그 문턱을 넘는 일이 실측 40거래일 동안 한 번도 없어 시그널이 늘 0건이었다.
            results = []

            candidates = [build_stock_candidate(row) for row in prioritized_stocks.head(max(0, max_stocks)).itertuples(index=False)]
            analyzed = 0
            for result in self._analyze_candidates(candidates):
                if not result:
                    continue
                analyzed += 1
                if not safe_bool(result.get("is_vcp", False)):
                    continue
                result['market_status'] = gate_status['status']
                results.append(result)
            # 전 종목이 분석 전에 빠졌으면(가격 20행 미만, VCP 판정 예외) 0건이 아니라 실패다([VCP-053])
            if candidates and analyzed == 0:
                raise RuntimeError(f"분석 가능한 종목이 없습니다 (후보 {len(candidates)}개 모두 가격 부족 또는 분석 오류).")

            # DataFrame으로 변환
            df = pd.DataFrame(results)
            if not df.empty:
                df = df.sort_values('score', ascending=False)

            return df

        except Exception as e:
            logger.error(f"스크리닝 실패: {e}")
            raise

    def _analyze_candidates(self, candidates: List[Dict]) -> Iterator[Optional[Dict]]:
        if not getattr(self, "_target_datetime", None) or not self._should_use_csv_supply_for_target_date():
            for stock in candidates:
                try:
                    yield self._analyze_stock(stock)
                except Exception as error:
                    logger.debug("종목 분석 스킵 %s: %s", stock.get("ticker"), error, exc_info=True)
            return
        from engine.ticker_utils import normalize_ticker
        for offset in range(0, len(candidates), 4):
            prepared = [self._prepare_stock_analysis(stock) for stock in candidates[offset:offset + 4]]
            prepared = [item for item in prepared if item is not None]
            if not prepared:
                continue
            trends = get_investor_trends_5day_for_tickers(
                tickers=[item[0]["ticker"] for item in prepared], data_dir=os.path.join(BASE_DIR, "data"),
                target_datetime=self._target_datetime,
            )
            for item in prepared:
                try:
                    trend = trends.get(normalize_ticker(item[0]["ticker"]))
                    supply = score_supply_from_toss_trend(trend) if trend else dict(MISSING_SUPPLY)
                    yield self._finish_stock_analysis(item, supply)
                except Exception as error:
                    logger.debug("종목 분석 스킵 %s: %s", item[0].get("ticker"), error, exc_info=True)

    def _prepare_stock_analysis(self, stock: Dict) -> tuple[Dict, pd.DataFrame, VCPResult] | None:
        try:
            price_index = self._prices_by_ticker_target if self._target_datetime is not None else self._prices_by_ticker
            stock_prices = price_index.get(stock['ticker'])
            # 네 값(high·low·close·volume)이 모두 숫자인 행만 센다. 원래 행 수로 세면 값이 빈 프레임이
            # 「무효 프레임」 결과로 분석 수에 들어가 전 종목 결함이 「시그널 없음」이 된다([VCP-056])
            # 문턱은 판정의 최소 행 수와 같아야 부족분이 「Insufficient data」 결과로 분석 수에 들어가지 않는다
            from engine.constants import VCP_THRESHOLDS
            from engine.vcp import _normalize_price_frame
            if stock_prices is None or len(_normalize_price_frame(stock_prices)) < VCP_THRESHOLDS.MIN_DATA_POINTS:
                return None
            return stock, stock_prices, self._detect_vcp_pattern(stock_prices, stock)
        except Exception as error:
            logger.debug("종목 준비 실패 %s: %s", stock.get("ticker"), error, exc_info=True)
            return None

    def _analyze_stock(self, stock: Dict) -> Optional[Dict]:
        try:
            prepared = self._prepare_stock_analysis(stock)
            if prepared is None:
                return None
            return self._finish_stock_analysis(prepared, self._calculate_supply_score(stock['ticker']))
        except Exception as error:
            logger.debug("종목 분석 실패 %s: %s", stock.get("ticker"), error, exc_info=True)
            return None

    def _finish_stock_analysis(self, prepared: tuple[Dict, pd.DataFrame, VCPResult], supply_result: Dict) -> Dict:
        stock, stock_prices, vcp_result = prepared
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
            is_vcp=vcp_result.is_vcp,
            first_close=first_close,
            last_close=last_close,
        )

    def _detect_vcp_pattern(self, df: pd.DataFrame, stock: Dict) -> VCPResult:
        """VCP 패턴 감지 (Shared Logic). 예외는 호출자가 그 종목을 분석 불가로 센다([VCP-053])"""
        from engine.vcp import detect_vcp_pattern
        return detect_vcp_pattern(df, stock['ticker'], stock['name'])

    def _calculate_supply_score(self, ticker: str) -> Dict:
        """수급 점수 계산 (Toss API 기반)"""
        if self._should_use_csv_supply_for_target_date():
            return self._calculate_supply_score_csv(ticker)
        return calculate_supply_score_with_toss_impl(
            ticker=ticker,
            toss_collector=self.toss_collector,
            fallback_fn=self._calculate_supply_score_csv,
            score_supply_from_toss_trend_fn=score_supply_from_toss_trend,
            cache_data_dir=os.path.join(BASE_DIR, "data"),
        )

    def _should_use_csv_supply_for_target_date(self) -> bool:
        """과거 target_date 분석은 CSV 5일 수급만 사용한다."""
        if self._target_datetime is None:
            return False

        try:
            return self._target_datetime.date() < datetime.now().date()
        except Exception:
            return False

    def _calculate_supply_score_csv(self, ticker: str) -> Dict:
        """수급 점수 계산 (CSV Fallback - 단일 5일 합산 서비스 사용).

        verify=False 로 먼저 부르는 방식은 CSV 에 5거래일이 모이지 않은 종목을 놓쳤다.
        그때 반환값이 None 이라 이상징후 판정이 False 가 되고, 참조로 채울 수 있는
        종목에 점수 0 이 매겨졌다.

        대신 CSV 에 5거래일이 모이지 않은 종목마다 pykrx 왕복이 붙는다. 자료가 정상이면
        해당 종목이 없어 비용이 0 이다(2026-09-04 최신 날짜 기준 1997 종목 가운데 0 개).
        반대로 CSV 시작일 부근을 target_date 로 주면 전 종목이 해당한다. 그 경로는 수동
        CLI(`init_data.py vcp-signal <날짜>`) 뿐이고 예전에는 그 자리에서 전 종목이
        0 점이었다. [FLOW-025] 부터는 최근 5거래일 중 하루라도 행이 없는 종목도 CSV 에서
        빠지므로 정상 자료에서도 비용이 0 이 아니다(2026-09-21 로컬 파일 기준 2,002종목 중
        약 100개).

        이미 이상징후 플래그가 붙던 종목은 여기에 들지 않는다. 예전 방식도 둘째 호출로
        참조를 받아 왔으므로 비용이 같다.
        """
        trend_data = get_investor_trend_5day_for_ticker(
            ticker=ticker,
            data_dir=os.path.join(BASE_DIR, "data"),
            target_datetime=self._target_datetime,
            verify_with_references=True,
        )
        if not trend_data:
            return dict(MISSING_SUPPLY)
        return score_supply_from_toss_trend(
            {
                "foreign": trend_data.get("foreign", 0),
                "institution": trend_data.get("institution", 0),
                "details": trend_data.get("details", []),
            }
        )

    def generate_signals(self, results: pd.DataFrame) -> List[Dict]:
        """시그널 생성"""
        try:
            if results.empty:
                return []

            top_limit = resolve_vcp_signals_to_show(default=20, minimum=0)
            top_stocks = results.head(top_limit)

            signals = []
            for row in top_stocks.itertuples(index=False):
                signals.append(build_signal_item(row, self.target_date))

            return signals

        except Exception as e:
            logger.error(f"시그널 생성 실패: {e}")
            return []
