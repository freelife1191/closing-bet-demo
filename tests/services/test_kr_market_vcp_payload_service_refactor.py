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
from datetime import datetime

import pandas as pd

import app.routes.kr_market_vcp_signal_helpers as vcp_signal_helpers
import services.kr_market_vcp_payload_service as vcp_payload_service
import services.kr_market_vcp_signals_cache as vcp_signals_cache
from services.sqlite_utils import connect_sqlite


def _write_signals_csv(tmp_path, signal_date: str, **overrides) -> None:
    """한 행짜리 signals_log.csv. 기본 행은 status 가 NEW 라 시그널 판정에서 떨어진다.
    판정을 통과시키려면 status="OPEN", is_vcp=True 를 넘긴다."""
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
                **overrides,
            }
        ]
    ).to_csv(tmp_path / "signals_log.csv", index=False)


def _build_payload(
    tmp_path,
    *,
    req_date: str | None,
    count_total_scanned_stocks_fn=lambda _data_dir: 1,
    load_json_file_fn=None,
    filter_signals_dataframe_by_date_fn=None,
    now=None,
):
    logger = logging.getLogger("vcp-payload-cache-test")
    if load_json_file_fn is None:
        load_json_file_fn = lambda _name, **_kwargs: {}
    if filter_signals_dataframe_by_date_fn is None:
        filter_signals_dataframe_by_date_fn = lambda df, req, _today: (
            df if not req else df[df["signal_date"] == req],
            req or "",
        )
    return vcp_payload_service.build_vcp_signals_payload(
        req_date=req_date,
        load_csv_file=lambda name: pd.read_csv(tmp_path / name),
        load_json_file=load_json_file_fn,
        filter_signals_dataframe_by_date=filter_signals_dataframe_by_date_fn,
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
        now=now,
        data_dir=str(tmp_path),
    )


def _real_helper_kwargs(tmp_path, *, now: datetime, logger_name: str) -> dict:
    """실제 필터·변환 헬퍼로 날짜 없는 조회를 만드는 인자 묶음."""
    return {
        "req_date": None,
        "load_csv_file": lambda name: pd.read_csv(tmp_path / name),
        "load_json_file": lambda _name, **_kwargs: {},
        "filter_signals_dataframe_by_date": vcp_signal_helpers._filter_signals_dataframe_by_date,
        "build_vcp_signals_from_dataframe": vcp_signal_helpers._build_vcp_signals_from_dataframe,
        "load_latest_vcp_price_map": lambda: {},
        "apply_latest_prices_to_jongga_signals": lambda _signals, _price_map: 0,
        "sort_and_limit_vcp_signals": vcp_signal_helpers._sort_and_limit_vcp_signals,
        "build_ai_data_map": vcp_signal_helpers._build_ai_data_map,
        "merge_legacy_ai_fields_into_map": vcp_signal_helpers._merge_legacy_ai_fields_into_map,
        "merge_ai_data_into_vcp_signals": vcp_signal_helpers._merge_ai_data_into_vcp_signals,
        "count_total_scanned_stocks": lambda _data_dir: 1,
        "logger": logging.getLogger(logger_name),
        "now": now,
        "data_dir": str(tmp_path),
    }


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


def _merge_ai_for_test(
    signals: list[dict[str, object]],
    files: dict[str, object],
    *,
    now: datetime,
) -> tuple[list[str], list[dict[str, object]]]:
    loaded_names: list[str] = []

    def _load_json_file(name: str, **_kwargs):
        loaded_names.append(name)
        return files.get(name, {})

    vcp_payload_service._merge_ai_into_vcp_signals(
        signals=signals,
        load_json_file=_load_json_file,
        build_ai_data_map=vcp_signal_helpers._build_ai_data_map,
        merge_legacy_ai_fields_into_map=vcp_signal_helpers._merge_legacy_ai_fields_into_map,
        merge_ai_data_into_vcp_signals=vcp_signal_helpers._merge_ai_data_into_vcp_signals,
        logger=logging.getLogger("vcp-payload-date-proof-test"),
        current_time=now,
    )
    return loaded_names, signals


