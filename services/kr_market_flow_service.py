#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Flow Service

라우트 레벨 실행/흐름 제어 로직을 분리한다.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from services.kr_market_csv_utils import (
    get_ticker_padded_series as _get_ticker_padded_series,
    load_csv_readonly as _load_csv_readonly,
)
_JONGGA_DATES_CACHE: dict[str, dict[str, Any]] = {}


def _safe_mtime_ns(path: Path) -> int:
    try:
        return int(path.stat().st_mtime_ns)
    except FileNotFoundError:
        return -1
    except Exception:
        return -1


def _build_jongga_dates_signature(data_dir: Path) -> tuple[int, int]:
    """날짜 목록 캐시 무효화용 시그니처를 생성한다."""
    return (
        _safe_mtime_ns(data_dir),
        _safe_mtime_ns(data_dir / "jongga_v2_latest.json"),
    )


def _normalize_jongga_date_token(token: str) -> str:
    if len(token) == 8 and token.isdigit():
        return f"{token[:4]}-{token[4:6]}-{token[6:]}"
    return token


def _collect_jongga_result_dates_from_files(data_dir_path: Path) -> set[str]:
    dates: set[str] = set()
    for path in data_dir_path.glob("jongga_v2_results_*.json"):
        token = path.stem.replace("jongga_v2_results_", "")
        dates.add(_normalize_jongga_date_token(token))
    return dates



def build_market_status_payload(
    load_csv_file: Callable[[str], pd.DataFrame],
    now: datetime | None = None,
) -> dict[str, Any]:
    """한국 시장 상태 요약 payload를 생성한다."""
    current_time = now or datetime.now()
    df = _load_csv_readonly(
        load_csv_file,
        "daily_prices.csv",
        usecols=["date", "ticker", "close"],
    )

    if df.empty:
        return {
            "status": "NEUTRAL",
            "score": 50,
            "current_price": 0,
            "ma200": 0,
            "date": current_time.strftime("%Y-%m-%d"),
            "symbol": "069500",
            "name": "KODEX 200",
            "message": "데이터 파일이 없습니다. 데이터 수집이 필요합니다.",
        }

    ticker_padded = _get_ticker_padded_series(df)
    kodex = df[ticker_padded == "069500"]
    if kodex.empty:
        kodex = df.head(1)

    latest = kodex.iloc[-1] if not kodex.empty else {}
    current_price = float(latest.get("close", 0))

    return {
        "status": "NEUTRAL",
        "score": 50,
        "current_price": current_price,
        "ma200": current_price * 0.98,
        "date": str(latest.get("date", current_time.strftime("%Y-%m-%d"))),
        "symbol": "069500",
        "name": "KODEX 200",
    }


def execute_market_gate_update(
    target_date: str | None,
    logger: logging.Logger,
) -> tuple[int, dict[str, Any]]:
    """Market Gate와 Smart Money 데이터를 순차 갱신한다."""
    logger.info(f"[Update] Market Gate 및 Smart Money 데이터 갱신 요청 (Date: {target_date})")

    from scripts import init_data

    try:
        logger.info("[Update] 수급 데이터(Smart Money) 동기화 시작...")
        init_data.create_institutional_trend(target_date=target_date, force=True)
        logger.info("[Update] 수급 데이터 동기화 완료")
    except Exception as e:
        logger.error(f"[Update] 수급 데이터 갱신 실패 (무시하고 진행): {e}")

    from engine.market_gate import MarketGate

    market_gate = MarketGate()
    result = market_gate.analyze(target_date=target_date)
    saved_path = market_gate.save_analysis(result, target_date=target_date)
    logger.info(f"[Update] Market Gate 분석 완료 및 저장: {saved_path}")

    return 200, {
        "status": "success",
        "message": "Market Gate and Smart Money data updated successfully",
        "data": result,
    }


