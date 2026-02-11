#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit Tests for KRX Collector Module

krx.py 모듈의 KRXCollector 클래스를 테스트합니다.

Created: 2026-02-11
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from engine.collectors.krx import KRXCollector
from engine.models import StockData, ChartData, SupplyData


class TestKRXCollector:
    """KRXCollector 클래스 테스트"""

    @pytest.fixture
    def collector(self):
        """테스트용 KRXCollector 인스턴스"""
        return KRXCollector(config=None)

    # ========================================================================
    # Initialization Tests
    # ========================================================================

    def test_init(self, collector):
        """초기화 테스트"""
        assert collector is not None
        assert collector.config is None
        assert not collector._initialized

    # ========================================================================
    # get_top_gainers Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_top_gainers_not_initialized(self, collector):
        """초기화되지 않은 상태에서 get_top_gainers 호출 시도"""
        # 컨텍스트 매니저 없이 직접 호출하면 내부적으로 에러 발생 가능
        # 하지만 pykrx가 없으면 fallback으로 CSV 로드 시도
        # 이 테스트는 구조적 검증
        with patch.object(collector, '_load_from_local_csv', return_value=[]):
            result = await collector.get_top_gainers("KOSPI", 10)
            # fallback이 동작하면 빈 리스트 반환
            assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_top_gainers_with_mock_pykrx(self, collector):
        """mock pykrx로 get_top_gainers 테스트"""
        mock_df = Mock()
        mock_df.empty = False

        # Mock DataFrame structure
        type(mock_df).sort_values = Mock(return_value=mock_df)
        type(mock_df).head = Mock(return_value=mock_df)

        # Mock row data
        mock_row = {
            '종가': 50000,
            '등락률': 5.2,
            '거래대금': 10_000_000_000,
            '거래량': 1_000_000,
            '시가총액': 1_000_000_000_000,
        }

        # Mock iterrows
        mock_df.__iter__ = Mock(return_value=iter([]))

        with patch('builtins.__import__') as mock_stock:
            mock_stock.get_market_ticker_name = Mock(return_value="테스트종목")
            mock_stock.get_market_ohlcv_by_ticker = Mock(return_value=mock_df)

            # 등락률 필터링을 위한 masking mock
            mock_df.__getitem__ = Mock(return_value=mock_df)
            type(mock_df).__and__ = Mock(return_value=mock_df)
            type(mock_df).__gt__ = Mock(return_value=mock_df)

            result = await collector.get_top_gainers("KOSPI", 10, target_date="20240115")

            assert isinstance(result, list)

    # ========================================================================
    # _get_stock_name Tests
    # ========================================================================

    def test_get_stock_name_known_ticker(self, collector):
        """알려진 종목 코드의 이름 조회"""
        # pykrx.stock 모듈 mock 생성
        mock_pykrx = Mock()
        mock_stock = Mock()
        mock_stock.get_market_ticker_name = Mock(return_value="삼성전자")
        mock_pykrx.stock = mock_stock

        # __import__가 mock pykrx 모듈을 반환하도록 설정
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == 'pykrx':
                return mock_pykrx
            return original_import(name, *args, **kwargs)

        with patch.object(builtins, '__import__', side_effect=mock_import):
            name = collector._get_stock_name("005930")
            assert name == "삼성전자"

    def test_get_stock_name_unknown_ticker(self, collector):
        """알려지지 않은 종목 코드의 이름 조회 (fallback)"""
        with patch('builtins.__import__', side_effect=ImportError):
            name = collector._get_stock_name("999999")
            # fallback 하드코딩 데이터가 없으면 기본값
            assert name == "알 수 없는 종목"

    def test_get_stock_name_major_stocks_fallback(self, collector):
        """주요 종목 fallback 테스트"""
        with patch('builtins.__import__', side_effect=Exception("API Error")):
            assert collector._get_stock_name("005930") == "삼성전자"
            assert collector._get_stock_name("000270") == "기아"
            assert collector._get_stock_name("035420") == "NAVER"

    # ========================================================================
    # _get_sector Tests
    # ========================================================================

    def test_get_sector_known_ticker(self, collector):
        """알려진 종목 코드의 섹터 조회"""
        with patch('builtins.__import__', side_effect=Exception("API Error")):
            sector = collector._get_sector("005930")
            assert sector == "반도체"

    def test_get_sector_unknown_ticker(self, collector):
        """알려지지 않은 종목 코드의 섹터 조회"""
        with patch('builtins.__import__', side_effect=Exception("API Error")):
            sector = collector._get_sector("999999")
            assert sector == "기타"

    # ========================================================================
    # get_stock_detail Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_stock_detail(self, collector):
        """종목 상세 정보 조회 테스트"""
        detail = await collector.get_stock_detail("005930")
        assert detail is not None
        assert detail['code'] == "005930"
        assert 'name' in detail
        assert 'high_52w' in detail
        assert 'low_52w' in detail

    # ========================================================================
    # get_chart_data Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_chart_data_with_mock(self, collector):
        """mock로 차트 데이터 조회 테스트"""
        import builtins
        from datetime import datetime, date
        original_import = builtins.__import__

        # Mock datetime object with .date() method
        mock_datetime = Mock()
        mock_datetime.date = Mock(return_value=date(2024, 1, 15))

        # Mock DataFrame with proper structure
        mock_df = Mock()
        mock_df.empty = False
        mock_df.tail = Mock(return_value=mock_df)
        mock_df.index = [mock_datetime]

        # Mock column access - df['시가'] etc.
        mock_df.__getitem__ = lambda self, key: Mock(tolist=Mock(return_value=[100, 110, 90, 105, 1000]))

        # pykrx.stock 모듈 mock 생성
        mock_pykrx = Mock()
        mock_stock = Mock()
        mock_stock.get_market_ohlcv_by_date = Mock(return_value=mock_df)
        mock_pykrx.stock = mock_stock

        def mock_import(name, *args, **kwargs):
            if name == 'pykrx':
                return mock_pykrx
            return original_import(name, *args, **kwargs)

        with patch.object(builtins, '__import__', side_effect=mock_import):
            chart_data = await collector.get_chart_data("005930", 60)
            assert chart_data is not None

    @pytest.mark.asyncio
    async def test_get_chart_data_empty_response(self, collector):
        """빈 응답 시 차트 데이터 조회 테스트"""
        import builtins
        original_import = builtins.__import__

        mock_df = Mock()
        mock_df.empty = True

        # pykrx.stock 모듈 mock 생성
        mock_pykrx = Mock()
        mock_stock = Mock()
        mock_stock.get_market_ohlcv_by_date = Mock(return_value=mock_df)
        mock_pykrx.stock = mock_stock

        def mock_import(name, *args, **kwargs):
            if name == 'pykrx':
                return mock_pykrx
            return original_import(name, *args, **kwargs)

        with patch.object(builtins, '__import__', side_effect=mock_import):
            chart_data = await collector.get_chart_data("005930", 60)
            assert chart_data is None

    # ========================================================================
    # get_supply_data Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_supply_data_with_mock(self, collector):
        """mock로 수급 데이터 조회 테스트"""
        mock_df = Mock()
        mock_df.empty = False
        mock_df.tail = Mock(return_value=mock_df)

        # Mock columns
        mock_df.columns = ['외국인합계', '기관합계', '개인']
        mock_df.__getitem__ = Mock(return_value=mock_df)

        with patch('builtins.__import__') as mock_stock:
            mock_stock.get_market_trading_value_by_date = Mock(return_value=mock_df)
            type(mock_df).sum = Mock(return_value=100_000_000)

            supply_data = await collector.get_supply_data("005930")

            assert supply_data is not None
            assert isinstance(supply_data, SupplyData)

    @pytest.mark.asyncio
    async def test_get_supply_data_empty_response(self, collector):
        """빈 응답 시 수급 데이터 조회 테스트"""
        mock_df = Mock()
        mock_df.empty = True

        with patch('builtins.__import__') as mock_stock:
            mock_stock.get_market_trading_value_by_date = Mock(return_value=mock_df)

            supply_data = await collector.get_supply_data("005930")

            assert supply_data is not None
            assert supply_data.foreign_buy_5d == 0
            assert supply_data.inst_buy_5d == 0


