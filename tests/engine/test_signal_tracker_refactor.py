#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SignalTracker 리팩토링 회귀 테스트
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta

import pandas as pd
import pytest

from engine.signal_tracker import SignalTracker
import engine.signal_tracker as signal_tracker_module
import engine.signal_tracker_analysis_mixin as signal_tracker_analysis_mixin
import engine.signal_tracker_source_cache as signal_tracker_source_cache


@pytest.fixture(autouse=True)
def _reset_signal_tracker_source_cache():
    signal_tracker_source_cache.clear_signal_tracker_source_cache(reset_sqlite_state=True)
    yield
    signal_tracker_source_cache.clear_signal_tracker_source_cache(reset_sqlite_state=True)


def _build_price_frame() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    base_date = datetime(2026, 2, 1)

    for i in range(20):
        dt = (base_date + timedelta(days=i)).strftime("%Y-%m-%d")
        if i < 10:
            low = 90
            high = 110
            close = 100 + (i % 2)
        else:
            low = 98
            high = 102
            close = 101 if i % 2 == 0 else 100

        rows.append(
            {
                "ticker": "000001",
                "date": dt,
                "open": close,
                "high": high,
                "low": low,
                "close": close,
                "volume": 100_000,
            }
        )

    # 비대상 티커 1개 추가
    for i in range(5):
        dt = (base_date + timedelta(days=i)).strftime("%Y-%m-%d")
        rows.append(
            {
                "ticker": "000002",
                "date": dt,
                "open": 50,
                "high": 52,
                "low": 48,
                "close": 50,
                "volume": 50_000,
            }
        )

    return pd.DataFrame(rows)


def test_detect_vcp_forming_uses_indexed_price_data(tmp_path):
    price_df = _build_price_frame()
    price_df.to_csv(tmp_path / "daily_prices.csv", index=False, encoding="utf-8-sig")

    tracker = SignalTracker(data_dir=str(tmp_path))
    is_vcp, info = tracker.detect_vcp_forming("1")

    assert is_vcp is True
    assert info["contraction_ratio"] <= 0.8
    assert info["near_high"] is True
    assert info["recent_high"] > 0


def test_scan_today_signals_builds_signal_and_applies_name_map(tmp_path):
    price_df = _build_price_frame()
    price_df.to_csv(tmp_path / "daily_prices.csv", index=False, encoding="utf-8-sig")

    inst_rows = []
    for i in range(5):
        inst_rows.append(
            {
                "ticker": "000001",
                "date": f"2026-02-1{i+1}",
                "foreign_buy": 400_000_000,
                "inst_buy": 300_000_000,
            }
        )
    pd.DataFrame(inst_rows).to_csv(
        tmp_path / "all_institutional_trend_data.csv",
        index=False,
        encoding="utf-8-sig",
    )

    pd.DataFrame(
        [{"ticker": "000001", "name": "테스트주", "market": "KOSPI"}]
    ).to_csv(tmp_path / "korean_stocks_list.csv", index=False, encoding="utf-8-sig")

    tracker = SignalTracker(data_dir=str(tmp_path))
    signals_df = tracker.scan_today_signals()

    assert len(signals_df) == 1
    signal = signals_df.iloc[0]
    assert signal["ticker"] == "000001"
    assert signal["name"] == "테스트주"
    assert signal["score"] >= 40
    assert signal["vcp_score"] > 0
    assert (tmp_path / "signals_log.csv").exists()


def test_update_open_signals_uses_latest_price_cache_for_exit(tmp_path):
    price_rows = [
        {
            "ticker": "000001",
            "date": "2026-02-20",
            "close": 110,
            "high": 111,
            "low": 109,
            "volume": 10_000,
        }
    ]
    pd.DataFrame(price_rows).to_csv(tmp_path / "daily_prices.csv", index=False, encoding="utf-8-sig")

    old_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
    signals_log = pd.DataFrame(
        [
            {
                "signal_date": old_date,
                "ticker": "000001",
                "name": "테스트주",
                "foreign_5d": 1,
                "inst_5d": 1,
                "score": 70,
                "contraction_ratio": 0.5,
                "entry_price": 100,
                "current_price": 100,
                "status": "OPEN",
                "exit_price": "",
                "exit_date": "",
                "return_pct": "",
                "hold_days": 0,
                "vcp_score": 10,
            }
        ]
    )
    signals_log.to_csv(tmp_path / "signals_log.csv", index=False, encoding="utf-8-sig")

    tracker = SignalTracker(data_dir=str(tmp_path))
    tracker.update_open_signals()

    updated = pd.read_csv(tmp_path / "signals_log.csv", dtype={"ticker": str})
    row = updated.iloc[0]
    assert row["status"] == "CLOSED"
    assert int(row["exit_price"]) == 110
    assert float(row["return_pct"]) == 10.0


