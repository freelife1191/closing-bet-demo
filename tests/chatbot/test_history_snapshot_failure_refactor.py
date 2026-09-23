#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[CHAT-040] 스냅샷 쓰기 실패는 SQLite 저장의 성패를 바꾸지 않는다."""

import json
import time

import pytest

import chatbot.core as chatbot_core

OWNER = "alice@example.test"


def _disk_full(_data):
    raise OSError(28, "No space left on device")


def _manager_with_snapshot(monkeypatch, tmp_path):
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)
    manager = chatbot_core.HistoryManager(user_id="u1")
    session_id = manager.create_session(owner_id=OWNER)
    manager.add_message(session_id, "user", "지울 대화")
    manager._snapshot.sync(manager._read_sqlite_sessions, force=True)
    assert manager.file_path.exists()
    return manager


def test_delete_succeeds_and_stays_deleted_when_snapshot_write_fails(monkeypatch, tmp_path):
    manager = _manager_with_snapshot(monkeypatch, tmp_path)
    manager._snapshot.write = _disk_full

    assert manager.clear_for_owner(OWNER) == 1
    # 낡은 JSON 이 남으면 빈 SQLite 를 본 다음 로드가 그것을 다시 이관해 지운 대화가 살아난다
    assert not manager.file_path.exists()
    assert chatbot_core.HistoryManager(user_id="u2").get_all_sessions(owner_id=OWNER) == []

    # 복구 사본은 15초 간격을 기다리지 않고 다음 저장이 다시 만든다
    del manager._snapshot.write  # 인스턴스 대체를 걷어 원래 메서드로 돌린다
    manager.create_session(owner_id="bob@example.test")
    assert manager.file_path.exists()


def test_delete_reports_failure_when_stale_snapshot_cannot_be_removed(monkeypatch, tmp_path):
    manager = _manager_with_snapshot(monkeypatch, tmp_path)
    manager._snapshot.write = _disk_full
    monkeypatch.setattr(type(manager.file_path), "unlink", lambda *_a, **_k: _disk_full(None))

    with pytest.raises(RuntimeError):
        manager.clear_for_owner(OWNER)
    # 삭제는 SQLite 에 커밋됐다. 남은 장부가 나중에 되살아난 세션을 몰래 지우지 않게 비운다
    assert not manager._delta.has_delta
    assert manager._last_reload_signature is None


def test_non_delete_save_survives_snapshot_failure(monkeypatch, tmp_path):
    manager = _manager_with_snapshot(monkeypatch, tmp_path)
    session_id = next(iter(manager.sessions))
    manager._snapshot.write = _disk_full
    manager._snapshot.last_monotonic = None  # 간격이 차서 이번 저장이 스냅샷을 쓰게 한다

    manager.add_message(session_id, "user", "두 번째", save=False)
    assert manager._save() is True
    assert manager.file_path.exists()  # 삭제가 없으면 사본을 지우지 않는다
    assert len(chatbot_core.HistoryManager(user_id="u2").get_messages(session_id)) == 2


def _snapshot_owners(manager):
    return sorted(s.get("owner_id") for s in json.loads(manager.file_path.read_text("utf-8")).values())


def test_delete_retry_clears_snapshot_left_by_failed_delete(monkeypatch, tmp_path):
    """[CHAT-041] 앞선 삭제가 사본을 정리하지 못했으면 대상이 0 인 재시도가 정리한다."""
    manager = _manager_with_snapshot(monkeypatch, tmp_path)
    manager.create_session(owner_id="bob@example.test")  # SQLite 가 비지 않아 이관이 일어나지 않는다
    manager._snapshot.sync(manager._read_sqlite_sessions, force=True)
    manager._snapshot.write = _disk_full
    with monkeypatch.context() as m:
        m.setattr(type(manager.file_path), "unlink", lambda *_a, **_k: _disk_full(None))
        with pytest.raises(RuntimeError):
            manager.clear_for_owner(OWNER)
    assert OWNER in _snapshot_owners(manager)

    del manager._snapshot.write
    # 재시도는 간격이 아직 차지 않은 다른 워커에 닿을 수 있다
    manager._snapshot.last_monotonic = time.monotonic()
    assert manager.clear_for_owner(OWNER) == 0
    assert _snapshot_owners(manager) == ["bob@example.test"]


def test_snapshot_ignores_stale_memory_of_another_worker(monkeypatch, tmp_path):
    """[CHAT-041] 다른 워커가 지운 세션을 낡은 메모리 사본이 스냅샷에 되살리지 않는다."""
    worker_a = _manager_with_snapshot(monkeypatch, tmp_path)
    bob_session = worker_a.create_session(owner_id="bob@example.test")
    worker_b = chatbot_core.HistoryManager(user_id="u2")  # A 의 삭제 전에 읽은 사본

    assert worker_a.clear_for_owner(OWNER) == 1
    worker_b._snapshot.last_monotonic = None
    worker_b._mark_session_changed(bob_session)
    assert worker_b._save() is True
    assert _snapshot_owners(worker_b) == ["bob@example.test"]


def test_manager_starts_when_load_snapshot_write_fails(monkeypatch, tmp_path):
    """[CHAT-041] 기동 때 사본 쓰기가 실패해도 SQLite 의 대화로 시작한다."""
    _manager_with_snapshot(monkeypatch, tmp_path)
    monkeypatch.setattr("chatbot.storage_history_parts.LegacySnapshot.write", lambda self, data: _disk_full(data))

    manager = chatbot_core.HistoryManager(user_id="u2")
    assert len(manager.get_all_sessions(owner_id=OWNER)) == 1
    assert manager._snapshot.last_monotonic is None  # 다음 저장이 간격을 기다리지 않고 다시 쓴다


def test_delete_reports_failure_when_reload_failed_even_without_targets(monkeypatch, tmp_path):
    """[CHAT-041] 정본을 읽지 못하면 지울 대상을 알 수 없으므로 0 건도 성공으로 돌려주지 않는다."""
    manager = _manager_with_snapshot(monkeypatch, tmp_path)
    monkeypatch.setattr(chatbot_core.HistoryManager, "_load", lambda self: None)

    with pytest.raises(RuntimeError):
        manager.clear_for_owner("nobody@example.test")


def test_snapshot_keeps_messages_when_message_table_comes_back_empty(monkeypatch, tmp_path):
    """[CHAT-041] 메시지 표가 빈 채 복구된 DB 로 사본을 덮지 않는다([CHAT-039] 의 복구 원천)."""
    import sqlite3

    manager = _manager_with_snapshot(monkeypatch, tmp_path)
    with sqlite3.connect(manager.db_path) as conn:
        conn.execute("DELETE FROM chatbot_messages")

    manager._snapshot.sync(manager._read_sqlite_sessions, force=True)
    saved = json.loads(manager.file_path.read_text("utf-8"))
    assert [len(s["messages"]) for s in saved.values()] == [1]
