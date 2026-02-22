#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQLite 공통 연결 유틸.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
import os
import re
import sqlite3
import threading
import time
from typing import Callable, Iterable, TypeVar
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlparse


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
_SQLITE_PARENT_DIRS_READY: OrderedDict[str, None] = OrderedDict()
_SQLITE_PARENT_DIRS_MAX_ENTRIES = 2_048
_SQLITE_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SQLITE_PRAGMA_ASSIGNMENT_PATTERN = re.compile(
    r"^\s*PRAGMA\s+([A-Za-z_][A-Za-z0-9_]*)\s*=",
    re.IGNORECASE,
)
_SQLITE_TRANSIENT_ERROR_MARKERS: tuple[str, ...] = (
    "database is locked",
    "database schema is locked",
    "database schema has changed",
    "database table is locked",
    "database is busy",
    "locking protocol",
)
_SQLITE_PERSISTENT_PRAGMA_NAMES = frozenset({"journal_mode", "synchronous"})
_SQLITE_READ_ONLY_BLOCKED_PRAGMA_NAMES = frozenset({"journal_mode", "synchronous"})
_SQLITE_PERSISTENT_PRAGMAS_LOCK = threading.Lock()
_SQLITE_PERSISTENT_PRAGMAS_MAX_ENTRIES = 2_048

_T = TypeVar("_T")


@dataclass
class _SQLitePersistentPragmaState:
    applied_pragmas: set[str] = field(default_factory=set)
    file_signature: tuple[int, int] | None = None


_SQLITE_PERSISTENT_PRAGMAS_READY: OrderedDict[str, _SQLitePersistentPragmaState] = OrderedDict()


def _extract_sqlite_filesystem_path_from_uri(db_uri: str) -> str | None:
    normalized_uri = str(db_uri).strip()
    if not normalized_uri.startswith("file:"):
        return None

    parsed = urlparse(normalized_uri)
    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    if any(
        str(key).strip().lower() == "mode" and str(value).strip().lower() == "memory"
        for key, value in query_pairs
    ):
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
        # :memory: 및 mode=memory URI는 비영속 스토리지이므로 파일 존재로 간주하지 않는다.
        return False
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


def _is_read_only_blocked_pragma(pragma_sql: str) -> bool:
    pragma_name = _extract_pragma_name(pragma_sql)
    return bool(pragma_name) and pragma_name in _SQLITE_READ_ONLY_BLOCKED_PRAGMA_NAMES


def _build_read_only_sqlite_uri(db_path: str) -> tuple[str, bool]:
    normalized_path = str(db_path).strip()
    if not normalized_path or normalized_path == ":memory:":
        return db_path, False

    if normalized_path.startswith("file:"):
        uri_without_fragment, has_fragment, fragment_text = normalized_path.partition("#")
        base_uri, has_query, raw_query = uri_without_fragment.partition("?")
        raw_pairs = parse_qsl(raw_query if has_query else "", keep_blank_values=True)
        query_pairs = [(str(key), str(value)) for key, value in raw_pairs]
        parsed_uri = urlparse(uri_without_fragment)
        normalized_uri_path = str(parsed_uri.path or "").strip().lower()
        has_memory_mode = any(
            str(key).strip().lower() == "mode"
            and str(value).strip().lower() == "memory"
            for key, value in query_pairs
        )
        is_memory_file_uri = (
            normalized_uri_path == ":memory:"
            or uri_without_fragment.lower().startswith("file::memory:")
        )
        if has_memory_mode or is_memory_file_uri:
            return normalized_path, True

        normalized_pairs = [
            (key, value)
            for key, value in query_pairs
            if str(key).strip().lower() != "mode"
        ]
        normalized_pairs.append(("mode", "ro"))
        encoded_query = urlencode(normalized_pairs, doseq=True)
        read_only_uri = f"{base_uri}?{encoded_query}" if encoded_query else base_uri
        if has_fragment:
            read_only_uri = f"{read_only_uri}#{fragment_text}"
        return read_only_uri, True

    absolute_path = os.path.realpath(os.path.expanduser(normalized_path))
    quoted_path = quote(absolute_path, safe="/")
    return f"file:{quoted_path}?mode=ro", True


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
        _SQLITE_PERSISTENT_PRAGMAS_READY.move_to_end(db_key)
        _prune_persistent_pragmas_ready_locked()
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
        _SQLITE_PERSISTENT_PRAGMAS_READY.move_to_end(db_key)
        _prune_persistent_pragmas_ready_locked()


def _prune_persistent_pragmas_ready_locked() -> None:
    normalized_max_entries = max(1, int(_SQLITE_PERSISTENT_PRAGMAS_MAX_ENTRIES))
    while len(_SQLITE_PERSISTENT_PRAGMAS_READY) > normalized_max_entries:
        _SQLITE_PERSISTENT_PRAGMAS_READY.popitem(last=False)


def _mark_parent_dir_ready_locked(parent_key: str) -> None:
    _SQLITE_PARENT_DIRS_READY[parent_key] = None
    _SQLITE_PARENT_DIRS_READY.move_to_end(parent_key)
    _prune_parent_dirs_ready_locked()