def test_merge_ai_does_not_use_current_legacy_for_historical_signal_date():
    signals: list[dict[str, object]] = [{"ticker": "005930", "signal_date": "2026-02-13"}]
    legacy = {
        "signal_date": "2026-05-05",
        "signals": [
            {"ticker": "005930", "gpt_recommendation": {"action": "BUY", "reason": "최신"}}
        ],
    }

    loaded_names, merged = _merge_ai_for_test(
        signals,
        {"kr_ai_analysis.json": legacy},
        now=datetime(2026, 5, 5, 9, 0, 0),
    )

    assert loaded_names == ["ai_analysis_results_20260213.json"]
    assert "gpt_recommendation" not in merged[0]


def test_merge_ai_rejects_date_named_file_with_conflicting_internal_date():
    signals: list[dict[str, object]] = [{"ticker": "005930", "signal_date": "2026-02-13"}]
    conflicting = {
        "signal_date": "2026-05-05",
        "signals": [
            {"ticker": "005930", "gemini_recommendation": {"action": "BUY", "reason": "다른 날"}}
        ],
    }

    loaded_names, merged = _merge_ai_for_test(
        signals,
        {"ai_analysis_results_20260213.json": conflicting},
        now=datetime(2026, 2, 13, 9, 0, 0),
    )

    assert loaded_names == ["ai_analysis_results_20260213.json", "kr_ai_analysis.json"]
    assert "gemini_recommendation" not in merged[0]


def test_merge_ai_accepts_date_named_file_without_internal_date():
    signals: list[dict[str, object]] = [{"ticker": "005930", "signal_date": "2026-02-13"}]
    date_payload = {
        "signals": [
            {"ticker": "005930", "gemini_recommendation": {"action": "BUY", "reason": "파일명 날짜"}}
        ],
    }

    loaded_names, merged = _merge_ai_for_test(
        signals,
        {"ai_analysis_results_20260213.json": date_payload},
        now=datetime(2026, 5, 5, 9, 0, 0),
    )

    assert loaded_names == ["ai_analysis_results_20260213.json"]
    assert merged[0]["gemini_recommendation"]["reason"] == "파일명 날짜"


def test_merge_ai_uses_generic_legacy_only_when_current_date_is_proven():
    signals: list[dict[str, object]] = [{"ticker": "005930", "signal_date": "2026-02-13"}]
    legacy = {
        "signal_date": "2026-02-13",
        "signals": [
            {"ticker": "005930", "gpt_recommendation": {"action": "HOLD", "reason": "같은 날"}}
        ],
    }

    loaded_names, merged = _merge_ai_for_test(
        signals,
        {"kr_ai_analysis.json": legacy},
        now=datetime(2026, 2, 13, 9, 0, 0),
    )

    assert loaded_names == ["ai_analysis_results_20260213.json", "kr_ai_analysis.json"]
    assert merged[0]["gpt_recommendation"]["reason"] == "같은 날"


def test_merge_ai_fills_only_missing_fields_from_same_day_generic_legacy():
    signals: list[dict[str, object]] = [{"ticker": "005930", "signal_date": "2026-02-13"}]
    date_payload = {
        "signal_date": "2026-02-13",
        "signals": [
            {"ticker": "005930", "gemini_recommendation": {"action": "BUY", "reason": "날짜 파일"}}
        ],
    }
    legacy = {
        "signal_date": "2026-02-13",
        "signals": [
            {
                "ticker": "005930",
                "gemini_recommendation": {"action": "SELL", "reason": "덮어쓰면 안 됨"},
                "perplexity_recommendation": {"action": "HOLD", "reason": "legacy 보강"},
            }
        ],
    }

    _, merged = _merge_ai_for_test(
        signals,
        {
            "ai_analysis_results_20260213.json": date_payload,
            "kr_ai_analysis.json": legacy,
        },
        now=datetime(2026, 2, 13, 9, 0, 0),
    )

    assert merged[0]["gemini_recommendation"]["reason"] == "날짜 파일"
    assert merged[0]["perplexity_recommendation"]["reason"] == "legacy 보강"


