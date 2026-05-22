#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Jongga Latest Payload Builder
"""

from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any, Callable

import pandas as pd
from engine.market_schedule import MarketSchedule

from services.kr_market_csv_utils import (
    build_latest_close_map_from_prices_df,
    load_csv_readonly as _load_csv_readonly,
)
from services.kr_market_data_cache_core import (
    load_csv_file as _load_cached_csv_file,
)
from services.kr_market_jongga_payload_helpers import (
    build_no_jongga_data_payload,
    find_recent_valid_jongga_payload,
    has_non_empty_signals,
    write_json_to_path,
)


def _parse_payload_date(payload: dict[str, Any]) -> date | None:
    """종가베팅 payload의 기준일을 date로 정규화한다."""
    raw_date = payload.get("date")
    if isinstance(raw_date, date):
        return raw_date
    if isinstance(raw_date, str) and raw_date.strip():
        try:
            return datetime.strptime(raw_date.strip()[:10], "%Y-%m-%d").date()
        except ValueError:
            return None

    signals = payload.get("signals")
    if isinstance(signals, list) and signals:
        signal_date = signals[0].get("signal_date") if isinstance(signals[0], dict) else None
        if isinstance(signal_date, str) and signal_date.strip():
            try:
                return datetime.strptime(signal_date.strip()[:10], "%Y-%m-%d").date()
            except ValueError:
                return None
    return None


def _is_latest_payload_stale(payload: dict[str, Any], current_time: datetime) -> bool:
    """오늘 개장일인데 latest payload 기준일이 오늘보다 과거인지 확인한다."""
    payload_date = _parse_payload_date(payload)
    current_date = current_time.date()
    if payload_date is None or payload_date >= current_date:
        return False
    return MarketSchedule.is_market_open(current_date)


def _build_stale_jongga_data_payload(
    current_time: datetime,
    payload: dict[str, Any],
) -> dict[str, Any]:
    latest_date = _parse_payload_date(payload)
    latest_date_str = latest_date.isoformat() if latest_date else str(payload.get("date") or "")
    today_str = current_time.date().isoformat()
    return {
        "date": today_str,
        "signals": [],
        "filtered_count": 0,
        "status": "stale",
        "is_stale": True,
        "latest_available_date": latest_date_str,
        "stale_warning": (
            f"오늘({today_str}) 기준 종가베팅 데이터가 없습니다. "
            f"최신 저장 데이터는 {latest_date_str or '알 수 없음'}입니다."
        ),
        "message": "오래된 종가베팅 데이터가 최신 리포트로 표시되지 않도록 숨겼습니다. [업데이트] 버튼을 눌러 분석을 실행해주세요.",
    }


def _build_empty_latest_jongga_data_payload(
    current_time: datetime,
    payload: dict[str, Any],
) -> dict[str, Any]:
    payload_date = _parse_payload_date(payload) or current_time.date()
    return {
        **payload,
        "date": payload_date.isoformat(),
        "signals": [],
        "filtered_count": 0,
        "by_grade": payload.get("by_grade") or {"S": 0, "A": 0, "B": 0, "D": 0},
        "status": payload.get("status") or "no_data",
        "message": payload.get("message")
        or "해당 기준일의 종가베팅 추천 종목이 없습니다. 과거 리포트로 대체하지 않았습니다.",
    }


def _build_latest_price_map_from_dataframe(df_prices: pd.DataFrame) -> dict[str, float]:
    return build_latest_close_map_from_prices_df(df_prices)


def _load_latest_price_map_for_jongga(
    *,
    load_csv_file: Callable[[str], pd.DataFrame] | None,
    daily_prices_path: str,
    load_latest_price_map: Callable[[], dict[str, float]] | None,
) -> dict[str, float]:
    if load_latest_price_map is not None:
        loaded = load_latest_price_map()
        if isinstance(loaded, dict):
            return loaded

    if load_csv_file is not None:
        df_prices = _load_csv_readonly(
            load_csv_file,
            "daily_prices.csv",
            usecols=["date", "ticker", "close"],
        )
        if not isinstance(df_prices, pd.DataFrame):
            return {}
        if df_prices.empty:
            return {}
        required_cols = {"ticker", "close"}
        if not required_cols.issubset(set(df_prices.columns)):
            return {}
        if "date" in df_prices.columns:
            use_columns = ["date", "ticker", "close"]
            df_prices = df_prices[[col for col in use_columns if col in df_prices.columns]]
        else:
            df_prices = df_prices[["ticker", "close"]]
        return _build_latest_price_map_from_dataframe(df_prices)

    if not os.path.exists(daily_prices_path):
        return {}

    try:
        data_dir = os.path.dirname(daily_prices_path)
        filename = os.path.basename(daily_prices_path)
        if not filename:
            return {}
        df_prices = _load_cached_csv_file(
            data_dir,
            filename,
            deep_copy=False,
            usecols=["date", "ticker", "close"],
        )
    except Exception:
        try:
            df_prices = _load_cached_csv_file(
                data_dir,
                filename,
                deep_copy=False,
            )
        except Exception:
            return {}

    if not isinstance(df_prices, pd.DataFrame):
        return {}
    if df_prices.empty:
        return {}
    required = {"ticker", "close"}
    if not required.issubset(set(df_prices.columns)):
        return {}
    if "date" in df_prices.columns:
        df_prices = df_prices[[col for col in ["date", "ticker", "close"] if col in df_prices.columns]]
    else:
        df_prices = df_prices[[col for col in ["ticker", "close"] if col in df_prices.columns]]

    return _build_latest_price_map_from_dataframe(df_prices)


def inject_latest_prices_into_jongga_payload(
    payload: dict[str, Any],
    load_csv_file: Callable[[str], pd.DataFrame] | None,
    daily_prices_path: str,
    apply_latest_prices_to_jongga_signals: Callable[[list[dict[str, Any]], dict[str, float]], int],
    logger: Any,
    load_latest_price_map: Callable[[], dict[str, float]] | None = None,
) -> None:
    if not has_non_empty_signals(payload):
        return

    try:
        latest_price_map = _load_latest_price_map_for_jongga(
            load_csv_file=load_csv_file,
            daily_prices_path=daily_prices_path,
            load_latest_price_map=load_latest_price_map,
        )
        if not latest_price_map:
            return
        updated_count = apply_latest_prices_to_jongga_signals(payload["signals"], latest_price_map)
        logger.debug(f"[Jongga V2 Latest] Updated prices for {updated_count} signals")
    except Exception as error:
        logger.warning(f"Failed to inject prices for Jongga V2: {error}")


def build_jongga_latest_payload(
    data_dir: str,
    load_json_file: Callable[[str], dict[str, Any]],
    get_data_path: Callable[[str], str],
    recalculate_jongga_grades: Callable[[dict[str, Any]], bool],
    sort_jongga_signals: Callable[[list[dict[str, Any]]], None],
    normalize_jongga_signals_for_frontend: Callable[[list[dict[str, Any]]], None],
    apply_latest_prices_to_jongga_signals: Callable[[list[dict[str, Any]], dict[str, float]], int],
    logger: Any,
    load_csv_file: Callable[[str], pd.DataFrame] | None = None,
    now: datetime | None = None,
    load_latest_price_map: Callable[[], dict[str, float]] | None = None,
) -> dict[str, Any]:
    """종가베팅 최신 조회 payload를 구성한다."""
    current_time = now or datetime.now()
    data = load_json_file("jongga_v2_latest.json")

    if isinstance(data, dict) and data:
        if _is_latest_payload_stale(data, current_time):
            logger.info(
                "[Jongga V2] 최신 종가베팅 데이터가 오래되었습니다. payload_date=%s, today=%s",
                _parse_payload_date(data),
                current_time.date(),
            )
            return _build_stale_jongga_data_payload(current_time, data)

        if not has_non_empty_signals(data):
            return _build_empty_latest_jongga_data_payload(current_time, data)

    if not has_non_empty_signals(data):
        recent_payload = find_recent_valid_jongga_payload(
            data_dir=data_dir,
            recalculate_jongga_grades=recalculate_jongga_grades,
            logger=logger,
        )
        if recent_payload:
            return recent_payload
        logger.info("[Jongga V2] 종가베팅 데이터 없음. 자동 실행 비활성화 상태.")
        return build_no_jongga_data_payload(current_time)

    inject_latest_prices_into_jongga_payload(
        payload=data,
        load_csv_file=load_csv_file,
        daily_prices_path=get_data_path("daily_prices.csv"),
        apply_latest_prices_to_jongga_signals=apply_latest_prices_to_jongga_signals,
        logger=logger,
        load_latest_price_map=load_latest_price_map,
    )

    if recalculate_jongga_grades(data):
        write_json_to_path(get_data_path("jongga_v2_latest.json"), data, logger)

    sort_jongga_signals(data["signals"])
    normalize_jongga_signals_for_frontend(data["signals"])
    return data
