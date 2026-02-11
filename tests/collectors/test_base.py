#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit Tests for Base Collector Module

base.py 모듈의 BaseCollector 클래스와 예외 클래스들을 테스트합니다.

Created: 2026-02-11
"""
import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, patch

from engine.collectors.base import (
    BaseCollector,
    CollectorError,
    DataSourceUnavailableError,
    DataParsingError,
    RateLimitError,
)


# ========================================================================
# Test Helper: Concrete Collector for Testing
# ========================================================================

class ConcreteTestCollector(BaseCollector):
    """테스트용 구체 수집기 클래스"""

    async def get_top_gainers(self, market: str, top_n: int, target_date: str = None) -> list:
        """구체적 구현 (테스트용)"""
        self._require_initialized()
        return []  # 빈 리스트 반환


class TestBaseCollector:
    """BaseCollector 클래스 테스트"""

    # ========================================================================
    # Context Manager Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        """비동기 컨텍스트 매니저 동작 테스트"""
        collector = ConcreteTestCollector()

        # 컨텍스트 매니저 외부에서는 초기화되지 않음
        assert not collector._initialized

        async with collector as c:
            # 내부에서는 초기화됨
            assert c._initialized
            assert c is collector

        # 종료 후 초기화 상태 해제
        assert not collector._initialized

    @pytest.mark.asyncio
    async def test_require_initialized_raises_when_not_initialized(self):
        """초기화되지 않은 상태에서 _require_initialized 호출 시 예외 발생"""
        collector = ConcreteTestCollector()

        # 초기화되지 않은 상태에서 예외 발생
        with pytest.raises(RuntimeError, match="is not initialized"):
            collector._require_initialized()

    # ========================================================================
    # Utility Method Tests
    # ========================================================================

    def test_safe_int_valid_value(self):
        """유효한 정수 변환 테스트"""
        collector = ConcreteTestCollector()
        assert collector._safe_int("123") == 123
        assert collector._safe_int(456) == 456
        assert collector._safe_int(0) == 0

    def test_safe_int_invalid_value(self):
        """무효한 값의 정수 변환 테스트 (기본값 반환)"""
        collector = ConcreteTestCollector()
        assert collector._safe_int("abc") == 0
        assert collector._safe_int(None) == 0
        assert collector._safe_int("") == 0
        assert collector._safe_int("abc", default=99) == 99

    def test_safe_float_valid_value(self):
        """유효한 실수 변환 테스트"""
        collector = ConcreteTestCollector()
        assert collector._safe_float("123.45") == 123.45
        assert collector._safe_float(78.9) == 78.9
        assert collector._safe_float(0) == 0.0

    def test_safe_float_invalid_value(self):
        """무효한 값의 실수 변환 테스트 (기본값 반환)"""
        collector = ConcreteTestCollector()
        assert collector._safe_float("abc") == 0.0
        assert collector._safe_float(None) == 0.0
        assert collector._safe_float("", default=99.9) == 99.9

    def test_safe_str_valid_value(self):
        """유효한 문자열 변환 테스트"""
        collector = ConcreteTestCollector()
        assert collector._safe_str(123) == "123"
        assert collector._safe_str("hello") == "hello"
        assert collector._safe_str(None) == ""
        assert collector._safe_str("", default="N/A") == "N/A"

    def test_parse_date_yyyymmdd_format(self):
        """YYYYMMDD 형식 날짜 파싱 테스트"""
        collector = ConcreteTestCollector()
        result = collector._parse_date("20240115")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_parse_date_yyyy_mm_dd_format(self):
        """YYYY-MM-DD 형식 날짜 파싱 테스트"""
        collector = ConcreteTestCollector()
        result = collector._parse_date("2024-01-15")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_parse_date_invalid_format(self):
        """무효한 날짜 형식 파싱 테스트"""
        collector = ConcreteTestCollector()
        assert collector._parse_date("") is None
        assert collector._parse_date(None) is None
        assert collector._parse_date("invalid") is None

    def test_format_trading_value_trillion(self):
        """조 단위 거래대금 포맷팅 테스트"""
        collector = ConcreteTestCollector()
        assert collector._format_trading_value(1_500_000_000_000) == "1.5조"
        assert collector._format_trading_value(-2_000_000_000_000) == "-2.0조"

    def test_format_trading_value_hundred_million(self):
        """억 단위 거래대금 포맷팅 테스트"""
        collector = ConcreteTestCollector()
        assert collector._format_trading_value(500_000_000) == "5억"
        assert collector._format_trading_value(1_200_000_000) == "12억"
        assert collector._format_trading_value(-5_000_000_000) == "-50억"  # 50억 = 5,000,000,000

    def test_format_trading_value_ten_thousand(self):
        """만 단위 거래대금 포맷팅 테스트"""
        collector = ConcreteTestCollector()
        assert collector._format_trading_value(50_000) == "5만"
        assert collector._format_trading_value(150_000) == "15만"

    def test_format_trading_value_small_value(self):
        """소액 거래대금 포맷팅 테스트"""
        collector = ConcreteTestCollector()
        assert collector._format_trading_value(1000) == "1,000"
        assert collector._format_trading_value(-500) == "-500"

    def test_build_user_agent(self):
        """User-Agent 생성 테스트"""
        collector = ConcreteTestCollector()
        ua = collector._build_user_agent()
        assert "Mozilla" in ua
        assert "Chrome" in ua

    def test_build_default_headers_without_referer(self):
        """기본 헤더 생성 테스트 (Referer 없음)"""
        collector = ConcreteTestCollector()
        headers = collector._build_default_headers()
        assert "User-Agent" in headers
        assert "Accept" in headers
        assert "Connection" in headers
        assert "Referer" not in headers

    def test_build_default_headers_with_referer(self):
        """기본 헤더 생성 테스트 (Referer 포함)"""
        collector = ConcreteTestCollector()
        referer = "https://finance.naver.com/"
        headers = collector._build_default_headers(referer=referer)
        assert headers["Referer"] == referer

    def test_get_latest_market_date_structure(self):
        """_get_latest_market_date 메서드 반환값 구조 테스트"""
        collector = ConcreteTestCollector()
        # 실제 pykrx 호출은 mock하지 않고 형식만 검증
        date_str = collector._get_latest_market_date()
        assert len(date_str) == 8  # YYYYMMDD
        assert date_str.isdigit()


class TestCollectorExceptions:
    """예외 클래스 테스트"""

    def test_collector_error(self):
        """CollectorError 예외 테스트"""
        with pytest.raises(CollectorError):
            raise CollectorError("Test error")

    def test_data_source_unavailable_error(self):
        """DataSourceUnavailableError 예외 테스트"""
        with pytest.raises(DataSourceUnavailableError):
            raise DataSourceUnavailableError("Data source unavailable")

    def test_data_parsing_error(self):
        """DataParsingError 예외 테스트"""
        with pytest.raises(DataParsingError):
            raise DataParsingError("Parsing failed")

    def test_rate_limit_error(self):
        """RateLimitError 예외 테스트"""
        with pytest.raises(RateLimitError):
            raise RateLimitError("Rate limit exceeded")

    def test_exception_inheritance(self):
        """예외 상속 관계 테스트"""
        assert issubclass(DataSourceUnavailableError, CollectorError)
        assert issubclass(DataParsingError, CollectorError)
        assert issubclass(RateLimitError, CollectorError)

    def test_exception_catching_by_base_type(self):
        """기본 예외 타입으로 서브 예외 캐치 테스트"""
        try:
            raise DataSourceUnavailableError("Test")
        except CollectorError:
            pass  # Should catch
        else:
            pytest.fail("Should have been caught by CollectorError")


class TestBaseCollectorAbstractMethod:
    """추상 메서드 테스트"""

    def test_get_top_gainers_is_abstract(self):
        """get_top_gainers가 추상 메서드인지 테스트"""
        # BaseCollector는 추상 클래스이므로 직접 인스턴스화 불가
        with pytest.raises(TypeError):
            BaseCollector()

    @pytest.mark.asyncio
    async def test_concrete_implementation_works(self):
        """구체적 구현 동작 테스트"""
        async with ConcreteTestCollector() as collector:
            result = await collector.get_top_gainers("KOSPI", 50)
            assert result == []


# ========================================================================
# Parametrized Tests
# ========================================================================

class TestBaseCollectorParametrized:
    """매개변수화된 테스트"""

    @pytest.mark.parametrize("input_val,expected", [
        ("123", 123),
        ("0", 0),
        ("-100", -100),
        (456, 456),
    ])
    def test_safe_int_various_inputs(self, input_val, expected):
        """다양한 입력에 대한 _safe_int 테스트"""
        collector = ConcreteTestCollector()
        assert collector._safe_int(input_val) == expected

    @pytest.mark.parametrize("input_val,expected", [
        ("123.45", 123.45),
        ("0.0", 0.0),
        ("-99.9", -99.9),
        (78.9, 78.9),
    ])
    def test_safe_float_various_inputs(self, input_val, expected):
        """다양한 입력에 대한 _safe_float 테스트"""
        collector = ConcreteTestCollector()
        assert collector._safe_float(input_val) == expected

    @pytest.mark.parametrize("input_val,expected", [
        (123, "123"),
        (45.67, "45.67"),
        (True, "True"),
        (None, ""),
        ("", ""),
    ])
    def test_safe_str_various_inputs(self, input_val, expected):
        """다양한 입력에 대한 _safe_str 테스트"""
        collector = ConcreteTestCollector()
        assert collector._safe_str(input_val) == expected

    @pytest.mark.parametrize("date_str,year,month,day", [
        ("20240115", 2024, 1, 15),
        ("20231231", 2023, 12, 31),
        ("20240229", 2024, 2, 29),  # Leap year
    ])
    def test_parse_date_valid_dates(self, date_str, year, month, day):
        """유효한 날짜 파싱 테스트"""
        collector = ConcreteTestCollector()
        result = collector._parse_date(date_str)
        assert result is not None
        assert result.year == year
        assert result.month == month
        assert result.day == day