def _prune_parent_dirs_ready_locked() -> None:
    normalized_max_entries = max(1, int(_SQLITE_PARENT_DIRS_MAX_ENTRIES))
    while len(_SQLITE_PARENT_DIRS_READY) > normalized_max_entries:
        _SQLITE_PARENT_DIRS_READY.popitem(last=False)


def _ensure_sqlite_parent_dir(db_path: str) -> None:
    resolved_path = _resolve_sqlite_filesystem_path(db_path)
    if resolved_path is None:
        return
    parent = os.path.dirname(str(resolved_path))
    if parent:
        parent_key = os.path.realpath(os.path.expanduser(parent))
        with _SQLITE_PARENT_DIRS_LOCK:
            if parent_key in _SQLITE_PARENT_DIRS_READY:
                _SQLITE_PARENT_DIRS_READY.move_to_end(parent_key)
                if os.path.isdir(parent_key):
                    return
                _SQLITE_PARENT_DIRS_READY.pop(parent_key, None)
            if os.path.isdir(parent_key):
                _mark_parent_dir_ready_locked(parent_key)
                return
            os.makedirs(parent_key, exist_ok=True)
            _mark_parent_dir_ready_locked(parent_key)


def _normalize_sqlite_identifier(identifier: str, *, label: str) -> str:
    normalized = str(identifier).strip()
    if not normalized or _SQLITE_IDENTIFIER_PATTERN.fullmatch(normalized) is None:
        raise ValueError(f"Invalid SQLite identifier for {label}: {identifier!r}")
    return normalized


def add_bounded_ready_key(
    ready_keys: set[str],
    db_key: str,
    *,
    max_entries: int = 2_048,
) -> None:
    """
    SQLite ready-key set의 크기를 상한 내로 유지한다.
    상한 초과 시 필요한 수만큼만 제거해 캐시 히트율 저하를 줄인다.
    """
    normalized_max_entries = max(1, int(max_entries))
    if db_key in ready_keys:
        return
    overflow_count = len(ready_keys) - normalized_max_entries + 1
    while overflow_count > 0 and ready_keys:
        ready_keys.pop()
        overflow_count -= 1
    ready_keys.add(db_key)


def build_sqlite_in_placeholders(lookup_keys: Iterable[object]) -> str:
    """
    SQL IN (...) 절용 placeholder 문자열을 생성한다.
    """
    normalized_lookup_keys = tuple(lookup_keys)
    if not normalized_lookup_keys:
        raise ValueError("lookup_keys must not be empty")
    return ",".join("?" for _ in normalized_lookup_keys)


def build_sqlite_order_case_sql(
    *,
    column_name: str,
    lookup_keys: Iterable[object],
) -> str:
    """
    lookup key 우선순위를 보장하는 CASE ORDER BY 절을 생성한다.
    """
    normalized_lookup_keys = tuple(lookup_keys)
    if not normalized_lookup_keys:
        raise ValueError("lookup_keys must not be empty")
    normalized_column_name = _normalize_sqlite_identifier(
        column_name,
        label="column_name",
    )
    return f"CASE {normalized_column_name} " + " ".join(
        f"WHEN ? THEN {index}" for index, _ in enumerate(normalized_lookup_keys)
    ) + f" ELSE {len(normalized_lookup_keys)} END"


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
        ORDER BY {normalized_updated_at_column} DESC, rowid DESC
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
            ORDER BY {normalized_updated_at_column} DESC, rowid DESC
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
    read_only: bool = False,
    connect_retries: int = 2,
    connect_retry_delay_seconds: float = 0.03,
) -> sqlite3.Connection:
    """Auto-closing Connection을 생성하고 지정된 PRAGMA를 적용한다."""
    normalized_path = str(db_path).strip()
    is_uri = bool(normalized_path) and normalized_path.startswith("file:")
    connect_path = normalized_path if normalized_path else db_path
    if read_only:
        connect_path, is_uri = _build_read_only_sqlite_uri(connect_path)
    if ensure_parent_dir and not read_only:
        _ensure_sqlite_parent_dir(connect_path)

    normalized_cached_statements = max(1, int(cached_statements))
    normalized_pragmas = _deduplicate_pragmas(pragmas or ())
    if read_only:
        normalized_pragmas = tuple(
            pragma_sql
            for pragma_sql in normalized_pragmas
            if not _is_read_only_blocked_pragma(pragma_sql)
        )
        if not any(
            _extract_pragma_name(pragma_sql) == "query_only"
            for pragma_sql in normalized_pragmas
        ):
            normalized_pragmas = ("PRAGMA query_only=ON", *normalized_pragmas)
    persistent_pragmas = {
        pragma_sql for pragma_sql in normalized_pragmas if _is_persistent_pragma(pragma_sql)
    }
    persistent_db_key: str | None = None
    pending_persistent_pragmas: set[str] = set()
    if persistent_pragmas:
        persistent_db_key = _normalize_sqlite_filesystem_key(connect_path)
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
