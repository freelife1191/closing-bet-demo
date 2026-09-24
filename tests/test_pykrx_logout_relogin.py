#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[INFRA-089] KRX 가 끊은 세션(400 LOGOUT)을 재로그인 1회로 복구하는 계약."""

import importlib
import threading
import time

import pytest
import requests

URL = "https://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd"


def _response(status: int, body: bytes) -> requests.Response:
    response = requests.Response()
    response.status_code = status
    response._content = body
    return response


OK = (200, b'{"output":[]}')
LOGOUT = (400, b"LOGOUT")


@pytest.fixture
def krx(monkeypatch):
    """가짜 전송과 가짜 로그인. 로그인한 세션 객체에만 answer 가 정한 응답을 준다."""
    # pykrx 는 import 시 환경의 KRX 계정으로 로그인한다. 다른 테스트가 .env 를 읽어 두었을 수 있으므로
    # 계정을 지운 상태에서 처음 import 하게 한다
    monkeypatch.delenv("KRX_ID", raising=False)
    monkeypatch.delenv("KRX_PW", raising=False)
    auth = importlib.import_module("pykrx.website.comm.auth")
    monkeypatch.setenv("KRX_ID", "dummy-id")
    monkeypatch.setenv("KRX_PW", "dummy-pw")
    monkeypatch.setattr(auth, "_refresh_blocked_until", 0.0, raising=False)
    monkeypatch.setattr(auth, "_auth_session", None)
    state = {"logins": 0, "requests": 0, "calls": [], "login_ok": True, "login_delay": 0.0,
             "answer": lambda session: OK if getattr(session, "logged_in", False) else LOGOUT}
    lock = threading.Lock()

    def fake_login(_id, _pw, session):
        time.sleep(state["login_delay"])
        with lock:
            state["logins"] += 1
        session.logged_in = state["login_ok"]
        return state["login_ok"]

    def fake_request(session, method, url, **kwargs):
        with lock:
            state["requests"] += 1
            state["calls"].append((method, url, kwargs))
        return _response(*state["answer"](session))

    monkeypatch.setattr(auth, "login_krx", fake_login)
    monkeypatch.setattr(requests.Session, "request", fake_request)
    krxs = auth.KRXSession(is_authenticated=True)  # 클라이언트는 유효하다고 보지만 서버는 끊은 세션
    krxs.login_time = time.time() - 600  # 10분 전에 로그인한 세션
    state["auth"] = auth
    return krxs, state


def test_logout_response_relogins_once_and_retries(krx):
    krxs, state = krx
    response = krxs.post(URL, data={"bld": "x"})
    assert (response.status_code, state["logins"], state["requests"]) == (200, 1, 2)
    assert state["calls"][0] == state["calls"][1]  # 같은 요청을 그대로 다시 보낸다


def test_concurrent_logout_logs_in_once(krx):
    krxs, state = krx
    state["login_delay"] = 0.2
    barrier = threading.Barrier(4)

    def call():
        barrier.wait()
        return krxs.post(URL, data={}).status_code

    threads_out = []
    threads = [threading.Thread(target=lambda: threads_out.append(call())) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert threads_out == [200] * 4
    assert state["logins"] == 1


@pytest.mark.parametrize("answer", [(400, b"INVALIDPERIOD"), (302, b"")])
def test_other_errors_do_not_relogin(krx, answer):
    krxs, state = krx
    state["answer"] = lambda _session: answer
    response = krxs.post(URL, data={})
    assert (response.status_code, response.content) == answer
    assert (state["logins"], state["requests"]) == (0, 1)


def test_failed_relogin_blocks_retries_for_a_minute(krx):
    krxs, state = krx
    state["login_ok"] = False
    assert krxs.post(URL, data={}).content == b"LOGOUT"
    assert state["logins"] == 1
    assert krxs.post(URL, data={}).content == b"LOGOUT"
    assert state["logins"] == 1
    state["auth"]._refresh_blocked_until = 0.0  # 60초가 지난 것으로 본다
    krxs.post(URL, data={})
    assert state["logins"] == 2


def test_retry_still_logout_returns_without_loop(krx):
    krxs, state = krx
    state["answer"] = lambda _session: LOGOUT
    response = krxs.post(URL, data={})
    assert response.content == b"LOGOUT"
    assert (state["logins"], state["requests"]) == (1, 2)


def test_expired_timer_uses_same_guard(krx, monkeypatch):
    krxs, state = krx
    auth = state["auth"]
    krxs.expiry_time = time.time() - 1
    state["login_ok"] = False
    monkeypatch.setattr(auth, "_auth_session", krxs)
    assert auth.get_auth_session() is None
    assert auth.get_auth_session() is None
    assert state["logins"] == 1


def test_expired_timer_relogins(krx, monkeypatch):
    krxs, state = krx
    auth = state["auth"]
    krxs.expiry_time = time.time() - 1
    monkeypatch.setattr(auth, "_auth_session", krxs)
    assert auth.get_auth_session() is krxs
    assert (state["logins"], krxs.is_authenticated) == (1, True)


def test_missing_session_login_failure_is_blocked(krx):
    _krxs, state = krx
    auth = state["auth"]
    state["login_ok"] = False
    assert auth.get_auth_session() is None
    assert auth.get_auth_session() is None
    assert state["logins"] == 1


def test_logout_without_credentials_does_not_login(krx, monkeypatch):
    krxs, state = krx
    monkeypatch.delenv("KRX_PW")
    assert krxs.post(URL, data={}).content == b"LOGOUT"
    assert (state["logins"], state["requests"]) == (0, 1)


def test_logout_soon_after_login_does_not_relogin(krx):
    krxs, state = krx
    krxs.login_time = time.time() - 5  # 방금 로그인한 세션이 다시 끊김(프로세스끼리 서로 끊는 경우)
    assert krxs.post(URL, data={}).content == b"LOGOUT"
    assert (state["logins"], state["requests"]) == (0, 1)


def test_logout_after_another_thread_relogged_retries(krx):
    # 옛 세션으로 보낸 요청의 LOGOUT 을 다른 스레드의 재로그인이 끝난 뒤에 받으면 로그인 없이 재전송한다
    krxs, state = krx
    answer = state["answer"]

    def relogged_by_other_thread(session):
        if not getattr(session, "logged_in", False):
            fresh = requests.Session()
            fresh.logged_in = True
            krxs.session, krxs.login_time = fresh, time.time()
        return answer(session)

    state["answer"] = relogged_by_other_thread
    response = krxs.post(URL, data={})
    assert (response.status_code, state["logins"], state["requests"]) == (200, 0, 2)
