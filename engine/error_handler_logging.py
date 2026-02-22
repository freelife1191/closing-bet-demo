#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Error Handler Logging
"""

from __future__ import annotations

import logging
import traceback

from engine.exceptions import get_error_category


logger = logging.getLogger(__name__)


def log_error(
    error: Exception,
    context: str = "",
    include_traceback: bool = False,
):
    """에러 로깅."""
    category = get_error_category(error)
    ctx = f" [{context}]" if context else ""

    if include_traceback:
        logger.error(
            f"[{category}]{ctx} {type(error).__name__}: {error}\n"
            f"{traceback.format_exc()}"
        )
    else:
        logger.error(f"[{category}]{ctx} {type(error).__name__}: {error}")


def log_warning(error: Exception, context: str = ""):
    """경고 로깅."""
    category = get_error_category(error)
    ctx = f" [{context}]" if context else ""
    logger.warning(f"[{category}]{ctx} {type(error).__name__}: {error}")


__all__ = ["log_error", "log_warning"]
