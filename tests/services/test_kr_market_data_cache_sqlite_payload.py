#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Data Cache SQLite payload helper 회귀 테스트
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
import time
from io import StringIO

import pandas as pd

import services.kr_market_data_cache_sqlite_payload as sqlite_payload_cache
from services.sqlite_utils import connect_sqlite


def _reset_sqlite_payload_state() -> None:
    with sqlite_payload_cache.JSON_PAYLOAD_SQLITE_READY_LOCK:
        sqlite_payload_cache.JSON_PAYLOAD_SQLITE_READY.clear()
        sqlite_payload_cache.JSON_PAYLOAD_SQLITE_IN_PROGRESS.clear()
    with sqlite_payload_cache.JSON_PAYLOAD_SQLITE_KNOWN_KEYS_LOCK:
        sqlite_payload_cache.JSON_PAYLOAD_SQLITE_KNOWN_KEYS.clear()
    with sqlite_payload_cache.JSON_PAYLOAD_SQLITE_SAVE_COUNTER_LOCK:
        sqlite_payload_cache.JSON_PAYLOAD_SQLITE_SAVE_COUNTER = 0
    with sqlite_payload_cache.CSV_PAYLOAD_SQLITE_READY_LOCK:
        sqlite_payload_cache.CSV_PAYLOAD_SQLITE_READY.clear()
        sqlite_payload_cache.CSV_PAYLOAD_SQLITE_IN_PROGRESS.clear()
    with sqlite_payload_cache.CSV_PAYLOAD_SQLITE_KNOWN_KEYS_LOCK:
        sqlite_payload_cache.CSV_PAYLOAD_SQLITE_KNOWN_KEYS.clear()
    with sqlite_payload_cache.CSV_PAYLOAD_SQLITE_SAVE_COUNTER_LOCK:
        sqlite_payload_cache.CSV_PAYLOAD_SQLITE_SAVE_COUNTER = 0


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


def test_csv_payload_sqlite_load_projects_existing_usecols_columns(tmp_path):
    _reset_sqlite_payload_state()
    filepath = str(tmp_path / "daily_prices_usecols_projection.csv")
    signature = (741, 852)
    payload = pd.DataFrame(
        [
            {"date": "2026-02-20", "ticker": "005930", "close": 100.0},
            {"date": "2026-02-21", "ticker": "000660", "close": 200.0},
        ]
    )

    sqlite_payload_cache.save_csv_payload_to_sqlite(
        filepath=filepath,
        signature=signature,
        usecols=("date", "ticker"),
        payload=payload,
        max_rows=8,
    )

    loaded_df = sqlite_payload_cache.load_csv_payload_from_sqlite(
        filepath=filepath,
        signature=signature,
        usecols=("date", "ticker"),
    )
    assert isinstance(loaded_df, pd.DataFrame)
    assert list(loaded_df.columns) == ["date", "ticker"]
    assert len(loaded_df) == 2


def test_csv_payload_sqlite_save_projects_usecols_before_persisting(tmp_path):
    _reset_sqlite_payload_state()
    filepath = str(tmp_path / "daily_prices_save_projection.csv")
    signature = (258, 369)
    payload = pd.DataFrame(
        [
            {"date": "2026-02-20", "ticker": "005930", "close": 100.0, "volume": 1000},
            {"date": "2026-02-21", "ticker": "000660", "close": 200.0, "volume": 2000},
        ]
    )

    usecols = ("date", "ticker")
    sqlite_payload_cache.save_csv_payload_to_sqlite(
        filepath=filepath,
        signature=signature,
        usecols=usecols,
        payload=payload,
        max_rows=8,
    )

    db_path = tmp_path / "runtime_cache.db"
    with sqlite3.connect(str(db_path)) as conn:
        row = conn.execute(
            """
            SELECT payload_json
            FROM csv_file_payload_cache
            WHERE filepath = ?
              AND usecols_signature = ?
            """,
            (
                filepath,
                sqlite_payload_cache.serialize_usecols_signature(usecols),
            ),
        ).fetchone()

    assert row is not None
    stored = pd.read_json(StringIO(row[0]), orient="split")
    assert list(stored.columns) == ["date", "ticker"]


