#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Naver Finance Collector Module

네이버 금융에서 종목 상세 정보(투자 지표, 재무 정보, 52주 범위 등)를 수집합니다.

Created: 2026-02-11
Refactored from: engine/collectors.py (NaverFinanceCollector class)
"""

import logging
from typing import Dict, List, Optional

from engine.collectors.base import BaseCollector
from engine.collectors.naver_extractors_mixin import NaverExtractorsMixin
from engine.collectors.naver_pykrx_mixin import NaverPykrxMixin
from engine.collectors.naver_request_mixin import NaverRequestMixin


logger = logging.getLogger(__name__)


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

    def __init__(self, config=None):
        """
        Args:
            config: 설정 객체
        """
        super().__init__(config)
        self.headers = self._build_default_headers(referer="https://finance.naver.com/")

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
            from bs4 import BeautifulSoup

            result = self._create_empty_result_dict(code)
            result["code"] = code

            url = f"https://finance.naver.com/item/main.naver?code={code}"
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

            await self._get_investor_trend(code, result)
            await self._get_fundamental_data(code, result)

            logger.info(f"상세 정보 수집 완료: {result.get('name', code)} ({code})")
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
            from bs4 import BeautifulSoup

            result = {
                "revenue": 0,
                "operatingProfit": 0,
                "netIncome": 0,
            }

            url = f"https://navercomp.wisereport.co.kr/v2/company/c1010001.aspx?cmp_cd={code}"
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
            from bs4 import BeautifulSoup

            themes = []
            url = f"https://finance.naver.com/item/main.naver?code={code}"
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

            return unique_themes

        except Exception as e:
            logger.debug(f"테마 수집 실패 ({code}): {e}")
            return []


__all__ = ["NaverFinanceCollector"]
