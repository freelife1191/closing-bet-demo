#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
슬래시 명령어 처리 서비스
"""

from __future__ import annotations

from typing import Any, List, Optional


def clear_current_session_messages(bot: Any, session_id: Optional[str]) -> bool:
    """현재 세션 메시지를 초기화한다."""
    if not session_id:
        return False
    session = bot.history.get_session(session_id)
    if not session:
        return False
    session["messages"] = []
    bot.history._save()
    return True


def handle_clear_command(bot: Any, parts: List[str], session_id: Optional[str]) -> str:
    """`/clear` 명령 처리."""
    if len(parts) > 1 and parts[1] == "all":
        bot.history.clear_all()
        bot.memory.clear()
        return "✅ 모든 데이터가 초기화되었습니다."
    if clear_current_session_messages(bot, session_id):
        return "🧹 현재 대화 세션이 초기화되었습니다."
    return "⚠️ 세션 ID가 없어 초기화할 수 없습니다."


def handle_refresh_command(bot: Any) -> str:
    """데이터 캐시 초기화."""
    bot._data_cache = None
    return "✅ 데이터 캐시가 새로고침되었습니다."


def render_model_command_help(bot: Any) -> str:
    """`/model` 도움말 텍스트 렌더링."""
    available_models = "\n".join(
        [f"- {model_name}" for model_name in bot.get_available_models()]
    )
    return f"""🤖 **모델 설정**
━━━━━━━━━━━━━━━━━━━━

📌 **현재 모델**: {bot.current_model_name}

📋 **사용 가능 모델**:
{available_models}

━━━━━━━━━━━━━━━━━━━━"""


def handle_model_command(bot: Any, parts: List[str], session_id: Optional[str]) -> str:
    """`/model` 명령 처리."""
    if len(parts) <= 1:
        return render_model_command_help(bot)

    requested_model = parts[1]
    if not bot.set_model(requested_model):
        return f"⚠️ 유효하지 않은 모델입니다. 가능한 모델: {', '.join(bot.get_available_models())}"

    if session_id:
        session = bot.history.get_session(session_id)
        if session:
            session["model"] = requested_model
            bot.history._save()
    return f"✅ 모델이 '{requested_model}'로 변경되었습니다."


def render_memory_view(bot: Any) -> str:
    """저장된 메모리 목록 문자열 생성."""
    memories = bot.memory.view()
    if not memories:
        return "📭 저장된 메모리가 없습니다."

    result = "📝 **저장된 메모리**\n"
    for index, (key, data) in enumerate(memories.items(), 1):
        result += f"{index}. **{key}**: {data['value']}\n"
    return result


def render_memory_help() -> str:
    """메모리 명령어 사용법 문자열."""
    return """**사용법:**
`/memory view` - 저장된 메모리 보기
`/memory add 키 값` - 메모리 추가
`/memory update 키 값` - 메모리 수정  
`/memory remove 키` - 메모리 삭제
`/memory clear` - 전체 삭제"""


def handle_memory_write_action(bot: Any, action: str, args: List[str]) -> Optional[str]:
    """메모리 쓰기 액션(add/update/remove/clear)을 처리한다."""
    if action == "clear":
        return bot.memory.clear()

    if action == "remove" and len(args) >= 2:
        return bot.memory.remove(args[1])

    if action in ("add", "update") and len(args) >= 3:
        key = args[1]
        value = " ".join(args[2:])
        if action == "add":
            return bot.memory.add(key, value)
        return bot.memory.update(key, value)

    return None


def handle_memory_command(bot: Any, args: list) -> str:
    """메모리 명령어 처리."""
    if not args:
        args = ["view"]

    action = args[0].lower()

    if action == "view":
        return render_memory_view(bot)

    handled = handle_memory_write_action(bot, action, args)
    if handled is not None:
        return handled

    return render_memory_help()


def get_status_message(bot: Any) -> str:
    """현재 상태 확인 메시지."""
    status = bot.get_status()
    return f"""📊 **현재 상태**
━━━━━━━━━━━━━━━━━━━━

- 👤 **사용자**: {status['user_id']}
- 🖥️ **모델**: {status['model']}
- 💾 **저장된 메모리**: {status['memory_count']}개
- 💬 **대화 히스토리**: {status['history_count']}개

━━━━━━━━━━━━━━━━━━━━"""


def get_help() -> str:
    """도움말."""
    return """🤖 **스마트머니봇 도움말**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📌 **일반 대화**

그냥 질문하면 됩니다!

* "오늘 뭐 살까?"
* "삼성전자 어때?"
* "반도체 섹터 상황은?"

📌 **명령어**

* `/memory view` - 저장된 정보 보기
* `/memory add 키 값` - 정보 저장
* `/memory remove 키` - 정보 삭제
* `/clear` - 대화 히스토리 초기화
* `/clear all` - 모든 데이터 초기화
* `/status` - 현재 상태 확인
* `/refresh` - 데이터 새로고침
* `/help` - 도움말

📌 **저장 추천 정보**

* 투자성향: 공격적/보수적/중립
* 관심섹터: 반도체, 2차전지 등
* 보유종목: 삼성전자, SK하이닉스 등

━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""


def handle_command(bot: Any, command: str, session_id: str = None) -> str:
    """명령어 처리."""
    parts = command.split(maxsplit=3)
    cmd = parts[0].lower()

    handlers = {
        "/memory": lambda: handle_memory_command(bot, parts[1:]),
        "/clear": lambda: handle_clear_command(bot, parts, session_id),
        "/status": lambda: get_status_message(bot),
        "/help": get_help,
        "/refresh": lambda: handle_refresh_command(bot),
        "/model": lambda: handle_model_command(bot, parts, session_id),
    }
    handler = handlers.get(cmd)
    if not handler:
        return f"❓ 알 수 없는 명령어: {cmd}\n/help로 명령어를 확인하세요."
    return handler()
