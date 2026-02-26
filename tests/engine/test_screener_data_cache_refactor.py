#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Screener 데이터 로드 캐시(파일 mtime) 회귀 테스트
"""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd

import engine.screener as screener_mod


def _build_minimal_screener_instance():
    inst = object.__new__(screener_mod.SmartMoneyScreener)
    inst.stocks_df = None
    inst.prices_df = None
    inst.inst_df = None
    inst._prices_by_ticker = {}
    inst._prices_by_ticker_target = {}
    inst._inst_by_ticker = {}
    inst._data_mtimes = {}
    inst._target_datetime = None
    return inst


def test_load_data_uses_mtime_cache_to_skip_reloading(monkeypatch, tmp_path: Path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    for name in ("korean_stocks_list.csv", "daily_prices.csv", "all_institutional_trend_data.csv"):
        (data_dir / name).write_text("dummy\n", encoding="utf-8")

    monkeypatch.setattr(screener_mod, "BASE_DIR", str(tmp_path))

    calls = {"count": 0}

    def _fake_read_csv(path, *args, **kwargs):
        del args, kwargs
        calls["count"] += 1
        path = str(path)
        if path.endswith("korean_stocks_list.csv"):
            return pd.DataFrame([{"ticker": "5930", "name": "삼성전자", "market": "KOSPI"}])
        if path.endswith("daily_prices.csv"):
            return pd.DataFrame([{"ticker": "5930", "date": "2026-02-21", "close": 100, "volume": 1000}])
        return pd.DataFrame([{"ticker": "5930", "date": "2026-02-21", "foreign_buy": 1, "inst_buy": 1}])

    monkeypatch.setattr(screener_mod.pd, "read_csv", _fake_read_csv)

    screener = _build_minimal_screener_instance()
    screener_mod.SmartMoneyScreener._load_data(screener)
    screener_mod.SmartMoneyScreener._load_data(screener)

    assert calls["count"] == 3


def test_load_data_reloads_when_file_mtime_changes(monkeypatch, tmp_path: Path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    stocks_file = data_dir / "korean_stocks_list.csv"
    prices_file = data_dir / "daily_prices.csv"
    inst_file = data_dir / "all_institutional_trend_data.csv"
    for file in (stocks_file, prices_file, inst_file):
        file.write_text("dummy\n", encoding="utf-8")

    monkeypatch.setattr(screener_mod, "BASE_DIR", str(tmp_path))

    calls = {"count": 0}

    def _fake_read_csv(path, *args, **kwargs):
        del args, kwargs
        calls["count"] += 1
        path = str(path)
        if path.endswith("korean_stocks_list.csv"):
            return pd.DataFrame([{"ticker": "5930", "name": "삼성전자", "market": "KOSPI"}])
        if path.endswith("daily_prices.csv"):
            return pd.DataFrame([{"ticker": "5930", "date": "2026-02-21", "close": 100, "volume": 1000}])
        return pd.DataFrame([{"ticker": "5930", "date": "2026-02-21", "foreign_buy": 1, "inst_buy": 1}])

    monkeypatch.setattr(screener_mod.pd, "read_csv", _fake_read_csv)

    screener = _build_minimal_screener_instance()
    screener_mod.SmartMoneyScreener._load_data(screener)

    before = calls["count"]
    time.sleep(0.01)
    prices_file.write_text("dummy2\n", encoding="utf-8")
    screener_mod.SmartMoneyScreener._load_data(screener)

    # 파일 시그니처 기반 소스 캐시(SQLite/메모리)로 변경되어
    # 변경된 파일만 실제 재로드된다.
    assert calls["count"] == before + 1


def test_load_data_builds_target_date_price_index_once(monkeypatch, tmp_path: Path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    for name in ("korean_stocks_list.csv", "daily_prices.csv", "all_institutional_trend_data.csv"):
        (data_dir / name).write_text("dummy\n", encoding="utf-8")

    monkeypatch.setattr(screener_mod, "BASE_DIR", str(tmp_path))

    def _fake_read_csv(path, *args, **kwargs):
        del args, kwargs
        path = str(path)
        if path.endswith("korean_stocks_list.csv"):
            return pd.DataFrame([{"ticker": "5930", "name": "삼성전자", "market": "KOSPI"}])
        if path.endswith("daily_prices.csv"):
            return pd.DataFrame(
                [
                    {"ticker": "5930", "date": "2026-02-20", "close": 99, "volume": 1000},
                    {"ticker": "5930", "date": "2026-02-21", "close": 100, "volume": 1100},
                    {"ticker": "5930", "date": "2026-02-22", "close": 101, "volume": 1200},
                ]
            )
        return pd.DataFrame([{"ticker": "5930", "date": "2026-02-21", "foreign_buy": 1, "inst_buy": 1}])

    monkeypatch.setattr(screener_mod.pd, "read_csv", _fake_read_csv)

    screener = _build_minimal_screener_instance()
    screener._target_datetime = pd.Timestamp("2026-02-21")
    screener_mod.SmartMoneyScreener._load_data(screener)

    assert "005930" in screener._prices_by_ticker_target
    target_prices = screener._prices_by_ticker_target["005930"]
    assert len(target_prices) == 2
    assert str(target_prices["date"].max().date()) == "2026-02-21"


def test_load_data_skips_reload_when_inst_file_missing_and_mtime_unchanged(monkeypatch, tmp_path: Path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "korean_stocks_list.csv").write_text("dummy\n", encoding="utf-8")
    (data_dir / "daily_prices.csv").write_text("dummy\n", encoding="utf-8")

    monkeypatch.setattr(screener_mod, "BASE_DIR", str(tmp_path))

    calls = {"count": 0}

    def _fake_read_csv(path, *args, **kwargs):
        del args, kwargs
        calls["count"] += 1
        path = str(path)
        if path.endswith("korean_stocks_list.csv"):
            return pd.DataFrame([{"ticker": "5930", "name": "삼성전자", "market": "KOSPI"}])
        return pd.DataFrame([{"ticker": "5930", "date": "2026-02-21", "close": 100, "volume": 1000}])

    monkeypatch.setattr(screener_mod.pd, "read_csv", _fake_read_csv)

    screener = _build_minimal_screener_instance()
    screener_mod.SmartMoneyScreener._load_data(screener)
    screener_mod.SmartMoneyScreener._load_data(screener)

    assert calls["count"] == 2


def test_load_data_uses_minimum_columns_per_file(monkeypatch, tmp_path: Path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    for name in ("korean_stocks_list.csv", "daily_prices.csv", "all_institutional_trend_data.csv"):
        (data_dir / name).write_text("dummy\n", encoding="utf-8")

    monkeypatch.setattr(screener_mod, "BASE_DIR", str(tmp_path))
    captured: dict[str, object] = {}

    def _fake_read_csv(path, *args, **kwargs):
        path_text = str(path)
        captured[path_text] = kwargs.get("usecols")
        if path_text.endswith("korean_stocks_list.csv"):
            return pd.DataFrame([{"ticker": "5930", "name": "삼성전자", "market": "KOSPI"}])
        if path_text.endswith("daily_prices.csv"):
            return pd.DataFrame(
                [{"ticker": "5930", "date": "2026-02-21", "close": 100, "volume": 1000}]
            )
        return pd.DataFrame([{"ticker": "5930", "date": "2026-02-21", "foreign_buy": 1, "inst_buy": 1}])

    monkeypatch.setattr(screener_mod.pd, "read_csv", _fake_read_csv)

    screener = _build_minimal_screener_instance()
    screener_mod.SmartMoneyScreener._load_data(screener)

    stocks_path = str(data_dir / "korean_stocks_list.csv")
    prices_path = str(data_dir / "daily_prices.csv")
    inst_path = str(data_dir / "all_institutional_trend_data.csv")
    assert captured[stocks_path] == ["ticker", "name", "market"]
    assert captured[prices_path] == ["ticker", "date", "open", "high", "low", "close", "volume", "current_price"]
    assert captured[inst_path] == ["ticker", "date", "foreign_buy", "inst_buy"]


def test_load_data_falls_back_to_full_read_when_usecols_mismatch(monkeypatch, tmp_path: Path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    for name in ("korean_stocks_list.csv", "daily_prices.csv", "all_institutional_trend_data.csv"):
        (data_dir / name).write_text("dummy\n", encoding="utf-8")

    monkeypatch.setattr(screener_mod, "BASE_DIR", str(tmp_path))
    calls: dict[str, list[object]] = {}

    def _fake_read_csv(path, *args, **kwargs):
        path_text = str(path)
        calls.setdefault(path_text, []).append(kwargs.get("usecols"))
        if kwargs.get("usecols") is not None:
            raise ValueError("Usecols do not match columns")
        if path_text.endswith("korean_stocks_list.csv"):
            return pd.DataFrame([{"ticker": "5930", "name": "삼성전자", "market": "KOSPI"}])
        if path_text.endswith("daily_prices.csv"):
            return pd.DataFrame([{"ticker": "5930", "date": "2026-02-21", "close": 100, "volume": 1000}])
        return pd.DataFrame([{"ticker": "5930", "date": "2026-02-21", "foreign_buy": 1, "inst_buy": 1}])

    monkeypatch.setattr(screener_mod.pd, "read_csv", _fake_read_csv)

    screener = _build_minimal_screener_instance()
    screener_mod.SmartMoneyScreener._load_data(screener)

    stocks_path = str(data_dir / "korean_stocks_list.csv")
    prices_path = str(data_dir / "daily_prices.csv")
    inst_path = str(data_dir / "all_institutional_trend_data.csv")
    assert calls[stocks_path] == [
        ["ticker", "name", "market"],
        ["ticker", "name", "market"],
        None,
    ]
    assert calls[prices_path] == [
        ["ticker", "date", "open", "high", "low", "close", "volume", "current_price"],
        ["ticker", "date", "open", "high", "low", "close", "volume"],
        ["ticker", "date", "open", "high", "low", "close", "volume"],
        None,
    ]
    assert calls[inst_path] == [
        ["ticker", "date", "foreign_buy", "inst_buy"],
        ["ticker", "date", "foreign_buy", "inst_buy"],
        None,
    ]


def test_load_data_retries_prices_with_required_columns_when_optional_missing(monkeypatch, tmp_path: Path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    for name in ("korean_stocks_list.csv", "daily_prices.csv", "all_institutional_trend_data.csv"):
        (data_dir / name).write_text("dummy\n", encoding="utf-8")

    monkeypatch.setattr(screener_mod, "BASE_DIR", str(tmp_path))
    calls: dict[str, list[object]] = {}

    def _fake_read_csv(path, *args, **kwargs):
        path_text = str(path)
        usecols = kwargs.get("usecols")
        calls.setdefault(path_text, []).append(usecols)
        if path_text.endswith("korean_stocks_list.csv"):
            return pd.DataFrame([{"ticker": "5930", "name": "삼성전자", "market": "KOSPI"}])
        if path_text.endswith("daily_prices.csv"):
            if usecols and "current_price" in usecols:
                raise ValueError("current_price missing")
            return pd.DataFrame([{"ticker": "5930", "date": "2026-02-21", "close": 100, "volume": 1000}])
        return pd.DataFrame([{"ticker": "5930", "date": "2026-02-21", "foreign_buy": 1, "inst_buy": 1}])

    monkeypatch.setattr(screener_mod.pd, "read_csv", _fake_read_csv)

    screener = _build_minimal_screener_instance()
    screener_mod.SmartMoneyScreener._load_data(screener)

    prices_path = str(data_dir / "daily_prices.csv")
    assert calls[prices_path] == [
        ["ticker", "date", "open", "high", "low", "close", "volume", "current_price"],
        ["ticker", "date", "open", "high", "low", "close", "volume"],
    ]
