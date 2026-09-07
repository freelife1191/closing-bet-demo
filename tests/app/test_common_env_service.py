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