def test_merge_ai_rejects_mixed_missing_or_non_iso_signal_dates():
    for signals in (
        [
            {"ticker": "005930", "signal_date": "2026-02-13"},
            {"ticker": "000660", "signal_date": "2026-02-14"},
        ],
        [{"ticker": "005930", "signal_date": ""}],
        [{"ticker": "005930", "signal_date": "20260213"}],
    ):
        loaded_names, merged = _merge_ai_for_test(
            signals,
            {},
            now=datetime(2026, 2, 13, 9, 0, 0),
        )

        assert loaded_names == []
        assert all("gemini_recommendation" not in item for item in merged)


def test_merge_ai_keeps_verified_date_payload_when_legacy_loader_fails_after_typeerror():
    signals: list[dict[str, object]] = [{"ticker": "005930", "signal_date": "2026-02-13"}]
    date_payload = {
        "signal_date": "2026-02-13",
        "signals": [
            {"ticker": "005930", "gemini_recommendation": {"action": "BUY", "reason": "날짜 파일"}}
        ],
    }

    def _load_json_file(name: str, **kwargs):
        if name == "ai_analysis_results_20260213.json":
            return date_payload
        if kwargs:
            raise TypeError("legacy loader does not accept deep_copy")
        raise RuntimeError("legacy file unavailable")

    vcp_payload_service._merge_ai_into_vcp_signals(
        signals=signals,
        load_json_file=_load_json_file,
        build_ai_data_map=vcp_signal_helpers._build_ai_data_map,
        merge_legacy_ai_fields_into_map=vcp_signal_helpers._merge_legacy_ai_fields_into_map,
        merge_ai_data_into_vcp_signals=vcp_signal_helpers._merge_ai_data_into_vcp_signals,
        logger=logging.getLogger("vcp-payload-legacy-loader-failure-test"),
        current_time=datetime(2026, 2, 13, 9, 0, 0),
    )

    assert signals[0]["gemini_recommendation"]["reason"] == "날짜 파일"


def test_merge_ai_keeps_verified_date_payload_when_legacy_shape_is_invalid():
    signals: list[dict[str, object]] = [{"ticker": "005930", "signal_date": "2026-02-13"}]
    date_payload = {
        "signal_date": "2026-02-13",
        "signals": [
            {"ticker": "005930", "gemini_recommendation": {"action": "BUY", "reason": "날짜 파일"}}
        ],
    }
    invalid_legacy = {"signal_date": "2026-02-13", "signals": None}

    _, merged = _merge_ai_for_test(
        signals,
        {
            "ai_analysis_results_20260213.json": date_payload,
            "kr_ai_analysis.json": invalid_legacy,
        },
        now=datetime(2026, 2, 13, 9, 0, 0),
    )

    assert merged[0]["gemini_recommendation"]["reason"] == "날짜 파일"


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


def test_build_vcp_payload_names_latest_date_when_filter_returns_nothing(tmp_path):
    """필터가 빈 결과를 주면 안내 문구가 오늘과 최신 저장 날짜를 함께 말한다."""
    _reset_vcp_signals_cache_state()
    _write_signals_csv(tmp_path, "2026-02-22")

    payload = _build_payload(
        tmp_path,
        req_date=None,
        filter_signals_dataframe_by_date_fn=lambda df, req, today: (
            df[df["signal_date"] == today],
            today,
        ),
        now=datetime(2026, 2, 23, 9, 0, 0),
    )

    assert payload["count"] == 0
    assert payload["signals"] == []
    assert payload["stale_warning"] == (
        "오늘(2026-02-23) 기준 VCP 시그널이 없습니다. 최신 저장 데이터는 2026-02-22입니다."
    )


def test_build_vcp_signals_cache_signature_includes_schema_version(tmp_path):
    _write_signals_csv(tmp_path, "2026-02-22")

    signature = vcp_signals_cache.build_vcp_signals_cache_signature(
        data_dir=str(tmp_path),
        req_date=None,
        today="2026-02-23",
    )

    assert signature is not None
    assert signature[0] == "vcp-signals"
    assert signature[1] == vcp_signals_cache._VCP_SIGNALS_CACHE_SCHEMA_VERSION


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