def test_scan_today_signals_loads_minimum_supply_columns(tmp_path, monkeypatch):
    price_df = _build_price_frame()
    price_df.to_csv(tmp_path / "daily_prices.csv", index=False, encoding="utf-8-sig")
    (tmp_path / "all_institutional_trend_data.csv").write_text("dummy\n", encoding="utf-8-sig")
    pd.DataFrame(
        [{"ticker": "000001", "name": "테스트주", "market": "KOSPI"}]
    ).to_csv(tmp_path / "korean_stocks_list.csv", index=False, encoding="utf-8-sig")

    tracker = SignalTracker(data_dir=str(tmp_path))
    captured: dict[str, object] = {}

    def _fake_read_csv(path, *args, **kwargs):
        captured["path"] = str(path)
        captured["usecols"] = kwargs.get("usecols")
        captured["low_memory"] = kwargs.get("low_memory")
        return pd.DataFrame(
            [
                {"ticker": "000001", "date": "2026-02-20", "foreign_buy": 1, "inst_buy": 1},
                {"ticker": "000001", "date": "2026-02-21", "foreign_buy": 1, "inst_buy": 1},
                {"ticker": "000001", "date": "2026-02-22", "foreign_buy": 1, "inst_buy": 1},
                {"ticker": "000001", "date": "2026-02-23", "foreign_buy": 1, "inst_buy": 1},
                {"ticker": "000001", "date": "2026-02-24", "foreign_buy": 1, "inst_buy": 1},
            ]
        )

    monkeypatch.setattr(signal_tracker_analysis_mixin.pd, "read_csv", _fake_read_csv)
    monkeypatch.setattr(tracker, "detect_vcp_forming", lambda _ticker: (False, {}))

    tracker.scan_today_signals()

    assert str(captured.get("path", "")).endswith("all_institutional_trend_data.csv")
    assert callable(captured.get("usecols"))
    assert captured.get("low_memory") is False


def test_scan_today_signals_uses_sqlite_supply_cache_after_memory_clear(tmp_path, monkeypatch):
    price_df = _build_price_frame()
    price_df.to_csv(tmp_path / "daily_prices.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(
        [
            {"ticker": "000001", "date": "2026-02-20", "foreign_buy": 1, "inst_buy": 1},
            {"ticker": "000001", "date": "2026-02-21", "foreign_buy": 1, "inst_buy": 1},
            {"ticker": "000001", "date": "2026-02-22", "foreign_buy": 1, "inst_buy": 1},
            {"ticker": "000001", "date": "2026-02-23", "foreign_buy": 1, "inst_buy": 1},
            {"ticker": "000001", "date": "2026-02-24", "foreign_buy": 1, "inst_buy": 1},
        ]
    ).to_csv(tmp_path / "all_institutional_trend_data.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(
        [{"ticker": "000001", "name": "테스트주", "market": "KOSPI"}]
    ).to_csv(tmp_path / "korean_stocks_list.csv", index=False, encoding="utf-8-sig")

    tracker = SignalTracker(data_dir=str(tmp_path))
    monkeypatch.setattr(tracker, "detect_vcp_forming", lambda _ticker: (False, {}))

    first = tracker.scan_today_signals()
    assert first.empty

    signal_tracker_analysis_mixin._SUPPLY_SOURCE_CACHE.clear()
    monkeypatch.setattr(
        signal_tracker_analysis_mixin.pd,
        "read_csv",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("read_csv should not run")),
    )
    second = tracker.scan_today_signals()
    assert second.empty


