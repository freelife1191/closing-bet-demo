#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Naver collector HTTP request mixin
"""

import logging
import time
from typing import Dict

import requests


logger = logging.getLogger(__name__)


class NaverRequestMixin:
    """네이버 요청 재시도 로직을 제공한다."""

    def _request(self, url: str, headers: Dict = None, timeout: int = 10, retries: int = 3):
        """
        HTTP 요청 헬퍼 (재시도 로직 포함)

        Args:
            url: 요청 URL
            headers: 헤더
            timeout: 타임아웃 (초)
            retries: 재시도 횟수

        Returns:
            Response 객체 또는 None
        """
        for attempt in range(retries):
            try:
                response = requests.get(url, headers=headers, timeout=timeout)

                if response.status_code == 429:
                    wait_time = (2 ** attempt) * 0.5
                    logger.warning(f"Naver API Rate Limit (429). Waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue

                if 500 <= response.status_code < 600:
                    wait_time = (2 ** attempt) * 0.5
                    logger.warning(
                        f"Naver Server Error ({response.status_code}). Waiting {wait_time}s..."
                    )
                    time.sleep(wait_time)
                    continue

                return response

            except requests.RequestException as e:
                if attempt < retries - 1:
                    wait_time = (2 ** attempt) * 0.5
                    logger.debug(f"Request failed ({e}). Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Request failed after {retries} attempts: {url}")
                    return None

        return None


__all__ = ["NaverRequestMixin"]
