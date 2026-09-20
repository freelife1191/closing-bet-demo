#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""INFRA-028·066 경계 fixture의 scratch 전용 계약을 검증한다."""

from __future__ import annotations

import importlib.util
import json
import logging
from pathlib import Path
from types import ModuleType
from typing import Any

from flask import Blueprint, Flask, g

from app.routes.kr_market_system_http_routes import _register_reanalyze_gemini_route
from services.kr_market_route_service import execute_user_gemini_reanalysis_request
from services import usage_tracker as usage_tracker_module


def _load_fixture(repo: Path) -> ModuleType:
    fixture_path = repo / "docs/dev-cycle/evidence/infra-boundaries-20260920/fixture.py"
    spec = importlib.util.spec_from_file_location("infra_boundaries_fixture", fixture_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _actual_user_reanalysis_probe() -> None:
    """실제 등록 라우트의 날짜·quota·runner 순서를 합성 outer boundary로 확인한다."""
    app = Flask("infra-boundaries-user-route")
    calls: list[dict[str, Any]] = []

    class SyntheticTracker:
        def __init__(self) -> None:
            self.calls = 0

        def check_and_increment(self, _email: str) -> bool:
            self.calls += 1
            return True

    tracker = SyntheticTracker()

    @app.before_request
    def install_fake_identity() -> None:
        g.user_api_key = None
        g.user_email = "fixture@example.test"

    blueprint = Blueprint("infra-boundaries-user-reanalysis", __name__)
    _register_reanalyze_gemini_route(
        blueprint,
        logger=logging.getLogger(__name__),
        deps={
            "execute_user_gemini_reanalysis_request": execute_user_gemini_reanalysis_request,
            "run_user_gemini_reanalysis": lambda **kwargs: calls.append(kwargs) or {"count": 1},
        },
    )
    app.register_blueprint(blueprint, url_prefix="/api/kr")
    client = app.test_client()
    original_tracker = usage_tracker_module.usage_tracker
    usage_tracker_module.usage_tracker = tracker
    try:
        def assert_rejected(response: Any, expected_status: int) -> None:
            assert response.status_code == expected_status
            assert calls == [] and tracker.calls == 0

        for body in [
            [], None, False, 42,
            {"target_dates": ["2023-02-29"]},
            {"target_dates": ["2024-02-30"]},
            {"target_dates": ["2024-０２-２９"]},
            {"target_dates": ["../2024-02-29"]},
            {"target_dates": ["x" * 100_000]},
            {"target_dates": ["2024-02-29"] * 31},
        ]:
            response = client.post(
                "/api/kr/reanalyze/gemini",
                data=json.dumps(body),
                content_type="application/json",
            )
            assert_rejected(response, 400)
            assert response.content_type.startswith("application/json")

        malformed_json = client.post("/api/kr/reanalyze/gemini", data=b"{", content_type="application/json")
        assert_rejected(malformed_json, 400)
        assert malformed_json.content_type.startswith("text/html")
        wrong_content_type = client.post("/api/kr/reanalyze/gemini", data=b"{}", content_type="text/plain")
        assert_rejected(wrong_content_type, 415)
        assert wrong_content_type.content_type.startswith("text/html")

        thirty_dates = [f"2024-02-{day:02d}" for day in range(1, 29)] + ["2024-03-01", "2024-03-02"]
        for body, expected_dates in [
            ({}, []),
            ({"target_dates": None}, []),
            ({"target_dates": []}, []),
            ({"target_dates": thirty_dates}, thirty_dates),
        ]:
            response = client.post("/api/kr/reanalyze/gemini", json=body)
            assert response.status_code == 200 and response.json["status"] == "success"
            assert calls[-1] == {"target_dates": expected_dates, "api_key": None}
        assert tracker.calls == len(calls) == 4
    finally:
        usage_tracker_module.usage_tracker = original_tracker
    print(json.dumps({"reanalysis_valid_runs": len(calls), "quota_calls": tracker.calls}))


def main() -> None:
    repo = Path.cwd()
    fixture = _load_fixture(repo)
    app = fixture.build_app(repo, reset_log=True)
    client = app.test_client()

    for path in [
        "/api/auth/session", "/api/kr/config/interval", "/api/kr/status", "/api/kr/backtest-summary", "/api/kr/closing-bet/cumulative",
        "/api/admin/check",
        "/api/system/env",
        "/api/kr/user/quota",
        "/api/kr/jongga-v2/latest",
        "/api/kr/signals",
        "/api/portfolio",
        "/api/system/data-status",
    ]:
        response = client.get(path)
        assert response.status_code == 200, (path, response.status_code)
        assert response.is_json, path

    for path in [
        "/api/auth/signout",
        "/api/auth/signin/google",
        "/api/system/env",
        "/api/portfolio/buy",
        "/api/kr/chatbot",
    ]:
        response = client.post(path)
        assert response.status_code == 405, (path, response.status_code)

    assert client.post("/__qa/control", json={"mode": "normal"}).status_code == 200
    assert client.get("/api/admin/check").json["isAdmin"] is False
    print("fixture required GET, fake auth, and mutation boundaries PASS")

    assert client.post("/__qa/control", json={"mode": "d-only"}).status_code == 200
    response = client.get("/api/kr/jongga-v2/latest").json
    assert len(response["signals"]) == 1 and response["signals"][0]["grade"] == "D"

    assert client.post("/__qa/control", json={"mode": "zero"}).status_code == 200
    response = client.get("/api/kr/stock-detail/005930").json
    assert "investorTrend5Day" not in response
    assert response["investorTrend"] == {"institution": 0, "individual": 0}

    assert client.post("/__qa/control", json={"mode": "admin", "price_mode": "success"}).status_code == 200
    response = client.post("/api/kr/realtime-prices", json={"tickers": ["005930"]})
    assert response.status_code == 200 and response.json["prices"]["005930"] == 76_200
    assert client.post("/__qa/control", json={"price_mode": "error"}).status_code == 200
    response = client.post("/api/kr/realtime-prices", json={"tickers": ["005930"]})
    assert response.status_code == 503 and response.json["error"] == "합성 현재가 조회 실패"

    for refresh_path in ["/api/kr/market-gate/update"]:
        assert client.post("/__qa/control", json={"refresh_mode": "success"}).status_code == 200
        response = client.post(refresh_path, json={"target_date": "2026-09-20"})
        assert response.status_code == 200 and response.json["source"] == "synthetic-ui-fixture"
        assert client.post("/__qa/control", json={"refresh_mode": "error-500"}).status_code == 200
        response = client.post(refresh_path, json={"target_date": "2026-09-20"})
        assert response.status_code == 500 and response.is_json
        assert client.post("/__qa/control", json={"refresh_mode": "html-500"}).status_code == 200
        response = client.post(refresh_path, json={"target_date": "2026-09-20"})
        assert response.status_code == 500 and response.mimetype == "text/html"
        assert client.post("/__qa/control", json={"refresh_mode": "forbidden"}).status_code == 200
        response = client.post(refresh_path, json={"target_date": "2026-09-20"})
        assert response.status_code == 403 and response.is_json
    timeout_control = client.post("/__qa/control", json={"refresh_mode": "timeout"})
    assert timeout_control.status_code == 200 and timeout_control.json["refresh_mode"] == "timeout"
    assert client.post("/__qa/control", json={"refresh_mode": "success"}).status_code == 200
    response = client.post("/api/kr/refresh", json={})
    assert response.status_code == 200 and response.json["source"] == "registered-route-fixture"
    assert client.post("/__qa/control", json={"refresh_mode": "error-500"}).status_code == 200
    response = client.post("/api/kr/refresh", json={})
    assert response.status_code == 500 and b"/private/infra-boundary-sentinel" not in response.data
    print("registered refresh success/error boundary PASS")

    assert client.post("/__qa/control", json={"portfolio_mode": "success"}).status_code == 200
    response = client.get("/api/portfolio")
    assert response.status_code == 200 and response.json["cash"] == 91_060_000
    assert client.post("/__qa/control", json={"portfolio_mode": "error-500"}).status_code == 200
    response = client.get("/api/portfolio")
    assert response.status_code == 500 and b"/private/infra-boundary-sentinel" not in response.data
    _actual_user_reanalysis_probe()
    print("registered portfolio and user reanalysis API boundary PASS")



if __name__ == "__main__":
    main()
