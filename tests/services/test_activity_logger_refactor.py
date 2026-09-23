#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
활동 로그 보관 기간·권한·다중 워커 회전 회귀 테스트 ([FE-046])
"""

from __future__ import annotations

import logging
import os
import stat
import time
from pathlib import Path

from services.activity_logger import ActivityLogger, RetentionTimedRotatingFileHandler


def _touch(path: Path, days_ago: float) -> None:
    path.write_text("x\n", encoding="utf-8")
    ts = time.time() - days_ago * 86_400
    os.utime(path, (ts, ts))


def _handler(base: Path) -> RetentionTimedRotatingFileHandler:
    return RetentionTimedRotatingFileHandler(str(base), when="midnight", encoding="utf-8")


def _mode(path: Path) -> int:
    return stat.S_IMODE(os.stat(path).st_mode)


def _emit(handler: logging.Handler, message: str) -> None:
    handler.emit(logging.makeLogRecord({"msg": message}))


def test_prune_uses_mtime_not_the_date_in_the_name(tmp_path: Path):
    old = tmp_path / "user_activity.log.2026-09-20"  # 이름은 최근, 수정 시각은 31일 전
    young = tmp_path / "user_activity.log.2026-01-01"  # 이름은 오래됨, 수정 시각은 29일 전
    other = tmp_path / "other.log.2026-01-01"
    _touch(old, 31)
    _touch(young, 29)
    _touch(other, 400)
    handler = _handler(tmp_path / "user_activity.log")
    try:
        handler.prune_expired()
    finally:
        handler.close()
    assert not old.exists()
    assert young.exists() and other.exists()


def test_prune_expired_narrows_surviving_rotated_files(tmp_path: Path):
    young = tmp_path / "user_activity.log.2026-09-20"
    _touch(young, 2)
    os.chmod(young, 0o644)
    handler = _handler(tmp_path / "user_activity.log")
    try:
        handler.prune_expired()
    finally:
        handler.close()
    assert _mode(young) == 0o600


def test_base_file_is_opened_as_0600(tmp_path: Path):
    base = tmp_path / "user_activity.log"
    base.write_text("", encoding="utf-8")
    os.chmod(base, 0o644)
    _handler(base).close()
    assert _mode(base) == 0o600


def test_rollover_deletes_expired_files_and_reopens_as_0600(tmp_path: Path):
    base = tmp_path / "user_activity.log"
    old = tmp_path / "user_activity.log.2026-02-22"
    _touch(old, 200)
    handler = _handler(base)
    try:
        handler.rolloverAt = time.time() - 1
        _emit(handler, "after-midnight")
    finally:
        handler.close()
    assert not old.exists()
    assert _mode(base) == 0o600
    assert "after-midnight" in base.read_text(encoding="utf-8")


def test_late_worker_writes_to_new_base_after_other_worker_rotated(tmp_path: Path):
    # 워커 두 개를 핸들러 두 개로 흉내 낸다. A 가 먼저 회전하면 표준 구현의 B 는
    # 「이미 회전됨」으로 돌아가 날짜가 붙은 어제 파일에 계속 쓴다.
    base = tmp_path / "user_activity.log"
    a, b = _handler(base), _handler(base)
    try:
        _emit(a, "a-day1")
        _emit(b, "b-day1")
        a.rolloverAt = b.rolloverAt = time.time() - 1
        _emit(a, "a-day2")
        _emit(b, "b-day2")
        _emit(b, "b-day2-again")
    finally:
        a.close()
        b.close()
    today = base.read_text(encoding="utf-8")
    assert "b-day2\n" in today and "b-day2-again" in today
    assert b.rolloverAt > time.time()


def test_activity_logger_prunes_on_creation(tmp_path: Path, monkeypatch):
    user_logger = logging.getLogger("user_activity")
    monkeypatch.setattr(user_logger, "handlers", [])
    old = tmp_path / "user_activity.log.2026-02-22"
    _touch(old, 200)
    try:
        ActivityLogger(log_dir=str(tmp_path))
    finally:
        for handler in list(user_logger.handlers):
            handler.close()
    assert not old.exists()


def test_activity_logger_rotates_and_prunes_a_stale_base_file_on_creation(tmp_path: Path, monkeypatch):
    # GET 은 활동 로그에 남지 않으므로 30일 넘게 기록이 없을 수 있다. 그 기준 파일도
    # 다음 기록을 기다리지 않고 기동 때 지워져야 방침 3항과 맞는다.
    user_logger = logging.getLogger("user_activity")
    monkeypatch.setattr(user_logger, "handlers", [])
    base = tmp_path / "user_activity.log"
    base.write_text("stale-record\n", encoding="utf-8")
    ts = time.time() - 40 * 86_400
    os.utime(base, (ts, ts))
    try:
        ActivityLogger(log_dir=str(tmp_path))
    finally:
        for handler in list(user_logger.handlers):
            handler.close()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["user_activity.log"]
    assert "stale-record" not in base.read_text(encoding="utf-8")


def test_rotate_never_overwrites_a_file_another_worker_already_rotated(tmp_path: Path):
    # 두 워커가 동시에 「아직 회전 전」으로 판정해도 늦은 쪽이 먼저 만든 날짜 파일을
    # 새 기준 파일로 덮어써 전날 기록을 잃지 않아야 한다.
    base = tmp_path / "user_activity.log"
    dated = tmp_path / "user_activity.log.2026-09-22"
    dated.write_text("yesterday\n", encoding="utf-8")
    base.write_text("", encoding="utf-8")
    handler = _handler(base)
    try:
        handler.rotate(str(base), str(dated))
    finally:
        handler.close()
    assert dated.read_text(encoding="utf-8") == "yesterday\n"
    assert base.exists()


def test_rotate_tolerates_a_source_another_worker_already_moved(tmp_path: Path):
    # 다른 워커가 link·unlink 를 마친 직후라 기준 파일이 없어도 예외 없이 지나가야 한다.
    # 예외가 기동 중에 나면 그 워커는 수명 내내 활동 로그를 남기지 못한다.
    base = tmp_path / "user_activity.log"
    handler = _handler(base)
    try:
        base.unlink()
        handler.rotate(str(base), str(tmp_path / "user_activity.log.2026-09-22"))
    finally:
        handler.close()
