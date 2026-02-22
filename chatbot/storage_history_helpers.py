#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
챗봇 History 저장/필터링 헬퍼
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from .markdown_utils import _normalize_markdown_text


def atomic_write_json(file_path: Path, data: Dict[str, Any]) -> None:
    """히스토리 파일을 원자적으로 저장한다."""
    data_dir = file_path.parent
    if not data_dir.exists():
        data_dir.mkdir(parents=True, exist_ok=True)

    tmp_path = file_path.with_name(f"{file_path.name}.tmp-{uuid.uuid4().hex}")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
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
            "model": "gemini-2.0-flash-lite",
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
    """기존 owner 필터 계약을 유지한다."""
    if owner_id and session.get("owner_id") != owner_id:
        if session.get("owner_id"):
            return False

    sess_owner = session.get("owner_id")
    if sess_owner != owner_id:
        return False
    return True


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
    "load_history_sessions",
    "sanitize_session_messages",
    "should_include_session_for_owner",
]

