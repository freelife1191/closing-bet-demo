#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQLite 공통 연결 유틸.
"""

from __future__ import annotations

import os
import re
import sqlite3
import threading
from typing import Iterable


class AutoClosingSQLiteConnection(sqlite3.Connection):
    """with 블록 종료 시 커밋/롤백 후 연결을 닫는 SQLite Connection."""

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            return super().__exit__(exc_type, exc_val, exc_tb)
        finally:
            self.close()


SQLITE_BALANCED_PRAGMAS: tuple[str, ...] = (
    "PRAGMA journal_mode=WAL",
    "PRAGMA synchronous=NORMAL",
    "PRAGMA temp_store=MEMORY",
    "PRAGMA cache_size=-8000",
)
_SQLITE_PARENT_DIRS_LOCK = threading.Lock()
_SQLITE_PARENT_DIRS_READY: set[str] = set()
_SQLITE_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _deduplicate_pragmas(pragmas: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    deduplicated: list[str] = []
    for pragma_sql in pragmas:
        normalized = str(pragma_sql).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduplicated.append(normalized)
    return tuple(deduplicated)


def _ensure_sqlite_parent_dir(db_path: str) -> None:
    if not db_path:
        return
    normalized_path = str(db_path).strip()
    if not normalized_path or normalized_path == ":memory:" or normalized_path.startswith("file:"):
        return
    parent = os.path.dirname(normalized_path)
    if parent:
        parent_key = os.path.realpath(os.path.expanduser(parent))
        with _SQLITE_PARENT_DIRS_LOCK:
            if parent_key in _SQLITE_PARENT_DIRS_READY:
                if os.path.isdir(parent_key):
                    return
                _SQLITE_PARENT_DIRS_READY.discard(parent_key)
            if os.path.isdir(parent_key):
                _SQLITE_PARENT_DIRS_READY.add(parent_key)
                return
            os.makedirs(parent_key, exist_ok=True)
            _SQLITE_PARENT_DIRS_READY.add(parent_key)


def _normalize_sqlite_identifier(identifier: str, *, label: str) -> str:
    normalized = str(identifier).strip()
    if not normalized or _SQLITE_IDENTIFIER_PATTERN.fullmatch(normalized) is None:
        raise ValueError(f"Invalid SQLite identifier for {label}: {identifier!r}")
    return normalized


def prune_rows_by_updated_at_if_needed(
    cursor: sqlite3.Cursor,
    *,
    table_name: str,
    max_rows: int,
    updated_at_column: str = "updated_at",
) -> bool:
    """
    updated_at DESC 기준으로 max_rows를 초과하는 오래된 row를 삭제한다.
    초과 여부는 COUNT(*) 대신 LIMIT/OFFSET sentinel 조회로 판별한다.
    """
    normalized_max_rows = max(1, int(max_rows))
    normalized_table_name = _normalize_sqlite_identifier(
        table_name,
        label="table_name",
    )
    normalized_updated_at_column = _normalize_sqlite_identifier(
        updated_at_column,
        label="updated_at_column",
    )
    marker_row = cursor.execute(
        f"""
        SELECT rowid
        FROM {normalized_table_name}
        ORDER BY {normalized_updated_at_column} DESC
        LIMIT 1 OFFSET ?
        """,
        (normalized_max_rows,),
    ).fetchone()
    if marker_row is None:
        return False

    cursor.execute(
        f"""
        DELETE FROM {normalized_table_name}
        WHERE rowid IN (
            SELECT rowid
            FROM {normalized_table_name}
            ORDER BY {normalized_updated_at_column} DESC
            LIMIT -1 OFFSET ?
        )
        """,
        (normalized_max_rows,),
    )
    return True


def build_sqlite_pragmas(
    *,
    busy_timeout_ms: int | None = None,
    include_foreign_keys: bool = False,
    base_pragmas: Iterable[str] = SQLITE_BALANCED_PRAGMAS,
    extra_pragmas: Iterable[str] | None = None,
) -> tuple[str, ...]:
    """공통 SQLite PRAGMA 조합을 생성한다."""
    pragmas: list[str] = [str(item).strip() for item in base_pragmas]
    if busy_timeout_ms is not None:
        pragmas.append(f"PRAGMA busy_timeout={int(busy_timeout_ms)}")
    if include_foreign_keys:
        pragmas.append("PRAGMA foreign_keys=ON")
    if extra_pragmas:
        pragmas.extend(str(item).strip() for item in extra_pragmas)
    return _deduplicate_pragmas(pragmas)


def connect_sqlite(
    db_path: str,
    *,
    timeout_seconds: float = 5.0,
    pragmas: Iterable[str] | None = None,
    cached_statements: int = 256,
    ensure_parent_dir: bool = True,
) -> sqlite3.Connection:
    """Auto-closing Connection을 생성하고 지정된 PRAGMA를 적용한다."""
    normalized_path = str(db_path).strip()
    is_uri = bool(normalized_path) and normalized_path.startswith("file:")
    if ensure_parent_dir:
        _ensure_sqlite_parent_dir(db_path)

    conn = sqlite3.connect(
        db_path,
        timeout=timeout_seconds,
        factory=AutoClosingSQLiteConnection,
        cached_statements=max(1, int(cached_statements)),
        uri=is_uri,
    )
    try:
        for pragma_sql in pragmas or ():
            conn.execute(pragma_sql)
    except Exception:
        conn.close()
        raise
    return conn
