#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""종가베팅 메시지 요청이 인증 뒤 JSON 객체 경계를 지키는지 검사한다."""

from __future__ import annotations

import base64
import hashlib
import hmac
import io
import json
from pathlib import Path
from typing import Any

import pytest
from flask import Blueprint, Flask

from app import _register_request_context
from app.routes.kr_market_jongga_execution_routes import _register_jongga_message_route


PATH = "/api/kr/jongga-v2/message"
IDENTITY_SECRET = "jongga-message-boundary-fixture-secret"
ADMIN_EMAIL = "admin@example.test"
USER_EMAIL = "user@example.test"
INPUT_SENTINEL = "입력-비반사-비밀-테스트"


class _Logger:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def error(self, message: object) -> None:
        self.errors.append(str(message))


def _identity_headers(email: str, *, method: str = "POST") -> dict[str, str]:
    encoded_email = base64.urlsafe_b64encode(email.encode("utf-8")).decode("ascii").rstrip("=")
    prefix = f"v2.{encoded_email}.4000000000"
    encoded_path = base64.urlsafe_b64encode(PATH.encode("utf-8")).decode("ascii").rstrip("=")
    signing_input = f"{prefix}.{method}.{encoded_path}"
    mac = hmac.new(
        IDENTITY_SECRET.encode("utf-8"),
        signing_input.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return {"X-Auth-Identity": f"{prefix}.{mac}"}


def _guard_snapshot(data_dir: Path) -> dict[str, str]:
    return {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted(data_dir.glob("jongga_notification_sent.*"))
    }


@pytest.fixture
def message_app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, Any]:
    monkeypatch.setenv("INTERNAL_IDENTITY_SECRET", IDENTITY_SECRET)
    monkeypatch.setenv("ADMIN_EMAILS", ADMIN_EMAIL)

    logger = _Logger()
    counters = {"load": 0, "construct": 0, "send": 0}
    delivery_outcomes: list[Exception | None] = []
    resolved_target_dates: list[str | None] = []

    def load_json_file(_filename: str, **_kwargs: object) -> dict[str, object]:
        counters["load"] += 1
        return {"signals": [{"stock_code": "005930", "stock_name": "삼성전자"}]}

    def build_screener_result_for_message(
        _file_data: dict[str, object],
    ) -> tuple[dict[str, bool], int, str]:
        return {"ready": True}, 1, "2026-09-08"

    def resolve_jongga_message_filename(target_date: str | None) -> str:
        resolved_target_dates.append(target_date)
        return "fixture.json"

    class _FakeMessenger:
        def __init__(self) -> None:
            counters["construct"] += 1

        def send_screener_result(self, _result: object) -> None:
            counters["send"] += 1
            if delivery_outcomes:
                outcome = delivery_outcomes.pop(0)
                if outcome is not None:
                    raise outcome

    import engine.messenger as messenger_module

    monkeypatch.setattr(messenger_module, "Messenger", _FakeMessenger)

    app = Flask(__name__)
    app.testing = True
    _register_request_context(app)
    blueprint = Blueprint("jongga_message_boundary", __name__)
    _register_jongga_message_route(
        blueprint,
        data_dir=str(tmp_path),
        logger=logger,
        load_json_file=load_json_file,
        resolve_jongga_message_filename=resolve_jongga_message_filename,
        build_screener_result_for_message=build_screener_result_for_message,
    )
    app.register_blueprint(blueprint, url_prefix="/api/kr")
    return {
        "client": app.test_client(),
        "counters": counters,
        "data_dir": tmp_path,
        "delivery_outcomes": delivery_outcomes,
        "logger": logger,
        "resolved_target_dates": resolved_target_dates,
    }


def _assert_no_message_side_effects(message_app: dict[str, Any], before_guard: dict[str, str]) -> None:
    assert message_app["counters"] == {"load": 0, "construct": 0, "send": 0}
    assert _guard_snapshot(message_app["data_dir"]) == before_guard


@pytest.mark.parametrize(
    ("data", "content_type"),
    [
        ({"force": "true"}, "application/x-www-form-urlencoded"),
        ({"file": (io.BytesIO(b"{}"), "body.txt")}, "multipart/form-data"),
        ("{}", "text/plain"),
        (b"{}", None),
    ],
)
def test_non_json_admin_requests_are_rejected_before_message_work(
    message_app: dict[str, Any],
    data: object,
    content_type: str | None,
) -> None:
    before_guard = _guard_snapshot(message_app["data_dir"])
    response = message_app["client"].post(
        PATH,
        data=data,
        content_type=content_type,
        headers=_identity_headers(ADMIN_EMAIL),
    )

    assert response.status_code == 415
    assert response.get_json() == {
        "status": "error",
        "error": "JSON 요청 본문이 필요합니다.",
    }
    _assert_no_message_side_effects(message_app, before_guard)


