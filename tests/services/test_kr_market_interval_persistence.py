#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Market Gate 주기 .env 영속화 회귀 테스트."""

from __future__ import annotations

import errno
import os
import stat
import threading
from pathlib import Path

import pytest
from dotenv import dotenv_values

from services import common_env_service, kr_market_interval_service
from services.common_env_service import resolve_env_path, update_env_file
from services.kr_market_data_cache_core import atomic_write_text
from services.kr_market_interval_service import persist_market_gate_interval_to_env


def _persist(
    env_path: Path,
    interval: int,
    applied: list[int],
    *,
    atomic_writer=atomic_write_text,
) -> None:
    persist_market_gate_interval_to_env(
        interval=interval,
        env_path=str(env_path),
        atomic_write_text=atomic_writer,
        apply_interval_fn=applied.append,
    )


def test_persist_normalizes_only_target_key_and_keeps_non_target_bindings(tmp_path: Path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "# keep this comment\n"
        "export MARKET_GATE_UPDATE_INTERVAL_MINUTES = \"30\"\n"
        "MARKET_GATE_UPDATE_INTERVAL_MINUTES=45\n"
        "MARKET_GATE_UPDATE_INTERVAL_MINUTES_EXTRA=unchanged\n"
        "OTHER_SETTING='quoted value'\n",
        encoding="utf-8",
    )
    applied: list[int] = []

    _persist(env_path, 15, applied)

    content = env_path.read_text(encoding="utf-8")
    assert content == (
        "# keep this comment\n"
        "MARKET_GATE_UPDATE_INTERVAL_MINUTES=15\n"
        "MARKET_GATE_UPDATE_INTERVAL_MINUTES_EXTRA=unchanged\n"
        "OTHER_SETTING='quoted value'\n"
    )
    assert dotenv_values(env_path)["MARKET_GATE_UPDATE_INTERVAL_MINUTES"] == "15"
    assert applied == [15]
    assert stat.S_IMODE(env_path.stat().st_mode) == 0o600


@pytest.mark.parametrize(
    ("initial", "expected"),
    [
        ("SMTP_HOST=mail.example.com\n", "SMTP_HOST=mail.example.com\nMARKET_GATE_UPDATE_INTERVAL_MINUTES=15\n"),
        ("SMTP_HOST=mail.example.com", "SMTP_HOST=mail.example.com\nMARKET_GATE_UPDATE_INTERVAL_MINUTES=15\n"),
        ("", "MARKET_GATE_UPDATE_INTERVAL_MINUTES=15\n"),
    ],
)
def test_persist_adds_target_to_missing_or_empty_env(
    tmp_path: Path, initial: str, expected: str
):
    env_path = tmp_path / ".env"
    env_path.write_text(initial, encoding="utf-8")
    applied: list[int] = []

    _persist(env_path, 15, applied)

    assert env_path.read_text(encoding="utf-8") == expected
    assert applied == [15]


def test_persist_creates_missing_env_file_with_interval_and_narrow_mode(tmp_path: Path):
    env_path = tmp_path / ".env"
    applied: list[int] = []

    _persist(env_path, 15, applied)

    assert dotenv_values(env_path)["MARKET_GATE_UPDATE_INTERVAL_MINUTES"] == "15"
    assert stat.S_IMODE(env_path.stat().st_mode) == 0o600
    assert applied == [15]


def test_persist_keeps_multiline_and_crlf_non_target_bytes(tmp_path: Path):
    env_path = tmp_path / ".env"
    original = (
        b'# preserved comment\r\n'
        b'MULTILINE="first line\r\nMARKET_GATE_UPDATE_INTERVAL_MINUTES=999\r\nsecond line"\r\n'
        b'export MARKET_GATE_UPDATE_INTERVAL_MINUTES = "30"\r\n'
        b'OTHER_VALUE=unchanged\r\n'
    )
    env_path.write_bytes(original)

    _persist(env_path, 15, [])

    content = env_path.read_bytes()
    assert (
        b'# preserved comment\r\n'
        b'MULTILINE="first line\r\n'
        b'MARKET_GATE_UPDATE_INTERVAL_MINUTES=999\r\n'
        b'second line"\r\n'
    ) in content
    assert b'OTHER_VALUE=unchanged\r\n' in content
    assert b'MARKET_GATE_UPDATE_INTERVAL_MINUTES=15\n' in content
    assert b'export MARKET_GATE_UPDATE_INTERVAL_MINUTES' not in content


