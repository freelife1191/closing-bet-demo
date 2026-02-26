#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SignalTracker 로그 헬퍼 리팩토링 테스트
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from engine.signal_tracker_log_helpers import append_signals_log, update_open_signals_frame


def test_append_signals_log_replaces_same_day_same_ticker(tmp_path):
    today = "2026-02-21"
    log_path = tmp_path / "signals_log.csv"

    existing = pd.DataFrame(
        [
            {"signal_date": today, "ticker": "000001", "status": "OPEN"},
            {"signal_date": "2026-02-20", "ticker": "000002", "status": "CLOSED"},
        ]
    )
    existing.to_csv(log_path, index=False, encoding="utf-8-sig")

    new_signals = pd.DataFrame(
        [
            {"signal_date": today, "ticker": "1", "status": "OPEN"},
            {"signal_date": today, "ticker": "3", "status": "OPEN"},
        ]
    )

    combined = append_signals_log(
        signals_log_path=str(log_path),
        new_signals=new_signals,
        today=today,
    )

    today_rows = combined[combined["signal_date"] == today]
    assert len(today_rows) == 2
    assert set(today_rows["ticker"]) == {"000001", "000003"}


def test_append_signals_log_reads_with_ticker_dtype_and_low_memory_disabled(tmp_path, monkeypatch):
    today = "2026-02-21"
    log_path = tmp_path / "signals_log.csv"
    log_path.write_text("dummy\n", encoding="utf-8-sig")
    captured: dict[str, object] = {}

    def _fake_read_csv(path, *args, **kwargs):
        captured["path"] = str(path)
        captured["dtype"] = kwargs.get("dtype")
        captured["low_memory"] = kwargs.get("low_memory")
        return pd.DataFrame([{"signal_date": "2026-02-20", "ticker": "000002", "status": "CLOSED"}])

    monkeypatch.setattr("engine.signal_tracker_log_helpers._shared_file_signature", lambda _path: None)
    monkeypatch.setattr("engine.signal_tracker_log_helpers.pd.read_csv", _fake_read_csv)

    append_signals_log(
        signals_log_path=str(log_path),
        new_signals=pd.DataFrame([{"signal_date": today, "ticker": "1", "status": "OPEN"}]),
        today=today,
    )

    assert str(captured.get("path", "")).endswith("signals_log.csv")
    assert captured.get("dtype") == {"ticker": str}
    assert captured.get("low_memory") is False


def test_append_signals_log_uses_shared_loader_before_read_csv(tmp_path, monkeypatch):
    today = "2026-02-21"
    log_path = tmp_path / "signals_log.csv"
    log_path.write_text("dummy\n", encoding="utf-8-sig")
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "engine.signal_tracker_log_helpers._shared_file_signature",
        lambda _path: (1, 1),
    )

    def _fake_shared_loader(data_dir, filename, *, deep_copy=True, signature=None):
        captured["data_dir"] = str(data_dir)
        captured["filename"] = filename
        captured["deep_copy"] = deep_copy
        captured["signature"] = signature
        return pd.DataFrame([{"signal_date": "2026-02-20", "ticker": "2", "status": "CLOSED"}])

    monkeypatch.setattr(
        "engine.signal_tracker_log_helpers._load_shared_csv_file",
        _fake_shared_loader,
    )
    monkeypatch.setattr(
        "engine.signal_tracker_log_helpers.pd.read_csv",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("read_csv should not run")),
    )

    combined = append_signals_log(
        signals_log_path=str(log_path),
        new_signals=pd.DataFrame([{"signal_date": today, "ticker": "1", "status": "OPEN"}]),
        today=today,
    )

    assert len(combined) == 2
    assert captured["filename"] == "signals_log.csv"
    assert captured["deep_copy"] is False
    assert captured["signature"] == (1, 1)


