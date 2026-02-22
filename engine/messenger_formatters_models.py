#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Messenger formatter DTO models.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class SignalData:
    """시그널 데이터 DTO."""

    index: int
    name: str
    code: str
    market: str
    market_icon: str
    grade: str
    score: float
    change_pct: float
    volume_ratio: float
    trading_value: int
    f_buy: int
    i_buy: int
    entry: int
    target: int
    stop: int
    ai_reason: str


@dataclass
class MessageData:
    """메시지 데이터 DTO."""

    title: str
    summary_title: str
    summary_desc: str
    gate_info: str
    signals: List[SignalData]
    timestamp: str
