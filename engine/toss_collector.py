#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Toss Securities Collector (토스증권 데이터 수집기)
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

import requests

from engine.toss_collector_parsers import (
    parse_financials,
    parse_investment_indicators,
    parse_investor_trend,
    parse_price_details,
    parse_prices_batch,
    parse_stability,
    parse_stock_info,
)


logger = logging.getLogger(__name__)


class TossCollector:
    """토스증권 API를 통한 주식 상세 정보 수집기"""

    BASE_URL = "https://wts-info-api.tossinvest.com/api"
    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
        "Referer": "https://tossinvest.com/",
        "Origin": "https://tossinvest.com",
    }

    def __init__(self, config=None):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update(self.DEFAULT_HEADERS)

    def _format_code(self, code: str) -> str:
        """종목코드를 토스증권 형식으로 변환 (010120 -> A010120)"""
        if not code.startswith("A"):
            return f"A{code}"
        return code

    def _safe_request(
        self,
        url: str,
        method: str = "GET",
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """안전한 API 요청 (재시도 로직 포함)"""
        max_retries = 3
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                if method.upper() == "POST":
                    response = self.session.post(url, json=json_data or {}, timeout=10)
                else:
                    response = self.session.get(url, timeout=10)

                if response.status_code == 200:
                    return response.json()

                if response.status_code == 429:
                    time.sleep(retry_delay * (attempt + 1))
                    continue

                if response.status_code not in [404, 400]:
                    logger.warning(f"토스증권 API 상세 오류: {url} - {response.status_code}")
                else:
                    logger.debug(f"토스증권 API 데이터 없음 (Skip): {url} - {response.status_code}")
                return None
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                logger.error(f"토스증권 API 최종 실패: {url} - {e}")
                return None

        return None

    def get_stock_info(self, code: str) -> dict[str, Any] | None:
        """기본 종목 정보 (마켓, 상장일 등)"""
        toss_code = self._format_code(code)
        url = f"{self.BASE_URL}/v2/stock-infos/{toss_code}"
        data = self._safe_request(url)
        return parse_stock_info(code, data)

    def get_price_details(self, code: str) -> dict[str, Any] | None:
        """가격 상세 정보 (현재가, 1일/52주 범위)"""
        toss_code = self._format_code(code)
        url = f"{self.BASE_URL}/v3/stock-prices/details?productCodes={toss_code}"
        data = self._safe_request(url)
        return parse_price_details(data)

    def get_prices_batch(self, codes: list[str]) -> dict[str, dict[str, Any]]:
        """
        여러 종목의 가격 상세 정보 조회 (Batch)
        Args:
            codes: 종목 코드 리스트 (예: ['005930', '000660'])
        Returns:
            Dict[code, price_detail_dict]
        """
        if not codes:
            return {}

        chunk_size = 20
        results: dict[str, dict[str, Any]] = {}

        for i in range(0, len(codes), chunk_size):
            chunk = codes[i : i + chunk_size]
            toss_codes = [self._format_code(c) for c in chunk]
            codes_str = ",".join(toss_codes)

            url = f"{self.BASE_URL}/v3/stock-prices/details?productCodes={codes_str}"
            data = self._safe_request(url)
            parsed = parse_prices_batch(data)
            if parsed:
                results.update(parsed)

        return results

    def get_investment_indicators(self, code: str) -> dict[str, Any] | None:
        """투자 지표 (PER, PBR, ROE, PSR, 배당수익률, 시가총액)"""
        toss_code = self._format_code(code)
        url = f"{self.BASE_URL}/v1/stock-detail/ui/wts/{toss_code}/investment-indicators"
        data = self._safe_request(url)
        return parse_investment_indicators(data)

    def get_investor_trend(self, code: str, days: int = 5) -> dict[str, Any] | None:
        """투자자 동향 (개인, 외국인, 기관)"""
        toss_code = self._format_code(code)
        url = (
            f"{self.BASE_URL}/v1/stock-infos/trade/trend/trading-trend?"
            f"productCode={toss_code}&size={days}"
        )
        data = self._safe_request(url)
        return parse_investor_trend(data, days)

    def get_financials(self, code: str) -> dict[str, Any]:
        """재무 정보 (매출, 영업이익, 순이익)"""
        toss_code = self._format_code(code)

        revenue_url = f"{self.BASE_URL}/v2/stock-infos/revenue-and-net-profit/{toss_code}"
        revenue_data = self._safe_request(revenue_url, method="POST", json_data={})

        operating_url = f"{self.BASE_URL}/v2/stock-infos/operating-income/{toss_code}"
        operating_data = self._safe_request(operating_url, method="POST", json_data={})

        return parse_financials(revenue_data, operating_data)

    def get_stability(self, code: str) -> dict[str, Any] | None:
        """안정성 지표 (부채비율, 유동비율, 이자보상비율)"""
        toss_code = self._format_code(code)
        url = f"{self.BASE_URL}/v2/stock-infos/stability/{toss_code}"
        data = self._safe_request(url, method="POST", json_data={})
        return parse_stability(data)

    def get_full_stock_detail(self, code: str) -> dict[str, Any]:
        """
        종목의 모든 상세 정보를 한번에 수집
        """
        result = {
            "code": code,
            "name": "",
            "market": "UNKNOWN",
            "fetched_at": datetime.now().isoformat(),
        }

        info = self.get_stock_info(code)
        if info:
            result["name"] = info.get("name", "")
            result["market"] = info.get("market", "UNKNOWN")
            result["sector"] = info.get("sector", "")

        result["price"] = self.get_price_details(code) or {}
        result["indicators"] = self.get_investment_indicators(code) or {}
        result["investor_trend"] = self.get_investor_trend(code) or {}
        result["financials"] = self.get_financials(code) or {}
        result["stability"] = self.get_stability(code) or {}

        return result


__all__ = ["TossCollector"]

