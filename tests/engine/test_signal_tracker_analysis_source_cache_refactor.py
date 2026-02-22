#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Signal Tracker analysis source cache 리팩토링 테스트
"""

from __future__ import annotations

import os
import sqlite3

import pandas as pd

import engine.signal_tracker_analysis_source_cache as source_cache


def test_usecols_signature_is_compact_and_sorted():
    signature = source_cache._usecols_signature({"close", "ticker"})
    assert signature == '["close","ticker"]'


def test_load_csv_with_signature_cache_normalizes_relative_and_absolute_path(monkeypatch, tmp_path):
    csv_path = tmp_path / "sample.csv"
    pd.DataFrame([{"ticker": "005930", "score": 90}]).to_csv(csv_path, index=False, encoding="utf-8-sig")

    monkeypatch.chdir(tmp_path)
    calls = {"count": 0}
    original_read_csv = source_cache.pd.read_csv

    def _counted_read_csv(*args, **kwargs):
        calls["count"] += 1
        return original_read_csv(*args, **kwargs)

    monkeypatch.setattr(source_cache.pd, "read_csv", _counted_read_csv)

    cache: dict[str, tuple[tuple[int, int, int], pd.DataFrame]] = {}
    first = source_cache.load_csv_with_signature_cache(
        path="sample.csv",
        usecols_filter=None,
        cache=cache,
        sqlite_cache_kind=None,
    )
    second = source_cache.load_csv_with_signature_cache(
        path=str(csv_path),
        usecols_filter=None,
        cache=cache,
        sqlite_cache_kind=None,
    )

    assert len(first) == 1
    assert len(second) == 1
    assert calls["count"] == 1
    assert list(cache.keys()) == [os.path.abspath(str(csv_path))]


def test_load_csv_with_signature_cache_creates_sqlite_parent_dir_when_missing(monkeypatch, tmp_path):
    csv_path = tmp_path / "signals_log.csv"
    pd.DataFrame(
        [
            {
                "status": "OPEN",
                "return_pct": 0.0,
                "signal_date": "2026-02-20",
                "exit_date": "",
                "hold_days": 1,
            }
        ]
    ).to_csv(csv_path, index=False, encoding="utf-8-sig")

    db_path = tmp_path / "cache" / "nested" / "runtime_cache.db"
    source_cache.PERFORMANCE_SOURCE_CACHE.clear()
    source_cache.CSV_SOURCE_SQLITE_READY.clear()
    monkeypatch.setattr(source_cache, "_source_cache_db_path", lambda _path: str(db_path))

    cache: dict[str, tuple[tuple[int, int, int], pd.DataFrame]] = {}
    loaded = source_cache.load_csv_with_signature_cache(
        path=str(csv_path),
        usecols_filter={"status", "return_pct", "signal_date", "exit_date", "hold_days"},
        cache=cache,
        sqlite_cache_kind="performance_source",
    )

    assert len(loaded) == 1
    assert db_path.exists()

    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM signal_tracker_csv_source_cache
            WHERE cache_kind = ?
            """,
            ("performance_source",),
        )
        row = cursor.fetchone()
    assert row and row[0] >= 1


def test_load_csv_with_signature_cache_prunes_sqlite_rows(monkeypatch, tmp_path):
    db_path = tmp_path / "runtime_cache.db"
    source_cache.CSV_SOURCE_SQLITE_READY.clear()
    source_cache.PERFORMANCE_SOURCE_CACHE.clear()
    monkeypatch.setattr(source_cache, "_source_cache_db_path", lambda _path: str(db_path))
    monkeypatch.setattr(source_cache, "CSV_SOURCE_SQLITE_MAX_ROWS", 2)

    for index in range(3):
        csv_path = tmp_path / f"signals_{index}.csv"
        pd.DataFrame(
            [
                {
                    "status": "OPEN",
                    "return_pct": float(index),
                    "signal_date": "2026-02-20",
                    "exit_date": "",
                    "hold_days": 1,
                }
            ]
        ).to_csv(csv_path, index=False, encoding="utf-8-sig")

        cache: dict[str, tuple[tuple[int, int, int], pd.DataFrame]] = {}
        loaded = source_cache.load_csv_with_signature_cache(
            path=str(csv_path),
            usecols_filter={"status", "return_pct", "signal_date", "exit_date", "hold_days"},
            cache=cache,
            sqlite_cache_kind=f"performance_source_{index}",
        )
        assert len(loaded) == 1

    with sqlite3.connect(str(db_path)) as conn:
        row_count = int(
            conn.execute("SELECT COUNT(*) FROM signal_tracker_csv_source_cache").fetchone()[0]
        )
    assert row_count == 2


