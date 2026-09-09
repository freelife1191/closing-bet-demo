#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""INFRA-058: 파일에 없어도 명시적 삭제를 저장 성공 후 워커에 적용한다."""

import pytest

from services import common_env_service


@pytest.mark.parametrize("file_exists", [True, False])
def test_empty_value_removes_absent_key_from_worker(tmp_path, file_exists):
    path = tmp_path / ".env"
    if file_exists:
        path.write_text("SMTP_PORT=587\n")
    environ = {"SMTP_USER": "stale@example.test", "OTHER": "keep"}
    common_env_service.update_env_file(str(path), {"SMTP_USER": ""}, environ)
    assert "SMTP_USER" not in environ
    assert environ["OTHER"] == "keep"
    assert "SMTP_USER" not in path.read_text()


def test_failed_write_preserves_absent_key_in_worker(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text("SMTP_PORT=587\n")
    environ = {"SMTP_USER": "stale@example.test"}

    def fail_write(*args):
        raise OSError("synthetic failure")

    monkeypatch.setattr(common_env_service, "atomic_write_text", fail_write)
    with pytest.raises(OSError):
        common_env_service.update_env_file(str(path), {"SMTP_USER": ""}, environ)
    assert environ == {"SMTP_USER": "stale@example.test"}
    assert path.read_text() == "SMTP_PORT=587\n"