def test_build_vcp_payload_emits_stale_warning_when_today_signals_missing(tmp_path):
    _reset_vcp_signals_cache_state()
    _write_signals_csv(tmp_path, "2026-03-03")

    payload = vcp_payload_service.build_vcp_signals_payload(
        req_date=None,
        load_csv_file=lambda name: pd.read_csv(tmp_path / name),
        load_json_file=lambda _name, **_kwargs: {},
        filter_signals_dataframe_by_date=vcp_signal_helpers._filter_signals_dataframe_by_date,
        build_vcp_signals_from_dataframe=vcp_signal_helpers._build_vcp_signals_from_dataframe,
        load_latest_vcp_price_map=lambda: {},
        apply_latest_prices_to_jongga_signals=lambda _signals, _price_map: 0,
        sort_and_limit_vcp_signals=vcp_signal_helpers._sort_and_limit_vcp_signals,
        build_ai_data_map=vcp_signal_helpers._build_ai_data_map,
        merge_legacy_ai_fields_into_map=vcp_signal_helpers._merge_legacy_ai_fields_into_map,
        merge_ai_data_into_vcp_signals=vcp_signal_helpers._merge_ai_data_into_vcp_signals,
        count_total_scanned_stocks=lambda _data_dir: 1,
        logger=logging.getLogger("vcp-payload-stale-warning-test"),
        now=datetime(2026, 3, 4, 9, 0, 0),
        data_dir=str(tmp_path),
    )

    assert payload["count"] == 0
    assert "stale_warning" in payload
    assert "2026-03-03" in str(payload["stale_warning"])


def test_build_vcp_payload_falls_back_to_latest_saved_signals_when_today_missing(tmp_path):
    """[VCP-026] 오늘 자 시그널이 없으면 최신 저장분을 싣고 그 사실을 경고로 알린다.

    캐시에서 돌아오는 두 번째 호출도 같은 시그널과 같은 경고를 유지해야 한다.
    """
    _reset_vcp_signals_cache_state()
    _write_signals_csv(tmp_path, "2026-03-03", status="OPEN", is_vcp=True)

    kwargs = _real_helper_kwargs(tmp_path, now=datetime(2026, 3, 4, 9, 0, 0), logger_name="vcp-payload-latest-fallback-test")
    expected_warning = "오늘(2026-03-04) 기준 VCP 시그널이 없어 최신 저장분(2026-03-03)을 표시합니다."

    first = vcp_payload_service.build_vcp_signals_payload(**kwargs)
    second = vcp_payload_service.build_vcp_signals_payload(**kwargs)

    assert first["count"] == 1
    assert first["signals"][0]["signal_date"] == "2026-03-03"
    assert first["source"] == "signals_log.csv"
    assert first["stale_warning"] == expected_warning
    assert second["count"] == 1
    assert second["stale_warning"] == expected_warning


def test_build_vcp_payload_ignores_empty_cache_saved_under_the_previous_schema(tmp_path):
    """[VCP-026] 배포 전 스키마(버전 4)로 저장된 「오늘 기준 빈 결과」는 새 조회를 막지 못한다.

    빈 결과도 캐시에 남고 워커 재기동에도 살아남으므로, 같은 날짜·같은 CSV 서명으로 저장된
    옛 항목이 있으면 새 대체 로직이 그날 내내 무력화된다. 스키마 버전을 올려 옛 항목을
    통째로 무효화한다. 코드 리뷰가 스크립트로 재현한 회귀다.
    """
    _reset_vcp_signals_cache_state()
    _write_signals_csv(tmp_path, "2026-03-03", status="OPEN", is_vcp=True)
    legacy_signature = list(
        vcp_signals_cache.build_vcp_signals_cache_signature(
            data_dir=str(tmp_path), req_date=None, today="2026-03-04"
        )
    )
    legacy_signature[1] = 4
    vcp_signals_cache.save_cached_vcp_signals(
        signature=tuple(legacy_signature),
        payload=[],
        data_dir=str(tmp_path),
        logger=logging.getLogger("vcp-payload-legacy-cache-test"),
    )
    _reset_vcp_signals_cache_state()

    payload = vcp_payload_service.build_vcp_signals_payload(
        **_real_helper_kwargs(tmp_path, now=datetime(2026, 3, 4, 9, 0, 0), logger_name="vcp-payload-legacy-cache-test")
    )

    assert payload["count"] == 1
    assert payload["stale_warning"] == (
        "오늘(2026-03-04) 기준 VCP 시그널이 없어 최신 저장분(2026-03-03)을 표시합니다."
    )


