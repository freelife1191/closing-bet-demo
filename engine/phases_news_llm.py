#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Signal Generation Phases (News/LLM)

Phase2(뉴스 수집) / Phase3(LLM 배치 분석) 로직을 담당합니다.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List

from engine.constants import LLM as LLM_THRESHOLD
from engine.llm_analyzer import LLMAnalyzer
from engine.phases_base import BasePhase

logger = logging.getLogger(__name__)


def _adapt_to_jongga_signal(item: Dict[str, Any]) -> Dict[str, Any]:
    """Phase1+2 결과 item을 종가베팅(jongga) 재분석과 동일한 dict 형태로 변환.

    매일 종가베팅 생성 파이프라인의 Phase3 입력은 stock=StockData 객체,
    supply=SupplyData 객체, score는 별도 키(pre_score)로 분리된 형태이지만,
    재분석/jongga 프롬프트가 기대하는 입력은 stock=dict(score/score_details
    inline), supply=dict(foreign_buy_5d/inst_buy_5d) 형태이다.

    이 어댑터는 양쪽 입력 shape의 차이만 흡수한다. 별도 계산은 하지 않는다.
    """
    stock_obj = item.get("stock")
    pre_score = item.get("pre_score")
    score_details = item.get("score_details") or {}
    supply_obj = item.get("supply")
    news = item.get("news") or []

    def _g(obj: Any, attr: str, default: Any = 0) -> Any:
        if obj is None:
            return default
        return getattr(obj, attr, default)

    score = {
        "total": _g(pre_score, "total", 0),
        "news": _g(pre_score, "news", 0),
        "volume": _g(pre_score, "volume", 0),
        "chart": _g(pre_score, "chart", 0),
        "candle": _g(pre_score, "candle", 0),
        "timing": _g(pre_score, "timing", 0),
        "supply": _g(pre_score, "supply", 0),
    }

    signal_stock: Dict[str, Any] = {
        "stock_code": _g(stock_obj, "code", "") or "",
        "stock_name": _g(stock_obj, "name", "") or "",
        "current_price": _g(stock_obj, "close", 0) or 0,
        "change_pct": _g(stock_obj, "change_pct", 0) or 0,
        "trading_value": _g(stock_obj, "trading_value", 0) or 0,
        "score": score,
        "score_details": score_details,
    }

    foreign = inst = None
    if supply_obj is not None:
        foreign = getattr(supply_obj, "foreign_buy_5d", None)
        inst = getattr(supply_obj, "inst_buy_5d", None)
    if foreign is None:
        foreign = score_details.get("foreign_net_buy", 0)
    if inst is None:
        inst = score_details.get("inst_net_buy", 0)

    supply_dict = {
        "foreign_buy_5d": int(foreign or 0),
        "inst_buy_5d": int(inst or 0),
    }

    return {"stock": signal_stock, "news": news, "supply": supply_dict}


class Phase2NewsCollector(BasePhase):
    """
    2단계: 뉴스 수집

    - 필터링된 후보 종목의 뉴스 수집
    - 뉴스 없는 종목 제외
    """

    def __init__(self, news_collector, max_news_per_stock: int = 3):
        super().__init__("Phase2: News Collection")
        self.news_collector = news_collector
        self.max_news_per_stock = max_news_per_stock
        self.no_news_count = 0

    async def execute(self, items: List[Dict]) -> List[Dict]:
        """뉴스 수집 실행."""
        self.stats["processed"] += len(items)
        results = []

        for item in items:
            self._check_stop_requested()

            try:
                stock = item['stock']
                news_list = await self.news_collector.get_stock_news(
                    stock.code,
                    self.max_news_per_stock,
                    stock.name,
                )

                if news_list:
                    item['news'] = news_list
                    results.append(item)
                    self.stats["passed"] += 1
                    logger.debug(f"[News] {stock.name}: {len(news_list)} collected")
                else:
                    self.no_news_count += 1
                    self.stats["failed"] += 1
                    logger.debug(f"[No News] {stock.name}")

            except Exception as e:
                logger.debug(f"News collection failed: {e}")
                self.stats["failed"] += 1

        logger.info(
            f"[Phase 2] Complete: {self.stats['passed']} with news, "
            f"{self.no_news_count} without news"
        )

        return results

    def get_no_news_count(self) -> int:
        """뉴스 없는 종목 수 반환."""
        return self.no_news_count


