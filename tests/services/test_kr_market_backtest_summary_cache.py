#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Backtest Summary Cache 단위 테스트
"""

from __future__ import annotations

import logging

from services import kr_market_backtest_summary_cache as summary_cache
from services.sqlite_utils import connect_sqlite


def _reset_cache_state() -> None:
    summary_cache.clear_backtest_summary_cache()
    summary_cache._BACKTEST_SUMMARY_SQLITE_READY.clear()


def test_save_cached_backtest_summary_prunes_sqlite_rows(tmp_path, monkeypatch):
    _reset_cache_state()
    monkeypatch.setattr(
        summary_cache,
        "_BACKTEST_SUMMARY_CACHE_DB_PATH",
        str(tmp_path / "runtime_cache.db"),
    )
    monkeypatch.setattr(summary_cache, "_BACKTEST_SUMMARY_SQLITE_MAX_ROWS", 2)

    logger = logging.getLogger("test-backtest-sqlite-prune")

    for idx in range(5):
        summary_cache.save_cached_backtest_summary(
            signature=(("seed", idx),),
            payload={"vcp": {"count": idx}, "closing_bet": {"count": idx}},
            logger=logger,
        )

    with connect_sqlite(str(tmp_path / "runtime_cache.db")) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM backtest_summary_cache")
        row_count = int(cursor.fetchone()[0])

    assert row_count == 2


def test_save_cached_backtest_summary_bounds_memory_entries(monkeypatch):
    _reset_cache_state()
    monkeypatch.setattr(summary_cache, "_BACKTEST_SUMMARY_MEMORY_MAX_ENTRIES", 2)

    logger = logging.getLogger("test-backtest-memory-bound")

    summary_cache.save_cached_backtest_summary(
        signature=(("seed", 1),),
        payload={"id": 1},
        logger=logger,
    )
    summary_cache.save_cached_backtest_summary(
        signature=(("seed", 2),),
        payload={"id": 2},
        logger=logger,
    )
    summary_cache.save_cached_backtest_summary(
        signature=(("seed", 3),),
        payload={"id": 3},
        logger=logger,
    )

    assert len(summary_cache._BACKTEST_SUMMARY_CACHE) <= 2
    assert (("seed", 3),) in summary_cache._BACKTEST_SUMMARY_CACHE
