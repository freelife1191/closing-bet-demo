#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generator_result_storage 리팩토링 회귀 테스트
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date
from types import SimpleNamespace
from pathlib import Path


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import engine.generator_result_storage as storage


class _DummySignal:
    def __init__(self, payload: dict):
        self._payload = payload

    def to_dict(self) -> dict:
        return dict(self._payload)


def _build_result() -> SimpleNamespace:
    return SimpleNamespace(
        date=date(2026, 2, 22),
        total_candidates=2,
        filtered_count=1,
        signals=[
            _DummySignal(
                {
                    "stock_code": "005930",
                    "grade": "A",
                    "score": {"total": 9},
                }
            )
        ],
        by_grade={"A": 1},
        by_market={"KOSPI": 1},
        processing_time_ms=123.4,
        market_status={"status": "GREEN"},
        market_summary="ok",
        trending_themes=["반도체"],
        scanned_count=200,
    )


def test_save_result_to_json_uses_atomic_writer(monkeypatch, tmp_path: Path):
    writes: list[tuple[str, str]] = []

    def _atomic_write(path: str, content: str):
        writes.append((path, content))
        Path(path).write_text(content, encoding="utf-8")

    monkeypatch.setattr(storage, "atomic_write_text", _atomic_write)

    storage.save_result_to_json(_build_result(), data_dir=str(tmp_path))

    assert len(writes) == 2
    written_paths = {Path(path).name for path, _ in writes}
    assert "jongga_v2_latest.json" in written_paths
    assert "jongga_v2_results_20260222.json" in written_paths

    latest_content = next(content for path, content in writes if path.endswith("jongga_v2_latest.json"))
    payload = json.loads(latest_content)
    assert payload["date"] == "2026-02-22"
    assert payload["signals"][0]["stock_code"] == "005930"


def test_update_single_signal_json_uses_cached_loader_and_atomic_writer(monkeypatch, tmp_path: Path):
    latest_path = tmp_path / "jongga_v2_latest.json"
    daily_path = tmp_path / "jongga_v2_results_20260222.json"
    latest_path.write_text("{}", encoding="utf-8")
    daily_path.write_text("{}", encoding="utf-8")

    called = {"path": None}
    writes: list[tuple[str, str]] = []

    def _loader(path: str):
        called["path"] = path
        return {
            "signals": [
                {"stock_code": "005930", "grade": "B", "score": {"total": 1}},
                {"stock_code": "000660", "grade": "S", "score": {"total": 3}},
            ]
        }

    def _atomic_write(path: str, content: str):
        writes.append((path, content))
        Path(path).write_text(content, encoding="utf-8")

    monkeypatch.setattr(storage, "load_json_payload_from_path", _loader)
    monkeypatch.setattr(storage, "atomic_write_text", _atomic_write)

    storage.update_single_signal_json(
        code="005930",
        signal=_DummySignal({"stock_code": "005930", "grade": "A", "score": {"total": 99}}),
        data_dir=str(tmp_path),
        as_of_date=date(2026, 2, 22),
    )

    assert called["path"] == str(latest_path)
    assert len(writes) == 2

    latest_payload = json.loads(next(content for path, content in writes if path.endswith("jongga_v2_latest.json")))
    assert latest_payload["signals"][0]["stock_code"] == "000660"
    assert any(row["stock_code"] == "005930" and row["score"]["total"] == 99 for row in latest_payload["signals"])


def test_update_single_signal_json_skips_when_cached_payload_invalid(monkeypatch, tmp_path: Path):
    latest_path = tmp_path / "jongga_v2_latest.json"
    latest_path.write_text("{}", encoding="utf-8")
    writes: list[tuple[str, str]] = []

    monkeypatch.setattr(storage, "load_json_payload_from_path", lambda _path: [])
    monkeypatch.setattr(storage, "atomic_write_text", lambda path, content: writes.append((path, content)))

    storage.update_single_signal_json(
        code="005930",
        signal=_DummySignal({"stock_code": "005930", "grade": "A", "score": {"total": 99}}),
        data_dir=str(tmp_path),
        as_of_date=date(2026, 2, 22),
    )

    assert writes == []
