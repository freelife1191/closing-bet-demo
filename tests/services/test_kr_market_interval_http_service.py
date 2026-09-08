#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market interval HTTP service 단위 테스트
"""

from __future__ import annotations

import pytest

from services.kr_market_interval_http_service import handle_interval_config_request


def test_handle_interval_config_request_get_returns_current_interval():
    calls: list[int] = []
    status, payload = handle_interval_config_request(
        method="GET",
        req_data={},
        current_interval=30,
        set_interval_fn=calls.append,
    )
    assert status == 200
    assert payload == {"interval": 30}
    assert calls == []


def test_handle_interval_config_request_post_validates_and_sets_once():
    applied: list[int] = []

    status, payload = handle_interval_config_request(
        method="POST",
        req_data={"interval": "15"},
        current_interval=30,
        set_interval_fn=applied.append,
    )
    assert status == 200
    assert payload["interval"] == 15
    assert applied == [15]


@pytest.mark.parametrize(
    "invalid_interval",
    ["abc", 0, -1, 1441, 10**100, None, [], {}, "../15", "오류", float("inf"), float("nan")],
)
def test_handle_interval_config_request_post_rejects_invalid_values(invalid_interval):
    calls: list[int] = []
    status, payload = handle_interval_config_request(
        method="POST",
        req_data={"interval": invalid_interval},
        current_interval=30,
        set_interval_fn=calls.append,
    )
    assert status == 400
    assert payload["error"] == "Invalid interval"
    assert calls == []


@pytest.mark.parametrize("interval", [1, 1440])
def test_handle_interval_config_request_accepts_interval_boundaries(interval: int):
    calls: list[int] = []

    status, payload = handle_interval_config_request(
        method="POST",
        req_data={"interval": interval},
        current_interval=30,
        set_interval_fn=calls.append,
    )

    assert status == 200
    assert payload["interval"] == interval
    assert calls == [interval]


def test_handle_interval_config_request_propagates_set_callback_failure():
    def _set_fails(_value: int) -> None:
        raise RuntimeError("persist failed")

    with pytest.raises(RuntimeError, match="persist failed"):
        handle_interval_config_request(
            method="POST",
            req_data={"interval": 15},
            current_interval=30,
            set_interval_fn=_set_fails,
        )
