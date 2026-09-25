#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pytest 공통 설정
"""

import os

# [INFRA-121] .env 의 KRX 자격 증명으로 pykrx 가 로그인하지 않게 한다. load_dotenv 는 이미 있는 키를
# 덮어쓰지 않으므로 프로젝트 모듈 import 전에 빈 값으로 둔다
os.environ["KRX_ID"] = ""
os.environ["KRX_PW"] = ""
# [INFRA-122] create_app() 이 실제 스케줄러를 켜면 저장소 services/scheduler.lock 을 잡고 가격 동기화·스케줄 루프
# 스레드가 세션 끝까지 돈다. 켜야 하는 테스트는 monkeypatch.setenv 로 연다
os.environ["SCHEDULER_ENABLED"] = "false"

import sys
import errno
import socket
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


# [INFRA-121] 테스트가 외부로 나가는 시도. (테스트 nodeid, 종류, 대상)
_NETWORK_LEAKS = []
_CURRENT_TEST = {"nodeid": "<collect>"}
_LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost", "0.0.0.0"}


def _install_network_guard():
    """loopback·AF_UNIX 가 아닌 접속을 막고 어느 테스트가 시도했는지 남긴다."""
    # ponytail: 이 프로세스의 socket.connect·connect_ex·getaddrinfo 와 curl_cffi Session 만 본다. 하위 프로세스,
    # UDP sendto, gethostbyname, C 확장 전송(grpc 등)은 잡지 못한다. 쓰는 코드가 생기면 여기에 더한다
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_getaddrinfo = socket.getaddrinfo

    def is_local(sock, address):
        if sock.family == getattr(socket, "AF_UNIX", None):
            return True
        host = address[0] if isinstance(address, tuple) else address
        return str(host) in _LOCAL_HOSTS

    def record(kind, target):
        _NETWORK_LEAKS.append((_CURRENT_TEST["nodeid"], kind, str(target)))

    def guarded_connect(self, address):
        if is_local(self, address):
            return original_connect(self, address)
        record("connect", address)
        raise OSError(errno.ECONNREFUSED, "[INFRA-121] 테스트의 외부 접속 차단")

    def guarded_connect_ex(self, address):
        if is_local(self, address):
            return original_connect_ex(self, address)
        record("connect_ex", address)
        return errno.ECONNREFUSED

    def guarded_getaddrinfo(host, *args, **kwargs):
        if host is None or str(host) in _LOCAL_HOSTS:
            return original_getaddrinfo(host, *args, **kwargs)
        record("dns", host)
        raise socket.gaierror(socket.EAI_NONAME, "[INFRA-121] 테스트의 외부 DNS 조회 차단")

    socket.socket.connect = guarded_connect
    socket.socket.connect_ex = guarded_connect_ex
    socket.getaddrinfo = guarded_getaddrinfo

    # yfinance 가 쓰는 curl_cffi 는 파이썬 socket 을 거치지 않는다
    try:
        from curl_cffi import requests as curl_requests
    except ImportError:
        return

    def guarded_request(self, method, url, *args, **kwargs):
        record("curl_cffi", f"{method} {url}")
        raise OSError(errno.ECONNREFUSED, "[INFRA-121] 테스트의 외부 접속 차단")

    async def guarded_async_request(self, method, url, *args, **kwargs):
        return guarded_request(self, method, url)

    curl_requests.Session.request = guarded_request
    curl_requests.AsyncSession.request = guarded_async_request


# 수동 Gemini 통합 테스트는 실제 API 에 닿아야 한다
if os.getenv("RUN_GEMINI_HANG_TESTS", "").strip().lower() != "true":
    _install_network_guard()


def pytest_configure(config):
    config._network_leaks = _NETWORK_LEAKS


@pytest.hookimpl(wrapper=True)
def pytest_runtest_protocol(item, nextitem):
    _CURRENT_TEST["nodeid"] = item.nodeid
    try:
        return (yield)
    finally:
        _CURRENT_TEST["nodeid"] = "<between tests>"


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
    if _NETWORK_LEAKS:
        lines = "\n".join(f"  {nodeid}  {kind}  {target}" for nodeid, kind, target in _NETWORK_LEAKS[:50])
        sys.stderr.write(f"\n[INFRA-121] 테스트가 외부 접속을 시도했다 ({len(_NETWORK_LEAKS)}건):\n{lines}\n")
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
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
    steps = sys.modules.get("services.common_update_pipeline_steps")
    if steps is not None:
        # [INFRA-106] stale 검증이 기대 날짜 없이도 출력 파일을 읽으므로 저장소 data/ 를 보지 않게 한다
        monkeypatch.setattr(steps, "_BASE_DIR", str(fake_root))
    common = sys.modules.get("app.routes.common")
    if common is not None:
        # 상태 파일 옆 runtime_cache.db 에 캐시 행이 쓰이므로 디렉터리까지 만든다
        (fake_root / "data").mkdir()
        status_file = str(fake_root / "data" / "update_status.json")
        monkeypatch.setattr(common, "UPDATE_STATUS_FILE", status_file)
        monkeypatch.setattr(common.route_context, "update_status_file", status_file)
