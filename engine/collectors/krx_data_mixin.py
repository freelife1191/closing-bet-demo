#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KRX Collector 데이터 수집 믹스인.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import List

import pandas as pd

from engine.collectors.krx_local_data_mixin import KRXCollectorLocalDataMixin
from engine.models import StockData


logger = logging.getLogger(__name__)


def _normalize_ticker(ticker: object) -> str:
    return str(ticker).zfill(6)


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
    """KRXCollector의 상승종목 조회 메서드를 제공하는 믹스인."""

    async def get_top_gainers(
        self,
        market: str,
        top_n: int,
        target_date: str = None,
    ) -> List[StockData]:
        """상승률 상위 종목 조회 (pykrx 실데이터 + 로컬 CSV Fallback)."""
        try:
            from pykrx import stock

            if target_date:
                target_date_str = target_date
                logger.info(f"지정 날짜 기준 조회: {target_date_str}")
            else:
                target_date_str = self._get_latest_market_date()

            logger.info(f"목표 날짜: {target_date_str}")

            df = None
            base_date = datetime.strptime(target_date_str, "%Y%m%d")
            for days_ago in range(7):
                try:
                    check_date = (base_date - timedelta(days=days_ago)).strftime("%Y%m%d")
                    df = stock.get_market_ohlcv_by_ticker(check_date, market=market)
                    if not df.empty:
                        logger.info(f"pykrx 데이터 로드 성공: {check_date}")
                        break
                except Exception:
                    continue

            if df is not None and not df.empty:
                return self._process_ohlcv_dataframe(df, market, top_n)

        except ImportError:
            logger.warning("pykrx 미설치 - CSV fallback 사용")
        except Exception as error:
            logger.warning(f"pykrx 실시간 데이터 수집 실패: {error}")

        logger.info(f"Fallback: 로컬 daily_prices.csv 사용 ({market}) Target={target_date}")
        return self._load_from_local_csv(market, top_n, target_date)

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

        mask_price = working["종가"].fillna(0) >= 1000
        mask_vol = working["거래대금"].fillna(0) >= 1_000_000_000
        mask_rise = working["등락률"].fillna(0) > 0

        top_df = (
            working[mask_price & mask_vol & mask_rise]
            .nlargest(top_n, "등락률")
            .reset_index()
            .rename(columns={"index": "ticker"})
        )

        results = []
        for row in top_df.itertuples(index=False):
            code = _normalize_ticker(getattr(row, "ticker", ""))
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