def test_persist_rejects_invalid_env_syntax_before_file_or_runtime_change(tmp_path: Path):
    env_path = tmp_path / ".env"
    original = b'KEEP=value\nBROKEN="unterminated\n'
    env_path.write_bytes(original)
    applied: list[int] = []

    with pytest.raises(ValueError, match="Invalid environment file syntax"):
        _persist(env_path, 15, applied)

    assert env_path.read_bytes() == original
    assert applied == []


@pytest.mark.parametrize("link_name", [".env", ".env.lock"])
def test_persist_refuses_env_or_lock_symlink_without_touching_target(
    tmp_path: Path, link_name: str
):
    env_path = tmp_path / ".env"
    victim = tmp_path / "victim.txt"
    victim.write_text("MARKET_GATE_UPDATE_INTERVAL_MINUTES=30\n", encoding="utf-8")
    if link_name == ".env":
        env_path.symlink_to(victim)
    else:
        env_path.write_text("MARKET_GATE_UPDATE_INTERVAL_MINUTES=30\n", encoding="utf-8")
        (tmp_path / ".env.lock").symlink_to(victim)
    original_env = None if link_name == ".env" else env_path.read_bytes()
    applied: list[int] = []

    with pytest.raises(OSError) as raised:
        _persist(env_path, 15, applied)

    assert raised.value.errno == errno.ELOOP
    assert victim.read_text(encoding="utf-8") == "MARKET_GATE_UPDATE_INTERVAL_MINUTES=30\n"
    if original_env is None:
        assert env_path.is_symlink()
    else:
        assert env_path.read_bytes() == original_env
    assert applied == []


def test_persist_replace_failure_keeps_file_and_runtime_and_removes_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    env_path = tmp_path / ".env"
    original = "MARKET_GATE_UPDATE_INTERVAL_MINUTES=30\nSMTP_HOST=old\n"
    env_path.write_text(original, encoding="utf-8")
    applied: list[int] = []

    import services.kr_market_data_cache_core as cache_core

    def _replace_fails(_source: str, _destination: str) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(cache_core.os, "replace", _replace_fails)

    with pytest.raises(OSError, match="replace failed"):
        _persist(env_path, 15, applied)

    assert env_path.read_text(encoding="utf-8") == original
    assert applied == []
    assert sorted(path.name for path in tmp_path.iterdir()) == [".env", ".env.lock"]


