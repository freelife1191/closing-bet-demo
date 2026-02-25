#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VCP AI Analyzer orchestration helpers.
"""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable


async def orchestrate_stock_analysis(
    *,
    stock_name: str,
    stock_data: dict[str, Any],
    providers: list[str],
    second_provider: str,
    perplexity_disabled: bool,
    build_prompt_fn: Callable[[str, dict[str, Any]], str],
    analyze_with_gemini_fn: Callable[[str, dict[str, Any], str | None], Awaitable[dict[str, Any] | None]],
    analyze_with_gpt_fn: Callable[[str, dict[str, Any], str | None], Awaitable[dict[str, Any] | None]],
    analyze_with_perplexity_fn: Callable[[str, dict[str, Any], str | None], Awaitable[dict[str, Any] | None]],
    logger: Any,
) -> dict[str, Any]:
    """단일 종목에 대해 멀티 Provider 병렬 분석을 오케스트레이션한다."""
    results = {
        "ticker": stock_data.get("ticker", ""),
        "stock_name": stock_name,
        "gemini_recommendation": None,
        "gpt_recommendation": None,
        "perplexity_recommendation": None,
    }

    tasks: list[Awaitable[dict[str, Any] | None]] = []
    providers_map: list[str] = []
    shared_prompt = build_prompt_fn(stock_name, stock_data)

    skip_gemini = bool(stock_data.get("skip_gemini"))
    skip_second = bool(stock_data.get("skip_second"))
    if "gemini" in providers and not skip_gemini:
        tasks.append(analyze_with_gemini_fn(stock_name, stock_data, shared_prompt))
        providers_map.append("gemini")

    if not skip_second and second_provider == "perplexity" and ("perplexity" in providers or "gpt" in providers):
        if not perplexity_disabled:
            tasks.append(analyze_with_perplexity_fn(stock_name, stock_data, shared_prompt))
            providers_map.append("perplexity")
    elif not skip_second and second_provider == "gpt" and ("gpt" in providers or "openai" in providers):
        tasks.append(analyze_with_gpt_fn(stock_name, stock_data, shared_prompt))
        providers_map.append("gpt")

    if not tasks:
        logger.warning(f"{stock_name}: 실행 가능한 AI Provider가 없습니다.")
        return results

    try:
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        for idx, response in enumerate(responses):
            provider = providers_map[idx]
            if isinstance(response, Exception):
                logger.error(f"[{provider}] {stock_name} 분석 중 예외 발생: {response}")
                continue
            if response:
                results[f"{provider}_recommendation"] = response
            else:
                logger.warning(f"[{provider}] {stock_name} 분석 결과 없음 (None)")
    except Exception as error:
        logger.error(f"{stock_name} AI 병렬 분석 전체 실패: {error}")

    return results


async def analyze_batch_with_limit(
    *,
    stocks: list[dict[str, Any]],
    concurrency: int,
    analyze_stock_fn: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any] | None]],
    logger: Any,
) -> tuple[dict[str, dict[str, Any]], int]:
    """동시성 제한을 적용해 여러 종목을 병렬 분석한다."""
    total = len(stocks)
    sem = asyncio.Semaphore(max(1, int(concurrency)))

    async def _bounded_analyze(stock: dict[str, Any], idx: int):
        async with sem:
            ticker = stock.get("ticker", "")
            name = stock.get("name", ticker)
            try:
                res = await analyze_stock_fn(name, stock)
                logger.info(f"✅ [{idx+1}/{total}] {name} AI 분석 완료")
                return ticker, res
            except Exception as error:
                logger.error(f"❌ [{idx+1}/{total}] {name} 분석 실패: {error}")
                return ticker, None

    tasks = [_bounded_analyze(stocks[idx], idx) for idx in range(total)]
    batch_results = await asyncio.gather(*tasks, return_exceptions=True)

    results: dict[str, dict[str, Any]] = {}
    success_count = 0
    for item in batch_results:
        if isinstance(item, Exception):
            logger.error(f"배치 작업 중 예외 발생: {item}")
            continue
        if item:
            ticker, res = item
            if res:
                results[ticker] = res
                success_count += 1

    return results, success_count


__all__ = ["orchestrate_stock_analysis", "analyze_batch_with_limit"]
