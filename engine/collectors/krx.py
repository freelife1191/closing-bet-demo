#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KRX Collector Module

KRX(한국거래소) 데이터를 수집하는 클래스입니다.
"""

from __future__ import annotations

import logging

from engine.collectors.base import BaseCollector
from engine.collectors.krx_data_mixin import KRXCollectorDataMixin


logger = logging.getLogger(__name__)


class KRXCollector(KRXCollectorDataMixin, BaseCollector):
    """KRX 데이터 수집기."""

    _market_date_warning_shown = False

    def __init__(self, config=None):
        super().__init__(config)
        self._stock_name_cache: dict[str, str] = {}
        self._sector_cache: dict[str, str] = {}

    def _get_stock_name(self, ticker: str) -> str:
        """종목명 조회 (pykrx 사용)."""
        normalized = str(ticker).zfill(6)
        cached = self._stock_name_cache.get(normalized)
        if cached:
            return cached

        try:
            from pykrx import stock

            name = stock.get_market_ticker_name(normalized)
            if name:
                self._stock_name_cache[normalized] = name
                return name
        except Exception as error:
            logger.debug(f"종목명 조회 실패 ({normalized}): {error}")

        names = {
            "005930": "삼성전자",
            "000270": "기아",
            "035420": "NAVER",
            "005380": "현대차",
            "015760": "한화사이언스",
            "068270": "셀트리온",
            "052190": "삼성에스디에스",
            "011200": "HMM",
            "096770": "SK이노베이션",
            "066570": "LG전자",
            "056080": "유진로봇",
        }
        fallback_name = names.get(normalized, "알 수 없는 종목")
        self._stock_name_cache[normalized] = fallback_name
        return fallback_name

    def _get_sector(self, ticker: str) -> str:
        """섹터 조회."""
        normalized = str(ticker).zfill(6)
        cached = self._sector_cache.get(normalized)
        if cached:
            return cached

        try:
            from pykrx import stock

            pass
        except Exception as error:
            logger.debug(f"섹터 조회 기본 경로 실패 ({normalized}): {error}")

        sectors = {
            "005930": "반도체",
            "000270": "자동차",
            "035420": "인터넷",
            "005380": "자동차",
            "015760": "반도체",
            "068270": "헬스케어",
            "052190": "반도체",
            "011200": "해운",
            "096770": "통신",
            "066570": "2차전지",
            "056080": "로봇",
        }
        fallback_sector = sectors.get(normalized, "기타")
        self._sector_cache[normalized] = fallback_sector
        return fallback_sector
