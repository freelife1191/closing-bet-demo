#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market VCP Payload Service SQLite 캐시 회귀 테스트
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
import time

import pandas as pd

import services.kr_market_vcp_payload_service as vcp_payload_service
import services.kr_market_vcp_signals_cache as vcp_signals_cache
from services.sqlite_utils import connect_sqlite


def _write_signals_csv(tmp_path, signal_date: str) -> None:
    pd.DataFrame(
        [
            {
                "ticker": "005930",
                "name": "삼성전자",
                "signal_date": signal_date,
                "market": "KOSPI",
                "status": "NEW",
                "score": 85,
                "contraction_ratio": 0.42,
                "entry_price": 100.0,
                "target_price": 120.0,
                "stop_price": 95.0,
                "foreign_5d": 1000,
                "inst_5d": 2000,
                "vcp_score": 85,
                "current_price": 101.0,
                "return_pct": 1.0,
                "ai_action": "BUY",
                "ai_reason": "ok",
                "ai_confidence": 0.9,
            }
        ]
    ).to_csv(tmp_path / "signals_log.csv", index=False)


def _build_payload(
    tmp_path,
    *,
    req_date: str | None,
    count_total_scanned_stocks_fn=lambda _data_dir: 1,
    load_json_file_fn=None,
):
    logger = logging.getLogger("vcp-payload-cache-test")
    if load_json_file_fn is None:
        load_json_file_fn = lambda _name, **_kwargs: {}
    return vcp_payload_service.build_vcp_signals_payload(
        req_date=req_date,
        load_csv_file=lambda name: pd.read_csv(tmp_path / name),
        load_json_file=load_json_file_fn,
        filter_signals_dataframe_by_date=lambda df, req, _today: (
            df if not req else df[df["signal_date"] == req],
            req or "",
        ),
        build_vcp_signals_from_dataframe=lambda df: [
            {
                "ticker": str(row["ticker"]).zfill(6),
                "signal_date": row["signal_date"],
                "score": int(row["score"]),
            }
            for _, row in df.iterrows()
        ],
        load_latest_vcp_price_map=lambda: {},
        apply_latest_prices_to_jongga_signals=lambda _signals, _price_map: 0,
        sort_and_limit_vcp_signals=lambda signals, limit=100: list(signals)[:limit],
        build_ai_data_map=lambda _payload: {},
        merge_legacy_ai_fields_into_map=lambda _ai_map, _legacy: None,
        merge_ai_data_into_vcp_signals=lambda _signals, _ai_map: 0,
        count_total_scanned_stocks=count_total_scanned_stocks_fn,
        logger=logger,
        data_dir=str(tmp_path),
    )


def _reset_vcp_signals_cache_state() -> None:
    with vcp_signals_cache._VCP_SIGNALS_CACHE_LOCK:
        vcp_signals_cache._VCP_SIGNALS_MEMORY_CACHE.clear()
    with vcp_signals_cache._VCP_SIGNALS_SQLITE_READY_CONDITION:
        vcp_signals_cache._VCP_SIGNALS_SQLITE_READY.clear()
        vcp_signals_cache._VCP_SIGNALS_SQLITE_INIT_IN_PROGRESS.clear()
    with vcp_signals_cache._VCP_SIGNALS_SQLITE_KNOWN_HASHES_LOCK:
        vcp_signals_cache._VCP_SIGNALS_SQLITE_KNOWN_HASHES.clear()
    with vcp_signals_cache._VCP_SIGNALS_SQLITE_SAVE_COUNTER_LOCK:
        vcp_signals_cache._VCP_SIGNALS_SQLITE_SAVE_COUNTER = 0


