#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Base Collector Module

추상 기본 클래스를 제공하여 모든 데이터 수집기가 공통 인터페이스를 따르도록 합니다.
이를 통해 OCP(Open/Closed Principle)와 DIP(Dependency Inversion Principle)를 준수합니다.

Created: 2026-02-11
Refactored from: engine/collectors.py
"""
import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta

from engine.models import StockData, ChartData, SupplyData, NewsItem

logger = logging.getLogger(__name__)


class BaseCollector(ABC):
    """
    데이터 수집기 추상 기본 클래스

    모든 수집기는 이 인터페이스를 구현해야 하며,
    공통 유틸리티 메서드를 제공합니다.
    """

    def __init__(self, config=None):
        """
        Args:
            config: 설정 객체 (선택)
        """
        self.config = config
        self._initialized = False

    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        self._initialized = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        self._initialized = False

    def _require_initialized(self) -> None:
        """초기화 확인 (Guard Clause)"""
        if not self._initialized:
            raise RuntimeError(f"{self.__class__.__name__} is not initialized. Use 'async with' statement.")

    # ========================================================================
    # Abstract Methods (하위 클래스에서 구현 필요)
    # ========================================================================

    @abstractmethod
    async def get_top_gainers(self, market: str, top_n: int, target_date: str = None) -> List[StockData]:
        """
        상승률 상위 종목 조회

        Args:
            market: 'KOSPI' or 'KOSDAQ'
            top_n: 조회할 종목 수
            target_date: (Optional) 특정 날짜 기준 조회 (YYYYMMDD 형식)

        Returns:
            StockData 리스트
        """
        pass

    # ========================================================================
    # Common Utility Methods (공통 유틸리티)
    # ========================================================================

    def _safe_int(self, val: Any, default: int = 0) -> int:
        """안전한 정수 변환"""
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    def _safe_float(self, val: Any, default: float = 0.0) -> float:
        """안전한 실수 변환"""
        try:
            return float(val)
        except (ValueError, TypeError):
            return default

    def _safe_str(self, val: Any, default: str = "") -> str:
        """안전한 문자열 변환"""
        try:
            if val is None:
                return default
            # 빈 문자열/빈 시퀀스도 기본값 반환
            converted = str(val)
            return converted if converted else default
        except (ValueError, TypeError):
            return default

    def _parse_date(
        self,
        date_input: Optional[str],
        input_format: str = "%Y%m%d"
    ) -> Optional[datetime]:
        """
        날짜 문자열 파싱 (여러 형식 지원)

        Args:
            date_input: 날짜 문자열 (YYYYMMDD or YYYY-MM-DD)
            input_format: 입력 형식

        Returns:
            datetime 객체 또는 None
        """
        if not date_input:
            return None

        # YYYY-MM-DD 형식 처리
        if "-" in str(date_input):
            try:
                return datetime.strptime(str(date_input), "%Y-%m-%d")
            except ValueError:
                pass

        # YYYYMMDD 형식 처리 (기본)
        try:
            return datetime.strptime(str(date_input), input_format)
        except ValueError:
            logger.warning(f"날짜 파싱 실패: {date_input}")
            return None

    def _get_latest_market_date(self) -> str:
        """
        가장 최근 장 마감 날짜 반환

        - 주말(토/일): 금요일 날짜 반환
        - 금요일이 휴일인 경우: pykrx를 통해 실제 마지막 개장일 확인
        - 평일 장 마감 전(~15:30): 전일 날짜 반환
        - 평일 장 마감 후(15:30~): 당일 날짜 반환

        Returns:
            YYYYMMDD 형식의 날짜 문자열
        """
        now = datetime.now()
        weekday = now.weekday()  # 0=월, 1=화, ..., 5=토, 6=일

        # 장 마감 시간 (15:30)
        market_close_hour = 15
        market_close_minute = 30

        if weekday == 5:  # 토요일 -> 금요일
            target = now - timedelta(days=1)
        elif weekday == 6:  # 일요일 -> 금요일
            target = now - timedelta(days=2)
        elif now.hour < market_close_hour or (now.hour == market_close_hour and now.minute < market_close_minute):
            # 평일 장 마감 전 -> 전일 데이터 (주말 건너뛰기)
            if weekday == 0:  # 월요일 아침 -> 금요일
                target = now - timedelta(days=3)
            else:
                target = now - timedelta(days=1)
        else:
            # 평일 장 마감 후 -> 당일 데이터
            target = now

        # pykrx를 통해 실제 개장일 확인 (휴일 대응)
        try:
            from pykrx import stock

            # 최근 10일간 거래일 조회 (휴일 연속 대비)
            start_check = (target - timedelta(days=10)).strftime('%Y%m%d')
            end_check = target.strftime('%Y%m%d')

            # KOSPI 지수의 OHLCV로 개장일 확인
            kospi_data = stock.get_index_ohlcv_by_date(start_check, end_check, "1001")

            if not kospi_data.empty:
                # 마지막 거래일을 가져옴
                last_trading_date = kospi_data.index[-1]
                return last_trading_date.strftime('%Y%m%d')

        except ImportError:
            logger.warning("pykrx 미설치 - 주말 처리만 적용")
        except Exception as e:
            logger.warning(f"개장일 확인 실패: {e} - 주말 처리만 적용")

        # 폴백: 주말 처리만 된 날짜 반환
        return target.strftime('%Y%m%d')

    def _format_trading_value(self, value: float) -> str:
        """
        거래대금 포맷팅 (조/억/만 단위)

        Args:
            value: 거래대금 (원)

        Returns:
            포맷된 문자열 (예: "1.5조", "500억")
        """
        abs_val = abs(value)

        if abs_val >= 1_000_000_000_000:  # 1조 이상
            return f"{value / 1_000_000_000_000:.1f}조"
        elif abs_val >= 100_000_000:  # 1억 이상
            billions = value / 100_000_000
            return f"{int(billions):,}억"
        elif abs_val >= 10_000:  # 1만 이상
            thousands = value / 10_000
            return f"{int(thousands):,}만"
        return f"{value:,}"

    def _build_user_agent(self) -> str:
        """
        User-Agent 헤더 생성

        Returns:
            User-Agent 문자열
        """
        return (
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/121.0.0.0 Safari/537.36'
        )

    def _build_default_headers(self, referer: str = None) -> Dict[str, str]:
        """
        기본 HTTP 헤더 생성

        Args:
            referer: (Optional) Referer 헤더

        Returns:
            헤더 딕셔너리
        """
        headers = {
            'User-Agent': self._build_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        }

        if referer:
            headers['Referer'] = referer

        return headers


class CollectorError(Exception):
    """데이터 수집기 기본 예외"""
    pass


class DataSourceUnavailableError(CollectorError):
    """데이터 소스를 사용할 수 없을 때 발생"""
    pass


class DataParsingError(CollectorError):
    """데이터 파싱 실패시 발생"""
    pass


class RateLimitError(CollectorError):
    """API 호출 속도 제한 초과시 발생"""
    pass
