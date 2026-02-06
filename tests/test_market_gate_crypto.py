
import unittest
from unittest.mock import patch, MagicMock
import sys
import os
import math
import pandas as pd

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.market_gate import MarketGate

class TestMarketGateCrypto(unittest.TestCase):
    def setUp(self):
        self.mg = MarketGate()

    def test_crypto_logic_integration(self):
        """실제 외부 API를 호출하여 데이터 포맷이 올바른지 확인하는 통합 테스트"""
        try:
            print("\n--- Running Integration Test ---")
            result = self.mg.analyze()
            crypto = result.get('crypto', {})
            
            for key in ['btc', 'eth', 'xrp']:
                self.assertIn(key, crypto)
                data = crypto[key]
                
                # Check value validity
                value = data.get('value')
                self.assertIsNotNone(value)
                self.assertGreater(value, 0)
                
                # Check change_pct validity (Must not be None)
                # 0.0 could happen, but ensure it's a valid float
                change = data.get('change_pct')
                self.assertIsNotNone(change, f"{key} change_pct should not be None")
                self.assertIsInstance(change, (int, float))
                
                print(f"✅ {key.upper()}: Value=${value}, Change={change}%")
                
        except Exception as e:
            self.fail(f"MarketGate analyze failed: {e}")

if __name__ == '__main__':
    unittest.main()
