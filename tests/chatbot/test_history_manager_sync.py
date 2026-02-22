#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HistoryManager 멀티 인스턴스 동기화 회귀 테스트
"""

import json
import os
import sys
import time
from pathlib import Path


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import chatbot.core as chatbot_core
import chatbot.storage as chatbot_storage


def _read_history_file(tmp_path: Path) -> dict:
    history_file = tmp_path / "chatbot_history.json"
    if not history_file.exists():
        return {}
    return json.loads(history_file.read_text(encoding="utf-8"))


def test_get_messages_reflects_latest_file_state(monkeypatch, tmp_path):
    """다른 인스턴스에서 삭제한 세션은 즉시 빈 히스토리로 보여야 한다."""
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)

    manager_a = chatbot_core.HistoryManager(user_id="u1")
    session_id = manager_a.create_session(owner_id="owner")
    manager_a.add_message(session_id, "user", "삭제될 세션")

    manager_b = chatbot_core.HistoryManager(user_id="u2")
    manager_a.delete_session(session_id)

    # 현재 버그: _load() 없이 self.sessions를 바로 조회해 삭제된 메시지가 반환됨
    assert manager_b.get_messages(session_id) == []


def test_deleted_session_is_not_resurrected_by_stale_add_message(monkeypatch, tmp_path):
    """오래된 인메모리 상태를 가진 인스턴스가 저장해도 삭제 세션이 부활하면 안 된다."""
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)

    manager_a = chatbot_core.HistoryManager(user_id="u1")
    deleted_session_id = manager_a.create_session(owner_id="owner")
    manager_a.add_message(deleted_session_id, "user", "삭제 대상")

    active_session_id = manager_a.create_session(owner_id="owner")
    manager_a.add_message(active_session_id, "user", "유지 대상")

    # manager_b는 삭제 전 상태를 메모리에 보유
    manager_b = chatbot_core.HistoryManager(user_id="u2")

    manager_a.delete_session(deleted_session_id)
    data_after_delete = _read_history_file(tmp_path)
    assert deleted_session_id not in data_after_delete

    # 현재 버그: add_message가 _load() 없이 전체 self.sessions를 저장하여 삭제 세션이 부활
    manager_b.add_message(active_session_id, "model", "후속 응답")

    data_after_stale_save = _read_history_file(tmp_path)
    assert deleted_session_id not in data_after_stale_save


def test_load_reinitializes_empty_history_file(monkeypatch, tmp_path):
    """빈 히스토리 파일이어도 예외 없이 빈 JSON으로 자동 복구되어야 한다."""
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)

    history_file = tmp_path / "chatbot_history.json"
    history_file.write_text("", encoding="utf-8")

    manager = chatbot_core.HistoryManager(user_id="u1")

    assert manager.sessions == {}
    assert json.loads(history_file.read_text(encoding="utf-8")) == {}


def test_load_backs_up_corrupt_history_file(monkeypatch, tmp_path):
    """손상된 JSON은 백업 파일로 보존하고 원본은 빈 JSON으로 복구되어야 한다."""
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)

    history_file = tmp_path / "chatbot_history.json"
    history_file.write_text("{not-json", encoding="utf-8")

    manager = chatbot_core.HistoryManager(user_id="u1")

    assert manager.sessions == {}
    assert json.loads(history_file.read_text(encoding="utf-8")) == {}
    backups = list(tmp_path.glob("chatbot_history.corrupt-*.json"))
    assert len(backups) == 1


def test_history_manager_skips_reload_when_history_file_unchanged(monkeypatch, tmp_path):
    """파일 시그니처가 같으면 불필요한 재로딩을 건너뛰어야 한다."""
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)

    manager = chatbot_core.HistoryManager(user_id="u1")
    load_calls = {"count": 0}
    original_load = manager._load

    def _counted_load():
        load_calls["count"] += 1
        return original_load()

    monkeypatch.setattr(manager, "_load", _counted_load)

    manager.get_session("missing-session")
    manager.get_session("missing-session")
    manager.get_messages("missing-session")

    assert load_calls["count"] == 0


def test_history_manager_reload_only_when_file_signature_changes(monkeypatch, tmp_path):
    """다른 인스턴스가 파일을 갱신하면 한 번만 재로딩하고 이후에는 캐시를 재사용해야 한다."""
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)

    writer = chatbot_core.HistoryManager(user_id="writer")
    reader = chatbot_core.HistoryManager(user_id="reader")
    load_calls = {"count": 0}
    original_load = reader._load

    def _counted_load():
        load_calls["count"] += 1
        return original_load()

    monkeypatch.setattr(reader, "_load", _counted_load)

    session_id = writer.create_session(owner_id="owner")
    writer.add_message(session_id, "user", "새 메시지")

    first_messages = reader.get_messages(session_id)
    second_messages = reader.get_messages(session_id)

    assert first_messages and first_messages[0]["role"] == "user"
    assert second_messages and second_messages[0]["role"] == "user"
    assert load_calls["count"] == 1


def test_get_messages_reuses_sanitized_cache_until_session_changes(monkeypatch, tmp_path):
    """세션이 변경되지 않으면 sanitize를 재사용하고, 변경 후에는 다시 sanitize해야 한다."""
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)

    manager = chatbot_core.HistoryManager(user_id="u1")
    session_id = manager.create_session(owner_id="owner")
    manager.add_message(session_id, "user", "첫 메시지")

    sanitize_calls = {"count": 0}
    original_sanitize = chatbot_storage.sanitize_session_messages

    def _counted_sanitize(session):
        sanitize_calls["count"] += 1
        return original_sanitize(session)

    monkeypatch.setattr(chatbot_storage, "sanitize_session_messages", _counted_sanitize)

    first = manager.get_messages(session_id)
    second = manager.get_messages(session_id)

    assert first == second
    assert sanitize_calls["count"] == 1

    manager.add_message(session_id, "model", "두번째 메시지")
    third = manager.get_messages(session_id)

    assert len(third) == 2
    assert sanitize_calls["count"] == 2


def test_add_message_auto_create_session_saves_once(monkeypatch, tmp_path):
    """없는 세션에 add_message 시 자동 생성되더라도 저장은 한 번만 발생해야 한다."""
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)

    manager = chatbot_core.HistoryManager(user_id="u1")
    save_calls = {"count": 0}
    original_save = manager._save

    def _counted_save():
        save_calls["count"] += 1
        return original_save()

    monkeypatch.setattr(manager, "_save", _counted_save)

    manager.add_message("session-auto", "user", "자동 생성 메시지")

    assert save_calls["count"] == 1
    assert manager.sessions["session-auto"]["messages"][0]["parts"][0]["text"] == "자동 생성 메시지"


def test_get_all_sessions_reuses_filtered_cache_until_session_changes(monkeypatch, tmp_path):
    """세션 목록이 변경되지 않으면 필터링 계산을 재사용하고, 변경 시에만 다시 계산해야 한다."""
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)

    manager = chatbot_core.HistoryManager(user_id="u1")
    session_id = manager.create_session(owner_id="owner")
    manager.add_message(session_id, "user", "의미 있는 첫 질문")

    meaningful_calls = {"count": 0}
    original_has_meaningful = chatbot_storage.has_meaningful_user_message

    def _counted_has_meaningful(messages):
        meaningful_calls["count"] += 1
        return original_has_meaningful(messages)

    monkeypatch.setattr(chatbot_storage, "has_meaningful_user_message", _counted_has_meaningful)

    first = manager.get_all_sessions(owner_id="owner")
    second = manager.get_all_sessions(owner_id="owner")

    assert len(first) == 1
    assert len(second) == 1
    assert meaningful_calls["count"] == 1

    manager.add_message(session_id, "model", "응답 추가")
    third = manager.get_all_sessions(owner_id="owner")

    assert len(third) == 1
    assert meaningful_calls["count"] == 2


def test_get_all_sessions_cache_invalidates_when_file_signature_changes(monkeypatch, tmp_path):
    """다른 인스턴스가 파일을 갱신하면 세션 목록 캐시를 무효화하고 다시 계산해야 한다."""
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)

    writer = chatbot_core.HistoryManager(user_id="writer")
    reader = chatbot_core.HistoryManager(user_id="reader")
    session_id = writer.create_session(owner_id="owner")
    writer.add_message(session_id, "user", "초기 메시지")

    meaningful_calls = {"count": 0}
    original_has_meaningful = chatbot_storage.has_meaningful_user_message

    def _counted_has_meaningful(messages):
        meaningful_calls["count"] += 1
        return original_has_meaningful(messages)

    monkeypatch.setattr(chatbot_storage, "has_meaningful_user_message", _counted_has_meaningful)

    first = reader.get_all_sessions(owner_id="owner")
    second = reader.get_all_sessions(owner_id="owner")

    assert len(first) == 1
    assert len(second) == 1
    assert meaningful_calls["count"] == 1

    writer.add_message(session_id, "model", "파일 갱신")
    third = reader.get_all_sessions(owner_id="owner")

    assert len(third) == 1
    assert meaningful_calls["count"] == 2


def test_reload_from_sqlite_skips_legacy_snapshot_rewrite(monkeypatch, tmp_path):
    """시그니처 변경으로 SQLite 재로딩할 때 legacy snapshot 재쓰기 없이 동기화되어야 한다."""
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)

    writer = chatbot_core.HistoryManager(user_id="writer")
    session_id = writer.create_session(owner_id="owner")
    writer.add_message(session_id, "user", "초기 메시지")

    reader = chatbot_core.HistoryManager(user_id="reader")
    baseline = reader.get_messages(session_id)
    assert baseline and baseline[0]["parts"][0]["text"] == "초기 메시지"

    monkeypatch.setattr(
        reader,
        "_atomic_write",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("legacy snapshot rewrite should be skipped")),
    )

    writer.add_message(session_id, "model", "후속 응답")
    refreshed = reader.get_messages(session_id)

    assert refreshed[-1]["parts"][0]["text"] == "후속 응답"


def test_history_manager_save_uses_sqlite_delta_batch_path(monkeypatch, tmp_path):
    """변경된 세션 저장 시 세션별 반복 연결 대신 SQLite delta 배치 경로를 사용해야 한다."""
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)

    manager = chatbot_core.HistoryManager(user_id="u1")
    session_id = manager.create_session(owner_id="owner", save_immediate=False)
    manager.add_message(session_id, "user", "배치 저장", save=False)

    calls = {"delta": 0}

    def _delta_ok(db_path, sessions, changed_session_ids, deleted_session_ids, clear_all, logger):
        del db_path, sessions, deleted_session_ids, clear_all, logger
        calls["delta"] += 1
        assert session_id in changed_session_ids
        return True

    monkeypatch.setattr(chatbot_storage, "apply_history_session_deltas_in_sqlite", _delta_ok)
    monkeypatch.setattr(
        chatbot_storage,
        "save_history_sessions_to_sqlite",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("full sync should not run")),
    )
    monkeypatch.setattr(manager, "_atomic_write", lambda *_a, **_k: None)

    manager._save()

    assert calls["delta"] == 1


def test_history_manager_skips_legacy_snapshot_on_frequent_sqlite_writes(monkeypatch, tmp_path):
    """연속 저장 시 SQLite가 성공하면 legacy JSON 스냅샷 쓰기를 생략할 수 있어야 한다."""
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)

    manager = chatbot_core.HistoryManager(user_id="u1")
    session_id = manager.create_session(owner_id="owner")

    manager._legacy_snapshot_interval_seconds = 3_600.0
    manager._last_legacy_snapshot_monotonic = time.monotonic()
    monkeypatch.setattr(
        manager,
        "_atomic_write",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("legacy snapshot write should be skipped")),
    )

    manager.add_message(session_id, "model", "스냅샷 생략 테스트")


def test_history_manager_detects_sqlite_wal_change_without_legacy_snapshot(monkeypatch, tmp_path):
    """legacy snapshot을 생략해도 SQLite WAL 시그니처 변경으로 reader가 최신 상태를 읽어야 한다."""
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)

    writer = chatbot_core.HistoryManager(user_id="writer")
    session_id = writer.create_session(owner_id="owner")
    writer.add_message(session_id, "user", "초기 메시지")

    reader = chatbot_core.HistoryManager(user_id="reader")
    baseline = reader.get_messages(session_id)
    assert baseline[-1]["parts"][0]["text"] == "초기 메시지"

    writer._legacy_snapshot_interval_seconds = 3_600.0
    writer._last_legacy_snapshot_monotonic = time.monotonic()
    monkeypatch.setattr(
        writer,
        "_atomic_write",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("legacy snapshot write should be skipped")),
    )

    writer.add_message(session_id, "model", "WAL 변경 메시지")
    refreshed = reader.get_messages(session_id)
    assert refreshed[-1]["parts"][0]["text"] == "WAL 변경 메시지"
