#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Messenger Legacy Payload Adapter
"""

from datetime import datetime

from engine.messenger_formatters import MessageData, SignalData


def _to_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def build_message_data_from_payload(payload: dict) -> MessageData:
    """기존 dict 기반 payload를 MessageData로 변환한다."""
    signals: list[SignalData] = []
    for idx, raw_signal in enumerate(payload.get("signals", []), start=1):
        signal = SignalData(
            index=_to_int(raw_signal.get("index", idx), idx),
            name=str(raw_signal.get("name", "")),
            code=str(raw_signal.get("code", "")).zfill(6),
            market=str(raw_signal.get("market", "KR")),
            market_icon=str(raw_signal.get("market_icon", "")),
            grade=str(raw_signal.get("grade", "")),
            score=_to_float(raw_signal.get("score", 0)),
            change_pct=_to_float(raw_signal.get("change_pct", 0)),
            volume_ratio=_to_float(raw_signal.get("volume_ratio", 0)),
            trading_value=_to_int(raw_signal.get("trading_value", 0)),
            f_buy=_to_int(raw_signal.get("f_buy", 0)),
            i_buy=_to_int(raw_signal.get("i_buy", 0)),
            entry=_to_int(raw_signal.get("entry", 0)),
            target=_to_int(raw_signal.get("target", 0)),
            stop=_to_int(raw_signal.get("stop", 0)),
            ai_reason=str(raw_signal.get("ai_reason", "")),
        )
        signals.append(signal)

    return MessageData(
        title=str(payload.get("title", "Notification")),
        summary_title=str(payload.get("summary_title", "")),
        summary_desc=str(payload.get("summary_desc", "")),
        gate_info=str(payload.get("gate_info", "")),
        signals=signals,
        timestamp=str(payload.get("timestamp", datetime.now().isoformat())),
    )


__all__ = [
    "_to_int",
    "_to_float",
    "build_message_data_from_payload",
]
