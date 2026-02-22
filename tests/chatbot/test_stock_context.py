#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stock_context 유틸 회귀 테스트
"""

import logging
import os
import sqlite3
import sys
import time
from pathlib import Path

import pandas as pd
import pytest


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from chatbot.stock_context import (
    clear_stock_context_cache,
    fetch_institutional_trend,
    fetch_signal_history,
    fetch_stock_history,
)


LOGGER = logging.getLogger("test.stock_context")


@pytest.fixture(autouse=True)
def _clear_caches():
    clear_stock_context_cache()
    yield
    clear_stock_context_cache()


def test_fetch_stock_history_formats_recent_rows(tmp_path: Path):
    pd.DataFrame(
        [
            {"date": "2026-02-20", "ticker": "005930", "open": 10000, "close": 10100, "volume": 200000},
            {"date": "2026-02-21", "ticker": "005930", "open": 10100, "close": 10200, "volume": 210000},
        ]
    ).to_csv(tmp_path / "daily_prices.csv", index=False)

    text = fetch_stock_history(tmp_path, "5930", LOGGER)
    assert "2026-02-21" in text
    assert "종가 10,200" in text


def test_fetch_stock_history_uses_cached_csv(monkeypatch, tmp_path: Path):
    pd.DataFrame(
        [
            {"date": "2026-02-21", "ticker": "005930", "open": 10000, "close": 10100, "volume": 200000},
        ]
    ).to_csv(tmp_path / "daily_prices.csv", index=False)

    original_read_csv = pd.read_csv
    call_count = {"value": 0}

    def _counted_read_csv(*args, **kwargs):
        call_count["value"] += 1
        return original_read_csv(*args, **kwargs)

    monkeypatch.setattr(pd, "read_csv", _counted_read_csv)

    fetch_stock_history(tmp_path, "005930", LOGGER)
    fetch_stock_history(tmp_path, "005930", LOGGER)
    assert call_count["value"] == 1


def test_fetch_stock_history_reads_only_required_columns(monkeypatch, tmp_path: Path):
    pd.DataFrame(
        [
            {
                "date": "2026-02-21",
                "ticker": "005930",
                "open": 10000,
                "close": 10100,
                "volume": 200000,
                "extra_col": "x",
            },
        ]
    ).to_csv(tmp_path / "daily_prices.csv", index=False)

    original_read_csv = pd.read_csv
    captured: dict[str, object] = {}

    def _spy_read_csv(*args, **kwargs):
        captured["usecols"] = kwargs.get("usecols")
        return original_read_csv(*args, **kwargs)

    monkeypatch.setattr(pd, "read_csv", _spy_read_csv)

    fetch_stock_history(tmp_path, "005930", LOGGER)

    assert captured["usecols"] == ["date", "ticker", "open", "close", "volume"]


def test_fetch_stock_history_cache_refreshes_after_file_change(monkeypatch, tmp_path: Path):
    file_path = tmp_path / "daily_prices.csv"
    pd.DataFrame(
        [
            {"date": "2026-02-21", "ticker": "005930", "open": 10000, "close": 10100, "volume": 200000},
        ]
    ).to_csv(file_path, index=False)

    original_read_csv = pd.read_csv
    call_count = {"value": 0}

    def _counted_read_csv(*args, **kwargs):
        call_count["value"] += 1
        return original_read_csv(*args, **kwargs)

    monkeypatch.setattr(pd, "read_csv", _counted_read_csv)

    first = fetch_stock_history(tmp_path, "005930", LOGGER)
    time.sleep(0.002)
    pd.DataFrame(
        [
            {"date": "2026-02-21", "ticker": "005930", "open": 10000, "close": 11100, "volume": 200000},
        ]
    ).to_csv(file_path, index=False)

    second = fetch_stock_history(tmp_path, "005930", LOGGER)

    assert call_count["value"] == 2
    assert "종가 11,100" in second
    assert first != second


def test_fetch_stock_history_reuses_sqlite_cache_after_memory_clear(monkeypatch, tmp_path: Path):
    pd.DataFrame(
        [
            {"date": "2026-02-21", "ticker": "005930", "open": 10000, "close": 10100, "volume": 200000},
        ]
    ).to_csv(tmp_path / "daily_prices.csv", index=False)

    first = fetch_stock_history(tmp_path, "005930", LOGGER)
    assert "종가 10,100" in first

    clear_stock_context_cache()
    monkeypatch.setattr(
        pd,
        "read_csv",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("should use sqlite cache")),
    )

    second = fetch_stock_history(tmp_path, "005930", LOGGER)
    assert second == first

    db_path = tmp_path / "runtime_cache.db"
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM chatbot_stock_context_cache
            WHERE dataset = ? AND ticker = ?
            """,
            ("stock_history", "005930"),
        )
        row = cursor.fetchone()
    assert row and row[0] >= 1


def test_fetch_institutional_trend_and_signal_history_formats_text(tmp_path: Path):
    pd.DataFrame(
        [
            {"date": "2026-02-21", "ticker": "005930", "foreign_buy": 12345, "inst_buy": -2345},
        ]
    ).to_csv(tmp_path / "all_institutional_trend_data.csv", index=False)
    pd.DataFrame(
        [
            {"signal_date": "2026-02-21", "ticker": "005930", "score": 8},
        ]
    ).to_csv(tmp_path / "signals_log.csv", index=False)

    trend_text = fetch_institutional_trend(tmp_path, "5930")
    signal_text = fetch_signal_history(tmp_path, "5930")

    assert "외인 +12,345" in trend_text
    assert "기관 -2,345" in trend_text
    assert "2026-02-21: 8점 VCP 포착" in signal_text


def test_fetch_institutional_trend_handles_missing_columns(tmp_path: Path):
    pd.DataFrame(
        [
            {"date": "2026-02-21", "ticker": "005930"},
        ]
    ).to_csv(tmp_path / "all_institutional_trend_data.csv", index=False)

    text = fetch_institutional_trend(tmp_path, "5930")
    assert text == "데이터 조회 실패"


def test_fetch_signal_history_handles_missing_columns(tmp_path: Path):
    pd.DataFrame(
        [
            {"signal_date": "2026-02-21", "ticker": "005930"},
        ]
    ).to_csv(tmp_path / "signals_log.csv", index=False)

    text = fetch_signal_history(tmp_path, "5930")
    assert text == "조회 실패"
