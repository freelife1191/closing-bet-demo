#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
종가베팅 V2 실행 시작(launch_jongga_v2_screener) 회귀 테스트
"""

from __future__ import annotations

import logging
import os
import sys
import threading

import pytest


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from services.kr_market_jongga_runtime_service import launch_jongga_v2_screener


def test_launch_jongga_v2_screener_saves_running_before_thread_start(monkeypatch):
    # [INFRA-114] 백그라운드가 곧바로 끝나 False 를 쓴 뒤 True 가 덮어 409 로 굳지 않는다
    saved: list[bool] = []
    done = threading.Event()

    def _save(running: bool) -> None:
        saved.append(running)
        if running is False:
            done.set()

    status_code, _ = launch_jongga_v2_screener(
        req_data={},
        load_v2_status=lambda: {"isRunning": False},
        save_v2_status=_save,
        run_jongga_background=lambda **_: None,
        logger=logging.getLogger(__name__),
    )

    assert status_code == 200
    assert done.wait(5)
    assert saved == [True, False]


def test_launch_jongga_v2_screener_clears_running_when_thread_start_fails(monkeypatch):
    # [INFRA-114] 스레드 시작이 실패하면 살아 있는 워커 pid 의 True 로 409 가 굳지 않게 되돌린다
    def _fail_start(self):
        raise RuntimeError("can't start new thread")

    monkeypatch.setattr(threading.Thread, "start", _fail_start)
    saved: list[bool] = []

    with pytest.raises(RuntimeError):
        launch_jongga_v2_screener(
            req_data={},
            load_v2_status=lambda: {"isRunning": False},
            save_v2_status=saved.append,
            run_jongga_background=lambda **_: None,
            logger=logging.getLogger(__name__),
        )

    assert saved == [True, False]


def test_launch_jongga_v2_screener_serializes_concurrent_requests(tmp_path):
    # [INFRA-115] 두 워커의 실행 요청이 겹쳐도 파일 잠금 안에서 확인·저장하므로 하나만 시작한다
    import json
    import time

    from services.common_update_status_service import _status_file_lock

    status_file = tmp_path / "v2_screener_status.json"
    status_file.write_text(json.dumps({"isRunning": False}), encoding="utf-8")
    logger = logging.getLogger(__name__)

    def _load():
        loaded = json.loads(status_file.read_text(encoding="utf-8"))
        time.sleep(0.2)  # 읽은 뒤 저장 전에 상대가 끼어들 틈을 연다
        return loaded

    def _save(running: bool) -> None:
        if running:
            status_file.write_text(json.dumps({"isRunning": True}), encoding="utf-8")

    codes: list[int] = []
    barrier = threading.Barrier(2)

    def _request() -> None:
        barrier.wait()
        code, _ = launch_jongga_v2_screener(
            req_data={},
            load_v2_status=_load,
            save_v2_status=_save,
            run_jongga_background=lambda **_: None,
            logger=logger,
            status_lock=lambda: _status_file_lock(str(status_file), logger),
        )
        codes.append(code)

    threads = [threading.Thread(target=_request) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(5)

    assert not any(thread.is_alive() for thread in threads)
    assert sorted(codes) == [200, 409]
