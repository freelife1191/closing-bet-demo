#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
챗봇 History 저장/필터링 헬퍼
"""

from __future__ import annotations

import functools
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict

from .markdown_utils import _normalize_markdown_text


def locked(method: Callable) -> Callable:
    """인스턴스의 self._lock(RLock) 아래에서 메서드를 실행한다.

    워커의 요청 스레드들이 저장소 인스턴스 하나를 공유하고, 재적재가 인메모리 사전을 통째로
    바꾸므로 「재적재 → 변경 → 저장」을 한 덩어리로 묶는다([CHAT-033]).
    """
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return wrapper


def atomic_write_json(file_path: Path, data: Dict[str, Any]) -> None:
    """히스토리 파일을 원자적으로 저장한다."""
    data_dir = file_path.parent
    if not data_dir.exists():
        data_dir.mkdir(parents=True, exist_ok=True)

    tmp_path = file_path.with_name(f"{file_path.name}.tmp-{uuid.uuid4().hex}")
    try:
        # 대화 내용이 담기므로 서버 계정만 읽도록 0600 으로 만든다. os.replace 가 권한을 옮긴다.
        fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, file_path)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass


def backup_corrupt_history(file_path: Path, logger: Any) -> None:
    """손상된 히스토리 파일을 백업한다."""
    if not file_path.exists():
        return

    backup_path = file_path.with_name(
        f"{file_path.stem}.corrupt-"
        f"{datetime.now().strftime('%Y%m%d%H%M%S')}-"
        f"{uuid.uuid4().hex[:8]}{file_path.suffix}"
    )
    try:
        os.replace(file_path, backup_path)
        logger.warning(f"Corrupt history backed up to: {backup_path}")
    except Exception as backup_error:
        logger.error(f"Failed to backup corrupt history: {backup_error}")


def _migrate_legacy_list_history(data: list[Any]) -> Dict[str, Any]:
    default_id = str(uuid.uuid4())
    return {
        default_id: {
            "id": default_id,
            "title": "이전 대화",
            "messages": data,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "model": "gemini-3.7-flash",
        }
    }


def load_history_sessions(file_path: Path, logger: Any) -> Dict[str, Any]:
    """히스토리 파일을 로드하고 필요 시 복구한다."""
    if not file_path.exists():
        return {}

    try:
        raw = file_path.read_text(encoding="utf-8")
        if not raw.strip():
            logger.warning("History file is empty. Reinitializing with empty JSON.")
            atomic_write_json(file_path, {})
            return {}

        data = json.loads(raw)
        if isinstance(data, list):
            migrated = _migrate_legacy_list_history(data)
            atomic_write_json(file_path, migrated)
            return migrated
        if isinstance(data, dict):
            return data

        logger.error(f"Unexpected history format type: {type(data).__name__}")
        backup_corrupt_history(file_path, logger)
        atomic_write_json(file_path, {})
    except json.JSONDecodeError as e:
        logger.error(f"Failed to load history (invalid JSON): {e}")
        try:
            backup_corrupt_history(file_path, logger)
            atomic_write_json(file_path, {})
        except Exception as recover_error:
            logger.error(f"Failed to recover corrupt history file: {recover_error}")
    except Exception as e:
        logger.error(f"Failed to load history: {e}")

    return {}


def _get_user_message_text(message: dict[str, Any]) -> str:
    parts = message.get("parts", [])
    if not parts:
        return ""
    first = parts[0]
    if isinstance(first, dict):
        return str(first.get("text", ""))
    return str(first)


def has_meaningful_user_message(messages: list[dict[str, Any]]) -> bool:
    """세션에 실질 사용자 질의가 포함되는지 확인한다."""
    for message in messages:
        if message.get("role") != "user":
            continue
        content = _get_user_message_text(message)
        if not content.strip().startswith(("/status", "/help", "/memory view", "/clear")):
            return True
    return False


def should_include_session_for_owner(session: dict[str, Any], owner_id: str | None) -> bool:
    """세션 목록에 포함할지 판정한다. 소유자가 정확히 일치할 때만 포함한다.

    요청자의 소유자를 알 수 없으면 빈 목록을 돌려준다. 그렇게 하지 않으면
    owner_id 가 None 인 요청과 소유자가 비어 있는 레거시 세션이 서로 같다고
    판정되어, 인증 헤더를 싣지 않은 요청이 레거시 세션 전부를 목록으로 받는다.
    목록 응답은 메시지까지 함께 실으므로 그것만으로 대화 전문이 새어 나간다.
    접근 허용 여부는 기준이 달라서 is_session_accessible_by_owner 가 판정한다.
    """
    if not owner_id:
        return False
    return session.get("owner_id") == owner_id


def is_session_accessible_by_owner(session: dict[str, Any], owner_id: str | None) -> bool:
    """세션을 조회하거나 삭제할 수 있는지 판정한다.

    접근은 「확실히 남의 것인가」를 묻는다. 소유자가 기록된 세션은 그 소유자만
    건드릴 수 있고, 소유자가 비어 있는 레거시 세션은 세션 ID 를 아는 요청에만
    열어 둔다. 세션 ID 는 uuid4 라 추측할 수 없고, 그 세션으로 대화를 이어 가면
    session_access._assign_owner_if_empty 가 소유자를 채워 준다.
    """
    session_owner = session.get("owner_id")
    if not session_owner:
        return True
    return session_owner == owner_id


def sanitize_session_messages(session: dict[str, Any]) -> list[dict[str, Any]]:
    """히스토리 메시지를 Gemini SDK 호환 구조로 정규화한다."""
    messages = session.get("messages", [])
    sanitized = []
    total = len(messages)

    for index, msg in enumerate(messages):
        parts = msg.get("parts", [])
        new_parts = []
        for part in parts:
            if isinstance(part, str):
                new_parts.append({"text": _normalize_markdown_text(part)})
                continue

            if isinstance(part, dict) and isinstance(part.get("text"), str):
                new_parts.append({**part, "text": _normalize_markdown_text(part["text"])})
            else:
                new_parts.append(part)

        sanitized_msg = {
            "role": msg.get("role", "user"),
            "parts": new_parts,
        }

        if "timestamp" in msg:
            sanitized_msg["timestamp"] = msg["timestamp"]
        else:
            if index == 0:
                sanitized_msg["timestamp"] = session.get("created_at", datetime.now().isoformat())
            elif index == total - 1:
                sanitized_msg["timestamp"] = session.get("updated_at", datetime.now().isoformat())
            else:
                sanitized_msg["timestamp"] = session.get("created_at", datetime.now().isoformat())

        sanitized.append(sanitized_msg)

    return sanitized


__all__ = [
    "atomic_write_json",
    "backup_corrupt_history",
    "has_meaningful_user_message",
    "is_session_accessible_by_owner",
    "load_history_sessions",
    "locked",
    "sanitize_session_messages",
    "should_include_session_for_owner",
]

