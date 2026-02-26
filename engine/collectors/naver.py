#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Naver Finance Collector Module

네이버 금융에서 종목 상세 정보(투자 지표, 재무 정보, 52주 범위 등)를 수집합니다.

Created: 2026-02-11
Refactored from: engine/collectors.py (NaverFinanceCollector class)
"""

from __future__ import annotations

import logging
import os
import threading
from collections import OrderedDict
from datetime import datetime
from typing import Any, Dict, List, Optional

from engine.collectors.base import BaseCollector
from engine.collectors.naver_extractors_mixin import NaverExtractorsMixin
from engine.collectors.naver_pykrx_mixin import NaverPykrxMixin
from engine.collectors.naver_request_mixin import NaverRequestMixin
from services.kr_market_data_cache_sqlite_payload import (
    load_json_payload_from_sqlite as _load_json_payload_from_sqlite,
    save_json_payload_to_sqlite as _save_json_payload_to_sqlite,
)


logger = logging.getLogger(__name__)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class NaverFinanceCollector(
    NaverRequestMixin,
    NaverExtractorsMixin,
    NaverPykrxMixin,
    BaseCollector,
):
    """
    네이버 금융 상세 정보 수집기

    네이버 금융 웹사이트에서 종목 상세 정보를 수집합니다:
    - 시세 정보 (현재가, 전일가, 시가, 고가, 저가)
    - 52주 최고/최저가
    - 투자 지표 (PER, PBR, ROE 등)
    - 시가총액
    - 투자자 동향
    """
    _naver_cache_lock = threading.Lock()
    _naver_cache: OrderedDict[tuple[str, str, str], dict[str, object]] = OrderedDict()
    _naver_cache_max_entries = 2_048
    _naver_sqlite_max_rows = 8_192
    _naver_cache_interval_minutes = 60
    _naver_sqlite_schema_version = "naver_finance_collector_v1"

    def __init__(self, config=None):
        """
        Args:
            config: 설정 객체
        """
        super().__init__(config)
        self.headers = self._build_default_headers(referer="https://finance.naver.com/")

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
    def _current_cache_slot(cls, now: datetime | None = None) -> str:
        normalized_now = now or datetime.now()
        interval_minutes = max(1, int(cls._naver_cache_interval_minutes))
        minute_bucket = (normalized_now.minute // interval_minutes) * interval_minutes
        return normalized_now.replace(minute=minute_bucket, second=0, microsecond=0).strftime("%Y%m%d%H%M")

    @classmethod
    def _cache_sqlite_context(
        cls,
        *,
        namespace: str,
        code: str,
        cache_slot: str,
    ) -> tuple[str, tuple[int, int]]:
        code_key = str(code).zfill(6)
        namespace_key = str(namespace or "unknown").strip().lower() or "unknown"
        slot_key = str(cache_slot or "latest")
        sqlite_key = os.path.join(
            BASE_DIR,
            "data",
            ".naver_finance_cache",
            namespace_key,
            f"{code_key}__{slot_key}.snapshot",
        )
        signature_seed = (
            f"{namespace_key}:{code_key}:{slot_key}:{cls._naver_sqlite_schema_version}"
        )
        signature = (
            cls._stable_token_to_int(signature_seed),
            cls._stable_token_to_int(f"naver::{signature_seed[::-1]}"),
        )
        return sqlite_key, signature

    @classmethod
    def _load_cached_payload(
        cls,
        *,
        namespace: str,
        code: str,
        cache_slot: str,
    ) -> dict[str, object] | None:
        namespace_key = str(namespace or "unknown").strip().lower() or "unknown"
        code_key = str(code).zfill(6)
        slot_key = str(cache_slot or "latest")
        memory_key = (namespace_key, code_key, slot_key)

        with cls._naver_cache_lock:
            payload = cls._naver_cache.get(memory_key)
            if isinstance(payload, dict):
                cls._naver_cache.move_to_end(memory_key)
                return dict(payload)

        sqlite_key, sqlite_signature = cls._cache_sqlite_context(
            namespace=namespace_key,
            code=code_key,
            cache_slot=slot_key,
        )
        try:
            loaded, payload = _load_json_payload_from_sqlite(
                filepath=sqlite_key,
                signature=sqlite_signature,
                logger=logger,
            )
        except Exception as error:
            logger.debug("NaverFinanceCollector cache load failed (%s/%s): %s", namespace_key, code_key, error)
            return None

        if not loaded or not isinstance(payload, dict):
            return None

        with cls._naver_cache_lock:
            cls._naver_cache[memory_key] = payload
            cls._naver_cache.move_to_end(memory_key)
            while len(cls._naver_cache) > cls._naver_cache_max_entries:
                cls._naver_cache.popitem(last=False)
        return dict(payload)

    @classmethod
    def _save_cached_payload(
        cls,
        *,
        namespace: str,
        code: str,
        cache_slot: str,
        payload: dict[str, object],
    ) -> None:
        namespace_key = str(namespace or "unknown").strip().lower() or "unknown"
        code_key = str(code).zfill(6)
        slot_key = str(cache_slot or "latest")
        memory_key = (namespace_key, code_key, slot_key)

        with cls._naver_cache_lock:
            cls._naver_cache[memory_key] = dict(payload)
            cls._naver_cache.move_to_end(memory_key)
            while len(cls._naver_cache) > cls._naver_cache_max_entries:
                cls._naver_cache.popitem(last=False)

        sqlite_key, sqlite_signature = cls._cache_sqlite_context(
            namespace=namespace_key,
            code=code_key,
            cache_slot=slot_key,
        )
        try:
            _save_json_payload_to_sqlite(
                filepath=sqlite_key,
                signature=sqlite_signature,
                payload=dict(payload),
                max_rows=cls._naver_sqlite_max_rows,
                logger=logger,
            )
        except Exception as error:
            logger.debug("NaverFinanceCollector cache save failed (%s/%s): %s", namespace_key, code_key, error)

    @classmethod
    def _normalize_financial_payload(cls, payload: dict[str, object] | None) -> dict[str, int] | None:
        if not isinstance(payload, dict):
            return None
        try:
            revenue = int(float(payload.get("revenue", 0)))
            operating_profit = int(float(payload.get("operatingProfit", 0)))
            net_income = int(float(payload.get("netIncome", 0)))
        except (TypeError, ValueError):
            return None
        return {
            "revenue": revenue,
            "operatingProfit": operating_profit,
            "netIncome": net_income,
        }

    @classmethod
    def _normalize_themes_payload(cls, payload: dict[str, object] | None) -> list[str] | None:
        if not isinstance(payload, dict):
            return None
        rows = payload.get("themes")
        if not isinstance(rows, list):
            return None
        normalized: list[str] = []
        for item in rows[:5]:
            text = str(item or "").strip()
            if not text or text in normalized:
                continue
            normalized.append(text)
        return normalized

    @classmethod
    def _normalize_stock_detail_payload(cls, payload: dict[str, object] | None) -> dict[str, object] | None:
        if not isinstance(payload, dict):
            return None
        code_value = str(payload.get("code") or "").zfill(6)
        if len(code_value) != 6 or not code_value.isdigit():
            return None
        normalized = dict(payload)
        normalized["code"] = code_value
        return normalized

    async def get_top_gainers(self, market: str, top_n: int, target_date: str = None) -> List:
        """NaverFinanceCollector는 상승률 조회를 지원하지 않음"""
        _ = market, top_n, target_date
        raise NotImplementedError("NaverFinanceCollector does not support get_top_gainers")

    async def get_stock_detail_info(self, code: str) -> Optional[Dict]:
        """
        네이버 금융에서 종목 상세 정보 수집

        수집 항목:
        - 시세 정보: 현재가, 전일가, 시가, 고가, 저가
        - 52주 최고/최저가
        - 투자 지표: PER, PBR, ROE 등
        - 시가총액

        Args:
            code: 종목 코드

        Returns:
            상세 정보 딕셔너리 또는 None
        """
        try:
            normalized_code = str(code).zfill(6)
            cache_slot = self._current_cache_slot()
            cached_payload = self._load_cached_payload(
                namespace="detail_info",
                code=normalized_code,
                cache_slot=cache_slot,
            )
            normalized_cached = self._normalize_stock_detail_payload(cached_payload)
            if normalized_cached is not None:
                return normalized_cached

            from bs4 import BeautifulSoup

            result = self._create_empty_result_dict(normalized_code)
            result["code"] = normalized_code

            url = f"https://finance.naver.com/item/main.naver?code={normalized_code}"
            response = self._request(url, headers=self.headers)

            if not response or not response.ok:
                logger.warning(f"상세 정보 요청 실패: {code}")
                return None

            soup = BeautifulSoup(response.text, "html.parser")

            self._extract_stock_name(soup, result)
            self._extract_market_info(soup, result)
            self._extract_current_price(soup, result)
            self._extract_prev_close(soup, result)
            self._extract_ohlcv(soup, result)
            self._extract_52week_range(soup, result)
            self._extract_indicators(soup, result)
            self._extract_market_cap(soup, result)

            await self._get_investor_trend(normalized_code, result)
            await self._get_fundamental_data(normalized_code, result)

            logger.info(f"상세 정보 수집 완료: {result.get('name', normalized_code)} ({normalized_code})")
            normalized_result = self._normalize_stock_detail_payload(result)
            if normalized_result is not None:
                self._save_cached_payload(
                    namespace="detail_info",
                    code=normalized_code,
                    cache_slot=cache_slot,
                    payload=normalized_result,
                )
                return normalized_result
            return result

        except ImportError as e:
            logger.error(f"requests/BeautifulSoup 미설치: {e}")
            return None
        except Exception as e:
            logger.error(f"상세 정보 수집 실패 ({code}): {e}")
            return None

    async def get_financials(self, code: str) -> Dict:
        """
        재무 정보 수집 (네이버 금융 기업분석)

        Args:
            code: 종목 코드

        Returns:
            재무 정보 딕셔너리
        """
        try:
            normalized_code = str(code).zfill(6)
            cache_slot = self._current_cache_slot()
            cached_payload = self._load_cached_payload(
                namespace="financials",
                code=normalized_code,
                cache_slot=cache_slot,
            )
            normalized_cached = self._normalize_financial_payload(cached_payload)
            if normalized_cached is not None:
                return normalized_cached

            from bs4 import BeautifulSoup

            result = {
                "revenue": 0,
                "operatingProfit": 0,
                "netIncome": 0,
            }

            url = f"https://navercomp.wisereport.co.kr/v2/company/c1010001.aspx?cmp_cd={normalized_code}"
            response = self._request(url, headers=self.headers)

            if response and response.ok:
                soup = BeautifulSoup(response.text, "html.parser")
                tables = soup.select("table.gHead01")

                for table in tables:
                    rows = table.select("tr")
                    for row in rows:
                        th = row.select_one("th")
                        tds = row.select("td")

                        if th and tds:
                            label = th.text.strip()

                            if "매출액" in label and tds:
                                try:
                                    result["revenue"] = float(tds[0].text.replace(",", "").strip()) * 100_000_000
                                except (TypeError, ValueError, AttributeError):
                                    pass
                            elif "영업이익" in label and tds:
                                try:
                                    result["operatingProfit"] = float(tds[0].text.replace(",", "").strip()) * 100_000_000
                                except (TypeError, ValueError, AttributeError):
                                    pass
                            elif ("순이익" in label or "당기순이익" in label) and tds:
                                try:
                                    result["netIncome"] = float(tds[0].text.replace(",", "").strip()) * 100_000_000
                                except (TypeError, ValueError, AttributeError):
                                    pass

            normalized_result = self._normalize_financial_payload(result)
            if normalized_result is not None:
                self._save_cached_payload(
                    namespace="financials",
                    code=normalized_code,
                    cache_slot=cache_slot,
                    payload=normalized_result,
                )
                return normalized_result
            return result

        except Exception as e:
            logger.debug(f"재무정보 수집 실패 ({code}): {e}")
            return {"revenue": 0, "operatingProfit": 0, "netIncome": 0}

    async def get_themes(self, code: str) -> List[str]:
        """
        네이버 금융에서 종목 관련 테마 태그 수집

        예: 원전, SMR, 전력인프라, 반도체 등

        Args:
            code: 종목 코드

        Returns:
            테마 리스트 (최대 5개)
        """
        try:
            normalized_code = str(code).zfill(6)
            cache_slot = self._current_cache_slot()
            cached_payload = self._load_cached_payload(
                namespace="themes",
                code=normalized_code,
                cache_slot=cache_slot,
            )
            normalized_cached = self._normalize_themes_payload(cached_payload)
            if normalized_cached is not None:
                return normalized_cached

            from bs4 import BeautifulSoup

            themes = []
            url = f"https://finance.naver.com/item/main.naver?code={normalized_code}"
            response = self._request(url, headers=self.headers)

            if response and response.ok:
                soup = BeautifulSoup(response.text, "html.parser")

                theme_links = soup.select("div.sub_section th em a, div.sub_section td a")
                for link in theme_links:
                    theme_text = link.text.strip()
                    if theme_text and 2 <= len(theme_text) <= 20:
                        if theme_text not in ["더보기", "차트", "뉴스", "게시판", "종합정보"]:
                            themes.append(theme_text)

                sector_el = soup.select_one("div.section.trade_compare em a")
                if sector_el:
                    sector = sector_el.text.strip()
                    if sector and sector not in themes:
                        themes.append(sector)

                category_links = soup.select("div.wrap_company a")
                for link in category_links:
                    text = link.text.strip()
                    if text and text not in ["KOSPI", "KOSDAQ", "", " "] and len(text) <= 15:
                        if text not in themes:
                            themes.append(text)

            unique_themes = list(dict.fromkeys(themes))[:5]
            if unique_themes:
                logger.info(f"테마 수집 완료: {code} -> {unique_themes}")

            self._save_cached_payload(
                namespace="themes",
                code=normalized_code,
                cache_slot=cache_slot,
                payload={"themes": unique_themes},
            )

            return unique_themes

        except Exception as e:
            logger.debug(f"테마 수집 실패 ({code}): {e}")
            return []


__all__ = ["NaverFinanceCollector"]
