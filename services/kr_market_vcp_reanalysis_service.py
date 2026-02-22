#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market VCP Reanalysis Service
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

import pandas as pd


def prepare_vcp_signals_scope(
    signals_df: pd.DataFrame,
    target_date: str | None,
) -> tuple[str, pd.DataFrame]:
    """재분석 대상 범위(날짜)를 계산한다."""
    normalized_df = signals_df.copy()
    normalized_df["ticker"] = normalized_df["ticker"].astype(str).str.zfill(6)
    normalized_df["signal_date"] = normalized_df["signal_date"].astype(str)

    if target_date:
        target_date_alt = target_date.replace("-", "")
        scoped_df = normalized_df[
            (normalized_df["signal_date"] == target_date)
            | (normalized_df["signal_date"] == target_date_alt)
        ].copy()
        return target_date, scoped_df

    latest_date = str(normalized_df["signal_date"].max())
    scoped_df = normalized_df[normalized_df["signal_date"] == latest_date].copy()
    return latest_date, scoped_df


def collect_failed_vcp_rows(
    scoped_df: pd.DataFrame,
    is_failed: Callable[[dict[str, Any]], bool],
) -> tuple[list[tuple[int, dict[str, Any]]], int]:
    """스코프 내 실패 행을 수집한다."""
    failed_rows: list[tuple[int, dict[str, Any]]] = []
    columns = list(scoped_df.columns)
    for idx, row_values in zip(scoped_df.index, scoped_df.itertuples(index=False, name=None)):
        row_dict = dict(zip(columns, row_values))
        if is_failed(row_dict):
            failed_rows.append((idx, row_dict))
    return failed_rows, len(scoped_df)


def run_async_analyzer_batch(analyzer: Any, stocks_to_analyze: list[dict[str, Any]]) -> dict[str, Any]:
    """비동기 analyzer 배치를 동기 컨텍스트에서 실행한다."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(analyzer.analyze_batch(stocks_to_analyze))
    finally:
        loop.close()
        asyncio.set_event_loop(None)


def validate_vcp_reanalysis_source_frame(
    signals_df: pd.DataFrame,
) -> tuple[int | None, dict[str, Any] | None]:
    """VCP 실패 재분석용 원본 DataFrame 유효성을 검증한다."""
    if signals_df.empty:
        return 404, {"status": "error", "message": "signals_log.csv 데이터가 없습니다."}

    if "ticker" not in signals_df.columns:
        return 400, {"status": "error", "message": "signals_log.csv에 ticker 컬럼이 없습니다."}

    if "signal_date" not in signals_df.columns:
        return 400, {"status": "error", "message": "signals_log.csv에 signal_date 컬럼이 없습니다."}

    return None, None


def build_vcp_reanalysis_no_targets_payload(
    target_date: str,
    total_in_scope: int,
) -> dict[str, Any]:
    return {
        "status": "success",
        "message": "재분석이 필요한 실패 항목이 없습니다.",
        "target_date": target_date,
        "total_in_scope": total_in_scope,
        "failed_targets": 0,
        "updated_count": 0,
        "still_failed_count": 0,
        "cache_files_updated": 0,
    }


def build_vcp_reanalysis_success_payload(
    target_date: str,
    total_in_scope: int,
    failed_targets: int,
    updated_count: int,
    still_failed_count: int,
    cache_files_updated: int,
) -> dict[str, Any]:
    return {
        "status": "success",
        "message": f"실패 {failed_targets}건 중 {updated_count}건 재분석 완료",
        "target_date": target_date,
        "total_in_scope": total_in_scope,
        "failed_targets": failed_targets,
        "updated_count": updated_count,
        "still_failed_count": still_failed_count,
        "cache_files_updated": cache_files_updated,
    }


def execute_vcp_failed_ai_reanalysis(
    target_date: str | None,
    signals_df: pd.DataFrame,
    signals_path: str,
    update_cache_files: Callable[[str, dict[str, Any]], int],
    logger: logging.Logger,
) -> tuple[int, dict[str, Any]]:
    """VCP 실패 AI 재분석 전체 파이프라인을 실행한다."""
    try:
        from app.routes.kr_market_helpers import (
            _apply_vcp_reanalysis_updates,
            _build_vcp_stock_payloads,
            _is_vcp_ai_analysis_failed,
        )
        from engine.vcp_ai_analyzer import get_vcp_analyzer

        normalized_target_date = str(target_date).strip() if target_date else None
        normalized_target_date, scoped_df = prepare_vcp_signals_scope(
            signals_df=signals_df,
            target_date=normalized_target_date,
        )

        if scoped_df.empty:
            return 404, {
                "status": "error",
                "message": f"해당 날짜({normalized_target_date})의 VCP 시그널 데이터가 없습니다.",
            }

        failed_rows, total_in_scope = collect_failed_vcp_rows(
            scoped_df=scoped_df,
            is_failed=_is_vcp_ai_analysis_failed,
        )
        failed_targets = len(failed_rows)

        if failed_targets == 0:
            return 200, build_vcp_reanalysis_no_targets_payload(
                target_date=normalized_target_date,
                total_in_scope=total_in_scope,
            )

        analyzer = get_vcp_analyzer()
        if not analyzer.get_available_providers():
            return 503, {
                "status": "error",
                "message": "사용 가능한 AI Provider가 없습니다.",
            }

        stocks_to_analyze = _build_vcp_stock_payloads([row for _, row in failed_rows])
        ai_results = run_async_analyzer_batch(
            analyzer=analyzer,
            stocks_to_analyze=stocks_to_analyze,
        )

        updated_count, still_failed_count, updated_recommendations = _apply_vcp_reanalysis_updates(
            signals_df,
            failed_rows,
            ai_results,
        )

        signals_df.to_csv(signals_path, index=False, encoding="utf-8-sig")
        cache_files_updated = update_cache_files(normalized_target_date, updated_recommendations)

        return 200, build_vcp_reanalysis_success_payload(
            target_date=normalized_target_date,
            total_in_scope=total_in_scope,
            failed_targets=failed_targets,
            updated_count=updated_count,
            still_failed_count=still_failed_count,
            cache_files_updated=cache_files_updated,
        )
    except Exception as e:
        logger.error(f"Error reanalyzing VCP failed AI: {e}")
        return 500, {"status": "error", "message": str(e)}


__all__ = [
    "prepare_vcp_signals_scope",
    "collect_failed_vcp_rows",
    "run_async_analyzer_batch",
    "validate_vcp_reanalysis_source_frame",
    "build_vcp_reanalysis_no_targets_payload",
    "build_vcp_reanalysis_success_payload",
    "execute_vcp_failed_ai_reanalysis",
]
