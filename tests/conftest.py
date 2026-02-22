#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pytest 공통 설정
"""

import os
import sys
import asyncio
import inspect
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


def pytest_pyfunc_call(pyfuncitem):
    """pytest-asyncio 미설치 환경에서도 async test 함수를 실행한다."""
    test_func = pyfuncitem.obj
    if not inspect.iscoroutinefunction(test_func):
        return None

    loop = asyncio.new_event_loop()
    try:
        kwargs = {
            name: pyfuncitem.funcargs[name]
            for name in pyfuncitem._fixtureinfo.argnames
            if name in pyfuncitem.funcargs
        }
        loop.run_until_complete(test_func(**kwargs))
    finally:
        loop.close()
    return True


@pytest.fixture(params=["005930"])
def ticker(request):
    """script-style 가격 조회 테스트용 기본 티커."""
    return request.param
