#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market VCP Reanalysis Service
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Callable

import pandas as pd

from engine.config import app_config


_VCP_SECOND_RECOMMENDATION_KEY_MAP = {
    "gpt": "gpt_recommendation",
    "openai": "gpt_recommendation",
    "perplexity": "perplexity_recommendation",
}


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


def resolve_vcp_second_recommendation_key(second_provider: str) -> str:
    """second_provider 문자열을 recommendation 필드명으로 변환한다."""
    provider = str(second_provider or "").strip().lower()
    return _VCP_SECOND_RECOMMENDATION_KEY_MAP.get(provider, "gpt_recommendation")


def load_vcp_ai_cache_map(
    *,
    target_date: str | None,
    signals_path: str,
    logger: logging.Logger,
) -> tuple[bool, dict[str, dict[str, Any]]]:
    """
    VCP AI 캐시 파일들을 읽어 ticker 기준 추천 맵을 구성한다.

    반환값:
      - bool: AI 캐시 파일 존재 여부
      - dict: {ticker: {"gemini_recommendation": ..., "gpt_recommendation": ..., "perplexity_recommendation": ...}}
    """
    date_str = str(target_date or "").replace("-", "")
    data_dir = os.path.dirname(str(signals_path))
    candidate_files = [
        f"ai_analysis_results_{date_str}.json" if date_str else "",
        "ai_analysis_results.json",
        f"kr_ai_analysis_{date_str}.json" if date_str else "",
        "kr_ai_analysis.json",
    ]

    ai_data_map: dict[str, dict[str, Any]] = {}
    cache_file_exists = False
    recommendation_keys = (
        "gemini_recommendation",
        "gpt_recommendation",
        "perplexity_recommendation",
    )

    for filename in candidate_files:
        if not filename:
            continue

        file_path = os.path.join(data_dir, filename)
        if not os.path.exists(file_path):
            continue
        cache_file_exists = True

        try:
            with open(file_path, "r", encoding="utf-8") as fp:
                payload = json.load(fp)
        except Exception as error:
            logger.warning(f"VCP AI 캐시 로드 실패 ({filename}): {error}")
            continue

        signals = payload.get("signals", []) if isinstance(payload, dict) else []
        if not isinstance(signals, list):
            continue

        for item in signals:
            if not isinstance(item, dict):
                continue
            ticker = str(item.get("ticker") or item.get("stock_code") or "").zfill(6)
            if ticker == "000000":
                continue

            ticker_entry = ai_data_map.setdefault(ticker, {})
            for key in recommendation_keys:
                value = item.get(key)
                if isinstance(value, dict) and value and not isinstance(ticker_entry.get(key), dict):
                    ticker_entry[key] = value

    return cache_file_exists, ai_data_map


def collect_missing_vcp_ai_rows(
    *,
    scoped_df: pd.DataFrame,
    ai_data_map: dict[str, dict[str, Any]],
    second_recommendation_key: str,
) -> list[tuple[int, dict[str, Any]]]:
    """
    Gemini/Second AI 추천이 누락된 행을 수집한다.
    """
    missing_rows: list[tuple[int, dict[str, Any]]] = []
    columns = list(scoped_df.columns)

    for idx, row_values in zip(scoped_df.index, scoped_df.itertuples(index=False, name=None)):
        row_dict = dict(zip(columns, row_values))
        ticker = str(row_dict.get("ticker", "")).zfill(6)
        ai_item = ai_data_map.get(ticker, {})

        gemini_missing = not isinstance(ai_item.get("gemini_recommendation"), dict)
        second_missing = not isinstance(ai_item.get(second_recommendation_key), dict)
        if gemini_missing or second_missing:
            missing_rows.append((idx, row_dict))

    return missing_rows


def merge_vcp_reanalysis_target_rows(
    primary_rows: list[tuple[int, dict[str, Any]]],
    additional_rows: list[tuple[int, dict[str, Any]]],
) -> list[tuple[int, dict[str, Any]]]:
    """기본 대상(primary)과 추가 대상(additional)을 index 기준으로 병합한다."""
    merged_rows = list(primary_rows)
    seen_indexes = {idx for idx, _ in primary_rows}

    for idx, row in additional_rows:
        if idx in seen_indexes:
            continue
        merged_rows.append((idx, row))
        seen_indexes.add(idx)

    return merged_rows


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
        "message": "재분석이 필요한 실패/누락 항목이 없습니다.",
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

        second_recommendation_key = resolve_vcp_second_recommendation_key(
            app_config.VCP_SECOND_PROVIDER
        )
        cache_exists, ai_data_map = load_vcp_ai_cache_map(
            target_date=normalized_target_date,
            signals_path=signals_path,
            logger=logger,
        )

        target_rows = list(failed_rows)
        if cache_exists:
            missing_rows = collect_missing_vcp_ai_rows(
                scoped_df=scoped_df,
                ai_data_map=ai_data_map,
                second_recommendation_key=second_recommendation_key,
            )
            target_rows = merge_vcp_reanalysis_target_rows(target_rows, missing_rows)

        failed_targets = len(target_rows)

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

        stocks_to_analyze = _build_vcp_stock_payloads([row for _, row in target_rows])
        ai_results = run_async_analyzer_batch(
            analyzer=analyzer,
            stocks_to_analyze=stocks_to_analyze,
        )

        updated_count, still_failed_count, updated_recommendations = _apply_vcp_reanalysis_updates(
            signals_df,
            target_rows,
            ai_results,
        )

        signals_df.to_csv(signals_path, index=False, encoding="utf-8-sig")
        try:
            cache_files_updated = update_cache_files(
                normalized_target_date,
                updated_recommendations,
                ai_results,
            )
        except TypeError:
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
    "resolve_vcp_second_recommendation_key",
    "load_vcp_ai_cache_map",
    "collect_missing_vcp_ai_rows",
    "merge_vcp_reanalysis_target_rows",
    "run_async_analyzer_batch",
    "validate_vcp_reanalysis_source_frame",
    "build_vcp_reanalysis_no_targets_payload",
    "build_vcp_reanalysis_success_payload",
    "execute_vcp_failed_ai_reanalysis",
]
