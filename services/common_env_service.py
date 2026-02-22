#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Common Env Service

공통 라우트의 .env 관리 로직을 분리한다.
"""

from __future__ import annotations

import os
from typing import Any


SENSITIVE_KEYWORDS = [
    "KEY",
    "SECRET",
    "PASSWORD",
    "TOKEN",
    "USER",
    "ID",
    "URL",
    "HOST",
    "RECIPIENTS",
]

FACTORY_RESET_SENSITIVE_KEYS = [
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "GOOGLE_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "ZAI_API_KEY",
    "PERPLEXITY_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "DISCORD_WEBHOOK_URL",
    "SLACK_WEBHOOK_URL",
    "SMTP_USER",
    "SMTP_PASSWORD",
    "EMAIL_RECIPIENTS",
    "USER_PROFILE",
]

FACTORY_RESET_DELETE_FILES = [
    "user_quota.json",
    "chatbot_history.json",
    "chatbot_memory.json",
    "chatbot_sessions.json",
    "chatbot_storage.db",
    "chatbot_storage.db-shm",
    "chatbot_storage.db-wal",
]


def resolve_project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resolve_env_path(project_root: str | None = None) -> str:
    root = project_root or resolve_project_root()
    return os.path.join(root, ".env")


def resolve_data_dir(project_root: str | None = None) -> str:
    root = project_root or resolve_project_root()
    return os.path.join(root, "data")


def _mask_env_value(key: str, value: str) -> str:
    if not any(keyword in key for keyword in SENSITIVE_KEYWORDS):
        return value
    if len(value) > 8:
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
            env_vars[key] = _mask_env_value(key, value)

    return env_vars


def update_env_file(
    env_path: str,
    data: dict[str, Any],
    environ: dict[str, str],
) -> None:
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


def reset_sensitive_env_and_user_data(
    env_path: str,
    data_dir: str,
    environ: dict[str, str],
    logger: Any,
) -> None:
    lines: list[str] = []
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as file:
            lines = file.readlines()

    new_lines: list[str] = []
    for line in lines:
        line_stripped = line.strip()
        if not line_stripped or line_stripped.startswith("#"):
            new_lines.append(line)
            continue

        if "=" not in line_stripped:
            new_lines.append(line)
            continue

        key = line_stripped.split("=", 1)[0]
        if key in FACTORY_RESET_SENSITIVE_KEYS:
            new_lines.append(f"{key}=\n")
            environ[key] = ""
        else:
            new_lines.append(line)

    os.makedirs(os.path.dirname(env_path) or ".", exist_ok=True)
    with open(env_path, "w", encoding="utf-8") as file:
        file.writelines(new_lines)

    for filename in FACTORY_RESET_DELETE_FILES:
        file_path = os.path.join(data_dir, filename)
        if not os.path.exists(file_path):
            continue
        try:
            os.remove(file_path)
            logger.info(f"Factory Reset: Deleted {filename}")
        except Exception as e:
            logger.error(f"Failed to delete {filename}: {e}")
