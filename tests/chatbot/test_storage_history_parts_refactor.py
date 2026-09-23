#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HistoryManager 부품의 분기 검사([CHAT-035])."""

import json
import sqlite3
from types import SimpleNamespace

import pytest

import chatbot.storage_history_parts as parts
from chatbot.storage_history_parts import (
    HistoryReadCache,
    LegacySnapshot,
    SessionDeltaLedger,
    storage_signature,
)


def test_delta_ledger_keeps_latest_intent_per_session():
    ledger = SessionDeltaLedger()
    ledger.mark_changed("")
    assert not ledger.has_delta
    ledger.mark_changed("a")
    ledger.mark_deleted("a")
    assert (ledger.changed, ledger.deleted) == (set(), {"a"})
    ledger.mark_changed("a")
    assert (ledger.changed, ledger.deleted) == ({"a"}, set())
    ledger.mark_clear_all()
    assert ledger.clear_all and not ledger.changed and not ledger.deleted
    # 종전 동작 그대로: 변경 표시가 전체 삭제 표시를 내린다
    ledger.mark_changed("b")
    assert ledger.clear_all is False
    ledger.reset()
    assert not ledger.has_delta


def test_legacy_snapshot_writes_only_when_due(tmp_path, monkeypatch):
    now = {"t": 100.0}
    # 전역 time 모듈이 아니라 이 모듈의 참조만 바꾼다
    monkeypatch.setattr(parts, "time", SimpleNamespace(monotonic=lambda: now["t"]))
    snapshot = LegacySnapshot(tmp_path / "history.json", interval_seconds=15.0)
    assert snapshot.sync({"a": {}}) is True
    assert snapshot.sync({"b": {}}) is False
    assert snapshot.sync({"c": {}}, force=True) is True
    now["t"] += 15.0
    assert snapshot.sync({}) is True
    assert json.loads((tmp_path / "history.json").read_text(encoding="utf-8")) == {}
    snapshot.interval_seconds = 0.0
    assert snapshot.sync({"d": {}}) is True


@pytest.mark.parametrize("raw, expected", [("3", 3.0), ("-1", 0.0), ("abc", 15.0)])
def test_legacy_snapshot_interval_from_env(monkeypatch, tmp_path, raw, expected):
    monkeypatch.setenv("CHATBOT_HISTORY_LEGACY_SNAPSHOT_INTERVAL_SECONDS", raw)
    assert LegacySnapshot.from_env(tmp_path / "h.json").interval_seconds == expected


def test_read_cache_returns_copies_and_evicts_least_recent():
    cache = HistoryReadCache(messages_max_entries=2, session_list_max_entries=2)
    returned = cache.put_messages("s1", ("t1", 1), [{"role": "user", "parts": [{"text": "x"}]}])
    returned[0]["parts"][0]["text"] = "changed"
    assert cache.get_messages("s1", ("t1", 1))[0]["parts"][0]["text"] == "x"
    assert cache.get_messages("s1", ("t1", 2)) is None
    cache.put_messages("s2", ("t2", 1), [])
    cache.get_messages("s1", ("t1", 1))
    cache.put_messages("s3", ("t3", 1), [])
    assert list(cache.messages) == ["s1", "s3"]

    cache.put_session_list("owner", [{"id": "s1"}])
    assert cache.get_session_list("owner") == [{"id": "s1"}]
    cache.invalidate_session_list()
    assert cache.get_session_list("owner") is None
    cache.put_session_list("empty", [])
    assert cache.get_session_list("empty") == []  # 빈 목록도 적중이다


def test_storage_signature_prefers_sqlite_files(tmp_path):
    db_path = tmp_path / "chatbot_storage.db"
    json_path = tmp_path / "chatbot_history.json"
    assert storage_signature(db_path, json_path) is None
    json_path.write_text("{}", encoding="utf-8")
    assert isinstance(storage_signature(db_path, json_path)[0], int)  # JSON 한 파일의 (inode, mtime, size)
    sqlite3.connect(db_path).close()
    db_sig, wal_sig, shm_sig = storage_signature(db_path, json_path)
    assert db_sig is not None and wal_sig is None and shm_sig is None


def test_storage_signature_uses_wal_even_without_db_file(tmp_path):
    db_path = tmp_path / "chatbot_storage.db"
    (tmp_path / "chatbot_storage.db-wal").write_bytes(b"x")
    db_sig, wal_sig, shm_sig = storage_signature(db_path, tmp_path / "chatbot_history.json")
    assert db_sig is None and wal_sig is not None and shm_sig is None


def test_storage_signature_treats_stat_error_as_missing(tmp_path, monkeypatch):
    def _denied(self, *args, **kwargs):
        raise PermissionError("denied")

    monkeypatch.setattr(parts.Path, "stat", _denied)
    assert storage_signature(tmp_path / "chatbot_storage.db", tmp_path / "chatbot_history.json") is None
