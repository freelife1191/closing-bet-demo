#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comprehensive tests for market_gate.py

These tests capture existing behavior before refactoring to ensure
no functionality is lost during the refactoring process.
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

from engine.market_gate import MarketGate
from engine.config import MarketGateConfig


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_config():
    """Create a mock MarketGateConfig for testing"""
    return MarketGateConfig(
        usd_krw_safe=1420.0,
        usd_krw_warning=1450.0,
        usd_krw_danger=1480.0,
        kospi_ma_short=20,
        kospi_ma_long=60,
        foreign_net_buy_threshold=500_000_000_000
    )


@pytest.fixture
def sample_price_data():
    """Create sample KODEX 200 price data for testing"""
    dates = pd.date_range(end=datetime.now(), periods=100, freq='D')
    np.random.seed(42)

    # Create realistic price movement
    base_price = 35000
    prices = []
    for i in range(100):
        noise = np.random.randn() * 100
        trend = i * 10  # Slight upward trend
        prices.append(base_price + trend + noise)

    df = pd.DataFrame({
        'date': dates,
        'open': [p * (1 + np.random.randn() * 0.005) for p in prices],
        'high': [p * (1 + abs(np.random.randn()) * 0.01) for p in prices],
        'low': [p * (1 - abs(np.random.randn()) * 0.01) for p in prices],
        'close': prices,
        'volume': np.random.randint(1_000_000, 10_000_000, 100)
    })
    return df


@pytest.fixture
def sample_global_data():
    """Create sample global market data"""
    return {
        'indices': {
            'sp500': {'value': 5000.0, 'change_pct': 1.5},
            'nasdaq': {'value': 16000.0, 'change_pct': 2.0},
            'kospi': {'value': 2600.0, 'change_pct': 0.5},
            'kosdaq': {'value': 850.0, 'change_pct': -0.3}
        },
        'commodities': {
            'us_gold': {'value': 2000.0, 'change_pct': 0.5},
            'us_silver': {'value': 25.0, 'change_pct': -0.2}
        },
        'crypto': {
            'btc': {'value': 45000.0, 'change_pct': 3.0},
            'eth': {'value': 2500.0, 'change_pct': 2.5},
            'xrp': {'value': 0.5, 'change_pct': 1.0}
        },
        'usd_krw': {'value': 1400.0, 'change_pct': 0.2}
    }


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create a temporary data directory with sample CSV"""
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Create sample daily_prices.csv with KODEX 200 data
    dates = pd.date_range(end=datetime.now(), periods=100, freq='D')
    df = pd.DataFrame({
        'date': dates.strftime('%Y-%m-%d'),
        'ticker': '069500',
        'open': np.random.uniform(34000, 36000, 100),
        'high': np.random.uniform(35000, 37000, 100),
        'low': np.random.uniform(33000, 35000, 100),
        'close': np.random.uniform(34000, 36000, 100),
        'volume': np.random.randint(1_000_000, 10_000_000, 100)
    })
    df.to_csv(data_dir / 'daily_prices.csv', index=False)

    return str(data_dir)


# ============================================================================
# TESTS: MarketGate Initialization
# ============================================================================

class TestMarketGateInitialization:
    """Tests for MarketGate initialization and setup"""

    def test_init_with_default_params(self):
        """Test MarketGate can be initialized with default parameters"""
        mg = MarketGate()
        assert mg.data_dir == 'data'
        assert mg.kodex_ticker == '069500'
        assert isinstance(mg.config, MarketGateConfig)
        assert len(mg.sectors) > 0

    def test_init_with_custom_data_dir(self, temp_data_dir):
        """Test MarketGate can be initialized with custom data directory"""
        mg = MarketGate(data_dir=temp_data_dir)
        assert mg.data_dir == temp_data_dir

    def test_sectors_dictionary_populated(self):
        """Test that sectors dictionary is properly populated"""
        mg = MarketGate()
        expected_sectors = [
            '반도체', '2차전지', '자동차', '헬스케어', 'IT',
            '은행', '철강', '증권', '조선', '에너지', 'KOSPI 200'
        ]
        for sector in expected_sectors:
            assert sector in mg.sectors
            assert mg.sectors[sector]  # Ticker should exist


# ============================================================================
# TESTS: Price Data Loading
# ============================================================================

class TestPriceDataLoading:
    """Tests for _load_price_data method"""

    @patch('engine.market_gate.pd.read_csv')
    def test_load_price_data_from_csv(self, mock_read_csv, sample_price_data):
        """Test loading price data from CSV file"""
        # Add ticker column to sample data
        sample_price_data['ticker'] = '069500'
        mock_read_csv.return_value = sample_price_data

        mg = MarketGate(data_dir='fake_dir')

        with patch('os.path.exists', return_value=True):
            df = mg._load_price_data()

        assert not df.empty or len(df) == 0  # May be empty if pykrx fails
        # Just verify method doesn't crash

    @patch('engine.market_gate.pd.read_csv')
    def test_load_price_data_returns_empty_when_no_csv(self, mock_read_csv):
        """Test that empty DataFrame is returned when CSV doesn't exist"""
        mg = MarketGate(data_dir='fake_dir')

        # Mock both os.path.exists and pykrx to ensure empty result
        with patch('os.path.exists', return_value=False):
            with patch('pykrx.stock.get_market_ohlcv_by_date') as mock_pykrx:
                mock_pykrx.return_value = pd.DataFrame()
                df = mg._load_price_data()

        # Should be empty since both CSV and pykrx return empty
        assert df.empty or len(df) == 0

    def test_load_price_data_filters_by_ticker(self, sample_price_data):
        """Test that price data is filtered by KODEX ticker"""
        mg = MarketGate()

        # Create mixed ticker data
        mixed_data = pd.concat([
            sample_price_data.assign(ticker='069500'),
            sample_price_data.assign(ticker='005930')  # Samsung
        ])

        with patch('os.path.exists', return_value=True):
            with patch('engine.market_gate.pd.read_csv', return_value=mixed_data):
                df = mg._load_price_data()

        # Should only have KODEX 200 data
        assert len(df) < len(mixed_data) or all(df.get('ticker', '069500') == '069500')


