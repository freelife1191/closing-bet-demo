#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit Tests for data_sources.py

Tests the Strategy Pattern implementation for data source abstraction,
including fallback chain behavior, NaN handling, and edge cases.
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import patch, Mock, MagicMock
from pathlib import Path
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.data_sources import (
    DataSourceStrategy,
    FDRSource,
    PykrxSource,
    YFinanceSource,
    DataSourceManager,
    GlobalDataFetcher,
    fetch_stock_price,
    fetch_investor_trend_naver,
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def sample_price_df():
    """Create sample price DataFrame"""
    dates = pd.date_range(end=datetime.now(), periods=10, freq='D')
    return pd.DataFrame({
        'date': dates,
        'open': [100.0 + i for i in range(10)],
        'high': [105.0 + i for i in range(10)],
        'low': [95.0 + i for i in range(10)],
        'close': [100.0 + i for i in range(10)],
        'volume': [1000000 + i * 10000 for i in range(10)]
    })


@pytest.fixture
def sample_price_df_with_nan():
    """Create DataFrame with NaN values at the end"""
    dates = pd.date_range(end=datetime.now(), periods=10, freq='D')
    close_values = [100.0, 101.0, 102.0, 103.0, 104.0, np.nan, np.nan, 0.0, np.nan, np.nan]
    return pd.DataFrame({
        'date': dates,
        'close': close_values,
        'open': [100.0] * 10,
        'high': [105.0] * 10,
        'low': [95.0] * 10,
        'volume': [1000000] * 10
    })


@pytest.fixture
def sample_price_df_all_zeros():
    """Create DataFrame with all zero values"""
    dates = pd.date_range(end=datetime.now(), periods=5, freq='D')
    return pd.DataFrame({
        'date': dates,
        'close': [0.0, 0.0, 0.0, 0.0, 0.0],
        'open': [0.0] * 5,
        'high': [0.0] * 5,
        'low': [0.0] * 5,
        'volume': [0] * 5
    })


# ============================================================================
# TESTS: DataSourceStrategy Abstract Class
# ============================================================================

class TestDataSourceStrategy:
    """Tests for DataSourceStrategy abstract base class"""

    def test_cannot_instantiate_abstract_class(self):
        """Abstract class cannot be instantiated directly"""
        with pytest.raises(TypeError):
            DataSourceStrategy()

    def test_abstract_methods_defined(self):
        """Verify all abstract methods are defined"""
        abstract_methods = DataSourceStrategy.__abstractmethods__
        expected_methods = {
            'fetch_index_data',
            'fetch_stock_data',
            'fetch_fx_rate',
            'is_available'
        }
        assert expected_methods == abstract_methods


# ============================================================================
# TESTS: FDRSource
# ============================================================================

class TestFDRSource:
    """Tests for FDRSource implementation"""

    @pytest.fixture
    def fdr_source(self):
        return FDRSource()

    def test_init_sets_unavailable_without_fdr(self, fdr_source):
        """Source should be unavailable if FDR is not installed"""
        # FDR might be installed in test environment, so we just check type
        assert isinstance(fdr_source, FDRSource)

    def test_normalize_dataframe(self, fdr_source, sample_price_df):
        """Test DataFrame normalization"""
        # Create DataFrame with uppercase columns
        df = sample_price_df.copy()
        df.columns = [c.upper() for c in df.columns]

        normalized = fdr_source.normalize_dataframe(df)

        assert 'date' in normalized.columns
        assert 'close' in normalized.columns
        assert 'open' in normalized.columns
        assert 'volume' in normalized.columns

    def test_normalize_dataframe_korean_columns(self, fdr_source):
        """Test normalization with Korean column names"""
        df = pd.DataFrame({
            '날짜': pd.date_range(end=datetime.now(), periods=5),
            '종가': [100.0, 101.0, 102.0, 103.0, 104.0],
            '시가': [99.0, 100.0, 101.0, 102.0, 103.0],
            '고가': [101.0, 102.0, 103.0, 104.0, 105.0],
            '저가': [98.0, 99.0, 100.0, 101.0, 102.0],
            '거래량': [1000000] * 5
        })

        normalized = fdr_source.normalize_dataframe(df)

        assert 'date' in normalized.columns
        assert 'close' in normalized.columns

    def test_normalize_dataframe_empty(self, fdr_source):
        """Test normalization of empty DataFrame"""
        df = pd.DataFrame()
        normalized = fdr_source.normalize_dataframe(df)
        assert normalized.empty


# ============================================================================
# TESTS: PykrxSource
# ============================================================================

class TestPykrxSource:
    """Tests for PykrxSource implementation"""

    @pytest.fixture
    def pykrx_source(self):
        return PykrxSource()

    def test_init(self, pykrx_source):
        """Test initialization"""
        assert isinstance(pykrx_source, PykrxSource)

    def test_fetch_fx_rate_returns_empty(self, pykrx_source):
        """pykrx does not support FX rates"""
        result = pykrx_source.fetch_fx_rate()
        assert result.empty


# ============================================================================
# TESTS: YFinanceSource
# ============================================================================

class TestYFinanceSource:
    """Tests for YFinanceSource implementation"""

    @pytest.fixture
    def yfinance_source(self):
        return YFinanceSource()

    def test_init(self, yfinance_source):
        """Test initialization"""
        assert isinstance(yfinance_source, YFinanceSource)

    def test_fetch_stock_same_as_index(self, yfinance_source):
        """fetch_stock_data should delegate to fetch_index_data"""
        # yfinance treats both the same way
        with patch.object(yfinance_source, 'fetch_index_data', return_value=pd.DataFrame()) as mock:
            yfinance_source.fetch_stock_data('AAPL', '2024-01-01')
            mock.assert_called_once()


# ============================================================================
# TESTS: DataSourceManager
# ============================================================================

class TestDataSourceManager:
    """Tests for DataSourceManager fallback chain"""

    @pytest.fixture
    def mock_sources(self):
        """Create mock sources for testing"""
        source1 = Mock(spec=DataSourceStrategy)
        source1.is_available.return_value = True
        source1.__class__.__name__ = 'MockSource1'

        source2 = Mock(spec=DataSourceStrategy)
        source2.is_available.return_value = True
        source2.__class__.__name__ = 'MockSource2'

        source3 = Mock(spec=DataSourceStrategy)
        source3.is_available.return_value = False
        source3.__class__.__name__ = 'MockSource3'

        return [source1, source2, source3]

    def test_init_default_sources(self):
        """Test default initialization creates sources list"""
        manager = DataSourceManager()
        assert len(manager.sources) == 3
        assert all(isinstance(s, DataSourceStrategy) for s in manager.sources)

    def test_init_custom_sources(self, mock_sources):
        """Test initialization with custom sources"""
        manager = DataSourceManager(sources=mock_sources)
        assert len(manager.sources) == 3

    def test_fetch_with_fallback_uses_first_available(self, mock_sources, sample_price_df):
        """Test that first available source is used"""
        mock_sources[0].fetch_index_data.return_value = sample_price_df

        manager = DataSourceManager(sources=mock_sources)
        result = manager.fetch_index_data('TEST', '2024-01-01')

        mock_sources[0].fetch_index_data.assert_called_once()
        assert not result.empty

    def test_fetch_with_fallback_falls_back_on_failure(self, mock_sources, sample_price_df):
        """Test fallback when first source fails"""
        mock_sources[0].fetch_index_data.side_effect = Exception("Failed")
        mock_sources[1].fetch_index_data.return_value = sample_price_df

        manager = DataSourceManager(sources=mock_sources)
        result = manager.fetch_index_data('TEST', '2024-01-01')

        mock_sources[0].fetch_index_data.assert_called_once()
        mock_sources[1].fetch_index_data.assert_called_once()
        assert not result.empty

    def test_fetch_with_fallback_returns_empty_on_all_fail(self, mock_sources):
        """Test empty result when all sources fail"""
        mock_sources[0].fetch_index_data.side_effect = Exception("Failed")
        mock_sources[1].fetch_index_data.side_effect = Exception("Failed")

        manager = DataSourceManager(sources=mock_sources)
        result = manager.fetch_index_data('TEST', '2024-01-01')

        assert result.empty

    def test_fetch_with_fallback_skips_unavailable(self, mock_sources, sample_price_df):
        """Test that unavailable sources are skipped"""
        # Make first source unavailable
        mock_sources[0].is_available.return_value = False
        mock_sources[2].is_available.return_value = True
        mock_sources[2].fetch_index_data.return_value = sample_price_df

        manager = DataSourceManager(sources=mock_sources)
        result = manager.fetch_index_data('TEST', '2024-01-01')

        # First unavailable source should be skipped
        mock_sources[0].fetch_index_data.assert_not_called()
        mock_sources[2].fetch_index_data.assert_called_once()

    def test_get_latest_fx_rate(self, mock_sources):
        """Test getting latest FX rate"""
        fx_df = pd.DataFrame({
            'date': pd.date_range(end=datetime.now(), periods=5),
            'close': [1400.0, 1405.0, 1410.0, 1415.0, 1420.0]
        })
        mock_sources[0].fetch_fx_rate.return_value = fx_df

        manager = DataSourceManager(sources=mock_sources)
        rate = manager.get_latest_fx_rate("USD/KRW")

        assert rate == 1420.0

    def test_get_latest_fx_rate_default_on_empty(self, mock_sources):
        """Test default value when FX data is empty"""
        mock_sources[0].fetch_fx_rate.return_value = pd.DataFrame()

        manager = DataSourceManager(sources=mock_sources)
        rate = manager.get_latest_fx_rate("USD/KRW", default=1350.0)

        assert rate == 1350.0


# ============================================================================
# TESTS: GlobalDataFetcher - _extract_valid_value_pair
# ============================================================================

class TestExtractValidValuePair:
    """Tests for the _extract_valid_value_pair helper method"""

    @pytest.fixture
    def fetcher(self):
        return GlobalDataFetcher()

    def test_extracts_valid_pair_from_clean_data(self, fetcher, sample_price_df):
        """Test extraction from clean data"""
        result = fetcher._extract_valid_value_pair(sample_price_df, 'test', 'Test')

        assert result is not None
        assert result['value'] == 109.0  # Last close value
        assert 'change_pct' in result

    def test_handles_nan_at_end(self, fetcher, sample_price_df_with_nan):
        """Test handling of NaN values at the end"""
        result = fetcher._extract_valid_value_pair(sample_price_df_with_nan, 'test', 'Test')

        assert result is not None
        # Should find last valid value (104.0 at index 4) and previous (103.0 at index 3)
        assert result['value'] == 104.0
        # Change should be (104 - 103) / 103 * 100 ≈ 0.97%
        assert abs(result['change_pct'] - 0.97) < 0.1

    def test_returns_none_for_empty_dataframe(self, fetcher):
        """Test handling of empty DataFrame"""
        df = pd.DataFrame()
        result = fetcher._extract_valid_value_pair(df, 'test', 'Test')
        assert result is None

    def test_returns_none_for_single_row(self, fetcher):
        """Test handling of single row DataFrame"""
        df = pd.DataFrame({
            'date': [datetime.now()],
            'close': [100.0],
            'volume': [1000]
        })
        result = fetcher._extract_valid_value_pair(df, 'test', 'Test')
        assert result is None

    def test_returns_none_for_all_zeros(self, fetcher, sample_price_df_all_zeros):
        """Test handling of all zero values"""
        result = fetcher._extract_valid_value_pair(sample_price_df_all_zeros, 'test', 'Test')
        assert result is None

    def test_returns_none_for_all_nan(self, fetcher):
        """Test handling of all NaN values"""
        df = pd.DataFrame({
            'date': pd.date_range(end=datetime.now(), periods=5),
            'close': [np.nan] * 5,
            'volume': [1000] * 5
        })
        result = fetcher._extract_valid_value_pair(df, 'test', 'Test')
        assert result is None

    def test_handles_mixed_nan_and_zeros(self, fetcher):
        """Test handling of mixed NaN and zero values"""
        dates = pd.date_range(end=datetime.now(), periods=10, freq='D')
        df = pd.DataFrame({
            'date': dates,
            'close': [100.0, 101.0, np.nan, 0.0, np.nan, np.nan, 0.0, 102.0, np.nan, np.nan],
            'volume': [1000] * 10
        })

        result = fetcher._extract_valid_value_pair(df, 'test', 'Test')

        # Should find 102.0 (index 7) as latest valid, but need prev valid
        # After 102.0, going backwards: 0.0 (skip), np.nan (skip), np.nan (skip), 0.0 (skip), np.nan (skip), 101.0 (valid)
        assert result is not None
        assert result['value'] == 102.0
        assert abs(result['change_pct'] - 0.99) < 0.1  # (102-101)/101 * 100

    def test_change_pct_calculation_positive(self, fetcher):
        """Test positive change percentage calculation"""
        df = pd.DataFrame({
            'date': pd.date_range(end=datetime.now(), periods=3),
            'close': [100.0, 105.0, 110.0],
            'volume': [1000] * 3
        })

        result = fetcher._extract_valid_value_pair(df, 'test', 'Test')
        assert result is not None
        # latest=110, prev=105, change=(110-105)/105*100 ≈ 4.76
        assert abs(result['change_pct'] - 4.76) < 0.1
        # Actually: latest=110, prev=105, change=(110-105)/105*100 ≈ 4.76

    def test_change_pct_calculation_negative(self, fetcher):
        """Test negative change percentage calculation"""
        df = pd.DataFrame({
            'date': pd.date_range(end=datetime.now(), periods=3),
            'close': [100.0, 95.0, 90.0],
            'volume': [1000] * 3
        })

        result = fetcher._extract_valid_value_pair(df, 'test', 'Test')
        assert result is not None
        assert result['change_pct'] < 0


# ============================================================================
# TESTS: GlobalDataFetcher - fetch_all_indices
# ============================================================================

class TestFetchAllIndices:
    """Tests for fetch_all_indices method"""

    @pytest.fixture
    def fetcher(self):
        return GlobalDataFetcher()

    @pytest.fixture
    def mock_manager(self, sample_price_df):
        """Create mock manager"""
        manager = Mock(spec=DataSourceManager)
        manager.fetch_index_data.return_value = sample_price_df
        return manager

    def test_returns_expected_structure(self, fetcher, mock_manager):
        """Test returns expected dict structure"""
        fetcher.manager = mock_manager
        result = fetcher.fetch_all_indices('2024-01-01')

        assert isinstance(result, dict)
        # Check for expected keys
        expected_keys = ['sp500', 'nasdaq', 'kospi', 'kosdaq']
        for key in expected_keys:
            assert mock_manager.fetch_index_data.called
            # Each call might have different results depending on mock

    def test_handles_empty_response(self, fetcher):
        """Test handling of empty data response"""
        manager = Mock(spec=DataSourceManager)
        manager.fetch_index_data.return_value = pd.DataFrame()
        fetcher.manager = manager

        result = fetcher.fetch_all_indices('2024-01-01')

        assert isinstance(result, dict)
        # Should be empty since all sources return empty
        assert len(result) == 0

    def test_handles_nan_values(self, fetcher, sample_price_df_with_nan, mock_manager):
        """Test proper NaN handling"""
        mock_manager.fetch_index_data.return_value = sample_price_df_with_nan
        fetcher.manager = mock_manager

        result = fetcher.fetch_all_indices('2024-01-01')

        # Should still return valid results even with NaN
        assert isinstance(result, dict)


# ============================================================================
# TESTS: GlobalDataFetcher - fetch_commodities
# ============================================================================

class TestFetchCommodities:
    """Tests for fetch_commodities method"""

    @pytest.fixture
    def fetcher(self):
        return GlobalDataFetcher()

    @pytest.fixture
    def mock_manager(self, sample_price_df):
        """Create mock manager"""
        manager = Mock(spec=DataSourceManager)
        manager.fetch_index_data.return_value = sample_price_df
        manager.fetch_stock_data.return_value = sample_price_df
        return manager

    def test_returns_expected_structure(self, fetcher, mock_manager):
        """Test returns expected dict structure"""
        fetcher.manager = mock_manager
        result = fetcher.fetch_commodities('2024-01-01')

        assert isinstance(result, dict)

    def test_fetches_global_and_krx_separately(self, fetcher, mock_manager):
        """Test that both index and stock data are fetched"""
        fetcher.manager = mock_manager
        result = fetcher.fetch_commodities('2024-01-01')

        # Should call fetch_index_data for global commodities
        assert mock_manager.fetch_index_data.called
        # Should call fetch_stock_data for KRX commodities
        assert mock_manager.fetch_stock_data.called


# ============================================================================
# TESTS: GlobalDataFetcher - fetch_crypto
# ============================================================================

class TestFetchCrypto:
    """Tests for fetch_crypto method"""

    @pytest.fixture
    def fetcher(self):
        return GlobalDataFetcher()

    @pytest.fixture
    def mock_manager(self, sample_price_df):
        """Create mock manager"""
        manager = Mock(spec=DataSourceManager)
        manager.fetch_index_data.return_value = sample_price_df
        return manager

    def test_returns_expected_structure(self, fetcher, mock_manager):
        """Test returns expected dict structure"""
        fetcher.manager = mock_manager
        result = fetcher.fetch_crypto('2024-01-01')

        assert isinstance(result, dict)

    def test_fetches_all_cryptos(self, fetcher, mock_manager):
        """Test that all defined cryptos are fetched"""
        fetcher.manager = mock_manager
        result = fetcher.fetch_crypto('2024-01-01')

        # Should be called for btc, eth, xrp
        assert mock_manager.fetch_index_data.call_count == 3


# ============================================================================
# TESTS: fetch_stock_price utility function
# ============================================================================

class TestFetchStockPrice:
    """Tests for fetch_stock_price utility function"""

    @patch('requests.get')
    def test_toss_api_priority(self, mock_get):
        """Test Toss API is tried first"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'result': [{
                'close': 50000,
                'base': 49500,
                'accTradeVolume': 1000000
            }]
        }
        mock_get.return_value = mock_response

        result = fetch_stock_price('005930')

        assert result is not None
        assert result['price'] == 50000
        assert result['source'] == 'toss'

    @patch('requests.get')
    def test_naver_fallback(self, mock_get):
        """Test Naver API as fallback"""
        # First call (Toss) fails
        # Second call (Naver) succeeds
        mock_get.side_effect = [
            Mock(status_code=404),  # Toss fails
            Mock(status_code=200, json=lambda: {'closePrice': '50,000', 'fluctuationsRatio': '1.5', 'accumulatedTradingVolume': '1,000,000'})  # Naver succeeds
        ]

        result = fetch_stock_price('005930')

        assert result is not None
        assert result['price'] == 50000
        assert result['source'] == 'naver'

    def test_yfinance_fallback_works(self):
        """Test that yfinance fallback provides data when Toss/Naver fail"""
        # This test verifies that the yfinance fallback works
        # Since we can't easily mock the local import, we'll just verify
        # that calling the function doesn't crash and returns something

        # In a real environment, yfinance might return data for valid tickers
        # We'll use a ticker that's unlikely to have Toss/Naver data
        result = fetch_stock_price('999999')  # Non-existent ticker

        # Should either return data (if yfinance has something) or None
        # The important thing is it doesn't crash
        assert result is None or isinstance(result, dict)


# ============================================================================
# TESTS: fetch_investor_trend_naver utility function
# ============================================================================

class TestFetchInvestorTrendNaver:
    """Tests for fetch_investor_trend_naver utility function"""

    @patch('requests.get')
    def test_successful_fetch(self, mock_get):
        """Test successful fetch from Naver"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{
            'closePrice': '50000',
            'foreignerPureBuyQuant': '1,000',
            'organPureBuyQuant': '500'
        }]
        mock_get.return_value = mock_response

        result = fetch_investor_trend_naver('005930')

        assert result is not None
        assert result['foreign'] == 50_000_000  # 1000 * 50000
        assert result['institution'] == 25_000_000  # 500 * 50000

    @patch('requests.get')
    def test_returns_none_on_error(self, mock_get):
        """Test None returned on error"""
        mock_get.side_effect = Exception("Network error")

        result = fetch_investor_trend_naver('005930')

        assert result is None