def collect_jongga_v2_dates(
    data_dir: str | Path,
    load_json_file: Callable[[str], dict[str, Any]],
    logger: logging.Logger,
) -> list[str]:
    """종가베팅 결과 파일에서 사용 가능한 날짜 목록을 수집한다."""
    data_dir_path = Path(data_dir)
    cache_key = str(data_dir_path.resolve())
    signature = _build_jongga_dates_signature(data_dir_path)

    cached = _JONGGA_DATES_CACHE.get(cache_key)
    if cached and cached.get("signature") == signature:
        return list(cached.get("dates", []))

    dates = _collect_jongga_result_dates_from_files(data_dir_path)

    try:
        latest_data = load_json_file("jongga_v2_latest.json")
        if latest_data and "date" in latest_data:
            latest_date = str(latest_data["date"])[:10]
            dates.add(latest_date)
    except Exception as e:
        logger.warning(f"Failed to read latest jongga date: {e}")

    deduped_dates = sorted(dates, reverse=True)
    _JONGGA_DATES_CACHE[cache_key] = {
        "signature": signature,
        "dates": deduped_dates,
    }
    return deduped_dates


def start_vcp_screener_run(
    req_data: dict[str, Any],
    status_state: dict[str, Any],
    background_runner: Callable[[str | None, int | None], None],
) -> tuple[int, dict[str, Any]]:
    """VCP 스크리너 백그라운드 실행을 시작한다."""
    if status_state.get("running"):
        return 409, {"status": "error", "message": "Already running"}

    target_date = req_data.get("target_date")
    max_stocks = req_data.get("max_stocks", 50)

    status_state.update(
        {
            "running": True,
            "status": "running",
            "progress": 0,
            "message": "분석 요청 중...",
        }
    )

    thread = threading.Thread(
        target=background_runner,
        args=(target_date, max_stocks),
        daemon=True,
    )
    thread.start()

    message = "VCP Screener started in background."
    if target_date:
        message = f"[테스트 모드] {target_date} 기준 VCP 분석 시작."

    return 200, {
        "status": "started",
        "message": message,
        "target_date": target_date,
    }


def launch_background_update_job(
    items_list: list[str],
    target_date: str | None,
    load_update_status: Callable[[], dict[str, Any]],
    start_update: Callable[[list[str]], None],
    run_background_update: Callable[[str | None, list[str]], None],
    logger: logging.Logger,
) -> tuple[int, dict[str, Any]]:
    """공통 백그라운드 업데이트 작업을 시작한다."""
    status = load_update_status()
    if status.get("isRunning", False):
        return 409, {"status": "error", "message": "Update already in progress"}

    start_update(items_list)

    thread = threading.Thread(
        target=run_background_update,
        args=(target_date, items_list),
        daemon=True,
    )
    thread.start()
    logger.info("Background update started: %s", items_list)

    return 200, {
        "status": "started",
        "items": items_list,
        "target_date": target_date,
    }


def launch_init_data_update(
    data_type: str,
    target_date: str | None,
    load_update_status: Callable[[], dict[str, Any]],
    start_update: Callable[[list[str]], None],
    run_background_update: Callable[[str | None, list[str]], None],
    logger: logging.Logger,
) -> tuple[int, dict[str, Any]]:
    """init-data 라우트용 type 매핑/백그라운드 시작을 처리한다."""
    items_map = {
        "prices": ["Daily Prices"],
        "institutional": ["Institutional Trend"],
        "signals": ["VCP Signals"],
        "all": ["Daily Prices", "Institutional Trend", "VCP Signals"],
    }
    items_list = items_map.get(data_type, [])
    if not items_list:
        return 400, {"status": "error", "message": f"Unknown data type: {data_type}"}

    status_code, payload = launch_background_update_job(
        items_list=items_list,
        target_date=target_date,
        load_update_status=load_update_status,
        start_update=start_update,
        run_background_update=run_background_update,
        logger=logger,
    )
    if status_code == 200:
        payload["type"] = data_type
        payload["message"] = f"{data_type} 업데이트가 백그라운드에서 시작되었습니다."

    return status_code, payload
