#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""임시 DB에서 예수금 반영과 stale P&L을 독립 검증한다."""

import os
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.paper_trading import PaperTradingService

OWNER = "pnl@example.test"


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        service = PaperTradingService(db_path=os.path.join(directory, "pnl.sqlite3"), auto_start_sync=False)
        assert service.reset_account(owner_id=OWNER)
        assert service.buy_stock("005930", "Samsung", 10_000, 10, owner_id=OWNER)["status"] == "success"
        assert service.deposit_cash(50_000_000, owner_id=OWNER)["status"] == "success"
        with service.cache_lock:
            service.price_cache.clear()
        valuation = service.get_portfolio_valuation(owner_id=OWNER)
        assert valuation["total_principal"] == 150_000_000
        assert valuation["total_profit"] == 0
        assert valuation["holdings"][0]["is_stale"] is True
        assert service.get_balance(owner_id="other@example.test") == 100_000_000
        print("PASS: owner P&L principal/profit/stale and second-owner isolation verified")


if __name__ == "__main__":
    main()
