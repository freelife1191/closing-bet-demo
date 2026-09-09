#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Data Signals Routes 리팩토링 회귀 테스트
"""

from __future__ import annotations

import logging
import os
import sys
import threading
from typing import Any

import pandas as pd
import pytest
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


@pytest.fixture(autouse=True)
def _admin_env(monkeypatch):
    """_seed_admin_identity 가 세우는 이메일이 관리자로 판정되게 한다([INFRA-042])."""
    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")


def _seed_admin_identity(app):
    """[INFRA-042] 가 이 파일의 라우트 일부에 require_admin 을 붙였다.

    이 파일이 재는 것은 인가가 아니라 그 뒤의 위임 동작이므로 관리자 신원을 세워 두고
    그대로 잰다. 게이트 자체는 tests/app/test_admin_gated_routes.py 가 잰다.

    OPTIONS 에서 일찍 빠지는 것은 실제 before_request 와 같다(app/__init__.py:171).
    """

    @app.before_request
    def _seed():
        from flask import g, request

        if request.method == "OPTIONS":
            return
        g.user_email = "admin@example.com"


def _create_client(fetch_realtime_prices_fn):
    app = Flask(__name__)
    app.testing = True
    bp = Blueprint("kr_signal_routes_test", __name__)
    register_market_data_signal_routes(
        bp,
        logger=logging.getLogger("test.kr_market_data_signals_routes"),
        deps=_build_deps(fetch_realtime_prices_fn),
    )
    _seed_admin_identity(app)
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
    _seed_admin_identity(app)
    app.register_blueprint(bp, url_prefix="/api/kr")
    client = app.test_client()

    response = client.get("/api/kr/signals/status")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["running"] is True
    assert payload["status"] == "running"
    assert payload["message"] == "VCP 시그널 스케쥴링 진행 중인 상태"
    assert payload["schedulerRunning"] is True


def test_signal_dates_route_requests_only_signal_judgement_columns():
    """날짜와 시그널 판정에 쓰는 세 열만 요청한다.

    판정 열이 늘어난 것은 `[VCP-008]` 때문이다. 날짜 목록이 시그널 조회와 같은
    기준으로 걸러지려면 status·score·is_vcp 를 함께 읽어야 한다. 그래도 CSV 의
    나머지 열은 읽지 않는다.
    """
    captured: dict[str, Any] = {}

    def _load_csv_file(name: str, **kwargs):
        captured["name"] = name
        captured["kwargs"] = kwargs
        return pd.DataFrame(
            [{"signal_date": "2026-02-21", "status": "OPEN", "score": 85, "is_vcp": True}]
        )

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
    _seed_admin_identity(app)
    app.register_blueprint(bp, url_prefix="/api/kr")
    client = app.test_client()

    response = client.get("/api/kr/signals/dates")

    assert response.status_code == 200
    assert response.get_json() == ["2026-02-21"]
    assert captured["name"] == "signals_log.csv"
    assert captured["kwargs"]["deep_copy"] is False
    assert captured["kwargs"]["usecols"] == ["signal_date", "status", "score", "is_vcp"]


def test_signal_dates_route_normalizes_datetime_strings_and_deduplicates():
    def _load_csv_file(_name: str, **_kwargs):
        return pd.DataFrame(
            [
                {"signal_date": "2026-02-21 00:00:00", "status": "OPEN", "score": 85, "is_vcp": True},
                {"signal_date": "20260222", "status": "OPEN", "score": 85, "is_vcp": True},
                {"signal_date": "2026-02-21", "status": "OPEN", "score": 85, "is_vcp": True},
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
    _seed_admin_identity(app)
    app.register_blueprint(bp, url_prefix="/api/kr")
    client = app.test_client()

    response = client.get("/api/kr/signals/dates")

    assert response.status_code == 200
    assert response.get_json() == ["2026-02-22", "2026-02-21"]


def test_signal_dates_route_omits_dates_whose_rows_are_not_signals():
    """[VCP-008] 회귀: 목록에 남은 날짜는 그 날짜로 조회했을 때 반드시 시그널이 있다.

    signals_log.csv 에 행이 있어도 status·score·is_vcp 판정에서 떨어지면 조회 결과가
    비므로, 날짜 목록에도 그 날짜를 내보내지 않는다. 판정을 통과하는 날짜만 남는다.
    """

    def _load_csv_file(_name: str, **_kwargs):
        return pd.DataFrame(
            [
                # is_vcp 가 비어 있어 시그널이 되지 못한다. 실제 data/signals_log.csv 의 상태다.
                {"signal_date": "2026-05-05", "status": "OPEN", "score": 82, "is_vcp": ""},
                # 이미 종료된 시그널이다.
                {"signal_date": "2026-04-04", "status": "CLOSED", "score": 90, "is_vcp": True},
                # 최소 점수 60 에 못 미친다.
                {"signal_date": "2026-03-03", "status": "OPEN", "score": 41, "is_vcp": True},
                {"signal_date": "2026-02-21", "status": "OPEN", "score": 85, "is_vcp": True},
            ]
        )

    deps = _build_deps(fetch_realtime_prices_fn=lambda **_kwargs: {})
    deps["load_csv_file"] = _load_csv_file

    app = Flask(__name__)
    app.testing = True
    bp = Blueprint("kr_signal_dates_signal_filter_test", __name__)
    register_market_data_signal_routes(
        bp,
        logger=logging.getLogger("test.kr_market_data_signals_routes"),
        deps=deps,
    )
    _seed_admin_identity(app)
    app.register_blueprint(bp, url_prefix="/api/kr")
    client = app.test_client()

    response = client.get("/api/kr/signals/dates")

    assert response.status_code == 200
    assert response.get_json() == ["2026-02-21"]


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
    _seed_admin_identity(app)
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
    _seed_admin_identity(app)
    app.register_blueprint(bp, url_prefix="/api/kr")
    client = app.test_client()

    response = client.get("/api/kr/signals")

    assert response.status_code == 200
    assert captured["data_dir"] == "/tmp"
    assert captured["total_scanned"] == 77
    assert response.get_json()["total_scanned"] == 77


def test_reanalyze_failed_ai_background_supports_stop_request():
    deps = _build_deps(fetch_realtime_prices_fn=lambda **_kwargs: {})
    reanalysis_started = threading.Event()
    allow_reanalysis_to_finish = threading.Event()
    reanalysis_finished = threading.Event()

    class _ReanalysisStatus(dict):
        def update(self, *args, **kwargs):
            super().update(*args, **kwargs)
            if self.get("running") is False and self.get("task_type") is None:
                reanalysis_finished.set()

    status_state = _ReanalysisStatus(deps["vcp_status"])
    deps["vcp_status"] = status_state

    def _execute(**kwargs):
        should_stop = kwargs.get("should_stop")
        on_progress = kwargs.get("on_progress")
        reanalysis_started.set()
        # 중지 요청을 관찰하기 전까지 백그라운드 작업을 멈춘다. 시간 대기는 CI 부하에
        # 따라 stop 요청보다 먼저 끝날 수 있어 중지 경로를 보장하지 못한다.
        allow_reanalysis_to_finish.wait()
        if callable(should_stop) and should_stop():
            return 200, {"status": "cancelled", "message": "사용자 중지"}
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
    _seed_admin_identity(app)
    app.register_blueprint(bp, url_prefix="/api/kr")
    client = app.test_client()

    try:
        start_response = client.post(
            "/api/kr/signals/reanalyze-failed-ai",
            json={"background": True, "target_date": "2026-02-21"},
        )
        assert start_response.status_code == 202
        assert reanalysis_started.wait(timeout=1.0)
        assert status_state["running"] is True
        assert status_state["task_type"] == "reanalysis_failed_ai"

        stop_response = client.post("/api/kr/signals/reanalyze-failed-ai/stop", json={})
        assert stop_response.status_code == 202
        assert status_state["cancel_requested"] is True

        allow_reanalysis_to_finish.set()
        assert reanalysis_finished.wait(timeout=1.0)
        assert status_state["running"] is False
        assert status_state["task_type"] is None
        assert status_state["cancel_requested"] is False
        assert status_state["status"] == "cancelled"
    finally:
        # 앞선 단언이 실패해도 daemon 스레드가 다음 테스트까지 남지 않게 한다.
        allow_reanalysis_to_finish.set()
        assert reanalysis_finished.wait(timeout=1.0)


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
    _seed_admin_identity(app)
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
    _seed_admin_identity(app)
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
    _seed_admin_identity(app)
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
    _seed_admin_identity(app)
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
    _seed_admin_identity(app)
    app.register_blueprint(bp, url_prefix="/api/kr")
    client = app.test_client()

    response = client.post(
        "/api/kr/signals/reanalyze-failed-ai",
        json={"background": False, "force_provider": "not-supported"},
    )

    assert response.status_code == 400
    assert response.get_json()["status"] == "error"


def test_stock_chart_route_forwards_end_query_to_payload_builder():
    """`?end=` 이 서비스까지 닿는지 라우트 계층에서 확인한다.

    서비스 단위 테스트는 `build_stock_chart_payload` 를 직접 부르므로, 여기서 이름이
    어긋나면 과거 시그널의 차트가 조용히 오늘 구간으로 돌아가도 아무도 알아채지 못한다.
    """
    deps = _build_deps(fetch_realtime_prices_fn=lambda **_kwargs: {})
    captured: dict[str, Any] = {}

    def _build(**kwargs):
        captured.update(kwargs)
        return {"ticker": kwargs.get("ticker"), "data": []}

    deps["build_stock_chart_payload"] = _build

    app = Flask(__name__)
    app.testing = True
    bp = Blueprint("kr_signal_stock_chart_end_test", __name__)
    register_market_data_signal_routes(
        bp,
        logger=logging.getLogger("test.kr_market_data_signals_routes"),
        deps=deps,
    )
    _seed_admin_identity(app)
    app.register_blueprint(bp, url_prefix="/api/kr")
    client = app.test_client()

    assert client.get("/api/kr/stock-chart/034730?period=3m&end=2026-05-05").status_code == 200
    assert captured.get("end_date") == "2026-05-05"

    captured.clear()
    assert client.get("/api/kr/stock-chart/034730?period=3m").status_code == 200
    assert captured.get("end_date") is None
