#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
슬래시 명령 처리 유틸
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional


def clear_current_session_messages(bot: Any, session_id: Optional[str]) -> bool:
    """현재 세션 메시지를 비운다."""
    if not session_id:
        return False

    session = bot.history.get_session(session_id)
    if not session:
        return False

    session["messages"] = []
    session["updated_at"] = datetime.now().isoformat()

    if hasattr(bot.history, "_mark_session_changed"):
        bot.history._mark_session_changed(session_id)
    if hasattr(bot.history, "_invalidate_message_cache"):
        bot.history._invalidate_message_cache(session_id)
    if hasattr(bot.history, "_invalidate_session_list_cache"):
        bot.history._invalidate_session_list_cache()
    if hasattr(bot.history, "_save"):
        bot.history._save()
    return True


def handle_clear_command(bot: Any, parts: list[str], session_id: Optional[str]) -> str:
    """`/clear` 명령 처리."""
    subcommand = parts[1].lower() if len(parts) > 1 else ""
    if subcommand == "all":
        bot.history.clear_all()
        bot.memory.clear()
        bot._data_cache = None
        if hasattr(bot, "_cache_timestamp"):
            bot._cache_timestamp = None
        return "🧹 모든 데이터가 초기화되었습니다. (히스토리/메모리/캐시)"

    if clear_current_session_messages(bot, session_id):
        return "🧹 현재 대화 세션이 초기화되었습니다."
    return "⚠️ 초기화할 현재 세션이 없습니다."


def handle_refresh_command(bot: Any) -> str:
    """시장 데이터 캐시 수동 갱신."""
    bot._data_cache = None
    if hasattr(bot, "_cache_timestamp"):
        bot._cache_timestamp = None
    return "🔄 데이터 캐시를 초기화했습니다. 다음 질의에서 최신 데이터를 다시 로드합니다."


def render_model_command_help(bot: Any) -> str:
    models = bot.get_available_models()
    lines = ["🤖 **모델 명령어 도움말**", "", "사용법: `/model [모델명]`", ""]
    if models:
        lines.append("사용 가능한 모델:")
        lines.extend([f"- `{model}`" for model in models])
    else:
        lines.append("- 사용 가능한 모델이 없습니다.")
    lines.append("")
    lines.append(f"현재 모델: `{bot.current_model_name}`")
    return "\n".join(lines)


def handle_model_command(bot: Any, parts: list[str], session_id: Optional[str]) -> str:
    """`/model` 명령 처리."""
    if len(parts) == 1:
        return render_model_command_help(bot)

    target = parts[1].strip()
    if not target:
        return render_model_command_help(bot)

    if not bot.set_model(target):
        models = ", ".join(bot.get_available_models())
        return f"⚠️ 지원하지 않는 모델입니다: `{target}`\n사용 가능: {models}"

    if session_id:
        session = bot.history.get_session(session_id)
        if session is not None:
            session["model"] = target
            session["updated_at"] = datetime.now().isoformat()
            if hasattr(bot.history, "_mark_session_changed"):
                bot.history._mark_session_changed(session_id)
            if hasattr(bot.history, "_invalidate_session_list_cache"):
                bot.history._invalidate_session_list_cache()
            if hasattr(bot.history, "_save"):
                bot.history._save()

    return f"✅ 모델이 `{target}`로 변경되었습니다."


def _normalize_memory_value(memory_entry: Any) -> Any:
    if isinstance(memory_entry, dict) and "value" in memory_entry:
        return memory_entry["value"]
    return memory_entry


def render_memory_view(bot: Any) -> str:
    memories = bot.memory.view()
    if not memories:
        return "📭 저장된 메모리가 없습니다."

    lines = ["🧠 **저장된 메모리**"]
    for key in sorted(memories.keys()):
        value = _normalize_memory_value(memories[key])
        lines.append(f"- `{key}`: {value}")
    return "\n".join(lines)


def render_memory_help() -> str:
    return "\n".join(
        [
            "🧠 **메모리 명령어 도움말**",
            "- `/memory view`",
            "- `/memory add <key> <value>`",
            "- `/memory update <key> <value>`",
            "- `/memory remove <key>`",
            "- `/memory clear`",
        ]
    )


def handle_memory_write_action(bot: Any, action: str, args: list[str]) -> Optional[str]:
    """메모리 쓰기 액션(add/update/remove/clear)을 처리한다."""
    action = action.lower()

    if action == "clear":
        return bot.memory.clear()

    if action in {"add", "update"}:
        if len(args) < 2:
            return "⚠️ key/value를 함께 입력해주세요."
        key = args[0]
        value = " ".join(args[1:])
        if action == "add":
            return bot.memory.add(key, value)
        return bot.memory.update(key, value)

    if action == "remove":
        if not args:
            return "⚠️ 삭제할 key를 입력해주세요."
        return bot.memory.remove(args[0])

    return None


def handle_memory_command(bot: Any, args: list[str]) -> str:
    """`/memory` 명령 처리."""
    if not args:
        return render_memory_help()

    action = args[0].lower()
    if action in {"help", "?", "h"}:
        return render_memory_help()
    if action == "view":
        return render_memory_view(bot)

    result = handle_memory_write_action(bot, action, args[1:])
    if result is not None:
        return result
    return f"⚠️ 알 수 없는 memory 명령입니다: `{action}`\n{render_memory_help()}"


def get_status_message(bot: Any) -> str:
    """현재 상태 메시지."""
    status = bot.get_status()
    return "\n".join(
        [
            "📊 **현재 상태**",
            f"- 사용자: {status.get('user_id', '-')}",
            f"- 모델: {status.get('model', '-')}",
            f"- 메모리 개수: {status.get('memory_count', 0)}",
            f"- 세션 개수: {status.get('history_count', 0)}",
        ]
    )


def get_help() -> str:
    """전체 명령 도움말."""
    return "\n".join(
        [
            "🤖 **스마트머니봇 도움말**",
            "",
            "주요 명령어:",
            "- `/status` 현재 상태",
            "- `/help` 도움말",
            "- `/clear` 현재 세션 초기화",
            "- `/clear all` 전체 초기화",
            "- `/refresh` 캐시 새로고침",
            "- `/model` 모델 확인/변경",
            "- `/memory ...` 메모리 관리",
        ]
    )


def handle_command(bot: Any, command: str, session_id: str = None) -> str:
    """슬래시 명령 라우팅."""
    parts = (command or "").strip().split()
    if not parts:
        return "⚠️ 빈 명령어입니다."

    root = parts[0].lower()
    if root == "/status":
        return get_status_message(bot)
    if root == "/help":
        return get_help()
    if root == "/clear":
        return handle_clear_command(bot, parts, session_id)
    if root == "/refresh":
        return handle_refresh_command(bot)
    if root == "/model":
        return handle_model_command(bot, parts, session_id)
    if root == "/memory":
        return handle_memory_command(bot, parts[1:])

    return f"⚠️ 알 수 없는 명령어입니다: `{root}`\n`/help`로 사용법을 확인하세요."


__all__ = [
    "clear_current_session_messages",
    "get_help",
    "get_status_message",
    "handle_clear_command",
    "handle_command",
    "handle_memory_command",
    "handle_memory_write_action",
    "handle_model_command",
    "handle_refresh_command",
    "render_memory_help",
    "render_memory_view",
    "render_model_command_help",
]

