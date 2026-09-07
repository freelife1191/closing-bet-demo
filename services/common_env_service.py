#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Common Env Service

공통 라우트의 .env 관리 로직을 분리한다.
"""

from __future__ import annotations

import os
from typing import Any


# 설정 화면(`SettingsModal.tsx`)이 실제로 읽고 쓰는 키만 오간다. 나머지를 함께 실어
# 보내면 관리자 화면 하나가 .env 전체의 사본이 된다. 종전에는 키 이름에 KEY·SECRET
# 같은 단어가 있는지로 가릴지 정했는데, 그 방식은 해당 단어가 없는 변수를 그대로
# 흘렸고 그 안에 ADMIN_EMAILS 가 있었다. 화면에 필드를 더할 때 이 목록에도 더한다.
EDITABLE_ENV_KEYS = frozenset(
    {
        "AI_PROVIDER",
        "DISCORD_WEBHOOK_URL",
        "EMAIL_RECIPIENTS",
        "GOOGLE_SEARCH_ENGINE_ID",
        "OPENAI_API_KEY",
        "PERPLEXITY_API_KEY",
        "SMTP_HOST",
        "SMTP_PASSWORD",
        "SMTP_PORT",
        "SMTP_USER",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
    }
)

# 값 자체가 화면 동작에 필요하고 새어도 무해한 키. AI_PROVIDER 를 가리면 공급자
# 버튼이 어느 것도 선택되지 않는다. 종전 규칙에서는 PROVIDER 안의 "ID" 가 걸려
# 실제로 마스킹되고 있었다. SMTP_HOST 는 smtp.gmail.com 같은 공개 주소이고, 아래
# MASK_KEEP_EDGES_MIN 을 올리면 짧아서 전부 가려지는 탓에 관리자가 어느 서버로
# 보내는지 화면에서 확인할 수 없게 된다.
PLAIN_ENV_KEYS = frozenset({"AI_PROVIDER", "SMTP_HOST", "SMTP_PORT"})

# 이 길이 이하의 값은 앞뒤를 남기지 않고 전부 가린다. 종전 기준은 8 이었는데, 그러면
# 16자인 Google 앱 비밀번호가 절반을 그대로 흘렸다. SMTP_HOST 와 SMTP_USER 가 같은
# 응답에 함께 실리므로 나머지만 맞히면 곧바로 인증된다.
MASK_KEEP_EDGES_MIN = 24


def resolve_project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resolve_env_path(project_root: str | None = None) -> str:
    root = project_root or resolve_project_root()
    return os.path.join(root, ".env")


def _mask_env_value(key: str, value: str) -> str:
    if key in PLAIN_ENV_KEYS:
        return value
    if len(value) > MASK_KEEP_EDGES_MIN:
        return value[:4] + ("*" * (len(value) - 8)) + value[-4:]
    return "*" * len(value)


def read_masked_env_vars(env_path: str) -> dict[str, str]:
    if not os.path.exists(env_path):
        return {}

    env_vars: dict[str, str] = {}
    with open(env_path, "r", encoding="utf-8") as file:
        for raw_line in file:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            if not value or value.strip() == "":
                continue
            if key not in EDITABLE_ENV_KEYS:
                continue
            env_vars[key] = _mask_env_value(key, value)

    return env_vars


def update_env_file(
    env_path: str,
    data: dict[str, Any],
    environ: dict[str, str],
) -> None:
    if not data:
        return

    # 게이트를 통과한 관리자라도 화면에서 ADMIN_EMAILS 나 ADMIN_API_TOKEN 을 덮어쓰면
    # 자기 자신을 잠글 수 있다. 읽기와 같은 목록으로 쓰기도 막는다.
    #
    # 키만 보면 부족하다. 값에 개행이 있으면 한 항목이 두 줄로 나뉘어, 목록 밖의 키를
    # .env 에 그대로 쓸 수 있다. restart_all.sh 와 stop_all.sh 가 이 파일을 source 하므로
    # 주입한 줄은 다음 기동에서 셸 명령으로도 실행된다. 아래 두 쓰기 경로에 각각 두지
    # 않고 여기 한 자리에서 함께 막는다.
    data = {
        key: value
        for key, value in data.items()
        if key in EDITABLE_ENV_KEYS and "\n" not in str(value) and "\r" not in str(value)
    }
    if not data:
        return

    lines: list[str] = []
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as file:
            lines = file.readlines()

    updated_keys: set[str] = set()
    new_lines: list[str] = []

    for original_line in lines:
        line_stripped = original_line.strip()
        if not line_stripped or line_stripped.startswith("#"):
            new_lines.append(original_line)
            continue

        if "=" not in line_stripped:
            new_lines.append(original_line)
            continue

        key = line_stripped.split("=", 1)[0]
        if key not in data:
            new_lines.append(original_line)
            continue

        new_value = str(data.get(key, ""))
        updated_keys.add(key)

        if "*" in new_value:
            # 마스킹 값은 사용자 입력이 아닌 조회 결과일 수 있어 기존 값 유지
            new_lines.append(original_line)
            continue

        if not new_value:
            environ.pop(key, None)
            continue

        new_lines.append(f"{key}={new_value}\n")
        environ[key] = new_value

    for key, raw_value in data.items():
        if key in updated_keys:
            continue
        value = str(raw_value)
        if "*" in value or not value:
            continue
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] += "\n"
        new_lines.append(f"{key}={value}\n")
        environ[key] = value

    os.makedirs(os.path.dirname(env_path) or ".", exist_ok=True)
    with open(env_path, "w", encoding="utf-8") as file:
        file.writelines(new_lines)