def test_build_vcp_payload_fallback_survives_memory_cache_eviction(tmp_path):
    """대체 결과가 SQLite 캐시에서 돌아와도 같은 시그널과 경고를 유지한다."""
    _reset_vcp_signals_cache_state()
    _write_signals_csv(tmp_path, "2026-03-03", status="OPEN", is_vcp=True)
    kwargs = _real_helper_kwargs(tmp_path, now=datetime(2026, 3, 4, 9, 0, 0), logger_name="vcp-payload-sqlite-fallback-test")

    first = vcp_payload_service.build_vcp_signals_payload(**kwargs)
    with vcp_signals_cache._VCP_SIGNALS_CACHE_LOCK:
        vcp_signals_cache._VCP_SIGNALS_MEMORY_CACHE.clear()
    second = vcp_payload_service.build_vcp_signals_payload(**kwargs)

    assert second["count"] == first["count"] == 1
    assert second["stale_warning"] == first["stale_warning"]
    assert "최신 저장분(2026-03-03)" in second["stale_warning"]


def test_build_vcp_payload_requested_past_date_has_no_fallback_warning(tmp_path):
    """날짜를 지정한 조회는 과거 날짜라도 대체 표시 경고를 붙이지 않는다."""
    _reset_vcp_signals_cache_state()
    _write_signals_csv(tmp_path, "2026-03-03", status="OPEN", is_vcp=True)
    kwargs = _real_helper_kwargs(tmp_path, now=datetime(2026, 3, 4, 9, 0, 0), logger_name="vcp-payload-req-date-test")
    kwargs["req_date"] = "2026-03-03"

    payload = vcp_payload_service.build_vcp_signals_payload(**kwargs)

    assert payload["count"] == 1
    assert "stale_warning" not in payload


def test_build_vcp_payload_has_no_warning_when_today_signals_exist(tmp_path):
    _reset_vcp_signals_cache_state()
    _write_signals_csv(tmp_path, "2026-03-04", status="OPEN", is_vcp=True)

    payload = vcp_payload_service.build_vcp_signals_payload(
        **_real_helper_kwargs(tmp_path, now=datetime(2026, 3, 4, 9, 0, 0), logger_name="vcp-payload-today-present-test")
    )

    assert payload["count"] == 1
    assert "stale_warning" not in payload


def test_build_vcp_payload_warns_when_requested_date_has_no_signals(tmp_path):
    """[VCP-008] 회귀: 날짜를 지정한 조회가 비면 그 날짜를 담은 안내를 내려보낸다.

    종전에는 req_date 가 있으면 안내를 만들지 않아, 히스토리 탭이 빈 표만 보이고
    왜 비었는지 알 수 없었다.
    """
    _reset_vcp_signals_cache_state()
    _write_signals_csv(tmp_path, "2026-02-22")

    payload = _build_payload(tmp_path, req_date="2026-01-05")

    assert payload["count"] == 0
    assert payload["stale_warning"] == "2026-01-05에 저장된 VCP 시그널이 없습니다."

    # 요청 값을 그대로 문구에 싣지 않는다. 날짜로 읽히지 않으면 일반 문구를 쓴다.
    _reset_vcp_signals_cache_state()
    unparsable = _build_payload(tmp_path, req_date="not-a-date")

    assert unparsable["stale_warning"] == "요청한 날짜에 저장된 VCP 시그널이 없습니다."


