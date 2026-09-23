#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pytest 공통 설정
"""

import os
import sys
import asyncio
import inspect
import shutil
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 테스트가 건드리면 안 되는 저장소의 실제 자료 디렉터리([INFRA-083])
_GUARDED_DIRS = ("data", "logs")


def _snapshot_guarded_dirs():
    snapshot = {}
    for name in _GUARDED_DIRS:
        for root, _, files in os.walk(PROJECT_ROOT / name):
            for filename in files:
                path = os.path.join(root, filename)
                try:
                    snapshot[path] = os.stat(path).st_mtime_ns
                except FileNotFoundError:
                    continue
    return snapshot


def pytest_sessionstart(session):
    session.config._guarded_snapshot = _snapshot_guarded_dirs()
    # 수집 단계의 import 가 상대 경로(logs/ 등)를 저장소 기준으로 고정하지 않게 한다
    session.config._session_cwd = tempfile.mkdtemp(prefix="pytest-cwd-")
    os.chdir(session.config._session_cwd)


def pytest_sessionfinish(session, exitstatus):
    os.chdir(session.config.invocation_params.dir)
    shutil.rmtree(session.config._session_cwd, ignore_errors=True)
    before = session.config._guarded_snapshot
    after = _snapshot_guarded_dirs()
    changed = sorted(p for p in before.keys() | after.keys() if before.get(p) != after.get(p))
    if not changed:
        return
    # ponytail: 같은 저장소에서 서버가 돌며 logs/ 를 쓰면 테스트 탓이 아니어도 실패로 잡힌다
    lines = "\n".join(f"  {os.path.relpath(p, PROJECT_ROOT)}" for p in changed[:30])
    sys.stderr.write(f"\n[INFRA-083] 테스트 중 저장소 data/·logs/ 가 바뀌었다 ({len(changed)}개):\n{lines}\n")
    session.exitstatus = pytest.ExitCode.TESTS_FAILED


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


# 모듈 위치로 data/ 를 정하는 곳([INFRA-082]). 운영 코드는 그대로 두고 테스트에서만 돌린다
_BASE_DIR_MODULES = (
    "engine.collectors.krx",
    "engine.collectors.news",
    "engine.collectors.naver_pykrx_mixin",
)
_FILE_ROOTED_MODULES = (
    "engine.market_schedule",
    "services.paper_trading",
    "services.kr_market_realtime_price_cache",
)


@pytest.fixture(autouse=True)
def _isolate_repo_writes(tmp_path, tmp_path_factory, monkeypatch):
    """data/·logs/ 쓰기가 저장소가 아닌 임시 디렉터리로 가게 한다([INFRA-083])."""
    monkeypatch.chdir(tmp_path)
    # tmp_path 안에 두면 디렉터리 목록을 단언하는 테스트가 깨진다
    fake_root = tmp_path_factory.mktemp("repo")
    # ponytail: 이미 import 된 모듈만 돌린다. 테스트 안에서 처음 import 하면 세션 끝 검사가 잡는다
    for name in _BASE_DIR_MODULES:
        module = sys.modules.get(name)
        if module is not None:
            monkeypatch.setattr(module, "BASE_DIR", str(fake_root))
    for name in _FILE_ROOTED_MODULES:
        module = sys.modules.get(name)
        if module is not None:
            relative = Path(module.__file__).resolve().relative_to(PROJECT_ROOT)
            monkeypatch.setattr(module, "__file__", str(fake_root / relative))
    common = sys.modules.get("app.routes.common")
    if common is not None:
        # 상태 파일 옆 runtime_cache.db 에 캐시 행이 쓰이므로 디렉터리까지 만든다
        (fake_root / "data").mkdir()
        status_file = str(fake_root / "data" / "update_status.json")
        monkeypatch.setattr(common, "UPDATE_STATUS_FILE", status_file)
        monkeypatch.setattr(common.route_context, "update_status_file", status_file)


@pytest.fixture(params=["005930"])
def ticker(request):
    """script-style 가격 조회 테스트용 기본 티커."""
    return request.param
