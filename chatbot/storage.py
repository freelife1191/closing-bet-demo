#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
챗봇 메모리/히스토리 저장소 매니저
"""

import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .markdown_utils import _normalize_markdown_text


logger = logging.getLogger(__name__)


class MemoryManager:
    """간단한 인메모리 메모리 매니저 (JSON 파일 영구 저장)"""

    def __init__(self, user_id: str, data_dir: Optional[Path] = None):
        self.user_id = user_id
        self.data_dir = data_dir or (Path(__file__).parent.parent / "data")
        self.file_path = self.data_dir / "chatbot_memory.json"
        self.memories = self._load()

    def _load(self) -> Dict[str, Any]:
        if self.file_path.exists():
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load memory: {e}")
        return {}

    def _save(self) -> None:
        try:
            if not self.data_dir.exists():
                self.data_dir.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self.memories, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save memory: {e}")

    def view(self) -> Dict[str, Any]:
        return self.memories

    def get(self, key: str) -> Any:
        return self.memories.get(key)

    def add(self, key: str, value: Any) -> str:
        self.memories[key] = {"value": value, "updated_at": datetime.now().isoformat()}
        self._save()
        return f"✅ 메모리 저장: {key} = {value}"

    def remove(self, key: str) -> str:
        if key in self.memories:
            del self.memories[key]
            self._save()
            return f"🗑️ 메모리 삭제: {key}"
        return "⚠️ 해당 키를 찾을 수 없습니다."

    def update(self, key: str, value: Any) -> str:
        if key in self.memories:
            self.memories[key]["value"] = value
            self.memories[key]["updated_at"] = datetime.now().isoformat()
            self._save()
            return f"✅ 메모리 수정: {key} = {value}"
        return self.add(key, value)

    def clear(self) -> str:
        self.memories = {}
        self._save()
        return "🧹 메모리가 초기화되었습니다."

    def format_for_prompt(self) -> str:
        if not self.memories:
            return ""
        text = "## 사용자 정보 (Long-term Memory)\n"
        for k, v in self.memories.items():
            text += f"- **{k}**: {v['value']}\n"
        return text

    def to_dict(self) -> Dict[str, Any]:
        return self.memories


class HistoryManager:
    """대화 히스토리 매니저 (세션별 관리 + JSON 영구 저장)"""

    def __init__(self, user_id: str, data_dir: Optional[Path] = None):
        self.user_id = user_id
        self.data_dir = data_dir or (Path(__file__).parent.parent / "data")
        self.file_path = self.data_dir / "chatbot_history.json"

        # Structure: { session_id: { id, title, messages, created_at, updated_at, model } }
        self.sessions = self._load()

    def _atomic_write(self, data: Dict[str, Any]) -> None:
        """히스토리 파일을 원자적으로 저장해 부분 저장/빈 파일 상태를 방지한다."""
        data_dir = self.file_path.parent
        if not data_dir.exists():
            data_dir.mkdir(parents=True, exist_ok=True)

        tmp_path = self.file_path.with_name(
            f"{self.file_path.name}.tmp-{uuid.uuid4().hex}"
        )
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self.file_path)
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass

    def _backup_corrupt_history(self) -> None:
        """손상된 히스토리 파일을 백업하고 원본 경로는 재초기화 가능 상태로 만든다."""
        if not self.file_path.exists():
            return

        backup_path = self.file_path.with_name(
            f"{self.file_path.stem}.corrupt-"
            f"{datetime.now().strftime('%Y%m%d%H%M%S')}-"
            f"{uuid.uuid4().hex[:8]}{self.file_path.suffix}"
        )
        try:
            os.replace(self.file_path, backup_path)
            logger.warning(f"Corrupt history backed up to: {backup_path}")
        except Exception as backup_error:
            logger.error(f"Failed to backup corrupt history: {backup_error}")

    def _load(self) -> Dict[str, Any]:
        if self.file_path.exists():
            try:
                raw = self.file_path.read_text(encoding="utf-8")
                if not raw.strip():
                    logger.warning("History file is empty. Reinitializing with empty JSON.")
                    self._atomic_write({})
                    return {}

                data = json.loads(raw)
                # Migration: if list (old format), convert to default session
                if isinstance(data, list):
                    default_id = str(uuid.uuid4())
                    migrated = {
                        default_id: {
                            "id": default_id,
                            "title": "이전 대화",
                            "messages": data,
                            "created_at": datetime.now().isoformat(),
                            "updated_at": datetime.now().isoformat(),
                            "model": "gemini-2.0-flash-lite",
                        }
                    }
                    self._atomic_write(migrated)
                    return migrated
                if isinstance(data, dict):
                    return data

                logger.error(f"Unexpected history format type: {type(data).__name__}")
                self._backup_corrupt_history()
                self._atomic_write({})
            except json.JSONDecodeError as e:
                logger.error(f"Failed to load history (invalid JSON): {e}")
                try:
                    self._backup_corrupt_history()
                    self._atomic_write({})
                except Exception as recover_error:
                    logger.error(f"Failed to recover corrupt history file: {recover_error}")
            except Exception as e:
                logger.error(f"Failed to load history: {e}")
        return {}

    def _save(self) -> None:
        try:
            self._atomic_write(self.sessions)
        except Exception as e:
            logger.error(f"Failed to save history: {e}")

    def create_session(
        self,
        model_name: str = "gemini-2.0-flash-lite",
        save_immediate: bool = True,
        owner_id: str = None,
        session_id: str = None,
    ) -> str:
        self.sessions = self._load()  # [Fix] Multi-worker Sync
        session_id = session_id or str(uuid.uuid4())
        self.sessions[session_id] = {
            "id": session_id,
            "title": "새로운 대화",
            "messages": [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "model": model_name,
            "owner_id": owner_id,  # [Fix] Session Ownership
        }
        if save_immediate:
            self._save()
        return session_id

    def delete_session(self, session_id: str) -> bool:
        self.sessions = self._load()  # [Fix] Multi-worker Sync
        if session_id in self.sessions:
            del self.sessions[session_id]
            self._save()
            return True
        return False

    def delete_message(self, session_id: str, msg_index: int) -> bool:
        self.sessions = self._load()  # [Fix] Multi-worker Sync
        if session_id in self.sessions:
            session = self.sessions[session_id]
            if 0 <= msg_index < len(session["messages"]):
                del session["messages"][msg_index]
                session["updated_at"] = datetime.now().isoformat()
                self._save()
                return True
        return False

    def clear_all(self) -> None:
        self.sessions = {}
        self._save()

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        self.sessions = self._load()  # [Fix] Multi-worker Sync
        return self.sessions.get(session_id)

    def get_all_sessions(self, owner_id: str = None) -> list:
        self.sessions = self._load()  # [Fix] Multi-worker Sync
        # Filter out empty or ephemeral-only sessions AND filter by owner
        valid_sessions = []
        for s in self.sessions.values():
            # [Fix] Owner Check
            # If owner_id is provided, only show sessions for that owner.
            # If session has no owner (legacy), it might be visible to all or migration needed.
            # For strict isolation: if owner_id provided, must match.
            if owner_id and s.get("owner_id") != owner_id:
                # Allow access to legacy sessions (no owner_id) if configured,
                # but for new logic, we assume strict isolation.
                # However, to avoid hiding old sessions from everyone,
                # maybe we don't show them if owner_id is passed?
                # Let's show only matching owner_id.
                if s.get("owner_id"):  # If it HAS an owner and it doesn't match, skip
                    continue
                # If it doesn't have an owner, we might choose to show it or not.
                # Let's hide it to be safe for new users.
                # But existing users might lose history.
                # Tradeoff: Hide header-less sessions from header-bearing users?
                # Let's stick to strict match if session has owner,
                # and if session has no owner, maybe allow?
                # For now: strict match if session has owner.
                pass

            # Additional logic: If request has owner_id, only return matching sessions.
            # If session has no owner_id, only return if request has no owner_id?
            sess_owner = s.get("owner_id")
            if sess_owner != owner_id:
                continue

            msgs = s.get("messages", [])
            if not msgs:
                continue

            # Check if has any meaningful user message
            has_meaningful = False
            for m in msgs:
                if m["role"] == "user":
                    # Handle both string and object parts (legacy/new mix)
                    content = ""
                    parts = m.get("parts", [])
                    if parts:
                        p = parts[0]
                        if isinstance(p, dict):
                            content = p.get("text", "")
                        else:
                            content = str(p)

                    # Ephemeral commands that shouldn't persist session
                    if not content.strip().startswith(("/status", "/help", "/memory view", "/clear")):
                        has_meaningful = True
                        break

            if has_meaningful:
                valid_sessions.append(s)

        # Sort by updated_at desc
        return sorted(
            valid_sessions,
            key=lambda x: x.get("updated_at", ""),
            reverse=True,
        )

    def add_message(self, session_id: str, role: str, message: str, save: bool = True) -> None:
        # Always reload latest snapshot before mutating.
        # Without this, stale in-memory state from another worker can resurrect deleted sessions.
        self.sessions = self._load()
        if session_id not in self.sessions:
            # Fallback (Ephemeral check handled in chat, but here strictly requires existence or auto-create)
            # Since chat method handles ephemeral, if we reach here, we must modify a session.
            # If logic is correct, this might be rare, but let's be safe.
            self.create_session(session_id=session_id)  # Auto-recover

        session = self.sessions[session_id]

        # FIX: Store parts as objects for Gemini SDK compatibility
        # parts=[{"text": "message"}] instead of parts=["message"]
        # Add timestamp
        session["messages"].append(
            {
                "role": role,
                "parts": [{"text": message}],
                "timestamp": datetime.now().isoformat(),
            }
        )
        session["updated_at"] = datetime.now().isoformat()

        # Auto-title (first user message)
        if len(session["messages"]) == 1 and role == "user":
            clean_msg = message.strip().replace("\n", " ")
            session["title"] = clean_msg[:30] + "..." if len(clean_msg) > 30 else clean_msg
        elif len(session["messages"]) == 2 and role == "user":
            clean_msg = message.strip().replace("\n", " ")
            session["title"] = clean_msg[:30] + "..." if len(clean_msg) > 30 else clean_msg

        # Limit per session (optional, kept 50 for now)
        if len(session["messages"]) > 50:
            session["messages"] = session["messages"][-50:]

        if save:
            self._save()

    def get_messages(self, session_id: str) -> list:
        # Sync from disk for multi-worker consistency.
        self.sessions = self._load()
        session = self.sessions.get(session_id)
        if session:
            # FIX: Sanitize legacy messages where parts might be strings
            sanitized = []
            for i, msg in enumerate(session["messages"]):
                new_parts = []
                for p in msg["parts"]:
                    if isinstance(p, str):
                        new_parts.append({"text": _normalize_markdown_text(p)})
                    else:
                        if isinstance(p, dict) and isinstance(p.get("text"), str):
                            sanitized_part = {**p, "text": _normalize_markdown_text(p["text"])}
                            new_parts.append(sanitized_part)
                        else:
                            new_parts.append(p)

                # Create sanitized message object
                sanitized_msg = {
                    "role": msg["role"],
                    "parts": new_parts,
                }

                # Preserve timestamp if exists, else backfill with session time
                if "timestamp" in msg:
                    sanitized_msg["timestamp"] = msg["timestamp"]
                else:
                    # Fallback for legacy messages
                    if i == 0:
                        sanitized_msg["timestamp"] = session.get("created_at", datetime.now().isoformat())
                    elif i == len(session["messages"]) - 1:
                        sanitized_msg["timestamp"] = session.get("updated_at", datetime.now().isoformat())
                    else:
                        # For middle messages, just use created_at or interpolate if needed.
                        # Using created_at is safe enough for history.
                        sanitized_msg["timestamp"] = session.get("created_at", datetime.now().isoformat())

                sanitized.append(sanitized_msg)
            return sanitized
        return []

    def to_dict(self) -> Dict[str, Any]:
        """전체 세션 딕셔너리를 반환한다."""
        self.sessions = self._load()
        return self.sessions
