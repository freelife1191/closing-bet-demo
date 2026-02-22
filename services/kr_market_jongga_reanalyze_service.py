#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Jongga Reanalyze Service

종가 뉴스 Gemini 재분석 파이프라인.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from services.kr_market_data_cache_service import (
    atomic_write_text,
    load_json_payload_from_path,
)


def parse_jongga_reanalyze_request_options(req_data: dict[str, Any]) -> tuple[list[str], bool]:
    """종가 뉴스 재분석 요청 옵션을 정규화한다."""
    target_tickers = req_data.get("target_tickers", [])
    force_update = bool(req_data.get("force", False))

    if not isinstance(target_tickers, list):
        target_tickers = [target_tickers]

    normalized_tickers = [str(item).strip() for item in target_tickers if str(item).strip()]
    return normalized_tickers, force_update


def load_jongga_signals_for_reanalysis(
    data_dir: str | Path,
    logger: logging.Logger | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], Path]:
    """
    재분석 대상 시그널을 로드한다.
    우선순위: jongga_v2_latest.json -> 최근 jongga_v2_results_*.json
    """
    base_dir = Path(data_dir)
    latest_file = base_dir / "jongga_v2_latest.json"

    if not latest_file.exists():
        raise FileNotFoundError("분석할 시그널이 없습니다. 먼저 엔진을 실행하세요.")

    data = _load_json_dict(latest_file, logger=logger)

    all_signals = data.get("signals", [])
    if all_signals:
        return data, all_signals, latest_file

    for file_path in sorted(base_dir.glob("jongga_v2_results_*.json"), reverse=True):
        try:
            candidate = _load_json_dict(file_path, logger=logger)
        except Exception as e:
            if logger is not None:
                logger.warning(f"Failed to load historical jongga file ({file_path.name}): {e}")
            continue

        candidate_signals = candidate.get("signals", [])
        if candidate_signals:
            return candidate, candidate_signals, file_path

    raise ValueError("분석할 시그널이 없습니다. 평일에 엔진을 먼저 실행해주세요.")


def load_market_status_for_reanalysis(logger: logging.Logger) -> Any:
    """Market Gate 상태를 안전하게 로드한다."""
    try:
        from engine.market_gate import MarketGate

        return MarketGate().analyze()
    except Exception as e:
        logger.warning(f"Error checking market gate: {e}")
        return None


def run_jongga_news_reanalysis_batch(
    analyzer: Any,
    app_config: Any,
    items_to_analyze: list[dict[str, Any]],
    market_status: Any,
    logger: logging.Logger,
) -> dict[str, Any]:
    """Chunk 기반으로 뉴스 재분석을 실행하고 결과를 병합한다."""
    if not items_to_analyze:
        raise ValueError("분석 대상 종목들에 뉴스가 없어 분석할 수 없습니다.")

    is_analysis_llm = analyzer.provider == "gemini"
    chunk_size = app_config.ANALYSIS_LLM_CHUNK_SIZE if is_analysis_llm else app_config.LLM_CHUNK_SIZE
    chunks = [items_to_analyze[i : i + chunk_size] for i in range(0, len(items_to_analyze), chunk_size)]

    logger.info(
        "[Jongga Reanalyze] total_items=%d chunk_size=%d chunks=%d",
        len(items_to_analyze),
        chunk_size,
        len(chunks),
    )

    results_map: dict[str, Any] = {}
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        async def process_chunk(chunk_idx: int, chunk_data: list[dict[str, Any]]) -> dict[str, Any]:
            logger.debug("[Jongga Reanalyze] processing chunk %d/%d", chunk_idx + 1, len(chunks))
            chunk_results = await analyzer.analyze_news_batch(chunk_data, market_status)
            return chunk_results or {}

        async def process_all_chunks() -> list[dict[str, Any]]:
            concurrency = app_config.ANALYSIS_LLM_CONCURRENCY if is_analysis_llm else app_config.LLM_CONCURRENCY
            delay = app_config.ANALYSIS_LLM_REQUEST_DELAY if is_analysis_llm else 0.5
            collected_results: list[dict[str, Any]] = []

            batch_size = max(1, int(concurrency))
            for start_idx in range(0, len(chunks), batch_size):
                batch = chunks[start_idx : start_idx + batch_size]
                tasks = [
                    asyncio.create_task(process_chunk(start_idx + offset, chunk))
                    for offset, chunk in enumerate(batch)
                ]
                batch_results = await asyncio.gather(*tasks)
                collected_results.extend(batch_results)

                if start_idx + batch_size < len(chunks):
                    await asyncio.sleep(delay)
            return collected_results

        merged_results = loop.run_until_complete(process_all_chunks())
        for chunk_result in merged_results:
            if chunk_result:
                results_map.update(chunk_result)
    finally:
        loop.close()
        asyncio.set_event_loop(None)

    return results_map


