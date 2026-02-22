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
from datetime import datetime

from services.sqlite_utils import connect_sqlite

logger = logging.getLogger(__name__)

class UsageTracker:
    SQLITE_BUSY_TIMEOUT_MS = 30_000
    SQLITE_INIT_PRAGMAS = (
        "PRAGMA journal_mode=WAL",
        "PRAGMA synchronous=NORMAL",
        "PRAGMA temp_store=MEMORY",
    )

    def __init__(self, db_path='usage.db', limit=10):
        # DB Path relative to data directory or root
        self.db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', db_path)
        self.limit = limit
        self._init_db()

    @staticmethod
    def _normalize_email(email: str | None) -> str:
        """이메일 키를 SQLite PK로 저장하기 전에 정규화한다."""
        return str(email or "").strip().lower()

    def _connect(self):
        timeout_seconds = max(1, self.SQLITE_BUSY_TIMEOUT_MS // 1000)
        return connect_sqlite(
            self.db_path,
            timeout_seconds=timeout_seconds,
            pragmas=(
                f"PRAGMA busy_timeout={self.SQLITE_BUSY_TIMEOUT_MS}",
                "PRAGMA temp_store=MEMORY",
            ),
        )

    def _init_db(self):
        """Initialize SQLite database table"""
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            with self._connect() as conn:
                cursor = conn.cursor()
                for pragma_sql in self.SQLITE_INIT_PRAGMAS:
                    cursor.execute(pragma_sql)
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
        except Exception as e:
            logger.error(f"Failed to initialize usage db: {e}")

    def check_and_increment(self, email: str) -> bool:
        """
        Check if user has remaining quota and increment if yes.
        Returns True if allowed, False if limit exceeded.
        """
        normalized_email = self._normalize_email(email)
        if not normalized_email:
            return False

        try:
            now = datetime.now().isoformat()
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

            logger.info(f"User {normalized_email} usage incremented (limit={self.limit})")
            return True

        except Exception as e:
            logger.error(f"Usage tracking error: {e}")
            # Fail open or closed? Let's fail open for now to avoid blocking users on DB error, 
            # OR fail closed to protect costs. Let's fail closed.
            return False

    def get_usage(self, email: str) -> int:
        """Get current usage count"""
        normalized_email = self._normalize_email(email)
        if not normalized_email:
            return 0
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT count FROM usage_log WHERE email = ?', (normalized_email,))
                row = cursor.fetchone()
            return row[0] if row else 0
        except Exception as e:
            logger.warning(f"Failed to read usage for {normalized_email}: {e}")
            return 0

# Global Instance
usage_tracker = UsageTracker()
