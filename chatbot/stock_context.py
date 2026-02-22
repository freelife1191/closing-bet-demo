#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
종목 상세 컨텍스트 조회/포맷 유틸
"""

import logging
from pathlib import Path
from typing import Any, Callable, Iterable

from services.kr_market_data_cache_service import load_csv_file as load_shared_csv_file

from .stock_context_cache import (
    clear_result_text_cache,
    load_cached_result_text,
    save_cached_result_text,
)


LOGGER = logging.getLogger(__name__)


def _file_signature(path: Path) -> tuple[int, int] | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    return int(stat.st_mtime_ns), int(stat.st_size)


def clear_stock_context_cache() -> None:
    clear_result_text_cache()


def _ensure_normalized_ticker(df: Any) -> Any:
    if "ticker" not in df.columns:
        return df

    padded_col = "_ticker_padded"
    if padded_col not in df.columns:
        df[padded_col] = df["ticker"].astype(str).str.zfill(6)
    return df


def _select_ticker_rows(
    df: Any,
    *,
    ticker_padded: str,
    date_column: str,
    limit: int | None = None,
) -> Any:
    import pandas as pd

    if df.empty:
        return df

    if "_ticker_padded" not in df.columns:
        df = _ensure_normalized_ticker(df)
        if "_ticker_padded" not in df.columns:
            return df.iloc[0:0]

    target = df[df["_ticker_padded"] == ticker_padded]
    if target.empty:
        return target

    if date_column in target.columns:
        if not pd.api.types.is_datetime64_any_dtype(target[date_column]):
            converted = pd.to_datetime(target[date_column], errors="coerce")
            if converted.notna().any():
                target = target.copy()
                target[date_column] = converted
        target = target.sort_values(date_column, ascending=False)

    if limit is not None:
        target = target.head(limit)
    return target


def _load_cached_csv(
    path: Path,
    *,
    usecols: tuple[str, ...] | None = None,
    signature: tuple[int, int] | None = None,
) -> Any:
    df = load_shared_csv_file(
        str(path.parent),
        path.name,
        deep_copy=False,
        usecols=list(usecols) if usecols is not None else None,
        signature=signature,
    )
    df = _ensure_normalized_ticker(df)
    return df


def _format_date_text(value: Any) -> str:
    return str(value)[:10]


def _iter_selected_rows(df: Any, *, columns: tuple[str, ...]) -> Iterable[tuple[Any, ...]]:
    """지정 컬럼만 튜플로 순회해 dict 변환 비용을 줄인다."""
    return df.loc[:, list(columns)].itertuples(index=False, name=None)


def _fetch_ticker_context_text(
    *,
    data_dir: Path,
    ticker: str,
    filename: str,
    dataset: str,
    usecols: tuple[str, ...],
    date_column: str,
    line_columns: tuple[str, ...],
    empty_text: str,
    limit: int | None,
    line_builder: Callable[[tuple[Any, ...]], str],
) -> str:
    path = data_dir / filename
    if not path.exists():
        return ""

    signature = _file_signature(path)
    if signature is None:
        return ""

    ticker_padded = str(ticker).zfill(6)
    cached_text = load_cached_result_text(
        data_dir=data_dir,
        path=path,
        dataset=dataset,
        ticker_padded=ticker_padded,
        signature=signature,
    )
    if cached_text is not None:
        return cached_text

    df = _load_cached_csv(
        path,
        usecols=usecols,
        signature=signature,
    )
    if df.empty or "ticker" not in df.columns:
        save_cached_result_text(
            data_dir=data_dir,
            path=path,
            dataset=dataset,
            ticker_padded=ticker_padded,
            signature=signature,
            payload_text=empty_text,
        )
        return empty_text

    target = _select_ticker_rows(
        df,
        ticker_padded=ticker_padded,
        date_column=date_column,
        limit=limit,
    )
    if target.empty:
        save_cached_result_text(
            data_dir=data_dir,
            path=path,
            dataset=dataset,
            ticker_padded=ticker_padded,
            signature=signature,
            payload_text=empty_text,
        )
        return empty_text

    lines = []
    for row in _iter_selected_rows(target, columns=line_columns):
        lines.append(line_builder(row))
    result_text = "\n".join(lines)
    save_cached_result_text(
        data_dir=data_dir,
        path=path,
        dataset=dataset,
        ticker_padded=ticker_padded,
        signature=signature,
        payload_text=result_text,
    )
    return result_text


def _build_stock_history_line(row: tuple[Any, ...]) -> str:
    date_value, open_value, close_value, volume_value = row
    date_text = _format_date_text(date_value)
    return (
        f"- {date_text}: 종가 {close_value:,.0f} | 거래량 {volume_value:,.0f} | "
        f"등락 {(close_value - open_value):+,.0f}"
    )


def _build_institutional_trend_line(row: tuple[Any, ...]) -> str:
    date_value, foreign_buy, inst_buy = row
    date_text = _format_date_text(date_value)
    return f"- {date_text}: 외인 {foreign_buy:+,.0f} | 기관 {inst_buy:+,.0f}"


def _build_signal_history_line(row: tuple[Any, ...]) -> str:
    signal_date, score = row
    date_text = _format_date_text(signal_date)
    return f"- {date_text}: {score}점 VCP 포착"


def fetch_stock_history(data_dir: Path, ticker: str, logger: logging.Logger) -> str:
    """daily_prices.csv에서 최근 5일 주가 조회"""
    try:
        return _fetch_ticker_context_text(
            data_dir=data_dir,
            ticker=ticker,
            filename="daily_prices.csv",
            dataset="stock_history",
            usecols=("date", "ticker", "open", "close", "volume"),
            date_column="date",
            line_columns=("date", "open", "close", "volume"),
            empty_text="주가 데이터 없음",
            limit=5,
            line_builder=_build_stock_history_line,
        )
    except Exception as exc:
        logger.error("Price fetch error for %s: %s", ticker, exc)
        return "데이터 조회 실패"


def fetch_institutional_trend(data_dir: Path, ticker: str) -> str:
    """all_institutional_trend_data.csv에서 수급 데이터 조회 (최근 5일)"""
    try:
        return _fetch_ticker_context_text(
            data_dir=data_dir,
            ticker=ticker,
            filename="all_institutional_trend_data.csv",
            dataset="institutional_trend",
            usecols=("date", "ticker", "foreign_buy", "inst_buy"),
            date_column="date",
            line_columns=("date", "foreign_buy", "inst_buy"),
            empty_text="수급 데이터 없음",
            limit=5,
            line_builder=_build_institutional_trend_line,
        )
    except Exception as exc:
        LOGGER.error("Institutional trend fetch error for %s: %s", ticker, exc)
        return "데이터 조회 실패"


def fetch_signal_history(data_dir: Path, ticker: str) -> str:
    """signals_log.csv에서 VCP 시그널 이력 조회"""
    try:
        return _fetch_ticker_context_text(
            data_dir=data_dir,
            ticker=ticker,
            filename="signals_log.csv",
            dataset="signal_history",
            usecols=("signal_date", "ticker", "score"),
            date_column="signal_date",
            line_columns=("signal_date", "score"),
            empty_text="과거 VCP 포착 이력 없음",
            limit=None,
            line_builder=_build_signal_history_line,
        )
    except Exception as exc:
        LOGGER.error("Signal history fetch error for %s: %s", ticker, exc)
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
