#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scheduler loop 유틸리티.
"""

from __future__ import annotations


def compute_scheduler_sleep_seconds(
    idle_seconds: float | None,
    *,
    min_sleep: float = 0.2,
    max_sleep: float = 5.0,
    default_sleep: float = 1.0,
) -> float:
    """schedule.idle_seconds() 기반으로 다음 sleep 시간을 계산한다."""
    if idle_seconds is None:
        return default_sleep
    if idle_seconds < min_sleep:
        return min_sleep
    if idle_seconds > max_sleep:
        return max_sleep
    return float(idle_seconds)