def test_persist_reader_failure_does_not_write_or_apply(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    env_path = tmp_path / ".env"
    original = "MARKET_GATE_UPDATE_INTERVAL_MINUTES=30\n"
    env_path.write_text(original, encoding="utf-8")
    applied: list[int] = []

    def _read_fails(_env_path: str) -> list[str]:
        raise OSError("read failed")

    monkeypatch.setattr(kr_market_interval_service, "_read_env_lines", _read_fails)

    with pytest.raises(OSError, match="read failed"):
        _persist(env_path, 15, applied)

    assert env_path.read_text(encoding="utf-8") == original
    assert applied == []


def test_persist_callback_failure_keeps_new_file_and_releases_lock_for_retry(tmp_path: Path):
    env_path = tmp_path / ".env"
    env_path.write_text("MARKET_GATE_UPDATE_INTERVAL_MINUTES=30\n", encoding="utf-8")

    def _apply_fails(_interval: int) -> None:
        raise RuntimeError("scheduler unavailable")

    with pytest.raises(RuntimeError, match="scheduler unavailable"):
        persist_market_gate_interval_to_env(
            interval=15,
            env_path=str(env_path),
            atomic_write_text=atomic_write_text,
            apply_interval_fn=_apply_fails,
        )

    assert dotenv_values(env_path)["MARKET_GATE_UPDATE_INTERVAL_MINUTES"] == "15"
    applied: list[int] = []
    _persist(env_path, 20, applied)
    assert dotenv_values(env_path)["MARKET_GATE_UPDATE_INTERVAL_MINUTES"] == "20"
    assert applied == [20]


def test_interval_and_common_env_updates_keep_both_changes_during_contention(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "MARKET_GATE_UPDATE_INTERVAL_MINUTES=30\nSMTP_HOST=old\n",
        encoding="utf-8",
    )
    first_write_started = threading.Event()
    allow_first_write = threading.Event()
    common_attempted = threading.Event()
    common_read = threading.Event()
    errors: list[BaseException] = []
    applied: list[int] = []
    original_common_reader = common_env_service._read_env_lines

    def _slow_atomic_write(path: str, content: str) -> None:
        first_write_started.set()
        assert allow_first_write.wait(timeout=5), "공통 저장 경합을 기다리지 못했다"
        atomic_write_text(path, content)

    def _persist_interval() -> None:
        try:
            _persist(env_path, 15, applied, atomic_writer=_slow_atomic_write)
        except BaseException as error:  # noqa: BLE001 - 스레드 오류를 주 스레드로 전달한다.
            errors.append(error)

    def _update_common_env() -> None:
        try:
            common_attempted.set()
            update_env_file(str(env_path), {"SMTP_HOST": "new"}, {})
        except BaseException as error:  # noqa: BLE001 - 스레드 오류를 주 스레드로 전달한다.
            errors.append(error)

    def _observe_common_reader(path: str) -> list[str]:
        common_read.set()
        return original_common_reader(path)

    monkeypatch.setattr(common_env_service, "_read_env_lines", _observe_common_reader)

    interval_thread = threading.Thread(target=_persist_interval, daemon=True)
    common_thread = threading.Thread(target=_update_common_env, daemon=True)
    common_started = False
    interval_thread.start()
    try:
        assert first_write_started.wait(timeout=5), "주기 저장이 쓰기 단계에 도달하지 못했다"
        common_thread.start()
        common_started = True
        assert common_attempted.wait(timeout=5), "공통 저장 요청이 시작되지 않았다"
        assert not common_read.wait(timeout=0.2), "공통 저장이 주기 적용 전 파일을 읽었다"
    finally:
        allow_first_write.set()
        interval_thread.join(timeout=5)
        if common_started:
            common_thread.join(timeout=5)

    assert not interval_thread.is_alive()
    assert not common_thread.is_alive()
    assert errors == []
    assert dotenv_values(env_path)["MARKET_GATE_UPDATE_INTERVAL_MINUTES"] == "15"
    assert dotenv_values(env_path)["SMTP_HOST"] == "new"
    assert applied == [15]


def test_interval_apply_callback_runs_while_shared_env_lock_is_held(tmp_path: Path):
    env_path = tmp_path / ".env"
    env_path.write_text("MARKET_GATE_UPDATE_INTERVAL_MINUTES=30\n", encoding="utf-8")
    first_apply_started = threading.Event()
    release_first_apply = threading.Event()
    second_apply_started = threading.Event()
    errors: list[BaseException] = []

    def _first_apply(_interval: int) -> None:
        first_apply_started.set()
        assert release_first_apply.wait(timeout=5), "두 번째 요청이 잠금 대기를 확인하지 못했다"

    def _run_first() -> None:
        try:
            persist_market_gate_interval_to_env(
                interval=15,
                env_path=str(env_path),
                atomic_write_text=atomic_write_text,
                apply_interval_fn=_first_apply,
            )
        except BaseException as error:  # noqa: BLE001 - 스레드 오류를 주 스레드로 전달한다.
            errors.append(error)

    def _run_second() -> None:
        try:
            persist_market_gate_interval_to_env(
                interval=20,
                env_path=str(env_path),
                atomic_write_text=atomic_write_text,
                apply_interval_fn=lambda _interval: second_apply_started.set(),
            )
        except BaseException as error:  # noqa: BLE001 - 스레드 오류를 주 스레드로 전달한다.
            errors.append(error)

    first_thread = threading.Thread(target=_run_first, daemon=True)
    second_thread = threading.Thread(target=_run_second, daemon=True)
    second_started = False
    first_thread.start()
    try:
        assert first_apply_started.wait(timeout=5), "첫 callback이 시작되지 않았다"
        second_thread.start()
        second_started = True
        assert not second_apply_started.wait(timeout=0.2), "callback 전에 잠금이 풀렸다"
    finally:
        release_first_apply.set()
        first_thread.join(timeout=5)
        if second_started:
            second_thread.join(timeout=5)

    assert not first_thread.is_alive()
    assert not second_thread.is_alive()
    assert errors == []
    assert dotenv_values(env_path)["MARKET_GATE_UPDATE_INTERVAL_MINUTES"] == "20"


def test_route_and_common_env_resolvers_point_to_same_absolute_env_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    from app.routes import kr_market

    monkeypatch.setattr(common_env_service, "resolve_project_root", lambda: str(tmp_path))

    common_path = resolve_env_path()
    route_path = kr_market._project_env_path()
    assert os.path.isabs(common_path)
    assert common_path == route_path == str(tmp_path / ".env")
