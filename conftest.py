#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pytest 공통 설정
"""

import os
import pytest


def pytest_collection_modifyitems(config, items):
    """수동 통합 테스트는 명시적으로 활성화될 때만 실행."""
    _ = config
    if os.getenv("RUN_GEMINI_HANG_TESTS", "").strip().lower() == "true":
        return

    skip_marker = pytest.mark.skip(
        reason="manual integration test (set RUN_GEMINI_HANG_TESTS=true to enable)"
    )
    for item in items:
        if "scripts/test_gemini_hang.py" in str(item.fspath):
            item.add_marker(skip_marker)
