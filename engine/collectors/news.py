#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
News Collector Module

네이버 금융, 네이버 뉴스 검색, 다음 뉴스 검색을 통해 종목 뉴스를 수집합니다.

Created: 2026-02-11
Refactored from: engine/collectors.py (EnhancedNewsCollector class)
"""
import logging
from typing import List, Dict, Optional
from datetime import datetime

from engine.collectors.base import BaseCollector, CollectorError
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
            referer='https://finance.naver.com/'
        )

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
        name: str = None
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
            import requests
            from bs4 import BeautifulSoup

            stock_name = name or self._get_stock_name(code)
            all_news = []
            seen_titles = set()

            # 수집 목록 (각 소스별 최대 수집 개수 - limit보다 넉넉하게)
            SOURCE_LIMIT = limit * 2

            # 1. 네이버 금융 종목 뉴스 페이지
            try:
                naver_finance_news = self._fetch_naver_finance_news(code, SOURCE_LIMIT, seen_titles)
                all_news.extend(naver_finance_news)
            except Exception as e:
                logger.debug(f"네이버 금융 뉴스 수집 실패: {e}")

            # 2. 네이버 뉴스 검색
            if stock_name:
                try:
                    naver_search_news = self._fetch_naver_search_news(
                        stock_name, SOURCE_LIMIT, seen_titles
                    )
                    all_news.extend(naver_search_news)
                except Exception as e:
                    logger.debug(f"네이버 뉴스 검색 실패: {e}")

            # 3. 다음 뉴스 검색
            if stock_name:
                try:
                    daum_search_news = self._fetch_daum_search_news(
                        stock_name, SOURCE_LIMIT, seen_titles
                    )
                    all_news.extend(daum_search_news)
                except Exception as e:
                    logger.debug(f"다음 뉴스 검색 실패: {e}")

            if not all_news:
                return []

            # 통합 정렬 (가중치 기준)
            sorted_news = sorted(all_news, key=lambda x: x.weight, reverse=True)

            final_news = sorted_news[:limit]

            # 로그 출력 (디버깅용)
            sources_summary = [f"{n.source}({n.weight})" for n in final_news]
            logger.info(f"뉴스 수집 완료: {stock_name} -> {len(final_news)}개 [{', '.join(sources_summary[:3])}...]")

            return final_news

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
        import requests
        from bs4 import BeautifulSoup

        url = f'https://finance.naver.com/item/news_news.naver?code={code}'

        headers_finance = self.headers.copy()
        headers_finance['Referer'] = f'https://finance.naver.com/item/news.naver?code={code}'

        response = requests.get(url, headers=headers_finance, timeout=5)

        if not response.ok:
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        news_table = soup.select_one('table.type5')

        if not news_table:
            return []

        results = []
        for row in news_table.select('tr'):
            title_el = row.select_one('td.title a')
            if not title_el:
                continue

            title = title_el.text.strip()
            if not title or title in seen_titles:
                continue

            news_url = title_el.get('href', '')
            if news_url and not news_url.startswith('http'):
                news_url = f'https://finance.naver.com{news_url}'

            source_el = row.select_one('td.info')
            source = source_el.text.strip() if source_el else '네이버금융'

            seen_titles.add(title)
            results.append(NewsItem(
                title=title,
                summary=title,
                source=source,
                url=news_url,
                published_at=datetime.now(),
                weight=self._get_weight(source, platform='finance')
            ))

            if len(results) >= limit:
                break

        return results

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
        import requests
        from bs4 import BeautifulSoup

        search_url = f'https://search.naver.com/search.naver?where=news&query={stock_name}&sort=1'
        response = requests.get(search_url, headers=self.headers, timeout=5)

        if not response.ok:
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        items = soup.select('div.news_wrap') or soup.select('li.bx') or soup.select('div.news_area')

        results = []
        for item in items:
            title_el = item.select_one('a.news_tit')
            if not title_el:
                continue

            title = title_el.get('title') or title_el.text.strip()
            if not title or title in seen_titles:
                continue

            source_el = (
                item.select_one('a.info.press') or
                item.select_one('span.info.press') or
                item.select_one('a.press')
            )
            source = source_el.text.strip().replace('언론사 선정', '') if source_el else '네이버검색'

            seen_titles.add(title)
            results.append(NewsItem(
                title=title,
                summary=title,
                source=source,
                url=title_el.get('href', ''),
                published_at=datetime.now(),
                weight=self._get_weight(source, platform='search_naver')
            ))

            if len(results) >= limit:
                break

        return results

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
        import requests
        from bs4 import BeautifulSoup

        daum_url = f'https://search.daum.net/search?w=news&q={stock_name}&sort=recency'
        response = requests.get(daum_url, headers=self.headers, timeout=5)

        if not response.ok:
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        items = soup.select('div.c-item-content') or soup.select('ul.list_news > li')

        results = []
        for item in items:
            link = item.select_one('a.item-title') or item.select_one('a.f_link_b') or item.select_one('a.tit_main')
            if not link:
                continue

            title = link.text.strip()
            if not title or title in seen_titles:
                continue

            source_el = item.select_one('span.txt_info') or item.select_one('a.txt_info')
            source = source_el.text.strip() if source_el else '다음검색'

            seen_titles.add(title)
            results.append(NewsItem(
                title=title,
                summary=title,
                source=source,
                url=link.get('href', ''),
                published_at=datetime.now(),
                weight=self._get_weight(source, platform='search_daum')
            ))

            if len(results) >= limit:
                break

        return results

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
        publisher_weight = 0.7  # 기본값

        for major_source, weight in self.MAJOR_SOURCES.items():
            if major_source in source:
                publisher_weight = weight
                break

        platform_score = self.PLATFORM_RELIABILITY.get(platform, 0.8)

        return round(publisher_weight * platform_score, 2)

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
