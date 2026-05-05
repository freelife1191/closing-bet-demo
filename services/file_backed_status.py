#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""파일에 영구화되는 dict-like 상태 저장소.

gunicorn 멀티 워커 환경에서 모든 워커가 동일한 상태를 공유해야 하는
in-memory 상태(예: VCP_STATUS) 용도. JSON 파일에 atomic write로 저장하고,
fcntl 기반 파일락으로 read/write 경합을 방지한다.
"""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
from typing import Any, Iterator


class FileBackedStatus:
    """JSON 파일에 영구화되는 dict-like 상태 객체."""

    def __init__(self, file_path: str, defaults: dict[str, Any] | None = None) -> None:
        self._path = file_path
        self._defaults = dict(defaults or {})
        os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
        if not os.path.exists(file_path):
            self._write_locked(self._defaults)

    # ---- internal helpers -------------------------------------------------

    def _read_locked(self) -> dict[str, Any]:
        try:
            with open(self._path, "r", encoding="utf-8") as fp:
                fcntl.flock(fp.fileno(), fcntl.LOCK_SH)
                try:
                    raw = fp.read() or "{}"
                finally:
                    fcntl.flock(fp.fileno(), fcntl.LOCK_UN)
            data = json.loads(raw)
            if not isinstance(data, dict):
                return dict(self._defaults)
            merged = dict(self._defaults)
            merged.update(data)
            return merged
        except FileNotFoundError:
            return dict(self._defaults)
        except (json.JSONDecodeError, OSError):
            return dict(self._defaults)

    def _write_locked(self, data: dict[str, Any]) -> None:
        target_dir = os.path.dirname(self._path) or "."
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=target_dir, delete=False
        ) as tmp_fp:
            fcntl.flock(tmp_fp.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(data, tmp_fp, ensure_ascii=False)
                tmp_fp.flush()
                os.fsync(tmp_fp.fileno())
            finally:
                fcntl.flock(tmp_fp.fileno(), fcntl.LOCK_UN)
            tmp_path = tmp_fp.name
        os.replace(tmp_path, self._path)

    # ---- dict-like API ----------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        return self._read_locked().get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self._read_locked()[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.update({key: value})

    def __delitem__(self, key: str) -> None:
        lock_path = self._path + ".lock"
        with open(lock_path, "a+") as lock_fp:
            fcntl.flock(lock_fp.fileno(), fcntl.LOCK_EX)
            try:
                merged = self._read_locked()
                merged.pop(key, None)
                self._write_locked(merged)
            finally:
                fcntl.flock(lock_fp.fileno(), fcntl.LOCK_UN)

    def __contains__(self, key: object) -> bool:
        return key in self._read_locked()

    def __iter__(self) -> Iterator[str]:
        return iter(self._read_locked())

    def __len__(self) -> int:
        return len(self._read_locked())

    def keys(self):
        return self._read_locked().keys()

    def items(self):
        return self._read_locked().items()

    def values(self):
        return self._read_locked().values()

    def update(self, *args: Any, **kwargs: Any) -> None:
        # 단일 update 안에서 read-modify-write를 직렬화하기 위해 잠금 파일을 사용한다.
        lock_path = self._path + ".lock"
        with open(lock_path, "a+") as lock_fp:
            fcntl.flock(lock_fp.fileno(), fcntl.LOCK_EX)
            try:
                merged = self._read_locked()
                if args:
                    other = args[0]
                    if hasattr(other, "items"):
                        for k, v in other.items():
                            merged[k] = v
                    else:
                        for k, v in other:
                            merged[k] = v
                merged.update(kwargs)
                self._write_locked(merged)
            finally:
                fcntl.flock(lock_fp.fileno(), fcntl.LOCK_UN)


__all__ = ["FileBackedStatus"]