def test_vcp_signals_memory_cache_keeps_recently_used_entry_on_eviction(monkeypatch, tmp_path):
    _reset_vcp_signals_cache_state()
    monkeypatch.setattr(vcp_signals_cache, "_VCP_SIGNALS_MEMORY_MAX_ENTRIES", 2)

    signature1 = ("vcp-signals", "2026-02-01", "2026-02-01", 1, 10)
    signature2 = ("vcp-signals", "2026-02-02", "2026-02-02", 2, 20)
    signature3 = ("vcp-signals", "2026-02-03", "2026-02-03", 3, 30)

    payload1 = [{"ticker": "000001", "score": 80}]
    payload2 = [{"ticker": "000002", "score": 81}]
    payload3 = [{"ticker": "000003", "score": 82}]

    vcp_signals_cache.save_cached_vcp_signals(
        signature=signature1,
        payload=payload1,
        data_dir=str(tmp_path),
        logger=None,
    )
    vcp_signals_cache.save_cached_vcp_signals(
        signature=signature2,
        payload=payload2,
        data_dir=str(tmp_path),
        logger=None,
    )

    loaded_first = vcp_signals_cache.get_cached_vcp_signals(
        signature=signature1,
        data_dir=str(tmp_path),
        logger=None,
    )
    assert loaded_first == payload1

    vcp_signals_cache.save_cached_vcp_signals(
        signature=signature3,
        payload=payload3,
        data_dir=str(tmp_path),
        logger=None,
    )

    digest1, _ = vcp_signals_cache._signature_digest(signature1)
    digest2, _ = vcp_signals_cache._signature_digest(signature2)
    digest3, _ = vcp_signals_cache._signature_digest(signature3)

    with vcp_signals_cache._VCP_SIGNALS_CACHE_LOCK:
        cache_keys = list(vcp_signals_cache._VCP_SIGNALS_MEMORY_CACHE.keys())

    assert len(cache_keys) == 2
    assert digest1 in cache_keys
    assert digest2 not in cache_keys
    assert digest3 in cache_keys


def test_build_vcp_payload_reuses_sqlite_cache_after_memory_clear(monkeypatch, tmp_path):
    _reset_vcp_signals_cache_state()
    _write_signals_csv(tmp_path, "2026-02-22")

    first = _build_payload(tmp_path, req_date="2026-02-22")
    assert first["count"] == 1
    assert first["signals"][0]["ticker"] == "005930"

    with vcp_signals_cache._VCP_SIGNALS_CACHE_LOCK:
        vcp_signals_cache._VCP_SIGNALS_MEMORY_CACHE.clear()

    monkeypatch.setattr(
        vcp_payload_service,
        "_load_csv_readonly",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("CSV loader should not run")),
    )
    second = _build_payload(tmp_path, req_date="2026-02-22")

    assert second["count"] == 1
    assert second["signals"][0]["ticker"] == "005930"


def test_build_vcp_payload_requests_readonly_ai_json_load(tmp_path):
    _reset_vcp_signals_cache_state()
    _write_signals_csv(tmp_path, "2026-02-22")

    captured_calls: list[tuple[str, dict[str, object]]] = []

    def _load_json_file(name: str, **kwargs):
        captured_calls.append((name, dict(kwargs)))
        return {"signals": []}

    payload = _build_payload(
        tmp_path,
        req_date="2026-02-22",
        load_json_file_fn=_load_json_file,
    )

    assert payload["count"] == 1
    assert captured_calls
    assert captured_calls[0][0] == "ai_analysis_results_20260222.json"
    assert all(kwargs.get("deep_copy") is False for _, kwargs in captured_calls)


def test_build_vcp_payload_sqlite_load_uses_read_only_connection(monkeypatch, tmp_path):
    _reset_vcp_signals_cache_state()
    _write_signals_csv(tmp_path, "2026-02-22")

    first = _build_payload(tmp_path, req_date="2026-02-22")
    assert first["count"] == 1

    with vcp_signals_cache._VCP_SIGNALS_CACHE_LOCK:
        vcp_signals_cache._VCP_SIGNALS_MEMORY_CACHE.clear()

    read_only_flags: list[bool] = []
    original_connect = vcp_signals_cache.connect_sqlite

    def _traced_connect(*args, **kwargs):
        if "read_only" in kwargs:
            read_only_flags.append(bool(kwargs["read_only"]))
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(vcp_signals_cache, "connect_sqlite", _traced_connect)

    second = _build_payload(tmp_path, req_date="2026-02-22")
    assert second["count"] == 1
    assert True in read_only_flags


def test_build_vcp_payload_prunes_sqlite_cache_rows(monkeypatch, tmp_path):
    _reset_vcp_signals_cache_state()
    monkeypatch.setattr(vcp_signals_cache, "_VCP_SIGNALS_SQLITE_MAX_ROWS", 2)

    for day in range(1, 5):
        _write_signals_csv(tmp_path, f"2026-02-0{day}")
        _ = _build_payload(tmp_path, req_date=f"2026-02-0{day}")

    with connect_sqlite(str(tmp_path / "runtime_cache.db")) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM vcp_signals_payload_cache")
        row_count = int(cursor.fetchone()[0])

    assert row_count == 2


