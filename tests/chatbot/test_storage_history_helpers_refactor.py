#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
챗봇 JSON 스냅샷 권한 회귀 테스트 ([FE-046])
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

from chatbot.storage_history_helpers import atomic_write_json


def test_atomic_write_json_creates_0600(tmp_path: Path):
    target = tmp_path / "chatbot_history.json"
    atomic_write_json(target, {"a": 1})
    assert stat.S_IMODE(os.stat(target).st_mode) == 0o600
    assert json.loads(target.read_text(encoding="utf-8")) == {"a": 1}


def test_atomic_write_json_narrows_an_existing_0644_file(tmp_path: Path):
    target = tmp_path / "chatbot_history.json"
    target.write_text("{}", encoding="utf-8")
    os.chmod(target, 0o644)
    atomic_write_json(target, {"b": 2})
    assert stat.S_IMODE(os.stat(target).st_mode) == 0o600
