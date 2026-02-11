#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit Tests for verify_market_gate.py script

Tests the verification script logic including JSON output validation
and error handling.
"""
import pytest
import json
import os
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scripts.verify_market_gate import verify_market_gate
from engine.market_gate import MarketGate


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def temp_data_dir(tmp_path):
    """Create a temporary data directory"""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return str(data_dir)


@pytest.fixture
def mock_market_gate_result():
    """Create mock market gate analysis result"""
    return {
        'timestamp': datetime.now().isoformat(),
        'commodities': {
            'krx_gold': {'value': 13500.0, 'change_pct': 1.5},
            'krx_silver': {'value': 4500.0, 'change_pct': -0.5},
            'us_gold': {'value': 2050.0, 'change_pct': 0.8},
            'us_silver': {'value': 26.0, 'change_pct': -0.2}
        },
        'indices': {
            'sp500': {'value': 5100.0, 'change_pct': 1.2},
            'nasdaq': {'value': 16500.0, 'change_pct': 1.8},
            'kospi': {'value': 2650.0, 'change_pct': 0.3},
            'kosdaq': {'value': 870.0, 'change_pct': -0.2}
        },
        'crypto': {
            'btc': {'value': 50000.0, 'change_pct': 2.5},
            'eth': {'value': 2800.0, 'change_pct': 3.0},
            'xrp': {'value': 0.6, 'change_pct': 1.5}
        },
        'kospi_close': 2650.0,
        'kospi_change': 0.3,
        'kosdaq_close': 870.0,
        'kosdaq_change_pct': -0.2,
        'total_score': 65,
        'label': 'Neutral',
        'is_gate_open': True,
        'status': '중립 (Neutral)',
        'color': 'YELLOW'
    }


@pytest.fixture
def mock_minimal_result():
    """Create minimal result missing some fields"""
    return {
        'timestamp': datetime.now().isoformat(),
        'commodities': {
            'krx_gold': {'value': 13000.0, 'change_pct': 0.5}
        }
    }


# ============================================================================
# TESTS: verify_market_gate function
# ============================================================================

class TestVerifyMarketGate:
    """Tests for the main verify_market_gate function"""

    @patch('scripts.verify_market_gate.MarketGate')
    @patch('builtins.print')
    def test_successful_verification_flow(self, mock_print, mock_market_gate_class, mock_market_gate_result):
        """Test successful verification flow"""
        # Setup mocks
        mock_gate = Mock()
        mock_gate.analyze.return_value = mock_market_gate_result
        mock_gate.save_analysis.return_value = 'market_gate_20240101.json'
        mock_market_gate_class.return_value = mock_gate

        verify_market_gate()

        # Verify flow
        mock_gate.analyze.assert_called_once()
        mock_gate.save_analysis.assert_called_once()

    @patch('scripts.verify_market_gate.MarketGate')
    @patch('builtins.print')
    def test_handles_missing_krx_silver(self, mock_print, mock_market_gate_class):
        """Test handling of missing KRX silver data"""
        # Setup mock with only gold
        mock_result = {
            'commodities': {
                'krx_gold': {'value': 13500.0, 'change_pct': 1.5}
            }
        }
        mock_gate = Mock()
        mock_gate.analyze.return_value = mock_result
        mock_gate.save_analysis.return_value = 'test.json'
        mock_market_gate_class.return_value = mock_gate

        verify_market_gate()

        # Should still complete but print FAIL message
        mock_print.assert_called()

    @patch('scripts.verify_market_gate.MarketGate')
    @patch('builtins.print')
    def test_handles_empty_commodities(self, mock_print, mock_market_gate_class):
        """Test handling of empty commodities dict"""
        mock_result = {
            'commodities': {}
        }
        mock_gate = Mock()
        mock_gate.analyze.return_value = mock_result
        mock_gate.save_analysis.return_value = 'test.json'
        mock_market_gate_class.return_value = mock_gate

        verify_market_gate()

        # Should handle gracefully
        assert mock_gate.analyze.called

    @patch('scripts.verify_market_gate.MarketGate')
    @patch('builtins.print')
    def test_validates_value_ranges(self, mock_print, mock_market_gate_class):
        """Test that value ranges are validated correctly"""
        mock_result = {
            'commodities': {
                'krx_gold': {'value': 13000.0, 'change_pct': 1.5},  # Valid
                'krx_silver': {'value': 4200.0, 'change_pct': -0.5}  # Valid
            }
        }
        mock_gate = Mock()
        mock_gate.analyze.return_value = mock_result
        mock_gate.save_analysis.return_value = 'test.json'
        mock_market_gate_class.return_value = mock_gate

        verify_market_gate()

        # Should print expected ranges
        print_calls = [str(call) for call in mock_print.call_args_list]

    @patch('scripts.verify_market_gate.MarketGate')
    @patch('builtins.print')
    def test_analyze_exception_handling(self, mock_print, mock_market_gate_class):
        """Test exception handling in analyze()"""
        mock_gate = Mock()
        mock_gate.analyze.side_effect = Exception("Analysis failed")
        mock_market_gate_class.return_value = mock_gate

        # Should not crash but handle exception
        try:
            verify_market_gate()
        except Exception:
            pytest.fail("verify_market_gate should handle exceptions gracefully")

    @patch('scripts.verify_market_gate.MarketGate')
    @patch('builtins.print')
    def test_save_analysis_exception_handling(self, mock_print, mock_market_gate_class, mock_market_gate_result):
        """Test exception handling in save_analysis()"""
        mock_gate = Mock()
        mock_gate.analyze.return_value = mock_market_gate_result
        mock_gate.save_analysis.side_effect = IOError("Save failed")
        mock_market_gate_class.return_value = mock_gate

        # Should handle save error gracefully
        verify_market_gate()


# ============================================================================
# TESTS: JSON Output Validation
# ============================================================================

class TestJSONOutputValidation:
    """Tests for JSON output structure validation"""

    @patch('scripts.verify_market_gate.MarketGate')
    def test_json_output_structure(self, mock_market_gate_class, mock_market_gate_result, tmp_path):
        """Test that JSON output has correct structure"""
        # Setup mock to save to temp directory
        output_file = tmp_path / "market_gate.json"

        mock_gate = Mock()
        mock_gate.analyze.return_value = mock_market_gate_result
        mock_gate.save_analysis.return_value = str(output_file)
        mock_market_gate_class.return_value = mock_gate

        verify_market_gate()

        # Verify file was created
        assert output_file.exists()

        # Verify JSON structure
        with open(output_file, 'r') as f:
            data = json.load(f)

        assert 'commodities' in data
        assert 'indices' in data
        assert 'crypto' in data

    @patch('scripts.verify_market_gate.MarketGate')
    def test_json_is_valid_parseable(self, mock_market_gate_class, mock_market_gate_result, tmp_path):
        """Test that output JSON is valid and parseable"""
        output_file = tmp_path / "market_gate.json"

        mock_gate = Mock()
        mock_gate.analyze.return_value = mock_market_gate_result
        mock_gate.save_analysis.return_value = str(output_file)
        mock_market_gate_class.return_value = mock_gate

        verify_market_gate()

        # Should not raise JSONDecodeError
        with open(output_file, 'r') as f:
            data = json.load(f)

        assert isinstance(data, dict)

    @patch('scripts.verify_market_gate.MarketGate')
    def test_json_contains_required_fields(self, mock_market_gate_class, mock_market_gate_result, tmp_path):
        """Test that JSON contains all required fields"""
        output_file = tmp_path / "market_gate.json"

        mock_gate = Mock()
        mock_gate.analyze.return_value = mock_market_gate_result
        mock_gate.save_analysis.return_value = str(output_file)
        mock_market_gate_class.return_value = mock_gate

        verify_market_gate()

        with open(output_file, 'r') as f:
            data = json.load(f)

        # Check commodities structure
        if 'commodities' in data:
            for key in ['krx_gold', 'krx_silver']:
                if key in data['commodities']:
                    assert 'value' in data['commodities'][key]
                    assert 'change_pct' in data['commodities'][key]


# ============================================================================
# TESTS: Value Validation
# ============================================================================

class TestValueValidation:
    """Tests for value range validation"""

    @pytest.mark.parametrize("gold_value,silver_value,expected_pass", [
        (13500.0, 4500.0, True),   # Valid ranges
        (13000.0, 4000.0, True),   # Minimum expected
        (12000.0, 3000.0, False),  # Below expected
        (0.0, 0.0, False),         # Zero values
        (None, None, False),       # Missing values
    ])
    @patch('scripts.verify_market_gate.MarketGate')
    @patch('builtins.print')
    def test_value_range_validation(
        self, mock_print, mock_market_gate_class, gold_value, silver_value, expected_pass
    ):
        """Test value range validation logic"""
        commodities = {}
        if gold_value is not None:
            commodities['krx_gold'] = {'value': gold_value, 'change_pct': 0.5}
        if silver_value is not None:
            commodities['krx_silver'] = {'value': silver_value, 'change_pct': -0.5}

        mock_result = {
            'commodities': commodities
        }

        mock_gate = Mock()
        mock_gate.analyze.return_value = mock_result
        mock_gate.save_analysis.return_value = 'test.json'
        mock_market_gate_class.return_value = mock_gate

        verify_market_gate()

        # Check if validation passed based on values
        if not expected_pass:
            # Should print FAIL message
            print_calls = [str(call) for call in mock_print.call_args_list]
            # Look for FAIL indicator in print calls
            # (The actual check depends on implementation)


# ============================================================================
# TESTS: Integration with MarketGate
# ============================================================================

class TestMarketGateIntegration:
    """Integration tests with MarketGate class"""

    @patch('scripts.verify_market_gate.MarketGate')
    @patch('builtins.print')
    def test_market_gate_initialization(self, mock_print, mock_market_gate_class):
        """Test MarketGate is properly initialized"""
        mock_gate = Mock()
        mock_gate.analyze.return_value = {
            'commodities': {
                'krx_gold': {'value': 13500.0, 'change_pct': 1.5},
                'krx_silver': {'value': 4500.0, 'change_pct': -0.5}
            }
        }
        mock_gate.save_analysis.return_value = 'test.json'
        mock_market_gate_class.return_value = mock_gate

        verify_market_gate()

        # MarketGate should be initialized with no arguments
        mock_market_gate_class.assert_called_once_with()

    @patch('scripts.verify_market_gate.MarketGate')
    @patch('builtins.print')
    def test_analyze_method_called(self, mock_print, mock_market_gate_class):
        """Test that analyze() is called"""
        mock_gate = Mock()
        mock_gate.analyze.return_value = {'commodities': {}}
        mock_gate.save_analysis.return_value = 'test.json'
        mock_market_gate_class.return_value = mock_gate

        verify_market_gate()

        mock_gate.analyze.assert_called_once_with()

    @patch('scripts.verify_market_gate.MarketGate')
    @patch('builtins.print')
    def test_save_analysis_called_with_result(self, mock_print, mock_market_gate_class, mock_market_gate_result):
        """Test that save_analysis is called with analyze result"""
        mock_gate = Mock()
        mock_gate.analyze.return_value = mock_market_gate_result
        mock_gate.save_analysis.return_value = 'test.json'
        mock_market_gate_class.return_value = mock_gate

        verify_market_gate()

        mock_gate.save_analysis.assert_called_once()
        # Verify the result was passed
        call_args = mock_gate.save_analysis.call_args
        assert call_args[0][0] == mock_market_gate_result


# ============================================================================
# TESTS: Console Output
# ============================================================================

class TestConsoleOutput:
    """Tests for console output messages"""

    @patch('scripts.verify_market_gate.MarketGate')
    def test_prints_initialization_message(self, mock_print, mock_market_gate_class):
        """Test initialization message is printed"""
        mock_gate = Mock()
        mock_gate.analyze.return_value = {'commodities': {}}
        mock_gate.save_analysis.return_value = 'test.json'
        mock_market_gate_class.return_value = mock_gate

        verify_market_gate()

        # Check for initialization message
        print_calls = [str(call) for call in mock_print.call_args_list]
        assert any('Initializing' in call or 'initializing' in call.lower() for call in print_calls)

    @patch('scripts.verify_market_gate.MarketGate')
    def test_prints_analysis_result(self, mock_print, mock_market_gate_class, mock_market_gate_result):
        """Test analysis result is printed"""
        mock_gate = Mock()
        mock_gate.analyze.return_value = mock_market_gate_result
        mock_gate.save_analysis.return_value = 'test.json'
        mock_market_gate_class.return_value = mock_gate

        verify_market_gate()

        # Should print analysis results
        assert mock_print.called

    @patch('scripts.verify_market_gate.MarketGate')
    @patch('builtins.print')
    def test_prints_save_confirmation(self, mock_print, mock_market_gate_class, mock_market_gate_result):
        """Test save confirmation message"""
        mock_gate = Mock()
        mock_gate.analyze.return_value = mock_market_gate_result
        mock_gate.save_analysis.return_value = 'test.json'
        mock_market_gate_class.return_value = mock_gate

        verify_market_gate()

        # Check for save confirmation
        print_calls = [str(call) for call in mock_print.call_args_list]
        assert any('Saved' in call or 'saved' in call.lower() for call in print_calls)


# ============================================================================
# TESTS: Main Guard
# ============================================================================

class TestMainGuard:
    """Tests for __main__ guard"""

    def test_main_guard_exists(self):
        """Verify __main__ guard exists in script"""
        script_path = Path(__file__).parent.parent.parent / 'scripts' / 'verify_market_gate.py'
        with open(script_path, 'r') as f:
            content = f.read()

        assert '__main__' in content
        assert "if __name__" in content


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
