#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - LLM Utilities (Model Fallback)
"""

from __future__ import annotations

from typing import Dict, List, Optional


class ModelFallbackHandler:
    """
    모델 폴백 핸들러.
    """

    def __init__(
        self,
        models: Dict[str, str],
        fallback_errors: List[str] = None,
    ):
        self.models = models
        self.fallback_errors = fallback_errors or [
            "RESOURCE_EXHAUSTED",
            "OVERLOADED",
            "UNAVAILABLE",
        ]
        self.current_model = models.get("primary")
        self._used_fallback = False

    def should_fallback(self, error: Exception) -> bool:
        """폴백이 필요한지 확인."""
        if self._used_fallback:
            return False

        error_msg = str(error).upper()
        return any(keyword in error_msg for keyword in self.fallback_errors)

    def get_fallback_model(self) -> Optional[str]:
        """폴백 모델 반환."""
        self._used_fallback = True
        return self.models.get("fallback")

    def get_model(self) -> str:
        """현재 모델 반환."""
        return self.current_model

    def set_model(self, model: str):
        """현재 모델 설정."""
        self.current_model = model

    def reset(self):
        """상태 리셋."""
        self.current_model = self.models.get("primary")
        self._used_fallback = False


__all__ = ["ModelFallbackHandler"]
