#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market System HTTP Routes 리팩토링 회귀 테스트
"""

import logging
import os
import sys
from typing import Any

from flask import Blueprint, Flask, g


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import app.routes.kr_market_system_http_routes as system_routes


def _create_client(deps: dict[str, Any], user_api_key: str | None = None, user_email: str | None = None):
    app = Flask(__name__)
    app.testing = True

    @app.before_request
    def _inject_user():
        g.user_api_key = user_api_key
        g.user_email = user_email

    bp = Blueprint("kr_test_system_routes", __name__)
    system_routes.register_system_routes(
        bp,
        logger=logging.getLogger("test.kr_market_system_routes"),
        deps=deps,
    )
    app.register_blueprint(bp, url_prefix="/api/kr")
    return app.test_client()


def _build_base_deps(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "resolve_market_gate_filename": lambda _target_date: "market_gate.json",
        "load_json_file": lambda _filename: {"status": "GREEN"},
        "evaluate_market_gate_validity": lambda gate_data, target_date: (True, False),
        "apply_market_gate_snapshot_fallback": (
            lambda gate_data, is_valid, target_date, load_json_file, logger: (gate_data, is_valid)
        ),
        "build_market_gate_empty_payload": lambda: {"status": "EMPTY"},
        "normalize_market_gate_payload": lambda payload: payload,
        "execute_market_gate_update": lambda target_date, logger: (200, {"status": "success"}),
        "execute_user_gemini_reanalysis_request": (
            lambda user_api_key, user_email, req_data, usage_tracker, logger, run_reanalysis_func: (
                200,
                {"status": "success"},
            )
        ),
        "run_user_gemini_reanalysis": lambda **_kwargs: {"count": 1},
        "launch_background_update_job": (
            lambda items_list, target_date, load_update_status, start_update, run_background_update, logger: (
                200,
                {"status": "started", "items": items_list, "target_date": target_date},
            )
        ),
        "launch_init_data_update": (
            lambda data_type, target_date, load_update_status, start_update, run_background_update, logger: (
                200,
                {"status": "started", "type": data_type, "target_date": target_date},
            )
        ),
        "build_data_status_payload": lambda get_data_path, load_csv_file, load_json_file: {"ok": True},
        "get_data_path": lambda filename: filename,
        "load_csv_file": lambda _filename: None,
    }
    base.update(overrides)
    return base


def test_market_gate_invalid_get_is_read_only_without_refresh_dependency():
    deps = _build_base_deps(evaluate_market_gate_validity=lambda gate_data, target_date: (False, True))
    client = _create_client(deps)
    for url in ["/api/kr/market-gate", "/api/kr/market-gate", "/api/kr/market-gate?date=2026-09-01"]:
        response = client.get(url)
        assert response.status_code == 200
        assert response.get_json()["status"] == "EMPTY"


def test_market_gate_stale_valid_get_preserves_saved_payload():
    client = _create_client(_build_base_deps(evaluate_market_gate_validity=lambda gate_data, target_date: (True, True)))
    response = client.get("/api/kr/market-gate")
    assert response.status_code == 200
    assert response.get_json()["status"] == "GREEN"


def test_retired_gemini_does_not_call_former_dependency():
    deps = _build_base_deps(
        execute_user_gemini_reanalysis_request=(
            lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("boom"))
        )
    )
    client = _create_client(deps, user_api_key="test-key", user_email="tester@example.com")

    response = client.post("/api/kr/reanalyze/gemini", json={})

    assert response.status_code == 410
    assert response.get_json()["code"] == "LEGACY_ANALYSIS_RETIRED"


def test_refresh_route_uses_common_update_handlers_and_adds_success_message(monkeypatch):
    expected_handles = {
        "load": lambda: {"isRunning": False},
        "start": lambda _items: None,
        "run": lambda _target, _items, _force=False: None,
    }
    monkeypatch.setattr(
        system_routes,
        "_resolve_common_update_handlers",
        lambda: (expected_handles["load"], expected_handles["start"], expected_handles["run"]),
    )

    def _launch(items_list, target_date, load_update_status, start_update, run_background_update, logger):
        assert load_update_status is expected_handles["load"]
        assert start_update is expected_handles["start"]
        assert run_background_update is expected_handles["run"]
        return 200, {"status": "started", "items": items_list, "target_date": target_date}

    deps = _build_base_deps(launch_background_update_job=_launch)
    # [INFRA-059] 가 이 라우트에 require_admin 을 붙였다. 신원을 심지 않으면 403 이라
    # 아래 배선 검사가 시작조차 하지 못한다. 게이트 자체는
    # tests/app/test_admin_gated_routes.py 가 잰다.
    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")
    client = _create_client(deps, user_email="admin@example.com")

    response = client.post("/api/kr/refresh", json={"target_date": "2026-02-20"})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "started"
    assert payload["items"] == ["Market Gate", "AI Analysis"]
    assert payload["message"] == "데이터 갱신 작업이 백그라운드에서 시작되었습니다."


def test_status_route_returns_error_payload_when_builder_fails():
    deps = _build_base_deps(
        build_data_status_payload=lambda get_data_path, load_csv_file, load_json_file: (
            (_ for _ in ()).throw(RuntimeError("status failed"))
        )
    )
    client = _create_client(deps)

    response = client.get("/api/kr/status")

    assert response.status_code == 500
    assert response.get_json() == {"status": "error", "message": "Internal Server Error"}


def test_invalid_market_gate_date_is_rejected_before_any_file_load():
    from services.kr_market_market_gate_validity import resolve_market_gate_filename
    loaded = []
    deps = _build_base_deps(
        resolve_market_gate_filename=resolve_market_gate_filename,
        load_json_file=lambda filename: loaded.append(filename) or {"status": "GREEN"},
    )
    client = _create_client(deps)
    for date in ["../../../private", "2026/09/21", "2026-02-30", "20260230", "2026-9-21", "", "2026-09-21.json", "２０２６０９２１"]:
        response = client.get("/api/kr/market-gate", query_string={"date": date})
        assert response.status_code == 400
    assert loaded == []
