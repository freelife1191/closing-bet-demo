#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
종목 질의 감지 유틸
"""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, Optional


# 한글은 \w 이므로 \b 를 쓰면 「005930은」 같은 조사 붙은 티커를 놓친다.
_TICKER_REGEX = re.compile(r"(?<!\d)\d{6}(?!\d)")
# 두 글자 이하 종목명(대상·레이·TP 등)은 흔한 단어 안에 들어 있으므로 단어 경계에서만 잡는다.
# 뒤에 조사 한 글자는 허용한다. 「대상 종목」처럼 독립 단어로 쓰인 경우는 여전히 잡힌다.
_SHORT_NAME_MAX_LEN = 2
_WORD_CHAR = "가-힣A-Za-z0-9"


def _name_in_message(stock_name: str, message: str) -> bool:
    if len(stock_name) > _SHORT_NAME_MAX_LEN:
        return stock_name in message
    pattern = rf"(?<![{_WORD_CHAR}]){re.escape(stock_name)}[은는이가을를의도에와과로]?(?![{_WORD_CHAR}])"
    return re.search(pattern, message) is not None


def detect_stock_query_from_stock_map(
    message: str,
    stock_map: Dict[str, str],
    ticker_map: Dict[str, str],
    format_stock_context_fn: Callable[[str, str], str],
    logger: Any,
) -> Optional[str]:
    """전체 종목 맵에서 종목명/티커 매칭을 시도한다."""
    if not message:
        return None

    ticker_match = _TICKER_REGEX.search(message)
    if ticker_match:
        ticker = ticker_match.group(0)
        if ticker in ticker_map:
            stock_name = ticker_map[ticker]
            logger.info("Detected stock query by ticker: %s (%s)", stock_name, ticker)
            return format_stock_context_fn(stock_name, ticker)

    # ponytail: 가장 긴 이름 하나만 싣는다. 비교 질문은 한쪽 종목 문맥만 받는다.
    for stock_name in sorted(stock_map.keys(), key=len, reverse=True):
        if stock_name and _name_in_message(stock_name, message):
            ticker = stock_map[stock_name]
            logger.info("Detected stock query by name: %s (%s)", stock_name, ticker)
            return format_stock_context_fn(stock_name, ticker)

    return None


__all__ = [
    "detect_stock_query_from_stock_map",
]
