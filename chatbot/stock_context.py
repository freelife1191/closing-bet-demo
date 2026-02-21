#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
종목 상세 컨텍스트 조회/포맷 유틸
"""

import logging
from pathlib import Path


def fetch_stock_history(data_dir: Path, ticker: str, logger: logging.Logger) -> str:
    """daily_prices.csv에서 최근 5일 주가 조회"""
    try:
        import pandas as pd

        path = data_dir / "daily_prices.csv"
        if not path.exists():
            return ""

        df = pd.read_csv(path, dtype={"ticker": str})
        df["date"] = pd.to_datetime(df["date"])
        target = df[df["ticker"] == ticker].sort_values("date", ascending=False).head(5)
        if target.empty:
            return "주가 데이터 없음"

        lines = []
        for _, row in target.iterrows():
            date_text = row["date"].strftime("%Y-%m-%d")
            lines.append(
                f"- {date_text}: 종가 {row['close']:,.0f} | 거래량 {row['volume']:,.0f} | "
                f"등락 {(row['close'] - row['open']):+,.0f}"
            )
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Price fetch error for {ticker}: {e}")
        return "데이터 조회 실패"


def fetch_institutional_trend(data_dir: Path, ticker: str) -> str:
    """all_institutional_trend_data.csv에서 수급 데이터 조회 (최근 5일)"""
    try:
        import pandas as pd

        path = data_dir / "all_institutional_trend_data.csv"
        if not path.exists():
            return ""

        df = pd.read_csv(path, dtype={"ticker": str})
        df["date"] = pd.to_datetime(df["date"])
        target = df[df["ticker"] == ticker].sort_values("date", ascending=False).head(5)
        if target.empty:
            return "수급 데이터 없음"

        lines = []
        for _, row in target.iterrows():
            date_text = row["date"].strftime("%Y-%m-%d")
            lines.append(f"- {date_text}: 외인 {row['foreign_buy']:+,.0f} | 기관 {row['inst_buy']:+,.0f}")
        return "\n".join(lines)
    except Exception:
        return "데이터 조회 실패"


def fetch_signal_history(data_dir: Path, ticker: str) -> str:
    """signals_log.csv에서 VCP 시그널 이력 조회"""
    try:
        import pandas as pd

        path = data_dir / "signals_log.csv"
        if not path.exists():
            return ""

        df = pd.read_csv(path, dtype={"ticker": str})
        target = df[df["ticker"] == ticker].sort_values("signal_date", ascending=False)
        if target.empty:
            return "과거 VCP 포착 이력 없음"

        lines = []
        for _, row in target.iterrows():
            lines.append(f"- {row['signal_date']}: {row['score']}점 VCP 포착")
        return "\n".join(lines)
    except Exception:
        return "조회 실패"


def format_stock_context(name: str, ticker: str, price_text: str, trend_text: str, signal_text: str) -> str:
    """종목 상세 컨텍스트 문자열 생성."""
    return f"""
## [종목 상세 데이터: {name} ({ticker})]
### 1. 최근 주가 (5일)
{price_text}

### 2. 수급 현황 (5일)
{trend_text}

### 3. VCP 시그널 이력
{signal_text}
"""