def test_build_vcp_payload_creates_sqlite_parent_dir_when_missing(monkeypatch, tmp_path):
    _reset_vcp_signals_cache_state()
    _write_signals_csv(tmp_path, "2026-02-22")
    db_path = tmp_path / "cache" / "nested" / "runtime_cache.db"

    monkeypatch.setattr(vcp_signals_cache, "_resolve_cache_db_path", lambda _data_dir: str(db_path))

    payload = _build_payload(tmp_path, req_date="2026-02-22")

    assert payload["count"] == 1
    assert db_path.exists()

    with connect_sqlite(str(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM vcp_signals_payload_cache")
        row_count = int(cursor.fetchone()[0])

    assert row_count >= 1


def test_build_vcp_payload_allows_legacy_noarg_scanned_count_callback(tmp_path):
    _reset_vcp_signals_cache_state()
    _write_signals_csv(tmp_path, "2026-02-22")

    payload = _build_payload(
        tmp_path,
        req_date="2026-02-22",
        count_total_scanned_stocks_fn=lambda: 7,
    )

    assert payload["count"] == 1
    assert payload["total_scanned"] == 7


def test_build_vcp_payload_coerces_invalid_scanned_count_to_zero(tmp_path):
    _reset_vcp_signals_cache_state()
    _write_signals_csv(tmp_path, "2026-02-22")

    payload = _build_payload(
        tmp_path,
        req_date="2026-02-22",
        count_total_scanned_stocks_fn=lambda _data_dir: "N/A",
    )

    assert payload["count"] == 1
    assert payload["total_scanned"] == 0


def test_build_vcp_payload_recovers_when_sqlite_table_missing(tmp_path):
    _reset_vcp_signals_cache_state()
    _write_signals_csv(tmp_path, "2026-02-22")

    first = _build_payload(tmp_path, req_date="2026-02-22")
    assert first["count"] == 1

    db_path = tmp_path / "runtime_cache.db"
    with connect_sqlite(str(db_path)) as conn:
        conn.execute("DROP TABLE vcp_signals_payload_cache")
        conn.commit()

    with vcp_signals_cache._VCP_SIGNALS_CACHE_LOCK:
        vcp_signals_cache._VCP_SIGNALS_MEMORY_CACHE.clear()

    second = _build_payload(tmp_path, req_date="2026-02-22")
    assert second["count"] == 1
    assert second["signals"][0]["ticker"] == "005930"

    with connect_sqlite(str(db_path)) as conn:
        row_count = int(conn.execute("SELECT COUNT(*) FROM vcp_signals_payload_cache").fetchone()[0])
    assert row_count >= 1


def test_build_vcp_payload_skips_delete_when_rows_within_limit(monkeypatch, tmp_path):
    _reset_vcp_signals_cache_state()
    _write_signals_csv(tmp_path, "2026-02-22")
    monkeypatch.setattr(vcp_signals_cache, "_VCP_SIGNALS_SQLITE_MAX_ROWS", 16)

    traced_sql: list[str] = []
    original_connect = vcp_signals_cache.connect_sqlite

    def _traced_connect(*args, **kwargs):
        conn = original_connect(*args, **kwargs)
        conn.set_trace_callback(traced_sql.append)
        return conn

    monkeypatch.setattr(vcp_signals_cache, "connect_sqlite", _traced_connect)

    payload = _build_payload(tmp_path, req_date="2026-02-22")
    assert payload["count"] == 1
    assert not any("DELETE FROM vcp_signals_payload_cache" in sql for sql in traced_sql)


def test_save_cached_vcp_signals_repeated_signature_prunes_once(monkeypatch, tmp_path):
    _reset_vcp_signals_cache_state()
    monkeypatch.setattr(vcp_signals_cache, "_VCP_SIGNALS_SQLITE_PRUNE_FORCE_INTERVAL", 10_000)

    prune_calls = {"count": 0}
    original_prune = vcp_signals_cache.prune_rows_by_updated_at_if_needed

    def _counted_prune(*args, **kwargs):
        prune_calls["count"] += 1
        return original_prune(*args, **kwargs)

    monkeypatch.setattr(vcp_signals_cache, "prune_rows_by_updated_at_if_needed", _counted_prune)

    signature = ("vcp-signals", "2026-02-22", "2026-02-22", 1, 10)
    vcp_signals_cache.save_cached_vcp_signals(
        signature=signature,
        payload=[{"ticker": "005930", "score": 80}],
        data_dir=str(tmp_path),
        logger=None,
    )
    vcp_signals_cache.save_cached_vcp_signals(
        signature=signature,
        payload=[{"ticker": "005930", "score": 81}],
        data_dir=str(tmp_path),
        logger=None,
    )

    assert prune_calls["count"] == 1


def test_save_cached_vcp_signals_forces_prune_on_configured_interval(monkeypatch, tmp_path):
    _reset_vcp_signals_cache_state()
    monkeypatch.setattr(vcp_signals_cache, "_VCP_SIGNALS_SQLITE_PRUNE_FORCE_INTERVAL", 2)

    prune_calls = {"count": 0}
    original_prune = vcp_signals_cache.prune_rows_by_updated_at_if_needed

    def _counted_prune(*args, **kwargs):
        prune_calls["count"] += 1
        return original_prune(*args, **kwargs)

    monkeypatch.setattr(vcp_signals_cache, "prune_rows_by_updated_at_if_needed", _counted_prune)

    signature = ("vcp-signals", "2026-02-22", "2026-02-22", 1, 10)
    vcp_signals_cache.save_cached_vcp_signals(
        signature=signature,
        payload=[{"ticker": "005930", "score": 80}],
        data_dir=str(tmp_path),
        logger=None,
    )
    vcp_signals_cache.save_cached_vcp_signals(
        signature=signature,
        payload=[{"ticker": "005930", "score": 81}],
        data_dir=str(tmp_path),
        logger=None,
    )

    assert prune_calls["count"] == 2


def test_vcp_signals_sqlite_ready_cache_uses_normalized_db_key(monkeypatch, tmp_path):
    _reset_vcp_signals_cache_state()
    db_path = tmp_path / "runtime_cache.db"
    connect_calls = {"count": 0}
    logger = logging.getLogger("vcp-ready-normalized-test")
    original_connect = vcp_signals_cache.connect_sqlite

    def _counted_connect(*args, **kwargs):
        connect_calls["count"] += 1
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(vcp_signals_cache, "connect_sqlite", _counted_connect)

    assert vcp_signals_cache._ensure_sqlite_cache(str(db_path), logger) is True

    monkeypatch.chdir(tmp_path)
    relative_db_path = os.path.relpath(str(db_path), str(tmp_path))
    assert vcp_signals_cache._ensure_sqlite_cache(relative_db_path, logger) is True

    assert connect_calls["count"] == 1


def test_vcp_signals_sqlite_init_is_single_flight_under_concurrency(monkeypatch, tmp_path):
    _reset_vcp_signals_cache_state()
    db_path = str(tmp_path / "runtime_cache.db")
    logger = logging.getLogger("vcp-single-flight-test")

    monkeypatch.setattr(vcp_signals_cache, "sqlite_db_path_exists", lambda _path: True)

    entered_event = threading.Event()
    release_event = threading.Event()
    run_calls = {"count": 0}

    def _run_once(_operation, *, max_retries, retry_delay_seconds):
        run_calls["count"] += 1
        if run_calls["count"] == 1:
            entered_event.set()
            assert release_event.wait(timeout=2.0)
        return None

    monkeypatch.setattr(vcp_signals_cache, "run_sqlite_with_retry", _run_once)

    results: dict[str, bool] = {}

    def _worker(name: str) -> None:
        results[name] = bool(vcp_signals_cache._ensure_sqlite_cache(db_path, logger))

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
    assert run_calls["count"] == 1
    assert results == {"first": True, "second": True}


def test_vcp_signals_sqlite_waiter_retries_after_initializer_failure(monkeypatch, tmp_path):
    _reset_vcp_signals_cache_state()
    db_path = str(tmp_path / "runtime_cache.db")
    logger = logging.getLogger("vcp-waiter-retry-test")

    monkeypatch.setattr(vcp_signals_cache, "sqlite_db_path_exists", lambda _path: True)

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

    monkeypatch.setattr(vcp_signals_cache, "run_sqlite_with_retry", _fail_then_succeed)

    results: dict[str, bool] = {}

    def _worker(name: str) -> None:
        results[name] = bool(vcp_signals_cache._ensure_sqlite_cache(db_path, logger))

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
