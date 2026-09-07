#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Common Env Service 단위 테스트
"""

from pathlib import Path

from services.common_env_service import (
    read_masked_env_vars,
    update_env_file,
)


def test_read_masked_env_vars_masks_sensitive_and_skips_empty(tmp_path: Path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                # 24자를 넘는 값은 앞뒤 네 자를 남긴다
                "OPENAI_API_KEY=abcd1234567890123456789wxyz",
                # 24자 이하는 전부 가린다. 16자 앱 비밀번호가 절반을 흘리던 자리다
                "SMTP_PASSWORD=abcdefghijklmnop",
                "SMTP_PORT=587",
                "SMTP_USER=",
                "# comment",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = read_masked_env_vars(str(env_path))
    assert result["SMTP_PORT"] == "587"
    assert result["OPENAI_API_KEY"].startswith("abcd")
    assert result["OPENAI_API_KEY"].endswith("wxyz")
    assert result["SMTP_PASSWORD"] == "*" * 16
    assert "SMTP_USER" not in result


def test_update_env_file_preserves_masked_input_and_deletes_empty(tmp_path: Path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "OPENAI_API_KEY=secret-value\nSMTP_HOST=old\nSMTP_USER=1\n",
        encoding="utf-8",
    )

    environ: dict[str, str] = {}
    update_env_file(
        str(env_path),
        {
            "OPENAI_API_KEY": "****",  # 마스킹 값은 변경 금지
            "SMTP_HOST": "new",
            "SMTP_USER": "",
            "TELEGRAM_CHAT_ID": "ok",
        },
        environ,
    )

    content = env_path.read_text(encoding="utf-8")
    assert "OPENAI_API_KEY=secret-value" in content
    assert "SMTP_HOST=new" in content
    assert "SMTP_USER=" not in content
    assert "TELEGRAM_CHAT_ID=ok" in content
    assert environ["SMTP_HOST"] == "new"
    assert environ["TELEGRAM_CHAT_ID"] == "ok"


def test_read_masked_env_vars_omits_authorization_keys(tmp_path: Path):
    """[INFRA-044] 인가 판정 근거는 관리자 화면 응답에도 실리지 않는다."""
    env_path = tmp_path / ".env"
    env_path.write_text(
        "ADMIN_EMAILS=owner@example.com\nADMIN_API_TOKEN=token-value\nSMTP_PORT=587\n",
        encoding="utf-8",
    )

    result = read_masked_env_vars(str(env_path))
    assert "ADMIN_EMAILS" not in result
    assert "ADMIN_API_TOKEN" not in result
    # 전부 거르는 코드도 위 두 줄을 통과하므로 허용 키가 실리는 것을 함께 잰다.
    assert result["SMTP_PORT"] == "587"


def test_update_env_file_rejects_authorization_keys(tmp_path: Path):
    """[INFRA-044] 설정 화면으로 인가 판정 근거를 덮어쓸 수 없다.

    `is_admin_email` 은 매 요청 `os.environ` 을 다시 읽는다. 이 필터가 뚫리면 요청을
    처리한 워커의 명단만 바뀌어, 같은 관리자의 같은 요청이 어느 워커에 닿느냐에 따라
    통과와 거부로 갈린다.
    """
    env_path = tmp_path / ".env"
    env_path.write_text(
        "ADMIN_EMAILS=owner@example.com\nSMTP_HOST=old\n", encoding="utf-8"
    )

    environ: dict[str, str] = {}
    update_env_file(
        str(env_path),
        {
            "ADMIN_EMAILS": "attacker@example.com",
            "ADMIN_API_TOKEN": "forged",
            "SMTP_HOST": "new",
        },
        environ,
    )

    content = env_path.read_text(encoding="utf-8")
    assert "ADMIN_EMAILS=owner@example.com" in content
    assert "ADMIN_API_TOKEN" not in content
    assert "ADMIN_EMAILS" not in environ
    assert "ADMIN_API_TOKEN" not in environ
    assert "SMTP_HOST=new" in content
    assert environ["SMTP_HOST"] == "new"


def test_update_env_file_rejects_newline_in_value(tmp_path: Path):
    """[INFRA-044] 허용 키의 값에 개행을 넣어 목록 밖의 줄을 쓸 수 없다.

    키만 검사하면 값 하나가 두 줄이 되어 필터를 그대로 지나간다. `.env` 는
    restart_all.sh 와 stop_all.sh 가 source 하므로 주입한 줄은 다음 기동에서 셸
    명령으로도 실행된다.
    """
    env_path = tmp_path / ".env"
    env_path.write_text("SMTP_HOST=old\n", encoding="utf-8")

    environ: dict[str, str] = {}
    update_env_file(
        str(env_path),
        {
            # 기존 줄을 갱신하는 경로
            "SMTP_HOST": "smtp.example.com\nADMIN_EMAILS=attacker@example.com",
            # 새 키를 덧붙이는 경로
            "EMAIL_RECIPIENTS": "a@b.c\rADMIN_API_TOKEN=forged",
            "SMTP_PORT": "587",
        },
        environ,
    )

    content = env_path.read_text(encoding="utf-8")
    assert "ADMIN_EMAILS" not in content
    assert "ADMIN_API_TOKEN" not in content
    assert "SMTP_HOST=old" in content
    assert "EMAIL_RECIPIENTS" not in content
    assert "SMTP_HOST" not in environ
    # 개행이 없는 값은 그대로 반영되어야 한다.
    assert "SMTP_PORT=587" in content
    assert environ["SMTP_PORT"] == "587"


def test_update_env_file_rejects_interpolation_in_value(tmp_path: Path):
    """[INFRA-044] 값에 다른 키를 참조해 가려 둔 비밀을 끌어다 쓸 수 없다.

    python-dotenv 와 @next/env 가 `${VAR}` 와 맨 `$VAR` 를 보간하므로, 이것이 통과하면
    서버가 발송 대상 주소에 자기 토큰을 실어 보낸다. 읽는 쪽에서는 막을 수 없다.
    @next/env 에는 보간을 끄는 인자가 없다.
    """
    env_path = tmp_path / ".env"
    env_path.write_text("SMTP_HOST=old\n", encoding="utf-8")

    environ: dict[str, str] = {}
    update_env_file(
        str(env_path),
        {
            "DISCORD_WEBHOOK_URL": "https://x.test/${ADMIN_API_TOKEN}",
            "SMTP_PASSWORD": "$INTERNAL_IDENTITY_SECRET",
            "SMTP_USER": "u@x.test$(id)",
            # `$` 로 끝나거나 기호가 이어지는 값은 보간되지 않으므로 통과해야 한다.
            "TELEGRAM_BOT_TOKEN": "pass!word$",
            "TELEGRAM_CHAT_ID": "has$!bang",
            "SMTP_HOST": "new",
        },
        environ,
    )

    content = env_path.read_text(encoding="utf-8")
    assert "ADMIN_API_TOKEN" not in content
    assert "INTERNAL_IDENTITY_SECRET" not in content
    assert "$(id)" not in content
    assert "SMTP_PASSWORD" not in content
    assert "SMTP_USER" not in content
    # 전부 거부하는 코드도 위 다섯 줄을 통과하므로 정상 값 셋을 함께 잰다.
    assert "SMTP_HOST=new" in content
    assert "TELEGRAM_BOT_TOKEN=pass!word$" in content
    assert "TELEGRAM_CHAT_ID=has$!bang" in content
