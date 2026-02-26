#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Common Data Status Service 단위 테스트
"""

import json
from pathlib import Path
import types

import services.common_data_status_service as common_data_status_service
import services.file_row_count_cache as file_row_count_cache
from services.common_data_status_service import build_common_data_status_payload


def test_build_common_data_status_payload_with_csv_and_json(tmp_path: Path):
    common_data_status_service.clear_common_data_status_cache()
    csv_path = tmp_path / "daily_prices.csv"
    csv_path.write_text("date,ticker,close\n2026-02-21,005930,100\n", encoding="utf-8")

    json_path = tmp_path / "jongga_v2_latest.json"
    json_path.write_text(
        json.dumps({"signals": [{"stock_code": "005930"}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    payload = build_common_data_status_payload(
        data_files_to_check=[
            {"name": "Daily Prices", "path": str(csv_path), "link": "/a", "menu": "A"},
            {"name": "Jongga", "path": str(json_path), "link": "/b", "menu": "B"},
            {"name": "Missing", "path": str(tmp_path / "missing.csv"), "link": "/c", "menu": "C"},
        ],
        load_update_status=lambda: {"isRunning": True, "startTime": "2026-02-21T09:00:00", "currentItem": "X"},
        logger=types.SimpleNamespace(debug=lambda *_a, **_k: None),
    )

    files = payload["files"]
    assert files[0]["exists"] is True
    assert files[0]["rowCount"] == 1
    assert files[1]["exists"] is True
    assert files[1]["rowCount"] == 1
    assert files[2]["exists"] is False

    update_status = payload["update_status"]
    assert update_status["isRunning"] is True
    assert update_status["lastRun"] == "2026-02-21T09:00:00"
    assert update_status["progress"] == "X"


def test_build_common_data_status_payload_reuses_row_count_cache_until_file_changes(tmp_path: Path, monkeypatch):
    common_data_status_service.clear_common_data_status_cache()
    csv_path = tmp_path / "daily_prices.csv"
    csv_path.write_text("date,ticker,close\n2026-02-21,005930,100\n", encoding="utf-8")

    call_counter = {"count": 0}
    original_count_rows = file_row_count_cache.count_rows_for_path

    def _count_rows_spy(path, logger):
        call_counter["count"] += 1
        return original_count_rows(path, logger)

    monkeypatch.setattr(file_row_count_cache, "count_rows_for_path", _count_rows_spy)

    kwargs = dict(
        data_files_to_check=[{"name": "Daily Prices", "path": str(csv_path)}],
        load_update_status=lambda: {"isRunning": False},
        logger=types.SimpleNamespace(debug=lambda *_a, **_k: None),
    )

    first_payload = build_common_data_status_payload(**kwargs)
    second_payload = build_common_data_status_payload(**kwargs)

    assert first_payload["files"][0]["rowCount"] == 1
    assert second_payload["files"][0]["rowCount"] == 1
    assert call_counter["count"] == 1

    csv_path.write_text(
        "date,ticker,close\n2026-02-21,005930,100\n2026-02-22,005930,110\n",
        encoding="utf-8",
    )
    payload_after_change = build_common_data_status_payload(**kwargs)

    assert payload_after_change["files"][0]["rowCount"] == 2
    assert call_counter["count"] == 2


def test_build_common_data_status_payload_uses_sqlite_row_count_cache_after_memory_clear(
    tmp_path: Path,
    monkeypatch,
):
    cache_db = tmp_path / "runtime_cache.db"
    monkeypatch.setattr(file_row_count_cache, "_ROW_COUNT_CACHE_DB_PATH", str(cache_db))
    file_row_count_cache._ROW_COUNT_SQLITE_READY.clear()
    common_data_status_service.clear_common_data_status_cache()

    csv_path = tmp_path / "daily_prices.csv"
    csv_path.write_text("date,ticker,close\n2026-02-21,005930,100\n", encoding="utf-8")

    kwargs = dict(
        data_files_to_check=[{"name": "Daily Prices", "path": str(csv_path)}],
        load_update_status=lambda: {"isRunning": False},
        logger=types.SimpleNamespace(debug=lambda *_a, **_k: None),
    )
    first_payload = build_common_data_status_payload(**kwargs)
    assert first_payload["files"][0]["rowCount"] == 1

    common_data_status_service.clear_common_data_status_cache()

    monkeypatch.setattr(
        file_row_count_cache,
        "count_rows_for_path",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("should use sqlite cache")),
    )

    second_payload = build_common_data_status_payload(**kwargs)
    assert second_payload["files"][0]["rowCount"] == 1


def test_build_common_data_status_payload_requests_readonly_update_status():
    captured = {"kwargs": None}

    def _load_update_status(**kwargs):
        captured["kwargs"] = dict(kwargs)
        return {"isRunning": False, "startTime": None, "currentItem": None}

    payload = build_common_data_status_payload(
        data_files_to_check=[],
        load_update_status=_load_update_status,
        logger=types.SimpleNamespace(debug=lambda *_a, **_k: None),
    )

    assert payload["update_status"]["isRunning"] is False
    assert captured["kwargs"]["deep_copy"] is False
