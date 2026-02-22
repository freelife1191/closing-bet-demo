#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Error Handler Context Manager
"""

from __future__ import annotations

import logging
from typing import Any


logger = logging.getLogger(__name__)


class ErrorHandler:
    """
    에러 핸들링 컨텍스트 매니저.
    """

    def __init__(
        self,
        operation: str,
        default_return: Any = None,
        raise_on: tuple = (),
        log_level: str = "error",
    ):
        self.operation = operation
        self.default_return = default_return
        self.raise_on = raise_on
        self.log_level = log_level
        self.error = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.error = exc_val

            if isinstance(exc_val, self.raise_on):
                return False

            log_func = getattr(logger, self.log_level, logger.error)
            log_func(f"[{self.operation}] {exc_type.__name__}: {exc_val}")
            return True
        return False

    def get_result(self):
        """결과 반환 (에러 발생 시 기본값)."""
        if self.error:
            return self.default_return
        return None


__all__ = ["ErrorHandler"]
