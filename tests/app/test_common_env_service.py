#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Common Env Service 단위 테스트
"""

from pathlib import Path
import types

from services.common_env_service import (
    read_masked_env_vars,
    reset_sensitive_env_and_user_data,
    update_env_file,
)


def test_read_masked_env_vars_masks_sensitive_and_skips_empty(tmp_path: Path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "GOOGLE_API_KEY=abcd1234wxyz",
                "NORMAL_VALUE=hello",
                "EMPTY_VALUE=",
                "# comment",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = read_masked_env_vars(str(env_path))
    assert result["NORMAL_VALUE"] == "hello"
    assert result["GOOGLE_API_KEY"].startswith("abcd")
    assert "EMPTY_VALUE" not in result


def test_update_env_file_preserves_masked_input_and_deletes_empty(tmp_path: Path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "GOOGLE_API_KEY=secret-value\nNORMAL=old\nREMOVE_ME=1\n",
        encoding="utf-8",
    )

    environ: dict[str, str] = {}
    update_env_file(
        str(env_path),
        {
            "GOOGLE_API_KEY": "****",  # 마스킹 값은 변경 금지
            "NORMAL": "new",
            "REMOVE_ME": "",
            "ADDED": "ok",
        },
        environ,
    )

    content = env_path.read_text(encoding="utf-8")
    assert "GOOGLE_API_KEY=secret-value" in content
    assert "NORMAL=new" in content
    assert "REMOVE_ME=" not in content
    assert "ADDED=ok" in content
    assert environ["NORMAL"] == "new"
    assert environ["ADDED"] == "ok"


def test_reset_sensitive_env_and_user_data_clears_and_deletes(tmp_path: Path):
    env_path = tmp_path / ".env"
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    env_path.write_text(
        "GOOGLE_API_KEY=secret\nKEEP=value\nUSER_PROFILE=test\n",
        encoding="utf-8",
    )
    (data_dir / "user_quota.json").write_text("{}", encoding="utf-8")
    (data_dir / "chatbot_history.json").write_text("{}", encoding="utf-8")
    (data_dir / "chatbot_storage.db").write_text("sqlite", encoding="utf-8")
    (data_dir / "chatbot_storage.db-wal").write_text("wal", encoding="utf-8")
    (data_dir / "chatbot_storage.db-shm").write_text("shm", encoding="utf-8")

    environ: dict[str, str] = {}
    logger = types.SimpleNamespace(info=lambda *_a, **_k: None, error=lambda *_a, **_k: None)

    reset_sensitive_env_and_user_data(
        env_path=str(env_path),
        data_dir=str(data_dir),
        environ=environ,
        logger=logger,
    )

    content = env_path.read_text(encoding="utf-8")
    assert "GOOGLE_API_KEY=\n" in content
    assert "USER_PROFILE=\n" in content
    assert "KEEP=value" in content
    assert not (data_dir / "user_quota.json").exists()
    assert not (data_dir / "chatbot_history.json").exists()
    assert not (data_dir / "chatbot_storage.db").exists()
    assert not (data_dir / "chatbot_storage.db-wal").exists()
    assert not (data_dir / "chatbot_storage.db-shm").exists()
