#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Signal Tracker source cache 리팩토링 테스트
"""

from __future__ import annotations

import os
import sqlite3

import pandas as pd

import engine.signal_tracker_source_cache as source_cache


def test_serialize_signatures_are_compact_json():
    usecols_signature = source_cache._serialize_usecols(["ticker", "close"])
    dtype_signature = source_cache._serialize_dtype({"ticker": "str", "close": "float64"})

    assert usecols_signature == '["ticker","close"]'
    assert dtype_signature == '{"close":"float64","ticker":"str"}'


def test_load_signal_tracker_csv_cached_creates_sqlite_parent_dir_when_missing(monkeypatch, tmp_path):
    csv_path = tmp_path / "daily_prices.csv"
    pd.DataFrame(
        [
            {"ticker": "005930", "close": 100.0, "volume": 1_000},
        ]
    ).to_csv(csv_path, index=False, encoding="utf-8-sig")

    db_path = tmp_path / "cache" / "nested" / "runtime_cache.db"
    source_cache.clear_signal_tracker_source_cache(reset_sqlite_state=True)
    monkeypatch.setattr(source_cache, "_resolve_db_path", lambda _path: str(db_path))

    loaded = source_cache.load_signal_tracker_csv_cached(
        path=str(csv_path),
        cache_kind="price_source",
        usecols=["ticker", "close"],
        dtype={"ticker": str},
    )

    assert len(loaded) == 1
    assert loaded.iloc[0]["ticker"] == "005930"
    assert db_path.exists()

    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM signal_tracker_source_cache
            WHERE cache_kind = ?
            """,
            ("price_source",),
        )
        row = cursor.fetchone()
    assert row and row[0] >= 1


def test_load_signal_tracker_csv_cached_prunes_sqlite_rows(monkeypatch, tmp_path):
    db_path = tmp_path / "runtime_cache.db"
    source_cache.clear_signal_tracker_source_cache(reset_sqlite_state=True)
    monkeypatch.setattr(source_cache, "_resolve_db_path", lambda _path: str(db_path))
    monkeypatch.setattr(source_cache, "_SOURCE_SQLITE_MAX_ROWS", 2)

    for idx in range(3):
        csv_path = tmp_path / f"daily_prices_{idx}.csv"
        pd.DataFrame(
            [
                {"ticker": "005930", "close": 100.0 + idx, "volume": 1_000 + idx},
            ]
        ).to_csv(csv_path, index=False, encoding="utf-8-sig")

        loaded = source_cache.load_signal_tracker_csv_cached(
            path=str(csv_path),
            cache_kind=f"price_source_{idx}",
            usecols=["ticker", "close"],
            dtype={"ticker": str},
        )
        assert len(loaded) == 1

    with sqlite3.connect(str(db_path)) as conn:
        row_count = int(
            conn.execute("SELECT COUNT(*) FROM signal_tracker_source_cache").fetchone()[0]
        )
    assert row_count == 2


def test_load_signal_tracker_csv_cached_recovers_when_sqlite_table_missing(monkeypatch, tmp_path):
    db_path = tmp_path / "runtime_cache.db"
    source_cache.clear_signal_tracker_source_cache(reset_sqlite_state=True)
    monkeypatch.setattr(source_cache, "_resolve_db_path", lambda _path: str(db_path))

    first_csv = tmp_path / "daily_prices_first.csv"
    first_csv.write_text("ticker,close\n005930,100\n", encoding="utf-8")
    loaded_first = source_cache.load_signal_tracker_csv_cached(
        path=str(first_csv),
        cache_kind="price_source",
        usecols=["ticker", "close"],
        dtype={"ticker": str},
    )
    assert len(loaded_first) == 1

    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("DROP TABLE signal_tracker_source_cache")
        conn.commit()

    second_csv = tmp_path / "daily_prices_second.csv"
    second_csv.write_text("ticker,close\n000660,200\n", encoding="utf-8")
    loaded_second = source_cache.load_signal_tracker_csv_cached(
        path=str(second_csv),
        cache_kind="price_source",
        usecols=["ticker", "close"],
        dtype={"ticker": str},
    )
    assert len(loaded_second) == 1
    assert loaded_second.iloc[0]["ticker"] == "000660"

    with sqlite3.connect(str(db_path)) as conn:
        row_count = int(conn.execute("SELECT COUNT(*) FROM signal_tracker_source_cache").fetchone()[0])
    assert row_count >= 1


def test_load_signal_tracker_csv_cached_skips_delete_when_rows_within_limit(monkeypatch, tmp_path):
    db_path = tmp_path / "runtime_cache.db"
    source_cache.clear_signal_tracker_source_cache(reset_sqlite_state=True)
    monkeypatch.setattr(source_cache, "_resolve_db_path", lambda _path: str(db_path))
    monkeypatch.setattr(source_cache, "_SOURCE_SQLITE_MAX_ROWS", 16)

    traced_sql: list[str] = []
    original_connect = source_cache.connect_sqlite

    def _traced_connect(*args, **kwargs):
        conn = original_connect(*args, **kwargs)
        conn.set_trace_callback(traced_sql.append)
        return conn

    monkeypatch.setattr(source_cache, "connect_sqlite", _traced_connect)

    csv_path = tmp_path / "daily_prices_single.csv"
    pd.DataFrame([{"ticker": "005930", "close": 100.0}]).to_csv(csv_path, index=False, encoding="utf-8-sig")

    loaded = source_cache.load_signal_tracker_csv_cached(
        path=str(csv_path),
        cache_kind="price_source",
        usecols=["ticker", "close"],
        dtype={"ticker": str},
    )
    assert len(loaded) == 1
    assert not any("DELETE FROM signal_tracker_source_cache" in sql for sql in traced_sql)


def test_signal_tracker_source_sqlite_ready_cache_uses_normalized_db_key(monkeypatch, tmp_path):
    source_cache.clear_signal_tracker_source_cache(reset_sqlite_state=True)
    db_path = tmp_path / "runtime_cache.db"
    connect_calls = {"count": 0}
    original_connect = source_cache.connect_sqlite

    def _counted_connect(*args, **kwargs):
        connect_calls["count"] += 1
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(source_cache, "connect_sqlite", _counted_connect)

    assert source_cache._ensure_source_cache_sqlite(str(db_path), None) is True

    monkeypatch.chdir(tmp_path)
    relative_db_path = os.path.relpath(str(db_path), str(tmp_path))
    assert source_cache._ensure_source_cache_sqlite(relative_db_path, None) is True

    assert connect_calls["count"] == 1
