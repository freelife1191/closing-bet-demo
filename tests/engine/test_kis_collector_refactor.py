#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KIS Collector 리팩토링 회귀 테스트
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import engine.kis_collector as kis_module


def test_load_token_from_file_uses_shared_json_loader(monkeypatch, tmp_path: Path):
    token_path = tmp_path / ".kis_token_virtual.json"
    token_path.write_text("{}", encoding="utf-8")

    collector = kis_module.KisCollector.__new__(kis_module.KisCollector)
    collector.token_file = str(token_path)
    collector.access_token = None
    collector.token_expired_at = None

    captured = {"path": None}

    def _loader(path: str):
        captured["path"] = path
        return {"access_token": "abc", "expired_at": "2026-02-23T09:00:00"}

    monkeypatch.setattr(kis_module, "load_json_payload_from_path", _loader)

    collector._load_token_from_file()

    assert captured["path"] == str(token_path)
    assert collector.access_token == "abc"
    assert collector.token_expired_at == datetime.fromisoformat("2026-02-23T09:00:00")


def test_save_token_to_file_uses_atomic_writer(monkeypatch, tmp_path: Path):
    token_path = tmp_path / ".kis_token_virtual.json"
    collector = kis_module.KisCollector.__new__(kis_module.KisCollector)
    collector.token_file = str(token_path)
    collector.access_token = "saved-token"
    collector.token_expired_at = datetime(2026, 2, 23, 9, 0, 0)

    writes: list[tuple[str, str]] = []

    def _atomic_write(path: str, content: str):
        writes.append((path, content))
        Path(path).write_text(content, encoding="utf-8")

    monkeypatch.setattr(kis_module, "atomic_write_text", _atomic_write)

    collector._save_token_to_file()

    assert len(writes) == 1
    assert writes[0][0] == str(token_path)
    assert "saved-token" in writes[0][1]


def test_get_access_token_sets_datetime_expiry_without_pandas():
    class _Response:
        status_code = 200

        @staticmethod
        def json():
            return {"access_token": "new-token", "expires_in": 120}

    class _Session:
        @staticmethod
        def post(_url, headers=None, data=None):
            del headers, data
            return _Response()

    collector = kis_module.KisCollector.__new__(kis_module.KisCollector)
    collector.app_key = "k"
    collector.app_secret = "s"
    collector.base_url = "https://example.com"
    collector.session = _Session()
    collector.access_token = None
    collector.token_expired_at = None
    collector._is_token_valid = lambda: False
    collector._save_token_to_file = lambda: None

    assert collector.get_access_token() is True
    assert collector.access_token == "new-token"
    assert isinstance(collector.token_expired_at, datetime)