def persist_reanalyze_payload(latest_file: Path, data: dict[str, Any]) -> None:
    """재분석 반영 결과를 파일로 저장한다."""
    data["updated_at"] = datetime.now().isoformat()
    atomic_write_text(
        str(latest_file),
        json.dumps(data, indent=2, ensure_ascii=False),
    )


def _load_json_dict(path: Path, logger: logging.Logger | None = None) -> dict[str, Any]:
    try:
        payload = load_json_payload_from_path(str(path))
        if isinstance(payload, dict):
            return payload
    except Exception as error:
        if logger is not None:
            logger.warning(f"Failed to load JSON payload ({path.name}): {error}")
    return {}


def execute_jongga_gemini_reanalysis(
    req_data: dict[str, Any],
    data_dir: str | Path,
    select_signals_for_reanalysis: Callable[..., list[dict[str, Any]]],
    build_jongga_news_analysis_items: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
    apply_gemini_reanalysis_results: Callable[..., int],
    logger: logging.Logger,
) -> tuple[int, dict[str, Any]]:
    """종가 뉴스 Gemini 재분석 파이프라인."""
    try:
        target_tickers, force_update = parse_jongga_reanalyze_request_options(req_data)
        data, all_signals, latest_file = load_jongga_signals_for_reanalysis(
            data_dir=data_dir,
            logger=logger,
        )

        signals_to_process = select_signals_for_reanalysis(
            all_signals=all_signals,
            target_tickers=target_tickers,
            force_update=force_update,
        )
        logger.info(
            "[Gemini Reanalyze] force=%s target_tickers=%d selected=%d total=%d",
            force_update,
            len(target_tickers),
            len(signals_to_process),
            len(all_signals),
        )

        if not signals_to_process:
            return 200, {
                "status": "success",
                "message": "모든 종목에 AI 분석이 완료되어 있습니다. 재분석이 필요하면 force=true 옵션을 사용하세요.",
            }

        from engine.config import app_config
        from engine.llm_analyzer import LLMAnalyzer

        analyzer = LLMAnalyzer()
        items_to_analyze = build_jongga_news_analysis_items(signals_to_process)
        market_status = load_market_status_for_reanalysis(logger=logger)
        results_map = run_jongga_news_reanalysis_batch(
            analyzer=analyzer,
            app_config=app_config,
            items_to_analyze=items_to_analyze,
            market_status=market_status,
            logger=logger,
        )

        updated_count = apply_gemini_reanalysis_results(
            all_signals=all_signals,
            results_map=results_map,
        )
        persist_reanalyze_payload(latest_file=latest_file, data=data)

        return 200, {
            "status": "success",
            "message": f"{updated_count}개 종목의 Gemini 분석이 완료되었습니다.",
        }
    except (FileNotFoundError, ValueError) as e:
        return 404, {"status": "error", "error": str(e)}
    except ImportError as e:
        return 500, {"status": "error", "error": f"LLM 모듈 로드 실패: {e}"}
    except Exception as e:
        logger.exception(f"Error reanalyzing gemini all: {e}")
        return 500, {"status": "error", "error": str(e)}
