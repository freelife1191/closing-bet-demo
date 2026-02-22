#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market VCP Payload Service SQLite 캐시 회귀 테스트
"""

from __future__ import annotations

import logging
import os

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
):
    logger = logging.getLogger("vcp-payload-cache-test")
    return vcp_payload_service.build_vcp_signals_payload(
        req_date=req_date,
        load_csv_file=lambda name: pd.read_csv(tmp_path / name),
        load_json_file=lambda _name: {},
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
    vcp_signals_cache._VCP_SIGNALS_SQLITE_READY.clear()


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
