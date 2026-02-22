#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR AI Data Service 리팩토링 회귀 테스트
"""

import os
import sqlite3
import sys

import pandas as pd
import pytest


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import engine.kr_ai_data_service as kr_ai_data_service_module
from engine.kr_ai_data_service import KrAiDataService


@pytest.fixture(autouse=True)
def _clear_stock_info_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(
        kr_ai_data_service_module,
        "_resolve_stock_info_cache_db_path",
        lambda _signals_file: str(tmp_path / "runtime_cache.db"),
    )
    kr_ai_data_service_module.clear_kr_ai_stock_info_cache()
    yield
    kr_ai_data_service_module.clear_kr_ai_stock_info_cache()


def test_get_stock_info_reads_minimum_columns_and_normalizes_ticker(monkeypatch):
    service = KrAiDataService()
    captured: dict[str, object] = {}

    monkeypatch.setattr(kr_ai_data_service_module.os.path, "exists", lambda _path: True)
    monkeypatch.setattr(kr_ai_data_service_module, "_file_signature", lambda _path: (1, 1))

    def _fake_load_csv_file(_data_dir, _filename, **kwargs):
        captured["usecols"] = kwargs.get("usecols")
        captured["signature"] = kwargs.get("signature")
        return pd.DataFrame(
            [
                {
                    "ticker": "005930",
                    "name": "삼성전자",
                    "entry_price": 70000,
                    "current_price": 71000,
                    "return_pct": 1.4,
                    "market": "KOSPI",
                    "score": 88.0,
                    "vcp_score": 9.0,
                    "contraction_ratio": 0.42,
                    "foreign_5d": 100,
                    "inst_5d": 50,
                }
            ]
        )

    monkeypatch.setattr(kr_ai_data_service_module, "load_csv_file", _fake_load_csv_file)

    info = service.get_stock_info("5930")

    assert info is not None
    assert info["name"] == "삼성전자"
    assert info["price"] == 71000
    assert info["market"] == "KOSPI"
    assert captured["usecols"] == [
        "ticker",
        "name",
        "current_price",
        "entry_price",
        "return_pct",
        "market",
        "score",
        "vcp_score",
        "contraction_ratio",
        "foreign_5d",
        "inst_5d",
    ]
    assert captured["signature"] == (1, 1)


def test_get_stock_info_falls_back_when_no_matching_signal(monkeypatch):
    service = KrAiDataService()

    monkeypatch.setattr(kr_ai_data_service_module.os.path, "exists", lambda _path: True)
    monkeypatch.setattr(kr_ai_data_service_module, "_file_signature", lambda _path: (1, 1))
    monkeypatch.setattr(
        kr_ai_data_service_module.pd,
        "read_csv",
        lambda *_path, **kwargs: (_ for _ in ()).throw(AssertionError("load_csv_file path should be used")),
    )
    monkeypatch.setattr(
        kr_ai_data_service_module,
        "load_csv_file",
        lambda *_args, **_kwargs: pd.DataFrame([{"ticker": "000660", "name": "SK하이닉스"}]),
    )

    info = service.get_stock_info("005930")

    assert info is not None
    assert info["ticker"] == "005930"
    assert info["name"] == "삼성전자"
    assert info["score"] == 0


def test_get_stock_info_retries_without_usecols_on_value_error(monkeypatch):
    service = KrAiDataService()
    monkeypatch.setattr(kr_ai_data_service_module.os.path, "exists", lambda _path: True)
    monkeypatch.setattr(kr_ai_data_service_module, "_file_signature", lambda _path: (1, 1))

    calls = {"count": 0, "usecols": []}

    def _fake_load_csv_file(_data_dir, _filename, **kwargs):
        calls["count"] += 1
        calls["usecols"].append(kwargs.get("usecols"))
        if calls["count"] == 1:
            raise ValueError("Usecols do not match columns")
        return pd.DataFrame(
            [
                {
                    "ticker": "005930",
                    "name": "삼성전자",
                    "current_price": 72000,
                    "entry_price": 70000,
                    "return_pct": 2.8,
                    "market": "KOSPI",
                    "score": 90.0,
                    "vcp_score": 10.0,
                    "contraction_ratio": 0.35,
                    "foreign_5d": 120,
                    "inst_5d": 60,
                }
            ]
        )

    monkeypatch.setattr(kr_ai_data_service_module, "load_csv_file", _fake_load_csv_file)

    info = service.get_stock_info("005930")

    assert info is not None
    assert info["price"] == 72000
    assert calls["count"] == 2
    assert calls["usecols"][0] is not None
    assert calls["usecols"][1] is None


def test_get_stock_info_reuses_sqlite_cache_after_memory_clear(monkeypatch, tmp_path):
    service = KrAiDataService()
    monkeypatch.setattr(kr_ai_data_service_module.os.path, "exists", lambda _path: True)
    monkeypatch.setattr(kr_ai_data_service_module, "_file_signature", lambda _path: (1, 1))
    monkeypatch.setattr(
        kr_ai_data_service_module,
        "_resolve_stock_info_cache_db_path",
        lambda _signals_file: str(tmp_path / "runtime_cache.db"),
    )

    monkeypatch.setattr(
        kr_ai_data_service_module,
        "load_csv_file",
        lambda *_args, **_kwargs: pd.DataFrame(
            [
                {
                    "ticker": "005930",
                    "name": "삼성전자",
                    "current_price": 73000,
                    "entry_price": 70000,
                    "return_pct": 4.2,
                    "market": "KOSPI",
                    "score": 93.0,
                    "vcp_score": 11.0,
                    "contraction_ratio": 0.31,
                    "foreign_5d": 200,
                    "inst_5d": 90,
                }
            ]
        ),
    )

    first = service.get_stock_info("005930")
    assert first is not None
    assert first["price"] == 73000

    kr_ai_data_service_module.clear_kr_ai_stock_info_cache()
    monkeypatch.setattr(
        kr_ai_data_service_module,
        "load_csv_file",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("should use sqlite cache")),
    )

    second = service.get_stock_info("005930")
    assert second == first

    db_path = tmp_path / "runtime_cache.db"
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM kr_ai_stock_info_cache
            WHERE ticker = ?
            """,
            ("005930",),
        )
        row = cursor.fetchone()
    assert row and row[0] >= 1