class Phase3LLMAnalyzer(BasePhase):
    """
    3단계: 배치 LLM 분석

    - 뉴스가 있는 종목을 LLM으로 일괄 분석
    - 청크 단위로 병렬 처리
    - Rate Limit 방지를 위한 지연 시간 적용
    """

    def __init__(
        self,
        llm_analyzer: LLMAnalyzer,
        chunk_size: int = None,
        concurrency: int = None,
        request_delay: float = None,
    ):
        super().__init__("Phase3: LLM Analysis")
        self.llm_analyzer = llm_analyzer

        self.chunk_size = chunk_size or LLM_THRESHOLD.CHUNK_SIZE_ANALYSIS
        self.concurrency = concurrency or LLM_THRESHOLD.CONCURRENCY_ANALYSIS
        self.request_delay = request_delay or LLM_THRESHOLD.REQUEST_DELAY

    async def execute(self, items: List[Dict], market_status: Dict = None) -> Dict[str, Dict]:
        """LLM 배치 분석 실행."""
        self.stats["processed"] += len(items)

        if not self.llm_analyzer.client or not items:
            logger.info("[Phase 3] Skipped: No LLM client or items")
            return {}

        chunks = self._create_chunks(items, self.chunk_size)
        total_chunks = len(chunks)

        logger.info(f"[Phase 3] Processing {len(items)} items in {total_chunks} chunks...")

        semaphore = asyncio.Semaphore(self.concurrency)
        results = {}

        async def process_chunk(chunk_idx: int, chunk_data: List[Dict]) -> Dict:
            async with semaphore:
                self._check_stop_requested()

                start = time.time()
                logger.info(
                    f"[LLM Batch] Chunk {chunk_idx}/{total_chunks} ({len(chunk_data)} stocks)..."
                )

                try:
                    # 종가베팅 매일 생성 파이프라인은 reanalyze와 완전히 동일한
                    # 입력 shape(dict)으로 변환한 뒤 jongga 전용 프롬프트를 호출한다.
                    # (VCP 메타 누설 제거 + 19점 만점 명시 + 5섹션 350자 강제)
                    adapted_chunk = [_adapt_to_jongga_signal(it) for it in chunk_data]
                    chunk_result = await self.llm_analyzer.analyze_news_batch_jongga(
                        adapted_chunk, market_status
                    )

                    if self.request_delay > 0:
                        await asyncio.sleep(self.request_delay)

                    elapsed = time.time() - start
                    logger.info(f"[LLM Batch] Chunk {chunk_idx} done in {elapsed:.2f}s")
                    self.stats["passed"] += len(chunk_result)
                    return chunk_result

                except Exception as e:
                    logger.warning(f"[LLM Batch] Chunk {chunk_idx} error: {e}")
                    self.stats["failed"] += len(chunk_data)
                    return {}

        tasks = [process_chunk(i, chunk) for i, chunk in enumerate(chunks, 1)]
        chunk_results = await asyncio.gather(*tasks)

        for result in chunk_results:
            if result:
                results.update(result)

        logger.info(
            f"[Phase 3] Complete: {len(results)} stocks analyzed, "
            f"{self.stats['failed']} failed"
        )

        return results

    def _create_chunks(self, items: List[Any], size: int) -> List[List[Any]]:
        """리스트를 청크로 분할."""
        return [items[i:i + size] for i in range(0, len(items), size)]
