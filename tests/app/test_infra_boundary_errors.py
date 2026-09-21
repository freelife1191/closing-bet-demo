#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""INFRA-066: 독립 라우트 오류 경계가 내부 원문을 응답으로 보내지 않는다."""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import time
from types import SimpleNamespace
from typing import Any

import pytest
from flask import Blueprint, Flask, g
from werkzeug.exceptions import MethodNotAllowed, TooManyRequests

import app.routes.kr_market_system_http_routes as system_routes
from app.routes.common_portfolio_routes import register_common_portfolio_routes
import app.routes.kr_market_data_signals_routes as signals_routes
import app.routes.common_market_mock_routes as market_mock_routes
from app.routes.common_market_mock_routes import register_common_market_mock_routes
from app.routes.kr_market_data_signals_routes import register_market_data_signal_routes
from app.routes.kr_market_jongga_execution_routes import register_jongga_execution_routes
from app.routes.route_execution import execute_json_route


CANARY = "/private/qa-secret/INTERNAL_TOKEN=never-send"
IDENTITY_SECRET = "infra-boundary-test-secret"


def _raise_canary(*_args: Any, **_kwargs: Any) -> Any:
    raise RuntimeError(CANARY)


def _signed_identity(*, method: str, path: str) -> str:
    email = "admin@example.com"
    encoded_email = base64.urlsafe_b64encode(email.encode()).decode().rstrip("=")
    expiry = int(time.time()) + 120
    prefix = f"v2.{encoded_email}.{expiry}"
    encoded_path = base64.urlsafe_b64encode(path.encode()).decode().rstrip("=")
    payload = f"{prefix}.{method}.{encoded_path}"
    signature = hmac.new(IDENTITY_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{prefix}.{signature}"


def _assert_hidden(response, expected_payload: dict[str, str]) -> None:
    assert response.status_code == 500
    assert response.get_json() == expected_payload
    assert CANARY not in response.get_data(as_text=True)


def test_execute_json_route_hides_exception_but_keeps_original_in_logger(caplog: pytest.LogCaptureFixture):
    app = Flask(__name__)
    logger = logging.getLogger("test.infra_boundary_errors.execute_json_route")

    @app.get("/failure")
    def failure():
        return execute_json_route(
            handler=_raise_canary,
            logger=logger,
            error_label="Synthetic route failure",
        )

    with caplog.at_level(logging.ERROR, logger=logger.name):
        response = app.test_client().get("/failure")

    _assert_hidden(response, {"error": "Internal Server Error"})
    assert CANARY in caplog.text


def test_execute_json_route_reraises_http_exception_with_retry_after_header():
    app = Flask(__name__)

    @app.get("/rate-limit")
    def rate_limit():
        return execute_json_route(
            handler=lambda: (_ for _ in ()).throw(TooManyRequests(retry_after=19)),
            logger=logging.getLogger("test.infra_boundary_errors.http_exception"),
            error_label="Synthetic rate limit",
        )

    response = app.test_client().get("/rate-limit")

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "19"


class _FailingPortfolioService:
    def start_background_sync(self) -> None:
        _raise_canary()

    def __getattr__(self, _name: str):
        return _raise_canary


@pytest.fixture
def portfolio_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("INTERNAL_IDENTITY_SECRET", IDENTITY_SECRET)
    app = Flask(__name__)
    blueprint = Blueprint("infra_boundary_portfolio", __name__)
    register_common_portfolio_routes(
        blueprint,
        SimpleNamespace(
            paper_trading=_FailingPortfolioService(),
            logger=logging.getLogger("test.infra_boundary_errors.portfolio"),
        ),
    )
    app.register_blueprint(blueprint, url_prefix="/api")
    return app.test_client()


@pytest.mark.parametrize(
    ("method", "path", "payload", "expected"),
    [
        ("GET", "/api/portfolio", None, {"error": "Internal Server Error"}),
        ("POST", "/api/portfolio/buy", {"ticker": "005930", "name": "삼성", "price": 1, "quantity": 1}, {"status": "error", "message": "Internal Server Error"}),
        ("POST", "/api/portfolio/buy/bulk", {"orders": [{"ticker": "005930", "name": "삼성", "price": 1, "quantity": 1}]}, {"status": "error", "message": "Internal Server Error"}),
        ("POST", "/api/portfolio/sell", {"ticker": "005930", "price": 1, "quantity": 1}, {"status": "error", "message": "Internal Server Error"}),
        ("POST", "/api/portfolio/deposit", {"amount": 1}, {"status": "error", "message": "Internal Server Error"}),
        ("GET", "/api/portfolio/history", None, {"error": "Internal Server Error"}),
        ("GET", "/api/portfolio/history/asset", None, {"error": "Internal Server Error"}),
    ],
)
def test_every_portfolio_custom_error_builder_hides_exception(
    portfolio_client,
    method: str,
    path: str,
    payload: dict[str, Any] | None,
    expected: dict[str, str],
):
    response = portfolio_client.open(
        path,
        method=method,
        json=payload,
        headers={"X-Auth-Identity": _signed_identity(method=method, path=path)},
    )

    _assert_hidden(response, expected)


@pytest.mark.parametrize(
    ("method", "path", "payload", "service", "status", "header", "value"),
    [
        (
            "GET",
            "/api/portfolio",
            None,
            SimpleNamespace(
                start_background_sync=lambda: None,
                get_portfolio_valuation=lambda **_kwargs: (_ for _ in ()).throw(
                    TooManyRequests(retry_after=23)
                ),
            ),
            429,
            "Retry-After",
            "23",
        ),
        (
            "POST",
            "/api/portfolio/buy",
            {"ticker": "005930", "name": "삼성", "price": 1, "quantity": 1},
            SimpleNamespace(
                buy_stock=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                    MethodNotAllowed(valid_methods=["GET"])
                ),
            ),
            405,
            "Allow",
            "GET",
        ),
    ],
)
def test_portfolio_wrapper_preserves_http_exception_status_and_header(
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    path: str,
    payload: dict[str, Any] | None,
    service: Any,
    status: int,
    header: str,
    value: str,
):
    monkeypatch.setenv("INTERNAL_IDENTITY_SECRET", IDENTITY_SECRET)
    app = Flask(__name__)
    blueprint = Blueprint(f"infra_boundary_portfolio_http_{status}", __name__)
    register_common_portfolio_routes(
        blueprint,
        SimpleNamespace(
            paper_trading=service,
            logger=logging.getLogger("test.infra_boundary_errors.portfolio_http"),
        ),
    )
    app.register_blueprint(blueprint, url_prefix="/api")

    response = app.test_client().open(
        path,
        method=method,
        json=payload,
        headers={"X-Auth-Identity": _signed_identity(method=method, path=path)},
    )

    assert response.status_code == status
    assert value in response.headers[header]


