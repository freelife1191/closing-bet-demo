#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Cumulative Cache 단위 테스트
"""

from __future__ import annotations

import logging

from services import kr_market_cumulative_cache as cumulative_cache
from services.sqlite_utils import connect_sqlite


def _reset_cache_state() -> None:
    cumulative_cache.clear_cumulative_cache()
    cumulative_cache._CUMULATIVE_SQLITE_READY.clear()


def test_save_cached_cumulative_payload_prunes_sqlite_rows(tmp_path, monkeypatch):
    _reset_cache_state()
    monkeypatch.setattr(
        cumulative_cache,
        "_CUMULATIVE_CACHE_DB_PATH",
        str(tmp_path / "runtime_cache.db"),
    )
    monkeypatch.setattr(cumulative_cache, "_CUMULATIVE_SQLITE_MAX_ROWS", 2)

    logger = logging.getLogger("test-cumulative-sqlite-prune")
    for idx in range(5):
        cumulative_cache.save_cached_cumulative_payload(
            signature=(("seed", idx),),
            payload={"kpi": {"count": idx}, "trades": [{"id": idx}]},
            logger=logger,
        )

    with connect_sqlite(str(tmp_path / "runtime_cache.db")) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM cumulative_performance_cache")
        row_count = int(cursor.fetchone()[0])

    assert row_count == 2


def test_get_cached_cumulative_payload_uses_sqlite_after_memory_clear(tmp_path, monkeypatch):
    _reset_cache_state()
    monkeypatch.setattr(
        cumulative_cache,
        "_CUMULATIVE_CACHE_DB_PATH",
        str(tmp_path / "runtime_cache.db"),
    )
    cumulative_cache._CUMULATIVE_SQLITE_READY.clear()

    signature = (("seed", 1),)
    expected = {"kpi": {"count": 1}, "trades": [{"id": "a"}]}
    logger = logging.getLogger("test-cumulative-sqlite-reuse")

    cumulative_cache.save_cached_cumulative_payload(
        signature=signature,
        payload=expected,
        logger=logger,
    )
    cumulative_cache.clear_cumulative_cache()

    loaded = cumulative_cache.get_cached_cumulative_payload(
        signature=signature,
        logger=logger,
    )
    assert loaded == expected