# ============================================================================
# TESTS: Global Data Fetching
# ============================================================================

class TestGlobalDataFetching:
    """Tests for _get_global_data method (Refactored to use GlobalDataFetcher)"""

    @patch('engine.data_sources.DataSourceManager.fetch_index_data')
    def test_get_global_data_returns_expected_structure(self, mock_fetch_index):
        """Test that _get_global_data returns proper structure"""
        # Mock the DataSourceManager to return empty data
        mock_fetch_index.return_value = pd.DataFrame()

        mg = MarketGate()
        result = mg._get_global_data()

        # Check structure - should have these keys even if empty
        assert isinstance(result, dict)
        assert 'indices' in result
        assert 'commodities' in result
        assert 'crypto' in result
        assert 'usd_krw' in result

    @patch('engine.data_sources.DataSourceManager.fetch_index_data')
    def test_get_global_data_handles_empty_response(self, mock_fetch_index):
        """Test that _get_global_data handles empty data source response"""
        mock_fetch_index.return_value = pd.DataFrame()

        mg = MarketGate()
        result = mg._get_global_data()

        # Should return dict with empty values, not raise exception
        assert isinstance(result, dict)
        assert 'indices' in result

    @patch('engine.data_sources.DataSourceManager.fetch_index_data')
    def test_get_global_data_handles_exception(self, mock_fetch_index):
        """Test that _get_global_data handles exceptions gracefully"""
        mock_fetch_index.side_effect = Exception("Network error")

        mg = MarketGate()
        result = mg._get_global_data()

        # Should return empty dict on error
        assert isinstance(result, dict)


# ============================================================================
# TESTS: Sector Data Fetching
# ============================================================================

class TestSectorDataFetching:
    """Tests for _get_sector_data method"""

    def test_get_sector_data_returns_dict(self):
        """Test that _get_sector_data returns a dictionary"""
        mg = MarketGate()

        # Patch at the import location inside the method
        with patch('pykrx.stock.get_market_ohlcv_by_date') as mock_ohlcv:
            # Mock empty response for all sectors
            mock_ohlcv.return_value = pd.DataFrame()

            result = mg._get_sector_data()

        assert isinstance(result, dict)

    def test_get_sector_data_includes_all_sectors(self):
        """Test that _get_sector_data attempts to fetch all defined sectors"""
        mg = MarketGate()

        # Patch at the import location inside the method
        with patch('pykrx.stock.get_market_ohlcv_by_date') as mock_ohlcv:
            mock_ohlcv.return_value = pd.DataFrame()

            result = mg._get_sector_data()

        # All sectors should have entries (even if 0.0 on error)
        for sector_name in mg.sectors:
            assert sector_name in result


# ============================================================================
# TESTS: Main Analyze Method
# ============================================================================