def test_get_stock_info_reuses_latest_signal_index_for_multiple_tickers(monkeypatch):
    service = KrAiDataService()
    monkeypatch.setattr(kr_ai_data_service_module.os.path, "exists", lambda _path: True)
    monkeypatch.setattr(kr_ai_data_service_module, "_file_signature", lambda _path: (1, 1))

    calls = {"count": 0}

    def _fake_load_csv_file(_data_dir, _filename, **kwargs):
        calls["count"] += 1
        assert kwargs.get("usecols") is not None
        return pd.DataFrame(
            [
                {
                    "ticker": "005930",
                    "name": "삼성전자",
                    "current_price": 71000,
                    "entry_price": 70000,
                    "return_pct": 1.4,
                    "market": "KOSPI",
                    "score": 88.0,
                    "vcp_score": 9.0,
                    "contraction_ratio": 0.42,
                    "foreign_5d": 100,
                    "inst_5d": 50,
                },
                {
                    "ticker": "000660",
                    "name": "SK하이닉스",
                    "current_price": 121000,
                    "entry_price": 120000,
                    "return_pct": 0.83,
                    "market": "KOSPI",
                    "score": 84.0,
                    "vcp_score": 7.0,
                    "contraction_ratio": 0.48,
                    "foreign_5d": 80,
                    "inst_5d": 40,
                },
            ]
        )

    monkeypatch.setattr(kr_ai_data_service_module, "load_csv_file", _fake_load_csv_file)

    info_1 = service.get_stock_info("005930")
    info_2 = service.get_stock_info("000660")

    assert info_1 is not None
    assert info_2 is not None
    assert info_1["name"] == "삼성전자"
    assert info_2["name"] == "SK하이닉스"
    assert calls["count"] == 1


def test_get_stock_info_reloads_latest_signal_index_when_signature_changes(monkeypatch):
    service = KrAiDataService()
    monkeypatch.setattr(kr_ai_data_service_module.os.path, "exists", lambda _path: True)

    signature_state = {"value": (1, 1)}
    monkeypatch.setattr(
        kr_ai_data_service_module,
        "_file_signature",
        lambda _path: signature_state["value"],
    )

    calls = {"count": 0}

    def _fake_load_csv_file(_data_dir, _filename, **kwargs):
        calls["count"] += 1
        signature = kwargs.get("signature")
        current_price = 71000 if signature == (1, 1) else 73000
        return pd.DataFrame(
            [
                {
                    "ticker": "005930",
                    "name": "삼성전자",
                    "current_price": current_price,
                    "entry_price": 70000,
                    "return_pct": 1.4,
                    "market": "KOSPI",
                    "score": 88.0,
                    "vcp_score": 9.0,
                    "contraction_ratio": 0.42,
                    "foreign_5d": 100,
                    "inst_5d": 50,
                },
            ]
        )

    monkeypatch.setattr(kr_ai_data_service_module, "load_csv_file", _fake_load_csv_file)

    first = service.get_stock_info("005930")
    assert first is not None
    assert first["price"] == 71000
    assert calls["count"] == 1

    signature_state["value"] = (2, 2)

    second = service.get_stock_info("005930")
    assert second is not None
    assert second["price"] == 73000
    assert calls["count"] == 2


