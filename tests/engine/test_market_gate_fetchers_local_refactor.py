#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Market Gate local fetchers 리팩토링 회귀 테스트
"""

from __future__ import annotations

import logging
import os
import time

import pandas as pd

from engine.market_gate_logic_fetchers import load_price_data, load_supply_data


def test_load_price_data_uses_cached_csv(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    csv_path = data_dir / "daily_prices.csv"
    pd.DataFrame(
        [
            {"date": "2026-02-20", "ticker": "069500", "close": 100, "volume": 1000, "change_pct": 1.0},
            {"date": "2026-02-21", "ticker": "069500", "close": 101, "volume": 1100, "change_pct": 1.0},
            {"date": "2026-02-21", "ticker": "005930", "close": 50000, "volume": 2000, "change_pct": 0.5},
        ]
    ).to_csv(csv_path, index=False)

    calls = {"count": 0}
    original_read_csv = pd.read_csv

    def _counting_read_csv(*args, **kwargs):
        calls["count"] += 1
        return original_read_csv(*args, **kwargs)

    monkeypatch.setattr(pd, "read_csv", _counting_read_csv)

    first = load_price_data(
        data_dir=str(data_dir),
        kodex_ticker="069500",
        target_date="2026-02-21",
        logger=logging.getLogger(__name__),
    )
    second = load_price_data(
        data_dir=str(data_dir),
        kodex_ticker="069500",
        target_date="2026-02-21",
        logger=logging.getLogger(__name__),
    )

    assert calls["count"] == 1
    assert len(first) == 2
    assert len(second) == 2

    pd.DataFrame(
        [
            {"date": "2026-02-20", "ticker": "069500", "close": 100, "volume": 1000, "change_pct": 1.0},
            {"date": "2026-02-21", "ticker": "069500", "close": 101, "volume": 1100, "change_pct": 1.0},
            {"date": "2026-02-22", "ticker": "069500", "close": 102, "volume": 1200, "change_pct": 1.0},
        ]
    ).to_csv(csv_path, index=False)
    now = time.time()
    os.utime(csv_path, (now + 2, now + 2))

    third = load_price_data(
        data_dir=str(data_dir),
        kodex_ticker="069500",
        target_date="2026-02-22",
        logger=logging.getLogger(__name__),
    )

    assert calls["count"] == 2
    assert len(third) == 3


def test_load_supply_data_reads_latest_values(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    csv_path = data_dir / "all_institutional_trend_data.csv"
    pd.DataFrame(
        [
            {"date": "2026-02-20", "foreign_buy": 100, "inst_buy": 200},
            {"date": "2026-02-21", "foreign_buy": 300, "inst_buy": 400},
        ]
    ).to_csv(csv_path, index=False)

    loaded = load_supply_data(
        data_dir=str(data_dir),
        kis=None,
        logger=logging.getLogger(__name__),
    )

    assert loaded["foreign_buy"] == 300
    assert loaded["inst_buy"] == 400

