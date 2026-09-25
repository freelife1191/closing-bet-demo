#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[INFRA-121] conftest 의 외부 접속 가드 검사
"""

import os
import socket

import pytest


def test_guard_blocks_external_and_allows_loopback(request):
    if os.getenv("RUN_GEMINI_HANG_TESTS", "").strip().lower() == "true":
        pytest.skip("수동 Gemini 테스트를 켜면 가드를 설치하지 않는다")
    leaks = request.config._network_leaks
    nodeid = request.node.nodeid
    try:
        with socket.socket() as sock, pytest.raises(OSError):
            sock.connect(("192.0.2.1", 80))
        with pytest.raises(socket.gaierror):
            socket.getaddrinfo("example.com", 443)
        from curl_cffi import requests as curl_requests

        with pytest.raises(OSError):
            curl_requests.Session().get("https://example.com")
        assert [kind for owner, kind, _ in leaks if owner == nodeid] == ["connect", "dns", "curl_cffi"]

        with socket.socket() as server:
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            with socket.create_connection(server.getsockname(), timeout=1):
                pass
        assert [kind for owner, kind, _ in leaks if owner == nodeid] == ["connect", "dns", "curl_cffi"]
    finally:
        # 이 검사가 일부러 만든 기록이 세션을 실패로 돌리지 않게 지운다
        leaks[:] = [leak for leak in leaks if leak[0] != nodeid]