def test_signal_tracker_loads_minimum_price_columns(tmp_path, monkeypatch):
    (tmp_path / "daily_prices.csv").write_text("dummy\n", encoding="utf-8-sig")
    captured: dict[str, object] = {}

    def _fake_read_csv(path, *args, **kwargs):
        captured["path"] = str(path)
        captured["usecols"] = kwargs.get("usecols")
        return pd.DataFrame(
            [
                {
                    "ticker": "000001",
                    "date": "2026-02-20",
                    "close": 100,
                    "current_price": 101,
                    "high": 102,
                    "low": 99,
                    "volume": 1000,
                },
            ]
        )

    monkeypatch.setattr(signal_tracker_module.pd, "read_csv", _fake_read_csv)

    SignalTracker(data_dir=str(tmp_path))

    assert str(captured.get("path", "")).endswith("daily_prices.csv")
    assert captured.get("usecols") == [
        "ticker",
        "date",
        "close",
        "current_price",
        "high",
        "low",
        "volume",
    ]


def test_signal_tracker_loads_minimum_stock_map_columns(tmp_path, monkeypatch):
    (tmp_path / "daily_prices.csv").write_text("dummy\n", encoding="utf-8-sig")
    (tmp_path / "korean_stocks_list.csv").write_text("dummy\n", encoding="utf-8-sig")
    captured: dict[str, object] = {}

    def _fake_read_csv(path, *args, **kwargs):
        path_text = str(path)
        if path_text.endswith("daily_prices.csv"):
            return pd.DataFrame(
                [
                    {
                        "ticker": "000001",
                        "date": "2026-02-20",
                        "close": 100,
                        "current_price": 101,
                        "high": 102,
                        "low": 99,
                        "volume": 1000,
                    },
                ]
            )

        captured["path"] = path_text
        captured["usecols"] = kwargs.get("usecols")
        return pd.DataFrame([{"ticker": "000001", "name": "테스트주"}])

    monkeypatch.setattr(signal_tracker_module.pd, "read_csv", _fake_read_csv)

    tracker = SignalTracker(data_dir=str(tmp_path))

    assert tracker._stock_name_map["000001"] == "테스트주"
    assert str(captured.get("path", "")).endswith("korean_stocks_list.csv")
    assert captured.get("usecols") == ["ticker", "name"]


def test_signal_tracker_price_source_uses_sqlite_snapshot_after_memory_clear(tmp_path, monkeypatch):
    price_df = _build_price_frame()
    price_df.to_csv(tmp_path / "daily_prices.csv", index=False, encoding="utf-8-sig")

    tracker = SignalTracker(data_dir=str(tmp_path))
    assert not tracker.price_df.empty

    signal_tracker_source_cache.clear_signal_tracker_source_cache()

    monkeypatch.setattr(
        signal_tracker_module.pd,
        "read_csv",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("read_csv should not be called")),
    )

    tracker_reloaded = SignalTracker(data_dir=str(tmp_path))
    assert len(tracker_reloaded.price_df) == len(tracker.price_df)


def test_signal_tracker_stock_map_uses_sqlite_snapshot_after_memory_clear(tmp_path, monkeypatch):
    price_df = _build_price_frame()
    price_df.to_csv(tmp_path / "daily_prices.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(
        [{"ticker": "000001", "name": "테스트주", "market": "KOSPI"}]
    ).to_csv(tmp_path / "korean_stocks_list.csv", index=False, encoding="utf-8-sig")

    tracker = SignalTracker(data_dir=str(tmp_path))
    assert tracker._stock_name_map["000001"] == "테스트주"

    signal_tracker_source_cache.clear_signal_tracker_source_cache()

    monkeypatch.setattr(
        signal_tracker_module.pd,
        "read_csv",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("read_csv should not be called")),
    )

    tracker_reloaded = SignalTracker(data_dir=str(tmp_path))
    assert tracker_reloaded._stock_name_map["000001"] == "테스트주"


def test_get_performance_report_loads_minimum_columns(tmp_path, monkeypatch):
    signals_path = tmp_path / "signals_log.csv"
    signals_path.write_text("dummy\n", encoding="utf-8-sig")
    captured: dict[str, object] = {}

    def _fake_read_csv(path, *args, **kwargs):
        captured["path"] = str(path)
        captured["usecols"] = kwargs.get("usecols")
        captured["low_memory"] = kwargs.get("low_memory")
        return pd.DataFrame(
            [
                {
                    "status": "OPEN",
                    "return_pct": 0.0,
                    "signal_date": "2026-02-20",
                    "exit_date": "",
                    "hold_days": 1,
                }
            ]
        )

    monkeypatch.setattr(signal_tracker_analysis_mixin.pd, "read_csv", _fake_read_csv)

    tracker = object.__new__(SignalTracker)
    tracker.signals_log_path = str(signals_path)
    tracker.strategy_params = {"stop_loss_pct": 7.0}

    report = tracker.get_performance_report()

    assert report["message"] == "아직 청산된 시그널이 없습니다"
    assert str(captured.get("path", "")).endswith("signals_log.csv")
    assert callable(captured.get("usecols"))
    assert captured.get("low_memory") is False


