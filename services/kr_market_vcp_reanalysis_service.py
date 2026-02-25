#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market VCP Reanalysis Service
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Callable

import pandas as pd

from engine.config import app_config
from services.kr_market_data_cache_service import (
    atomic_write_text,
    load_json_payload_from_path,
)


_VCP_SECOND_RECOMMENDATION_KEY_MAP = {
    "gpt": "gpt_recommendation",
    "openai": "gpt_recommendation",
    "zai": "gpt_recommendation",
    "z.ai": "gpt_recommendation",
    "perplexity": "perplexity_recommendation",
}
_VCP_FORCE_PROVIDER_LABELS = {
    "gemini": "Gemini",
    "second": "Second AI",
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


def normalize_vcp_force_provider(force_provider: str | None) -> str | None:
    """강제 재분석 provider 파라미터를 정규화한다."""
    provider = str(force_provider or "").strip().lower()
    if provider in {"", "auto", "default", "failed", "none"}:
        return None
    if provider in {"gemini"}:
        return "gemini"
    if provider in {"second", "secondary", "2nd"}:
        return "second"
    return None


def _resolve_reanalysis_mode_label(force_provider: str | None) -> str | None:
    return _VCP_FORCE_PROVIDER_LABELS.get(str(force_provider or "").strip().lower())


def load_vcp_ai_cache_map(
    *,
    target_date: str | None,
    signals_path: str,
    logger: logging.Logger,
    load_json_payload_from_path_fn: Callable[[str], Any] | None = None,
    ticker_filter: set[str] | None = None,
    required_recommendation_keys: set[str] | None = None,
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
    json_loader = load_json_payload_from_path_fn or load_json_payload_from_path
    normalized_ticker_filter: set[str] | None = None
    if ticker_filter:
        normalized_ticker_filter = {
            str(ticker).strip().zfill(6)
            for ticker in ticker_filter
            if str(ticker).strip()
        }
    recommendation_keys = (
        "gemini_recommendation",
        "gpt_recommendation",
        "perplexity_recommendation",
    )
    normalized_required_keys: set[str] | None = None
    if required_recommendation_keys:
        allowed_keys = set(recommendation_keys)
        filtered_required_keys = {
            str(key).strip()
            for key in required_recommendation_keys
            if str(key).strip() in allowed_keys
        }
        if filtered_required_keys:
            normalized_required_keys = filtered_required_keys
    unresolved_tickers: set[str] | None = None
    if normalized_ticker_filter and normalized_required_keys:
        unresolved_tickers = set(normalized_ticker_filter)

    for filename in candidate_files:
        if not filename:
            continue

        file_path = os.path.join(data_dir, filename)
        if not os.path.exists(file_path):
            continue
        cache_file_exists = True

        try:
            payload = json_loader(file_path)
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
            if (
                normalized_ticker_filter is not None
                and ticker not in normalized_ticker_filter
            ):
                continue

            ticker_entry = ai_data_map.setdefault(ticker, {})
            for key in recommendation_keys:
                value = item.get(key)
                if isinstance(value, dict) and value and not isinstance(ticker_entry.get(key), dict):
                    ticker_entry[key] = value
            if (
                unresolved_tickers is not None
                and ticker in unresolved_tickers
                and all(
                    isinstance(ticker_entry.get(required_key), dict)
                    for required_key in normalized_required_keys or ()
                )
            ):
                unresolved_tickers.discard(ticker)
                if not unresolved_tickers:
                    break
        if unresolved_tickers is not None and not unresolved_tickers:
            break

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


def write_vcp_signals_csv_atomic(signals_df: pd.DataFrame, signals_path: str) -> None:
    """signals_log.csv를 원자적으로 저장하고 캐시를 무효화한다."""
    csv_content = signals_df.to_csv(index=False)
    # 기존 utf-8-sig 저장 형식을 유지한다.
    atomic_write_text(signals_path, f"\ufeff{csv_content}")


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


def run_async_analyzer_batch_with_control(
    *,
    analyzer: Any,
    stocks_to_analyze: list[dict[str, Any]],
    should_stop: Callable[[], bool] | None,
    on_progress: Callable[[int, int, str], None] | None,
    logger: logging.Logger,
) -> tuple[dict[str, Any], bool]:
    """중지/진행률 콜백을 지원하는 비동기 analyzer 배치 실행."""
    if not stocks_to_analyze:
        return {}, False

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    results: dict[str, Any] = {}
    cancelled = False
    total = len(stocks_to_analyze)

    try:
        for idx, stock in enumerate(stocks_to_analyze, start=1):
            ticker = str(stock.get("ticker", "")).zfill(6)
            stock_name = str(stock.get("name") or ticker)

            if callable(should_stop) and should_stop():
                cancelled = True
                break

            try:
                if hasattr(analyzer, "analyze_stock"):
                    analyzed = loop.run_until_complete(analyzer.analyze_stock(stock_name, stock))
                    if isinstance(analyzed, dict):
                        results[ticker] = analyzed
                else:
                    batch_result = loop.run_until_complete(analyzer.analyze_batch([stock]))
                    if isinstance(batch_result, dict):
                        batch_item = batch_result.get(ticker)
                        if isinstance(batch_item, dict):
                            results[ticker] = batch_item
            except Exception as error:
                logger.error(f"[VCP Reanalysis] {stock_name} 분석 실패: {error}")
            finally:
                if callable(on_progress):
                    try:
                        on_progress(idx, total, ticker)
                    except Exception as callback_error:
                        logger.debug(f"[VCP Reanalysis] progress callback 실패: {callback_error}")

        if callable(should_stop) and should_stop():
            cancelled = True
    finally:
        loop.close()
        asyncio.set_event_loop(None)

    return results, cancelled


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
    mode_label: str | None = None,
) -> dict[str, Any]:
    if mode_label:
        message = f"{mode_label} 강제 재분석 대상이 없습니다."
    else:
        message = "재분석이 필요한 실패/누락 항목이 없습니다."
    return {
        "status": "success",
        "message": message,
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
    mode_label: str | None = None,
) -> dict[str, Any]:
    if mode_label:
        message = f"{mode_label} 강제 재분석 {failed_targets}건 중 {updated_count}건 완료"
    else:
        message = f"실패 {failed_targets}건 중 {updated_count}건 재분석 완료"
    return {
        "status": "success",
        "message": message,
        "target_date": target_date,
        "total_in_scope": total_in_scope,
        "failed_targets": failed_targets,
        "updated_count": updated_count,
        "still_failed_count": still_failed_count,
        "cache_files_updated": cache_files_updated,
    }


def build_vcp_reanalysis_cancelled_payload(
    target_date: str,
    total_in_scope: int,
    failed_targets: int,
    updated_count: int,
    still_failed_count: int,
    cache_files_updated: int,
    mode_label: str | None = None,
) -> dict[str, Any]:
    if mode_label:
        message = f"사용자 요청으로 {mode_label} 강제 재분석이 중지되었습니다."
    else:
        message = "사용자 요청으로 실패 AI 재분석이 중지되었습니다."
    return {
        "status": "cancelled",
        "message": message,
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
    force_provider: str | None = None,
    should_stop: Callable[[], bool] | None = None,
    on_progress: Callable[[int, int, str], None] | None = None,
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
        normalized_force_provider = normalize_vcp_force_provider(force_provider)
        mode_label = _resolve_reanalysis_mode_label(normalized_force_provider)

        if scoped_df.empty:
            return 404, {
                "status": "error",
                "message": f"해당 날짜({normalized_target_date})의 VCP 시그널 데이터가 없습니다.",
            }

        scoped_columns = list(scoped_df.columns)
        all_scoped_rows: list[tuple[int, dict[str, Any]]] = [
            (idx, dict(zip(scoped_columns, row_values)))
            for idx, row_values in zip(scoped_df.index, scoped_df.itertuples(index=False, name=None))
        ]
        scoped_tickers: set[str] = {
            str(row.get("ticker", "")).zfill(6)
            for _, row in all_scoped_rows
            if str(row.get("ticker", "")).strip()
        }

        failed_rows, total_in_scope = collect_failed_vcp_rows(
            scoped_df=scoped_df,
            is_failed=_is_vcp_ai_analysis_failed,
        )

        second_recommendation_key = resolve_vcp_second_recommendation_key(
            app_config.VCP_SECOND_PROVIDER
        )
        cache_exists = False
        ai_data_map: dict[str, dict[str, Any]] = {}
        if normalized_force_provider not in {"gemini", "second"}:
            cache_exists, ai_data_map = load_vcp_ai_cache_map(
                target_date=normalized_target_date,
                signals_path=signals_path,
                logger=logger,
                ticker_filter=scoped_tickers,
                required_recommendation_keys={
                    "gemini_recommendation",
                    second_recommendation_key,
                },
            )

        if normalized_force_provider in {"gemini", "second"}:
            target_rows = list(all_scoped_rows)
        else:
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
                mode_label=mode_label,
            )

        analyzer = get_vcp_analyzer()
        if not analyzer.get_available_providers():
            return 503, {
                "status": "error",
                "message": "사용 가능한 AI Provider가 없습니다.",
            }

        apply_rows: list[tuple[int, dict[str, Any]]] = []
        second_only_rows: list[tuple[int, dict[str, Any]]] = []
        skip_gemini_tickers: set[str] = set()
        skip_second_tickers: set[str] = set()

        if normalized_force_provider == "gemini":
            apply_rows = list(target_rows)
            for _, row in target_rows:
                ticker = str(row.get("ticker", "")).zfill(6)
                skip_second_tickers.add(ticker)
        elif normalized_force_provider == "second":
            second_only_rows = list(target_rows)
            for _, row in target_rows:
                ticker = str(row.get("ticker", "")).zfill(6)
                skip_gemini_tickers.add(ticker)
        else:
            failed_indexes = {idx for idx, _ in failed_rows}
            for idx, row in target_rows:
                ticker = str(row.get("ticker", "")).zfill(6)
                ai_item = ai_data_map.get(ticker, {})
                has_cached_gemini = isinstance(ai_item.get("gemini_recommendation"), dict)
                has_cached_second = isinstance(ai_item.get(second_recommendation_key), dict)

                is_second_only = (
                    idx not in failed_indexes
                    and has_cached_gemini
                    and not has_cached_second
                )
                is_gemini_only = (
                    idx not in failed_indexes
                    and not has_cached_gemini
                    and has_cached_second
                )
                if is_second_only:
                    second_only_rows.append((idx, row))
                    skip_gemini_tickers.add(ticker)
                    continue
                if is_gemini_only:
                    skip_second_tickers.add(ticker)

                apply_rows.append((idx, row))

        stocks_to_analyze = _build_vcp_stock_payloads([row for _, row in target_rows])
        for stock_item in stocks_to_analyze:
            ticker = str(stock_item.get("ticker", "")).zfill(6)
            if ticker in skip_gemini_tickers:
                stock_item["skip_gemini"] = True
            if ticker in skip_second_tickers:
                stock_item["skip_second"] = True

        if callable(should_stop) or callable(on_progress):
            ai_results, cancelled = run_async_analyzer_batch_with_control(
                analyzer=analyzer,
                stocks_to_analyze=stocks_to_analyze,
                should_stop=should_stop,
                on_progress=on_progress,
                logger=logger,
            )
        else:
            ai_results = run_async_analyzer_batch(
                analyzer=analyzer,
                stocks_to_analyze=stocks_to_analyze,
            )
            cancelled = False

        updated_count, still_failed_count, updated_recommendations = _apply_vcp_reanalysis_updates(
            signals_df,
            apply_rows,
            ai_results,
        )

        second_only_success_count = 0
        second_only_failed_count = 0
        for _, row in second_only_rows:
            ticker = str(row.get("ticker", "")).zfill(6)
            rec_payload = ai_results.get(ticker, {}) if isinstance(ai_results, dict) else {}
            second_rec = rec_payload.get(second_recommendation_key) if isinstance(rec_payload, dict) else None
            if isinstance(second_rec, dict) and second_rec:
                second_only_success_count += 1
            else:
                second_only_failed_count += 1

        updated_count += second_only_success_count
        still_failed_count += second_only_failed_count

        write_vcp_signals_csv_atomic(signals_df, signals_path)
        try:
            cache_files_updated = update_cache_files(
                normalized_target_date,
                updated_recommendations,
                ai_results,
            )
        except TypeError:
            cache_files_updated = update_cache_files(normalized_target_date, updated_recommendations)

        if cancelled:
            return 200, build_vcp_reanalysis_cancelled_payload(
                target_date=normalized_target_date,
                total_in_scope=total_in_scope,
                failed_targets=failed_targets,
                updated_count=updated_count,
                still_failed_count=still_failed_count,
                cache_files_updated=cache_files_updated,
                mode_label=mode_label,
            )

        return 200, build_vcp_reanalysis_success_payload(
            target_date=normalized_target_date,
            total_in_scope=total_in_scope,
            failed_targets=failed_targets,
            updated_count=updated_count,
            still_failed_count=still_failed_count,
            cache_files_updated=cache_files_updated,
            mode_label=mode_label,
        )
    except Exception as e:
        logger.error(f"Error reanalyzing VCP failed AI: {e}")
        return 500, {"status": "error", "message": str(e)}


__all__ = [
    "prepare_vcp_signals_scope",
    "collect_failed_vcp_rows",
    "resolve_vcp_second_recommendation_key",
    "normalize_vcp_force_provider",
    "load_vcp_ai_cache_map",
    "collect_missing_vcp_ai_rows",
    "merge_vcp_reanalysis_target_rows",
    "write_vcp_signals_csv_atomic",
    "run_async_analyzer_batch",
    "run_async_analyzer_batch_with_control",
    "validate_vcp_reanalysis_source_frame",
    "build_vcp_reanalysis_no_targets_payload",
    "build_vcp_reanalysis_success_payload",
    "build_vcp_reanalysis_cancelled_payload",
    "execute_vcp_failed_ai_reanalysis",
]
