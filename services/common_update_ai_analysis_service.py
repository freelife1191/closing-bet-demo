#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Common Update AI Analysis Service
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Callable

import pandas as pd
from numpy_json_encoder import NumpyEncoder

from engine.pandas_utils_safe import sanitize_for_json
from engine.ticker_utils import normalize_ticker
from engine.signal_tracker_ai_helpers import AI_PROMPT_NUMERIC_FIELDS, build_ai_batch_payload
from engine.vcp_ai_analyzer import get_vcp_analyzer
from engine.vcp_ai_orchestration_helpers import VCP_AI_RECOMMENDATION_FIELDS
from services.kr_market_vcp_reanalysis_service import run_async_analyzer_batch
from engine.screening_runtime import resolve_vcp_signals_to_show
from services.common_env_service import _env_file_lock as ai_analysis_lock
from services.common_update_pipeline_steps import is_stop_requested, raise_if_stopped
from services.kr_market_ai_payload_service import normalize_ai_analysis_date as _analysis_date
from services.kr_market_data_cache_service import atomic_write_text, load_csv_file


_AI_TARGET_SIGNAL_COLUMNS = {"signal_date", "ticker", "name", "current_price", "entry_price", *AI_PROMPT_NUMERIC_FIELDS}


def _resolve_ai_target_limit() -> int:
    return resolve_vcp_signals_to_show(default=20, minimum=1)


def _load_ai_signal_targets(signals_path: str) -> pd.DataFrame:
    """AI 분석에 필요한 최소 컬럼만 로드한다."""
    data_dir = os.path.dirname(signals_path)
    filename = os.path.basename(signals_path)
    return load_csv_file(
        data_dir,
        filename,
        deep_copy=False,
        usecols=sorted(_AI_TARGET_SIGNAL_COLUMNS),
    )


def _resolve_ai_target_dataframe(
    *,
    target_date: str | None,
    selected_items: list[str],
    vcp_df: pd.DataFrame | None,
    signals_path: str,
    logger: Any,
) -> tuple[pd.DataFrame, str]:
    analysis_date = target_date if target_date else datetime.now().strftime("%Y-%m-%d")
    target_df = pd.DataFrame()

    if (
        "VCP Signals" in selected_items
        and isinstance(vcp_df, pd.DataFrame)
        and not vcp_df.empty
    ):
        logger.info("VCP 결과 메모리에서 로드")
        df = vcp_df.copy()
    else:
        logger.info("VCP 결과 파일에서 로드 시도")
        df = _load_ai_signal_targets(signals_path)
    if df.empty or "signal_date" not in df.columns:
        return target_df, analysis_date

    def normalized_date(value: Any) -> str | None:
        try:
            return _analysis_date(str(value))
        except ValueError:
            logger.warning("잘못된 signal_date 행을 AI 분석에서 제외합니다.")
            return None

    dates = df["signal_date"].map(normalized_date)
    if dates.notna().sum() == 0:
        return target_df, analysis_date
    analysis_date = _analysis_date(target_date) if target_date else dates.dropna().max()
    target_df = df[dates == analysis_date].copy()
    target_df["signal_date"] = analysis_date
    return target_df, analysis_date


def _valid_recommendations(result: Any) -> dict[str, Any]:
    from app.routes.kr_market_signal_common import _is_meaningful_ai_reason

    if not isinstance(result, dict):
        return {}
    return {field: rec for field in VCP_AI_RECOMMENDATION_FIELDS
            if isinstance((rec := result.get(field)), dict)
            and rec.get("action") in {"BUY", "SELL", "HOLD"}
            and _is_meaningful_ai_reason(rec.get("reason"))}


def _read_analysis(path: str) -> dict[str, Any]:
    if not os.path.exists(path):
        return {"signals": []}
    with open(path, encoding="utf-8") as source:
        payload = json.load(source)
    if not isinstance(payload, dict) or not isinstance(payload.get("signals"), list):
        raise ValueError("기존 AI 저장 형식이 올바르지 않습니다. 보존 후 분석을 중단합니다.")
    return payload


def _signal_date_of(path: str) -> Any:
    try:
        with open(path, encoding="utf-8") as source:
            return json.load(source).get("signal_date")
    except (OSError, ValueError, AttributeError):
        return None


def _write_ai_analysis_files(*, data_dir: str, analysis_date: str, results: dict[str, Any]) -> int:
    """유효 추천만 병합한다. 실패·과거 실행은 최신 정상 자료를 덮지 않는다."""
    analysis_date = _analysis_date(analysis_date)
    rows = results.get("signals", [])
    updates = {normalize_ticker(row.get("ticker")): row for row in rows
               if isinstance(row, dict) and normalize_ticker(row.get("ticker")) and _valid_recommendations(row)}
    if not updates:
        return 0
    # 수동 갱신·수집·재분석이 이 파일들을 함께 쓰므로 다시 읽기부터 교체까지 한 잠금 안에 둔다([VCP-052])
    with ai_analysis_lock(os.path.join(data_dir, "kr_ai_analysis.json")):
        return _merge_ai_analysis_files(data_dir=data_dir, analysis_date=analysis_date, results=results, updates=updates)


