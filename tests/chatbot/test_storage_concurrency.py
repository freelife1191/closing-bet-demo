#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[CHAT-033] 한 워커의 스레드들이 같은 저장소 인스턴스를 공유해도 쓰기가 유실되지 않는지 확인한다.
"""

import json
import sys
import threading
from datetime import datetime

import chatbot.core as chatbot_core
import chatbot.storage as chatbot_storage
import chatbot.storage_memory_manager as storage_memory_manager
from chatbot.storage_memory_manager import MemoryManager


def _run_threads(targets):
    errors = []

    def _wrap(fn):
        try:
            fn()
        except Exception as error:  # 스레드 안의 예외는 테스트로 올라오지 않으므로 모은다.
            errors.append(error)

    previous = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        threads = [threading.Thread(target=_wrap, args=(fn,)) for fn in targets]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
    finally:
        sys.setswitchinterval(previous)
    return errors


def test_memory_update_survives_a_reload_from_another_thread(monkeypatch, tmp_path):
    manager = MemoryManager(user_id="u", data_dir=tmp_path)
    manager.add("k", "old", owner_id="alice")
    readers = []

    class _Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            # update() 가 값을 바꾼 뒤 저장하기 전에 다른 요청 스레드가 view() 로 재적재한다.
            reader = threading.Thread(target=manager.view, args=("alice",))
            reader.start()
            reader.join(0.2)
            readers.append(reader)
            return datetime.fromtimestamp(0, tz)

    monkeypatch.setattr(storage_memory_manager, "datetime", _Clock)
    manager.update("k", "new", owner_id="alice")
    for reader in readers:
        reader.join()

    assert MemoryManager(user_id="v", data_dir=tmp_path).view("alice")["k"]["value"] == "new"


def test_history_manager_threads_keep_every_message(monkeypatch, tmp_path):
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)
    manager = chatbot_core.HistoryManager(user_id="u")
    first = manager.create_session(owner_id="alice")
    second = manager.create_session(owner_id="alice")

    def _writer(session_id):
        return lambda: [manager.add_message(session_id, "user", f"{session_id}-{i}") for i in range(20)]

    errors = _run_threads([_writer(first), _writer(second)])

    assert errors == []
    fresh = chatbot_core.HistoryManager(user_id="v")
    assert len(fresh.get_messages(first)) == 20
    assert len(fresh.get_messages(second)) == 20


def test_failed_delta_save_does_not_delete_another_workers_session(monkeypatch, tmp_path):
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)
    worker_a = chatbot_core.HistoryManager(user_id="a")
    worker_b = chatbot_core.HistoryManager(user_id="b")
    own = worker_b.create_session(owner_id="bob")
    created = {}
    real_delta = chatbot_storage.apply_history_session_deltas_in_sqlite

    def _fail_after_other_worker_writes(*args, **kwargs):
        # 재적재와 저장 사이에 다른 워커가 세션을 만든 상황을 만든다.
        monkeypatch.setattr(chatbot_storage, "apply_history_session_deltas_in_sqlite", real_delta)
        created["id"] = worker_a.create_session(owner_id="alice")
        worker_a.add_message(created["id"], "user", "다른 워커의 대화")
        return False

    monkeypatch.setattr(chatbot_storage, "apply_history_session_deltas_in_sqlite", _fail_after_other_worker_writes)
    assert worker_b.add_message(own, "user", "저장 실패") is None

    fresh = chatbot_core.HistoryManager(user_id="c")
    assert fresh.get_messages(created["id"])


def test_sqlite_read_failure_does_not_overwrite_sqlite_with_legacy_json(monkeypatch, tmp_path):
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)
    writer = chatbot_core.HistoryManager(user_id="w")
    kept = writer.create_session(owner_id="alice")
    writer.add_message(kept, "user", "SQLite 에만 있는 대화")
    (tmp_path / "chatbot_history.json").write_text(
        json.dumps({"legacy": {"id": "legacy", "title": "", "messages": [], "owner_id": None}}),
        encoding="utf-8",
    )

    real_load = chatbot_storage.load_history_sessions_from_sqlite
    monkeypatch.setattr(chatbot_storage, "load_history_sessions_from_sqlite", lambda *a, **k: None)
    chatbot_core.HistoryManager(user_id="x")
    monkeypatch.setattr(chatbot_storage, "load_history_sessions_from_sqlite", real_load)

    assert chatbot_core.HistoryManager(user_id="y").get_messages(kept)


def test_failed_delta_save_does_not_leave_the_change_in_this_workers_view(monkeypatch, tmp_path):
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)
    manager = chatbot_core.HistoryManager(user_id="u")
    session_id = manager.create_session(owner_id="alice")
    manager.add_message(session_id, "user", "m1")

    monkeypatch.setattr(chatbot_storage, "apply_history_session_deltas_in_sqlite", lambda *a, **k: False)
    manager.delete_session(session_id)

    # 저장되지 않은 삭제가 이 워커의 응답에 남으면 DB 와 다른 상태로 계속 응답한다.
    assert manager.get_messages(session_id)[0]["parts"][0]["text"] == "m1"


def test_failed_reload_does_not_write_a_stale_copy(monkeypatch, tmp_path):
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)
    reader = chatbot_core.HistoryManager(user_id="r")
    session_id = reader.create_session(owner_id="alice")
    reader.add_message(session_id, "user", "m1")
    writer = chatbot_core.HistoryManager(user_id="w")
    writer.add_message(session_id, "user", "m2")

    real_load = chatbot_storage.load_history_sessions_from_sqlite
    monkeypatch.setattr(chatbot_storage, "load_history_sessions_from_sqlite", lambda *a, **k: None)
    reader.add_message(session_id, "user", "m3")
    monkeypatch.setattr(chatbot_storage, "load_history_sessions_from_sqlite", real_load)

    texts = [m["parts"][0]["text"] for m in chatbot_core.HistoryManager(user_id="v").get_messages(session_id)]
    assert texts == ["m1", "m2"]
    # 읽기가 회복되면 같은 인스턴스가 DB 를 다시 읽고 쓰기를 재개한다.
    reader.add_message(session_id, "user", "m4")
    texts = [m["parts"][0]["text"] for m in chatbot_core.HistoryManager(user_id="v").get_messages(session_id)]
    assert texts == ["m1", "m2", "m4"]


def test_read_failure_at_startup_does_not_write_a_stale_copy(monkeypatch, tmp_path):
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)
    writer = chatbot_core.HistoryManager(user_id="w")
    session_id = writer.create_session(owner_id="alice")
    writer.add_message(session_id, "user", "m1")

    real_load = chatbot_storage.load_history_sessions_from_sqlite
    monkeypatch.setattr(chatbot_storage, "load_history_sessions_from_sqlite", lambda *a, **k: None)
    booted = chatbot_core.HistoryManager(user_id="b")
    booted.add_message(session_id, "user", "lost")
    monkeypatch.setattr(chatbot_storage, "load_history_sessions_from_sqlite", real_load)

    booted.add_message(session_id, "user", "m2")
    texts = [m["parts"][0]["text"] for m in chatbot_core.HistoryManager(user_id="v").get_messages(session_id)]
    assert texts == ["m1", "m2"]
