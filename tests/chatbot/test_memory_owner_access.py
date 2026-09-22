#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
챗봇 메모리 소유자 분리 회귀 테스트
"""

import json
import logging
import os
import sqlite3
import sys
from pathlib import Path

import pytest


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import chatbot.core as chatbot_core
from chatbot.command_service import handle_memory_command
from chatbot.payload_service import compose_system_prompt
from chatbot.runtime_setup_service import (
    DEFAULT_PROFILE,
    get_user_profile,
    update_user_profile,
)
from chatbot.storage_sqlite_common import (
    _ensure_chatbot_memories_owner_column,
    ensure_chatbot_storage_schema,
    resolve_chatbot_storage_db_path,
)
from chatbot.storage_sqlite_memory import (
    clear_memories_in_sqlite,
    delete_memory_entry_in_sqlite,
    load_memories_from_sqlite,
    save_memories_to_sqlite,
    upsert_memory_entry_in_sqlite,
)


_LOGGER = logging.getLogger("test_memory_owner_access")


def _create_legacy_memory_table(db_path: Path) -> None:
    """소유자 열이 없던 구 스키마를 그대로 만든다."""
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE chatbot_memories (
                memory_key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO chatbot_memories (memory_key, value_json, updated_at)
            VALUES ('interest', '"종가베팅"', '2026-02-24T14:53:29.893673')
            """
        )
        conn.commit()


def test_schema_migration_moves_legacy_rows_to_public_owner(tmp_path: Path):
    """소유자를 알 수 없는 기존 행은 공용('')으로 옮겨진다."""
    db_path = resolve_chatbot_storage_db_path(tmp_path)
    _create_legacy_memory_table(db_path)

    assert ensure_chatbot_storage_schema(db_path, _LOGGER, force_recheck=True)

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT owner_id, memory_key FROM chatbot_memories"
        ).fetchall()
    assert rows == [("", "interest")]


def test_schema_migration_allows_same_key_for_different_owners(tmp_path: Path):
    """기본 키가 (owner_id, memory_key) 로 옮겨졌는지 확인한다."""
    db_path = resolve_chatbot_storage_db_path(tmp_path)
    assert ensure_chatbot_storage_schema(db_path, _LOGGER, force_recheck=True)

    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO chatbot_memories (owner_id, memory_key, value_json, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            [
                ("owner-a", "risk", '"aggressive"', "2026-09-05T00:00:00"),
                ("owner-b", "risk", '"conservative"', "2026-09-05T00:00:01"),
            ],
        )
        conn.commit()
        count = conn.execute("SELECT COUNT(*) FROM chatbot_memories").fetchone()[0]
    assert count == 2


class _FailingCursor:
    """지정한 문장에서 한 번 실패하는 커서. 마이그레이션의 원자성을 검사한다."""

    def __init__(self, cursor: sqlite3.Cursor, fail_on: str):
        self._cursor = cursor
        self._fail_on = fail_on

    def execute(self, sql: str, *args):
        if self._fail_on in sql:
            raise sqlite3.OperationalError("주입한 실패")
        return self._cursor.execute(sql, *args)

    @property
    def connection(self) -> sqlite3.Connection:
        return self._cursor.connection


def test_schema_migration_is_atomic_on_failure(tmp_path: Path):
    """마이그레이션이 중간에 실패해도 기존 데이터가 그대로 남는다.

    트랜잭션으로 감싸지 않으면 새 빈 테이블과 데이터가 든 legacy 테이블이 함께
    남고, 다음 실행에서는 owner_id 가 이미 있어 마이그레이션이 건너뛰어지므로
    갇힌 데이터를 영영 잃는다.
    """
    db_path = resolve_chatbot_storage_db_path(tmp_path)
    _create_legacy_memory_table(db_path)

    with sqlite3.connect(db_path) as conn:
        failing = _FailingCursor(conn.cursor(), fail_on="INSERT INTO chatbot_memories")
        with pytest.raises(sqlite3.OperationalError):
            _ensure_chatbot_memories_owner_column(failing, _LOGGER)

    # 실패했으므로 구 스키마와 데이터가 그대로여야 한다.
    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        rows = conn.execute("SELECT memory_key FROM chatbot_memories").fetchall()
    assert "chatbot_memories_legacy" not in tables
    assert rows == [("interest",)]

    # 그다음 정상 마이그레이션이 데이터를 잃지 않고 끝난다.
    assert ensure_chatbot_storage_schema(db_path, _LOGGER, force_recheck=True)
    with sqlite3.connect(db_path) as conn:
        assert conn.execute(
            "SELECT owner_id, memory_key FROM chatbot_memories"
        ).fetchall() == [("", "interest")]