def _merge_ai_analysis_files(*, data_dir: str, analysis_date: str, results: dict[str, Any], updates: dict[str, Any]) -> int:
    writes = []
    for prefix in ("ai_analysis_results", "kr_ai_analysis"):
        dated = os.path.join(data_dir, f"{prefix}_{analysis_date.replace('-', '')}.json")
        existing = _read_analysis(dated)
        merged = {normalize_ticker(row.get("ticker")): dict(row) for row in existing["signals"] if isinstance(row, dict)}
        for ticker, new in updates.items():
            old = merged.setdefault(ticker, {key: value for key, value in new.items() if key not in VCP_AI_RECOMMENDATION_FIELDS})
            old["ticker"] = ticker
            old.update(_valid_recommendations(new))
        payload = {**existing, "signal_date": analysis_date, "generated_at": datetime.now().isoformat(), "signals": list(merged.values())}
        for key, value in results.items():
            if key not in {"signals", "generated_at", "signal_date"} and key not in payload:
                payload[key] = value
        serialized = json.dumps(sanitize_for_json(payload), ensure_ascii=False, indent=2, cls=NumpyEncoder, allow_nan=False)
        writes.append((dated, serialized))
        undated = os.path.join(data_dir, f"{prefix}.json")
        # 날짜 없는 파일은 최신 자료다. 오늘 분석이거나 그 파일이 같은 날짜를 가리킬 때만 덮는다([VCP-044])
        if analysis_date in (datetime.now().strftime("%Y-%m-%d"), _signal_date_of(undated)):
            writes.append((undated, serialized))
    for path, serialized in writes:
        atomic_write_text(path, serialized)
    return len(updates)


def _select_top_ai_targets(target_df: pd.DataFrame, limit: int) -> pd.DataFrame:
    """AI 분석 대상 상위 N개를 선택한다."""
    if target_df.empty:
        return target_df

    if "score" not in target_df.columns:
        return target_df.head(limit).copy()

    scores = pd.to_numeric(target_df["score"], errors="coerce").fillna(0)
    top_indices = scores.nlargest(limit).index
    return target_df.loc[top_indices].copy()


def _normalize_ai_target_dataframe(target_df: pd.DataFrame, logger: Any) -> pd.DataFrame:
    """AI 분석용 대상 DataFrame을 표준 형태로 정규화한다."""
    if target_df.empty:
        return target_df

    if "ticker" not in target_df.columns:
        logger.warning("AI 분석 대상에 ticker 컬럼이 없어 분석을 생략합니다.")
        return pd.DataFrame()

    normalized = target_df.copy()
    normalized["ticker"] = normalized["ticker"].map(normalize_ticker)
    normalized = normalized[normalized["ticker"] != ""]
    return normalized.drop_duplicates(subset=["ticker"])


def run_ai_analysis_step(
    *, target_date: str | None, selected_items: list[str], vcp_df: pd.DataFrame | None,
    update_item_status: Callable[[str, str], None], shared_state: Any, logger: Any,
    data_dir: str | None = None,
) -> dict[str, Any]:
    raise_if_stopped(shared_state)
    update_item_status("AI Analysis", "running")
    try:
        target_date = _analysis_date(target_date) if target_date is not None else None
        data_dir = data_dir or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
        targets, analysis_date = _resolve_ai_target_dataframe(
            target_date=target_date, selected_items=selected_items, vcp_df=vcp_df,
            signals_path=os.path.join(data_dir, "signals_log.csv"), logger=logger,
        )
        analysis_date = _analysis_date(analysis_date)
        targets = _select_top_ai_targets(_normalize_ai_target_dataframe(targets, logger), _resolve_ai_target_limit())
        if targets.empty:
            logger.info("AI 분석 대상 없음: 기존 저장 자료 유지")
            update_item_status("AI Analysis", "done")
            return {"count": 0}
        stocks = build_ai_batch_payload(targets)
        for stock in stocks:
            if not isinstance(stock.get("name"), str) or not stock["name"].strip():
                stock["name"] = stock["ticker"]
        if "VCP Signals" in selected_items:
            path = os.path.join(data_dir, f"ai_analysis_results_{analysis_date.replace('-', '')}.json")
            cached = _read_analysis(path)
            tickers = {stock["ticker"] for stock in stocks}
            count = len({normalize_ticker(row.get("ticker")) for row in cached["signals"]
                         if isinstance(row, dict) and normalize_ticker(row.get("ticker")) in tickers and _valid_recommendations(row)}) if cached.get("signal_date") == analysis_date else 0
            if not count:
                raise ValueError("대상 날짜·종목의 유효 VCP 분석 결과가 없습니다.")
            logger.info("저장된 VCP 분석 결과 재사용: 추가 모델 호출 없음")
            update_item_status("AI Analysis", "done")
            return {"count": count, "reused": True}
        results = run_async_analyzer_batch(get_vcp_analyzer(), stocks)
        raise_if_stopped(shared_state)
        rows = [{**stock, **_valid_recommendations(results.get(stock["ticker"]))} for stock in stocks] if isinstance(results, dict) else []
        count = _write_ai_analysis_files(data_dir=data_dir, analysis_date=analysis_date, results={"signals": rows})
        if not count:
            raise ValueError("유효한 AI 분석 결과가 없어 기존 자료를 유지합니다.")
        update_item_status("AI Analysis", "done")
        return {"count": count}
    except Exception as error:
        logger.error(f"AI Analysis Failed: {error}")
        update_item_status("AI Analysis", "error")
        if is_stop_requested(shared_state):
            raise
        return {"count": 0, "error": str(error)}


__all__ = ["run_ai_analysis_step"]
