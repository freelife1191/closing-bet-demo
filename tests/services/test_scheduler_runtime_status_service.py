#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scheduler Runtime Status Service 회귀 테스트
"""

from __future__ import annotations

import json
import os
import sys


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import services.scheduler_runtime_status_service as runtime_status_service


def test_get_scheduler_runtime_status_uses_deep_copy_false_loader(monkeypatch, tmp_path):
    captured = {"path": None, "kwargs": None}

    def _loader(path: str, **kwargs):
        captured["path"] = path
        captured["kwargs"] = dict(kwargs)
        return {
            "is_data_scheduling_running": 1,
            "is_jongga_scheduling_running": 0,
            "is_vcp_scheduling_running": True,
        }

    monkeypatch.setattr(runtime_status_service, "load_json_payload_from_path", _loader)

    status = runtime_status_service.get_scheduler_runtime_status(data_dir=str(tmp_path))

    assert captured["path"] == os.path.join(
        str(tmp_path),
        "scheduler_runtime_status.json",
    )
    assert captured["kwargs"]["deep_copy"] is False
    assert status["is_data_scheduling_running"] is True
    assert status["is_jongga_scheduling_running"] is False
    assert status["is_vcp_scheduling_running"] is True


def test_set_scheduler_runtime_status_records_owner_but_get_hides_it(tmp_path):
    # [INFRA-114] 기동 초기화가 소유 워커를 판정하도록 pid 를 남기고, 조회 응답에는 싣지 않는다
    runtime_status_service.set_scheduler_runtime_status(data_dir=str(tmp_path), jongga_scheduling_running=True)

    raw = json.loads((tmp_path / "scheduler_runtime_status.json").read_text(encoding="utf-8"))
    assert (raw["ownerPid"], raw["ownerPpid"]) == (os.getpid(), os.getppid())
    status = runtime_status_service.get_scheduler_runtime_status(data_dir=str(tmp_path))
    assert "ownerPid" not in status and "ownerPpid" not in status
    assert status["is_jongga_scheduling_running"] is True


def test_set_scheduler_runtime_status_overwrites_previous_owner(tmp_path):
    # [INFRA-114] 리더가 바뀌면 새 리더가 다음 기록에서 자기 pid 로 덮는다
    status_file = tmp_path / "scheduler_runtime_status.json"
    status_file.write_text(
        json.dumps({"is_data_scheduling_running": True, "ownerPid": 999_999, "ownerPpid": 1}),
        encoding="utf-8",
    )

    runtime_status_service.set_scheduler_runtime_status(data_dir=str(tmp_path), vcp_scheduling_running=True)

    raw = json.loads(status_file.read_text(encoding="utf-8"))
    assert (raw["ownerPid"], raw["ownerPpid"]) == (os.getpid(), os.getppid())
    assert raw["is_data_scheduling_running"] is True


def test_reset_scheduler_runtime_status_rewrites_idle_status_even_if_owner_alive(tmp_path):
    # [INFRA-114] 실행 중 플래그가 없으면 소유자가 살아 있어도 기본값으로 다시 쓴다
    status_file = tmp_path / "scheduler_runtime_status.json"
    status_file.write_text(
        json.dumps({"is_data_scheduling_running": False, "updated_at": "old", "ownerPid": os.getppid(), "ownerPpid": os.getppid()}),
        encoding="utf-8",
    )

    runtime_status_service.reset_scheduler_runtime_status(data_dir=str(tmp_path))

    raw = json.loads(status_file.read_text(encoding="utf-8"))
    assert raw["updated_at"] != "old"
    assert "ownerPid" not in raw
