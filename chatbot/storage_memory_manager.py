#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
챗봇 메모리 저장 매니저
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .storage_history_helpers import atomic_write_json
from .storage_sqlite_helpers import (
    clear_memories_in_sqlite,
    delete_memory_entry_in_sqlite,
    load_memories_from_sqlite,
    resolve_chatbot_storage_db_path,
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
            return _promote_legacy_flat_memories(loaded)
        logger.warning(f"Unexpected memory format type: {type(loaded).__name__}")
        return {}

    def _save_legacy_memory_snapshot(self, memories: Dict[str, Any]) -> None:
        if not self._should_sync_legacy_snapshot():
            return
        self._write_legacy_memory_snapshot(memories)

    def _write_legacy_memory_snapshot(self, memories: Dict[str, Any]) -> None:
        try:
            if not self.data_dir.exists():
                self.data_dir.mkdir(parents=True, exist_ok=True)
            atomic_write_json(self.file_path, memories)
            self._last_legacy_snapshot_monotonic = time.monotonic()
        except Exception as error:
            logger.error(f"Failed to save legacy memory JSON snapshot: {error}")

    def _load(self) -> Dict[str, Any]:
        sqlite_memories = load_memories_from_sqlite(self.db_path, logger)
        if sqlite_memories:
            self._write_legacy_memory_snapshot(sqlite_memories)
            return sqlite_memories

        legacy_memories = self._load_legacy_memory()
        if legacy_memories:
            save_memories_to_sqlite(self.db_path, legacy_memories, logger)
            return legacy_memories

        return sqlite_memories or {}

    def _save(self) -> None:
        sqlite_saved = save_memories_to_sqlite(self.db_path, self.memories, logger)
        if not sqlite_saved:
            logger.warning("SQLite memory save failed; legacy JSON snapshot only")
            self._write_legacy_memory_snapshot(self.memories)
            return
        self._save_legacy_memory_snapshot(self.memories)

    def _save_single_entry(self, owner_id: str, key: str) -> None:
        record = self.memories.get(owner_id, {}).get(key)
        if not isinstance(record, dict):
            self._save()
            return

        sqlite_saved = upsert_memory_entry_in_sqlite(
            self.db_path,
            owner_id=owner_id,
            key=key,
            record=record,
            logger=logger,
        )
        if not sqlite_saved:
            logger.warning("SQLite single memory upsert failed; full sync fallback")
            self._save()
            return
        self._save_legacy_memory_snapshot(self.memories)

    def _delete_single_entry(self, owner_id: str, key: str) -> None:
        sqlite_saved = delete_memory_entry_in_sqlite(
            self.db_path,
            owner_id=owner_id,
            key=key,
            logger=logger,
        )
        if not sqlite_saved:
            logger.warning("SQLite memory delete failed; full sync fallback")
            self._save()
            return
        self._write_legacy_memory_snapshot(self.memories)

    def _clear_storage(self, owner_id: str) -> None:
        sqlite_saved = clear_memories_in_sqlite(
            self.db_path,
            logger=logger,
            owner_id=owner_id,
        )
        if not sqlite_saved:
            logger.warning("SQLite memory clear failed; full sync fallback")
            self._save()
            return
        self._write_legacy_memory_snapshot(self.memories)

    def view(self, owner_id: Optional[str] = None) -> Dict[str, Any]:
        return self.memories.get(_normalize_memory_owner_id(owner_id), {})

    def get(self, key: str, owner_id: Optional[str] = None) -> Any:
        return self.view(owner_id).get(key)

    def add(self, key: str, value: Any, owner_id: Optional[str] = None) -> str:
        owner = _normalize_memory_owner_id(owner_id)
        self.memories.setdefault(owner, {})[key] = {
            "value": value,
            "updated_at": datetime.now().isoformat(),
        }
        self._save_single_entry(owner, key)
        return f"✅ 메모리 저장: {key} = {value}"

    def remove(self, key: str, owner_id: Optional[str] = None) -> str:
        owner = _normalize_memory_owner_id(owner_id)
        owned = self.memories.get(owner, {})
        if key in owned:
            del owned[key]
            self._delete_single_entry(owner, key)
            return f"🗑️ 메모리 삭제: {key}"
        return "⚠️ 해당 키를 찾을 수 없습니다."

    def update(self, key: str, value: Any, owner_id: Optional[str] = None) -> str:
        owner = _normalize_memory_owner_id(owner_id)
        owned = self.memories.get(owner, {})
        if key in owned:
            owned[key]["value"] = value
            owned[key]["updated_at"] = datetime.now().isoformat()
            self._save_single_entry(owner, key)
            return f"✅ 메모리 수정: {key} = {value}"
        return self.add(key, value, owner_id=owner_id)

    def clear(self, owner_id: Optional[str] = None) -> str:
        owner = _normalize_memory_owner_id(owner_id)
        self.memories.pop(owner, None)
        self._clear_storage(owner)
        return "🧹 메모리가 초기화되었습니다."

    def format_for_prompt(self, owner_id: Optional[str] = None) -> str:
        """요청자의 메모리만 프롬프트에 싣는다.

        소유자를 모르면 아무것도 싣지 않는다. 공용도 싣지 않는다. 거기에는
        추천 질문 캐시처럼 사용자 정보가 아닌 것과 소유자를 알 수 없는 레거시
        행이 들어 있기 때문이다.
        """
        owned = self.memories.get(owner_id) if owner_id else None
        if not owned:
            return ""
        text = "## 사용자 정보 (Long-term Memory)\n"
        for k, v in owned.items():
            text += f"- **{k}**: {v['value']}\n"
        return text

    def to_dict(self) -> Dict[str, Any]:
        return self.memories
