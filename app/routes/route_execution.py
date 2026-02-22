#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Route Execution Helpers
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import jsonify


def build_route_error_response(error: Exception) -> tuple[object, int]:
    return jsonify({"error": str(error)}), 500


def execute_json_route(
    *,
    handler: Callable[[], object],
    logger: Any,
    error_label: str,
    error_response_builder: Callable[[Exception], tuple[object, int]] = build_route_error_response,
) -> object:
    try:
        return handler()
    except Exception as error:
        logger.error(f"{error_label}: {error}")
        return error_response_builder(error)

