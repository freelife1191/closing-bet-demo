#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Market Gate Local Fetchers
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict

import pandas as pd

from services.kr_market_data_cache_service import load_csv_file

def _load_cached_csv_frame(
    *,
    data_dir: str,
    filename: str,
    usecols: list[str],
    logger: logging.Logger,
) -> pd.DataFrame:
    """공용 CSV 캐시(메모리 + SQLite 스냅샷)를 우선 사용해 로드한다."""
    filepath = os.path.join(data_dir, filename)
    if not os.path.exists(filepath):
        return pd.DataFrame()

    try:
        return load_csv_file(
            data_dir,
            filename,
            deep_copy=False,
            usecols=usecols,
        )
    except Exception as error:
        logger.debug(f"CSV 컬럼 제한 로드 실패({filename}): {error}")

    try:
        fallback = load_csv_file(
            data_dir,
            filename,
            deep_copy=False,
        )
    except Exception as error:
        logger.warning(f"CSV fallback 로드 실패({filename}): {error}")
        return pd.DataFrame()

    if fallback.empty:
        return fallback

    existing_columns = [column for column in usecols if column in fallback.columns]
    if not existing_columns:
        return pd.DataFrame()
    return fallback[existing_columns].copy()


def load_price_data(
    *,
    data_dir: str,
    kodex_ticker: str,
    target_date: str | None,
    logger: logging.Logger,
) -> pd.DataFrame:
    """KODEX 200 데이터 로드 및 날짜 필터링 (Fallback: pykrx)."""
    df = pd.DataFrame()
    filepath = os.path.join(data_dir, "daily_prices.csv")

    if os.path.exists(filepath):
        try:
            usecols = ["date", "ticker", "close", "volume", "change_pct"]
            temp_df = _load_cached_csv_frame(
                data_dir=data_dir,
                filename="daily_prices.csv",
                usecols=usecols,
                logger=logger,
            )
            if not temp_df.empty:
                temp_df["ticker"] = temp_df["ticker"].astype(str).str.zfill(6)
                df = temp_df[temp_df["ticker"] == kodex_ticker].copy()
                if not df.empty:
                    df = df.sort_values("date")
        except Exception as error:
            logger.error(f"CSV 로드 실패: {error}")

    if df.empty:
        logger.debug("CSV에 KODEX 200 데이터 없음. pykrx 조회 시도...")
        try:
            from pykrx import stock

            today = datetime.now().strftime("%Y%m%d")
            start = (datetime.now() - timedelta(days=120)).strftime("%Y%m%d")
            pdf = stock.get_market_ohlcv_by_date(start, today, kodex_ticker)

            if not pdf.empty:
                pdf = pdf.reset_index()
                rename_map = {
                    "날짜": "date",
                    "시가": "open",
                    "고가": "high",
                    "저가": "low",
                    "종가": "close",
                    "거래량": "volume",
                    "거래대금": "trading_value",
                    "등락률": "change_pct",
                }
                pdf.rename(columns=rename_map, inplace=True)
                pdf["date"] = pdf["date"].dt.strftime("%Y-%m-%d")
                pdf["ticker"] = kodex_ticker

                req_cols = ["date", "ticker", "close"]
                if all(c in pdf.columns for c in req_cols):
                    df = pdf
                    logger.debug(f"pykrx를 통해 KODEX 200 데이터 확보 ({len(df)} rows)")
        except Exception as error:
            logger.error(f"pykrx Fallback 실패: {error}")

    if df.empty:
        return pd.DataFrame()

    if target_date:
        df = df[df["date"] <= target_date]
        if df.empty:
            logger.warning(f"{target_date} 이전 데이터가 없습니다.")
            return pd.DataFrame()

    return df


def load_supply_data(*, data_dir: str, kis: Any, logger: logging.Logger) -> Dict:
    """최근 수급 데이터 로드 (실시간 KIS 지원)."""
    if kis and os.getenv("KIS_APP_KEY"):
        try:
            kis_data = kis.get_market_investor_trend("0001")
            if kis_data and kis_data.get("foreign_buy") != 0:
                logger.info(f"KIS 실시간 수급 데이터 확보: Foreign={kis_data['foreign_buy']}")
                return {
                    "foreign_buy": kis_data["foreign_buy"],
                    "inst_buy": kis_data["inst_buy"],
                }
        except Exception as error:
            logger.warning(f"KIS 실시간 수급 로드 실패: {error}")

    filepath = os.path.join(data_dir, "all_institutional_trend_data.csv")
    if not os.path.exists(filepath):
        return {}

    try:
        usecols = ["date", "foreign_buy", "inst_buy"]
        df = _load_cached_csv_frame(
            data_dir=data_dir,
            filename="all_institutional_trend_data.csv",
            usecols=usecols,
            logger=logger,
        )
        if df.empty:
            logger.warning(f"수급 데이터 파일이 비어있습니다: {filepath}")
            return {}

        df = df.sort_values("date")
        latest = df.iloc[-1]
        return {
            "foreign_buy": latest.get("foreign_buy", 0),
            "inst_buy": latest.get("inst_buy", 0),
        }
    except Exception as error:
        logger.error(f"수급 데이터 로드 실패: {error}")
        return {}
