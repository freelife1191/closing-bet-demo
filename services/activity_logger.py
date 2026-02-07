import logging
import os
import json
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler

class ActivityLogger:
    def __init__(self, log_dir='logs', filename='user_activity.log'):
        self.log_dir = log_dir
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        self.filepath = os.path.join(log_dir, filename)
        
        # Setup Logger
        self.logger = logging.getLogger('user_activity')
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False # don't propagate to root logger (avoid double logging)
        
        # Check if handlers already exist to avoid duplication
        if not self.logger.handlers:
            # Daily Rotation
            handler = TimedRotatingFileHandler(
                self.filepath, when='midnight', interval=1, backupCount=30, encoding='utf-8'
            )
            formatter = logging.Formatter('%(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            
    def _format_log(self, user_id, action, details, ip_address):
        """Format log entry as JSON"""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'user_id': user_id or 'anonymous',
            'action': action,
            'ip': ip_address or 'unknown',
            'details': details or {}
        }
        return json.dumps(entry, ensure_ascii=False)

    def log_action(self, user_id, action, details=None, ip_address=None):
        """Generic action logger"""
        try:
            msg = self._format_log(user_id, action, details, ip_address)
            self.logger.info(msg)
        except Exception as e:
            print(f"Failed to log activity: {e}")

# Global Instance
activity_logger = ActivityLogger()