def test_get_performance_report_handles_missing_columns_gracefully(tmp_path, monkeypatch):
    signals_path = tmp_path / "signals_log.csv"
    signals_path.write_text("dummy\n", encoding="utf-8-sig")

    def _fake_read_csv(_path, *args, **kwargs):
        del args, kwargs
        return pd.DataFrame([{"status": "OPEN"}])

    monkeypatch.setattr(signal_tracker_analysis_mixin.pd, "read_csv", _fake_read_csv)

    tracker = object.__new__(SignalTracker)
    tracker.signals_log_path = str(signals_path)
    tracker.strategy_params = {"stop_loss_pct": 7.0}

    report = tracker.get_performance_report()

    assert report["message"] == "아직 청산된 시그널이 없습니다"
    assert report["open_signals"] == 1


def test_update_open_signals_loads_log_with_ticker_dtype(tmp_path, monkeypatch):
    signals_path = tmp_path / "signals_log.csv"
    signals_path.write_text("dummy\n", encoding="utf-8-sig")
    captured: dict[str, object] = {}

    def _fake_read_csv(path, *args, **kwargs):
        captured["path"] = str(path)
        captured["dtype"] = kwargs.get("dtype")
        captured["low_memory"] = kwargs.get("low_memory")
        return pd.DataFrame(
            [
                {
                    "ticker": "000001",
                    "status": "OPEN",
                    "entry_price": 100,
                    "signal_date": "2026-02-20",
                    "hold_days": 0,
                }
            ]
        )

    tracker = object.__new__(SignalTracker)
    tracker.signals_log_path = str(signals_path)
    tracker.strategy_params = {"stop_loss_pct": 7.0, "hold_days": 5}
    tracker._latest_price_map = {"000001": 100.0}

    monkeypatch.setattr(signal_tracker_analysis_mixin.pd, "read_csv", _fake_read_csv)
    monkeypatch.setattr(
        pd.DataFrame,
        "to_csv",
        lambda self, path, *args, **kwargs: None,
    )

    tracker.update_open_signals()

    assert str(captured.get("path", "")).endswith("signals_log.csv")
    assert captured.get("dtype") == {"ticker": str}
    assert captured.get("low_memory") is False


