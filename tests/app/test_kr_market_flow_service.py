#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Flow Service 단위 테스트
"""

import os
import sys
import types
from pathlib import Path
from threading import Event

import pandas as pd

from services.kr_market_flow_service import (
    build_market_status_payload,
    collect_jongga_v2_dates,
    execute_market_gate_update,
    launch_background_update_job,
    launch_init_data_update,
    start_vcp_screener_run,
)


def test_build_market_status_payload_when_prices_are_empty():
    payload = build_market_status_payload(load_csv_file=lambda _name: pd.DataFrame())
    assert payload["status"] == "NEUTRAL"
    assert payload["symbol"] == "069500"
    assert "message" in payload


def test_build_market_status_payload_uses_kodex_row():
    df = pd.DataFrame(
        [
            {"ticker": "000001", "close": 100, "date": "2026-02-20"},
            {"ticker": "069500", "close": 345.2, "date": "2026-02-21"},
        ]
    )
    payload = build_market_status_payload(load_csv_file=lambda _name: df)
    assert payload["current_price"] == 345.2
    assert payload["date"] == "2026-02-21"


def test_build_market_status_payload_caches_ticker_padding_column_on_dataframe():
    df = pd.DataFrame(
        [
            {"ticker": "69500", "close": 350.0, "date": "2026-02-22"},
            {"ticker": "000001", "close": 100.0, "date": "2026-02-21"},
        ]
    )
    assert "_ticker_padded" not in df.columns

    first = build_market_status_payload(load_csv_file=lambda _name: df)
    second = build_market_status_payload(load_csv_file=lambda _name: df)

    assert "_ticker_padded" in df.columns
    assert first["current_price"] == 350.0
    assert second["current_price"] == 350.0


def test_collect_jongga_v2_dates_reads_files_and_latest(tmp_path: Path):
    (tmp_path / "jongga_v2_results_20260220.json").write_text("{}", encoding="utf-8")
    (tmp_path / "jongga_v2_results_custom.json").write_text("{}", encoding="utf-8")

    dates = collect_jongga_v2_dates(
        data_dir=tmp_path,
        load_json_file=lambda _name: {"date": "2026-02-21T15:30:00"},
        logger=types.SimpleNamespace(warning=lambda *_args, **_kwargs: None),
    )

    assert "2026-02-21" in dates
    assert "2026-02-20" in dates
    assert "custom" in dates


def test_collect_jongga_v2_dates_uses_cache_when_signature_is_same(tmp_path: Path):
    (tmp_path / "jongga_v2_results_20260220.json").write_text("{}", encoding="utf-8")
    latest_file = tmp_path / "jongga_v2_latest.json"
    latest_file.write_text("{}", encoding="utf-8")
    calls = {"count": 0}

    def _load_latest(_name: str):
        calls["count"] += 1
        return {"date": "2026-02-21T15:30:00"}

    dates1 = collect_jongga_v2_dates(
        data_dir=tmp_path,
        load_json_file=_load_latest,
        logger=types.SimpleNamespace(warning=lambda *_args, **_kwargs: None),
    )
    dates2 = collect_jongga_v2_dates(
        data_dir=tmp_path,
        load_json_file=_load_latest,
        logger=types.SimpleNamespace(warning=lambda *_args, **_kwargs: None),
    )

    assert calls["count"] == 1
    assert dates1 == dates2


def test_collect_jongga_v2_dates_invalidates_cache_when_latest_file_changes(tmp_path: Path):
    (tmp_path / "jongga_v2_results_20260220.json").write_text("{}", encoding="utf-8")
    latest_file = tmp_path / "jongga_v2_latest.json"
    latest_file.write_text("{}", encoding="utf-8")
    calls = {"count": 0}

    def _load_latest(_name: str):
        calls["count"] += 1
        return {"date": "2026-02-21T15:30:00"}

    _ = collect_jongga_v2_dates(
        data_dir=tmp_path,
        load_json_file=_load_latest,
        logger=types.SimpleNamespace(warning=lambda *_args, **_kwargs: None),
    )
    assert calls["count"] == 1

    updated_mtime = latest_file.stat().st_mtime + 2
    os.utime(latest_file, (updated_mtime, updated_mtime))

    _ = collect_jongga_v2_dates(
        data_dir=tmp_path,
        load_json_file=_load_latest,
        logger=types.SimpleNamespace(warning=lambda *_args, **_kwargs: None),
    )
    assert calls["count"] == 2


def test_start_vcp_screener_run_sets_status_and_invokes_runner():
    called = Event()
    received = {}

    def _runner(target_date, max_stocks):
        received["target_date"] = target_date
        received["max_stocks"] = max_stocks
        called.set()

    status_state = {"running": False}
    status_code, payload = start_vcp_screener_run(
        req_data={"target_date": "2026-02-21", "max_stocks": 33},
        status_state=status_state,
        background_runner=_runner,
    )

    assert status_code == 200
    assert payload["status"] == "started"
    assert status_state["running"] is True
    assert called.wait(timeout=1.0)
    assert received["target_date"] == "2026-02-21"
    assert received["max_stocks"] == 33


def test_launch_background_update_job_and_conflict():
    called = Event()

    def _run_background_update(target_date, items):
        assert target_date == "2026-02-21"
        assert items == ["A", "B"]
        called.set()

    started = {}
    status_code, payload = launch_background_update_job(
        items_list=["A", "B"],
        target_date="2026-02-21",
        load_update_status=lambda: {"isRunning": False},
        start_update=lambda items: started.setdefault("items", items),
        run_background_update=_run_background_update,
        logger=types.SimpleNamespace(info=lambda *_args, **_kwargs: None),
    )
    assert status_code == 200
    assert payload["status"] == "started"
    assert started["items"] == ["A", "B"]
    assert called.wait(timeout=1.0)

    status_code, payload = launch_background_update_job(
        items_list=["A"],
        target_date=None,
        load_update_status=lambda: {"isRunning": True},
        start_update=lambda _items: None,
        run_background_update=lambda *_args: None,
        logger=types.SimpleNamespace(info=lambda *_args, **_kwargs: None),
    )
    assert status_code == 409
    assert payload["message"] == "Update already in progress"


def test_launch_init_data_update_maps_type_and_validates():
    called = {}

    def _start_update(items):
        called["items"] = items

    status_code, payload = launch_init_data_update(
        data_type="prices",
        target_date="2026-02-21",
        load_update_status=lambda: {"isRunning": False},
        start_update=_start_update,
        run_background_update=lambda *_args: None,
        logger=types.SimpleNamespace(info=lambda *_args, **_kwargs: None),
    )
    assert status_code == 200
    assert payload["type"] == "prices"
    assert called["items"] == ["Daily Prices"]

    status_code, payload = launch_init_data_update(
        data_type="unknown",
        target_date=None,
        load_update_status=lambda: {"isRunning": False},
        start_update=lambda _items: None,
        run_background_update=lambda *_args: None,
        logger=types.SimpleNamespace(info=lambda *_args, **_kwargs: None),
    )
    assert status_code == 400
    assert payload["status"] == "error"


def test_execute_market_gate_update_runs_init_and_market_gate(monkeypatch):
    calls = {"init": 0, "analyze": 0, "save": 0}

    fake_scripts = types.ModuleType("scripts")
    fake_scripts.init_data = types.SimpleNamespace(
        create_institutional_trend=lambda **_kwargs: calls.__setitem__("init", calls["init"] + 1)
    )
    monkeypatch.setitem(sys.modules, "scripts", fake_scripts)

    class _DummyMarketGate:
        def analyze(self, target_date=None):
            calls["analyze"] += 1
            return {"target_date": target_date, "score": 55}

        def save_analysis(self, result, target_date=None):
            calls["save"] += 1
            assert result["target_date"] == target_date
            return "data/market_gate.json"

    fake_market_gate_module = types.ModuleType("engine.market_gate")
    fake_market_gate_module.MarketGate = _DummyMarketGate
    monkeypatch.setitem(sys.modules, "engine.market_gate", fake_market_gate_module)

    logger = types.SimpleNamespace(
        info=lambda *_args, **_kwargs: None,
        error=lambda *_args, **_kwargs: None,
    )
    status_code, payload = execute_market_gate_update(
        target_date="2026-02-21",
        logger=logger,
    )

    assert status_code == 200
    assert payload["status"] == "success"
    assert payload["data"]["score"] == 55
    assert calls == {"init": 1, "analyze": 1, "save": 1}
