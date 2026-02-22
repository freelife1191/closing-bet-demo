#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market interval HTTP service 단위 테스트
"""

from __future__ import annotations

from services.kr_market_interval_http_service import handle_interval_config_request


def test_handle_interval_config_request_get_returns_current_interval():
    status, payload = handle_interval_config_request(
        method="GET",
        req_data={},
        current_interval=30,
        apply_interval_fn=lambda _v: None,
        persist_interval_fn=lambda _v: None,
    )
    assert status == 200
    assert payload == {"interval": 30}


def test_handle_interval_config_request_post_validates_and_applies():
    applied = {"interval": None, "persisted": None}

    def _apply(value: int):
        applied["interval"] = value

    def _persist(value: int):
        applied["persisted"] = value

    status, payload = handle_interval_config_request(
        method="POST",
        req_data={"interval": "15"},
        current_interval=30,
        apply_interval_fn=_apply,
        persist_interval_fn=_persist,
    )
    assert status == 200
    assert payload["interval"] == 15
    assert applied == {"interval": 15, "persisted": 15}


def test_handle_interval_config_request_post_rejects_invalid_values():
    status_a, payload_a = handle_interval_config_request(
        method="POST",
        req_data={"interval": "abc"},
        current_interval=30,
        apply_interval_fn=lambda _v: None,
        persist_interval_fn=lambda _v: None,
    )
    status_b, payload_b = handle_interval_config_request(
        method="POST",
        req_data={"interval": 0},
        current_interval=30,
        apply_interval_fn=lambda _v: None,
        persist_interval_fn=lambda _v: None,
    )
    assert status_a == 400
    assert payload_a["error"] == "Invalid interval"
    assert status_b == 400
    assert payload_b["error"] == "Invalid interval"

