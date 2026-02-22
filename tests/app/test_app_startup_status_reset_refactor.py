#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app startup status reset 리팩토링 회귀 테스트
"""

from __future__ import annotations

import json
import os
import sys
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