def _build_system_deps(**overrides: Any) -> dict[str, Any]:
    deps: dict[str, Any] = {
        "resolve_market_gate_filename": lambda _target_date: "market_gate.json",
        "load_json_file": lambda _filename: {},
        "evaluate_market_gate_validity": lambda **_kwargs: (True, False),
        "apply_market_gate_snapshot_fallback": lambda **kwargs: (kwargs["gate_data"], kwargs["is_valid"]),
        "build_market_gate_empty_payload": lambda: {},
        "normalize_market_gate_payload": lambda payload: payload,
        "execute_market_gate_update": lambda **_kwargs: (200, {}),
        "execute_user_gemini_reanalysis_request": lambda **_kwargs: (200, {}),
        "run_user_gemini_reanalysis": lambda **_kwargs: {},
        "launch_background_update_job": lambda **_kwargs: (200, {}),
        "launch_init_data_update": lambda **_kwargs: (200, {}),
        "build_data_status_payload": lambda **_kwargs: {},
        "get_data_path": lambda filename: filename,
        "load_csv_file": lambda _filename: None,
    }
    deps.update(overrides)
    return deps


def _system_client(monkeypatch: pytest.MonkeyPatch, deps: dict[str, Any]):
    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")
    monkeypatch.setattr(
        system_routes,
        "_resolve_common_update_handlers",
        lambda: (lambda: {"isRunning": False}, lambda _items: None, lambda *_args: None),
    )
    app = Flask(__name__)

    @app.before_request
    def _seed_identity() -> None:
        g.user_api_key = None
        g.user_email = "admin@example.com"

    blueprint = Blueprint("infra_boundary_system", __name__)
    system_routes.register_system_routes(
        blueprint,
        logger=logging.getLogger("test.infra_boundary_errors.system"),
        deps=deps,
    )
    app.register_blueprint(blueprint, url_prefix="/api/kr")
    return app.test_client()


@pytest.mark.parametrize(
    ("path", "payload", "dependency", "expected"),
    [
        ("/api/kr/refresh", {}, "launch_background_update_job", {"status": "error", "message": "Internal Server Error"}),
        ("/api/kr/init-data", {}, "launch_init_data_update", {"status": "error", "message": "Internal Server Error"}),
        ("/api/kr/status", None, "build_data_status_payload", {"status": "error", "message": "Internal Server Error"}),
    ],
)
def test_every_system_custom_error_builder_hides_exception(
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    payload: dict[str, Any] | None,
    dependency: str,
    expected: dict[str, str],
):
    client = _system_client(monkeypatch, _build_system_deps(**{dependency: _raise_canary}))

    response = client.open(path, method="POST" if payload is not None else "GET", json=payload)

    _assert_hidden(response, expected)


