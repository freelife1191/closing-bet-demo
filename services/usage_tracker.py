#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Usage Tracker Service
- Tracks API usage for users without personal API keys.
- Enforces a limit (e.g., 10 uses per day or total).
- Uses SQLite for persistence.
"""

import os
import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class UsageTracker:
    def __init__(self, db_path='usage.db', limit=10):
        # DB Path relative to data directory or root
        self.db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', db_path)
        self.limit = limit
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database table"""
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS usage_log (
                    email TEXT PRIMARY KEY,
                    count INTEGER DEFAULT 0,
                    last_used TEXT
                )
            ''')
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to initialize usage db: {e}")

    def check_and_increment(self, email: str) -> bool:
        """
        Check if user has remaining quota and increment if yes.
        Returns True if allowed, False if limit exceeded.
        """
        if not email:
            return False

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check current usage
            cursor.execute('SELECT count FROM usage_log WHERE email = ?', (email,))
            row = cursor.fetchone()
            
            current_count = 0
            if row:
                current_count = row[0]
            
            if current_count >= self.limit:
                conn.close()
                return False
            
            # Increment
            now = datetime.now().isoformat()
            if row:
                cursor.execute('UPDATE usage_log SET count = count + 1, last_used = ? WHERE email = ?', (now, email))
            else:
                cursor.execute('INSERT INTO usage_log (email, count, last_used) VALUES (?, 1, ?)', (email, now))
                
            conn.commit()
            conn.close()
            
            logger.info(f"User {email} usage incremented: {current_count + 1}/{self.limit}")
            return True
            
        except Exception as e:
            logger.error(f"Usage tracking error: {e}")
            # Fail open or closed? Let's fail open for now to avoid blocking users on DB error, 
            # OR fail closed to protect costs. Let's fail closed.
            return False

    def get_usage(self, email: str) -> int:
        """Get current usage count"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT count FROM usage_log WHERE email = ?', (email,))
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else 0
        except:
            return 0

# Global Instance
usage_tracker = UsageTracker()