def test_update_open_signals_uses_sqlite_cache_after_memory_clear(tmp_path, monkeypatch):
    signals_path = tmp_path / "signals_log.csv"
    pd.DataFrame(
        [
            {
                "ticker": "000001",
                "status": "CLOSED",
                "entry_price": 100,
                "signal_date": "2026-02-20",
                "hold_days": 0,
            }
        ]
    ).to_csv(signals_path, index=False, encoding="utf-8-sig")

    signal_tracker_analysis_mixin._SIGNALS_LOG_SOURCE_CACHE.clear()
    signal_tracker_analysis_mixin._CSV_SOURCE_SQLITE_READY.clear()

    tracker = object.__new__(SignalTracker)
    tracker.signals_log_path = str(signals_path)
    tracker.strategy_params = {"stop_loss_pct": 7.0, "hold_days": 5}
    tracker._latest_price_map = {}

    tracker.update_open_signals()

    signal_tracker_analysis_mixin._SIGNALS_LOG_SOURCE_CACHE.clear()
    monkeypatch.setattr(
        signal_tracker_analysis_mixin.pd,
        "read_csv",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("should use sqlite cache")),
    )

    tracker.update_open_signals()

    db_path = tmp_path / "runtime_cache.db"
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM signal_tracker_csv_source_cache
            WHERE cache_kind = ?
            """,
            ("signals_log_update",),
        )
        row = cursor.fetchone()
    assert row and row[0] >= 1


def test_append_to_log_uses_sqlite_cache_after_memory_clear(tmp_path, monkeypatch):
    pd.DataFrame(
        [
            {"ticker": "5930", "date": "2026-02-20", "close": 100, "high": 101, "low": 99, "volume": 1000},
        ]
    ).to_csv(tmp_path / "daily_prices.csv", index=False, encoding="utf-8-sig")

    log_path = tmp_path / "signals_log.csv"
    pd.DataFrame(
        [
            {"signal_date": "2026-02-20", "ticker": "000002", "status": "CLOSED"},
        ]
    ).to_csv(log_path, index=False, encoding="utf-8-sig")

    tracker = SignalTracker(data_dir=str(tmp_path))
    warmed = tracker._load_signals_log_source_frame(str(log_path))
    assert len(warmed) == 1

    signal_tracker_analysis_mixin._SIGNALS_LOG_SOURCE_CACHE.clear()
    original_read_csv = pd.read_csv
    monkeypatch.setattr(
        signal_tracker_analysis_mixin.pd,
        "read_csv",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("should use sqlite cache")),
    )

    tracker._append_to_log(
        pd.DataFrame(
            [
                {"signal_date": "2026-02-21", "ticker": "1", "status": "OPEN"},
            ]
        )
    )

    updated = original_read_csv(log_path, dtype={"ticker": str})
    assert set(updated["ticker"]) == {"000001", "000002"}


def test_append_to_log_uses_fast_append_when_no_same_day_overlap(tmp_path, monkeypatch):
    pd.DataFrame(
        [
            {"ticker": "5930", "date": "2026-02-20", "close": 100, "high": 101, "low": 99, "volume": 1000},
        ]
    ).to_csv(tmp_path / "daily_prices.csv", index=False, encoding="utf-8-sig")

    log_path = tmp_path / "signals_log.csv"
    pd.DataFrame(
        [
            {"signal_date": "2026-02-20", "ticker": "000002", "status": "CLOSED"},
        ]
    ).to_csv(log_path, index=False, encoding="utf-8-sig")

    tracker = SignalTracker(data_dir=str(tmp_path))
    today = datetime.now().strftime("%Y-%m-%d")

    monkeypatch.setattr(
        signal_tracker_analysis_mixin,
        "append_signals_log",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("fallback merge path should not run")),
    )

    capture = {"append_mode": False}
    original_to_csv = pd.DataFrame.to_csv

    def _capture_to_csv(self, path, *args, **kwargs):
        if str(path).endswith("signals_log.csv") and kwargs.get("mode") == "a":
            capture["append_mode"] = True
            assert kwargs.get("header") is False
        return original_to_csv(self, path, *args, **kwargs)

    monkeypatch.setattr(pd.DataFrame, "to_csv", _capture_to_csv)

    tracker._append_to_log(
        pd.DataFrame(
            [
                {"signal_date": today, "ticker": "1", "status": "OPEN"},
            ]
        )
    )

    updated = pd.read_csv(log_path, dtype={"ticker": str})
    assert set(updated["ticker"]) == {"000001", "000002"}
    assert capture["append_mode"] is True


def test_signal_tracker_rebuild_price_cache_uses_close_when_current_price_missing(tmp_path):
    pd.DataFrame(
        [
            {"ticker": "5930", "date": "2026-02-20", "close": 100, "high": 101, "low": 99, "volume": 1000},
            {"ticker": "005930", "date": "2026-02-21", "close": 110, "high": 111, "low": 109, "volume": 2000},
            {"ticker": "000660", "date": "2026-02-21", "close": 210, "high": 211, "low": 209, "volume": 3000},
        ]
    ).to_csv(tmp_path / "daily_prices.csv", index=False, encoding="utf-8-sig")

    tracker = SignalTracker(data_dir=str(tmp_path))

    assert tracker._default_price_col == "close"
    assert tracker._latest_price_map["005930"] == 110.0
    assert tracker._latest_price_map["000660"] == 210.0


def test_signal_tracker_rebuild_price_cache_skips_invalid_latest_price(tmp_path):
    pd.DataFrame(
        [
            {"ticker": "005930", "date": "2026-02-20", "close": 100, "current_price": "N/A", "high": 101, "low": 99, "volume": 1000},
            {"ticker": "005930", "date": "2026-02-21", "close": 110, "current_price": "bad", "high": 111, "low": 109, "volume": 2000},
            {"ticker": "000660", "date": "2026-02-21", "close": 210, "current_price": 215, "high": 211, "low": 209, "volume": 3000},
        ]
    ).to_csv(tmp_path / "daily_prices.csv", index=False, encoding="utf-8-sig")

    tracker = SignalTracker(data_dir=str(tmp_path))

    assert tracker._default_price_col == "current_price"
    assert "005930" not in tracker._latest_price_map
    assert tracker._latest_price_map["000660"] == 215.0


def test_load_performance_source_frame_uses_signature_cache(tmp_path, monkeypatch):
    signals_path = tmp_path / "signals_log.csv"
    signals_path.write_text("dummy\n", encoding="utf-8-sig")
    signal_tracker_analysis_mixin._PERFORMANCE_SOURCE_CACHE.clear()
    calls = {"count": 0}

    def _fake_read_csv(path, *args, **kwargs):
        calls["count"] += 1
        assert str(path).endswith("signals_log.csv")
        assert callable(kwargs.get("usecols"))
        return pd.DataFrame(
            [
                {
                    "status": "OPEN",
                    "return_pct": 0.0,
                    "signal_date": "2026-02-20",
                    "exit_date": "",
                    "hold_days": 1,
                }
            ]
        )

    monkeypatch.setattr(signal_tracker_analysis_mixin.pd, "read_csv", _fake_read_csv)

    first = SignalTracker._load_performance_source_frame(str(signals_path))
    second = SignalTracker._load_performance_source_frame(str(signals_path))

    assert len(first) == 1
    assert len(second) == 1
    assert calls["count"] == 1


def test_load_performance_source_frame_reuses_sqlite_cache_after_memory_clear(tmp_path, monkeypatch):
    signals_path = tmp_path / "signals_log.csv"
    signals_path.write_text("dummy\n", encoding="utf-8-sig")
    signal_tracker_analysis_mixin._PERFORMANCE_SOURCE_CACHE.clear()
    signal_tracker_analysis_mixin._CSV_SOURCE_SQLITE_READY.clear()

    monkeypatch.setattr(
        signal_tracker_analysis_mixin.pd,
        "read_csv",
        lambda path, *args, **kwargs: pd.DataFrame(
            [
                {
                    "status": "OPEN",
                    "return_pct": 0.0,
                    "signal_date": "2026-02-20",
                    "exit_date": "",
                    "hold_days": 1,
                }
            ]
        ),
    )

    first = SignalTracker._load_performance_source_frame(str(signals_path))
    assert len(first) == 1

    signal_tracker_analysis_mixin._PERFORMANCE_SOURCE_CACHE.clear()
    monkeypatch.setattr(
        signal_tracker_analysis_mixin.pd,
        "read_csv",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("should use sqlite cache")),
    )

    second = SignalTracker._load_performance_source_frame(str(signals_path))
    assert len(second) == 1

    db_path = tmp_path / "runtime_cache.db"
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM signal_tracker_csv_source_cache
            WHERE cache_kind = ?
            """,
            ("performance_source",),
        )
        row = cursor.fetchone()
    assert row and row[0] >= 1


