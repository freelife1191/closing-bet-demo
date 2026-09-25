#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app startup status reset 리팩토링 회귀 테스트
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
from pathlib import Path


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import app as app_module


def test_reset_startup_status_files_resets_running_flags(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    (data_dir / "update_status.json").write_text(
        json.dumps(
            {
                "isRunning": True,
                "startTime": "2026-02-22T09:00:00",
                "currentItem": "signals",
                "items": [{"name": "signals", "status": "running"}],
            }
        ),
        encoding="utf-8",
    )

    app_module._reset_startup_status_files()

    reset_status = json.loads((data_dir / "update_status.json").read_text(encoding="utf-8"))
    v2_status = json.loads((data_dir / "v2_screener_status.json").read_text(encoding="utf-8"))

    assert reset_status["isRunning"] is False
    assert reset_status["items"] == []
    assert v2_status == {"isRunning": False}


def test_reset_startup_status_files_handles_corrupt_update_status(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "update_status.json").write_text("{invalid json", encoding="utf-8")

    app_module._reset_startup_status_files()

    v2_status = json.loads((data_dir / "v2_screener_status.json").read_text(encoding="utf-8"))
    assert v2_status == {"isRunning": False}


def _write_running_status(data_dir: Path, owner_pid, owner_ppid=None) -> None:
    (data_dir / "update_status.json").write_text(
        json.dumps(
            {
                "isRunning": True,
                "startTime": "2026-09-25T09:00:00",
                "ownerPid": owner_pid,
                "ownerPpid": os.getppid() if owner_ppid is None else owner_ppid,
                "items": [{"name": "Daily Prices", "status": "running"}],
            }
        ),
        encoding="utf-8",
    )


def test_reset_startup_status_files_keeps_running_status_of_live_other_worker(monkeypatch, tmp_path: Path):
    # [INFRA-107] 워커 하나만 다시 뜨면 살아 있는 다른 워커의 실행을 지우지 않는다
    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    # 두 번째 경우: 권한이 없는 프로세스(pid 1, EPERM)도 존재하므로 살아 있다고 본다
    for owner_pid in (os.getppid(), 1):
        _write_running_status(data_dir, owner_pid)

        app_module._reset_startup_status_files()

        status = json.loads((data_dir / "update_status.json").read_text(encoding="utf-8"))
        assert status["isRunning"] is True, owner_pid
        assert status["items"] == [{"name": "Daily Prices", "status": "running"}]


def test_reset_startup_status_files_resets_when_owner_dead_or_self(monkeypatch, tmp_path: Path):
    # [INFRA-107] 소유 워커가 죽었거나(전체 재기동) 자기 pid 이거나 bool 이면 종전처럼 초기화한다
    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()

    # 마지막 경우: 살아 있는 pid 라도 마스터가 다르면(재부팅 뒤 pid 재사용) 옛 실행이다
    for owner_pid, owner_ppid in ((dead.pid, None), (os.getpid(), None), (True, None), (2**40, None), (os.getppid(), -1)):
        _write_running_status(data_dir, owner_pid, owner_ppid)
        app_module._reset_startup_status_files()
        status = json.loads((data_dir / "update_status.json").read_text(encoding="utf-8"))
        assert (status["isRunning"], status["items"]) == (False, []), owner_pid


def test_reset_orphaned_update_status_waits_for_status_file_lock(tmp_path: Path):
    # [INFRA-107] 다른 워커가 상태를 읽고-쓰는 동안(중단 요청 등) 기동 초기화가 끼어들어 덮지 않는다
    import fcntl

    from services.common_update_status_service import reset_orphaned_update_status

    status_file = tmp_path / "update_status.json"
    status_file.write_text(json.dumps({"isRunning": True, "items": []}), encoding="utf-8")
    done = threading.Event()
    worker = threading.Thread(
        target=lambda: (reset_orphaned_update_status(update_status_file=str(status_file), logger=logging.getLogger()), done.set())
    )
    with open(str(status_file) + ".lock", "a+") as lock_fp:
        fcntl.flock(lock_fp.fileno(), fcntl.LOCK_EX)
        worker.start()
        assert not done.wait(0.3)
        fcntl.flock(lock_fp.fileno(), fcntl.LOCK_UN)
    assert done.wait(5)
    assert json.loads(status_file.read_text(encoding="utf-8"))["isRunning"] is False
