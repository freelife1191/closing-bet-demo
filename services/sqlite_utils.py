#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQLite 공통 연결 유틸.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
import re
import sqlite3
import threading
import time
from typing import Callable, Iterable, TypeVar
from urllib.parse import parse_qsl, unquote, urlparse


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
_SQLITE_PRAGMA_ASSIGNMENT_PATTERN = re.compile(
    r"^\s*PRAGMA\s+([A-Za-z_][A-Za-z0-9_]*)\s*=",
    re.IGNORECASE,
)
_SQLITE_TRANSIENT_ERROR_MARKERS: tuple[str, ...] = (
    "database is locked",
    "database schema is locked",
    "database table is locked",
    "database is busy",
    "locking protocol",
)
_SQLITE_PERSISTENT_PRAGMA_NAMES = frozenset({"journal_mode", "synchronous"})
_SQLITE_PERSISTENT_PRAGMAS_LOCK = threading.Lock()

_T = TypeVar("_T")


@dataclass
class _SQLitePersistentPragmaState:
    applied_pragmas: set[str] = field(default_factory=set)
    file_signature: tuple[int, int] | None = None


_SQLITE_PERSISTENT_PRAGMAS_READY: dict[str, _SQLitePersistentPragmaState] = {}


def _extract_sqlite_filesystem_path_from_uri(db_uri: str) -> str | None:
    normalized_uri = str(db_uri).strip()
    if not normalized_uri.startswith("file:"):
        return None

    parsed = urlparse(normalized_uri)
    query_map = dict(parse_qsl(parsed.query, keep_blank_values=True))
    mode = str(query_map.get("mode", "")).strip().lower()
    if mode == "memory":
        return None

    raw_path = parsed.path or ""
    if not raw_path:
        raw_path = normalized_uri[len("file:") :].split("?", 1)[0]
    if parsed.netloc and parsed.netloc not in {"", "localhost"}:
        raw_path = f"//{parsed.netloc}{raw_path}"

    normalized_path = unquote(raw_path).strip()
    if not normalized_path or normalized_path == ":memory:":
        return None
    return normalized_path


def _resolve_sqlite_filesystem_path(db_path: str) -> str | None:
    normalized_path = str(db_path).strip()
    if not normalized_path:
        return None
    if normalized_path == ":memory:":
        return None
    if normalized_path.startswith("file:"):
        return _extract_sqlite_filesystem_path_from_uri(normalized_path)
    return normalized_path


def normalize_sqlite_db_key(db_path: str) -> str:
    """
    SQLite DB 식별용 key를 canonical path 기준으로 정규화한다.
    file URI가 실제 파일을 가리키면 파일 경로 기준 key를 반환한다.
    """
    resolved_path = _resolve_sqlite_filesystem_path(db_path)
    if resolved_path is None:
        return str(db_path).strip()
    return os.path.realpath(os.path.expanduser(str(resolved_path)))


def _normalize_sqlite_filesystem_key(db_path: str) -> str | None:
    resolved_path = _resolve_sqlite_filesystem_path(db_path)
    if resolved_path is None:
        return None
    return os.path.realpath(os.path.expanduser(str(resolved_path)))


def _load_sqlite_file_signature(db_key: str) -> tuple[int, int] | None:
    try:
        stat_result = os.stat(db_key)
    except OSError:
        return None
    return (int(stat_result.st_dev), int(stat_result.st_ino))


def sqlite_db_path_exists(db_path: str) -> bool:
    resolved_path = _resolve_sqlite_filesystem_path(db_path)
    if resolved_path is None:
        normalized_path = str(db_path).strip()
        return normalized_path in {":memory:"} or normalized_path.startswith("file:")
    return os.path.exists(
        os.path.realpath(os.path.expanduser(str(resolved_path))),
    )


def is_sqlite_transient_error(error: Exception) -> bool:
    if not isinstance(error, sqlite3.OperationalError):
        return False
    lowered = str(error).lower()
    return any(marker in lowered for marker in _SQLITE_TRANSIENT_ERROR_MARKERS)


def is_sqlite_missing_table_error(
    error: Exception,
    *,
    table_names: str | Iterable[str] | None = None,
) -> bool:
    """
    SQLite no such table 오류인지 판별한다.
    table_names가 주어지면 메시지에 해당 테이블명이 포함된 경우만 True를 반환한다.
    """
    if not isinstance(error, sqlite3.OperationalError):
        return False

    message = str(error).lower()
    if "no such table" not in message:
        return False

    if table_names is None:
        return True

    if isinstance(table_names, str):
        normalized_table_names = (table_names.strip().lower(),)
    else:
        normalized_table_names = tuple(
            str(name).strip().lower()
            for name in table_names
            if str(name).strip()
        )

    if not normalized_table_names:
        return True
    return any(table_name in message for table_name in normalized_table_names)


