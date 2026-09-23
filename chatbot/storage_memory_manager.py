#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
챗봇 메모리 저장 매니저
"""

from __future__ import annotations

import fcntl
import json
import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .storage_history_helpers import atomic_write_json, locked
from .storage_sqlite_helpers import (
    clear_general_memories_in_sqlite,
    clear_memories_in_sqlite,
    delete_memory_entry_in_sqlite,
    load_memories_from_sqlite,
    normalize_daily_suggestions_memories,
    resolve_chatbot_storage_db_path,
    save_daily_suggestions_in_sqlite,
    save_memories_to_sqlite,
    upsert_memory_entry_in_sqlite,
)


logger = logging.getLogger(__name__)

PUBLIC_OWNER_ID = ""


def _normalize_memory_owner_id(owner_id: Optional[str]) -> str:
    """소유자를 모르면 공용으로 본다. 캐시와 user_profile 이 그 자리에 남는다."""
    return owner_id or PUBLIC_OWNER_ID


def _promote_legacy_flat_memories(loaded: Dict[str, Any]) -> Dict[str, Any]:
    """1단으로 저장된 레거시 스냅샷을 공용 영역으로 옮긴다.

    1단은 값이 전부 {"value": ..., "updated_at": ...} 레코드다. 두 키를 함께
    보아야 한다. "value" 만 보면 사용자가 `/memory add value 삼성전자` 로 넣은
    2단 스냅샷을 1단으로 오판해 모든 소유자를 공용 아래로 밀어 넣는다.
    """
    if loaded and all(
        isinstance(value, dict) and "value" in value and "updated_at" in value
        for value in loaded.values()
    ):
        return {PUBLIC_OWNER_ID: loaded}
    return loaded


class MemoryManager:
    """간단한 인메모리 메모리 매니저 (SQLite + JSON 스냅샷)"""

    def __init__(self, user_id: str, data_dir: Optional[Path] = None):
        self.user_id = user_id
        self.data_dir = data_dir or (Path(__file__).parent.parent / "data")
        self.file_path = self.data_dir / "chatbot_memory.json"
        self.db_path = resolve_chatbot_storage_db_path(self.data_dir)
        self._legacy_snapshot_interval_seconds = self._resolve_legacy_snapshot_interval_seconds()
        self._last_legacy_snapshot_monotonic: float | None = None
        self._lock = threading.RLock()
        self.memories = self._load()

    @staticmethod
    def _resolve_legacy_snapshot_interval_seconds() -> float:
        raw = os.getenv("CHATBOT_MEMORY_LEGACY_SNAPSHOT_INTERVAL_SECONDS", "30")
        try:
            value = float(raw)
            return value if value >= 0 else 0.0
        except (TypeError, ValueError):
            return 30.0

    def _should_sync_legacy_snapshot(self, force: bool = False) -> bool:
        if force or self._legacy_snapshot_interval_seconds <= 0:
            return True
        if self._last_legacy_snapshot_monotonic is None:
            return True
        return (time.monotonic() - self._last_legacy_snapshot_monotonic) >= self._legacy_snapshot_interval_seconds

    def _load_legacy_memory(self) -> Dict[str, Any]:
        if not self.file_path.exists():
            return {}

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
        except Exception as error:
            logger.error(f"Failed to load legacy memory JSON: {error}")
            return {}

        if isinstance(loaded, dict):
            return normalize_daily_suggestions_memories(
                _promote_legacy_flat_memories(loaded),
            )
        logger.warning(f"Unexpected memory format type: {type(loaded).__name__}")
        return {}

    def _save_legacy_memory_snapshot(self, memories: Dict[str, Any]) -> None:
        if not self._should_sync_legacy_snapshot():
            return
        self._write_legacy_memory_snapshot(memories)

    def _write_legacy_memory_snapshot(
        self,
        memories: Dict[str, Any],
        *,
        allow_uncommitted: bool = False,
    ) -> bool:
        """SQLite 권위 데이터를 sidecar lock 아래에서 legacy JSON으로 교체한다."""
        try:
            if not self.data_dir.exists():
                self.data_dir.mkdir(parents=True, exist_ok=True)
            lock_path = self.file_path.with_name(f"{self.file_path.name}.lock")
            with open(lock_path, "a+", encoding="utf-8") as lock_file:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    authoritative_memories = load_memories_from_sqlite(self.db_path, logger)
                    if authoritative_memories is None:
                        if not allow_uncommitted:
                            logger.error("SQLite memory reload failed; legacy snapshot left unchanged")
                            return False
                        authoritative_memories = memories
                    self.memories = authoritative_memories
                    atomic_write_json(self.file_path, authoritative_memories)
                    self._last_legacy_snapshot_monotonic = time.monotonic()
                    return True
                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        except Exception as error:
            logger.error(f"Failed to save legacy memory JSON snapshot: {error}")
            return False

    def _load(self) -> Dict[str, Any]:
        sqlite_memories = load_memories_from_sqlite(self.db_path, logger)
        if sqlite_memories:
            if self._write_legacy_memory_snapshot(sqlite_memories):
                return self.memories
            return sqlite_memories

        legacy_memories = self._load_legacy_memory()
        if legacy_memories:
            if save_memories_to_sqlite(self.db_path, legacy_memories, logger):
                imported_memories = load_memories_from_sqlite(self.db_path, logger)
                if imported_memories is not None:
                    if self._write_legacy_memory_snapshot(imported_memories):
                        return self.memories
                    return imported_memories
            return legacy_memories

        return sqlite_memories or {}

    def _reload(self) -> bool:
        """다른 워커가 저장한 행을 보도록 SQLite 를 다시 읽는다. 읽기 실패면 기존 스냅샷을 둔다."""
        # ponytail: 호출마다 작은 표 전체를 읽는다. 비용이 보이면 HistoryManager 처럼 파일 서명 비교를 붙인다.
        loaded = load_memories_from_sqlite(self.db_path, logger)
        if loaded is not None:
            self.memories = loaded
            return True
        return False

    def _save_single_entry(self, owner_id: str, key: str, record: Dict[str, Any]) -> None:
        sqlite_saved = upsert_memory_entry_in_sqlite(
            self.db_path,
            owner_id=owner_id,
            key=key,
            record=record,
            logger=logger,
        )
        if not sqlite_saved:
            # ponytail: 실패해도 호출자는 성공 문구를 돌려준다(remove·clear 도 같다). 다음 재적재가
            # 그 변경을 되돌린다. 종전의 전체 동기화 재시도는 다른 워커의 행을 지웠으므로 두지
            # 않는다. 유실이 실제로 보이면 여기서 예외로 올려 명령 응답을 실패로 바꾼다.
            logger.warning("SQLite single memory upsert failed; legacy JSON snapshot only")
            self._write_legacy_memory_snapshot(
                self.memories,
                allow_uncommitted=True,
            )
            return
        self._save_legacy_memory_snapshot(self.memories)

    @locked
    def view(self, owner_id: Optional[str] = None) -> Dict[str, Any]:
        self._reload()
        # 사본을 돌려준다. 호출자가 순회하는 동안 다른 스레드가 같은 사전을 바꾸지 않게 한다.
        return dict(self.memories.get(_normalize_memory_owner_id(owner_id), {}))

    def get(self, key: str, owner_id: Optional[str] = None) -> Any:
        return self.view(owner_id).get(key)

    @locked
    def add(self, key: str, value: Any, owner_id: Optional[str] = None) -> str:
        owner = _normalize_memory_owner_id(owner_id)
        self._reload()
        record = {"value": value, "updated_at": datetime.now().isoformat()}
        self.memories.setdefault(owner, {})[key] = record
        self._save_single_entry(owner, key, record)
        return f"✅ 메모리 저장: {key} = {value}"

    @locked
    def remove(self, key: str, owner_id: Optional[str] = None) -> str:
        owner = _normalize_memory_owner_id(owner_id)
        self._reload()
        owned = self.memories.get(owner, {})
        if key in owned:
            del owned[key]
            if not delete_memory_entry_in_sqlite(self.db_path, owner_id=owner, key=key, logger=logger):
                logger.warning("SQLite memory delete failed; legacy JSON snapshot only")
                self._write_legacy_memory_snapshot(
                    self.memories,
                    allow_uncommitted=True,
                )
                return f"🗑️ 메모리 삭제: {key}"
            self._write_legacy_memory_snapshot(self.memories)
            return f"🗑️ 메모리 삭제: {key}"
        return "⚠️ 해당 키를 찾을 수 없습니다."

    @locked
    def update(self, key: str, value: Any, owner_id: Optional[str] = None) -> str:
        owner = _normalize_memory_owner_id(owner_id)
        self._reload()
        owned = self.memories.get(owner, {})
        if key in owned:
            owned[key]["value"] = value
            owned[key]["updated_at"] = datetime.now().isoformat()
            self._save_single_entry(owner, key, owned[key])
            return f"✅ 메모리 수정: {key} = {value}"
        return self.add(key, value, owner_id=owner_id)

    @locked
    def clear(self, owner_id: Optional[str] = None) -> str:
        owner = _normalize_memory_owner_id(owner_id)
        self._reload()
        self.memories.pop(owner, None)
        if not clear_memories_in_sqlite(self.db_path, logger=logger, owner_id=owner):
            logger.warning("SQLite memory clear failed; legacy JSON snapshot only")
            self._write_legacy_memory_snapshot(
                self.memories,
                allow_uncommitted=True,
            )
            return "🧹 메모리가 초기화되었습니다."
        self._write_legacy_memory_snapshot(self.memories)
        return "🧹 메모리가 초기화되었습니다."

    @locked
    def delete_owner(self, owner_id: str) -> bool:
        """한 소유자의 메모리를 프로필까지 지우고 SQLite 삭제의 성패를 돌려준다([FE-045]).

        clear 와 달리 소유자를 모르면 공용으로 떨어지지 않고 거절한다. 계정 삭제가 공용
        캐시를 지워서는 안 된다.
        """
        if not owner_id:
            return False
        self._reload()
        self.memories.pop(owner_id, None)
        deleted = clear_memories_in_sqlite(self.db_path, logger=logger, owner_id=owner_id)
        # 스냅샷이 옛 메모리를 쥔 채 남으면 표가 비었을 때 _load 가 그것을 SQLite 로 되돌린다.
        written = self._write_legacy_memory_snapshot(self.memories, allow_uncommitted=not deleted)
        return deleted and written

    @locked
    def clear_general(self, owner_id: Optional[str] = None) -> str:
        """설정 프로필을 남기고 요청자의 일반 메모리만 초기화한다."""
        if not owner_id:
            logger.error("Refused to clear general memories without an owner")
            return "⚠️ 사용자를 식별할 수 없어 메모리를 초기화하지 않았습니다."
        if not clear_general_memories_in_sqlite(
            self.db_path,
            logger=logger,
            owner_id=owner_id,
        ):
            logger.error("SQLite general memory clear failed; memory and snapshot left unchanged")
            return "⚠️ 메모리 초기화에 실패했습니다."
        if not self._reload():
            logger.error("SQLite general memory clear committed but reload failed")
            return "⚠️ 메모리 초기화 후 동기화에 실패했습니다."
        if not self._write_legacy_memory_snapshot(self.memories):
            return "⚠️ 메모리 초기화 후 동기화에 실패했습니다."
        return "🧹 메모리가 초기화되었습니다."

    @locked
    def save_daily_suggestions(self, key: str, value: Any) -> bool:
        """공용 재생성 추천 캐시를 원자적으로 저장하고 JSON 스냅샷을 맞춘다."""
        if not save_daily_suggestions_in_sqlite(
            self.db_path,
            key,
            value,
            logger=logger,
        ):
            logger.error("Daily suggestion cache save failed; memory and snapshot left unchanged")
            return False
        if not self._reload():
            logger.error("Daily suggestion cache committed but reload failed")
            return False
        if not self._write_legacy_memory_snapshot(self.memories):
            logger.error("Daily suggestion cache committed but snapshot write failed")
            return False
        return True

    def format_for_prompt(self, owner_id: Optional[str] = None) -> str:
        """요청자의 메모리만 프롬프트에 싣는다.

        소유자를 모르면 아무것도 싣지 않는다. 공용도 싣지 않는다. 거기에는
        추천 질문 캐시처럼 사용자 정보가 아닌 것과 소유자를 알 수 없는 레거시
        행이 들어 있기 때문이다.
        """
        owned = self.view(owner_id) if owner_id else None
        if not owned:
            return ""
        text = "## 사용자 정보 (Long-term Memory)\n"
        for k, v in owned.items():
            text += f"- **{k}**: {v['value']}\n"
        return text

    def to_dict(self) -> Dict[str, Any]:
        return self.memories
