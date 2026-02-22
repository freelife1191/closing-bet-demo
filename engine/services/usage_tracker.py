import os
import logging
import sqlite3
from datetime import datetime

from services.sqlite_utils import build_sqlite_pragmas, connect_sqlite

# 데이터 디렉토리 확보
DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'data',
)

DB_PATH = os.path.join(DATA_DIR, 'usage.db')
MAX_FREE_USAGE = 10

logger = logging.getLogger(__name__)

class UsageTracker:
    SQLITE_BUSY_TIMEOUT_MS = 30_000
    SQLITE_INIT_PRAGMAS = build_sqlite_pragmas(
        busy_timeout_ms=SQLITE_BUSY_TIMEOUT_MS,
    )
    SQLITE_SESSION_PRAGMAS = build_sqlite_pragmas(
        busy_timeout_ms=SQLITE_BUSY_TIMEOUT_MS,
        base_pragmas=("PRAGMA temp_store=MEMORY", "PRAGMA cache_size=-8000"),
    )

    def __init__(self):
        self._init_db()

    @staticmethod
    def _normalize_email(email: str | None) -> str:
        """이메일 키를 SQLite PK로 저장하기 전에 정규화한다."""
        return str(email or "").strip().lower()

    def _connect(self):
        timeout_seconds = max(1, self.SQLITE_BUSY_TIMEOUT_MS // 1000)
        return connect_sqlite(
            DB_PATH,
            timeout_seconds=timeout_seconds,
            pragmas=self.SQLITE_SESSION_PRAGMAS,
        )

    def _init_db(self):
        """DB 초기화"""
        try:
            with connect_sqlite(
                DB_PATH,
                timeout_seconds=max(1, self.SQLITE_BUSY_TIMEOUT_MS // 1000),
                pragmas=self.SQLITE_INIT_PRAGMAS,
            ) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS api_usage (
                        email TEXT PRIMARY KEY,
                        count INTEGER DEFAULT 0,
                        last_used_at TEXT
                    )
                ''')
                cursor.execute(
                    '''
                    CREATE INDEX IF NOT EXISTS idx_api_usage_last_used_at
                    ON api_usage(last_used_at DESC)
                    '''
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Usage DB Initialization Error: {e}")

    @staticmethod
    def _is_missing_usage_table_error(error: Exception) -> bool:
        if not isinstance(error, sqlite3.OperationalError):
            return False
        message = str(error).lower()
        return "no such table" in message and "api_usage" in message

    def check_and_increment(self, email: str, *, _retried: bool = False) -> bool:
        """
        사용량 확인 및 증가
        Returns:
            bool: 사용 가능 여부 (True: 가능, False: 제한 초과)
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
                    INSERT INTO api_usage (email, count, last_used_at)
                    VALUES (?, 1, ?)
                    ON CONFLICT(email) DO UPDATE SET
                        count = api_usage.count + 1,
                        last_used_at = excluded.last_used_at
                    WHERE api_usage.count < ?
                    ''',
                    (normalized_email, now, MAX_FREE_USAGE),
                )
                if cursor.rowcount == 0:
                    return False

                conn.commit()
            return True
            
        except Exception as e:
            if (not _retried) and self._is_missing_usage_table_error(e):
                self._init_db()
                return self.check_and_increment(email, _retried=True)
            logger.error(f"Usage Tracking Error: {e}")
            # DB 에러 시 일단 허용 (Fail-open)
            return True

    def get_usage(self, email: str, *, _retried: bool = False) -> int:
        """현재 사용량 조회"""
        normalized_email = self._normalize_email(email)
        if not normalized_email:
            return 0
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT count FROM api_usage WHERE email = ?', (normalized_email,))
                result = cursor.fetchone()
                return result[0] if result else 0
        except Exception as e:
            if (not _retried) and self._is_missing_usage_table_error(e):
                self._init_db()
                return self.get_usage(email, _retried=True)
            logger.error(f"Usage lookup error: {e}")
            return 0

    def get_usaage(self, email: str) -> int:
        """오탈자 기반 레거시 인터페이스 호환."""
        return self.get_usage(email)

usage_tracker = UsageTracker()
