#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market 라우트 파일 캐시 회귀 테스트
"""

import json
import os
import sys
from pathlib import Path

import pandas as pd


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from app.routes import kr_market


def _reset_route_file_cache() -> None:
    with kr_market._FILE_CACHE_LOCK:
        kr_market._JSON_FILE_CACHE.clear()
        kr_market._CSV_FILE_CACHE.clear()
        kr_market._LATEST_VCP_PRICE_MAP_CACHE["signature"] = None
        kr_market._LATEST_VCP_PRICE_MAP_CACHE["value"] = {}
        kr_market._SCANNED_STOCK_COUNT_CACHE["signature"] = None
        kr_market._SCANNED_STOCK_COUNT_CACHE["value"] = 0
        kr_market._BACKTEST_PRICE_SNAPSHOT_CACHE["signature"] = None
        kr_market._BACKTEST_PRICE_SNAPSHOT_CACHE["df"] = pd.DataFrame()
        kr_market._BACKTEST_PRICE_SNAPSHOT_CACHE["price_map"] = {}
        if hasattr(kr_market, "_JONGGA_RESULT_PAYLOADS_CACHE"):
            kr_market._JONGGA_RESULT_PAYLOADS_CACHE["signature"] = None
            kr_market._JONGGA_RESULT_PAYLOADS_CACHE["payloads"] = []


def test_load_json_file_returns_copy_and_refreshes_on_file_change(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(kr_market, "DATA_DIR", str(tmp_path))
    _reset_route_file_cache()

    file_path = tmp_path / "sample.json"
    file_path.write_text(
        json.dumps({"a": 1, "nested": {"x": 10}}, ensure_ascii=False),
        encoding="utf-8",
    )

    payload_1 = kr_market.load_json_file("sample.json")
    payload_1["nested"]["x"] = 999

    payload_2 = kr_market.load_json_file("sample.json")
    assert payload_2["nested"]["x"] == 10

    file_path.write_text(
        json.dumps({"a": 2, "nested": {"x": 20}}, ensure_ascii=False),
        encoding="utf-8",
    )
    payload_3 = kr_market.load_json_file("sample.json")
    assert payload_3["a"] == 2
    assert payload_3["nested"]["x"] == 20


def test_load_json_file_forwards_optional_kwargs_to_cache_service(monkeypatch):
    captured = {"data_dir": None, "filename": None, "kwargs": None}

    def _loader(data_dir: str, filename: str, **kwargs):
        captured["data_dir"] = data_dir
        captured["filename"] = filename
        captured["kwargs"] = dict(kwargs)
        return {"ok": True}

    monkeypatch.setattr(kr_market, "DATA_DIR", "/tmp/kr_market_file_cache")
    monkeypatch.setattr(kr_market, "load_json_file_service", _loader)

    payload = kr_market.load_json_file("sample.json", deep_copy=False)

    assert payload["ok"] is True
    assert captured["data_dir"] == "/tmp/kr_market_file_cache"
    assert captured["filename"] == "sample.json"
    assert captured["kwargs"]["deep_copy"] is False


def test_load_csv_file_returns_copy_and_refreshes_on_file_change(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(kr_market, "DATA_DIR", str(tmp_path))
    _reset_route_file_cache()

    csv_path = tmp_path / "sample.csv"
    pd.DataFrame([{"ticker": "000001", "close": 100.0}]).to_csv(csv_path, index=False)

    df_1 = kr_market.load_csv_file("sample.csv")
    df_1.loc[0, "close"] = 999.0

    df_2 = kr_market.load_csv_file("sample.csv")
    assert float(df_2.loc[0, "close"]) == 100.0

    pd.DataFrame([{"ticker": "000001", "close": 250.0}]).to_csv(csv_path, index=False)
    df_3 = kr_market.load_csv_file("sample.csv")
    assert float(df_3.loc[0, "close"]) == 250.0


def test_load_csv_file_caches_separately_by_usecols(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(kr_market, "DATA_DIR", str(tmp_path))
    _reset_route_file_cache()

    csv_path = tmp_path / "sample.csv"
    pd.DataFrame(
        [
            {"ticker": "000001", "close": 100.0, "volume": 10},
            {"ticker": "000002", "close": 200.0, "volume": 20},
        ]
    ).to_csv(csv_path, index=False)

    import services.kr_market_data_cache_core as cache_core

    original_read_csv = cache_core.pd.read_csv
    call_count = {"value": 0}

    def _counted_read_csv(*args, **kwargs):
        call_count["value"] += 1
        return original_read_csv(*args, **kwargs)

    monkeypatch.setattr(cache_core.pd, "read_csv", _counted_read_csv)

    df_ticker_1 = kr_market.load_csv_file("sample.csv", usecols=["ticker"])
    df_ticker_2 = kr_market.load_csv_file("sample.csv", usecols=["ticker"])
    df_close_1 = kr_market.load_csv_file("sample.csv", usecols=["close"])
    df_close_2 = kr_market.load_csv_file("sample.csv", usecols=["close"])

    assert call_count["value"] == 2
    assert list(df_ticker_1.columns) == ["ticker"]
    assert list(df_ticker_2.columns) == ["ticker"]
    assert list(df_close_1.columns) == ["close"]
    assert list(df_close_2.columns) == ["close"]


def test_load_latest_vcp_price_map_cache_updates_after_daily_prices_change(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(kr_market, "DATA_DIR", str(tmp_path))
    _reset_route_file_cache()

    daily_prices = tmp_path / "daily_prices.csv"
    pd.DataFrame(
        [
            {"date": "2026-02-20", "ticker": "005930", "close": 100.0},
            {"date": "2026-02-21", "ticker": "005930", "close": 110.0},
        ]
    ).to_csv(daily_prices, index=False)

    price_map_1 = kr_market._load_latest_vcp_price_map()
    price_map_1["005930"] = 999.0

    price_map_2 = kr_market._load_latest_vcp_price_map()
    assert price_map_2["005930"] == 110.0

    pd.DataFrame(
        [
            {"date": "2026-02-22", "ticker": "005930", "close": 123.0},
        ]
    ).to_csv(daily_prices, index=False)
    price_map_3 = kr_market._load_latest_vcp_price_map()
    assert price_map_3["005930"] == 123.0


def test_count_total_scanned_stocks_cache_updates_after_file_change(tmp_path: Path):
    _reset_route_file_cache()

    stocks_file = tmp_path / "korean_stocks_list.csv"
    stocks_file.write_text(
        "ticker,name\n005930,삼성전자\n000660,SK하이닉스\n",
        encoding="utf-8",
    )

    count_1 = kr_market._count_total_scanned_stocks(str(tmp_path))
    assert count_1 == 2

    stocks_file.write_text(
        "ticker,name\n005930,삼성전자\n000660,SK하이닉스\n035420,NAVER\n",
        encoding="utf-8",
    )

    count_2 = kr_market._count_total_scanned_stocks(str(tmp_path))
    assert count_2 == 3


def test_load_backtest_price_snapshot_cache_updates_after_daily_prices_change(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(kr_market, "DATA_DIR", str(tmp_path))
    _reset_route_file_cache()

    daily_prices = tmp_path / "daily_prices.csv"
    pd.DataFrame(
        [
            {"date": "2026-02-20", "ticker": "5930", "close": 100.0, "high": 101.0, "low": 99.0},
            {"date": "2026-02-21", "ticker": "5930", "close": 110.0, "high": 111.0, "low": 109.0},
        ]
    ).to_csv(daily_prices, index=False)

    df_1, price_map_1 = kr_market._load_backtest_price_snapshot()
    assert len(df_1) == 2
    assert price_map_1["005930"] == 110.0

    # copy isolation 확인
    df_1.loc[0, "close"] = 999.0

    df_2, price_map_2 = kr_market._load_backtest_price_snapshot()
    assert float(df_2.loc[0, "close"]) == 100.0
    assert price_map_2["005930"] == 110.0

    pd.DataFrame(
        [
            {"date": "2026-02-22", "ticker": "5930", "close": 123.0, "high": 125.0, "low": 120.0},
        ]
    ).to_csv(daily_prices, index=False)

    df_3, price_map_3 = kr_market._load_backtest_price_snapshot()
    assert len(df_3) == 1
    assert price_map_3["005930"] == 123.0


def test_load_jongga_result_payloads_cache_refreshes_when_result_file_changes(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(kr_market, "DATA_DIR", str(tmp_path))
    _reset_route_file_cache()

    first_file = tmp_path / "jongga_v2_results_20260221.json"
    first_file.write_text(
        json.dumps({"date": "2026-02-21", "signals": [{"stock_code": "000001"}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    payloads_1 = kr_market._load_jongga_result_payloads()
    assert len(payloads_1) == 1
    assert payloads_1[0][1]["date"] == "2026-02-21"

    second_file = tmp_path / "jongga_v2_results_20260220.json"
    second_file.write_text(
        json.dumps({"date": "2026-02-20", "signals": [{"stock_code": "000002"}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    payloads_2 = kr_market._load_jongga_result_payloads()
    assert len(payloads_2) == 2
    assert payloads_2[0][1]["date"] == "2026-02-21"
    assert payloads_2[1][1]["date"] == "2026-02-20"
