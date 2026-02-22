#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Error Handler Validation Utilities
"""

from __future__ import annotations

from typing import Any


def validate_required(value: Any, name: str) -> None:
    """필수 값 검증."""
    if value is None:
        raise ValueError(f"{name} is required but was None")
    if isinstance(value, (str, list, dict)) and not value:
        raise ValueError(f"{name} is required but was empty")


def validate_range(
    value: float,
    name: str,
    min_val: float = None,
    max_val: float = None,
) -> None:
    """범위 검증."""
    if min_val is not None and value < min_val:
        raise ValueError(f"{name} ({value}) is below minimum ({min_val})")
    if max_val is not None and value > max_val:
        raise ValueError(f"{name} ({value}) is above maximum ({max_val})")


def validate_positive(value: float, name: str) -> None:
    """양수 검증."""
    if value is not None and value <= 0:
        raise ValueError(f"{name} must be positive, got {value}")


__all__ = ["validate_required", "validate_range", "validate_positive"]
