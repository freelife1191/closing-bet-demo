#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Jongga Payload Helpers 리팩토링 회귀 테스트
"""

from __future__ import annotations

import os
import types

import services.kr_market_jongga_payload_helpers as payload_helpers
from services.sqlite_utils import connect_sqlite


def _logger_stub():
    return types.SimpleNamespace(
        info=lambda *_args, **_kwargs: None,
        warning=lambda *_args, **_kwargs: None,
    )


def test_find_recent_valid_jongga_payload_reuses_cache_when_files_unchanged(monkeypatch, tmp_path):
    payload_helpers._RECENT_JONGGA_PAYLOAD_CACHE.clear()
    payload_helpers._RECENT_JONGGA_SQLITE_READY.clear()
    result_path = tmp_path / "jongga_v2_results_20260220.json"
    result_path.write_text("{}", encoding="utf-8")
    calls = {"count": 0}

    original_loader = payload_helpers.load_json_from_path

    def _counted_loader(file_path, logger):
        calls["count"] += 1
        return original_loader(file_path, logger)

    monkeypatch.setattr(payload_helpers, "load_json_from_path", _counted_loader)

    # 파일 내용을 dict로 강제 주입해 유효 payload를 만들기 위해 loader만 대체
    monkeypatch.setattr(
        payload_helpers,
        "load_json_from_path",
        lambda file_path, logger: (
            calls.__setitem__("count", calls["count"] + 1)
            or {"date": "2026-02-20", "signals": [{"ticker": "000001"}]}
        ),
    )

    first = payload_helpers.find_recent_valid_jongga_payload(
        data_dir=str(tmp_path),
        recalculate_jongga_grades=lambda _payload: False,
        logger=_logger_stub(),
    )
    second = payload_helpers.find_recent_valid_jongga_payload(
        data_dir=str(tmp_path),
        recalculate_jongga_grades=lambda _payload: False,
        logger=_logger_stub(),
    )

    assert first is not None and second is not None
    assert calls["count"] == 1


def test_find_recent_valid_jongga_payload_invalidates_cache_when_file_changes(monkeypatch, tmp_path):
    payload_helpers._RECENT_JONGGA_PAYLOAD_CACHE.clear()
    payload_helpers._RECENT_JONGGA_SQLITE_READY.clear()
    result_path = tmp_path / "jongga_v2_results_20260220.json"
    result_path.write_text("{}", encoding="utf-8")
    calls = {"count": 0}

    monkeypatch.setattr(
        payload_helpers,
        "load_json_from_path",
        lambda file_path, logger: (
            calls.__setitem__("count", calls["count"] + 1)
            or {"date": "2026-02-20", "signals": [{"ticker": "000001"}]}
        ),
    )

    _ = payload_helpers.find_recent_valid_jongga_payload(
        data_dir=str(tmp_path),
        recalculate_jongga_grades=lambda _payload: False,
        logger=_logger_stub(),
    )
    assert calls["count"] == 1

    updated_mtime = result_path.stat().st_mtime + 2
    os.utime(result_path, (updated_mtime, updated_mtime))

    _ = payload_helpers.find_recent_valid_jongga_payload(
        data_dir=str(tmp_path),
        recalculate_jongga_grades=lambda _payload: False,
        logger=_logger_stub(),
    )
    assert calls["count"] == 2


def test_find_recent_valid_jongga_payload_returns_cloned_payload(monkeypatch, tmp_path):
    payload_helpers._RECENT_JONGGA_PAYLOAD_CACHE.clear()
    payload_helpers._RECENT_JONGGA_SQLITE_READY.clear()
    (tmp_path / "jongga_v2_results_20260220.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        payload_helpers,
        "load_json_from_path",
        lambda file_path, logger: {
            "date": "2026-02-20",
            "signals": [{"ticker": "000001", "grade": "A"}],
        },
    )

    first = payload_helpers.find_recent_valid_jongga_payload(
        data_dir=str(tmp_path),
        recalculate_jongga_grades=lambda _payload: False,
        logger=_logger_stub(),
    )
    assert first is not None
    first["signals"][0]["grade"] = "Z"

    second = payload_helpers.find_recent_valid_jongga_payload(
        data_dir=str(tmp_path),
        recalculate_jongga_grades=lambda _payload: False,
        logger=_logger_stub(),
    )
    assert second is not None
    assert second["signals"][0]["grade"] == "A"


def test_find_recent_valid_jongga_payload_uses_sqlite_cache_after_memory_clear(monkeypatch, tmp_path):
    payload_helpers._RECENT_JONGGA_PAYLOAD_CACHE.clear()
    payload_helpers._RECENT_JONGGA_SQLITE_READY.clear()
    (tmp_path / "jongga_v2_results_20260220.json").write_text("{}", encoding="utf-8")

    first = payload_helpers.find_recent_valid_jongga_payload(
        data_dir=str(tmp_path),
        recalculate_jongga_grades=lambda _payload: False,
        logger=_logger_stub(),
    )
    assert first is None

    monkeypatch.setattr(
        payload_helpers,
        "load_json_from_path",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("loader should not run")),
    )
    payload_helpers._RECENT_JONGGA_PAYLOAD_CACHE.clear()

    # 유효 payload를 sqlite 캐시에 넣기 위해 한 번 실제 payload 생성
    monkeypatch.setattr(
        payload_helpers,
        "load_json_from_path",
        lambda file_path, logger: {
            "date": "2026-02-20",
            "signals": [{"ticker": "000001"}],
        },
    )
    _ = payload_helpers.find_recent_valid_jongga_payload(
        data_dir=str(tmp_path),
        recalculate_jongga_grades=lambda _payload: False,
        logger=_logger_stub(),
    )

    payload_helpers._RECENT_JONGGA_PAYLOAD_CACHE.clear()
    monkeypatch.setattr(
        payload_helpers,
        "load_json_from_path",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("loader should not run")),
    )
    second = payload_helpers.find_recent_valid_jongga_payload(
        data_dir=str(tmp_path),
        recalculate_jongga_grades=lambda _payload: False,
        logger=_logger_stub(),
    )

    assert second is not None
    assert second["signals"][0]["ticker"] == "000001"


def test_find_recent_valid_jongga_payload_prunes_sqlite_rows(monkeypatch, tmp_path):
    payload_helpers._RECENT_JONGGA_PAYLOAD_CACHE.clear()
    payload_helpers._RECENT_JONGGA_SQLITE_READY.clear()
    monkeypatch.setattr(payload_helpers, "_RECENT_JONGGA_SQLITE_MAX_ROWS", 2)
    result_path = tmp_path / "jongga_v2_results_20260220.json"
    result_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        payload_helpers,
        "load_json_from_path",
        lambda file_path, logger: {
            "date": "2026-02-20",
            "signals": [{"ticker": "000001"}],
        },
    )

    for i in range(4):
        updated_mtime = result_path.stat().st_mtime + 2 + i
        os.utime(result_path, (updated_mtime, updated_mtime))
        _ = payload_helpers.find_recent_valid_jongga_payload(
            data_dir=str(tmp_path),
            recalculate_jongga_grades=lambda _payload: False,
            logger=_logger_stub(),
        )
        payload_helpers._RECENT_JONGGA_PAYLOAD_CACHE.clear()

    with connect_sqlite(str(tmp_path / "runtime_cache.db")) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM jongga_recent_valid_payload_cache")
        row_count = int(cursor.fetchone()[0])

    assert row_count == 2