def test_csv_payload_sqlite_load_returns_none_when_all_usecols_missing(tmp_path):
    _reset_sqlite_payload_state()
    filepath = str(tmp_path / "daily_prices_usecols_all_missing.csv")
    signature = (963, 147)
    payload = pd.DataFrame(
        [
            {"close": 100.0, "volume": 1000},
            {"close": 200.0, "volume": 2000},
        ]
    )

    sqlite_payload_cache.save_csv_payload_to_sqlite(
        filepath=filepath,
        signature=signature,
        usecols=("date", "ticker"),
        payload=payload,
        max_rows=8,
    )

    db_path = tmp_path / "runtime_cache.db"
    with sqlite3.connect(str(db_path)) as conn:
        row_count = int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM csv_file_payload_cache
                WHERE filepath = ?
                """,
                (filepath,),
            ).fetchone()[0]
        )
    assert row_count == 0

    loaded_df = sqlite_payload_cache.load_csv_payload_from_sqlite(
        filepath=filepath,
        signature=signature,
        usecols=("date", "ticker"),
    )
    assert loaded_df is None


def test_json_payload_sqlite_load_uses_read_only_connection(monkeypatch, tmp_path):
    _reset_sqlite_payload_state()
    filepath = str(tmp_path / "read_only_json_payload.json")
    signature = (333, 444)
    payload = {"signals": [{"stock_code": "005930"}]}

    sqlite_payload_cache.save_json_payload_to_sqlite(
        filepath=filepath,
        signature=signature,
        payload=payload,
        max_rows=8,
    )

    read_only_flags: list[bool] = []
    original_connect = sqlite_payload_cache.connect_sqlite

    def _traced_connect(*args, **kwargs):
        if "read_only" in kwargs:
            read_only_flags.append(bool(kwargs["read_only"]))
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(sqlite_payload_cache, "connect_sqlite", _traced_connect)

    found, loaded = sqlite_payload_cache.load_json_payload_from_sqlite(
        filepath=filepath,
        signature=signature,
    )
    assert found is True
    assert loaded["signals"][0]["stock_code"] == "005930"
    assert True in read_only_flags


def test_json_payload_sqlite_load_reads_legacy_filepath_key(monkeypatch, tmp_path):
    _reset_sqlite_payload_state()
    monkeypatch.chdir(tmp_path)

    relative_filepath = "legacy_json_payload.json"
    absolute_filepath = str((tmp_path / relative_filepath).resolve())
    signature = (777, 888)
    payload = {"signals": [{"stock_code": "005930"}]}

    sqlite_payload_cache.save_json_payload_to_sqlite(
        filepath=relative_filepath,
        signature=signature,
        payload=payload,
        max_rows=8,
    )

    with sqlite3.connect(tmp_path / "runtime_cache.db") as conn:
        conn.execute(
            """
            UPDATE json_file_payload_cache
            SET filepath = ?
            WHERE filepath = ?
            """,
            (
                relative_filepath,
                sqlite_payload_cache._normalize_payload_filepath(absolute_filepath),
            ),
        )
        conn.commit()

    found, loaded = sqlite_payload_cache.load_json_payload_from_sqlite(
        filepath=absolute_filepath,
        signature=signature,
    )
    assert found is True
    assert loaded["signals"][0]["stock_code"] == "005930"


def test_json_payload_sqlite_legacy_lookup_runs_single_select_query(monkeypatch, tmp_path):
    _reset_sqlite_payload_state()
    monkeypatch.chdir(tmp_path)

    relative_filepath = "legacy_json_single_select.json"
    absolute_filepath = str((tmp_path / relative_filepath).resolve())
    signature = (901, 902)
    payload = {"signals": [{"stock_code": "005930"}]}

    sqlite_payload_cache.save_json_payload_to_sqlite(
        filepath=relative_filepath,
        signature=signature,
        payload=payload,
        max_rows=8,
    )

    with sqlite3.connect(tmp_path / "runtime_cache.db") as conn:
        conn.execute(
            """
            UPDATE json_file_payload_cache
            SET filepath = ?
            WHERE filepath = ?
            """,
            (
                relative_filepath,
                sqlite_payload_cache._normalize_payload_filepath(absolute_filepath),
            ),
        )
        conn.commit()

    traced_sql: list[str] = []
    original_connect = sqlite_payload_cache.connect_sqlite

    def _traced_connect(*args, **kwargs):
        conn = original_connect(*args, **kwargs)
        conn.set_trace_callback(traced_sql.append)
        return conn

    monkeypatch.setattr(sqlite_payload_cache, "connect_sqlite", _traced_connect)

    found, loaded = sqlite_payload_cache.load_json_payload_from_sqlite(
        filepath=absolute_filepath,
        signature=signature,
    )

    select_count = sum(
        1
        for sql in traced_sql
        if "select payload_json" in sql.lower()
        and "from json_file_payload_cache" in sql.lower()
    )
    assert found is True
    assert loaded["signals"][0]["stock_code"] == "005930"
    assert select_count == 1


def test_csv_payload_sqlite_load_uses_read_only_connection(monkeypatch, tmp_path):
    _reset_sqlite_payload_state()
    filepath = str(tmp_path / "read_only_csv_payload.csv")
    signature = (555, 666)
    payload = pd.DataFrame([{"date": "2026-02-20", "ticker": "005930", "close": 101.0}])

    sqlite_payload_cache.save_csv_payload_to_sqlite(
        filepath=filepath,
        signature=signature,
        usecols=("date", "ticker", "close"),
        payload=payload,
        max_rows=8,
    )

    read_only_flags: list[bool] = []
    original_connect = sqlite_payload_cache.connect_sqlite

    def _traced_connect(*args, **kwargs):
        if "read_only" in kwargs:
            read_only_flags.append(bool(kwargs["read_only"]))
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(sqlite_payload_cache, "connect_sqlite", _traced_connect)

    loaded_df = sqlite_payload_cache.load_csv_payload_from_sqlite(
        filepath=filepath,
        signature=signature,
        usecols=("date", "ticker", "close"),
    )
    assert isinstance(loaded_df, pd.DataFrame)
    assert len(loaded_df) == 1
    assert True in read_only_flags


def test_csv_payload_sqlite_load_reads_legacy_filepath_key(monkeypatch, tmp_path):
    _reset_sqlite_payload_state()
    monkeypatch.chdir(tmp_path)

    relative_filepath = "legacy_csv_payload.csv"
    absolute_filepath = str((tmp_path / relative_filepath).resolve())
    signature = (889, 990)
    payload = pd.DataFrame([{"date": "2026-02-20", "ticker": "005930", "close": 101.0}])
    usecols = ("date", "ticker", "close")

    sqlite_payload_cache.save_csv_payload_to_sqlite(
        filepath=relative_filepath,
        signature=signature,
        usecols=usecols,
        payload=payload,
        max_rows=8,
    )

    with sqlite3.connect(tmp_path / "runtime_cache.db") as conn:
        conn.execute(
            """
            UPDATE csv_file_payload_cache
            SET filepath = ?
            WHERE filepath = ?
            """,
            (
                relative_filepath,
                sqlite_payload_cache._normalize_payload_filepath(absolute_filepath),
            ),
        )
        conn.commit()

    loaded_df = sqlite_payload_cache.load_csv_payload_from_sqlite(
        filepath=absolute_filepath,
        signature=signature,
        usecols=usecols,
    )
    assert isinstance(loaded_df, pd.DataFrame)
    assert len(loaded_df) == 1
    assert str(loaded_df.iloc[0]["ticker"]).zfill(6) == "005930"


def test_csv_payload_sqlite_legacy_lookup_runs_single_select_query(monkeypatch, tmp_path):
    _reset_sqlite_payload_state()
    monkeypatch.chdir(tmp_path)

    relative_filepath = "legacy_csv_single_select.csv"
    absolute_filepath = str((tmp_path / relative_filepath).resolve())
    signature = (903, 904)
    usecols = ("date", "ticker", "close")
    payload = pd.DataFrame([{"date": "2026-02-20", "ticker": "005930", "close": 101.0}])

    sqlite_payload_cache.save_csv_payload_to_sqlite(
        filepath=relative_filepath,
        signature=signature,
        usecols=usecols,
        payload=payload,
        max_rows=8,
    )

    with sqlite3.connect(tmp_path / "runtime_cache.db") as conn:
        conn.execute(
            """
            UPDATE csv_file_payload_cache
            SET filepath = ?
            WHERE filepath = ?
            """,
            (
                relative_filepath,
                sqlite_payload_cache._normalize_payload_filepath(absolute_filepath),
            ),
        )
        conn.commit()

    traced_sql: list[str] = []
    original_connect = sqlite_payload_cache.connect_sqlite

    def _traced_connect(*args, **kwargs):
        conn = original_connect(*args, **kwargs)
        conn.set_trace_callback(traced_sql.append)
        return conn

    monkeypatch.setattr(sqlite_payload_cache, "connect_sqlite", _traced_connect)

    loaded_df = sqlite_payload_cache.load_csv_payload_from_sqlite(
        filepath=absolute_filepath,
        signature=signature,
        usecols=usecols,
    )

    select_count = sum(
        1
        for sql in traced_sql
        if "select payload_json" in sql.lower()
        and "from csv_file_payload_cache" in sql.lower()
    )
    assert isinstance(loaded_df, pd.DataFrame)
    assert len(loaded_df) == 1
    assert select_count == 1


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


def test_delete_json_payload_from_sqlite_deletes_legacy_filepath_key(monkeypatch, tmp_path):
    _reset_sqlite_payload_state()
    monkeypatch.chdir(tmp_path)

    relative_filepath = "legacy_delete_payload.json"
    absolute_filepath = str((tmp_path / relative_filepath).resolve())

    sqlite_payload_cache.save_json_payload_to_sqlite(
        filepath=relative_filepath,
        signature=(10, 20),
        payload={"id": "legacy"},
        max_rows=8,
    )

    with sqlite3.connect(tmp_path / "runtime_cache.db") as conn:
        conn.execute(
            """
            UPDATE json_file_payload_cache
            SET filepath = ?
            WHERE filepath = ?
            """,
            (
                relative_filepath,
                sqlite_payload_cache._normalize_payload_filepath(absolute_filepath),
            ),
        )
        conn.commit()

    sqlite_payload_cache.delete_json_payload_from_sqlite(absolute_filepath)

    with sqlite3.connect(tmp_path / "runtime_cache.db") as conn:
        row_count = int(
            conn.execute(
                "SELECT COUNT(*) FROM json_file_payload_cache WHERE filepath = ?",
                (relative_filepath,),
            ).fetchone()[0]
        )
    assert row_count == 0


def test_delete_json_payload_from_sqlite_legacy_lookup_runs_single_delete_query(monkeypatch, tmp_path):
    _reset_sqlite_payload_state()
    monkeypatch.chdir(tmp_path)

    relative_filepath = "legacy_delete_single_query.json"
    absolute_filepath = str((tmp_path / relative_filepath).resolve())

    sqlite_payload_cache.save_json_payload_to_sqlite(
        filepath=relative_filepath,
        signature=(11, 21),
        payload={"id": "legacy"},
        max_rows=8,
    )

    with sqlite3.connect(tmp_path / "runtime_cache.db") as conn:
        conn.execute(
            """
            UPDATE json_file_payload_cache
            SET filepath = ?
            WHERE filepath = ?
            """,
            (
                relative_filepath,
                sqlite_payload_cache._normalize_payload_filepath(absolute_filepath),
            ),
        )
        conn.commit()

    traced_sql: list[str] = []
    original_connect = sqlite_payload_cache.connect_sqlite

    def _traced_connect(*args, **kwargs):
        conn = original_connect(*args, **kwargs)
        conn.set_trace_callback(traced_sql.append)
        return conn

    monkeypatch.setattr(sqlite_payload_cache, "connect_sqlite", _traced_connect)

    sqlite_payload_cache.delete_json_payload_from_sqlite(absolute_filepath)

    delete_count = sum(
        1
        for sql in traced_sql
        if "delete from json_file_payload_cache" in sql.lower()
    )
    assert delete_count == 1


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


def test_delete_csv_payload_from_sqlite_legacy_lookup_runs_single_delete_query(monkeypatch, tmp_path):
    _reset_sqlite_payload_state()
    monkeypatch.chdir(tmp_path)

    relative_filepath = "legacy_delete_single_query.csv"
    absolute_filepath = str((tmp_path / relative_filepath).resolve())
    payload = pd.DataFrame([{"date": "2026-02-20", "ticker": "005930", "close": 101.0}])

    sqlite_payload_cache.save_csv_payload_to_sqlite(
        filepath=relative_filepath,
        signature=(12, 22),
        usecols=("date", "ticker", "close"),
        payload=payload,
        max_rows=8,
    )

    with sqlite3.connect(tmp_path / "runtime_cache.db") as conn:
        conn.execute(
            """
            UPDATE csv_file_payload_cache
            SET filepath = ?
            WHERE filepath = ?
            """,
            (
                relative_filepath,
                sqlite_payload_cache._normalize_payload_filepath(absolute_filepath),
            ),
        )
        conn.commit()

    traced_sql: list[str] = []
    original_connect = sqlite_payload_cache.connect_sqlite

    def _traced_connect(*args, **kwargs):
        conn = original_connect(*args, **kwargs)
        conn.set_trace_callback(traced_sql.append)
        return conn

    monkeypatch.setattr(sqlite_payload_cache, "connect_sqlite", _traced_connect)

    sqlite_payload_cache.delete_csv_payload_from_sqlite(absolute_filepath)

    delete_count = sum(
        1
        for sql in traced_sql
        if "delete from csv_file_payload_cache" in sql.lower()
    )
    assert delete_count == 1


def test_json_payload_sqlite_repeated_snapshot_key_prunes_once(tmp_path, monkeypatch):
    _reset_sqlite_payload_state()
    monkeypatch.setattr(sqlite_payload_cache, "JSON_PAYLOAD_SQLITE_PRUNE_FORCE_INTERVAL", 10_000)
    prune_calls = {"count": 0}
    original_prune = sqlite_payload_cache.prune_rows_by_updated_at_if_needed

    def _counted_prune(*args, **kwargs):
        prune_calls["count"] += 1
        return original_prune(*args, **kwargs)

    monkeypatch.setattr(sqlite_payload_cache, "prune_rows_by_updated_at_if_needed", _counted_prune)

    filepath = str(tmp_path / "same_snapshot.json")
    sqlite_payload_cache.save_json_payload_to_sqlite(
        filepath=filepath,
        signature=(1, 10),
        payload={"id": 1},
        max_rows=8,
    )
    sqlite_payload_cache.save_json_payload_to_sqlite(
        filepath=filepath,
        signature=(2, 20),
        payload={"id": 2},
        max_rows=8,
    )

    assert prune_calls["count"] == 1


def test_json_payload_sqlite_forces_prune_on_configured_interval(tmp_path, monkeypatch):
    _reset_sqlite_payload_state()
    monkeypatch.setattr(sqlite_payload_cache, "JSON_PAYLOAD_SQLITE_PRUNE_FORCE_INTERVAL", 2)
    prune_calls = {"count": 0}
    original_prune = sqlite_payload_cache.prune_rows_by_updated_at_if_needed

    def _counted_prune(*args, **kwargs):
        prune_calls["count"] += 1
        return original_prune(*args, **kwargs)

    monkeypatch.setattr(sqlite_payload_cache, "prune_rows_by_updated_at_if_needed", _counted_prune)

    filepath = str(tmp_path / "interval_snapshot.json")
    sqlite_payload_cache.save_json_payload_to_sqlite(
        filepath=filepath,
        signature=(1, 10),
        payload={"id": 1},
        max_rows=8,
    )
    sqlite_payload_cache.save_json_payload_to_sqlite(
        filepath=filepath,
        signature=(2, 20),
        payload={"id": 2},
        max_rows=8,
    )

    assert prune_calls["count"] == 2


def test_csv_payload_sqlite_repeated_snapshot_key_prunes_once(tmp_path, monkeypatch):
    _reset_sqlite_payload_state()
    monkeypatch.setattr(sqlite_payload_cache, "CSV_PAYLOAD_SQLITE_PRUNE_FORCE_INTERVAL", 10_000)
    prune_calls = {"count": 0}
    original_prune = sqlite_payload_cache.prune_rows_by_updated_at_if_needed

    def _counted_prune(*args, **kwargs):
        prune_calls["count"] += 1
        return original_prune(*args, **kwargs)

    monkeypatch.setattr(sqlite_payload_cache, "prune_rows_by_updated_at_if_needed", _counted_prune)

    filepath = str(tmp_path / "same_snapshot.csv")
    payload = pd.DataFrame([{"date": "2026-02-22", "ticker": "005930", "close": 123.0}])
    sqlite_payload_cache.save_csv_payload_to_sqlite(
        filepath=filepath,
        signature=(1, 10),
        usecols=("date", "ticker", "close"),
        payload=payload,
        max_rows=8,
    )
    sqlite_payload_cache.save_csv_payload_to_sqlite(
        filepath=filepath,
        signature=(2, 20),
        usecols=("date", "ticker", "close"),
        payload=payload,
        max_rows=8,
    )

    assert prune_calls["count"] == 1


def test_csv_payload_sqlite_forces_prune_on_configured_interval(tmp_path, monkeypatch):
    _reset_sqlite_payload_state()
    monkeypatch.setattr(sqlite_payload_cache, "CSV_PAYLOAD_SQLITE_PRUNE_FORCE_INTERVAL", 2)
    prune_calls = {"count": 0}
    original_prune = sqlite_payload_cache.prune_rows_by_updated_at_if_needed

    def _counted_prune(*args, **kwargs):
        prune_calls["count"] += 1
        return original_prune(*args, **kwargs)

    monkeypatch.setattr(sqlite_payload_cache, "prune_rows_by_updated_at_if_needed", _counted_prune)

    filepath = str(tmp_path / "interval_snapshot.csv")
    payload = pd.DataFrame([{"date": "2026-02-22", "ticker": "005930", "close": 123.0}])
    sqlite_payload_cache.save_csv_payload_to_sqlite(
        filepath=filepath,
        signature=(1, 10),
        usecols=("date", "ticker", "close"),
        payload=payload,
        max_rows=8,
    )
    sqlite_payload_cache.save_csv_payload_to_sqlite(
        filepath=filepath,
        signature=(2, 20),
        usecols=("date", "ticker", "close"),
        payload=payload,
        max_rows=8,
    )

    assert prune_calls["count"] == 2


def test_json_payload_sqlite_ready_cache_uses_normalized_db_key(monkeypatch, tmp_path):
    _reset_sqlite_payload_state()
    db_path = tmp_path / "runtime_cache.db"
    logger = logging.getLogger("test-json-payload-normalized-key")
    connect_calls = {"count": 0}
    original_connect = sqlite_payload_cache.connect_sqlite

    def _counted_connect(*args, **kwargs):
        connect_calls["count"] += 1
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(sqlite_payload_cache, "connect_sqlite", _counted_connect)

    assert sqlite_payload_cache._ensure_json_payload_sqlite_cache(str(db_path), logger) is True

    monkeypatch.chdir(tmp_path)
    relative_db_path = os.path.relpath(str(db_path), str(tmp_path))
    assert sqlite_payload_cache._ensure_json_payload_sqlite_cache(relative_db_path, logger) is True

    assert connect_calls["count"] == 1


def test_json_payload_sqlite_cache_deduplicates_concurrent_initialization(monkeypatch, tmp_path):
    _reset_sqlite_payload_state()
    db_path = str(tmp_path / "runtime_cache.db")
    logger = logging.getLogger("test-json-payload-concurrent-init")
    connect_calls = {"count": 0}
    connect_calls_lock = threading.Lock()
    first_connect_entered = threading.Event()
    original_connect = sqlite_payload_cache.connect_sqlite

    def _slow_counted_connect(*args, **kwargs):
        with connect_calls_lock:
            connect_calls["count"] += 1
            call_index = connect_calls["count"]
        if call_index == 1:
            first_connect_entered.set()
            time.sleep(0.05)
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(sqlite_payload_cache, "connect_sqlite", _slow_counted_connect)

    first_result: list[bool] = []
    second_result: list[bool] = []

    thread_first = threading.Thread(
        target=lambda: first_result.append(
            sqlite_payload_cache._ensure_json_payload_sqlite_cache(db_path, logger)
        )
    )
    thread_first.start()
    assert first_connect_entered.wait(timeout=1.0)

    thread_second = threading.Thread(
        target=lambda: second_result.append(
            sqlite_payload_cache._ensure_json_payload_sqlite_cache(db_path, logger)
        )
    )
    thread_second.start()

    thread_first.join(timeout=2.0)
    thread_second.join(timeout=2.0)

    assert first_result == [True]
    assert second_result == [True]
    assert connect_calls["count"] == 1


def test_json_payload_sqlite_waiter_retries_after_initializer_failure(monkeypatch, tmp_path):
    _reset_sqlite_payload_state()
    db_path = str(tmp_path / "runtime_cache.db")
    logger = logging.getLogger("test-json-payload-waiter-retry")

    monkeypatch.setattr(sqlite_payload_cache, "sqlite_db_path_exists", lambda _path: True)

    entered_event = threading.Event()
    release_event = threading.Event()
    run_calls = {"count": 0}

    def _fail_then_succeed(_operation, *, max_retries, retry_delay_seconds):
        run_calls["count"] += 1
        if run_calls["count"] == 1:
            entered_event.set()
            assert release_event.wait(timeout=2.0)
            raise sqlite3.OperationalError("forced init failure")
        return None

    monkeypatch.setattr(sqlite_payload_cache, "run_sqlite_with_retry", _fail_then_succeed)

    results: dict[str, bool] = {}

    def _worker(name: str) -> None:
        results[name] = bool(sqlite_payload_cache._ensure_json_payload_sqlite_cache(db_path, logger))

    first_thread = threading.Thread(target=_worker, args=("first",))
    second_thread = threading.Thread(target=_worker, args=("second",))

    first_thread.start()
    assert entered_event.wait(timeout=2.0)
    second_thread.start()
    time.sleep(0.05)
    assert run_calls["count"] == 1

    release_event.set()
    first_thread.join(timeout=2.0)
    second_thread.join(timeout=2.0)

    assert first_thread.is_alive() is False
    assert second_thread.is_alive() is False
    assert run_calls["count"] == 2
    assert results.get("first") is False
    assert results.get("second") is True


def test_json_payload_sqlite_ready_cache_is_bounded(monkeypatch, tmp_path):
    _reset_sqlite_payload_state()
    monkeypatch.setattr(sqlite_payload_cache, "JSON_PAYLOAD_SQLITE_READY_MAX_ENTRIES", 1)
    monkeypatch.setattr(sqlite_payload_cache, "sqlite_db_path_exists", lambda _path: True)
    monkeypatch.setattr(
        sqlite_payload_cache,
        "run_sqlite_with_retry",
        lambda _operation, *, max_retries, retry_delay_seconds: None,
    )

    first_db_path = str(tmp_path / "first.db")
    second_db_path = str(tmp_path / "second.db")
    logger = logging.getLogger("json-ready-bound-test")

    assert sqlite_payload_cache._ensure_json_payload_sqlite_cache(first_db_path, logger) is True
    assert sqlite_payload_cache._ensure_json_payload_sqlite_cache(second_db_path, logger) is True

    with sqlite_payload_cache.JSON_PAYLOAD_SQLITE_READY_CONDITION:
        assert len(sqlite_payload_cache.JSON_PAYLOAD_SQLITE_READY) == 1
        assert sqlite_payload_cache.normalize_sqlite_db_key(second_db_path) in sqlite_payload_cache.JSON_PAYLOAD_SQLITE_READY


def test_csv_payload_sqlite_cache_deduplicates_concurrent_initialization(monkeypatch, tmp_path):
    _reset_sqlite_payload_state()
    db_path = str(tmp_path / "runtime_cache.db")
    logger = logging.getLogger("test-csv-payload-concurrent-init")
    connect_calls = {"count": 0}
    connect_calls_lock = threading.Lock()
    first_connect_entered = threading.Event()
    original_connect = sqlite_payload_cache.connect_sqlite

    def _slow_counted_connect(*args, **kwargs):
        with connect_calls_lock:
            connect_calls["count"] += 1
            call_index = connect_calls["count"]
        if call_index == 1:
            first_connect_entered.set()
            time.sleep(0.05)
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(sqlite_payload_cache, "connect_sqlite", _slow_counted_connect)

    first_result: list[bool] = []
    second_result: list[bool] = []

    thread_first = threading.Thread(
        target=lambda: first_result.append(
            sqlite_payload_cache._ensure_csv_payload_sqlite_cache(db_path, logger)
        )
    )
    thread_first.start()
    assert first_connect_entered.wait(timeout=1.0)

    thread_second = threading.Thread(
        target=lambda: second_result.append(
            sqlite_payload_cache._ensure_csv_payload_sqlite_cache(db_path, logger)
        )
    )
    thread_second.start()

    thread_first.join(timeout=2.0)
    thread_second.join(timeout=2.0)

    assert first_result == [True]
    assert second_result == [True]
    assert connect_calls["count"] == 1


def test_csv_payload_sqlite_waiter_retries_after_initializer_failure(monkeypatch, tmp_path):
    _reset_sqlite_payload_state()
    db_path = str(tmp_path / "runtime_cache.db")
    logger = logging.getLogger("test-csv-payload-waiter-retry")

    monkeypatch.setattr(sqlite_payload_cache, "sqlite_db_path_exists", lambda _path: True)

    entered_event = threading.Event()
    release_event = threading.Event()
    run_calls = {"count": 0}

    def _fail_then_succeed(_operation, *, max_retries, retry_delay_seconds):
        run_calls["count"] += 1
        if run_calls["count"] == 1:
            entered_event.set()
            assert release_event.wait(timeout=2.0)
            raise sqlite3.OperationalError("forced init failure")
        return None

    monkeypatch.setattr(sqlite_payload_cache, "run_sqlite_with_retry", _fail_then_succeed)

    results: dict[str, bool] = {}

    def _worker(name: str) -> None:
        results[name] = bool(sqlite_payload_cache._ensure_csv_payload_sqlite_cache(db_path, logger))

    first_thread = threading.Thread(target=_worker, args=("first",))
    second_thread = threading.Thread(target=_worker, args=("second",))

    first_thread.start()
    assert entered_event.wait(timeout=2.0)
    second_thread.start()
    time.sleep(0.05)
    assert run_calls["count"] == 1

    release_event.set()
    first_thread.join(timeout=2.0)
    second_thread.join(timeout=2.0)

    assert first_thread.is_alive() is False
    assert second_thread.is_alive() is False
    assert run_calls["count"] == 2
    assert results.get("first") is False
    assert results.get("second") is True


def test_csv_payload_sqlite_ready_cache_is_bounded(monkeypatch, tmp_path):
    _reset_sqlite_payload_state()
    monkeypatch.setattr(sqlite_payload_cache, "CSV_PAYLOAD_SQLITE_READY_MAX_ENTRIES", 1)
    monkeypatch.setattr(sqlite_payload_cache, "sqlite_db_path_exists", lambda _path: True)
    monkeypatch.setattr(
        sqlite_payload_cache,
        "run_sqlite_with_retry",
        lambda _operation, *, max_retries, retry_delay_seconds: None,
    )

    first_db_path = str(tmp_path / "first.db")
    second_db_path = str(tmp_path / "second.db")
    logger = logging.getLogger("csv-ready-bound-test")

    assert sqlite_payload_cache._ensure_csv_payload_sqlite_cache(first_db_path, logger) is True
    assert sqlite_payload_cache._ensure_csv_payload_sqlite_cache(second_db_path, logger) is True

    with sqlite_payload_cache.CSV_PAYLOAD_SQLITE_READY_CONDITION:
        assert len(sqlite_payload_cache.CSV_PAYLOAD_SQLITE_READY) == 1
        assert sqlite_payload_cache.normalize_sqlite_db_key(second_db_path) in sqlite_payload_cache.CSV_PAYLOAD_SQLITE_READY
