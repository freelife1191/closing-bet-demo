#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
챗봇 메모리/히스토리 저장소 매니저
"""

import logging
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .storage_history_helpers import (
    has_meaningful_user_message,
    is_session_accessible_by_owner,
    load_history_sessions,
    locked,
    sanitize_session_messages,
    should_include_session_for_owner,
)
from .storage_history_parts import (
    HistoryReadCache,
    LegacySnapshot,
    SessionDeltaLedger,
    storage_signature,
)
from .storage_sqlite_helpers import (
    apply_history_session_deltas_in_sqlite,
    load_history_sessions_from_sqlite,
    resolve_chatbot_storage_db_path,
    restore_lost_history_messages_in_sqlite,
    save_history_sessions_to_sqlite,
)
from .storage_memory_manager import MemoryManager


logger = logging.getLogger(__name__)
_SANITIZED_MESSAGES_CACHE_MAX_ENTRIES = 2_048
_SESSION_LIST_CACHE_MAX_ENTRIES = 256


class HistoryManager:
    """대화 히스토리 매니저 (세션별 관리 + SQLite 영구 저장)"""

    def __init__(self, user_id: str, data_dir: Optional[Path] = None):
        self.user_id = user_id
        self.data_dir = data_dir or (Path(__file__).parent.parent / "data")
        self.file_path = self.data_dir / "chatbot_history.json"
        self.db_path = resolve_chatbot_storage_db_path(self.data_dir)
        self._snapshot = LegacySnapshot.from_env(self.file_path)
        self._cache = HistoryReadCache(
            messages_max_entries=_SANITIZED_MESSAGES_CACHE_MAX_ENTRIES,
            session_list_max_entries=_SESSION_LIST_CACHE_MAX_ENTRIES,
        )
        self._delta = SessionDeltaLedger()
        self._last_reload_signature: Any = None
        self._sync_snapshot_on_load = True
        # ponytail: 잠금을 쥔 채 SQLite busy 대기와 재적재를 하므로, 다른 워커가 쓰기 잠금을 오래 쥐면
        # 이 워커의 읽기 요청도 함께 기다린다. 지연이 보이면 읽기 경로를 잠금 밖 사본 읽기로 나눈다.
        self._lock = threading.RLock()

        # Structure: { session_id: { id, title, messages, created_at, updated_at, model } }
        loaded = self._load()
        # 기동 시점의 읽기 실패도 재적재 실패와 같이 다룬다. 빈 사본으로 두고 쓰기를 막은 채 다음 접근에서 다시 읽는다.
        self._reload_failed = loaded is None
        self.sessions = loaded or {}
        self._last_reload_signature = None if loaded is None else storage_signature(self.db_path, self.file_path)

    def _load(self) -> Optional[Dict[str, Any]]:
        sqlite_sessions = load_history_sessions_from_sqlite(self.db_path, logger)
        if sqlite_sessions is None and self.db_path.exists():
            # 읽기 실패다. 최대 15초 늦은 JSON 스냅샷을 쓰면 그 위의 쓰기가 DB 를 덮어쓰므로,
            # None 을 돌려 호출자가 쓰기를 막고 다음 접근에서 다시 읽게 한다.
            return None
        if sqlite_sessions:
            sqlite_sessions = self._restore_lost_messages_from_snapshot(sqlite_sessions)
            if sqlite_sessions is None:
                # 되살린 메시지를 DB 에 남기지 못했다. 빈 사본을 쓰면 스냅샷이 덮이므로 읽기 실패로 다룬다.
                return None
            if self._sync_snapshot_on_load:
                self._snapshot.sync(sqlite_sessions, force=True)
            return sqlite_sessions

        legacy_sessions = load_history_sessions(self.file_path, logger)
        if legacy_sessions:
            # 여기까지 오면 DB 가 없거나 표가 비어 있다. 이관 함수의 삭제 절이 지울 행이 없다([CHAT-033]).
            save_history_sessions_to_sqlite(self.db_path, legacy_sessions, logger)
            return legacy_sessions

        return sqlite_sessions or {}

    def _restore_lost_messages_from_snapshot(self, sqlite_sessions: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """메시지 테이블이 통째로 사라졌다가 빈 채로 복구됐으면 JSON 스냅샷의 메시지로 되살린다([CHAT-039]).

        되살리지 않으면 다음 스냅샷 쓰기가 빈 메시지로 마지막 사본을 덮는다. 되살린 뒤에는 DB 를
        다시 읽은 결과를, 되살릴 것이 없으면 받은 사본을, DB 에 쓰지 못했으면 None 을 돌려준다.
        """
        # ponytail: 모든 세션이 비었을 때만 본다(일부 행 손실은 대상 밖). 스냅샷은 최대 15초 늦으므로
        # 그 사이 갱신된 세션은 updated_at 이 달라 되살리지 못한다. 메시지 없는 세션만 있는 정상
        # 상태에서도 서명이 바뀔 때마다 JSON 을 읽으며, 그때 load_history_sessions 가 빈·손상 파일을 다시 쓸 수 있다.
        if any(session.get("messages") for session in sqlite_sessions.values()):
            return sqlite_sessions
        snapshot = load_history_sessions(self.file_path, logger)
        restorable: Dict[str, Any] = {}
        for session_id, session in sqlite_sessions.items():
            saved = snapshot.get(session_id)
            # updated_at 이 같아야 같은 판이다. 메시지를 지우면 updated_at 이 바뀌므로 지운 메시지는 살아나지 않는다.
            if (
                isinstance(saved, dict)
                and isinstance(saved.get("messages"), list)
                and saved["messages"]
                and saved.get("updated_at") == session.get("updated_at")
            ):
                restorable[session_id] = {**session, "messages": saved["messages"]}
        if not restorable:
            return sqlite_sessions
        # 조건부로 쓰므로 다른 워커가 먼저 되살렸거나 갱신한 세션은 덮지 않는다([CHAT-033]).
        if not restore_lost_history_messages_in_sqlite(self.db_path, restorable, logger):
            logger.error("Failed to restore lost chat messages from the legacy snapshot")
            return None
        logger.warning(f"Restored messages of {len(restorable)} chat sessions from the legacy snapshot")
        return load_history_sessions_from_sqlite(self.db_path, logger)

    @locked
    def _save(self) -> bool:
        """SQLite 저장의 성패를 돌려준다. 실패해도 예외를 올리지 않고 스냅샷만 남긴다."""
        try:
            has_delta = self._delta.has_delta
            # 전체 동기화 폴백은 두지 않는다. 낡은 사본을 통째로 쓰면 다른 워커가 만든 세션을 지우거나
            # 지운 세션을 되살린다([CHAT-033]). 같은 이유로 재적재에 실패한 사본도 쓰지 않는다.
            # 실패한 변경은 다음 재적재가 되돌린다.
            if self._reload_failed:
                logger.warning("History reload failed; refusing to write a stale copy")
                sqlite_saved = False
            else:
                sqlite_saved = (not has_delta) or apply_history_session_deltas_in_sqlite(
                    self.db_path,
                    sessions=self.sessions,
                    changed_session_ids=self._delta.changed,
                    deleted_session_ids=self._delta.deleted,
                    clear_all=self._delta.clear_all,
                    logger=logger,
                )
                if not sqlite_saved:
                    logger.warning("SQLite history delta save failed; legacy JSON snapshot only")

                has_deletion = self._delta.clear_all or bool(self._delta.deleted)
                try:
                    self._snapshot.sync(self.sessions, force=(not sqlite_saved) or has_deletion)
                except OSError as e:
                    # 스냅샷은 복구용 사본이라 SQLite 저장의 성패를 바꾸지 않는다([CHAT-040]).
                    # 다음 저장이 간격을 기다리지 않고 다시 쓴다.
                    logger.error(f"Legacy history snapshot write failed: {e}")
                    self._snapshot.last_monotonic = None
                    if sqlite_saved and has_deletion:
                        # 낡은 사본이 남으면 SQLite 가 빈 다음 로드가 그것을 다시 이관해
                        # 지운 대화가 살아난다. 지우지 못하면 삭제를 실패로 돌려주되, 장부는 비우고
                        # 서명을 비워 다음 접근이 SQLite 를 다시 읽게 한다(재시도가 되살아난 세션도 찾는다).
                        try:
                            self._snapshot.file_path.unlink(missing_ok=True)
                        except OSError as unlink_error:
                            logger.error(f"Failed to remove stale history snapshot: {unlink_error}")
                            sqlite_saved = False
            # 실패했으면 서명을 비워 다음 접근이 DB 를 다시 읽게 한다. 그래야 저장되지 않은 변경이
            # 이 워커의 응답에 남지 않는다.
            self._last_reload_signature = (
                storage_signature(self.db_path, self.file_path) if sqlite_saved else None
            )
            self._delta.reset()
            return bool(sqlite_saved)
        except Exception as e:
            logger.error(f"Failed to save history: {e}")
            return False

    @locked
    def _reload_sessions(self, force: bool = False) -> None:
        """멀티 워커 환경에서 최신 파일 상태를 다시 로드한다."""
        current_signature = storage_signature(self.db_path, self.file_path)
        if not force and current_signature == self._last_reload_signature:
            return

        self._sync_snapshot_on_load = False
        try:
            loaded = self._load()
        finally:
            self._sync_snapshot_on_load = True
        self._reload_failed = loaded is None
        if loaded is None:
            self._last_reload_signature = None
            return
        self.sessions = loaded
        self._last_reload_signature = storage_signature(self.db_path, self.file_path)
        self._cache.invalidate_messages()
        self._cache.invalidate_session_list()

    @locked
    def _invalidate_message_cache(self, session_id: str | None = None) -> None:
        self._cache.invalidate_messages(session_id)

    @locked
    def _invalidate_session_list_cache(self) -> None:
        self._cache.invalidate_session_list()

    @locked
    def _mark_session_changed(self, session_id: str) -> None:
        self._delta.mark_changed(session_id)

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
            "title": "",  # 빈 값은 아직 첫 일반 질문이 없는 세션이다.
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
        # 표시 문구를 sentinel로 쓰면 같은 질문으로 만든 제목이 다시 덮어써진다.
        if session.get("title") or role != "user":
            return
        if not message.strip() or message.strip().startswith("/"):
            return
        session["title"] = self._derive_auto_title(message)

    @locked
    def create_session(
        self,
        model_name: str = "gemini-3.7-flash",
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

    @locked
    def delete_session(self, session_id: str) -> bool:
        self._reload_sessions()  # [Fix] Multi-worker Sync
        if session_id in self.sessions:
            del self.sessions[session_id]
            self._delta.mark_deleted(session_id)
            self._invalidate_message_cache(session_id)
            self._invalidate_session_list_cache()
            self._save()
            return True
        return False

    @locked
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

    @locked
    def clear_all(self) -> None:
        """모든 사용자의 세션을 지운다. HTTP 로 도달하는 경로는 없다.

        요청 하나가 전체 사용자의 대화를 날릴 수 있으므로, 사용자가 부르는
        「내 대화 전부 지우기」는 clear_for_owner 를 쓴다.
        """
        self.sessions = {}
        self._delta.mark_clear_all()
        self._invalidate_message_cache()
        self._invalidate_session_list_cache()
        self._save()

    @locked
    def clear_for_owner(self, owner_id: str) -> int:
        """해당 소유자의 세션만 지우고 지운 건수를 돌려준다.

        owner_id 가 비어 있으면 아무것도 지우지 않는다. 소유자가 기록되지 않은
        레거시 세션이 통째로 지워지는 것을 막기 위해서다.
        """
        if not owner_id:
            return 0

        # 파일 서명이 같아도 다시 읽는다. 직전 저장이 실패해 메모리에서만 사라진 세션을
        # 이번 호출이 다시 찾아 지우게 하기 위해서다([FE-045]).
        self._reload_sessions(force=True)
        targets = [
            session_id
            for session_id, session in self.sessions.items()
            if session.get("owner_id") == owner_id
        ]
        for session_id in targets:
            del self.sessions[session_id]
            self._delta.mark_deleted(session_id)
            self._invalidate_message_cache(session_id)

        if targets:
            self._invalidate_session_list_cache()
            if not self._save():
                # 삭제가 SQLite 에 남지 않았다. 지웠다고 돌려주면 계정 삭제가 성공으로 보인다.
                raise RuntimeError("chat history delete was not persisted")
        return len(targets)

    def clear(self) -> None:
        """하위호환용 별칭."""
        self.clear_all()

    @locked
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        # ponytail: 돌려준 사전을 잠금 밖에서 고친 뒤 _save() 를 부르는 호출자(command_service,
        # session_access)는 그 사이 다른 스레드의 재적재가 끼면 변경을 잃는다. 다중 워커와 같은
        # 의미라 두며, 유실이 보이면 수정·저장을 한 번에 하는 메서드를 이 클래스에 둔다.
        self._reload_sessions()  # [Fix] Multi-worker Sync
        return self.sessions.get(session_id)

    def is_session_accessible(self, session_id: str, owner_id: Optional[str]) -> bool:
        """요청자가 이 세션을 조회하거나 삭제할 수 있는지 판정한다.

        없는 세션도 False 를 돌려준다. 호출자가 「없음」과 「남의 것」을 같은
        404 로 응답해야 세션 ID 의 존재 여부가 새어 나가지 않는다.
        """
        session = self.get_session(session_id)
        if session is None:
            return False
        return is_session_accessible_by_owner(session, owner_id)

    @locked
    def get_all_sessions(self, owner_id: str = None) -> list:
        self._reload_sessions()  # [Fix] Multi-worker Sync
        cached = self._cache.get_session_list(owner_id)
        if cached is not None:
            return cached

        # Filter out empty or ephemeral-only sessions AND filter by owner
        valid_sessions = []
        for session in self.sessions.values():
            if not should_include_session_for_owner(session, owner_id):
                continue

            msgs = session.get("messages", [])
            if not msgs:
                continue

            if has_meaningful_user_message(msgs):
                valid_sessions.append({**session, "title": session.get("title") or "새로운 대화"})

        # Sort by updated_at desc
        sorted_sessions = sorted(
            valid_sessions,
            key=lambda x: x.get("updated_at", ""),
            reverse=True,
        )
        return self._cache.put_session_list(owner_id, sorted_sessions)

    @locked
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
                model_name="gemini-3.7-flash",
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

    @locked
    def get_messages(self, session_id: str) -> list:
        # Sync from disk for multi-worker consistency.
        self._reload_sessions()
        session = self.sessions.get(session_id)
        if session:
            fingerprint = (
                str(session.get("updated_at", "")),
                len(session.get("messages", [])),
            )
            cached = self._cache.get_messages(session_id, fingerprint)
            if cached is not None:
                return cached
            return self._cache.put_messages(session_id, fingerprint, sanitize_session_messages(session))
        return []

    @locked
    def to_dict(self) -> Dict[str, Any]:
        """전체 세션 딕셔너리를 반환한다."""
        self._reload_sessions()
        return self.sessions
