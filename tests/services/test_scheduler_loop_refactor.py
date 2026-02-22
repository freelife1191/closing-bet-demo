#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scheduler loop 유틸리티 테스트
"""

from __future__ import annotations

from services.scheduler_loop import compute_scheduler_sleep_seconds


def test_compute_scheduler_sleep_seconds_uses_default_for_none():
    assert compute_scheduler_sleep_seconds(None) == 1.0


def test_compute_scheduler_sleep_seconds_clamps_to_minimum():
    assert compute_scheduler_sleep_seconds(-3.0) == 0.2
    assert compute_scheduler_sleep_seconds(0.01) == 0.2


def test_compute_scheduler_sleep_seconds_clamps_to_maximum():
    assert compute_scheduler_sleep_seconds(100.0) == 5.0


def test_compute_scheduler_sleep_seconds_keeps_valid_value():
    assert compute_scheduler_sleep_seconds(2.5) == 2.5