def test_load_csv_with_signature_cache_recovers_when_sqlite_table_missing(monkeypatch, tmp_path):
    db_path = tmp_path / "runtime_cache.db"
    source_cache.CSV_SOURCE_SQLITE_READY.clear()
    source_cache.PERFORMANCE_SOURCE_CACHE.clear()
    monkeypatch.setattr(source_cache, "_source_cache_db_path", lambda _path: str(db_path))

    first_csv = tmp_path / "signals_first.csv"
    pd.DataFrame(
        [
            {"status": "OPEN", "return_pct": 1.0, "signal_date": "2026-02-20", "exit_date": "", "hold_days": 1}
        ]
    ).to_csv(first_csv, index=False, encoding="utf-8-sig")

    cache: dict[str, tuple[tuple[int, int, int], pd.DataFrame]] = {}
    first_loaded = source_cache.load_csv_with_signature_cache(
        path=str(first_csv),
        usecols_filter={"status", "return_pct", "signal_date", "exit_date", "hold_days"},
        cache=cache,
        sqlite_cache_kind="performance_source",
    )
    assert len(first_loaded) == 1

    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("DROP TABLE signal_tracker_csv_source_cache")
        conn.commit()

    second_csv = tmp_path / "signals_second.csv"
    pd.DataFrame(
        [
            {"status": "OPEN", "return_pct": 2.0, "signal_date": "2026-02-21", "exit_date": "", "hold_days": 2}
        ]
    ).to_csv(second_csv, index=False, encoding="utf-8-sig")

    cache = {}
    second_loaded = source_cache.load_csv_with_signature_cache(
        path=str(second_csv),
        usecols_filter={"status", "return_pct", "signal_date", "exit_date", "hold_days"},
        cache=cache,
        sqlite_cache_kind="performance_source",
    )
    assert len(second_loaded) == 1
    assert float(second_loaded.iloc[0]["return_pct"]) == 2.0

    with sqlite3.connect(str(db_path)) as conn:
        row_count = int(conn.execute("SELECT COUNT(*) FROM signal_tracker_csv_source_cache").fetchone()[0])
    assert row_count >= 1


def test_load_csv_with_signature_cache_skips_delete_when_rows_within_limit(monkeypatch, tmp_path):
    db_path = tmp_path / "runtime_cache.db"
    source_cache.CSV_SOURCE_SQLITE_READY.clear()
    source_cache.PERFORMANCE_SOURCE_CACHE.clear()
    monkeypatch.setattr(source_cache, "_source_cache_db_path", lambda _path: str(db_path))
    monkeypatch.setattr(source_cache, "CSV_SOURCE_SQLITE_MAX_ROWS", 16)

    traced_sql: list[str] = []
    original_connect = source_cache.connect_sqlite

    def _traced_connect(*args, **kwargs):
        conn = original_connect(*args, **kwargs)
        conn.set_trace_callback(traced_sql.append)
        return conn

    monkeypatch.setattr(source_cache, "connect_sqlite", _traced_connect)

    csv_path = tmp_path / "signals_single.csv"
    pd.DataFrame(
        [
            {"status": "OPEN", "return_pct": 1.0, "signal_date": "2026-02-22", "exit_date": "", "hold_days": 1}
        ]
    ).to_csv(csv_path, index=False, encoding="utf-8-sig")

    cache: dict[str, tuple[tuple[int, int, int], pd.DataFrame]] = {}
    loaded = source_cache.load_csv_with_signature_cache(
        path=str(csv_path),
        usecols_filter={"status", "return_pct", "signal_date", "exit_date", "hold_days"},
        cache=cache,
        sqlite_cache_kind="performance_source",
    )
    assert len(loaded) == 1
    assert not any("DELETE FROM signal_tracker_csv_source_cache" in sql for sql in traced_sql)
