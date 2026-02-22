#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQLite 공통 연결 유틸.
"""

from __future__ import annotations

import sqlite3
from typing import Iterable


class AutoClosingSQLiteConnection(sqlite3.Connection):
    """with 블록 종료 시 커밋/롤백 후 연결을 닫는 SQLite Connection."""

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            return super().__exit__(exc_type, exc_val, exc_tb)
        finally:
            self.close()


def connect_sqlite(
    db_path: str,
    *,
    timeout_seconds: float = 5.0,
    pragmas: Iterable[str] | None = None,
) -> sqlite3.Connection:
    """Auto-closing Connection을 생성하고 지정된 PRAGMA를 적용한다."""
    conn = sqlite3.connect(
        db_path,
        timeout=timeout_seconds,
        factory=AutoClosingSQLiteConnection,
    )
    try:
        for pragma_sql in pragmas or ():
            conn.execute(pragma_sql)
    except Exception:
        conn.close()
        raise
    return conn
