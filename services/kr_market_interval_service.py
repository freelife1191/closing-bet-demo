#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Interval Service
"""

from __future__ import annotations

from io import StringIO
from typing import Callable

from dotenv.parser import parse_stream

from services.common_env_service import _env_file_lock, _read_env_lines


def persist_market_gate_interval_to_env(
    *,
    interval: int,
    env_path: str,
    atomic_write_text: Callable[[str, str], None],
    apply_interval_fn: Callable[[int], None],
) -> None:
    """주기를 저장한 뒤 같은 잠금 안에서 런타임에 적용한다.

    읽기·파싱·교체 실패는 런타임을 바꾸지 않는다. 교체 후 적용 실패는
    이미 저장한 파일을 되돌리지 않고 호출자에게 전파한다.
    """
    with _env_file_lock(env_path):
        lines = _read_env_lines(env_path)
        parts: list[str] = []
        found = False
        for binding in parse_stream(StringIO("".join(lines))):
            if binding.error:
                raise ValueError("Invalid environment file syntax")
            if binding.key == "MARKET_GATE_UPDATE_INTERVAL_MINUTES":
                if not found:
                    parts.append(f"MARKET_GATE_UPDATE_INTERVAL_MINUTES={interval}\n")
                    found = True
            else:
                parts.append(binding.original.string)
        if not found:
            if parts and not parts[-1].endswith(("\n", "\r")):
                parts.append("\n")
            parts.append(f"MARKET_GATE_UPDATE_INTERVAL_MINUTES={interval}\n")
        atomic_write_text(env_path, "".join(parts))
        apply_interval_fn(interval)


def apply_market_gate_interval(
    *,
    interval: int,
    logger,
) -> None:
    """런타임 스케줄러/설정에 Market Gate 갱신 주기를 적용한다."""
    from engine.config import app_config

    app_config.MARKET_GATE_UPDATE_INTERVAL_MINUTES = interval

    try:
        from services.scheduler import update_market_gate_interval

        update_market_gate_interval(interval)
    except ImportError:
        logger.warning("Scheduler module not found, skipping runtime update")
    except Exception as error:
        logger.error(f"Scheduler update failed: {error}")