def run_sqlite_with_retry(
    operation: Callable[[], _T],
    *,
    max_retries: int = 2,
    retry_delay_seconds: float = 0.05,
    should_retry: Callable[[Exception], bool] | None = None,
) -> _T:
    """
    SQLite transient lock 오류에 대해 짧은 backoff로 재시도한다.
    """
    normalized_retries = max(0, int(max_retries))
    normalized_delay = max(0.0, float(retry_delay_seconds))
    retry_decider = should_retry or is_sqlite_transient_error

    attempt = 0
    while True:
        try:
            return operation()
        except Exception as error:
            if attempt >= normalized_retries or not retry_decider(error):
                raise
            attempt += 1
            if normalized_delay > 0:
                time.sleep(normalized_delay * attempt)


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


def _extract_pragma_name(pragma_sql: str) -> str | None:
    match = _SQLITE_PRAGMA_ASSIGNMENT_PATTERN.match(str(pragma_sql).strip())
    if match is None:
        return None
    return str(match.group(1)).strip().lower()


def _is_persistent_pragma(pragma_sql: str) -> bool:
    pragma_name = _extract_pragma_name(pragma_sql)
    return bool(pragma_name) and pragma_name in _SQLITE_PERSISTENT_PRAGMA_NAMES


def _compute_pending_persistent_pragmas(
    db_key: str | None,
    persistent_pragmas: Iterable[str],
) -> set[str]:
    normalized_persistent_pragmas = {
        str(pragma_sql).strip()
        for pragma_sql in persistent_pragmas
        if str(pragma_sql).strip()
    }
    if db_key is None or not normalized_persistent_pragmas:
        return normalized_persistent_pragmas

    current_signature = _load_sqlite_file_signature(db_key)
    with _SQLITE_PERSISTENT_PRAGMAS_LOCK:
        state = _SQLITE_PERSISTENT_PRAGMAS_READY.get(db_key)
        if state is None:
            state = _SQLitePersistentPragmaState(file_signature=current_signature)
            _SQLITE_PERSISTENT_PRAGMAS_READY[db_key] = state
        elif state.file_signature != current_signature:
            state.applied_pragmas.clear()
            state.file_signature = current_signature
        return normalized_persistent_pragmas - state.applied_pragmas


def _mark_persistent_pragmas_applied(
    db_key: str | None,
    applied_pragmas: Iterable[str],
) -> None:
    normalized_applied_pragmas = {
        str(pragma_sql).strip()
        for pragma_sql in applied_pragmas
        if str(pragma_sql).strip()
    }
    if db_key is None or not normalized_applied_pragmas:
        return

    current_signature = _load_sqlite_file_signature(db_key)
    with _SQLITE_PERSISTENT_PRAGMAS_LOCK:
        state = _SQLITE_PERSISTENT_PRAGMAS_READY.get(db_key)
        if state is None:
            state = _SQLitePersistentPragmaState(file_signature=current_signature)
            _SQLITE_PERSISTENT_PRAGMAS_READY[db_key] = state
        elif state.file_signature != current_signature:
            state.applied_pragmas.clear()
            state.file_signature = current_signature
        state.applied_pragmas.update(normalized_applied_pragmas)


def _ensure_sqlite_parent_dir(db_path: str) -> None:
    resolved_path = _resolve_sqlite_filesystem_path(db_path)
    if resolved_path is None:
        return
    parent = os.path.dirname(str(resolved_path))
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
    connect_retries: int = 2,
    connect_retry_delay_seconds: float = 0.03,
) -> sqlite3.Connection:
    """Auto-closing Connection을 생성하고 지정된 PRAGMA를 적용한다."""
    normalized_path = str(db_path).strip()
    is_uri = bool(normalized_path) and normalized_path.startswith("file:")
    connect_path = normalized_path if normalized_path else db_path
    if ensure_parent_dir:
        _ensure_sqlite_parent_dir(connect_path)

    normalized_cached_statements = max(1, int(cached_statements))
    normalized_pragmas = _deduplicate_pragmas(pragmas or ())
    persistent_db_key = _normalize_sqlite_filesystem_key(connect_path)
    persistent_pragmas = {
        pragma_sql for pragma_sql in normalized_pragmas if _is_persistent_pragma(pragma_sql)
    }
    pending_persistent_pragmas = _compute_pending_persistent_pragmas(
        persistent_db_key,
        persistent_pragmas,
    )

    def _open_connection() -> sqlite3.Connection:
        conn = sqlite3.connect(
            connect_path,
            timeout=timeout_seconds,
            factory=AutoClosingSQLiteConnection,
            cached_statements=normalized_cached_statements,
            uri=is_uri,
        )
        applied_persistent_pragmas: list[str] = []
        try:
            for pragma_sql in normalized_pragmas:
                if pragma_sql in persistent_pragmas and pragma_sql not in pending_persistent_pragmas:
                    continue
                conn.execute(pragma_sql)
                if pragma_sql in persistent_pragmas:
                    applied_persistent_pragmas.append(pragma_sql)
        except Exception:
            conn.close()
            raise
        if applied_persistent_pragmas:
            _mark_persistent_pragmas_applied(
                persistent_db_key,
                applied_persistent_pragmas,
            )
        return conn

    return run_sqlite_with_retry(
        _open_connection,
        max_retries=connect_retries,
        retry_delay_seconds=connect_retry_delay_seconds,
    )
