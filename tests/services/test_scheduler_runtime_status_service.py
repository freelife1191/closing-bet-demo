#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scheduler Runtime Status Service 회귀 테스트
"""

from __future__ import annotations

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
