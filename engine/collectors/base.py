#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Collectors Base Module
"""

from __future__ import annotations

from typing import Any


class BaseCollector:
    """Collector 공통 인터페이스/유틸."""

    def __init__(self, config: Any = None):
        self.config = config

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        _ = exc_type, exc_val, exc_tb
        return None

    @staticmethod
    def _build_default_headers(*, referer: str | None = None) -> dict[str, str]:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,"
                "image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
            ),
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        if referer:
            headers["Referer"] = referer
        return headers

    async def get_top_gainers(self, market: str, top_n: int, target_date: str = None):
        _ = market, top_n, target_date
        raise NotImplementedError


__all__ = ["BaseCollector"]