def test_schema_migration_skips_when_another_worker_already_migrated(tmp_path: Path):
    """다른 워커가 먼저 끝냈으면 마이그레이션을 되돌리지 않는다.

    바깥의 컬럼 확인과 잠금 획득 사이에 다른 프로세스가 마이그레이션을 끝낼 수
    있다. 그대로 진행하면 이미 옮겨 놓은 테이블을 legacy 로 되돌리고 소유자를
    전부 공용으로 되돌린다.
    """
    db_path = resolve_chatbot_storage_db_path(tmp_path)
    assert ensure_chatbot_storage_schema(db_path, _LOGGER, force_recheck=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO chatbot_memories (owner_id, memory_key, value_json, updated_at)
            VALUES ('owner-a', 'risk', '"aggressive"', '2026-09-05T00:00:00')
            """
        )
        conn.commit()

    # 마이그레이션이 끝난 테이블에 대고 함수를 다시 부른다. 바깥 확인을 통과한
    # 뒤 잠금을 잡은 시점의 상태가 바로 이것이다.
    with sqlite3.connect(db_path) as conn:
        _ensure_chatbot_memories_owner_column(conn.cursor(), _LOGGER)
        conn.commit()

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT owner_id, memory_key FROM chatbot_memories"
        ).fetchall()
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    assert rows == [("owner-a", "risk")]
    assert "chatbot_memories_legacy" not in tables


def test_sqlite_round_trip_keeps_owners_apart(tmp_path: Path):
    """서로 다른 소유자의 같은 키가 각자 저장되고 각자 돌아온다."""
    db_path = resolve_chatbot_storage_db_path(tmp_path)
    memories = {
        "": {"interest": {"value": "종가베팅", "updated_at": "2026-02-24T14:53:29"}},
        "owner-a": {"risk": {"value": "aggressive", "updated_at": "2026-09-05T00:00:00"}},
        "owner-b": {"risk": {"value": "conservative", "updated_at": "2026-09-05T00:00:01"}},
    }

    assert save_memories_to_sqlite(db_path, memories, _LOGGER)
    loaded = load_memories_from_sqlite(db_path, _LOGGER)

    assert loaded is not None
    assert loaded["owner-a"]["risk"]["value"] == "aggressive"
    assert loaded["owner-b"]["risk"]["value"] == "conservative"
    assert loaded[""]["interest"]["value"] == "종가베팅"


def test_sqlite_single_entry_operations_scope_to_owner(tmp_path: Path):
    """단건 저장과 삭제가 다른 소유자의 같은 키를 건드리지 않는다."""
    db_path = resolve_chatbot_storage_db_path(tmp_path)
    record = {"value": "aggressive", "updated_at": "2026-09-05T00:00:00"}

    assert upsert_memory_entry_in_sqlite(db_path, "owner-a", "risk", record, _LOGGER)
    assert upsert_memory_entry_in_sqlite(db_path, "owner-b", "risk", record, _LOGGER)
    assert delete_memory_entry_in_sqlite(db_path, "owner-a", "risk", _LOGGER)

    loaded = load_memories_from_sqlite(db_path, _LOGGER)
    assert loaded is not None
    assert "owner-a" not in loaded
    assert loaded["owner-b"]["risk"]["value"] == "aggressive"


def test_sqlite_clear_scopes_to_owner(tmp_path: Path):
    """소유자를 주고 지우면 그 소유자의 행만 사라진다."""
    db_path = resolve_chatbot_storage_db_path(tmp_path)
    record = {"value": "aggressive", "updated_at": "2026-09-05T00:00:00"}
    assert upsert_memory_entry_in_sqlite(db_path, "owner-a", "risk", record, _LOGGER)
    assert upsert_memory_entry_in_sqlite(db_path, "", "interest", record, _LOGGER)

    assert clear_memories_in_sqlite(db_path, _LOGGER, owner_id="owner-a")

    loaded = load_memories_from_sqlite(db_path, _LOGGER)
    assert loaded is not None
    assert "owner-a" not in loaded
    assert loaded[""]["interest"]["value"] == "aggressive"


def test_format_for_prompt_excludes_other_owners(monkeypatch, tmp_path: Path):
    """남의 메모리는 프롬프트에 실리지 않는다."""
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)
    memory = chatbot_core.MemoryManager(user_id="u1")
    memory.add("보유종목", "삼성전자", owner_id="owner-a")

    assert "삼성전자" in memory.format_for_prompt("owner-a")
    assert memory.format_for_prompt("owner-b") == ""


def test_format_for_prompt_excludes_public_area(monkeypatch, tmp_path: Path):
    """공용 영역은 프롬프트에 실리지 않는다.

    추천 질문 캐시(daily_suggestions_*)와 고정값(interest)이 여기 들어 있어서,
    종전에는 724바이트짜리 캐시 JSON 이 「사용자 정보」로 프롬프트에 실렸다.
    """
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)
    memory = chatbot_core.MemoryManager(user_id="u1")
    memory.add("daily_suggestions_default_empty", [{"prompt": "질문"}])

    assert memory.format_for_prompt("owner-a") == ""
    assert memory.format_for_prompt() == ""


def test_view_excludes_other_owners(monkeypatch, tmp_path: Path):
    """남의 메모리는 조회에도 나오지 않는다."""
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)
    memory = chatbot_core.MemoryManager(user_id="u1")
    memory.add("보유종목", "삼성전자", owner_id="owner-a")

    assert "보유종목" in memory.view("owner-a")
    assert memory.view("owner-b") == {}
    assert memory.view() == {}


def test_clear_scopes_to_requesting_owner(monkeypatch, tmp_path: Path):
    """초기화는 요청자의 메모리만 지운다."""
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)
    memory = chatbot_core.MemoryManager(user_id="u1")
    memory.add("보유종목", "삼성전자", owner_id="owner-a")
    memory.add("보유종목", "카카오", owner_id="owner-b")

    memory.clear("owner-a")

    assert memory.view("owner-a") == {}
    assert memory.view("owner-b")["보유종목"]["value"] == "카카오"


def test_legacy_json_snapshot_loads_as_public(monkeypatch, tmp_path: Path):
    """1단으로 저장된 레거시 JSON 스냅샷은 전부 공용으로 읽는다."""
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)
    (tmp_path / "chatbot_memory.json").write_text(
        json.dumps({"interest": {"value": "종가베팅", "updated_at": "2026-02-24T00:00:00"}}),
        encoding="utf-8",
    )

    memory = chatbot_core.MemoryManager(user_id="u1")

    assert memory.view()["interest"]["value"] == "종가베팅"
    assert memory.view("owner-a") == {}


def test_legacy_json_snapshot_keeps_two_level_when_key_is_named_value(
    monkeypatch, tmp_path: Path
):
    """`value` 라는 키를 저장한 2단 스냅샷을 1단으로 오판하지 않는다.

    판정이 "value" 키의 유무만 보면 사용자가 `/memory add value 삼성전자` 로
    넣은 스냅샷이 통째로 공용 아래로 내려가 누구에게도 보이지 않게 된다.
    """
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)
    (tmp_path / "chatbot_memory.json").write_text(
        json.dumps(
            {"owner-a": {"value": {"value": "삼성전자", "updated_at": "2026-09-05T00:00:00"}}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    memory = chatbot_core.MemoryManager(user_id="u1")

    assert memory.view("owner-a")["value"]["value"] == "삼성전자"
    assert memory.view() == {}


def test_worker_sees_rows_saved_by_another_worker(monkeypatch, tmp_path: Path):
    """다른 워커(다른 인스턴스)가 저장하거나 지운 행이 다음 조회에 반영된다.

    [CHAT-022] 종전에는 생성자에서 한 번 읽은 스냅샷을 다시 읽지 않아, 워커 A 에서
    `/memory add` 한 값이 워커 B 로 간 `/memory view` 에 보이지 않았다.
    """
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)
    worker_a = chatbot_core.MemoryManager(user_id="u1")
    worker_b = chatbot_core.MemoryManager(user_id="u1")

    worker_a.add("보유종목", "삼성전자", owner_id="owner-a")

    assert worker_b.view("owner-a")["보유종목"]["value"] == "삼성전자"
    assert "삼성전자" in worker_b.format_for_prompt("owner-a")

    worker_a.clear("owner-a")

    assert worker_b.view("owner-a") == {}


def test_failed_single_save_does_not_delete_other_workers_rows(monkeypatch, tmp_path: Path):
    """단건 저장이 실패해도 다른 워커가 저장한 행을 지우지 않는다.

    [CHAT-022] 종전에는 실패 폴백이 자기 스냅샷으로 전체 동기화를 돌려 스냅샷에
    없는 행을 전부 지웠다. 워커 B 의 낡은 스냅샷에는 워커 A 가 저장한 행이 없었다.
    재적재까지 막아 스냅샷이 낡은 상태를 그대로 재현한다.
    """
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)
    worker_a = chatbot_core.MemoryManager(user_id="u1")
    worker_b = chatbot_core.MemoryManager(user_id="u1")
    worker_a.add("보유종목", "삼성전자", owner_id="owner-a")

    monkeypatch.setattr(
        "chatbot.storage_memory_manager.load_memories_from_sqlite",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "chatbot.storage_memory_manager.upsert_memory_entry_in_sqlite",
        lambda *args, **kwargs: False,
    )
    worker_b.add("보유종목", "카카오", owner_id="owner-b")

    db_path = resolve_chatbot_storage_db_path(tmp_path)
    loaded = load_memories_from_sqlite(db_path, _LOGGER)
    assert loaded is not None
    assert loaded["owner-a"]["보유종목"]["value"] == "삼성전자"


class _FakeOwnedMemory:
    """소유자별 2단 구조를 흉내 낸다."""

    def __init__(self):
        self.store: dict[str, dict[str, dict]] = {}

    def view(self, owner_id=None):
        return self.store.get(owner_id or "", {})

    def add(self, key, value, owner_id=None):
        self.store.setdefault(owner_id or "", {})[key] = {"value": value}
        return "OK_ADD"

    def clear(self, owner_id=None):
        self.store.pop(owner_id or "", None)
        return "OK_CLEAR"


class _MemoryOnlyBot:
    def __init__(self):
        self.memory = _FakeOwnedMemory()


def test_memory_command_shows_only_requesting_owner():
    """/memory view 는 요청자의 메모리만 보여 준다."""
    bot = _MemoryOnlyBot()
    bot.memory.add("보유종목", "삼성전자", owner_id="owner-a")

    assert "삼성전자" in handle_memory_command(bot, ["view"], owner_id="owner-a")
    assert "저장된 메모리가 없습니다" in handle_memory_command(bot, ["view"], owner_id="owner-b")


def test_memory_command_refuses_without_owner():
    """소유자를 모르는 요청은 공용 영역에 닿지 못한다."""
    bot = _MemoryOnlyBot()
    bot.memory.add("daily_suggestions_default_empty", [{"prompt": "질문"}])

    response = handle_memory_command(bot, ["view"], owner_id=None)
    assert response.startswith("⚠️")
    assert "daily_suggestions" not in response


def test_memory_help_works_without_owner():
    """도움말은 소유자가 없어도 볼 수 있다."""
    bot = _MemoryOnlyBot()
    assert "메모리 명령어 도움말" in handle_memory_command(bot, [], owner_id=None)
    assert "메모리 명령어 도움말" in handle_memory_command(bot, ["help"], owner_id=None)


class _PromptFakeMemory:
    def __init__(self):
        self.seen_owner_ids: list = []

    def format_for_prompt(self, owner_id=None):
        self.seen_owner_ids.append(owner_id)
        return "MEM" if owner_id == "owner-a" else ""


class _PromptFakeBot:
    def __init__(self):
        self.memory = _PromptFakeMemory()

    def _detect_stock_query(self, user_message):
        _ = user_message
        return ""


def test_compose_system_prompt_passes_owner_to_memory():
    """프롬프트 조립이 요청자의 소유자 ID 를 메모리에 그대로 넘긴다."""
    bot = _PromptFakeBot()

    owned = compose_system_prompt(
        bot=bot,
        user_message="질문",
        target_model_name="gemini-2.0-flash-lite",
        market_data={},
        vcp_data=[],
        sector_scores={},
        watchlist=None,
        persona=None,
        additional_context="",
        owner_id="owner-a",
    )
    other = compose_system_prompt(
        bot=bot,
        user_message="질문",
        target_model_name="gemini-2.0-flash-lite",
        market_data={},
        vcp_data=[],
        sector_scores={},
        watchlist=None,
        persona=None,
        additional_context="",
        owner_id="owner-b",
    )

    assert bot.memory.seen_owner_ids == ["owner-a", "owner-b"]
    assert "MEM" in owned
    assert "MEM" not in other


def test_user_profile_is_isolated_by_owner(monkeypatch, tmp_path: Path):
    """프로필도 소유자별로 나뉜다.

    [CHAT-017] 이 메모리 저장소를 나눈 뒤에도 프로필만 공용 한 벌을 함께 쓰고
    있었다. 프로필 API 가 소유자를 넘기지 않았기 때문이다.
    """
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)
    memory = chatbot_core.MemoryManager(user_id="u1")

    update_user_profile(memory, "갑", "공격적", owner_id="owner-a")
    update_user_profile(memory, "을", "보수적", owner_id="owner-b")

    assert get_user_profile(memory, "owner-a") == {"name": "갑", "persona": "공격적"}
    assert get_user_profile(memory, "owner-b") == {"name": "을", "persona": "보수적"}


def test_user_profile_without_owner_falls_back_to_default(monkeypatch, tmp_path: Path):
    """소유자를 모르면 남의 프로필이 아니라 기본값이 나온다."""
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)
    memory = chatbot_core.MemoryManager(user_id="u1")

    update_user_profile(memory, "갑", "공격적", owner_id="owner-a")

    assert get_user_profile(memory) == DEFAULT_PROFILE


def test_saved_profile_reaches_only_its_owner_prompt(monkeypatch, tmp_path: Path):
    """프로필이 소유자 버킷에 들어가면서 그 사용자의 프롬프트에도 실린다.

    종전에는 공용에만 있어 어느 프롬프트에도 실리지 않았다. 의도한 변화이므로
    고정해 둔다. 남의 프롬프트에는 실리지 않아야 한다.
    """
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)
    memory = chatbot_core.MemoryManager(user_id="u1")

    update_user_profile(memory, "갑", "공격적", owner_id="owner-a")

    assert "공격적" in memory.format_for_prompt("owner-a")
    assert memory.format_for_prompt("owner-b") == ""


def test_delete_owner_removes_profile_too_and_keeps_other_owners(monkeypatch, tmp_path: Path):
    """계정 삭제는 user_profile 까지 지우고 다른 소유자와 공용 행은 남긴다([FE-045])."""
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)
    manager = chatbot_core.MemoryManager("u1")
    manager.add("risk", "aggressive", owner_id="alice@example.test")
    update_user_profile(manager, "앨리스", "리서치", "alice@example.test")
    manager.add("risk", "conservative", owner_id="bob@example.test")
    manager.add("interest", "종가베팅")  # 공용

    assert manager.delete_owner("alice@example.test") is True

    with sqlite3.connect(resolve_chatbot_storage_db_path(tmp_path)) as conn:
        owners = sorted({row[0] for row in conn.execute("SELECT owner_id FROM chatbot_memories")})
    assert owners == ["", "bob@example.test"]
    assert manager.view("alice@example.test") == {}
    assert manager.delete_owner("") is False


def test_delete_owner_reports_failure_when_snapshot_is_not_written(monkeypatch, tmp_path: Path):
    """SQLite 삭제가 성공해도 레거시 스냅샷 갱신이 실패하면 성공으로 돌려주지 않는다([FE-045])."""
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)
    manager = chatbot_core.MemoryManager("u1")
    manager.add("risk", "aggressive", owner_id="alice@example.test")
    monkeypatch.setattr(manager, "_write_legacy_memory_snapshot", lambda *a, **k: False)

    assert manager.delete_owner("alice@example.test") is False

    with sqlite3.connect(resolve_chatbot_storage_db_path(tmp_path)) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM chatbot_memories WHERE owner_id = ?", ("alice@example.test",)
        ).fetchone()[0] == 0