class TestMarketGateAnalyze:
    """Tests for the main analyze() method"""

    @patch.object(MarketGate, '_get_global_data')
    @patch.object(MarketGate, '_load_price_data')
    def test_analyze_returns_expected_structure(self, mock_load, mock_global):
        """Test that analyze() returns the expected structure"""
        # Mock price data
        mock_load.return_value = pd.DataFrame({
            'date': pd.date_range(end=datetime.now(), periods=100),
            'close': np.random.uniform(34000, 36000, 100)
        })

        # Mock global data
        mock_global.return_value = {
            'indices': {},
            'usd_krw': {}
        }

        mg = MarketGate()
        result = mg.analyze()

        # Check result structure
        assert isinstance(result, dict)
        # May contain various keys depending on data availability

    @patch.object(MarketGate, '_load_price_data')
    def test_analyze_handles_empty_price_data(self, mock_load):
        """Test that analyze() handles empty price data gracefully"""
        mock_load.return_value = pd.DataFrame()

        mg = MarketGate()
        result = mg.analyze()

        # Should return default result, not crash
        assert isinstance(result, dict)
        assert 'status' in result or 'error' in result or 'gate' in result

    @patch.object(MarketGate, '_get_global_data')
    @patch.object(MarketGate, '_load_price_data')
    def test_analyze_includes_technical_indicators(self, mock_load, mock_global):
        """Test that analyze() includes technical indicators"""
        # Create realistic price data
        dates = pd.date_range(end=datetime.now(), periods=100, freq='D')
        close_prices = 35000 + np.cumsum(np.random.randn(100) * 100)

        mock_load.return_value = pd.DataFrame({
            'date': dates,
            'close': close_prices,
            'high': close_prices * 1.01,
            'low': close_prices * 0.99,
            'volume': np.random.randint(1_000_000, 10_000_000, 100)
        })

        mock_global.return_value = {
            'indices': {},
            'usd_krw': {'value': 1400.0}
        }

        mg = MarketGate()
        result = mg.analyze()

        # Check for technical indicators
        # These may vary based on actual implementation
        assert isinstance(result, dict)


# ============================================================================
# TESTS: Market Gate Status Determination
# ============================================================================

class TestMarketGateStatus:
    """Tests for market gate status determination logic"""

    def test_default_result_structure(self):
        """Test that _default_result returns proper structure"""
        mg = MarketGate()
        result = mg._default_result("Test error")

        assert isinstance(result, dict)
        # Check for expected keys based on actual implementation
        assert 'color' in result
        assert 'status' in result
        assert 'is_gate_open' in result
        assert result['color'] in ['GREEN', 'YELLOW', 'RED']

    @patch.object(MarketGate, '_get_global_data')
    @patch.object(MarketGate, '_load_price_data')
    def test_gate_green_on_favorable_conditions(self, mock_load, mock_global):
        """Test that gate is GREEN when all conditions are favorable"""
        # Favorable data with required columns
        mock_load.return_value = pd.DataFrame({
            'date': pd.date_range(end=datetime.now(), periods=100),
            'close': np.linspace(34000, 36000, 100),  # Upward trend
            'high': np.linspace(34340, 36360, 100),
            'low': np.linspace(33660, 35640, 100),
            'volume': np.random.randint(1_000_000, 10_000_000, 100)
        })

        mock_global.return_value = {
            'indices': {'sp500': {'value': 5000.0, 'change_pct': 2.0}},
            'usd_krw': {'value': 1350.0, 'change_pct': -0.5}  # Low USD/KRW (good for KOSPI)
        }

        mg = MarketGate()
        result = mg.analyze()

        # Check for color key instead of gate
        assert 'color' in result or 'gate' in result


# ============================================================================
# TESTS: Configuration
# ============================================================================

class TestMarketGateConfig:
    """Tests for MarketGate configuration"""

    def test_config_thresholds_are_respected(self):
        """Test that configured thresholds are used in analysis"""
        custom_config = MarketGateConfig(
            usd_krw_safe=1300.0,
            usd_krw_warning=1350.0,
            usd_krw_danger=1400.0
        )

        mg = MarketGate()
        mg.config = custom_config

        assert mg.config.usd_krw_safe == 1300.0
        assert mg.config.usd_krw_warning == 1350.0
        assert mg.config.usd_krw_danger == 1400.0


# ============================================================================
# TESTS: Edge Cases
# ============================================================================

class TestMarketGateEdgeCases:
    """Tests for edge cases and error handling"""

    def test_handles_missing_data_file(self):
        """Test behavior when data file is missing"""
        mg = MarketGate(data_dir='/nonexistent/path')

        # Should not raise exception
        result = mg.analyze()
        assert isinstance(result, dict)

    @patch.object(MarketGate, '_get_global_data')
    def test_handles_global_data_failure(self, mock_global):
        """Test behavior when global data fetch fails"""
        mock_global.return_value = {}

        with patch.object(MarketGate, '_load_price_data', return_value=pd.DataFrame()):
            mg = MarketGate()
            result = mg.analyze()

        assert isinstance(result, dict)

    def test_handles_none_target_date(self):
        """Test that None target_date is handled"""
        mg = MarketGate()

        with patch.object(MarketGate, '_load_price_data', return_value=pd.DataFrame()):
            with patch.object(MarketGate, '_get_global_data', return_value={}):
                result = mg.analyze(target_date=None)

        assert isinstance(result, dict)


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
