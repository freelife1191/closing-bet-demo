#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
News Collector Module

네이버 금융, 네이버 뉴스 검색, 다음 뉴스 검색을 통해 종목 뉴스를 수집합니다.

Created: 2026-02-11
Refactored from: engine/collectors.py (EnhancedNewsCollector class)
"""
import logging
from typing import List

from engine.collectors.base import BaseCollector
from engine.collectors.news_orchestration_helpers import (
    collect_stock_news as collect_stock_news_impl,
)
from engine.collectors.news_scrape_helpers import (
    fetch_daum_search_news as fetch_daum_search_news_impl,
    fetch_naver_finance_news as fetch_naver_finance_news_impl,
    fetch_naver_search_news as fetch_naver_search_news_impl,
)
from engine.models import NewsItem

logger = logging.getLogger(__name__)


class EnhancedNewsCollector(BaseCollector):
    """
    향상된 뉴스 수집기

    네이버 금융 크롤링 + 네이버/다음 뉴스 검색을 통합하여
    다양한 소스에서 뉴스를 수집합니다.
    """

    # 주요 언론사 가중치
    MAJOR_SOURCES = {
        "한국경제": 0.9,
        "매일경제": 0.9,
        "머니투데이": 0.85,
        "서울경제": 0.85,
        "이데일리": 0.85,
        "연합뉴스": 0.85,
        "뉴스1": 0.8,
        "파이낸셜뉴스": 0.8,
        "아시아경제": 0.8,
        "헤럴드경제": 0.8,
    }

    # 플랫폼별 신뢰도
    PLATFORM_RELIABILITY = {
        "finance": 0.9,      # 네이버 금융 크롤링
        "search_naver": 0.85,  # 네이버 뉴스 검색
        "search_daum": 0.8,   # 다음 뉴스 검색
    }

    def __init__(self, config=None):
        """
        Args:
            config: 설정 객체
        """
        super().__init__(config)
        self.headers = self._build_default_headers(
            referer="https://finance.naver.com/"
        )
        self._major_source_items = tuple(self.MAJOR_SOURCES.items())
        self._weight_cache: dict[tuple[str, str], float] = {}

    # ========================================================================
    # Abstract Method Implementation (not applicable for news collector)
    # ========================================================================

    async def get_top_gainers(self, market: str, top_n: int, target_date: str = None) -> List:
        """뉴스 수집기는 상승률 조회를 지원하지 않음"""
        raise NotImplementedError("News collector does not support get_top_gainers")

    # ========================================================================
    # Public Methods
    # ========================================================================

    async def get_stock_news(
        self,
        code: str,
        limit: int,
        name: str = None,
    ) -> List[NewsItem]:
        """
        종목 뉴스 수집 - 다중 소스 통합

        Args:
            code: 종목 코드
            limit: 수집할 뉴스 개수
            name: (Optional) 종목명

        Returns:
            NewsItem 리스트 (가중치순 정렬)
        """
        try:
            stock_name = name or self._get_stock_name(code)
            return collect_stock_news_impl(
                code=code,
                limit=limit,
                stock_name=stock_name,
                fetch_naver_finance_news_fn=self._fetch_naver_finance_news,
                fetch_naver_search_news_fn=self._fetch_naver_search_news,
                fetch_daum_search_news_fn=self._fetch_daum_search_news,
                logger=logger,
            )

        except ImportError as e:
            logger.error(f"requests/BeautifulSoup 미설치: {e}")
            return []
        except Exception as e:
            logger.error(f"뉴스 수집 전체 실패 ({code}): {e}")
            return []

    # ========================================================================
    # Private Methods - Fetchers
    # ========================================================================

    def _fetch_naver_finance_news(
        self,
        code: str,
        limit: int,
        seen_titles: set
    ) -> List[NewsItem]:
        """
        네이버 금융 종목 뉴스 페이지에서 수집

        Args:
            code: 종목 코드
            limit: 수집 제한
            seen_titles: 이미 본 제목集合 (중복 방지)

        Returns:
            NewsItem 리스트
        """
        return fetch_naver_finance_news_impl(
            code=code,
            limit=limit,
            seen_titles=seen_titles,
            headers=self.headers,
            get_weight_fn=self._get_weight,
        )

    def _fetch_naver_search_news(
        self,
        stock_name: str,
        limit: int,
        seen_titles: set
    ) -> List[NewsItem]:
        """
        네이버 뉴스 검색에서 수집

        Args:
            stock_name: 종목명
            limit: 수집 제한
            seen_titles: 이미 본 제목 집합

        Returns:
            NewsItem 리스트
        """
        return fetch_naver_search_news_impl(
            stock_name=stock_name,
            limit=limit,
            seen_titles=seen_titles,
            headers=self.headers,
            get_weight_fn=self._get_weight,
        )

    def _fetch_daum_search_news(
        self,
        stock_name: str,
        limit: int,
        seen_titles: set
    ) -> List[NewsItem]:
        """
        다음 뉴스 검색에서 수집

        Args:
            stock_name: 종목명
            limit: 수집 제한
            seen_titles: 이미 본 제목 집합

        Returns:
            NewsItem 리스트
        """
        return fetch_daum_search_news_impl(
            stock_name=stock_name,
            limit=limit,
            seen_titles=seen_titles,
            headers=self.headers,
            get_weight_fn=self._get_weight,
        )

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _get_weight(self, source: str, platform: str = 'search_naver') -> float:
        """
        언론사 가중치 + 플랫폼 신뢰도 기반 최종 점수 반환

        Formula: Publisher Weight * Platform Reliability

        Args:
            source: 언론사명
            platform: 플랫폼 (finance, search_naver, search_daum)

        Returns:
            가중치 (0.0 ~ 1.0)
        """
        normalized_source = source or ""
        cache_key = (normalized_source, platform)
        cached = self._weight_cache.get(cache_key)
        if cached is not None:
            return cached

        publisher_weight = 0.7
        for major_source, weight in self._major_source_items:
            if major_source in normalized_source:
                publisher_weight = weight
                break

        platform_score = self.PLATFORM_RELIABILITY.get(platform, 0.8)
        resolved_weight = round(publisher_weight * platform_score, 2)

        if len(self._weight_cache) > 2048:
            self._weight_cache.clear()
        self._weight_cache[cache_key] = resolved_weight
        return resolved_weight

    def _get_stock_name(self, ticker: str) -> str:
        """
        종목명 조회

        Args:
            ticker: 종목 코드

        Returns:
            종목명
        """
        names = {
            '005930': '삼성전자', '000270': '기아', '035420': 'NAVER',
            '005380': '현대차', '015760': '한화사이언스',
        }
        return names.get(ticker, '알 수 없는 종목')
