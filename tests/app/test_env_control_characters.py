#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""INFRA-057: 저장한 값의 dotenv 재적재에서 제어문자가 생기지 않는다."""

from io import StringIO

import pytest
from dotenv import dotenv_values

from services.common_env_service import update_env_file


UNSAFE_VALUES = [f"a{chr(code)}b" for code in [*range(32), 127]] + [
    '"a' + chr(92) + escape + 'b"' for escape in "abfnrtv"
]


@pytest.mark.parametrize("value", UNSAFE_VALUES)
@pytest.mark.parametrize("existing", [True, False])
def test_control_characters_are_rejected_without_file_or_memory_change(tmp_path, value, existing):
    path = tmp_path / ".env"
    original = "SMTP_USER=old\n" if existing else "SMTP_PORT=587\n"
    path.write_text(original)
    environ = {"SMTP_USER": "old"}
    update_env_file(str(path), {"SMTP_USER": value}, environ)
    assert path.read_text() == original
    assert environ == {"SMTP_USER": "old"}
    assert dotenv_values(stream=StringIO(path.read_text())).get("SMTP_USER") == ("old" if existing else None)


@pytest.mark.parametrize("value", ["pass!word$", "has$!bang", "abcd efgh ijkl mnop"])
def test_existing_safe_passwords_survive_save_and_reload(tmp_path, value):
    path = tmp_path / ".env"
    environ = {}
    update_env_file(str(path), {"SMTP_PASSWORD": value}, environ)
    assert environ["SMTP_PASSWORD"] == value
    assert dotenv_values(str(path))["SMTP_PASSWORD"] == value
