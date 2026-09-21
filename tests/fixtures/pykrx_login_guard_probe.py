#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verify failed KRX logins remain unauthenticated without exposing credentials."""

import contextlib
import io
import json
from unittest.mock import patch

import requests


LOGIN_ID = "login-id-must-not-appear"
LOGIN_PASSWORD = "login-password-must-not-appear"
RESPONSE_BODY = "response-body-must-not-appear"


def response_with_json_error() -> requests.Response:
    response = requests.Response()
    response.status_code = 200
    response._content = f"<html>{RESPONSE_BODY}</html>".encode()
    return response


def response_with_http_error() -> requests.Response:
    response = requests.Response()
    response.status_code = 503
    response._content = f"<html>{RESPONSE_BODY}</html>".encode()
    return response


def response_with_wrong_schema() -> requests.Response:
    response = requests.Response()
    response.status_code = 200
    response._content = b"[]"
    return response


def response_without_error_code() -> requests.Response:
    response = requests.Response()
    response.status_code = 200
    response._content = b"{}"
    return response


def response_with_duplicate_login() -> requests.Response:
    response = requests.Response()
    response.status_code = 200
    response._content = b'{"_error_code":"CD011"}'
    return response


def response_with_success() -> requests.Response:
    response = requests.Response()
    response.status_code = 200
    response._content = b'{"_error_code":"CD001"}'
    return response


def response_with_hostile_redirect() -> requests.Response:
    response = requests.Response()
    response.status_code = 307
    response.headers["Location"] = "https://evil.example/login"
    return response


def main() -> None:
    from pykrx.website.comm import auth

    cases = {
        "non_json": ([response_with_json_error], None, None, "invalid_json", False),
        "http_error": ([response_with_http_error], None, None, "http_error", False),
        "wrong_schema": ([response_with_wrong_schema], None, None, "invalid_schema", False),
        "missing_error_code": ([response_without_error_code], None, None, "invalid_schema", False),
        "network_error": ([], requests.ConnectionError(RESPONSE_BODY), None, "network_error", False),
        "warmup_redirect": ([], None, None, "http_error", False),
        "post_network_error": ([], None, 1, "network_error", False),
        "post_redirect": ([response_with_hostile_redirect], None, None, "http_error", False),
        "duplicate_non_json": ([response_with_duplicate_login, response_with_json_error], None, None, "invalid_json", False),
        "duplicate_http_error": ([response_with_duplicate_login, response_with_http_error], None, None, "http_error", False),
        "duplicate_wrong_schema": ([response_with_duplicate_login, response_with_wrong_schema], None, None, "invalid_schema", False),
        "duplicate_network_error": ([response_with_duplicate_login], None, 2, "network_error", False),
        "success": ([response_with_success], None, None, "", True),
        "duplicate_success": ([response_with_duplicate_login, response_with_success], None, None, "", True),
    }
    observed = []

    for name, (post_responses, get_error, post_failure_call, expected_error, expected_success) in cases.items():
        responses = iter(post_responses)
        post_payloads = []
        request_options = []

        def fake_get(*_args: object, **_kwargs: object) -> requests.Response:
            request_options.append(dict(_kwargs))
            if get_error is not None:
                raise get_error
            if name == "warmup_redirect":
                return response_with_hostile_redirect()
            response = requests.Response()
            response.status_code = 200
            return response

        def fake_post(request_session: requests.Session, *_args: object, **_kwargs: object) -> requests.Response:
            request_session.cookies.set("temporary", LOGIN_PASSWORD)
            post_payloads.append(dict(_kwargs["data"]))
            request_options.append(dict(_kwargs))
            if post_failure_call == len(post_payloads):
                raise requests.ConnectionError(RESPONSE_BODY)
            return next(responses)()

        session = auth.KRXSession(is_authenticated=True, cookies={"old": {"value": LOGIN_PASSWORD}})
        old_session = session.session
        old_session.cookies.set("old_session", LOGIN_PASSWORD)
        captured = io.StringIO()
        with patch.object(requests.Session, "get", autospec=True, side_effect=fake_get), \
                patch.object(requests.Session, "post", autospec=True, side_effect=fake_post), \
                contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
            assert session.refresh(LOGIN_ID, LOGIN_PASSWORD) is expected_success
            assert session.is_authenticated is expected_success
            assert session.last_error == expected_error, name
            if expected_success:
                assert session.cookies["temporary"]["value"] == LOGIN_PASSWORD
            else:
                assert session.cookies == {}
                assert not old_session.cookies
                assert not session.session.cookies
            if name == "non_json":
                responses = iter([response_with_json_error])
                assert auth.build_krx_session(LOGIN_ID, LOGIN_PASSWORD) is None
            if name == "duplicate_success":
                assert "skipDup" not in post_payloads[0]
                assert post_payloads[1]["skipDup"] == "Y"
            assert all(options.get("allow_redirects") is False for options in request_options)
        output = captured.getvalue()
        assert LOGIN_ID not in output
        assert LOGIN_PASSWORD not in output
        assert RESPONSE_BODY not in output
        if name == "non_json":
            assert "invalid_json" in output
        observed.append(name)

    print(json.dumps({"cases": observed}))


if __name__ == "__main__":
    main()