def test_build_vcp_payload_warns_when_rows_exist_but_no_signal_qualifies(tmp_path):
    """[VCP-008] 회귀: 날짜 행이 남아도 시그널 판정에서 전부 떨어지면 안내를 만든다.

    안내 판정의 기준은 필터를 통과한 행 수가 아니라 변환된 시그널 수다. fixture 의
    행은 status 가 OPEN 이 아니어서 판정에서 떨어지며, 실제 data/signals_log.csv 도
    is_vcp 가 비어 같은 상태다.
    """
    _reset_vcp_signals_cache_state()
    _write_signals_csv(tmp_path, "2026-02-22")

    payload = vcp_payload_service.build_vcp_signals_payload(
        req_date="2026-02-22",
        load_csv_file=lambda name: pd.read_csv(tmp_path / name),
        load_json_file=lambda _name, **_kwargs: {},
        filter_signals_dataframe_by_date=vcp_signal_helpers._filter_signals_dataframe_by_date,
        build_vcp_signals_from_dataframe=vcp_signal_helpers._build_vcp_signals_from_dataframe,
        load_latest_vcp_price_map=lambda: {},
        apply_latest_prices_to_jongga_signals=lambda _signals, _price_map: 0,
        sort_and_limit_vcp_signals=vcp_signal_helpers._sort_and_limit_vcp_signals,
        build_ai_data_map=vcp_signal_helpers._build_ai_data_map,
        merge_legacy_ai_fields_into_map=vcp_signal_helpers._merge_legacy_ai_fields_into_map,
        merge_ai_data_into_vcp_signals=vcp_signal_helpers._merge_ai_data_into_vcp_signals,
        count_total_scanned_stocks=lambda _data_dir: 1,
        logger=logging.getLogger("vcp-payload-unqualified-rows-test"),
        now=datetime(2026, 2, 23, 9, 0, 0),
        data_dir=str(tmp_path),
    )

    assert payload["count"] == 0
    assert payload["stale_warning"] == "2026-02-22에 저장된 VCP 시그널이 없습니다."


def test_build_vcp_payload_warns_when_today_rows_exist_but_no_signal_qualifies(tmp_path):
    """[VCP-019] 회귀: 오늘 자 행이 있어도 시그널이 0건이면 그 사실을 알린다.

    종전에는 원본의 최신 signal_date 가 오늘 이상이면 곧바로 None 을 돌려주어, 그 행들이
    판정에서 전부 떨어져도 화면이 이유 없이 빈 표만 보였다. 캐시를 쓰는 두 번째 호출도
    같은 문구를 유지해야 하므로 이어서 확인한다.
    """
    _reset_vcp_signals_cache_state()
    _write_signals_csv(tmp_path, "2026-02-23")

    kwargs = {
        "req_date": None,
        "load_csv_file": lambda name: pd.read_csv(tmp_path / name),
        "load_json_file": lambda _name, **_kwargs: {},
        "filter_signals_dataframe_by_date": vcp_signal_helpers._filter_signals_dataframe_by_date,
        "build_vcp_signals_from_dataframe": vcp_signal_helpers._build_vcp_signals_from_dataframe,
        "load_latest_vcp_price_map": lambda: {},
        "apply_latest_prices_to_jongga_signals": lambda _signals, _price_map: 0,
        "sort_and_limit_vcp_signals": vcp_signal_helpers._sort_and_limit_vcp_signals,
        "build_ai_data_map": vcp_signal_helpers._build_ai_data_map,
        "merge_legacy_ai_fields_into_map": vcp_signal_helpers._merge_legacy_ai_fields_into_map,
        "merge_ai_data_into_vcp_signals": vcp_signal_helpers._merge_ai_data_into_vcp_signals,
        "count_total_scanned_stocks": lambda _data_dir: 1,
        "logger": logging.getLogger("vcp-payload-today-unqualified-rows-test"),
        "now": datetime(2026, 2, 23, 9, 0, 0),
        "data_dir": str(tmp_path),
    }

    payload = vcp_payload_service.build_vcp_signals_payload(**kwargs)
    cached_payload = vcp_payload_service.build_vcp_signals_payload(**kwargs)

    assert payload["count"] == 0
    assert payload["stale_warning"] == "오늘(2026-02-23) 기준 VCP 시그널이 없습니다."
    assert cached_payload["stale_warning"] == payload["stale_warning"]