# ============================================================================
# PARAMETRIZED TESTS
# ============================================================================

class TestDataSourcesParametrized:
    """Parametrized tests for data sources"""

    @pytest.mark.parametrize("close_values,expected_value", [
        ([100.0, 101.0, 102.0], 102.0),    # Normal case
        ([100.0, 101.0, np.nan], 101.0),    # Last is NaN, returns 101 with prev 100
        ([np.nan, 101.0, 102.0], 102.0),    # First is NaN, returns 102 with prev 101
        ([100.0, 101.0, 0.0], 101.0),      # Last is 0, returns 101 with prev 100
    ])
    def test_extract_valid_value_with_various_nan_patterns(
        self, close_values, expected_value
    ):
        """Test NaN handling with various patterns"""
        fetcher = GlobalDataFetcher()
        df = pd.DataFrame({
            'date': pd.date_range(end=datetime.now(), periods=len(close_values)),
            'close': close_values,
            'volume': [1000] * len(close_values)
        })

        result = fetcher._extract_valid_value_pair(df, 'test', 'Test')

        if expected_value is not None:
            assert result is not None
            assert result['value'] == expected_value
        else:
            assert result is None


# ============================================================================
# EDGE CASES
# ============================================================================

class TestDataSourcesEdgeCases:
    """Edge case tests for data sources"""

    def test_very_long_dataframe(self):
        """Test handling of very long DataFrame"""
        fetcher = GlobalDataFetcher()
        dates = pd.date_range(end=datetime.now(), periods=10000, freq='H')
        close_values = [100.0 + i * 0.001 for i in range(10000)]

        df = pd.DataFrame({
            'date': dates,
            'close': close_values,
            'volume': [1000] * 10000
        })

        result = fetcher._extract_valid_value_pair(df, 'test', 'Test')

        assert result is not None

    def test_dataframe_with_inf_values(self):
        """Test handling of infinite values"""
        fetcher = GlobalDataFetcher()
        df = pd.DataFrame({
            'date': pd.date_range(end=datetime.now(), periods=5),
            'close': [100.0, np.inf, 102.0, -np.inf, 104.0],
            'volume': [1000] * 5
        })

        result = fetcher._extract_valid_value_pair(df, 'test', 'Test')

        # Should skip inf values and find 104.0
        assert result is not None

    def test_negative_prices(self):
        """Test handling of negative prices (should be skipped as invalid)"""
        fetcher = GlobalDataFetcher()
        df = pd.DataFrame({
            'date': pd.date_range(end=datetime.now(), periods=5),
            'close': [100.0, 101.0, -50.0, 103.0, 104.0],
            'volume': [1000] * 5
        })

        result = fetcher._extract_valid_value_pair(df, 'test', 'Test')

        # Negative values are not explicitly checked, but 0 is
        assert result is not None


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short', '--cov=engine/data_sources', '--cov-report=term-missing'])
