#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Signal Generation Phases (Base)

공통 BasePhase 정의와 중단 요청 체크를 담당합니다.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict

from engine.exceptions import ScreeningStoppedError
import engine.shared as shared_state


class BasePhase(ABC):
    """모든 Phase의 기본 클래스."""

    def __init__(self, name: str):
        self.name = name
        self.stats = {"processed": 0, "passed": 0, "failed": 0}

    @abstractmethod
    async def execute(self, *args, **kwargs) -> Any:
        """Phase 실행."""
        raise NotImplementedError

    def _check_stop_requested(self) -> None:
        """사용자 중단 요청 확인."""
        if shared_state.STOP_REQUESTED:
            raise ScreeningStoppedError(f"User requested stop during {self.name}")

    def get_stats(self) -> Dict[str, int]:
        """통계 정보 반환."""
        return self.stats.copy()