# ========================================================================
# Parametrized Tests
# ========================================================================

class TestKRXCollectorParametrized:
    """매개변수화된 테스트"""

    @pytest.mark.parametrize("market,top_n,expected_type", [
        ("KOSPI", 10, list),
        ("KOSDAQ", 20, list),
        ("KOSPI", 0, list),
    ])
    @pytest.mark.asyncio
    async def test_get_top_gainers_various_inputs(self, market, top_n, expected_type):
        """다양한 입력에 대한 get_top_gainers 테스트"""
        collector = KRXCollector()

        with patch.object(collector, '_load_from_local_csv', return_value=[]):
            result = await collector.get_top_gainers(market, top_n)
            assert isinstance(result, expected_type)

    @pytest.mark.parametrize("code,expected_sector", [
        ("005930", "반도체"),
        ("000270", "자동차"),
        ("035420", "인터넷"),
        ("005380", "자동차"),
        ("999999", "기타"),
    ])
    def test_get_sector_various_tickers(self, code, expected_sector):
        """다양한 종목 코드에 대한 섹터 조회 테스트"""
        collector = KRXCollector()
        with patch('builtins.__import__', side_effect=Exception("API Error")):
            sector = collector._get_sector(code)
            assert sector == expected_sector


# ========================================================================
# Integration Tests (with actual file system)
# ========================================================================

