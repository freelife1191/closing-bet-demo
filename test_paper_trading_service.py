
import unittest
import sqlite3
import os
import time
from services.paper_trading import PaperTradingService

# Mock Config if needed, but we are testing the actual service against a test DB
class TestPaperTradingService(unittest.TestCase):
    def setUp(self):
        # Use a temporary database for testing
        self.service = PaperTradingService()
        # Override DB path for safety (optional, but good practice)
        # For now, we'll verify the methods don't crash on the actual DB dev instance
        # assuming it's safe to record history (it handles conflict safely)

    def test_1_record_asset_history(self):
        print("\n[Test] Verifying record_asset_history fix...")
        try:
            # Should not crash now
            self.service.record_asset_history(5000000) 
            print("✅ record_asset_history executed successfully")
        except NameError as ne:
            self.fail(f"❌ NameError still exists: {ne}")
        except Exception as e:
            self.fail(f"❌ Other error in record_asset_history: {e}")

    def test_2_portfolio_valuation_flow(self):
        print("\n[Test] Verifying get_portfolio_valuation...")
        try:
            # First call triggers background sync if needed
            val = self.service.get_portfolio_valuation()
            print(f"✅ Initial Valuation: Total Asset={val['total_asset_value']}")
            
            # Since we can't easily wait for the thread in a unit test without mocking,
            # we just ensure the method returns a valid structure
            self.assertIn('total_asset_value', val)
            self.assertIn('holdings', val)
            self.assertIn('cash', val)
            
        except Exception as e:
            self.fail(f"❌ get_portfolio_valuation crash: {e}")

    def test_3_wait_logic(self):
        print("\n[Test] Verifying wait logic...")
        # Clear cache first
        with self.service.cache_lock:
            self.service.price_cache = {}
        
        # Mock thread being alive
        import threading
        # Thread that sleeps to simulate being "busy"
        self.service.bg_thread = threading.Thread(target=lambda: time.sleep(2)) 
        self.service.bg_thread.start()
        
        # Simulate background update after 1 second
        def background_update():
            time.sleep(1)
            with self.service.cache_lock:
                self.service.price_cache = {'005930': 70000}
                
        threading.Thread(target=background_update).start()
        
        start_time = time.time()
        
        # Helper: Clean DB for idempotency
        conn = self.service.get_context()
        conn.execute("DELETE FROM portfolio WHERE ticker = '005930'")
        conn.commit()
        
        # Insert a dummy holding
        conn.execute("INSERT INTO portfolio (ticker, name, avg_price, quantity) VALUES ('005930', 'Test', 60000, 10)")
        conn.commit()
        conn.close()
        
        val = self.service.get_portfolio_valuation()
        duration = time.time() - start_time
        
        print(f"✅ Wait Duration: {duration:.2f}s")
        self.assertGreater(duration, 0.8, "Should have waited for at least 0.8s")
        self.assertIn('005930', self.service.price_cache, "Cache should be populated")

if __name__ == '__main__':
    unittest.main()
