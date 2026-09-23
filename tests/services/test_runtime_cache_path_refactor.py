#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
runtime_cache.db 경로가 데이터 파일과 같은 cwd 기준 data/ 를 따르는지 확인하는 회귀 테스트 ([INFRA-078])
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import services.common_update_status_service as common_update_status_service
import services.file_row_count_cache as file_row_count_cache
import services.kr_market_backtest_summary_cache as kr_market_backtest_summary_cache
import services.kr_market_cumulative_cache as kr_market_cumulative_cache
import services.kr_market_data_cache_jongga as kr_market_data_cache_jongga


@pytest.mark.parametrize(
    ("module", "attr"),
    [
        (file_row_count_cache, "_ROW_COUNT_CACHE_DB_PATH"),
        (common_update_status_service, "_UPDATE_STATUS_CACHE_DB_PATH"),
        (kr_market_data_cache_jongga, "_JONGGA_PAYLOAD_SQLITE_DB_PATH"),
        (kr_market_cumulative_cache, "_CUMULATIVE_CACHE_DB_PATH"),
        (kr_market_backtest_summary_cache, "_BACKTEST_SUMMARY_CACHE_DB_PATH"),
    ],
)
def test_runtime_cache_db_path_follows_cwd_data_dir(module, attr):
    # 데이터 파일은 cwd 의 data/ 를 읽는다. 캐시만 저장소 절대 경로면 격리 실행이 원본에 쓴다.
    assert getattr(module, attr) == os.path.join("data", "runtime_cache.db")


def test_row_count_cache_writes_under_cwd_data_dir(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    file_row_count_cache._ROW_COUNT_SQLITE_READY.clear()
    file_row_count_cache.clear_file_row_count_cache()
    csv_path = tmp_path / "data" / "rows.csv"
    csv_path.write_text("a\n1\n", encoding="utf-8")
    logger = type("L", (), {"debug": lambda *_a, **_k: None})()
    try:
        count = file_row_count_cache.get_cached_file_row_count(
            path=str(csv_path),
            signature=file_row_count_cache.file_signature(str(csv_path)),
            logger=logger,
        )
    finally:
        file_row_count_cache._ROW_COUNT_SQLITE_READY.clear()
        file_row_count_cache.clear_file_row_count_cache()
    assert count == 1
    assert (tmp_path / "data" / "runtime_cache.db").is_file()
