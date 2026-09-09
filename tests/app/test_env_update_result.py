#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""INFRA-051: 버린 값이 저장 성공으로 보고되지 않는다."""

import json
import logging
from unittest.mock import Mock

import pytest
from flask import Blueprint, Flask

from app.routes import common_update_routes
from app.routes.common_route_context import CommonRouteContext
from services.common_env_service import update_env_file


def test_partial_save_reports_keys_without_values(tmp_path):
    path = tmp_path / ".env"
    path.write_text("SMTP_USER=old\nSMTP_PASSWORD=original\n")
    environ = {}
    result = update_env_file(str(path), {
        "SMTP_USER": "PRIVATE_VALUE\nINJECTED=true", "SMTP_PORT": "587",
        "ADMIN_API_TOKEN": "PRIVATE_VALUE", "SMTP_PASSWORD": "********",
    }, environ)
    assert result == {"applied": ["SMTP_PORT"], "removed": [],
                      "preserved": ["SMTP_PASSWORD"], "rejected": {
                          "SMTP_USER": "unsafe_value", "ADMIN_API_TOKEN": "unsupported_key"}}
    assert "PRIVATE_VALUE" not in str(result)
    assert environ == {"SMTP_PORT": "587"}
    assert path.read_text() == "SMTP_USER=old\nSMTP_PASSWORD=original\nSMTP_PORT=587\n"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_API_TOKEN", "test-only-admin")
    monkeypatch.setattr(common_update_routes, "resolve_env_path", lambda: str(tmp_path / ".env"))
    # 실제 전역 환경 대신 요청 워커의 환경 역할을 하는 독립 mapping.
    monkeypatch.setattr(common_update_routes, "update_env_file",
                        lambda path, data, _env: update_env_file(path, data, {}))
    context = Mock(spec=CommonRouteContext)
    context.logger = logging.getLogger("env-result-contract")
    app = Flask(__name__)
    bp = Blueprint("env-result", __name__)
    common_update_routes._register_manage_env_route(bp, context)
    app.register_blueprint(bp, url_prefix="/api")
    return app.test_client()


@pytest.mark.parametrize("data", [["SMTP_USER"], "SMTP_USER=x", True, 42, None, [], "", 0])
def test_non_object_request_is_rejected(client, data):
    response = client.post("/api/system/env", data=json.dumps(data), content_type="application/json",
                           headers={"X-Admin-Token": "test-only-admin"})
    assert response.status_code == 400


@pytest.mark.parametrize("data,expected", [
    ({"SMTP_HOST": "valid"}, 200),
    ({"SMTP_HOST": "x\ny", "SMTP_PORT": "587"}, 400),
    ({"SMTP_HOST": None}, 400),
    ({"SMTP_HOST": {"private": "value"}}, 400),
    ({"ADMIN_API_TOKEN": "secret"}, 400),
])
def test_route_propagates_validation_result(client, data, expected):
    response = client.post("/api/system/env", json=data, headers={"X-Admin-Token": "test-only-admin"})
    assert response.status_code == expected
    assert response.json["status"] == ("ok" if expected == 200 else "error")
    assert "secret" not in response.get_data(as_text=True)
    if expected == 400:
        assert response.json["rejected"]


def test_empty_request_is_success_without_writes(client, tmp_path):
    response = client.post("/api/system/env", json={}, headers={"X-Admin-Token": "test-only-admin"})
    assert response.status_code == 200
    assert not (tmp_path / ".env").exists()


@pytest.mark.parametrize("body,content_type,status", [
    ('{"SMTP_HOST":', 'application/json', 400),
    ('SMTP_HOST=x', 'application/x-www-form-urlencoded', 415),
])
def test_invalid_json_is_an_explicit_client_error(client, tmp_path, body, content_type, status):
    response = client.post('/api/system/env', data=body, content_type=content_type,
                           headers={'X-Admin-Token': 'test-only-admin'})
    assert response.status_code == status
    assert not (tmp_path / '.env').exists()


def test_io_failure_is_not_success_and_does_not_expose_exception(client, monkeypatch, caplog, tmp_path):
    def fail_write(*args):
        raise OSError('PRIVATE_ERROR_CANARY')

    monkeypatch.setattr('services.common_env_service.atomic_write_text', fail_write)
    response = client.post('/api/system/env', json={'SMTP_HOST': 'valid'},
                           headers={'X-Admin-Token': 'test-only-admin'})
    assert response.status_code == 500
    assert response.get_json() == {'status': 'error', 'message': 'Settings could not be saved'}
    assert 'PRIVATE_ERROR_CANARY' not in response.get_data(as_text=True) + caplog.text
    assert not (tmp_path / '.env').exists()


def test_result_distinguishes_absent_key_deletion_and_mask_preservation(tmp_path):
    path = tmp_path / '.env'
    path.write_text('SMTP_PASSWORD=original\n')
    environ = {'SMTP_USER': 'stale'}
    result = update_env_file(str(path), {'SMTP_USER': '', 'SMTP_PASSWORD': '********'}, environ)
    assert result == {'applied': [], 'removed': ['SMTP_USER'], 'preserved': ['SMTP_PASSWORD'], 'rejected': {}}
    assert 'SMTP_USER' not in environ
    assert path.read_text() == 'SMTP_PASSWORD=original\n'
