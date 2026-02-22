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

from services.common_update_pipeline_steps import is_stop_requested, raise_if_stopped
from services.kr_market_data_cache_service import atomic_write_text, load_csv_file


_AI_TARGET_SIGNAL_COLUMNS = {"signal_date", "ticker", "score"}


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
        target_df = vcp_df.copy()
        if "signal_date" in target_df.columns:
            analysis_date = str(target_df["signal_date"].iloc[0])
        return target_df, analysis_date

    logger.info("VCP 결과 파일에서 로드 시도")
    df = _load_ai_signal_targets(signals_path)
    if df.empty or "signal_date" not in df.columns:
        return target_df, analysis_date

    if not target_date:
        analysis_date = str(df["signal_date"].max())
    target_df = df[df["signal_date"].astype(str) == analysis_date].copy()
    return target_df, analysis_date


def _delete_existing_ai_result_file(data_dir: str, analysis_date: str, logger: Any) -> None:
    date_str_clean = analysis_date.replace("-", "")
    target_filename = f"ai_analysis_results_{date_str_clean}.json"
    target_filepath = os.path.join(data_dir, target_filename)

    if not os.path.exists(target_filepath):
        return

    try:
        os.remove(target_filepath)
        logger.info(f"기존 AI 분석 파일 삭제 완료: {target_filename}")
    except Exception as delete_error:
        logger.warning(f"기존 AI 파일 삭제 실패: {delete_error}")


def _write_ai_analysis_files(
    *,
    data_dir: str,
    analysis_date: str,
    target_date: str | None,
    results: dict[str, Any],
) -> None:
    date_str = analysis_date.replace("-", "")
    date_file = os.path.join(data_dir, f"ai_analysis_results_{date_str}.json")
    serialized = json.dumps(results, ensure_ascii=False, indent=2, cls=NumpyEncoder)
    atomic_write_text(date_file, serialized)

    is_today = analysis_date == datetime.now().strftime("%Y-%m-%d")
    if not target_date or is_today:
        latest_file = os.path.join(data_dir, "ai_analysis_results.json")
        atomic_write_text(latest_file, serialized)


def _select_top_ai_targets(target_df: pd.DataFrame, limit: int = 20) -> pd.DataFrame:
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
    normalized["ticker"] = normalized["ticker"].astype(str).str.zfill(6)
    return normalized.drop_duplicates(subset=["ticker"])


def run_ai_analysis_step(
    *,
    target_date: str | None,
    selected_items: list[str],
    vcp_df: pd.DataFrame | None,
    update_item_status: Callable[[str, str], None],
    shared_state: Any,
    logger: Any,
) -> None:
    raise_if_stopped(shared_state)
    update_item_status("AI Analysis", "running")

    try:
        from engine.kr_ai_analyzer import KrAiAnalyzer
    except Exception as e:
        logger.error(f"AI Analysis Failed: {e}")
        update_item_status("AI Analysis", "error")
        if is_stop_requested(shared_state):
            raise
        return

    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_dir = os.path.join(base_dir, "data")
        signals_path = os.path.join(data_dir, "signals_log.csv")
        if not os.path.exists(signals_path):
            update_item_status("AI Analysis", "done")
            return

        target_df, analysis_date = _resolve_ai_target_dataframe(
            target_date=target_date,
            selected_items=selected_items,
            vcp_df=vcp_df,
            signals_path=signals_path,
            logger=logger,
        )

        if target_df.empty:
            logger.info(f"[{analysis_date}] 시그널 데이터가 없어 AI 분석 생략")
            update_item_status("AI Analysis", "done")
            return

        normalized_targets = _normalize_ai_target_dataframe(target_df, logger=logger)
        if normalized_targets.empty:
            logger.info(f"[{analysis_date}] 유효 ticker 데이터가 없어 AI 분석 생략")
            update_item_status("AI Analysis", "done")
            return

        selected_targets = _select_top_ai_targets(normalized_targets, limit=20)
        tickers = selected_targets["ticker"].tolist()

        _delete_existing_ai_result_file(data_dir, analysis_date, logger)
        logger.info(f"AI 분석 시작: {len(tickers)} 종목 ({analysis_date})")

        analyzer = KrAiAnalyzer()
        results = analyzer.analyze_multiple_stocks(tickers)
        results["generated_at"] = datetime.now().isoformat()
        results["signal_date"] = analysis_date

        _write_ai_analysis_files(
            data_dir=data_dir,
            analysis_date=analysis_date,
            target_date=target_date,
            results=results,
        )
        logger.info(f"AI 분석 결과 저장 완료: {analysis_date}")
        update_item_status("AI Analysis", "done")
    except Exception as e:
        logger.error(f"AI Analysis Failed: {e}")
        update_item_status("AI Analysis", "error")
        if is_stop_requested(shared_state):
            raise


__all__ = ["run_ai_analysis_step"]
