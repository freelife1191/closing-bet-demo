#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Collectors (데이터 수집기)
"""

from datetime import datetime, timedelta
from typing import List
import logging
import os

import pandas as pd

from engine.collectors.krx_local_data_mixin import KRXCollectorLocalDataMixin
from engine.models import StockData
from engine.ticker_utils import normalize_ticker

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_normalize_ticker = normalize_ticker

def _safe_int(value: object) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0

def _safe_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0

class KRXCollectorDataMixin(KRXCollectorLocalDataMixin):
    async def get_top_gainers(self, market: str, top_n: int, target_date: str = None) -> List[StockData]:
        """
        상승률 상위 종목 조회 (pykrx 실데이터 + 로컬 CSV Fallback)
        Args:
            market: 'KOSPI' or 'KOSDAQ'
            top_n: 조회할 종목 수
            target_date: (Optional) 특정 날짜 기준 데이터 조회 (YYYYMMDD 형식, 테스트용)
        """
        min_change_pct = float(getattr(self.config, "min_change_pct", 0.0))
        explicit_target_requested = bool(target_date)
        if target_date:
            target_date_str = self._normalize_top_gainers_target_token(target_date)
            logger.info(f"[테스트 모드] 지정 날짜 기준 조회: {target_date_str}")
        else:
            target_date_str = self._get_latest_market_date()

        # 1. pykrx 실시간 데이터 시도
        try:
            from pykrx import stock
            import pandas as pd

            logger.info(f"목표 날짜: {target_date_str}")

            cached_pykrx_results = self._load_cached_top_gainers(
                source="pykrx",
                market=market,
                top_n=top_n,
                target_date=target_date_str,
                min_change_pct=min_change_pct,
                csv_signature=None,
                stocks_signature=None,
            )
            if cached_pykrx_results is not None:
                logger.debug(
                    "KRX pykrx top gainers cache hit (market=%s, top_n=%s, target=%s)",
                    market,
                    top_n,
                    target_date_str,
                )
                return cached_pykrx_results

            df = None

            # 명시 날짜 분석은 과거 날짜로 대체하지 않는다.
            base_date = datetime.strptime(target_date_str, '%Y%m%d')
            lookback_days = 1 if explicit_target_requested else 7
            for days_ago in range(lookback_days):
                try:
                    check_date = (base_date - timedelta(days=days_ago)).strftime('%Y%m%d')
                    df = stock.get_market_ohlcv_by_ticker(check_date, market=market)
                    if not df.empty:
                        logger.info(f"pykrx 데이터 로드 성공: {check_date}")
                        break
                except Exception as e:
                    continue

            if df is not None and not df.empty:
                results = self._process_ohlcv_dataframe(df, market, top_n)
                self._save_cached_top_gainers(
                    source="pykrx",
                    market=market,
                    top_n=top_n,
                    target_date=target_date_str,
                    min_change_pct=min_change_pct,
                    csv_signature=None,
                    stocks_signature=None,
                    results=results,
                )
                return results

        except ValueError:
            logger.error("KRX 종목 데이터 변환 실패: 정상 빈 결과로 처리하지 않습니다.")
            raise
        except Exception as e:
            logger.warning(f"pykrx 실시간 데이터 수집 실패: {e}")

        # 2. Fallback: 로컬 daily_prices.csv 사용
        logger.info(f"Fallback: 로컬 daily_prices.csv 사용 ({market}) Target={target_date}")
        local_results = self._load_from_local_csv(market, top_n, target_date)
        if local_results:
            return local_results

        # 3. Fallback: 오늘/최신 거래일은 Toss 현재가로 후보를 복구한다.
        if self._should_use_toss_top_gainers_fallback(target_date_str):
            logger.info(
                "Fallback: Toss 현재가 기준 상승률 후보 복구 (%s, target=%s)",
                market,
                target_date_str,
            )
            toss_results = self._load_from_toss_prices(market, top_n)
            if toss_results:
                return toss_results

        return []

    def _should_use_toss_top_gainers_fallback(self, target_date_str: str | None) -> bool:
        """Toss 현재가 fallback 사용 가능 여부."""
        if not bool(getattr(self.config, "USE_TOSS_DATA", True)):
            return False

        target_token = self._normalize_top_gainers_target_token(target_date_str)
        if target_token == "latest":
            return True

        try:
            latest_token = self._normalize_top_gainers_target_token(self._get_latest_market_date())
        except Exception:
            latest_token = datetime.now().strftime("%Y%m%d")
        return target_token == latest_token

    def _process_ohlcv_dataframe(
        self,
        df: pd.DataFrame,
        market: str,
        top_n: int,
    ) -> List[StockData]:
        """pykrx DataFrame을 StockData 리스트로 변환."""
        working = df.copy()
        for column in ("종가", "거래대금", "등락률", "거래량", "시가총액"):
            if column in working.columns:
                working[column] = pd.to_numeric(working[column], errors="coerce")

        min_change_pct = float(getattr(getattr(self, "config", None), "min_change_pct", 0.0))
        mask_price = working["종가"].fillna(0) >= 1000
        mask_vol = working["거래대금"].fillna(0) >= 1_000_000_000
        mask_rise = working["등락률"].fillna(0) >= min_change_pct

        top_df = (
            working[mask_price & mask_vol & mask_rise]
            .nlargest(top_n, "등락률")
            .rename_axis("ticker")
            .reset_index()
        )

        results = []
        for row in top_df.itertuples(index=False):
            code = _normalize_ticker(getattr(row, "ticker", ""))
            if not code:
                logger.error("KRX 응답에 유효하지 않은 종목코드가 있습니다.")
                raise ValueError(f"유효하지 않은 티커: {getattr(row, 'ticker', '')!r}")
            try:
                name = self._get_stock_name(code)
                results.append(
                    StockData(
                        code=code,
                        name=name,
                        market=market,
                        sector=self._get_sector(code),
                        close=_safe_int(getattr(row, "종가", 0)),
                        change_pct=_safe_float(getattr(row, "등락률", 0.0)),
                        trading_value=_safe_float(getattr(row, "거래대금", 0.0)),
                        volume=_safe_int(getattr(row, "거래량", 0)),
                        marcap=_safe_int(getattr(row, "시가총액", 0)),
                        high_52w=0,
                        low_52w=0,
                    )
                )
            except Exception as error:
                logger.error(f"종목 데이터 변환 실패 ({code}): {error}")
                continue

        return results
