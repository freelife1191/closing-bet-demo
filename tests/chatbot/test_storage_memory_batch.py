#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CHAT-023/027 메모리 경계와 공용 추천 캐시 회귀 테스트."""

import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import chatbot.storage_memory_manager as storage_memory_manager
import chatbot.storage_sqlite_memory as storage_sqlite_memory

from chatbot.command_service import handle_clear_command, handle_memory_command
from chatbot.data_service import get_cached_daily_suggestions
from chatbot.runtime_setup_service import DEFAULT_PROFILE, get_user_profile, update_user_profile
from chatbot.storage_memory_manager import MemoryManager
from chatbot.storage_sqlite_memory import load_memories_from_sqlite


_LOGGER = logging.getLogger("test_storage_memory_batch")
_CACHE_PREFIX = "daily_suggestions_"


class _OwnerHistory:
    def clear_for_owner(self, owner_id: str) -> int:
        assert owner_id == "owner-a"
        return 0


def _new_manager(tmp_path: Path, monkeypatch) -> MemoryManager:
    monkeypatch.setenv("CHATBOT_MEMORY_LEGACY_SNAPSHOT_INTERVAL_SECONDS", "0")
    return MemoryManager(user_id="test-user", data_dir=tmp_path)


def _cache_record(value: object, updated_at: datetime) -> dict[str, object]:
    return {"value": value, "updated_at": updated_at.isoformat()}


def test_memory_commands_keep_profile_in_settings_boundary(tmp_path: Path, monkeypatch) -> None:
    """일반 메모리 명령은 설정 프로필을 노출하거나 변경·삭제하지 않는다."""
    memory = _new_manager(tmp_path, monkeypatch)
    bot = SimpleNamespace(memory=memory)
    update_user_profile(memory, "갑", "공격적", owner_id="owner-a")
    memory.add("watch", "삼성전자", owner_id="owner-a")

    rendered = handle_memory_command(bot, ["view"], owner_id="owner-a")
    assert "watch" in rendered
    assert "user_profile" not in rendered
    assert "공격적" not in rendered

    for action in (
        ["add", "user_profile", "변경"],
        ["update", "user_profile", "변경"],
        ["remove", "user_profile"],
    ):
        response = handle_memory_command(bot, action, owner_id="owner-a")
        assert "설정" in response
        assert get_user_profile(memory, "owner-a") == {"name": "갑", "persona": "공격적"}

    assert "초기화" in handle_memory_command(bot, ["clear"], owner_id="owner-a")
    assert memory.view("owner-a") == {
        "user_profile": memory.get("user_profile", "owner-a")
    }
    assert get_user_profile(memory, "owner-a") == {"name": "갑", "persona": "공격적"}

    clear_all_bot = SimpleNamespace(
        history=_OwnerHistory(),
        memory=memory,
    )
    assert "초기화" in handle_clear_command(
        clear_all_bot,
        ["/clear", "all"],
        session_id=None,
        owner_id="owner-a",
    )
    assert get_user_profile(memory, "owner-a") == DEFAULT_PROFILE


