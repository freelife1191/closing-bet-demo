#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""INFRA-028 target_dates 계약의 RED 테스트."""

from __future__ import annotations

import logging
import os
import sys

import pytest


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from services import kr_market_route_service as route_service


def test_parse_target_dates_accepts_scalar_and_preserves_list_order_duplicates():
    assert route_service.parse_target_dates({"target_dates": " 2024-02-29 "}) == [
        "2024-02-29"
    ]
    assert route_service.parse_target_dates(
        {"target_dates": ["2024-02-29", "2024-02-29", "2024-02-28"]}
    ) == ["2024-02-29", "2024-02-29", "2024-02-28"]


@pytest.mark.parametrize(
    "value",
    [
        "2023-02-29",
        "2024-02-30",
        "2024/02/29",
        "20240229",
        "2024-2-9",
        "2024-02-29\nsecret",
        "2024-０２-２９",
        "",
    ],
)
def test_parse_target_dates_rejects_invalid_scalar_values(value):
    with pytest.raises(ValueError, match="INVALID_TARGET_DATES"):
        route_service.parse_target_dates({"target_dates": value})


def test_parse_target_dates_rejects_invalid_items_instead_of_dropping_them():
    with pytest.raises(ValueError, match="INVALID_TARGET_DATES"):
        route_service.parse_target_dates(
            {"target_dates": ["2024-02-29", "", None]}
        )


def test_parse_target_dates_keeps_scalar_null_as_full_range_compatibility():
    assert route_service.parse_target_dates({"target_dates": None}) == []


def test_parse_target_dates_rejects_more_than_thirty_raw_items():
    with pytest.raises(ValueError, match="INVALID_TARGET_DATES"):
        route_service.parse_target_dates(
            {"target_dates": ["2024-02-01"] * 31}
        )


def test_parse_target_dates_allows_thirty_raw_items():
    dates = [f"2024-02-{day:02d}" for day in range(1, 29)] + [
        "2024-03-01",
        "2024-03-02",
    ]
    assert len(dates) == 30
    assert route_service.parse_target_dates({"target_dates": dates}) == dates


@pytest.mark.parametrize("body", [[], 42, "x"])
def test_parse_target_dates_rejects_non_object_body(body):
    with pytest.raises(ValueError, match="INVALID_TARGET_DATES"):
        route_service.parse_target_dates(body)


def test_parse_target_dates_keeps_missing_and_empty_list_compatibility():
    assert route_service.parse_target_dates({}) == []
    assert route_service.parse_target_dates({"target_dates": []}) == []


class _Tracker:
    def __init__(self):
        self.calls = 0

    def check_and_increment(self, _email):
        self.calls += 1
        return True


def test_invalid_dates_return_400_before_quota_or_runner():
    tracker = _Tracker()
    runner_calls = []

    def runner(**kwargs):
        runner_calls.append(kwargs)
        return {"count": 1}

    status, payload = route_service.execute_user_gemini_reanalysis_request(
        user_api_key=None,
        user_email="synthetic@example.test",
        req_data={"target_dates": ["2024-02-30"]},
        usage_tracker=tracker,
        logger=logging.getLogger("test-infra-028"),
        run_reanalysis_func=runner,
    )

    assert status == 400
    assert payload["code"] == "INVALID_TARGET_DATES"
    assert tracker.calls == 0
    assert runner_calls == []
