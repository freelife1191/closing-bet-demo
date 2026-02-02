import sys
import os
import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock Flask and dependencies before importing app
sys.modules['flask'] = MagicMock()
# Configure Blueprint to support route decorator
mock_bp = MagicMock()
def route_decorator(rule, **options):
    def decorator(f):
        return f
    return decorator
mock_bp.route.side_effect = route_decorator
# When Blueprint() is called, return our configured mock_bp
sys.modules['flask'].Blueprint.return_value = mock_bp

sys.modules['flask'].request = MagicMock()
sys.modules['flask'].jsonify = lambda x: x # Simple bypass
sys.modules['flask'].current_app = MagicMock()

# Mock Logger
logging = MagicMock()
sys.modules['logging'] = logging

# Now import the module to test
# Since we are mocking everything, we need to be careful about imports inside the module
# We will use patching for that.

from app.routes import kr_market

class TestKRSignals(unittest.TestCase):
    def setUp(self):
        # Setup mock data for signals_log.csv
        self.mock_signals_df = pd.DataFrame([{
            'ticker': '005930',
            'name': 'Samsung Elec',
            'signal_date': '2025-01-01',
            'status': 'OPEN',
            'score': 80,
            'entry_price': 50000,
            'contraction_ratio': 0.5,
            'foreign_5d': 100,
            'inst_5d': 100
        }])
        
        # Setup mock data for ticker_to_yahoo_map.csv
        self.mock_map_df = pd.DataFrame([
            {'ticker': '005930', 'yahoo_ticker': '005930.KS'}
        ])

    @patch('app.routes.kr_market.load_csv_file')
    @patch('yfinance.download')
    @patch('os.path.exists')
    @patch('pandas.read_csv')
    def test_get_kr_signals_yfinance_update(self, mock_read_csv, mock_exists, mock_yf_download, mock_load_csv):
        # 1. Setup Data Loading Mocks
        # First load_csv_file is for signals_log.csv
        # Note: logic calls load_csv_file('signals_log.csv') then later MIGHT call it again?
        # The new logic doesn't call load_csv_file for daily_prices unless in fallback?
        # Actually in new logic I removed the daily_prices loading block for signals update and replaced with yfinance.
        # But signals loading itself uses load_csv_file.
        mock_load_csv.side_effect = [self.mock_signals_df] 
        
        # os.path.exists for map file
        mock_exists.return_value = True
        
        # read_csv for map file
        mock_read_csv.return_value = self.mock_map_df
        
        # 2. Setup YFinance Mock
        # Mock price data: Close at 55000 (10% return)
        # yfinance.download returns a DataFrame.
        # If single ticker '005930.KS', columns could be MultiIndex or simple if grouped_by ticker?
        # Default auto_adjust=False, actions=False.
        # If multiple tickers, columns are (Price, Ticker). 
        # If single ticker, columns are Price types (Open, High, Low, Close...)
        # My code handles both but let's mock a simple DataFrame with 'Close'
        mock_price_data = pd.DataFrame({
            'Close': [55000.0]
        }, index=[pd.Timestamp('2025-01-02')])
        # Note: If my code accesses ['Close'], this works.
        
        mock_yf_download.return_value = mock_price_data

        # 3. Method Injection for request args (dummy)
        kr_market.request.args = {}
        
        # 4. Run Function
        result = kr_market.get_kr_signals()
        
        # 5. Assertions
        print("\n=== Test Result ===")
        print(f"DEBUG: Result Type: {type(result)}")
        print(f"DEBUG: Result Content: {result}")
        
        # Check if signals list is not empty
        self.assertTrue('signals' in result, f"Result does not contain 'signals'. Result: {result}")
        signals = result['signals']
        self.assertTrue(len(signals) > 0)
        
        signal = signals[0]
        print(f"Signal: {signal}")
        
        # Check if current_price is updated to 55000
        # If my code logic works, it should update.
        self.assertEqual(signal['current_price'], 55000.0)
        
        # Check if return_pct is calculated correctly
        # Entry: 50000, Current: 55000 -> (55000-50000)/50000 = 0.1 = 10%
        # return_pct is * 100 -> 10.0
        self.assertEqual(signal['return_pct'], 10.0)
        
        # Verify yfinance was called
        mock_yf_download.assert_called()
        print("✅ yfinance.download was called.")
        print("✅ Current Price updated to 55000.0")
        print("✅ Return % calculated as 10.0%")

if __name__ == '__main__':
    unittest.main()
