#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Data Signals Routes 리팩토링 회귀 테스트
"""

from __future__ import annotations

import logging
import os
import sys
import time
from typing import Any

import pandas as pd
from flask import Blueprint, Flask


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from app.routes.kr_market_data_signals_routes import register_market_data_signal_routes
import app.routes.kr_market_data_signals_routes as signals_routes


def _build_deps(fetch_realtime_prices_fn):
    return {
        "data_dir_getter": lambda: "/tmp",
        "load_csv_file": lambda _name: __import__("pandas").DataFrame(
            [{"ticker": "005930", "signal_date": "2026-02-21"}]
        ),
        "get_data_path": lambda name: name,
        "vcp_status": {
            "running": False,
            "task_type": None,
            "cancel_requested": False,
            "status": "idle",
            "message": "",
            "progress": 0,
        },
        "run_vcp_background_pipeline": lambda **_kwargs: None,
        "start_vcp_screener_run": lambda **_kwargs: (200, {"status": "started"}),
        "validate_vcp_reanalysis_source_frame": lambda _df: (None, None),
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


def test_vcp_status_route_reflects_scheduler_vcp_running(monkeypatch):
    monkeypatch.setattr(
        signals_routes,
        "get_scheduler_runtime_status",
        lambda data_dir="data": {
            "is_data_scheduling_running": True,
            "is_jongga_scheduling_running": False,
            "is_vcp_scheduling_running": True,
        },
    )

    deps = _build_deps(fetch_realtime_prices_fn=lambda **_kwargs: {})
    deps["vcp_status"] = {
        "running": False,
        "task_type": None,
        "cancel_requested": False,
        "status": "idle",
        "message": "",
        "progress": 0,
    }

    app = Flask(__name__)
    app.testing = True
    bp = Blueprint("kr_signal_status_scheduler_test", __name__)
    register_market_data_signal_routes(
        bp,
        logger=logging.getLogger("test.kr_market_data_signals_routes"),
        deps=deps,
    )
    app.register_blueprint(bp, url_prefix="/api/kr")
    client = app.test_client()

    response = client.get("/api/kr/signals/status")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["running"] is True
    assert payload["status"] == "running"
    assert payload["message"] == "VCP 시그널 스케쥴링 진행 중인 상태"
    assert payload["schedulerRunning"] is True


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


def test_signal_dates_route_normalizes_datetime_strings_and_deduplicates():
    def _load_csv_file(_name: str, **_kwargs):
        return pd.DataFrame(
            [
                {"signal_date": "2026-02-21 00:00:00"},
                {"signal_date": "20260222"},
                {"signal_date": "2026-02-21"},
            ]
        )

    deps = _build_deps(fetch_realtime_prices_fn=lambda **_kwargs: {})
    deps["load_csv_file"] = _load_csv_file

    app = Flask(__name__)
    app.testing = True
    bp = Blueprint("kr_signal_dates_normalize_test", __name__)
    register_market_data_signal_routes(
        bp,
        logger=logging.getLogger("test.kr_market_data_signals_routes"),
        deps=deps,
    )
    app.register_blueprint(bp, url_prefix="/api/kr")
    client = app.test_client()

    response = client.get("/api/kr/signals/dates")

    assert response.status_code == 200
    assert response.get_json() == ["2026-02-22", "2026-02-21"]


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


def test_reanalyze_failed_ai_background_supports_stop_request():
    deps = _build_deps(fetch_realtime_prices_fn=lambda **_kwargs: {})
    status_state = deps["vcp_status"]

    def _execute(**kwargs):
        should_stop = kwargs.get("should_stop")
        on_progress = kwargs.get("on_progress")
        for idx in range(5):
            if callable(on_progress):
                on_progress(idx + 1, 5, f"{idx + 1:06d}")
            if callable(should_stop) and should_stop():
                return 200, {"status": "cancelled", "message": "사용자 중지"}
            time.sleep(0.01)
        return 200, {"status": "success", "message": "완료"}

    deps["execute_vcp_failed_ai_reanalysis"] = _execute

    app = Flask(__name__)
    app.testing = True
    bp = Blueprint("kr_signal_reanalyze_background_test", __name__)
    register_market_data_signal_routes(
        bp,
        logger=logging.getLogger("test.kr_market_data_signals_routes"),
        deps=deps,
    )
    app.register_blueprint(bp, url_prefix="/api/kr")
    client = app.test_client()

    start_response = client.post(
        "/api/kr/signals/reanalyze-failed-ai",
        json={"background": True, "target_date": "2026-02-21"},
    )
    assert start_response.status_code == 202
    assert status_state["running"] is True
    assert status_state["task_type"] == "reanalysis_failed_ai"

    stop_response = client.post("/api/kr/signals/reanalyze-failed-ai/stop", json={})
    assert stop_response.status_code == 202
    assert status_state["cancel_requested"] is True

    deadline = time.time() + 1.0
    while status_state.get("running") and time.time() < deadline:
        time.sleep(0.01)

    assert status_state["running"] is False
    assert status_state["task_type"] is None
    assert status_state["cancel_requested"] is False
    assert status_state["status"] in {"cancelled", "success"}


def test_reanalyze_failed_ai_stop_returns_conflict_when_not_running():
    deps = _build_deps(fetch_realtime_prices_fn=lambda **_kwargs: {})

    app = Flask(__name__)
    app.testing = True
    bp = Blueprint("kr_signal_reanalyze_stop_conflict_test", __name__)
    register_market_data_signal_routes(
        bp,
        logger=logging.getLogger("test.kr_market_data_signals_routes"),
        deps=deps,
    )
    app.register_blueprint(bp, url_prefix="/api/kr")
    client = app.test_client()

    response = client.post("/api/kr/signals/reanalyze-failed-ai/stop", json={})
    assert response.status_code == 409


def test_reanalyze_failed_ai_stop_accepts_running_state_without_task_type():
    deps = _build_deps(fetch_realtime_prices_fn=lambda **_kwargs: {})
    deps["vcp_status"].update(
        {
            "running": True,
            "task_type": None,
            "status": "running",
            "message": "실패 AI 재분석 진행 중... (3/10)",
        }
    )

    app = Flask(__name__)
    app.testing = True
    bp = Blueprint("kr_signal_reanalyze_stop_missing_task_type_test", __name__)
    register_market_data_signal_routes(
        bp,
        logger=logging.getLogger("test.kr_market_data_signals_routes"),
        deps=deps,
    )
    app.register_blueprint(bp, url_prefix="/api/kr")
    client = app.test_client()

    response = client.post("/api/kr/signals/reanalyze-failed-ai/stop", json={})
    assert response.status_code == 202
    assert deps["vcp_status"]["cancel_requested"] is True
    assert deps["vcp_status"]["task_type"] == "reanalysis_failed_ai"


def test_reanalyze_failed_ai_route_forwards_force_provider_to_service():
    deps = _build_deps(fetch_realtime_prices_fn=lambda **_kwargs: {})
    captured: dict[str, Any] = {}

    def _execute(**kwargs):
        captured.update(kwargs)
        return 200, {"status": "success", "message": "ok"}

    deps["execute_vcp_failed_ai_reanalysis"] = _execute

    app = Flask(__name__)
    app.testing = True
    bp = Blueprint("kr_signal_reanalyze_force_provider_test", __name__)
    register_market_data_signal_routes(
        bp,
        logger=logging.getLogger("test.kr_market_data_signals_routes"),
        deps=deps,
    )
    app.register_blueprint(bp, url_prefix="/api/kr")
    client = app.test_client()

    response = client.post(
        "/api/kr/signals/reanalyze-failed-ai",
        json={"background": False, "target_date": "2026-02-21", "force_provider": "gemini"},
    )

    assert response.status_code == 200
    assert captured.get("force_provider") == "gemini"


def test_reanalyze_failed_ai_route_loads_min_columns_and_forwards_persist_loader():
    deps = _build_deps(fetch_realtime_prices_fn=lambda **_kwargs: {})
    captured_loader: list[tuple[str, dict[str, Any]]] = []
    captured_execute: dict[str, Any] = {}

    def _load_csv_file(name: str, **kwargs):
        captured_loader.append((name, dict(kwargs)))
        return pd.DataFrame(
            [
                {
                    "ticker": "005930",
                    "signal_date": "2026-02-21",
                    "name": "삼성전자",
                    "current_price": 10_000,
                    "entry_price": 9_900,
                    "score": 8,
                    "vcp_score": 7,
                    "contraction_ratio": 10,
                    "foreign_5d": 1,
                    "inst_5d": 1,
                    "foreign_1d": 1,
                    "inst_1d": 1,
                    "ai_action": "N/A",
                    "ai_reason": "분석 실패",
                    "ai_confidence": 0,
                }
            ]
        )

    def _execute(**kwargs):
        captured_execute.update(kwargs)
        return 200, {"status": "success", "message": "ok"}

    deps["load_csv_file"] = _load_csv_file
    deps["execute_vcp_failed_ai_reanalysis"] = _execute

    app = Flask(__name__)
    app.testing = True
    bp = Blueprint("kr_signal_reanalyze_usecols_test", __name__)
    register_market_data_signal_routes(
        bp,
        logger=logging.getLogger("test.kr_market_data_signals_routes"),
        deps=deps,
    )
    app.register_blueprint(bp, url_prefix="/api/kr")
    client = app.test_client()

    response = client.post(
        "/api/kr/signals/reanalyze-failed-ai",
        json={"background": False, "target_date": "2026-02-21"},
    )

    assert response.status_code == 200
    assert captured_loader
    first_name, first_kwargs = captured_loader[0]
    assert first_name == "signals_log.csv"
    assert first_kwargs.get("deep_copy") is False
    assert first_kwargs.get("usecols") == signals_routes._VCP_REANALYSIS_SIGNAL_USECOLS
    assert callable(captured_execute.get("load_csv_file_for_persist"))


def test_reanalyze_failed_ai_route_rejects_invalid_force_provider():
    deps = _build_deps(fetch_realtime_prices_fn=lambda **_kwargs: {})

    app = Flask(__name__)
    app.testing = True
    bp = Blueprint("kr_signal_reanalyze_force_provider_invalid_test", __name__)
    register_market_data_signal_routes(
        bp,
        logger=logging.getLogger("test.kr_market_data_signals_routes"),
        deps=deps,
    )
    app.register_blueprint(bp, url_prefix="/api/kr")
    client = app.test_client()

    response = client.post(
        "/api/kr/signals/reanalyze-failed-ai",
        json={"background": False, "force_provider": "not-supported"},
    )

    assert response.status_code == 400
    assert response.get_json()["status"] == "error"
