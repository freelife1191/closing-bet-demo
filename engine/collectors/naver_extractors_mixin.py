#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Naver collector HTML extraction mixin
"""

from typing import Dict


class NaverExtractorsMixin:
    """네이버 HTML 파싱 추출 로직을 제공한다."""

    def _create_empty_result_dict(self, code: str) -> Dict:
        """빈 결과 딕셔너리 생성"""
        return {
            "code": code,
            "market": "UNKNOWN",
            "name": "",
            "priceInfo": {
                "current": 0,
                "prevClose": 0,
                "open": 0,
                "high": 0,
                "low": 0,
                "change": 0,
                "change_pct": 0,
                "volume": 0,
                "trading_value": 0,
            },
            "yearRange": {
                "high_52w": 0,
                "low_52w": 0,
            },
            "indicators": {
                "marketCap": 0,
                "per": 0,
                "pbr": 0,
                "eps": 0,
                "bps": 0,
                "dividendYield": 0,
            },
            "investorTrend": {
                "foreign": 0,
                "institution": 0,
                "individual": 0,
            },
            "safety": {
                "debtRatio": 0,
                "currentRatio": 0,
            },
        }

    def _extract_stock_name(self, soup, result: Dict) -> None:
        """종목명 추출"""
        name_el = soup.select_one("div.wrap_company h2 a")
        if name_el:
            result["name"] = name_el.text.strip()

    def _extract_market_info(self, soup, result: Dict) -> None:
        """시장 구분 추출 (KOSPI/KOSDAQ)"""
        market_img = soup.select_one("img.kospi, img.kosdaq, img[alt*='코스피'], img[alt*='코스닥']")
        if market_img:
            alt = market_img.get("alt", "").upper()
            if "KOSDAQ" in alt or "코스닥" in alt:
                result["market"] = "KOSDAQ"
            else:
                result["market"] = "KOSPI"

    def _extract_current_price(self, soup, result: Dict) -> None:
        """현재가 추출"""
        current_price_el = soup.select_one("p.no_today span.blind")
        if current_price_el:
            try:
                result["priceInfo"]["current"] = int(current_price_el.text.replace(",", ""))
            except (TypeError, ValueError, AttributeError):
                pass

    def _extract_prev_close(self, soup, result: Dict) -> None:
        """전일가 추출"""
        prev_close_el = soup.select_one("td.first span.blind")
        if prev_close_el:
            try:
                result["priceInfo"]["prevClose"] = int(prev_close_el.text.replace(",", ""))
            except (TypeError, ValueError, AttributeError):
                pass

    def _extract_ohlcv(self, soup, result: Dict) -> None:
        """시가, 고가, 저가, 거래량 추출"""
        no_info_table = soup.select("table.no_info td span.blind")
        if len(no_info_table) >= 4:
            try:
                result["priceInfo"]["high"] = (
                    int(no_info_table[1].text.replace(",", "")) if no_info_table[1] else 0
                )
                result["priceInfo"]["low"] = (
                    int(no_info_table[3].text.replace(",", "")) if no_info_table[3] else 0
                )
            except (TypeError, ValueError, AttributeError, IndexError):
                pass

    def _extract_52week_range(self, soup, result: Dict) -> None:
        """52주 최고/최저가 추출"""
        aside_info = soup.select("table.tab_con1 tr")
        for tr in aside_info:
            th = tr.select_one("th")
            td = tr.select_one("td")
            if th and td:
                label = th.text.strip()
                value_el = td.select_one("span.blind")
                if value_el:
                    try:
                        value = int(value_el.text.replace(",", ""))
                        if "52주" in label and "최고" in label:
                            result["yearRange"]["high_52w"] = value
                        elif "52주" in label and "최저" in label:
                            result["yearRange"]["low_52w"] = value
                    except (TypeError, ValueError, AttributeError):
                        pass

    def _extract_indicators(self, soup, result: Dict) -> None:
        """투자 지표 추출 (PER, PBR 등)"""
        per_el = soup.select_one("#_per")
        pbr_el = soup.select_one("#_pbr")

        if per_el:
            try:
                result["indicators"]["per"] = float(per_el.text.replace(",", ""))
            except (TypeError, ValueError, AttributeError):
                pass
        if pbr_el:
            try:
                result["indicators"]["pbr"] = float(pbr_el.text.replace(",", ""))
            except (TypeError, ValueError, AttributeError):
                pass

    def _extract_market_cap(self, soup, result: Dict) -> None:
        """시가총액 추출"""
        market_cap_el = soup.select_one("#_market_sum")
        if market_cap_el:
            try:
                cap_text = (
                    market_cap_el.text.replace(",", "").replace("억원", "").replace("조", "").strip()
                )
                result["indicators"]["marketCap"] = int(float(cap_text) * 100_000_000)
            except (TypeError, ValueError, AttributeError):
                pass


__all__ = ["NaverExtractorsMixin"]
