#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Position Sizer (자금 관리)
"""
import logging
from typing import Optional
from dataclasses import dataclass
from engine.models import Grade
from engine.config import config, SignalConfig

logger = logging.getLogger(__name__)


@dataclass
class PositionInfo:
    """포지션 정보"""
    entry_price: float
    stop_price: float
    target_price: float
    r_value: float
    r_multiplier: float
    position_size: float
    quantity: int


class PositionSizer:
    """자금 관리"""

    def __init__(self, capital: float, config: SignalConfig = None):
        self.capital = capital
        self.config = config or SignalConfig()

    def calculate(self, current_price: float, grade: Grade) -> PositionInfo:
        """포지션 계산"""
        try:
            # R값 (리스크)
            r_value = self.capital * self.config.risk_per_trade

            # 손절가
            stop_price = current_price * (1 - self.config.stop_loss_pct)

            # 목표가
            target_price = current_price * (1 + self.config.take_profit_pct)

            # 등급별 R-Multiplier
            r_multiplier = self._get_r_multiplier(grade)

            # 포지션 크기
            position_size = r_value * r_multiplier

            # 수량
            quantity = int(position_size / current_price)

            return PositionInfo(
                entry_price=current_price,
                stop_price=stop_price,
                target_price=target_price,
                r_value=r_value,
                r_multiplier=r_multiplier,
                position_size=position_size,
                quantity=quantity
            )

        except Exception as e:
            logger.error(f"포지션 계산 실패: {e}")
            return PositionInfo(
                entry_price=current_price,
                stop_price=current_price * 0.97,
                target_price=current_price * 1.05,
                r_value=0,
                r_multiplier=1,
                position_size=0,
                quantity=0
            )

    def _get_r_multiplier(self, grade: Grade) -> float:
        """등급별 R-Multiplier (문서 기준)"""
        if grade == Grade.S:
            return 1.5  # S등급: 1.5R
        elif grade == Grade.A:
            return 1.0  # A등급: 1.0R
        elif grade == Grade.B:
            return 0.5  # B등급: 0.5R
        else:
            return 0.0  # C등급: 매매 안함

    def calculate_max_positions(self, grade: Grade) -> int:
        """최대 포지션 수"""
        return self.config.max_positions
