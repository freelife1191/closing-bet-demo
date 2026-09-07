#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Common Env Service

공통 라우트의 .env 관리 로직을 분리한다.
"""

from __future__ import annotations

import os
import re
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

# 값 하나가 .env 의 한 줄로 끝나지 않게 만드는 문자들. 이 파일은 셋이 읽는다.
#
# 개행과 캐리지리턴: 한 항목이 두 줄로 나뉘어 EDITABLE_ENV_KEYS 밖의 키를 그대로 쓸 수
# 있다. `$` 뒤의 `{`·글자·숫자: python-dotenv 와 @next/env 가 `${VAR}` 와 맨 `$VAR` 를
# 보간하므로, 편집 가능한 키의 값에 `${ADMIN_API_TOKEN}` 을 넣으면 읽기에서 가려 둔 값이
# 그 키의 실제 값이 된다. 발송 대상 주소에 그것을 심으면 서버가 스스로 토큰을 보낸다.
# `$` 뒤의 `(`: restart_all.sh 와 stop_all.sh 가 이 파일을 source 하므로 명령 치환이
# 다음 기동에서 실행된다. 근본 해법은 그 source 를 걷어내는 것이고 [INFRA-049] 가 맡지만,
# 한 글자 더 막아 두는 값이 그보다 크다.
#
# `$` 하나만으로 막지는 않는다. `$` 로 끝나거나 `$!` 처럼 기호가 이어지는 비밀번호가 있다.
# 공백도 막지 않는다. Google 앱 비밀번호에 들어 있고 EMAIL_RECIPIENTS 가 `, ` 로 나눈다.
# 공백은 source 하는 셸에서만 위험하므로 [INFRA-049] 가 그 자리에서 없앤다.
UNSAFE_ENV_VALUE = re.compile(r"[\r\n]|\$[{(\w]")


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
    # 자기 자신을 잠글 수 있다. 읽기와 같은 목록으로 쓰기도 막는다. 키만 보면 부족해서
    # 값도 함께 본다. 막는 것과 이유는 UNSAFE_ENV_VALUE 에 적어 두었다. 아래 두 쓰기
    # 경로에 각각 두지 않고 여기 한 자리에서 함께 막는다.
    data = {
        key: value
        for key, value in data.items()
        if key in EDITABLE_ENV_KEYS and not UNSAFE_ENV_VALUE.search(str(value))
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
        # 이 파일에는 SMTP 비밀번호와 API 키, ADMIN_API_TOKEN, INTERNAL_IDENTITY_SECRET 이
        # 들어 있는데 운영 파일이 0644 였다. open(w) 는 기존 모드를 그대로 두고 새 파일은
        # umask 를 따르므로, 한 번 넓어진 모드가 이 화면을 아무리 써도 좁아지지 않았다
        # ([INFRA-053]). 같은 .env 를 쓰는 다른 경로인 persist_market_gate_interval_to_env
        # 는 atomic_write_text 가 NamedTemporaryFile(0600) 을 os.replace 로 옮기므로 이미
        # 0600 을 남긴다. 그래서 여기 한 자리만 맞추면 두 경로가 같아진다.
        #
        # 이 줄을 with 밖으로 옮겨 os.chmod(env_path, 0o600) 으로 바꾸지 않는다. 검사는
        # 그래도 전부 통과하지만, open(w) 가 파일을 잘라낸 뒤부터 chmod 까지 새 시크릿이
        # 0644 아래에 놓이는 창이 되살아난다. 여기서는 이미 0바이트로 잘린 뒤라 비어 있는
        # 파일의 모드를 좁힌다.
        #
        # 다만 이 배치가 닫는 것은 **이 뒤에 새로 여는** 주체의 경로뿐이다. 모드 변경은
        # 이미 열려 있는 파일 기술자를 회수하지 않으므로, 파일이 0644 이던 동안 열어 둔
        # 기술자는 같은 inode 에 이어서 쓰이는 값을 계속 읽는다. 그것까지 닫으려면 새
        # inode 에 쓰고 os.replace 로 갈아 끼워야 하며 그 일은 [INFRA-050] 이 맡는다.
        # 이 지적은 2026-09-08 라운드에서 보안 리뷰와 Codex 가 각각 독립적으로 냈다.
        #
        # 대가는 이 자리가 잘라낸 뒤의 실패 지점 하나를 더한다는 것이다. 여기서 예외가
        # 나면 .env 가 빈 채로 남고 호출자는 그것을 되돌리지 않는다
        # (app/routes/common_update_routes.py:69-84 가 500 으로 바꿀 뿐이다). 다만
        # writelines 가 실패해도 결과는 같으므로 이 함수가 원래 갖고 있던 성질이고, 근본
        # 해법인 원자적 교체는 [INFRA-050] 이 맡는다.
        #
        # 이 배포는 파일 소유자와 gunicorn 워커가 같은 계정이라 계정 불일치로 인한 EPERM 은
        # 없다. 그것이 유일한 실패 원인은 아니다. macOS 의 chflags uchg 는 소유자가 스스로
        # 걸 수 있고 open 과 이 줄 사이에 걸리면 계정과 무관하게 실패하며, POSIX 권한 비트를
        # 지원하지 않는 마운트에서는 언제나 실패한다. 확률이 낮을 뿐 배제된 것이 아니다.
        os.fchmod(file.fileno(), 0o600)
        file.writelines(new_lines)