def test_append_signals_log_uses_signal_tracker_sqlite_cache_before_read_csv(tmp_path, monkeypatch):
    today = "2026-02-21"
    log_path = tmp_path / "signals_log.csv"
    log_path.write_text("dummy\n", encoding="utf-8-sig")
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "engine.signal_tracker_log_helpers._shared_file_signature",
        lambda _path: (1, 1),
    )
    monkeypatch.setattr(
        "engine.signal_tracker_log_helpers._load_shared_csv_file",
        lambda *_a, **_k: (_ for _ in ()).throw(ValueError("force shared loader fallback")),
    )

    def _fake_source_cache_loader(
        *,
        path: str,
        cache_kind: str,
        dtype=None,
        read_csv=None,
        logger=None,
        low_memory=False,
        deep_copy=True,
        **_kwargs,
    ):
        captured["path"] = path
        captured["cache_kind"] = cache_kind
        captured["dtype"] = dtype
        captured["low_memory"] = low_memory
        captured["deep_copy"] = deep_copy
        return pd.DataFrame([{"signal_date": "2026-02-20", "ticker": "2", "status": "CLOSED"}])

    monkeypatch.setattr(
        "engine.signal_tracker_log_helpers._load_signal_tracker_csv_cached",
        _fake_source_cache_loader,
    )
    monkeypatch.setattr(
        "engine.signal_tracker_log_helpers.pd.read_csv",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("read_csv should not run")),
    )

    combined = append_signals_log(
        signals_log_path=str(log_path),
        new_signals=pd.DataFrame([{"signal_date": today, "ticker": "1", "status": "OPEN"}]),
        today=today,
    )

    assert len(combined) == 2
    assert str(captured.get("path", "")).endswith("signals_log.csv")
    assert captured.get("cache_kind") == "signal_tracker_log_helpers:signals_log"
    assert captured.get("dtype") == {"ticker": str}
    assert captured.get("low_memory") is False
    assert captured.get("deep_copy") is False


def test_append_signals_log_uses_existing_signals_without_read_csv(monkeypatch):
    today = "2026-02-21"
    monkeypatch.setattr(
        "engine.signal_tracker_log_helpers.pd.read_csv",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("read_csv should not run")),
    )

    existing = pd.DataFrame(
        [
            {"signal_date": "2026-02-20", "ticker": "000002", "status": "CLOSED"},
        ]
    )
    new_signals = pd.DataFrame(
        [
            {"signal_date": today, "ticker": "1", "status": "OPEN"},
        ]
    )

    combined = append_signals_log(
        signals_log_path="/tmp/not-used.csv",
        new_signals=new_signals,
        today=today,
        existing_signals=existing,
    )

    assert len(combined) == 2
    assert set(combined["ticker"]) == {"000001", "000002"}


def test_update_open_signals_frame_vectorized_close_and_keep():
    now = datetime.now()
    old_date = (now - timedelta(days=10)).strftime("%Y-%m-%d")
    recent_date = (now - timedelta(days=1)).strftime("%Y-%m-%d")

    df = pd.DataFrame(
        [
            {"ticker": "1", "status": "OPEN", "entry_price": 100, "signal_date": old_date, "hold_days": 0},
            {"ticker": "2", "status": "OPEN", "entry_price": 100, "signal_date": old_date, "hold_days": 0},
            {"ticker": "3", "status": "OPEN", "entry_price": 100, "signal_date": recent_date, "hold_days": 0},
            {"ticker": "4", "status": "OPEN", "entry_price": 100, "signal_date": recent_date, "hold_days": 0},
        ]
    )

    updated, closed_logs = update_open_signals_frame(
        df=df,
        latest_price_map={
            "000001": 90.0,
            "000002": 105.0,
            "000003": 102.0,
        },
        stop_loss_pct=7.0,
        hold_days_limit=5,
        now=now,
    )

    row1 = updated[updated["ticker"] == "000001"].iloc[0]
    assert row1["status"] == "CLOSED"
    assert float(row1["return_pct"]) == -10.0

    row2 = updated[updated["ticker"] == "000002"].iloc[0]
    assert row2["status"] == "CLOSED"
    assert float(row2["return_pct"]) == 5.0
    assert int(row2["hold_days"]) >= 10

    row3 = updated[updated["ticker"] == "000003"].iloc[0]
    assert row3["status"] == "OPEN"
    assert float(row3["return_pct"]) == 2.0

    row4 = updated[updated["ticker"] == "000004"].iloc[0]
    assert row4["status"] == "OPEN"
    assert pd.isna(row4.get("return_pct"))

    assert len(closed_logs) == 2
    assert set(closed_logs["close_reason"]) == {"STOP_LOSS", "TIME_EXIT"}


def test_update_open_signals_frame_normalizes_unpadded_price_map_keys():
    now = datetime.now()
    signal_date = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    df = pd.DataFrame(
        [
            {"ticker": "1", "status": "OPEN", "entry_price": 100, "signal_date": signal_date, "hold_days": 0},
        ]
    )

    updated, closed_logs = update_open_signals_frame(
        df=df,
        latest_price_map={"1": 110.0},
        stop_loss_pct=7.0,
        hold_days_limit=5,
        now=now,
    )

    row = updated.iloc[0]
    assert row["ticker"] == "000001"
    assert float(row["return_pct"]) == 10.0
    assert closed_logs.empty
