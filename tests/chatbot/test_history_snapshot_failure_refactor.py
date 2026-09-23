#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[CHAT-040] 스냅샷 쓰기 실패는 SQLite 저장의 성패를 바꾸지 않는다."""

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
    manager._snapshot.sync(manager.sessions, force=True)
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