def test_latest_signal_index_cache_is_bounded_lru(monkeypatch, tmp_path):
    path_a = os.path.abspath(str(tmp_path / "signals_a.csv"))
    path_b = os.path.abspath(str(tmp_path / "signals_b.csv"))
    path_c = os.path.abspath(str(tmp_path / "signals_c.csv"))

    signature_map = {
        path_a: (1, 10),
        path_b: (2, 20),
        path_c: (3, 30),
    }

    with kr_ai_data_service_module._LATEST_SIGNAL_INDEX_CACHE_LOCK:
        kr_ai_data_service_module._LATEST_SIGNAL_INDEX_CACHE.clear()
    monkeypatch.setattr(kr_ai_data_service_module, "_LATEST_SIGNAL_INDEX_CACHE_MAX_ENTRIES", 2)
    monkeypatch.setattr(
        kr_ai_data_service_module,
        "_file_signature",
        lambda path: signature_map.get(path),
    )

    load_calls = {"count": 0}

    def _fake_load_latest_signal_source_frame(*, signals_file, file_signature):
        load_calls["count"] += 1
        ticker = {
            path_a: "005930",
            path_b: "000660",
            path_c: "035420",
        }[signals_file]
        return pd.DataFrame([{"ticker": ticker, "name": f"name_{ticker}"}])

    monkeypatch.setattr(
        KrAiDataService,
        "_load_latest_signal_source_frame",
        staticmethod(_fake_load_latest_signal_source_frame),
    )

    _ = KrAiDataService._load_latest_signal_index(path_a)
    _ = KrAiDataService._load_latest_signal_index(path_b)
    _ = KrAiDataService._load_latest_signal_index(path_a)
    _ = KrAiDataService._load_latest_signal_index(path_c)

    with kr_ai_data_service_module._LATEST_SIGNAL_INDEX_CACHE_LOCK:
        cache_keys = list(kr_ai_data_service_module._LATEST_SIGNAL_INDEX_CACHE.keys())

    assert len(cache_keys) == 2
    assert path_a in cache_keys
    assert path_c in cache_keys
    assert path_b not in cache_keys
    assert load_calls["count"] == 3


def test_get_stock_info_handles_invalid_numeric_values_gracefully(monkeypatch):
    service = KrAiDataService()
    monkeypatch.setattr(kr_ai_data_service_module.os.path, "exists", lambda _path: True)
    monkeypatch.setattr(kr_ai_data_service_module, "_file_signature", lambda _path: (1, 1))
    monkeypatch.setattr(
        kr_ai_data_service_module,
        "load_csv_file",
        lambda *_args, **_kwargs: pd.DataFrame(
            [
                {
                    "ticker": "005930",
                    "name": "삼성전자",
                    "current_price": float("nan"),
                    "entry_price": "70000",
                    "return_pct": "bad",
                    "market": "KOSPI",
                    "score": "n/a",
                    "vcp_score": None,
                    "contraction_ratio": "oops",
                    "foreign_5d": "x",
                    "inst_5d": "y",
                }
            ]
        ),
    )

    info = service.get_stock_info("005930")

    assert info is not None
    assert info["price"] == 70000
    assert info["change_pct"] == 0.0
    assert info["score"] == 0.0
    assert info["vcp_score"] == 0.0
    assert info["contraction_ratio"] == 0.0
    assert info["foreign_5d"] == 0
    assert info["inst_5d"] == 0


def test_default_news_collector_supports_legacy_constructor_signature(monkeypatch):
    class _LegacyCollector:
        def __init__(self, config):
            self.config = config

    monkeypatch.setattr(
        kr_ai_data_service_module,
        "_ENHANCED_NEWS_COLLECTOR_CLASS",
        _LegacyCollector,
    )

    service = KrAiDataService(news_collector=None)

    assert isinstance(service.news_collector, _LegacyCollector)
    assert service.news_collector.config is None