def test_legacy_public_cache_is_normalized_without_touching_other_namespaces(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """legacy JSON 이관 전 공용 literal 캐시만 TTL/500 정책으로 정규화한다."""
    now = datetime.now()
    valid_time = now - timedelta(minutes=30)
    expired_time = now - timedelta(hours=2)
    future_time = now + timedelta(minutes=1)
    public_cache = {
        f"{_CACHE_PREFIX}default_{index:03d}": _cache_record(index, valid_time)
        for index in range(502)
    }
    public_cache[f"{_CACHE_PREFIX}expired"] = _cache_record("old", expired_time)
    public_cache[f"{_CACHE_PREFIX}future"] = _cache_record("future", future_time)
    public_cache["shared_note"] = _cache_record("keep", valid_time)
    public_cache["user_profile"] = _cache_record(
        {"name": "공용", "persona": "중립"}, valid_time
    )
    legacy = {
        "": public_cache,
        "owner-a": {
            f"{_CACHE_PREFIX}private": _cache_record("private", expired_time),
            "user_profile": _cache_record({"name": "갑", "persona": "공격적"}, valid_time),
        },
    }
    (tmp_path / "chatbot_memory.json").write_text(
        json.dumps(legacy, ensure_ascii=False),
        encoding="utf-8",
    )

    memory = _new_manager(tmp_path, monkeypatch)
    shared = memory.view("")
    shared_cache_keys = sorted(
        key for key in shared if key.startswith(_CACHE_PREFIX)
    )

    assert len(shared_cache_keys) == 500
    assert f"{_CACHE_PREFIX}expired" not in shared
    assert f"{_CACHE_PREFIX}future" not in shared
    assert f"{_CACHE_PREFIX}default_000" not in shared
    assert f"{_CACHE_PREFIX}default_501" in shared
    assert shared["shared_note"]["value"] == "keep"
    assert shared["user_profile"]["value"]["name"] == "공용"
    assert memory.view("owner-a")[f"{_CACHE_PREFIX}private"]["value"] == "private"

    sqlite_memories = load_memories_from_sqlite(memory.db_path, _LOGGER)
    assert sqlite_memories == memory.to_dict()
    snapshot = json.loads((tmp_path / "chatbot_memory.json").read_text(encoding="utf-8"))
    assert snapshot == memory.to_dict()


def test_daily_suggestions_cache_is_bounded_across_memory_managers(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """여러 매니저의 공용 추천 캐시 저장도 500개와 JSON/SQLite 동기화를 지킨다."""
    manager_a = _new_manager(tmp_path, monkeypatch)
    manager_b = _new_manager(tmp_path, monkeypatch)
    manager_a.add("shared_note", "keep")
    manager_b.add(f"{_CACHE_PREFIX}private", "keep", owner_id="owner-b")
    update_user_profile(manager_a, "갑", "공격적", owner_id="owner-a")

    for index in range(502):
        manager = manager_a if index % 2 == 0 else manager_b
        assert manager.save_daily_suggestions(
            f"{_CACHE_PREFIX}default_{index:03d}", [{"title": str(index)}]
        )

    restored = _new_manager(tmp_path, monkeypatch)
    shared = restored.view("")
    shared_cache_keys = [key for key in shared if key.startswith(_CACHE_PREFIX)]
    assert len(shared_cache_keys) == 500
    assert shared["shared_note"]["value"] == "keep"
    assert restored.view("owner-b")[f"{_CACHE_PREFIX}private"]["value"] == "keep"
    assert get_user_profile(restored, "owner-a") == {"name": "갑", "persona": "공격적"}

    sqlite_memories = load_memories_from_sqlite(restored.db_path, _LOGGER)
    assert sqlite_memories == restored.to_dict()
    snapshot = json.loads((tmp_path / "chatbot_memory.json").read_text(encoding="utf-8"))
    assert snapshot == restored.to_dict()


def test_daily_suggestions_save_failure_does_not_apply_memory_or_snapshot(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """원자적 캐시 저장 실패는 메모리·legacy JSON에 성공처럼 남지 않는다."""
    memory = _new_manager(tmp_path, monkeypatch)
    memory.add("shared_note", "before")
    before_memory = memory.to_dict().copy()
    before_snapshot = (tmp_path / "chatbot_memory.json").read_text(encoding="utf-8")

    monkeypatch.setattr(
        "chatbot.storage_memory_manager.save_daily_suggestions_in_sqlite",
        lambda *args, **kwargs: False,
    )

    assert not memory.save_daily_suggestions(
        f"{_CACHE_PREFIX}default_failure", [{"title": "실패"}]
    )
    assert memory.to_dict() == before_memory
    assert (tmp_path / "chatbot_memory.json").read_text(encoding="utf-8") == before_snapshot


def test_snapshot_failure_keeps_committed_daily_suggestions_cache(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """스냅샷 실패는 저장 실패로 알리되 이미 커밋한 SQLite 캐시는 되돌리지 않는다."""
    memory = _new_manager(tmp_path, monkeypatch)
    memory.add("shared_note", "before")
    before_snapshot = (tmp_path / "chatbot_memory.json").read_text(encoding="utf-8")

    monkeypatch.setattr(
        "chatbot.storage_memory_manager.atomic_write_json",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("snapshot failure")),
    )

    key = f"{_CACHE_PREFIX}default_snapshot_failure"
    assert not memory.save_daily_suggestions(key, [{"title": "커밋"}])
    sqlite_memories = load_memories_from_sqlite(memory.db_path, _LOGGER)
    assert sqlite_memories is not None
    assert sqlite_memories[""][key]["value"] == [{"title": "커밋"}]
    assert (tmp_path / "chatbot_memory.json").read_text(encoding="utf-8") == before_snapshot


def test_clear_general_failure_preserves_memory_and_snapshot(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """일반 메모리 삭제가 실패하면 공용 또는 프로필로 흘러가지 않고 상태를 보존한다."""
    memory = _new_manager(tmp_path, monkeypatch)
    update_user_profile(memory, "갑", "공격적", owner_id="owner-a")
    memory.add("watch", "삼성전자", owner_id="owner-a")
    before_memory = json.loads(json.dumps(memory.to_dict(), ensure_ascii=False))
    before_snapshot = (tmp_path / "chatbot_memory.json").read_text(encoding="utf-8")

    monkeypatch.setattr(
        "chatbot.storage_memory_manager.clear_general_memories_in_sqlite",
        lambda *args, **kwargs: False,
    )

    assert "실패" in memory.clear_general("owner-a")
    assert "식별" in memory.clear_general("")
    assert memory.to_dict() == before_memory
    assert (tmp_path / "chatbot_memory.json").read_text(encoding="utf-8") == before_snapshot


def test_profile_only_memory_load_does_not_open_a_write_connection(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """정리 대상이 없으면 프로필 조회가 cache prune 쓰기 락을 잡지 않는다."""
    memory = _new_manager(tmp_path, monkeypatch)
    update_user_profile(memory, "갑", "공격적", owner_id="owner-a")
    observed_read_only: list[bool] = []
    original_connect_sqlite = storage_sqlite_memory.connect_sqlite

    def _observe_connect_sqlite(*args, **kwargs):
        observed_read_only.append(bool(kwargs.get("read_only")))
        return original_connect_sqlite(*args, **kwargs)

    monkeypatch.setattr(storage_sqlite_memory, "connect_sqlite", _observe_connect_sqlite)

    loaded = load_memories_from_sqlite(memory.db_path, _LOGGER)

    assert loaded is not None
    assert get_user_profile(memory, "owner-a") == {"name": "갑", "persona": "공격적"}
    assert observed_read_only
    assert all(observed_read_only)


def test_delayed_daily_suggestions_writer_keeps_newer_writer_cache(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """대기한 writer의 오래된 now가 먼저 끝난 writer 캐시를 future로 지우지 않는다."""
    manager_a = _new_manager(tmp_path, monkeypatch)
    manager_b = _new_manager(tmp_path, monkeypatch)
    key_a = f"{_CACHE_PREFIX}default_delayed_a"
    key_b = f"{_CACHE_PREFIX}default_newer_b"
    original_save = storage_memory_manager.save_daily_suggestions_in_sqlite
    entered = False

    def _save_b_before_a(*args, **kwargs):
        nonlocal entered
        if not entered:
            entered = True
            assert manager_b.save_daily_suggestions(key_b, [{"title": "B"}])
        return original_save(*args, **kwargs)

    monkeypatch.setattr(
        storage_memory_manager,
        "save_daily_suggestions_in_sqlite",
        _save_b_before_a,
    )

    assert manager_a.save_daily_suggestions(key_a, [{"title": "A"}])
    loaded = load_memories_from_sqlite(manager_a.db_path, _LOGGER)
    assert loaded is not None
    assert loaded[""][key_a]["value"] == [{"title": "A"}]
    assert loaded[""][key_b]["value"] == [{"title": "B"}]


def test_delayed_daily_suggestions_reader_keeps_newer_writer_cache(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """대기한 reader의 오래된 now가 앞서 저장된 캐시를 future로 지우지 않는다."""
    reader = _new_manager(tmp_path, monkeypatch)
    writer = _new_manager(tmp_path, monkeypatch)
    reader.add("shared_note", "ready")
    key_b = f"{_CACHE_PREFIX}default_newer_reader_b"
    original_prune = storage_sqlite_memory._prune_daily_suggestions_in_sqlite
    entered = False

    def _save_b_before_reader_prune(*args, **kwargs):
        nonlocal entered
        if not entered:
            entered = True
            assert writer.save_daily_suggestions(key_b, [{"title": "B"}])
        return original_prune(*args, **kwargs)

    monkeypatch.setattr(
        storage_sqlite_memory,
        "_prune_daily_suggestions_in_sqlite",
        _save_b_before_reader_prune,
    )

    loaded = load_memories_from_sqlite(reader.db_path, _LOGGER)
    assert loaded is not None
    assert loaded[""][key_b]["value"] == [{"title": "B"}]


def test_legacy_snapshot_written_after_sql_miss_keeps_new_cache(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """SQLite 미스 뒤 새로 읽은 legacy 캐시를 future로 오인해 지우지 않는다."""
    key = f"{_CACHE_PREFIX}default_legacy_after_sql_miss"
    memory_file = tmp_path / "chatbot_memory.json"
    original_load_memories = storage_memory_manager.load_memories_from_sqlite
    entered = False

    def _write_legacy_after_sql_miss(*args, **kwargs):
        nonlocal entered
        result = original_load_memories(*args, **kwargs)
        if not entered:
            entered = True
            assert result is None
            storage_memory_manager.atomic_write_json(
                memory_file,
                {"": {key: _cache_record([{"title": "새 캐시"}], datetime.now())}},
            )
        return result

    monkeypatch.setattr(
        storage_memory_manager,
        "load_memories_from_sqlite",
        _write_legacy_after_sql_miss,
    )

    memory = _new_manager(tmp_path, monkeypatch)

    assert memory.view("")[key]["value"] == [{"title": "새 캐시"}]


def test_daily_suggestions_cache_hit_uses_time_after_memory_get(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """memory.get 도중 새로 저장된 캐시도 현재 요청에서 cache hit로 사용한다."""
    memory = _new_manager(tmp_path, monkeypatch)
    key = f"{_CACHE_PREFIX}default_get_race"
    original_get = memory.get
    entered = False

    def _save_before_get(cache_key, owner_id=None):
        nonlocal entered
        if not entered:
            entered = True
            assert memory.save_daily_suggestions(key, [{"title": "새 캐시"}])
        return original_get(cache_key, owner_id)

    monkeypatch.setattr(memory, "get", _save_before_get)

    assert get_cached_daily_suggestions(memory, key, datetime.now()) == [
        {"title": "새 캐시"}
    ]


def test_snapshot_boundary_keeps_committed_other_writer(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """스냅샷 직전 다른 매니저가 커밋해도 JSON은 SQLite와 같은 행을 보존한다."""
    manager_a = _new_manager(tmp_path, monkeypatch)
    manager_b = _new_manager(tmp_path, monkeypatch)
    key_a = f"{_CACHE_PREFIX}default_snapshot_boundary_a"
    key_b = f"{_CACHE_PREFIX}default_snapshot_boundary_b"
    original_snapshot = MemoryManager._write_legacy_memory_snapshot
    entered = False

    def _save_b_before_a_snapshot(self, memories):
        nonlocal entered
        if self is manager_a and not entered:
            entered = True
            update_user_profile(manager_b, "을", "중립", owner_id="owner-b")
            assert manager_b.save_daily_suggestions(key_b, [{"title": "B"}])
        return original_snapshot(self, memories)

    monkeypatch.setattr(
        MemoryManager,
        "_write_legacy_memory_snapshot",
        _save_b_before_a_snapshot,
    )

    assert manager_a.save_daily_suggestions(key_a, [{"title": "A"}])
    snapshot = json.loads((tmp_path / "chatbot_memory.json").read_text(encoding="utf-8"))
    sqlite_memories = load_memories_from_sqlite(manager_a.db_path, _LOGGER)
    assert sqlite_memories is not None
    assert snapshot == sqlite_memories
    assert snapshot[""][key_a]["value"] == [{"title": "A"}]
    assert snapshot[""][key_b]["value"] == [{"title": "B"}]

    assert manager_a.to_dict() == snapshot
    assert snapshot["owner-b"]["user_profile"]["value"]["name"] == "을"