def test_reanalyze_route_preserves_non_object_json_for_service_validation(monkeypatch: pytest.MonkeyPatch):
    received: list[Any] = []

    def _record_request(**kwargs: Any) -> tuple[int, dict[str, str]]:
        received.append(kwargs["req_data"])
        return 400, {"status": "error", "error": "INVALID_TARGET_DATES"}

    client = _system_client(
        monkeypatch,
        _build_system_deps(execute_user_gemini_reanalysis_request=_record_request),
    )

    response = client.post("/api/kr/reanalyze/gemini", data="[]", content_type="application/json")

    assert response.status_code == 410
    assert received == []


@pytest.mark.parametrize(
    ("body", "content_type", "status"),
    [("{", "application/json", 400), ("{}", "text/plain", 415)],
)
def test_reanalyze_route_preserves_flask_json_request_errors(
    monkeypatch: pytest.MonkeyPatch,
    body: str,
    content_type: str,
    status: int,
):
    client = _system_client(monkeypatch, _build_system_deps())

    response = client.post("/api/kr/reanalyze/gemini", data=body, content_type=content_type)

    assert response.status_code == 410


def _jongga_client(tmp_path, **overrides: Any):
    deps = {
        "load_json_file": lambda _filename: {"signals": [{"ticker": "005930"}]},
        "launch_jongga_v2_screener": lambda **_kwargs: (200, {}),
        "run_jongga_v2_background_pipeline": lambda **_kwargs: None,
        "execute_single_stock_analysis": lambda **_kwargs: (200, {}),
        "execute_jongga_gemini_reanalysis": lambda **_kwargs: (200, {}),
        "resolve_jongga_message_filename": lambda _target_date: "jongga.json",
        "build_screener_result_for_message": lambda _payload: ({}, 1, "2026-09-20"),
        "select_signals_for_reanalysis": lambda **_kwargs: [],
        "build_jongga_news_analysis_items": lambda _signals: [],
        "apply_gemini_reanalysis_results": lambda **_kwargs: 0,
    }
    deps.update(overrides)
    app = Flask(__name__)
    app.config["TESTING"] = True

    @app.before_request
    def _seed_admin() -> None:
        g.user_email = "admin@example.com"

    blueprint = Blueprint("infra_boundary_jongga", __name__)
    register_jongga_execution_routes(
        blueprint,
        data_dir=str(tmp_path),
        logger=logging.getLogger("test.infra_boundary_errors.jongga"),
        **deps,
    )
    app.register_blueprint(blueprint, url_prefix="/api/kr")
    return app.test_client()


@pytest.mark.parametrize(
    ("path", "dependency", "expected"),
    [
        ("/api/kr/jongga-v2/analyze", "execute_single_stock_analysis", {"error": "Internal Server Error"}),
        ("/api/kr/jongga-v2/message", "build_screener_result_for_message", {"status": "error", "error": "Internal Server Error"}),
    ],
)
def test_every_jongga_custom_error_builder_hides_exception(tmp_path, monkeypatch: pytest.MonkeyPatch, path: str, dependency: str, expected: dict[str, str]):
    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")
    client = _jongga_client(tmp_path, **{dependency: _raise_canary})

    response = client.post(path, json={"code": "005930"})

    _assert_hidden(response, expected)


def _signal_deps(**overrides: Any) -> dict[str, Any]:
    deps: dict[str, Any] = {
        "data_dir_getter": lambda: "/tmp",
        "load_csv_file": lambda _name: __import__("pandas").DataFrame(),
        "get_data_path": lambda name: name,
        "vcp_status": {"running": False, "task_type": None, "cancel_requested": False, "status": "idle", "message": "", "progress": 0},
        "run_vcp_background_pipeline": lambda **_kwargs: None,
        "start_vcp_screener_run": lambda **_kwargs: (200, {}),
        "validate_vcp_reanalysis_source_frame": lambda _df: (None, None),
        "execute_vcp_failed_ai_reanalysis": lambda **_kwargs: (200, {}),
        "update_vcp_ai_cache_files": lambda *_args: 0,
        "build_market_status_payload": lambda **_kwargs: {},
        "build_vcp_signals_payload": lambda **_kwargs: {},
        "filter_signals_dataframe_by_date": lambda **_kwargs: None,
        "build_vcp_signals_from_dataframe": lambda **_kwargs: [],
        "load_latest_vcp_price_map": lambda: {},
        "apply_latest_prices_to_jongga_signals": lambda *_args: 0,
        "sort_and_limit_vcp_signals": lambda *_args, **_kwargs: None,
        "build_ai_data_map": lambda **_kwargs: {},
        "merge_legacy_ai_fields_into_map": lambda **_kwargs: None,
        "merge_ai_data_into_vcp_signals": lambda **_kwargs: None,
        "count_total_scanned_stocks": lambda _data_dir: 0,
        "build_stock_chart_payload": lambda **_kwargs: {},
        "resolve_chart_period_days": lambda _period: 90,
        "fetch_realtime_prices": lambda **_kwargs: {},
        "load_json_file": lambda _filename: {},
    }
    deps.update(overrides)
    return deps