def test_load_supply_source_frame_invalidates_signature_cache_on_file_change(tmp_path, monkeypatch):
    inst_path = tmp_path / "all_institutional_trend_data.csv"
    inst_path.write_text("dummy\n", encoding="utf-8-sig")
    signal_tracker_analysis_mixin._SUPPLY_SOURCE_CACHE.clear()
    calls = {"count": 0}

    def _fake_read_csv(path, *args, **kwargs):
        calls["count"] += 1
        assert str(path).endswith("all_institutional_trend_data.csv")
        assert callable(kwargs.get("usecols"))
        return pd.DataFrame(
            [
                {
                    "ticker": "000001",
                    "date": "2026-02-20",
                    "foreign_buy": 1,
                    "inst_buy": 1,
                }
            ]
        )

    monkeypatch.setattr(signal_tracker_analysis_mixin.pd, "read_csv", _fake_read_csv)

    first = SignalTracker._load_supply_source_frame(str(inst_path))
    second = SignalTracker._load_supply_source_frame(str(inst_path))
    assert len(first) == 1
    assert len(second) == 1
    assert calls["count"] == 1

    stat = inst_path.stat()
    updated_ns = stat.st_mtime_ns + 5_000_000
    os.utime(inst_path, ns=(updated_ns, updated_ns))

    third = SignalTracker._load_supply_source_frame(str(inst_path))
    assert len(third) == 1
    assert calls["count"] == 2
