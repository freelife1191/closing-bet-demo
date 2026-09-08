#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""개인 계정의 자산 기록·평가·시세 대기를 격리 DB에서 검증한다."""

import tempfile
import threading
import time
import unittest
from pathlib import Path

from services.paper_trading import PaperTradingService


class TestPaperTradingService(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="portfolio-regression-")
        self.addCleanup(temporary.cleanup)
        self.owner = "regression@example.test"
        self.service = PaperTradingService(
            db_path=str(Path(temporary.name) / "accounts.sqlite3"), auto_start_sync=False
        )

    def test_1_record_asset_history(self):
        self.service.record_asset_history(5_000_000, owner_id=self.owner)
        with self.service.get_read_context() as conn:
            row = conn.execute(
                "SELECT total_asset, cash, stock_value FROM asset_history WHERE owner_id=?",
                (self.owner,),
            ).fetchone()
        self.assertEqual(row, (105_000_000, 100_000_000, 5_000_000))

    def test_2_portfolio_valuation_flow(self):
        value = self.service.get_portfolio_valuation(owner_id=self.owner)
        self.assertEqual(value["total_asset_value"], 100_000_000)
        self.assertEqual(value["cash"], 100_000_000)
        self.assertEqual(value["holdings"], [])

    def test_3_wait_logic(self):
        self.service.buy_stock("005930", "Test", 60_000, 10, owner_id=self.owner)
        done = threading.Event()
        self.service.bg_thread = threading.Thread(target=lambda: done.wait(3))

        def background_update():
            time.sleep(1)
            with self.service.cache_lock:
                self.service.price_cache["005930"] = 70_000

        updater = threading.Thread(target=background_update)
        self.service.bg_thread.start()
        updater.start()
        try:
            start = time.monotonic()
            value = self.service.get_portfolio_valuation(owner_id=self.owner)
            self.assertGreater(time.monotonic() - start, 0.8)
            self.assertEqual(value["holdings"][0]["current_price"], 70_000)
        finally:
            done.set()
            updater.join(timeout=3)
            self.service.bg_thread.join(timeout=3)
            self.assertFalse(updater.is_alive())
            self.assertFalse(self.service.bg_thread.is_alive())


if __name__ == "__main__":
    unittest.main()
