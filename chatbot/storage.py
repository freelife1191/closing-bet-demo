#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
챗봇 메모리/히스토리 저장소 매니저
"""

import logging
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .storage_history_helpers import (
    atomic_write_json,
    backup_corrupt_history,
    has_meaningful_user_message,
    load_history_sessions,
    sanitize_session_messages,
    should_include_session_for_owner,
)
from .storage_sqlite_helpers import (
    apply_history_session_deltas_in_sqlite,
    load_history_sessions_from_sqlite,
    resolve_chatbot_storage_db_path,
    save_history_sessions_to_sqlite,
)
from .storage_memory_manager import MemoryManager


logger = logging.getLogger(__name__)


class HistoryManager:
    """대화 히스토리 매니저 (세션별 관리 + SQLite 영구 저장)"""

    def __init__(self, user_id: str, data_dir: Optional[Path] = None):
        self.user_id = user_id
        self.data_dir = data_dir or (Path(__file__).parent.parent / "data")
        self.file_path = self.data_dir / "chatbot_history.json"
        self.db_path = resolve_chatbot_storage_db_path(self.data_dir)
        self._legacy_snapshot_interval_seconds = self._resolve_legacy_snapshot_interval_seconds()
        self._last_legacy_snapshot_monotonic: float | None = None
        self._last_reload_signature: Any = None
        self._sanitized_messages_cache: dict[str, tuple[tuple[str, int], list[dict[str, Any]]]] = {}
        self._session_list_cache: dict[str | None, tuple[int, list[dict[str, Any]]]] = {}
        self._session_list_version = 0
        self._pending_changed_session_ids: set[str] = set()
        self._pending_deleted_session_ids: set[str] = set()
        self._pending_clear_all = False
        self._sync_snapshot_on_load = True

        # Structure: { session_id: { id, title, messages, created_at, updated_at, model } }
        self.sessions = self._load()
        self._last_reload_signature = self._get_file_signature()

    @staticmethod
    def _resolve_legacy_snapshot_interval_seconds() -> float:
        raw = os.getenv("CHATBOT_HISTORY_LEGACY_SNAPSHOT_INTERVAL_SECONDS", "15")
        try:
            value = float(raw)
            return value if value >= 0 else 0.0
        except (TypeError, ValueError):
            return 15.0

    @staticmethod
    def _get_path_signature(path: Path) -> tuple[int, int, int] | None:
        """스토리지 경로 변경 감지를 위한 시그니처(inode, mtime_ns, size)를 반환한다."""
        try:
            stat = path.stat()
            return (int(stat.st_ino), int(stat.st_mtime_ns), int(stat.st_size))
        except FileNotFoundError:
            return None
        except Exception as e:
            logger.error(f"Failed to stat storage path ({path}): {e}")
            return None

    def _get_file_signature(self) -> Any:
        signature = self._get_sqlite_storage_signature()
        if signature is not None:
            return signature
        return self._get_path_signature(self.file_path)

    def _get_sqlite_storage_signature(
        self,
    ) -> tuple[tuple[int, int, int] | None, tuple[int, int, int] | None, tuple[int, int, int] | None] | None:
        db_sig = self._get_path_signature(self.db_path)
        wal_sig = self._get_path_signature(self.db_path.with_name(f"{self.db_path.name}-wal"))
        shm_sig = self._get_path_signature(self.db_path.with_name(f"{self.db_path.name}-shm"))
        if db_sig is None and wal_sig is None and shm_sig is None:
            return None
        return (db_sig, wal_sig, shm_sig)

    def _should_sync_legacy_snapshot(self, force: bool = False) -> bool:
        if force or self._legacy_snapshot_interval_seconds <= 0:
            return True
        if self._last_legacy_snapshot_monotonic is None:
            return True
        return (time.monotonic() - self._last_legacy_snapshot_monotonic) >= self._legacy_snapshot_interval_seconds

    def _sync_legacy_snapshot(self, data: Dict[str, Any], force: bool = False) -> bool:
        if not self._should_sync_legacy_snapshot(force=force):
            return False
        self._atomic_write(data)
        self._last_legacy_snapshot_monotonic = time.monotonic()
        return True

    def _atomic_write(self, data: Dict[str, Any]) -> None:
        """히스토리 파일을 원자적으로 저장해 부분 저장/빈 파일 상태를 방지한다."""
        atomic_write_json(self.file_path, data)

    def _backup_corrupt_history(self) -> None:
        """손상된 히스토리 파일을 백업하고 원본 경로는 재초기화 가능 상태로 만든다."""
        backup_corrupt_history(self.file_path, logger)

    def _load(self) -> Dict[str, Any]:
        sqlite_sessions = load_history_sessions_from_sqlite(self.db_path, logger)
        if sqlite_sessions:
            if self._sync_snapshot_on_load:
                self._sync_legacy_snapshot(sqlite_sessions, force=True)
            return sqlite_sessions

        legacy_sessions = load_history_sessions(self.file_path, logger)
        if legacy_sessions:
            save_history_sessions_to_sqlite(self.db_path, legacy_sessions, logger)
            return legacy_sessions

        return sqlite_sessions or {}

    def _save(self) -> None:
        try:
            has_delta = (
                self._pending_clear_all
                or bool(self._pending_changed_session_ids)
                or bool(self._pending_deleted_session_ids)
            )
            if has_delta:
                sqlite_saved = apply_history_session_deltas_in_sqlite(
                    self.db_path,
                    sessions=self.sessions,
                    changed_session_ids=self._pending_changed_session_ids,
                    deleted_session_ids=self._pending_deleted_session_ids,
                    clear_all=self._pending_clear_all,
                    logger=logger,
                )
            else:
                sqlite_saved = save_history_sessions_to_sqlite(self.db_path, self.sessions, logger)

            if not sqlite_saved:
                logger.warning("SQLite incremental history save failed; full sync fallback")
                sqlite_saved = save_history_sessions_to_sqlite(self.db_path, self.sessions, logger)
                if not sqlite_saved:
                    logger.warning("SQLite history full sync failed; legacy JSON snapshot only")

            force_snapshot = (
                (not sqlite_saved)
                or self._pending_clear_all
                or bool(self._pending_deleted_session_ids)
            )
            self._sync_legacy_snapshot(self.sessions, force=force_snapshot)
            self._last_reload_signature = self._get_file_signature()
            self._pending_changed_session_ids.clear()
            self._pending_deleted_session_ids.clear()
            self._pending_clear_all = False
        except Exception as e:
            logger.error(f"Failed to save history: {e}")

    def _reload_sessions(self, force: bool = False) -> None:
        """멀티 워커 환경에서 최신 파일 상태를 다시 로드한다."""
        current_signature = self._get_file_signature()
        if not force and current_signature == self._last_reload_signature:
            return

        self._sync_snapshot_on_load = False
        try:
            self.sessions = self._load()
        finally:
            self._sync_snapshot_on_load = True
        self._last_reload_signature = self._get_file_signature()
        self._sanitized_messages_cache.clear()
        self._invalidate_session_list_cache()

    def _invalidate_message_cache(self, session_id: str | None = None) -> None:
        if session_id is None:
            self._sanitized_messages_cache.clear()
            return
        self._sanitized_messages_cache.pop(session_id, None)

    def _invalidate_session_list_cache(self) -> None:
        self._session_list_cache.clear()
        self._session_list_version += 1

    def _mark_session_changed(self, session_id: str) -> None:
        if not session_id:
            return
        self._pending_changed_session_ids.add(session_id)
        self._pending_deleted_session_ids.discard(session_id)
        self._pending_clear_all = False

    def _mark_session_deleted(self, session_id: str) -> None:
        if not session_id:
            return
        self._pending_deleted_session_ids.add(session_id)
        self._pending_changed_session_ids.discard(session_id)

    def _mark_clear_all(self) -> None:
        self._pending_clear_all = True
        self._pending_changed_session_ids.clear()
        self._pending_deleted_session_ids.clear()

    @staticmethod
    def _now_iso() -> str:
        return datetime.now().isoformat()

    @staticmethod
    def _build_session_record(
        *,
        session_id: str,
        model_name: str,
        owner_id: str | None,
        now_iso: str,
    ) -> dict[str, Any]:
        return {
            "id": session_id,
            "title": "새로운 대화",
            "messages": [],
            "created_at": now_iso,
            "updated_at": now_iso,
            "model": model_name,
            "owner_id": owner_id,
        }

    @staticmethod
    def _build_message_record(role: str, message: str, now_iso: str) -> dict[str, Any]:
        return {
            "role": role,
            "parts": [{"text": message}],
            "timestamp": now_iso,
        }

    @staticmethod
    def _derive_auto_title(message: str) -> str:
        clean_msg = message.strip().replace("\n", " ")
        return clean_msg[:30] + "..." if len(clean_msg) > 30 else clean_msg

    def _maybe_set_auto_title(self, session: dict[str, Any], role: str, message: str) -> None:
        if role != "user":
            return
        message_count = len(session.get("messages", []))
        if message_count in (1, 2):
            session["title"] = self._derive_auto_title(message)

    @staticmethod
    def _clone_sanitized_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
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

    def create_session(
        self,
        model_name: str = "gemini-2.0-flash-lite",
        save_immediate: bool = True,
        owner_id: str = None,
        session_id: str = None,
    ) -> str:
        self._reload_sessions()  # [Fix] Multi-worker Sync
        session_id = session_id or str(uuid.uuid4())
        now_iso = self._now_iso()
        self.sessions[session_id] = self._build_session_record(
            session_id=session_id,
            model_name=model_name,
            owner_id=owner_id,
            now_iso=now_iso,
        )
        self._mark_session_changed(session_id)
        self._invalidate_message_cache(session_id)
        self._invalidate_session_list_cache()
        if save_immediate:
            self._save()
        return session_id

    def delete_session(self, session_id: str) -> bool:
        self._reload_sessions()  # [Fix] Multi-worker Sync
        if session_id in self.sessions:
            del self.sessions[session_id]
            self._mark_session_deleted(session_id)
            self._invalidate_message_cache(session_id)
            self._invalidate_session_list_cache()
            self._save()
            return True
        return False

    def delete_message(self, session_id: str, msg_index: int) -> bool:
        self._reload_sessions()  # [Fix] Multi-worker Sync
        if session_id in self.sessions:
            session = self.sessions[session_id]
            if 0 <= msg_index < len(session["messages"]):
                del session["messages"][msg_index]
                session["updated_at"] = datetime.now().isoformat()
                self._mark_session_changed(session_id)
                self._invalidate_message_cache(session_id)
                self._invalidate_session_list_cache()
                self._save()
                return True
        return False

    def clear_all(self) -> None:
        self.sessions = {}
        self._mark_clear_all()
        self._invalidate_message_cache()
        self._invalidate_session_list_cache()
        self._save()

    def clear(self) -> None:
        """하위호환용 별칭."""
        self.clear_all()

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        self._reload_sessions()  # [Fix] Multi-worker Sync
        return self.sessions.get(session_id)

    def get_all_sessions(self, owner_id: str = None) -> list:
        self._reload_sessions()  # [Fix] Multi-worker Sync
        cached = self._session_list_cache.get(owner_id)
        if cached and cached[0] == self._session_list_version:
            return list(cached[1])

        # Filter out empty or ephemeral-only sessions AND filter by owner
        valid_sessions = []
        for session in self.sessions.values():
            if not should_include_session_for_owner(session, owner_id):
                continue

            msgs = session.get("messages", [])
            if not msgs:
                continue

            if has_meaningful_user_message(msgs):
                valid_sessions.append(session)

        # Sort by updated_at desc
        sorted_sessions = sorted(
            valid_sessions,
            key=lambda x: x.get("updated_at", ""),
            reverse=True,
        )
        self._session_list_cache[owner_id] = (self._session_list_version, sorted_sessions)
        return list(sorted_sessions)

    def add_message(self, session_id: str, role: str, message: str, save: bool = True) -> None:
        # Always reload latest snapshot before mutating.
        # Without this, stale in-memory state from another worker can resurrect deleted sessions.
        self._reload_sessions()
        if session_id not in self.sessions:
            # Fallback (Ephemeral check handled in chat, but here strictly requires existence or auto-create)
            # add_message 호출 내에서는 즉시 저장을 생략해 중복 write를 방지한다.
            now_iso = self._now_iso()
            self.sessions[session_id] = self._build_session_record(
                session_id=session_id,
                model_name="gemini-2.0-flash-lite",
                owner_id=None,
                now_iso=now_iso,
            )
            self._mark_session_changed(session_id)
            self._invalidate_message_cache(session_id)
            self._invalidate_session_list_cache()

        session = self.sessions[session_id]
        now_iso = self._now_iso()

        # FIX: Store parts as objects for Gemini SDK compatibility
        # parts=[{"text": "message"}] instead of parts=["message"]
        # Add timestamp
        session["messages"].append(self._build_message_record(role, message, now_iso))
        session["updated_at"] = now_iso

        # Auto-title (first user message)
        self._maybe_set_auto_title(session, role, message)

        # Limit per session (optional, kept 50 for now)
        if len(session["messages"]) > 50:
            session["messages"] = session["messages"][-50:]

        self._mark_session_changed(session_id)
        self._invalidate_message_cache(session_id)
        self._invalidate_session_list_cache()
        if save:
            self._save()

    def get_messages(self, session_id: str) -> list:
        # Sync from disk for multi-worker consistency.
        self._reload_sessions()
        session = self.sessions.get(session_id)
        if session:
            fingerprint = (
                str(session.get("updated_at", "")),
                len(session.get("messages", [])),
            )
            cached = self._sanitized_messages_cache.get(session_id)
            if cached and cached[0] == fingerprint:
                return self._clone_sanitized_messages(cached[1])

            sanitized = sanitize_session_messages(session)
            self._sanitized_messages_cache[session_id] = (fingerprint, sanitized)
            return self._clone_sanitized_messages(sanitized)
        return []

    def to_dict(self) -> Dict[str, Any]:
        """전체 세션 딕셔너리를 반환한다."""
        self._reload_sessions()
        return self.sessions
