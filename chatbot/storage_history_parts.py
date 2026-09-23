#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HistoryManager 가 조립하는 부품([CHAT-035])

세 클래스 모두 잠금이 없다. HistoryManager 의 RLock 을 쥔 채로만 부른다. 잠금을 부품마다
두면 부품 사이의 상태가 서로 다른 시점을 보게 되어 [CHAT-033] 같은 경합이 다시 생긴다.
"""

import logging
import os
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, Optional

from .storage_history_helpers import atomic_write_json


logger = logging.getLogger(__name__)


def _path_signature(path: Path) -> tuple[int, int, int] | None:
    """스토리지 경로 변경 감지를 위한 시그니처(inode, mtime_ns, size)를 반환한다."""
    try:
        stat = path.stat()
        return (int(stat.st_ino), int(stat.st_mtime_ns), int(stat.st_size))
    except FileNotFoundError:
        return None
    except Exception as e:
        logger.error(f"Failed to stat storage path ({path}): {e}")
        return None


def storage_signature(db_path: Path, file_path: Path) -> Any:
    """SQLite(db·wal·shm) 서명을, 셋 다 없으면 JSON 파일 서명을 돌려준다. 재적재 판정에 쓴다."""
    sqlite_signature = tuple(
        _path_signature(path)
        for path in (
            db_path,
            db_path.with_name(f"{db_path.name}-wal"),
            db_path.with_name(f"{db_path.name}-shm"),
        )
    )
    if any(signature is not None for signature in sqlite_signature):
        return sqlite_signature
    return _path_signature(file_path)


class LegacySnapshot:
    """레거시 JSON 스냅샷을 간격을 두고 쓴다. SQLite 가 정본이고 이 파일은 복구용 사본이다."""

    def __init__(self, file_path: Path, interval_seconds: float):
        self.file_path = file_path
        self.interval_seconds = interval_seconds
        self.last_monotonic: Optional[float] = None

    @classmethod
    def from_env(cls, file_path: Path) -> "LegacySnapshot":
        raw = os.getenv("CHATBOT_HISTORY_LEGACY_SNAPSHOT_INTERVAL_SECONDS", "15")
        try:
            value = float(raw)
            interval = value if value >= 0 else 0.0
        except (TypeError, ValueError):
            interval = 15.0
        return cls(file_path, interval)

    def write(self, data: Dict[str, Any]) -> None:
        """히스토리 파일을 원자적으로 저장해 부분 저장/빈 파일 상태를 방지한다."""
        atomic_write_json(self.file_path, data)

    def sync(self, data: Dict[str, Any], force: bool = False) -> bool:
        due = (
            force
            or self.interval_seconds <= 0
            or self.last_monotonic is None
            or (time.monotonic() - self.last_monotonic) >= self.interval_seconds
        )
        if not due:
            return False
        self.write(data)
        self.last_monotonic = time.monotonic()
        return True


def _clone_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """캐시 오염 방지를 위해 메시지 목록을 복제해 반환한다."""
    cloned: list[dict[str, Any]] = []
    for msg in messages:
        cloned_parts = [
            dict(part) if isinstance(part, dict) else part
            for part in msg.get("parts", [])
        ]
        cloned_msg = {"role": msg.get("role", "user"), "parts": cloned_parts}
        if "timestamp" in msg:
            cloned_msg["timestamp"] = msg["timestamp"]
        cloned.append(cloned_msg)
    return cloned


def _prune(cache: OrderedDict[Any, Any], max_entries: int) -> None:
    normalized_max_entries = max(1, int(max_entries))
    while len(cache) > normalized_max_entries:
        cache.popitem(last=False)


class HistoryReadCache:
    """정제한 메시지와 세션 목록을 LRU 로 담는다.

    메시지는 복제본을 돌려준다. 세션 목록은 얕은 사본이라 원소 dict 는 캐시와 공유된다(종전과 같다).
    """

    def __init__(self, messages_max_entries: int, session_list_max_entries: int):
        self.messages: OrderedDict[str, tuple[tuple[str, int], list[dict[str, Any]]]] = OrderedDict()
        self.session_list: OrderedDict[str | None, list[dict[str, Any]]] = OrderedDict()
        self._messages_max_entries = messages_max_entries
        self._session_list_max_entries = session_list_max_entries

    def get_messages(self, session_id: str, fingerprint: tuple[str, int]) -> Optional[list[dict[str, Any]]]:
        cached = self.messages.get(session_id)
        if not cached or cached[0] != fingerprint:
            return None
        self.messages.move_to_end(session_id)
        return _clone_messages(cached[1])

    def put_messages(
        self, session_id: str, fingerprint: tuple[str, int], sanitized: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        self.messages[session_id] = (fingerprint, sanitized)
        self.messages.move_to_end(session_id)
        _prune(self.messages, self._messages_max_entries)
        return _clone_messages(sanitized)

    def get_session_list(self, owner_id: str | None) -> Optional[list[dict[str, Any]]]:
        if owner_id not in self.session_list:
            return None
        self.session_list.move_to_end(owner_id)
        return list(self.session_list[owner_id])

    def put_session_list(self, owner_id: str | None, sessions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self.session_list[owner_id] = sessions
        self.session_list.move_to_end(owner_id)
        _prune(self.session_list, self._session_list_max_entries)
        return list(sessions)

    def invalidate_messages(self, session_id: str | None = None) -> None:
        if session_id is None:
            self.messages.clear()
            return
        self.messages.pop(session_id, None)

    def invalidate_session_list(self) -> None:
        self.session_list.clear()


class SessionDeltaLedger:
    """다음 저장에서 SQLite 에 반영할 세션 변경·삭제·전체 삭제 표시를 모은다."""

    def __init__(self):
        self.changed: set[str] = set()
        self.deleted: set[str] = set()
        self.clear_all = False

    def mark_changed(self, session_id: str) -> None:
        if not session_id:
            return
        self.changed.add(session_id)
        self.deleted.discard(session_id)
        self.clear_all = False

    def mark_deleted(self, session_id: str) -> None:
        if not session_id:
            return
        self.deleted.add(session_id)
        self.changed.discard(session_id)

    def mark_clear_all(self) -> None:
        self.clear_all = True
        self.changed.clear()
        self.deleted.clear()

    @property
    def has_delta(self) -> bool:
        return self.clear_all or bool(self.changed) or bool(self.deleted)

    def reset(self) -> None:
        self.changed.clear()
        self.deleted.clear()
        self.clear_all = False
