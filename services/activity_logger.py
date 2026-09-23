import logging
import os
import json
import time
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler

logger = logging.getLogger(__name__)

ACTIVITY_LOG_RETENTION_DAYS = 30


class RetentionTimedRotatingFileHandler(TimedRotatingFileHandler):
    """회전 파일을 개수가 아니라 마지막 수정 시각으로 지우고 0600 으로 연다.

    워커가 여럿이면 늦게 회전하는 워커는 표준 구현에서 「이미 회전됨」으로 돌아가
    날짜가 붙은 어제 파일에 계속 쓴다. 그 경우 새 기준 파일을 다시 연다.
    """

    def _rotated_files(self) -> list:
        dir_name, base_name = os.path.split(self.baseFilename)
        prefix = f"{base_name}."
        return [
            os.path.join(dir_name, name)
            for name in os.listdir(dir_name)
            if name.startswith(prefix) and self.extMatch.fullmatch(name[len(prefix):])
        ]

    def prune_expired(self) -> None:
        cutoff = time.time() - ACTIVITY_LOG_RETENTION_DAYS * 86_400
        for path in self._rotated_files():
            try:
                if os.stat(path).st_mtime < cutoff:
                    os.remove(path)
                else:
                    os.chmod(path, 0o600)
            except FileNotFoundError:
                continue  # 다른 워커가 먼저 지웠다
            except OSError as error:
                logger.warning("활동 로그 회전 파일을 정리하지 못했습니다(%s): %s", path, error)

    def rotate(self, source: str, dest: str) -> None:
        # 표준 os.rename 은 두 워커가 동시에 회전하면 먼저 만든 날짜 파일을 새 기준 파일로
        # 덮어써 전날 기록을 잃는다. link 는 대상이 있으면 실패하므로 그 경우 그대로 둔다.
        try:
            os.link(source, dest)
        except (FileExistsError, FileNotFoundError):
            return  # 다른 워커가 먼저 회전했다. 기준 파일은 이어지는 _open 이 다시 만든다
        os.unlink(source)

    def doRollover(self) -> None:
        # backupCount=0 이라 표준 구현은 지우지 않는다. 표준 os.remove 는
        # FileNotFoundError 를 잡지 않아 다른 워커와 겹치면 레코드를 잃는다.
        super().doRollover()
        now = time.time()
        if self.rolloverAt <= now:  # 표준 구현이 「이미 회전됨」으로 조기 반환했다
            if self.stream:
                self.stream.close()
            self.stream = self._open()
            self.rolloverAt = self.computeRollover(int(now))
        self.prune_expired()

    def _open(self):
        # ponytail: 새 파일은 umask 로 만든 뒤 좁히므로 잠깐 0644 다(그때는 비어 있음).
        stream = super()._open()
        try:
            os.chmod(self.baseFilename, 0o600)
        except OSError as error:
            logger.warning("활동 로그 권한을 좁히지 못했습니다: %s", error)
        return stream


class ActivityLogger:
    def __init__(self, log_dir='logs', filename='user_activity.log'):
        self.log_dir = log_dir
        # 새로 만들 때만 0700 이다. 이미 있는 디렉터리는 restart_all.sh 가 좁힌다 [INFRA-085]
        os.makedirs(log_dir, mode=0o700, exist_ok=True)
            
        self.filepath = os.path.join(log_dir, filename)
        
        # Setup Logger
        self.logger = logging.getLogger('user_activity')
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False # don't propagate to root logger (avoid double logging)
        
        # Check if handlers already exist to avoid duplication
        if not self.logger.handlers:
            # Daily Rotation. 보관 기간은 ACTIVITY_LOG_RETENTION_DAYS 가 정한다.
            handler = RetentionTimedRotatingFileHandler(
                self.filepath, when='midnight', interval=1, encoding='utf-8'
            )
            formatter = logging.Formatter('%(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            # GET 은 기록되지 않아 기준 파일이 며칠씩 그대로일 수 있다. 날짜가 이미 지났으면
            # 다음 기록을 기다리지 않고 지금 회전해, 30일 지난 기록도 기동 때 지워지게 한다.
            if handler.rolloverAt <= time.time():
                handler.doRollover()  # 회전 뒤 prune_expired 까지 한다
            else:
                handler.prune_expired()
            
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
