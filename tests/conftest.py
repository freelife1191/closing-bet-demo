#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pytest 공통 설정
"""

import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def pytest_collection_modifyitems(config, items):
    """무거운/수동 테스트는 명시적으로 활성화될 때만 실행."""
    _ = config
    run_gemini_hang_tests = os.getenv("RUN_GEMINI_HANG_TESTS", "").strip().lower() == "true"
    run_project_showcase_tests = (
        os.getenv("RUN_PROJECT_SHOWCASE_TESTS", "").strip().lower() == "true"
    )

    skip_gemini_hang_marker = pytest.mark.skip(
        reason="manual integration test (set RUN_GEMINI_HANG_TESTS=true to enable)"
    )
    skip_project_showcase_marker = pytest.mark.skip(
        reason="project-showcase-kit tests are excluded by default (set RUN_PROJECT_SHOWCASE_TESTS=true to enable)"
    )

    for item in items:
        path = str(item.fspath)
        normalized_path = path.replace("\\", "/")
        if not run_gemini_hang_tests and "/tests/manual/test_gemini_hang.py" in normalized_path:
            item.add_marker(skip_gemini_hang_marker)
        if not run_project_showcase_tests and "/project/project-showcase-kit/tests/" in normalized_path:
            item.add_marker(skip_project_showcase_marker)