def _signal_client(monkeypatch: pytest.MonkeyPatch, deps: dict[str, Any]):
    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")
    app = Flask(__name__)

    @app.before_request
    def _seed_admin() -> None:
        g.user_email = "admin@example.com"

    blueprint = Blueprint("infra_boundary_signals", __name__)
    register_market_data_signal_routes(
        blueprint,
        logger=logging.getLogger("test.infra_boundary_errors.signals"),
        deps=deps,
    )
    app.register_blueprint(blueprint, url_prefix="/api/kr")
    return app.test_client()


class _FailingStatus(dict[str, Any]):
    def get(self, _key: str, _default: Any = None) -> Any:
        _raise_canary()


@pytest.mark.parametrize(
    ("path", "overrides", "expected"),
    [
        ("/api/kr/signals/run", {"start_vcp_screener_run": _raise_canary}, {"status": "error", "error": "Internal Server Error"}),
        ("/api/kr/signals/reanalyze-failed-ai", {"vcp_status": _FailingStatus()}, {"status": "error", "message": "Internal Server Error"}),
        ("/api/kr/signals/reanalyze-failed-ai/stop", {"vcp_status": _FailingStatus()}, {"status": "error", "message": "Internal Server Error"}),
    ],
)
def test_every_signal_custom_error_builder_hides_exception(
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    overrides: dict[str, Any],
    expected: dict[str, str],
):
    client = _signal_client(monkeypatch, _signal_deps(**overrides))

    response = client.post(path, json={})

    _assert_hidden(response, expected)


class _SynchronousThread:
    """백그라운드 target을 테스트 경계 안에서 끝까지 실행한다."""

    def __init__(self, *, target, daemon: bool) -> None:
        self._target = target
        self.daemon = daemon

    def start(self) -> None:
        self._target()


def test_background_vcp_reanalysis_hides_exception_from_public_status(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    status = {
        "running": False,
        "task_type": None,
        "cancel_requested": False,
        "status": "idle",
        "message": "",
        "progress": 0,
    }
    monkeypatch.setattr(signals_routes.threading, "Thread", _SynchronousThread)
    client = _signal_client(
        monkeypatch,
        _signal_deps(
            vcp_status=status,
            execute_vcp_failed_ai_reanalysis=_raise_canary,
        ),
    )

    with caplog.at_level(logging.ERROR, logger="test.infra_boundary_errors.signals"):
        response = client.post("/api/kr/signals/reanalyze-failed-ai", json={"background": True})

    assert response.status_code == 202
    assert status["status"] == "error"
    assert status["message"] == "실패 AI 재분석 실패"
    assert status["running"] is False
    assert CANARY not in str(status)
    assert CANARY in caplog.text


def _market_mock_client():
    app = Flask(__name__)
    blueprint = Blueprint("infra_boundary_market_mock", __name__)
    register_common_market_mock_routes(
        blueprint,
        SimpleNamespace(logger=logging.getLogger("test.infra_boundary_errors.market_mock")),
    )
    app.register_blueprint(blueprint, url_prefix="/api")
    return app.test_client()


def test_registered_market_mock_route_hides_random_generator_exception(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    monkeypatch.setattr(market_mock_routes.random, "randint", _raise_canary)

    with caplog.at_level(logging.ERROR, logger="test.infra_boundary_errors.market_mock"):
        response = _market_mock_client().get("/api/stock/005930")

    _assert_hidden(response, {"error": "Internal Server Error"})
    assert CANARY in caplog.text


@pytest.mark.parametrize(
    ("body", "content_type", "status"),
    [("{", "application/json", 400), ("{}", "text/plain", 415)],
)
def test_registered_market_mock_realtime_prices_preserves_json_request_errors(
    body: str,
    content_type: str,
    status: int,
):
    response = _market_mock_client().post(
        "/api/realtime-prices",
        data=body,
        content_type=content_type,
    )

    assert response.status_code == status