@pytest.mark.parametrize(
    ("body", "expected_error"),
    [
        ("", "올바른 JSON 객체가 필요합니다."),
        ("{", "올바른 JSON 객체가 필요합니다."),
        (f'{{"payload":"{INPUT_SENTINEL}' + "x" * 131_072, "올바른 JSON 객체가 필요합니다."),
        ("null", "JSON 객체가 필요합니다."),
        ("[]", "JSON 객체가 필요합니다."),
        ("[1]", "JSON 객체가 필요합니다."),
        ('""', "JSON 객체가 필요합니다."),
        ('"text"', "JSON 객체가 필요합니다."),
        ("0", "JSON 객체가 필요합니다."),
        ("1", "JSON 객체가 필요합니다."),
        ("42", "JSON 객체가 필요합니다."),
        ("false", "JSON 객체가 필요합니다."),
        ("true", "JSON 객체가 필요합니다."),
    ],
)
def test_invalid_json_admin_requests_are_rejected_without_reflecting_input(
    message_app: dict[str, Any],
    body: str,
    expected_error: str,
) -> None:
    before_guard = _guard_snapshot(message_app["data_dir"])
    response = message_app["client"].post(
        PATH,
        data=body,
        content_type="application/json",
        headers=_identity_headers(ADMIN_EMAIL),
    )

    assert response.status_code == 400
    assert response.get_json() == {"status": "error", "error": expected_error}
    assert INPUT_SENTINEL not in response.get_data(as_text=True)
    assert all(INPUT_SENTINEL not in entry for entry in message_app["logger"].errors)
    _assert_no_message_side_effects(message_app, before_guard)


@pytest.mark.parametrize(
    ("payload", "content_type"),
    [
        ({}, "application/json"),
        ({"target_date": "2026-09-08"}, "application/json; charset=utf-8"),
        ({"target_date": None}, "application/vnd.smart-money+json"),
        ({"force": False}, "application/json"),
        ({"force": True}, "application/json"),
    ],
)
def test_json_object_admin_requests_reach_message_work(
    message_app: dict[str, Any],
    payload: dict[str, object],
    content_type: str,
) -> None:
    response = message_app["client"].post(
        PATH,
        data=json.dumps(payload),
        content_type=content_type,
        headers=_identity_headers(ADMIN_EMAIL),
    )

    assert response.status_code == 200
    assert response.get_json()["status"] == "success"
    assert message_app["counters"] == {"load": 1, "construct": 1, "send": 1}
    assert message_app["resolved_target_dates"] == [payload.get("target_date")]


@pytest.mark.parametrize("headers", [{}, _identity_headers(USER_EMAIL)])
@pytest.mark.parametrize(
    ("body", "content_type"),
    [({"force": "true"}, "application/x-www-form-urlencoded"), ("{", "application/json")],
)
def test_authorization_runs_before_message_json_parsing(
    message_app: dict[str, Any],
    headers: dict[str, str],
    body: object,
    content_type: str,
) -> None:
    before_guard = _guard_snapshot(message_app["data_dir"])
    response = message_app["client"].post(
        PATH,
        data=body,
        content_type=content_type,
        headers=headers,
    )

    assert response.status_code == 403
    assert response.get_json() == {"error": "Forbidden"}
    _assert_no_message_side_effects(message_app, before_guard)


def test_options_does_not_require_identity_or_start_message_work(message_app: dict[str, Any]) -> None:
    before_guard = _guard_snapshot(message_app["data_dir"])
    response = message_app["client"].options(PATH)

    assert response.status_code == 200
    assert "POST" in (response.headers.get("Allow") or "")
    _assert_no_message_side_effects(message_app, before_guard)


def test_duplicate_and_force_keep_existing_message_delivery_behavior(message_app: dict[str, Any]) -> None:
    headers = _identity_headers(ADMIN_EMAIL)
    first = message_app["client"].post(PATH, json={"target_date": "2026-09-08"}, headers=headers)
    duplicate = message_app["client"].post(PATH, json={"target_date": "2026-09-08"}, headers=headers)
    forced = message_app["client"].post(
        PATH,
        json={"target_date": "2026-09-08", "force": True},
        headers=headers,
    )

    assert first.get_json()["status"] == "success"
    assert duplicate.get_json() == {
        "status": "skipped",
        "message": "이미 발송된 종가베팅 메시지입니다. (2026-09-08)",
        "target_date": "2026-09-08",
        "duplicate": True,
    }
    assert forced.get_json()["status"] == "success"
    assert message_app["counters"] == {"load": 3, "construct": 2, "send": 2}


def test_delivery_failure_releases_claim_for_a_retry(message_app: dict[str, Any]) -> None:
    message_app["delivery_outcomes"].extend([RuntimeError("fixture delivery failed"), None])
    headers = _identity_headers(ADMIN_EMAIL)
    failed = message_app["client"].post(PATH, json={}, headers=headers)
    retried = message_app["client"].post(PATH, json={}, headers=headers)

    assert failed.status_code == 500
    assert failed.get_json() == {"status": "error", "error": "Internal Server Error"}
    assert retried.status_code == 200
    assert retried.get_json()["status"] == "success"
    assert message_app["counters"] == {"load": 2, "construct": 2, "send": 2}
    state = json.loads((message_app["data_dir"] / "jongga_notification_sent.json").read_text("utf-8"))
    assert state["records"]["2026-09-08:daily"]["status"] == "sent"
