#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Common Route Context
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class CommonRouteContext:
    """공통 라우트 의존성 컨테이너."""

    logger: Any
    update_lock: Any
    update_status_file: str
    load_update_status: Callable[[], dict[str, Any]]
    start_update: Callable[[list[str]], None]
    update_item_status: Callable[[str, str], None]
    stop_update: Callable[[], None]
    finish_update: Callable[[], None]
    run_background_update: Callable[[str | None, list[str] | None, bool], None]
    paper_trading: Any