def test_resolve_stale_warning_names_latest_date_when_it_is_in_the_future():
    """[VCP-019] 최신 저장 날짜가 미래이면 그 날짜를 감추지 않는다.

    날짜 목록은 같은 판정으로 만들어지므로 미래 날짜도 드롭다운에 나타난다. 배너가
    그 날짜를 말하지 않으면 사용자는 목록에 보이는 자료를 배너에서 확인할 수 없다.
    """
    message = vcp_payload_service._resolve_stale_warning_message(
        req_date=None,
        source_df=pd.DataFrame([{"signal_date": "2026-03-01"}]),
        today="2026-02-23",
    )

    assert message == (
        "오늘(2026-02-23) 기준 VCP 시그널이 없습니다. 최신 저장 데이터는 2026-03-01입니다."
    )


def test_build_vcp_payload_cached_empty_keeps_stale_warning(tmp_path):
    _reset_vcp_signals_cache_state()
    _write_signals_csv(tmp_path, "2026-03-03")

    kwargs = {
        "req_date": None,
        "load_csv_file": lambda name: pd.read_csv(tmp_path / name),
        "load_json_file": lambda _name, **_kwargs: {},
        "filter_signals_dataframe_by_date": vcp_signal_helpers._filter_signals_dataframe_by_date,
        "build_vcp_signals_from_dataframe": vcp_signal_helpers._build_vcp_signals_from_dataframe,
        "load_latest_vcp_price_map": lambda: {},
        "apply_latest_prices_to_jongga_signals": lambda _signals, _price_map: 0,
        "sort_and_limit_vcp_signals": vcp_signal_helpers._sort_and_limit_vcp_signals,
        "build_ai_data_map": vcp_signal_helpers._build_ai_data_map,
        "merge_legacy_ai_fields_into_map": vcp_signal_helpers._merge_legacy_ai_fields_into_map,
        "merge_ai_data_into_vcp_signals": vcp_signal_helpers._merge_ai_data_into_vcp_signals,
        "count_total_scanned_stocks": lambda _data_dir: 1,
        "logger": logging.getLogger("vcp-payload-cached-stale-warning-test"),
        "now": datetime(2026, 3, 4, 9, 0, 0),
        "data_dir": str(tmp_path),
    }

    first = vcp_payload_service.build_vcp_signals_payload(**kwargs)
    second = vcp_payload_service.build_vcp_signals_payload(**kwargs)

    assert first["count"] == 0
    assert second["count"] == 0
    assert "2026-03-03" in str(second.get("stale_warning"))


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


def test_build_vcp_payload_cache_hit_skips_signals_csv_reread(tmp_path):
    """캐시에 시그널이 있으면 stale 판정용 CSV를 다시 읽지 않는다."""
    _reset_vcp_signals_cache_state()
    _write_signals_csv(tmp_path, "2026-03-03")

    read_filenames: list[str] = []

    def _counting_load_csv(name):
        read_filenames.append(name)
        return pd.read_csv(tmp_path / name)

    kwargs = {
        "req_date": None,
        "load_csv_file": _counting_load_csv,
        "load_json_file": lambda _name, **_kwargs: {},
        "filter_signals_dataframe_by_date": lambda df, _req, _today: (df, ""),
        "build_vcp_signals_from_dataframe": lambda df: [
            {"ticker": str(row["ticker"]).zfill(6), "signal_date": row["signal_date"]}
            for _, row in df.iterrows()
        ],
        "load_latest_vcp_price_map": lambda: {},
        "apply_latest_prices_to_jongga_signals": lambda _signals, _price_map: 0,
        "sort_and_limit_vcp_signals": lambda signals, limit=100: list(signals)[:limit],
        "build_ai_data_map": lambda _payload: {},
        "merge_legacy_ai_fields_into_map": lambda _ai_map, _legacy: None,
        "merge_ai_data_into_vcp_signals": lambda _signals, _ai_map: 0,
        "count_total_scanned_stocks": lambda _data_dir: 1,
        "logger": logging.getLogger("vcp-payload-cache-hit-reread-test"),
        "now": datetime(2026, 3, 3, 9, 0, 0),
        "data_dir": str(tmp_path),
    }

    first = vcp_payload_service.build_vcp_signals_payload(**kwargs)
    reads_after_first = len(read_filenames)
    second = vcp_payload_service.build_vcp_signals_payload(**kwargs)

    assert first["count"] == 1
    assert second["count"] == 1
    assert second.get("stale_warning") is None
    assert len(read_filenames) == reads_after_first
