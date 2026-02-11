#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Collectors Package

데이터 수집기 모듈들을 통합하여 제공합니다.

Created: 2026-02-11
Refactored from: engine/collectors.py (1,005 lines)

Module Structure:
    base.py     - BaseCollector abstract class and exceptions
    krx.py      - KRXCollector (pykrx 기반 한국 주식 데이터)
    news.py     - EnhancedNewsCollector (네이버/다음 뉴스 수집)
    naver.py    - NaverFinanceCollector (네이버 금융 상세 정보)

Usage:
    from engine.collectors import (
        BaseCollector,
        KRXCollector,
        EnhancedNewsCollector,
        NaverFinanceCollector,
        CollectorError,
        DataSourceUnavailableError,
    )

    async with KRXCollector(config) as collector:
        top_gainers = await collector.get_top_gainers('KOSPI', 50)
"""

# Version tracking for refactored module
__version__ = "2.0.0"
__refactored_date__ = "2026-02-11"
__original_file__ = "engine/collectors.py"

# ========================================================================
# Base Classes and Exceptions
# ========================================================================

from engine.collectors.base import (
    BaseCollector,
    CollectorError,
    DataSourceUnavailableError,
    DataParsingError,
    RateLimitError,
)

# ========================================================================
# Concrete Collectors
# ========================================================================

from engine.collectors.krx import KRXCollector
from engine.collectors.news import EnhancedNewsCollector
from engine.collectors.naver import NaverFinanceCollector

# ========================================================================
# Public API Export
# ========================================================================

__all__ = [
    # Base
    'BaseCollector',

    # Collectors
    'KRXCollector',
    'EnhancedNewsCollector',
    'NaverFinanceCollector',

    # Exceptions
    'CollectorError',
    'DataSourceUnavailableError',
    'DataParsingError',
    'RateLimitError',
]

# ========================================================================
# Convenience Factory Functions
# ========================================================================

def create_collector(type_: str, config=None) -> BaseCollector:
    """
    팩토리 함수: 타입에 따라 적절한 수집기 생성

    Args:
        type_: 수집기 타입 ('krx', 'news', 'naver')
        config: 설정 객체

    Returns:
        BaseCollector 인스턴스

    Raises:
        ValueError: 지원하지 않는 타입인 경우

    Example:
        >>> collector = create_collector('krx', config)
        >>> async with collector:
        ...     data = await collector.get_top_gainers('KOSPI', 50)
    """
    collectors = {
        'krx': KRXCollector,
        'news': EnhancedNewsCollector,
        'naver': NaverFinanceCollector,
    }

    collector_class = collectors.get(type_.lower())
    if not collector_class:
        raise ValueError(
            f"Unknown collector type: {type_}. "
            f"Supported types: {list(collectors.keys())}"
        )

    return collector_class(config)


# Backward compatibility: 기존 코드와의 호환을 위해
# 이 파일은 기존 collectors.py의 모든 공개 API를 제공해야 합니다.
# 기존 코드에서 다음과 같이 import하는 경우를 지원:
#   from engine.collectors import KRXCollector, EnhancedNewsCollector, NaverFinanceCollector
