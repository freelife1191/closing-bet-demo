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
    SQLITE_RETRY_ATTEMPTS = 2
    SQLITE_RETRY_DELAY_SECONDS = 0.03
    SQLITE_INIT_PRAGMAS = build_sqlite_pragmas(
        busy_timeout_ms=SQLITE_BUSY_TIMEOUT_MS,
    )
    SQLITE_SESSION_PRAGMAS = build_sqlite_pragmas(
        busy_timeout_ms=SQLITE_BUSY_TIMEOUT_MS,
        base_pragmas=("PRAGMA temp_store=MEMORY", "PRAGMA cache_size=-8000"),
    )

    def __init__(self):
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
            DB_PATH,
            timeout_seconds=timeout_seconds,
            pragmas=self.SQLITE_SESSION_PRAGMAS,
            read_only=read_only,
        )

    def _init_db(self, *, force_recheck: bool = False) -> bool:
        """DB 초기화"""
        with self._db_init_condition:
            if self._db_ready and not force_recheck:
                if sqlite_db_path_exists(DB_PATH):
                    return True
                self._db_ready = False

            while self._db_init_in_progress:
                self._db_init_condition.wait()
                if self._db_ready and not force_recheck:
                    if sqlite_db_path_exists(DB_PATH):
                        return True
                    self._db_ready = False

            self._db_init_in_progress = True

        def _initialize() -> None:
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
            logger.error(f"Usage DB Initialization Error: {e}")
            return False
        finally:
            with self._db_init_condition:
                self._db_init_in_progress = False
                self._db_ready = bool(initialization_succeeded)
                self._db_init_condition.notify_all()

    @staticmethod
    def _is_missing_usage_table_error(error: Exception) -> bool:
        return is_sqlite_missing_table_error(error, table_names="api_usage")

    def check_and_increment(self, email: str, *, _retried: bool = False) -> bool:
        """
        사용량 확인 및 증가
        Returns:
            bool: 사용 가능 여부 (True: 가능, False: 제한 초과)
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

        try:
            return run_sqlite_with_retry(
                _check_and_increment,
                max_retries=self.SQLITE_RETRY_ATTEMPTS,
                retry_delay_seconds=self.SQLITE_RETRY_DELAY_SECONDS,
            )
            
        except Exception as e:
            if (not _retried) and self._is_missing_usage_table_error(e):
                if self._init_db(force_recheck=True):
                    return self.check_and_increment(email, _retried=True)
                return True
            logger.error(f"Usage Tracking Error: {e}")
            # DB 에러 시 일단 허용 (Fail-open)
            return True

    def get_usage(self, email: str, *, _retried: bool = False) -> int:
        """현재 사용량 조회"""
        normalized_email = self._normalize_email(email)
        if not normalized_email:
            return 0

        def _load_usage() -> int:
            with self._connect_read_only() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT count FROM api_usage WHERE email = ?', (normalized_email,))
                result = cursor.fetchone()
                return int(result[0]) if result else 0

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
            logger.error(f"Usage lookup error: {e}")
            return 0

    def get_usaage(self, email: str) -> int:
        """오탈자 기반 레거시 인터페이스 호환."""
        return self.get_usage(email)

usage_tracker = UsageTracker()