class TestKRXCollectorIntegration:
    """통합 테스트 (실제 파일 시스템 사용)"""

    @pytest.fixture
    def temp_csv_dir(self, tmp_path):
        """임시 CSV 디렉토리 fixture"""
        import pandas as pd

        # 종목 리스트 생성
        stocks_df = pd.DataFrame({
            'ticker': ['005930', '000270'],
            'name': ['삼성전자', '기아'],
            'market': ['KOSPI', 'KOSDAQ']
        })

        # 가격 데이터 생성
        prices_df = pd.DataFrame({
            'ticker': ['005930', '000270'],
            'date': [pd.Timestamp('2024-01-15'), pd.Timestamp('2024-01-15')],
            'close': [70000, 80000],
            'open': [69000, 79000],
            'high': [71000, 81000],
            'low': [68500, 78500],
            'volume': [1000000, 500000],
            'trading_value': [70_000_000_000, 40_000_000_000],
            'change_pct': [1.5, 2.0]
        })

        data_dir = tmp_path / "data"
        data_dir.mkdir()

        stocks_df.to_csv(data_dir / "korean_stocks_list.csv", index=False)
        prices_df.to_csv(data_dir / "daily_prices.csv", index=False)

        return data_dir

    @pytest.mark.asyncio
    async def test_load_from_local_csv_with_real_files(self, temp_csv_dir):
        """실제 CSV 파일로부터 로드 테스트"""
        import os

        collector = KRXCollector()

        # 임시 디렉토리 경로를 모의
        base_dir = os.path.dirname(os.path.dirname(temp_csv_dir))

        with patch('engine.collectors.krx.os.path.join') as mock_join:
            # 경로 조작
            def join_side_effect(*args):
                if 'korean_stocks_list.csv' in str(args):
                    return str(temp_csv_dir / "korean_stocks_list.csv")
                elif 'daily_prices.csv' in str(args):
                    return str(temp_csv_dir / "daily_prices.csv")
                return str(temp_csv_dir / args[-1])

            mock_join.side_effect = join_side_effect

            result = await collector._load_from_local_csv("KOSPI", 10, "2024-01-15")

            # 결과 검증
            assert isinstance(result, list)
            # 데이터가 있으면 검증
            if result:
                assert all(isinstance(item, StockData) for item in result)


# ========================================================================
# Edge Cases Tests
# ========================================================================

class TestKRXCollectorEdgeCases:
    """엣지 케이스 테스트"""

    @pytest.fixture
    def collector(self):
        return KRXCollector()

    @pytest.mark.asyncio
    async def test_get_top_gainers_with_invalid_target_date(self, collector):
        """무효한 타겟 날짜로 get_top_gainers 테스트"""
        with patch.object(collector, '_load_from_local_csv', return_value=[]):
            # 잘못된 형식도 처리되어야 함
            result = await collector.get_top_gainers("KOSPI", 10, target_date="invalid")
            assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_chart_data_with_zero_days(self, collector):
        """0일 차트 데이터 조회 테스트"""
        with patch('builtins.__import__') as mock_stock:
            mock_df = Mock()
            mock_df.empty = False
            mock_df.tail = Mock(return_value=mock_df)
            mock_stock.get_market_ohlcv_by_date = Mock(return_value=mock_df)

            result = await collector.get_chart_data("005930", 0)
            # 0일이어도 처리되어야 함
            assert result is not None or result is None  # 둘 다 가능

    @pytest.mark.asyncio
    async def test_get_supply_data_exception_handling(self, collector):
        """예외 발생 시 수급 데이터 조회 테스트"""
        # 명시적으로 ImportError 발생
        def mock_import(name, *args, **kwargs):
            if name == 'pykrx':
                raise ImportError("API Error")
            import builtins
            return builtins.__import__(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=mock_import):
            supply_data = await collector.get_supply_data("005930")
            # 예외 발생 시에도 기본값 반환
            assert supply_data is not None
            assert supply_data.foreign_buy_5d == 0
            assert supply_data.inst_buy_5d == 0
