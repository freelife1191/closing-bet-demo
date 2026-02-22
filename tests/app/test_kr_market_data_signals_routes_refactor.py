#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Data Signals Routes 리팩토링 회귀 테스트
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

import pandas as pd
from flask import Blueprint, Flask


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from app.routes.kr_market_data_signals_routes import register_market_data_signal_routes


def _build_deps(fetch_realtime_prices_fn):
    return {
        "data_dir_getter": lambda: "/tmp",
        "load_csv_file": lambda _name: __import__("pandas").DataFrame(),
        "get_data_path": lambda name: name,
        "vcp_status": {"running": False},
        "run_vcp_background_pipeline": lambda **_kwargs: None,
        "start_vcp_screener_run": lambda **_kwargs: (200, {"status": "started"}),
        "validate_vcp_reanalysis_source_frame": lambda **_kwargs: (200, {}),
        "execute_vcp_failed_ai_reanalysis": lambda **_kwargs: (200, {}),
        "update_vcp_ai_cache_files": lambda _date, _data: 0,
        "build_market_status_payload": lambda **_kwargs: {"status": "OK"},
        "build_vcp_signals_payload": lambda **_kwargs: {"signals": []},
        "filter_signals_dataframe_by_date": lambda **_kwargs: None,
        "build_vcp_signals_from_dataframe": lambda **_kwargs: [],
        "load_latest_vcp_price_map": lambda: {"005930": 321.0},
        "apply_latest_prices_to_jongga_signals": lambda _signals, _map: 0,
        "sort_and_limit_vcp_signals": lambda _signals, limit=100: None,
        "build_ai_data_map": lambda **_kwargs: {},
        "merge_legacy_ai_fields_into_map": lambda **_kwargs: None,
        "merge_ai_data_into_vcp_signals": lambda **_kwargs: None,
        "count_total_scanned_stocks": lambda _data_dir: 0,
        "build_stock_chart_payload": lambda **_kwargs: {"items": []},
        "resolve_chart_period_days": lambda _period: 90,
        "fetch_realtime_prices": fetch_realtime_prices_fn,
        "load_json_file": lambda _filename: {},
    }


def _create_client(fetch_realtime_prices_fn):
    app = Flask(__name__)
    app.testing = True
    bp = Blueprint("kr_signal_routes_test", __name__)
    register_market_data_signal_routes(
        bp,
        logger=logging.getLogger("test.kr_market_data_signals_routes"),
        deps=_build_deps(fetch_realtime_prices_fn),
    )
    app.register_blueprint(bp, url_prefix="/api/kr")
    return app.test_client()


def test_realtime_prices_route_passes_latest_price_loader_to_service():
    captured: dict[str, Any] = {}

    def _fake_fetch_realtime_prices(
        *,
        tickers,
        load_csv_file,
        logger,
        load_latest_price_map=None,
        get_data_path=None,
    ):
        captured["tickers"] = tickers
        captured["has_loader"] = callable(load_latest_price_map)
        captured["latest_price_map"] = load_latest_price_map() if callable(load_latest_price_map) else {}
        captured["has_get_data_path"] = callable(get_data_path)
        captured["sample_data_path"] = get_data_path("korean_stocks_list.csv") if callable(get_data_path) else None
        return {"005930": float(captured["latest_price_map"].get("005930", 0))}

    client = _create_client(_fake_fetch_realtime_prices)

    response = client.post("/api/kr/realtime-prices", json={"tickers": ["005930", "5930"]})

    assert response.status_code == 200
    assert captured["tickers"] == ["005930", "5930"]
    assert captured["has_loader"] is True
    assert captured["has_get_data_path"] is True
    assert captured["sample_data_path"] == "korean_stocks_list.csv"
    assert captured["latest_price_map"]["005930"] == 321.0
    assert response.get_json()["prices"]["005930"] == 321.0


def test_signal_dates_route_requests_only_signal_date_column_when_supported():
    captured: dict[str, Any] = {}

    def _load_csv_file(name: str, **kwargs):
        captured["name"] = name
        captured["kwargs"] = kwargs
        return pd.DataFrame([{"signal_date": "2026-02-21"}])

    deps = _build_deps(fetch_realtime_prices_fn=lambda **_kwargs: {})
    deps["load_csv_file"] = _load_csv_file

    app = Flask(__name__)
    app.testing = True
    bp = Blueprint("kr_signal_dates_usecols_test", __name__)
    register_market_data_signal_routes(
        bp,
        logger=logging.getLogger("test.kr_market_data_signals_routes"),
        deps=deps,
    )
    app.register_blueprint(bp, url_prefix="/api/kr")
    client = app.test_client()

    response = client.get("/api/kr/signals/dates")

    assert response.status_code == 200
    assert response.get_json() == ["2026-02-21"]
    assert captured["name"] == "signals_log.csv"
    assert captured["kwargs"]["deep_copy"] is False
    assert captured["kwargs"]["usecols"] == ["signal_date"]


def test_signals_route_count_callback_accepts_data_dir_argument():
    captured: dict[str, Any] = {}

    def _build_payload(**kwargs):
        count_fn = kwargs["count_total_scanned_stocks"]
        data_dir = kwargs["data_dir"]
        captured["data_dir"] = data_dir
        captured["total_scanned"] = count_fn(data_dir)
        return {
            "signals": [],
            "count": 0,
            "total_scanned": captured["total_scanned"],
            "generated_at": "2026-02-22T00:00:00",
            "source": "signals_log.csv",
        }

    deps = _build_deps(fetch_realtime_prices_fn=lambda **_kwargs: {})
    deps["build_vcp_signals_payload"] = _build_payload
    deps["count_total_scanned_stocks"] = lambda data_dir: 123 if data_dir == "/tmp" else 0

    app = Flask(__name__)
    app.testing = True
    bp = Blueprint("kr_signal_count_callback_test", __name__)
    register_market_data_signal_routes(
        bp,
        logger=logging.getLogger("test.kr_market_data_signals_routes"),
        deps=deps,
    )
    app.register_blueprint(bp, url_prefix="/api/kr")
    client = app.test_client()

    response = client.get("/api/kr/signals")

    assert response.status_code == 200
    assert captured["data_dir"] == "/tmp"
    assert captured["total_scanned"] == 123
    assert response.get_json()["total_scanned"] == 123


def test_signals_route_count_callback_allows_legacy_noarg_callback():
    captured: dict[str, Any] = {}

    def _build_payload(**kwargs):
        count_fn = kwargs["count_total_scanned_stocks"]
        data_dir = kwargs["data_dir"]
        captured["data_dir"] = data_dir
        captured["total_scanned"] = count_fn(data_dir)
        return {
            "signals": [],
            "count": 0,
            "total_scanned": captured["total_scanned"],
            "generated_at": "2026-02-22T00:00:00",
            "source": "signals_log.csv",
        }

    deps = _build_deps(fetch_realtime_prices_fn=lambda **_kwargs: {})
    deps["build_vcp_signals_payload"] = _build_payload
    deps["count_total_scanned_stocks"] = lambda: 77

    app = Flask(__name__)
    app.testing = True
    bp = Blueprint("kr_signal_count_callback_legacy_test", __name__)
    register_market_data_signal_routes(
        bp,
        logger=logging.getLogger("test.kr_market_data_signals_routes"),
        deps=deps,
    )
    app.register_blueprint(bp, url_prefix="/api/kr")
    client = app.test_client()

    response = client.get("/api/kr/signals")

    assert response.status_code == 200
    assert captured["data_dir"] == "/tmp"
    assert captured["total_scanned"] == 77
    assert response.get_json()["total_scanned"] == 77
