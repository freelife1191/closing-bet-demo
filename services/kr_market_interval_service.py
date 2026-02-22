#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Interval Service
"""

from __future__ import annotations

import os
import re
from typing import Callable


def project_env_path(base_file: str) -> str:
    """프로젝트 루트 .env 파일 경로를 반환한다."""
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(base_file))),
        ".env",
    )


def persist_market_gate_interval_to_env(
    *,
    interval: int,
    env_path: str,
    atomic_write_text: Callable[[str, str], None],
) -> None:
    """MARKET_GATE_UPDATE_INTERVAL_MINUTES 값을 .env에 반영한다."""
    if not os.path.exists(env_path):
        return

    with open(env_path, "r", encoding="utf-8") as file:
        content = file.read()

    pattern = r"^MARKET_GATE_UPDATE_INTERVAL_MINUTES=\d+"
    new_line = f"MARKET_GATE_UPDATE_INTERVAL_MINUTES={interval}"
    if re.search(pattern, content, re.MULTILINE):
        updated_content = re.sub(pattern, new_line, content, flags=re.MULTILINE)
    else:
        updated_content = f"{content.rstrip()}\n{new_line}\n"

    atomic_write_text(env_path, updated_content)


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
