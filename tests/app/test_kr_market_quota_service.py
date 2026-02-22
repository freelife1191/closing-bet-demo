#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Quota Service 단위 테스트
"""

from services.kr_market_quota_service import (
    build_quota_info_payload,
    load_quota_data_unlocked,
    resolve_quota_usage_key,
    safe_usage_count,
)


def test_safe_usage_count_normalizes_values():
    assert safe_usage_count(3) == 3
    assert safe_usage_count("5") == 5
    assert safe_usage_count("-4") == 0
    assert safe_usage_count(None) == 0


def test_load_quota_data_unlocked_filters_and_normalizes():
    payload = load_quota_data_unlocked(
        load_json_file=lambda _name: {"u1": "3", "": 10, "u2": -2, "u3": "abc"}
    )
    assert payload == {"u1": 3, "u2": 0, "u3": 0}


def test_resolve_quota_usage_key_prefers_authenticated_email():
    assert resolve_quota_usage_key("user@test.com", "session-a") == "user@test.com"
    assert resolve_quota_usage_key("user@example.com", "session-a") == "session-a"
    assert resolve_quota_usage_key(None, "session-a") == "session-a"


def test_build_quota_info_payload_for_guest_and_existing_usage():
    guest = build_quota_info_payload(
        usage_key=None,
        max_free_usage=10,
        get_user_usage_fn=lambda _key: 0,
        server_key_available=True,
    )
    assert guest["usage"] == 0
    assert guest["remaining"] == 10

    used = build_quota_info_payload(
        usage_key="session-x",
        max_free_usage=10,
        get_user_usage_fn=lambda _key: 7,
        server_key_available=False,
    )
    assert used["usage"] == 7
    assert used["remaining"] == 3
    assert used["is_exhausted"] is False
    assert used["server_key_configured"] is False
