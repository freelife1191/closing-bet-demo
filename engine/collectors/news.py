#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
News Collector Module

네이버 금융, 네이버 뉴스 검색, 다음 뉴스 검색을 통해 종목 뉴스를 수집합니다.

Created: 2026-02-11
Refactored from: engine/collectors.py (EnhancedNewsCollector class)
"""
import logging
import os
import threading
from collections import OrderedDict
from datetime import datetime
from typing import Any, List

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
from services.kr_market_data_cache_sqlite_payload import (
    load_json_payload_from_sqlite as _load_json_payload_from_sqlite,
    save_json_payload_to_sqlite as _save_json_payload_to_sqlite,
)

logger = logging.getLogger(__name__)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


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
    _news_cache_lock = threading.Lock()
    _news_cache: OrderedDict[tuple[str, int, str, str], dict[str, object]] = OrderedDict()
    _news_cache_max_entries = 4_096
    _news_sqlite_max_rows = 16_384
    _news_cache_interval_minutes = 15
    _news_sqlite_schema_version = "enhanced_news_v1"
    _stock_name_cache_lock = threading.Lock()
    _stock_name_cache: OrderedDict[str, str] = OrderedDict()
    _stock_name_cache_max_entries = 4_096
    _stock_name_sqlite_max_rows = 8_192

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
    # SQLite Cache Helpers
    # ========================================================================

    @classmethod
    def _stable_token_to_int(cls, token: str) -> int:
        normalized = str(token or "")
        if normalized.isdigit():
            try:
                return int(normalized)
            except Exception:
                pass
        acc = 17
        for char in normalized:
            acc = (acc * 31 + ord(char)) % 2_000_000_000
        return int(acc)

    @classmethod
    def _current_news_cache_slot(cls, now: datetime | None = None) -> str:
        normalized_now = now or datetime.now()
        interval_minutes = max(1, int(cls._news_cache_interval_minutes))
        minute_bucket = (normalized_now.minute // interval_minutes) * interval_minutes
        return normalized_now.replace(minute=minute_bucket, second=0, microsecond=0).strftime("%Y%m%d%H%M")

    @classmethod
    def _news_sqlite_context(
        cls,
        *,
        code: str,
        limit: int,
        stock_name: str,
        cache_slot: str,
    ) -> tuple[str, tuple[int, int]]:
        code_key = str(code).zfill(6)
        limit_key = max(1, int(limit))
        slot_key = str(cache_slot or "latest")
        sqlite_key = os.path.join(
            BASE_DIR,
            "data",
            ".enhanced_news_cache",
            f"{code_key}__{limit_key}__{slot_key}.snapshot",
        )
        signature_seed = (
            f"{code_key}:{limit_key}:{slot_key}:{str(stock_name or '').strip()}:"
            f"{cls._news_sqlite_schema_version}"
        )
        signature = (
            cls._stable_token_to_int(signature_seed),
            cls._stable_token_to_int(f"news::{signature_seed[::-1]}"),
        )
        return sqlite_key, signature

    @classmethod
    def _serialize_news_items(cls, news_items: List[NewsItem]) -> dict[str, object]:
        rows: list[list[object]] = []
        for item in news_items:
            published_value = ""
            if isinstance(item.published_at, datetime):
                published_value = item.published_at.isoformat()
            rows.append(
                [
                    str(item.title or ""),
                    str(item.source or ""),
                    str(item.url or ""),
                    published_value,
                    float(item.weight or 0.0),
                    str(item.summary or ""),
                ]
            )
        return {"rows": rows}

    @classmethod
    def _deserialize_news_items(cls, payload: dict[str, object]) -> List[NewsItem] | None:
        rows = payload.get("rows")
        if not isinstance(rows, list):
            return None

        news_items: list[NewsItem] = []
        for row in rows:
            if not isinstance(row, (list, tuple)) or len(row) < 6:
                continue
            published_at = None
            published_raw = str(row[3] or "").strip()
            if published_raw:
                try:
                    published_at = datetime.fromisoformat(published_raw)
                except ValueError:
                    published_at = None
            news_items.append(
                NewsItem(
                    title=str(row[0] or ""),
                    source=str(row[1] or ""),
                    url=str(row[2] or ""),
                    published_at=published_at,
                    weight=float(row[4] or 0.0),
                    summary=str(row[5] or ""),
                )
            )
        return news_items

    def _load_cached_news_items(
        self,
        *,
        code: str,
        limit: int,
        stock_name: str,
        cache_slot: str,
    ) -> List[NewsItem] | None:
        code_key = str(code).zfill(6)
        limit_key = max(1, int(limit))
        name_key = str(stock_name or "").strip()
        memory_key = (code_key, limit_key, str(cache_slot), name_key)

        with self._news_cache_lock:
            payload = self._news_cache.get(memory_key)
            if isinstance(payload, dict):
                self._news_cache.move_to_end(memory_key)
                cached_news = self._deserialize_news_items(payload)
                if cached_news is not None:
                    return cached_news
                self._news_cache.pop(memory_key, None)

        sqlite_key, sqlite_signature = self._news_sqlite_context(
            code=code_key,
            limit=limit_key,
            stock_name=name_key,
            cache_slot=cache_slot,
        )
        try:
            loaded, payload = _load_json_payload_from_sqlite(
                filepath=sqlite_key,
                signature=sqlite_signature,
                logger=logger,
            )
        except Exception as error:
            logger.debug("EnhancedNewsCollector SQLite cache load failed (%s): %s", code_key, error)
            return None

        if not loaded or not isinstance(payload, dict):
            return None
        cached_news = self._deserialize_news_items(payload)
        if cached_news is None:
            return None

        with self._news_cache_lock:
            self._news_cache[memory_key] = payload
            self._news_cache.move_to_end(memory_key)
            while len(self._news_cache) > self._news_cache_max_entries:
                self._news_cache.popitem(last=False)
        return cached_news

    def _save_cached_news_items(
        self,
        *,
        code: str,
        limit: int,
        stock_name: str,
        cache_slot: str,
        news_items: List[NewsItem],
    ) -> None:
        code_key = str(code).zfill(6)
        limit_key = max(1, int(limit))
        name_key = str(stock_name or "").strip()
        memory_key = (code_key, limit_key, str(cache_slot), name_key)
        payload = self._serialize_news_items(news_items)

        with self._news_cache_lock:
            self._news_cache[memory_key] = payload
            self._news_cache.move_to_end(memory_key)
            while len(self._news_cache) > self._news_cache_max_entries:
                self._news_cache.popitem(last=False)

        sqlite_key, sqlite_signature = self._news_sqlite_context(
            code=code_key,
            limit=limit_key,
            stock_name=name_key,
            cache_slot=cache_slot,
        )
        try:
            _save_json_payload_to_sqlite(
                filepath=sqlite_key,
                signature=sqlite_signature,
                payload=payload,
                max_rows=self._news_sqlite_max_rows,
                logger=logger,
            )
        except Exception as error:
            logger.debug("EnhancedNewsCollector SQLite cache save failed (%s): %s", code_key, error)

    @classmethod
    def _stock_name_sqlite_context(cls, ticker: str) -> tuple[str, tuple[int, int]]:
        ticker_key = str(ticker).zfill(6)
        sqlite_key = os.path.join(
            BASE_DIR,
            "data",
            ".krx_collector_cache",
            "stock_name",
            f"{ticker_key}.snapshot",
        )
        signature = (
            cls._stable_token_to_int(ticker_key),
            cls._stable_token_to_int("krx_collector_stock_name_v1"),
        )
        return sqlite_key, signature

    @classmethod
    def _set_stock_name_cache(cls, ticker: str, stock_name: str) -> None:
        ticker_key = str(ticker).zfill(6)
        name_value = str(stock_name or "").strip()
        if not ticker_key or not name_value:
            return

        with cls._stock_name_cache_lock:
            cls._stock_name_cache[ticker_key] = name_value
            cls._stock_name_cache.move_to_end(ticker_key)
            while len(cls._stock_name_cache) > cls._stock_name_cache_max_entries:
                cls._stock_name_cache.popitem(last=False)

    @classmethod
    def _load_cached_stock_name(cls, ticker: str) -> str | None:
        ticker_key = str(ticker).zfill(6)
        with cls._stock_name_cache_lock:
            cached = cls._stock_name_cache.get(ticker_key)
            if isinstance(cached, str) and cached:
                cls._stock_name_cache.move_to_end(ticker_key)
                return cached

        sqlite_key, sqlite_signature = cls._stock_name_sqlite_context(ticker_key)
        try:
            loaded, payload = _load_json_payload_from_sqlite(
                filepath=sqlite_key,
                signature=sqlite_signature,
                logger=logger,
            )
        except Exception as error:
            logger.debug("EnhancedNewsCollector stock name SQLite cache load failed (%s): %s", ticker_key, error)
            return None

        if not loaded or not isinstance(payload, dict):
            return None
        cached_name = str(payload.get("name") or "").strip()
        if not cached_name:
            return None
        cls._set_stock_name_cache(ticker_key, cached_name)
        return cached_name

    @classmethod
    def _save_cached_stock_name(cls, ticker: str, stock_name: str) -> None:
        ticker_key = str(ticker).zfill(6)
        normalized_name = str(stock_name or "").strip()
        if not ticker_key or not normalized_name:
            return

        cls._set_stock_name_cache(ticker_key, normalized_name)
        sqlite_key, sqlite_signature = cls._stock_name_sqlite_context(ticker_key)
        try:
            _save_json_payload_to_sqlite(
                filepath=sqlite_key,
                signature=sqlite_signature,
                payload={"name": normalized_name},
                max_rows=cls._stock_name_sqlite_max_rows,
                logger=logger,
            )
        except Exception as error:
            logger.debug("EnhancedNewsCollector stock name SQLite cache save failed (%s): %s", ticker_key, error)

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
            normalized_code = str(code).zfill(6)
            normalized_limit = max(1, int(limit))
            stock_name = name or self._get_stock_name(normalized_code)
            cache_slot = self._current_news_cache_slot()
            cached_news = self._load_cached_news_items(
                code=normalized_code,
                limit=normalized_limit,
                stock_name=stock_name,
                cache_slot=cache_slot,
            )
            if cached_news is not None:
                return cached_news

            result = collect_stock_news_impl(
                code=normalized_code,
                limit=normalized_limit,
                stock_name=stock_name,
                fetch_naver_finance_news_fn=self._fetch_naver_finance_news,
                fetch_naver_search_news_fn=self._fetch_naver_search_news,
                fetch_daum_search_news_fn=self._fetch_daum_search_news,
                logger=logger,
            )
            if isinstance(result, list):
                self._save_cached_news_items(
                    code=normalized_code,
                    limit=normalized_limit,
                    stock_name=stock_name,
                    cache_slot=cache_slot,
                    news_items=result,
                )
            return result

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
        normalized_ticker = str(ticker).zfill(6)
        cached_name = self._load_cached_stock_name(normalized_ticker)
        if cached_name:
            return cached_name

        try:
            from pykrx import stock

            resolved_name = str(stock.get_market_ticker_name(normalized_ticker) or "").strip()
            if resolved_name:
                self._save_cached_stock_name(normalized_ticker, resolved_name)
                return resolved_name
        except Exception as error:
            logger.debug(f"뉴스 종목명 pykrx 조회 실패 ({normalized_ticker}): {error}")

        names = {
            "005930": "삼성전자",
            "000270": "기아",
            "035420": "NAVER",
            "005380": "현대차",
            "015760": "한화사이언스",
        }
        fallback_name = names.get(normalized_ticker, "알 수 없는 종목")
        if fallback_name != "알 수 없는 종목":
            self._save_cached_stock_name(normalized_ticker, fallback_name)
        return fallback_name
