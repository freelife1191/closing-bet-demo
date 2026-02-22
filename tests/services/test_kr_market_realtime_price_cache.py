#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market realtime price cache(SQLite) 테스트
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from services.kr_market_realtime_price_cache import (
    load_cached_realtime_prices,
    save_realtime_prices_to_cache,
)


def test_realtime_price_cache_roundtrip(tmp_path: Path):
    get_data_path = lambda filename: str(tmp_path / filename)

    save_realtime_prices_to_cache(
        {"5930": 123.4, "000660": 0.0},
        source="test",
        get_data_path=get_data_path,
    )

    loaded = load_cached_realtime_prices(
        ["005930", "000660"],
        get_data_path=get_data_path,
        max_age_seconds=3600,
    )
    assert loaded == {"005930": 123.4}

    with sqlite3.connect(tmp_path / "runtime_cache.db") as conn:
        row_count = conn.execute("SELECT COUNT(*) FROM realtime_price_cache").fetchone()[0]
    assert int(row_count) == 1


def test_realtime_price_cache_respects_ttl(tmp_path: Path):
    get_data_path = lambda filename: str(tmp_path / filename)

    save_realtime_prices_to_cache(
        {"005930": 101.0},
        source="test",
        get_data_path=get_data_path,
    )

    db_path = tmp_path / "runtime_cache.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE realtime_price_cache SET updated_at = ? WHERE ticker = ?",
            ((datetime.now() - timedelta(hours=1)).isoformat(), "005930"),
        )
        conn.commit()

    loaded = load_cached_realtime_prices(
        ["005930"],
        get_data_path=get_data_path,
        max_age_seconds=60,
    )
    assert loaded == {}
