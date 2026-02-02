
import sqlite3
import os
import logging
from datetime import datetime

# 데이터 디렉토리 확보
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, 'usage.db')
MAX_FREE_USAGE = 10

logger = logging.getLogger(__name__)

class UsageTracker:
    def __init__(self):
        self._init_db()

    def _init_db(self):
        """DB 초기화"""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS api_usage (
                    email TEXT PRIMARY KEY,
                    count INTEGER DEFAULT 0,
                    last_used_at TEXT
                )
            ''')
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Usage DB Initialization Error: {e}")

    def check_and_increment(self, email: str) -> bool:
        """
        사용량 확인 및 증가
        Returns:
            bool: 사용 가능 여부 (True: 가능, False: 제한 초과)
        """
        if not email:
            return False

        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # 현재 사용량 조회
            cursor.execute('SELECT count FROM api_usage WHERE email = ?', (email,))
            result = cursor.fetchone()
            
            current_count = result[0] if result else 0
            
            if current_count >= MAX_FREE_USAGE:
                conn.close()
                return False
            
            # 사용량 증가 또는 신규 등록
            now = datetime.now().isoformat()
            if result:
                cursor.execute('UPDATE api_usage SET count = count + 1, last_used_at = ? WHERE email = ?', (now, email))
            else:
                cursor.execute('INSERT INTO api_usage (email, count, last_used_at) VALUES (?, 1, ?)', (email, now))
                
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"Usage Tracking Error: {e}")
            # DB 에러 시 일단 허용 (Fail-open)
            return True

    def get_usaage(self, email: str) -> int:
        """현재 사용량 조회"""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute('SELECT count FROM api_usage WHERE email = ?', (email,))
            result = cursor.fetchone()
            conn.close()
            return result[0] if result else 0
        except:
            return 0

usage_tracker = UsageTracker()
