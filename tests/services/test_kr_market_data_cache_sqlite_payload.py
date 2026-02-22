#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Data Cache SQLite payload helper 회귀 테스트
"""

from __future__ import annotations

import pandas as pd

import services.kr_market_data_cache_sqlite_payload as sqlite_payload_cache
from services.sqlite_utils import connect_sqlite


def _reset_sqlite_payload_state() -> None:
    sqlite_payload_cache.JSON_PAYLOAD_SQLITE_READY.clear()
    sqlite_payload_cache.CSV_PAYLOAD_SQLITE_READY.clear()


def test_json_payload_sqlite_roundtrip_and_delete(tmp_path):
    _reset_sqlite_payload_state()
    filepath = str(tmp_path / "kr_ai_analysis.json")
    signature = (123, 456)
    payload = {"signals": [{"stock_code": "005930"}]}

    sqlite_payload_cache.save_json_payload_to_sqlite(
        filepath=filepath,
        signature=signature,
        payload=payload,
        max_rows=8,
    )

    found, loaded = sqlite_payload_cache.load_json_payload_from_sqlite(
        filepath=filepath,
        signature=signature,
    )
    assert found is True
    assert loaded["signals"][0]["stock_code"] == "005930"

    sqlite_payload_cache.delete_json_payload_from_sqlite(filepath)
    found_after_delete, loaded_after_delete = sqlite_payload_cache.load_json_payload_from_sqlite(
        filepath=filepath,
        signature=signature,
    )
    assert found_after_delete is False
    assert loaded_after_delete == {}


def test_csv_payload_sqlite_roundtrip_with_usecols_none(tmp_path):
    _reset_sqlite_payload_state()
    filepath = str(tmp_path / "daily_prices.csv")
    signature = (321, 654)
    source_df = pd.DataFrame(
        [
            {"date": "2026-02-20", "ticker": "005930", "close": 100.0},
            {"date": "2026-02-21", "ticker": "005930", "close": 111.0},
        ]
    )

    sqlite_payload_cache.save_csv_payload_to_sqlite(
        filepath=filepath,
        signature=signature,
        usecols=None,
        payload=source_df,
        max_rows=8,
    )

    loaded_df = sqlite_payload_cache.load_csv_payload_from_sqlite(
        filepath=filepath,
        signature=signature,
        usecols=None,
    )
    assert isinstance(loaded_df, pd.DataFrame)
    assert len(loaded_df) == 2
    assert float(loaded_df.iloc[-1]["close"]) == 111.0

    sqlite_payload_cache.delete_csv_payload_from_sqlite(filepath)
    deleted_df = sqlite_payload_cache.load_csv_payload_from_sqlite(
        filepath=filepath,
        signature=signature,
        usecols=None,
    )
    assert deleted_df is None


def test_json_payload_sqlite_prunes_rows_with_limit(tmp_path):
    _reset_sqlite_payload_state()
    for index in range(1, 5):
        filepath = str(tmp_path / f"payload_{index}.json")
        sqlite_payload_cache.save_json_payload_to_sqlite(
            filepath=filepath,
            signature=(index, index * 10),
            payload={"id": index},
            max_rows=2,
        )

    db_path = tmp_path / "runtime_cache.db"
    with connect_sqlite(str(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM json_file_payload_cache")
        row_count = int(cursor.fetchone()[0])

    assert row_count == 2
