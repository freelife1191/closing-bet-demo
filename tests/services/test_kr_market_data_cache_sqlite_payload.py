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


def test_serialize_usecols_signature_is_compact_json():
    signature = sqlite_payload_cache.serialize_usecols_signature(("date", "ticker", "close"))
    assert signature == '["date","ticker","close"]'


def test_json_payload_sqlite_stores_compact_payload_json(tmp_path):
    _reset_sqlite_payload_state()
    filepath = str(tmp_path / "compact_payload.json")
    signature = (100, 200)
    payload = {"a": [1, 2], "b": {"c": 3}}

    sqlite_payload_cache.save_json_payload_to_sqlite(
        filepath=filepath,
        signature=signature,
        payload=payload,
        max_rows=8,
    )

    db_path = tmp_path / "runtime_cache.db"
    with connect_sqlite(str(db_path)) as conn:
        row = conn.execute(
            """
            SELECT payload_json
            FROM json_file_payload_cache
            WHERE filepath = ?
            """,
            (filepath,),
        ).fetchone()

    assert row is not None
    assert row[0] == '{"a":[1,2],"b":{"c":3}}'


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


def test_json_payload_sqlite_creates_parent_dir_when_missing(monkeypatch, tmp_path):
    _reset_sqlite_payload_state()
    filepath = str(tmp_path / "kr_ai_analysis.json")
    db_path = tmp_path / "cache" / "nested" / "runtime_cache.db"

    monkeypatch.setattr(sqlite_payload_cache, "resolve_payload_sqlite_db_path", lambda _filepath: str(db_path))

    sqlite_payload_cache.save_json_payload_to_sqlite(
        filepath=filepath,
        signature=(101, 202),
        payload={"signals": [{"stock_code": "000001"}]},
        max_rows=8,
    )

    found, loaded = sqlite_payload_cache.load_json_payload_from_sqlite(
        filepath=filepath,
        signature=(101, 202),
    )
    assert db_path.exists()
    assert found is True
    assert loaded["signals"][0]["stock_code"] == "000001"


def test_csv_payload_sqlite_creates_parent_dir_when_missing(monkeypatch, tmp_path):
    _reset_sqlite_payload_state()
    filepath = str(tmp_path / "daily_prices.csv")
    db_path = tmp_path / "cache" / "nested_csv" / "runtime_cache.db"

    monkeypatch.setattr(sqlite_payload_cache, "resolve_payload_sqlite_db_path", lambda _filepath: str(db_path))

    source_df = pd.DataFrame([{"date": "2026-02-20", "ticker": "005930", "close": 100.0}])
    sqlite_payload_cache.save_csv_payload_to_sqlite(
        filepath=filepath,
        signature=(111, 222),
        usecols=("date", "ticker", "close"),
        payload=source_df,
        max_rows=8,
    )

    loaded_df = sqlite_payload_cache.load_csv_payload_from_sqlite(
        filepath=filepath,
        signature=(111, 222),
        usecols=("date", "ticker", "close"),
    )
    assert db_path.exists()
    assert isinstance(loaded_df, pd.DataFrame)
    assert len(loaded_df) == 1


def test_json_payload_sqlite_recovers_when_table_missing(tmp_path):
    _reset_sqlite_payload_state()
    filepath = str(tmp_path / "recover_json.json")
    first_signature = (1, 10)
    second_signature = (2, 20)

    sqlite_payload_cache.save_json_payload_to_sqlite(
        filepath=filepath,
        signature=first_signature,
        payload={"id": "first"},
        max_rows=8,
    )

    db_path = tmp_path / "runtime_cache.db"
    with connect_sqlite(str(db_path)) as conn:
        conn.execute("DROP TABLE json_file_payload_cache")
        conn.commit()

    sqlite_payload_cache.save_json_payload_to_sqlite(
        filepath=filepath,
        signature=second_signature,
        payload={"id": "second"},
        max_rows=8,
    )

    found, loaded = sqlite_payload_cache.load_json_payload_from_sqlite(
        filepath=filepath,
        signature=second_signature,
    )
    assert found is True
    assert loaded["id"] == "second"


def test_csv_payload_sqlite_recovers_when_table_missing(tmp_path):
    _reset_sqlite_payload_state()
    filepath = str(tmp_path / "recover_csv.csv")
    first_signature = (1, 10)
    second_signature = (2, 20)

    first_df = pd.DataFrame([{"date": "2026-02-20", "ticker": "005930", "close": 100.0}])
    second_df = pd.DataFrame([{"date": "2026-02-21", "ticker": "000660", "close": 200.0}])

    sqlite_payload_cache.save_csv_payload_to_sqlite(
        filepath=filepath,
        signature=first_signature,
        usecols=("date", "ticker", "close"),
        payload=first_df,
        max_rows=8,
    )

    db_path = tmp_path / "runtime_cache.db"
    with connect_sqlite(str(db_path)) as conn:
        conn.execute("DROP TABLE csv_file_payload_cache")
        conn.commit()

    sqlite_payload_cache.save_csv_payload_to_sqlite(
        filepath=filepath,
        signature=second_signature,
        usecols=("date", "ticker", "close"),
        payload=second_df,
        max_rows=8,
    )

    loaded_df = sqlite_payload_cache.load_csv_payload_from_sqlite(
        filepath=filepath,
        signature=second_signature,
        usecols=("date", "ticker", "close"),
    )
    assert isinstance(loaded_df, pd.DataFrame)
    assert len(loaded_df) == 1
    assert str(loaded_df.iloc[0]["ticker"]).zfill(6) == "000660"


def test_json_payload_sqlite_skips_delete_when_row_count_within_limit(tmp_path, monkeypatch):
    _reset_sqlite_payload_state()
    traced_sql: list[str] = []
    original_connect = sqlite_payload_cache.connect_sqlite

    def _traced_connect(*args, **kwargs):
        conn = original_connect(*args, **kwargs)
        conn.set_trace_callback(traced_sql.append)
        return conn

    monkeypatch.setattr(sqlite_payload_cache, "connect_sqlite", _traced_connect)

    filepath = str(tmp_path / "single_payload.json")
    sqlite_payload_cache.save_json_payload_to_sqlite(
        filepath=filepath,
        signature=(10, 20),
        payload={"id": "single"},
        max_rows=8,
    )

    assert not any("DELETE FROM json_file_payload_cache" in sql for sql in traced_sql)


def test_csv_payload_sqlite_skips_delete_when_row_count_within_limit(tmp_path, monkeypatch):
    _reset_sqlite_payload_state()
    traced_sql: list[str] = []
    original_connect = sqlite_payload_cache.connect_sqlite

    def _traced_connect(*args, **kwargs):
        conn = original_connect(*args, **kwargs)
        conn.set_trace_callback(traced_sql.append)
        return conn

    monkeypatch.setattr(sqlite_payload_cache, "connect_sqlite", _traced_connect)

    filepath = str(tmp_path / "single_payload.csv")
    payload = pd.DataFrame([{"date": "2026-02-22", "ticker": "005930", "close": 123.0}])
    sqlite_payload_cache.save_csv_payload_to_sqlite(
        filepath=filepath,
        signature=(10, 20),
        usecols=("date", "ticker", "close"),
        payload=payload,
        max_rows=8,
    )

    assert not any("DELETE FROM csv_file_payload_cache" in sql for sql in traced_sql)
