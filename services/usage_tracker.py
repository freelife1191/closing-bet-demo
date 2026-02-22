#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Usage Tracker Service
- Tracks API usage for users without personal API keys.
- Enforces a limit (e.g., 10 uses per day or total).
- Uses SQLite for persistence.
"""

import os
import logging
import threading
from datetime import datetime

from services.sqlite_utils import (
    build_sqlite_pragmas,
    connect_sqlite,
    is_sqlite_missing_table_error,
    run_sqlite_with_retry,
    sqlite_db_path_exists,
)

logger = logging.getLogger(__name__)

class UsageTracker:
    SQLITE_BUSY_TIMEOUT_MS = 30_000
    SQLITE_RETRY_ATTEMPTS = 2
    SQLITE_RETRY_DELAY_SECONDS = 0.03
    SQLITE_INIT_PRAGMAS = build_sqlite_pragmas(
        busy_timeout_ms=SQLITE_BUSY_TIMEOUT_MS,
    )
    SQLITE_SESSION_PRAGMAS = build_sqlite_pragmas(
        busy_timeout_ms=SQLITE_BUSY_TIMEOUT_MS,
        base_pragmas=("PRAGMA temp_store=MEMORY", "PRAGMA cache_size=-8000"),
    )

    def __init__(self, db_path='usage.db', limit=10):
        # DB Path relative to data directory or root
        self.db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', db_path)
        self.limit = limit
        self._db_init_lock = threading.Lock()
        self._db_init_condition = threading.Condition(self._db_init_lock)
        self._db_init_in_progress = False
        self._db_ready = False
        self._init_db()

    @staticmethod
    def _normalize_email(email: str | None) -> str:
        """이메일 키를 SQLite PK로 저장하기 전에 정규화한다."""
        return str(email or "").strip().lower()

    def _connect(self):
        return self._connect_with_mode(read_only=False)

    def _connect_read_only(self):
        return self._connect_with_mode(read_only=True)

    def _connect_with_mode(self, *, read_only: bool):
        timeout_seconds = max(1, self.SQLITE_BUSY_TIMEOUT_MS // 1000)
        return connect_sqlite(
            self.db_path,
            timeout_seconds=timeout_seconds,
            pragmas=self.SQLITE_SESSION_PRAGMAS,
            read_only=read_only,
        )

    def _init_db(self, *, force_recheck: bool = False) -> bool:
        """Initialize SQLite database table"""
        with self._db_init_condition:
            if self._db_ready and not force_recheck:
                if sqlite_db_path_exists(self.db_path):
                    return True
                self._db_ready = False

            while self._db_init_in_progress:
                self._db_init_condition.wait()
                if self._db_ready and not force_recheck:
                    if sqlite_db_path_exists(self.db_path):
                        return True
                    self._db_ready = False

            self._db_init_in_progress = True

        def _initialize() -> None:
            with connect_sqlite(
                self.db_path,
                timeout_seconds=max(1, self.SQLITE_BUSY_TIMEOUT_MS // 1000),
                pragmas=self.SQLITE_INIT_PRAGMAS,
            ) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS usage_log (
                        email TEXT PRIMARY KEY,
                        count INTEGER DEFAULT 0,
                        last_used TEXT
                    )
                ''')
                cursor.execute(
                    '''
                    CREATE INDEX IF NOT EXISTS idx_usage_log_last_used
                    ON usage_log(last_used DESC)
                    '''
                )
                conn.commit()

        initialization_succeeded = False
        try:
            run_sqlite_with_retry(
                _initialize,
                max_retries=self.SQLITE_RETRY_ATTEMPTS,
                retry_delay_seconds=self.SQLITE_RETRY_DELAY_SECONDS,
            )
            initialization_succeeded = True
            return True
        except Exception as e:
            logger.error(f"Failed to initialize usage db: {e}")
            return False
        finally:
            with self._db_init_condition:
                self._db_init_in_progress = False
                self._db_ready = bool(initialization_succeeded)
                self._db_init_condition.notify_all()

    @staticmethod
    def _is_missing_usage_table_error(error: Exception) -> bool:
        return is_sqlite_missing_table_error(error, table_names="usage_log")

    def check_and_increment(self, email: str, *, _retried: bool = False) -> bool:
        """
        Check if user has remaining quota and increment if yes.
        Returns True if allowed, False if limit exceeded.
        """
        normalized_email = self._normalize_email(email)
        if not normalized_email:
            return False

        now = datetime.now().isoformat()

        def _check_and_increment() -> bool:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    INSERT INTO usage_log (email, count, last_used)
                    VALUES (?, 1, ?)
                    ON CONFLICT(email) DO UPDATE SET
                        count = usage_log.count + 1,
                        last_used = excluded.last_used
                    WHERE usage_log.count < ?
                    ''',
                    (normalized_email, now, self.limit),
                )
                if cursor.rowcount == 0:
                    return False

                conn.commit()
            return True

        try:
            allowed = run_sqlite_with_retry(
                _check_and_increment,
                max_retries=self.SQLITE_RETRY_ATTEMPTS,
                retry_delay_seconds=self.SQLITE_RETRY_DELAY_SECONDS,
            )
            if not allowed:
                return False

            logger.info(f"User {normalized_email} usage incremented (limit={self.limit})")
            return True

        except Exception as e:
            if (not _retried) and self._is_missing_usage_table_error(e):
                if self._init_db(force_recheck=True):
                    return self.check_and_increment(email, _retried=True)
                return False
            logger.error(f"Usage tracking error: {e}")
            # Fail open or closed? Let's fail open for now to avoid blocking users on DB error, 
            # OR fail closed to protect costs. Let's fail closed.
            return False

    def get_usage(self, email: str, *, _retried: bool = False) -> int:
        """Get current usage count"""
        normalized_email = self._normalize_email(email)
        if not normalized_email:
            return 0

        def _load_usage() -> int:
            with self._connect_read_only() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT count FROM usage_log WHERE email = ?', (normalized_email,))
                row = cursor.fetchone()
            return int(row[0]) if row else 0

        try:
            return run_sqlite_with_retry(
                _load_usage,
                max_retries=self.SQLITE_RETRY_ATTEMPTS,
                retry_delay_seconds=self.SQLITE_RETRY_DELAY_SECONDS,
            )
        except Exception as e:
            if (not _retried) and self._is_missing_usage_table_error(e):
                if self._init_db(force_recheck=True):
                    return self.get_usage(email, _retried=True)
                return 0
            logger.warning(f"Failed to read usage for {normalized_email}: {e}")
            return 0

# Global Instance
usage_tracker = UsageTracker()
