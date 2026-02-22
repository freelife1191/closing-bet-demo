#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - LLM Utilities (Batch Processing)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, List


logger = logging.getLogger(__name__)


async def process_batch_with_concurrency(
    items: List[Any],
    processor: Callable,
    concurrency: int = 3,
    delay_between_chunks: float = 0.0,
) -> List[Any]:
    """
    동시성 제어를 적용한 배치 처리.
    """

    semaphore = asyncio.Semaphore(concurrency)
    results = []

    async def process_with_semaphore(item, index):
        async with semaphore:
            try:
                result = await processor(item)
                return (index, result)
            except Exception as error:
                logger.warning(f"Item {index} processing failed: {error}")
                return (index, None)

    tasks = [process_with_semaphore(item, i) for i, item in enumerate(items)]
    chunk_size = concurrency

    for i in range(0, len(tasks), chunk_size):
        chunk = tasks[i : i + chunk_size]
        chunk_results = await asyncio.gather(*chunk)
        results.extend(chunk_results)

        if delay_between_chunks > 0 and i + chunk_size < len(tasks):
            await asyncio.sleep(delay_between_chunks)

    results.sort(key=lambda item: item[0])
    return [item[1] for item in results]


__all__ = ["process_batch_with_concurrency"]
