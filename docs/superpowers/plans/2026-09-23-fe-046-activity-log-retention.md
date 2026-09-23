# [FE-046] 활동 로그 날짜 기준 보관과 개인정보 파일 0600 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 활동 로그를 「마지막 기록 후 30일」 기준으로 지우고, 개인정보가 담긴 DB·로그·챗봇 JSON 파일을 0600 으로 만든다.

**Architecture:** 표준 `TimedRotatingFileHandler` 를 상속해 회전(`doRollover`)과 파일 열기(`_open`)를 덮어쓰고, 수정 시각 기준 삭제 `prune_expired` 를 더한다. DB 권한은 모든 SQLite 연결이 지나는 `connect_sqlite` 한 곳에서 좁힌다. 챗봇 JSON 은 원자적 쓰기 헬퍼의 임시 파일 생성 모드를 바꾼다.

**Tech Stack:** Python 3.11 표준 라이브러리(logging.handlers, os, stat), pytest, Next 16 서버 컴포넌트 문안, vitest.

**Spec:** 별도 설계 문서 없음(bounded). 설계는 2026-09-23 대화에서 제시하고 사용자가 「30일로 진행」으로 승인했다. 요지는 `docs/dev-cycle/TODO.md` 의 `[FE-046]` 설계 승인 줄에 있다.

## Global Constraints

- 보관 기간: 30일. 기준은 회전된 파일의 **마지막 수정 시각**(`st_mtime`)이며 파일 이름의 날짜가 아니다.
- 권한: `0o600`. 읽기 전용 연결과 메모리 DB 는 건드리지 않는다.
- 권한 변경 실패는 연결·기록을 막지 않는다. SQLite 쪽 경고는 경로마다 한 번만 남긴다.
- 테스트가 만드는 파일은 `tmp_path` 에만 둔다. **예외:** `services.activity_logger` 를 import 하면 전역 `ActivityLogger()` 가 cwd 기준 `logs/` 로 만들어지므로, 테스트 실행만으로 원본 `logs/` 의 30일 지난 회전 파일(2026-02~05, 아홉 개)이 지워지고 남은 파일은 0600 이 된다. 사용자가 설계 승인 때 이 영향을 승인했다.
- `services/sqlite_utils.py` 는 위험 경로(저장소 스키마)이므로 티어는 T3 이다.
- 다중 워커 회전 경합(늦게 회전하는 워커가 이미 날짜가 붙은 파일에 계속 쓰는 문제)은 **이 항목에서 고친다**(2026-09-23 계획 검토 B1 뒤 사용자가 범위 확장 승인). 경합이 남아 있으면 그 파일의 수정 시각이 계속 새로워져 영원히 지워지지 않고, 방침의 30일 서술이 거짓이 된다.
- 활동 로그 삭제는 **기동할 때**(워커마다 앱을 만들 때)와 날짜가 바뀐 뒤 처음 기록할 때 일어난다. `app/routes/kr_market_chatbot_http_routes.py:249` 의 `_register_chatbot_core_routes` 가 블루프린트 등록 시점에 `_build_chatbot_activity_logger`(:34)를 불러 모듈을 import 하기 때문이다. (계획 검토 B2 는 세 호출처가 모두 늦게 import 한다고 보고 「각 워커의 첫 기록」이라 적었으나, 코드 리뷰가 `create_app()` 실측으로 정정했다.)

---

### Task 1: 활동 로그 보관 기간, 파일 권한, 다중 워커 회전

**Files:**
- Modify: `services/activity_logger.py`
- Test: `tests/services/test_activity_logger_refactor.py` (신규)

**Interfaces:**
- Produces: `ACTIVITY_LOG_RETENTION_DAYS = 30`, `class RetentionTimedRotatingFileHandler(TimedRotatingFileHandler)` 와 메서드 `prune_expired() -> None`, `doRollover()`, `_open()`.

전역 로거 `user_activity` 는 이미 핸들러가 있으면 새로 붙이지 않으므로, 테스트는 대부분 핸들러 클래스를 직접 만든다.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def _touch(path, days_ago):
    path.write_text("x\n", encoding="utf-8")
    ts = time.time() - days_ago * 86_400
    os.utime(path, (ts, ts))

def _handler(base):
    return RetentionTimedRotatingFileHandler(str(base), when="midnight", encoding="utf-8")

def test_prune_uses_mtime_not_the_date_in_the_name(tmp_path):
    old = tmp_path / "user_activity.log.2026-09-20"    # 이름은 최근, 수정 시각은 31일 전
    young = tmp_path / "user_activity.log.2026-01-01"  # 이름은 오래됨, 수정 시각은 29일 전
    other = tmp_path / "other.log.2026-01-01"
    _touch(old, 31); _touch(young, 29); _touch(other, 400)
    handler = _handler(tmp_path / "user_activity.log")
    try:
        handler.prune_expired()
    finally:
        handler.close()
    assert not old.exists()
    assert young.exists() and other.exists()

def test_prune_expired_removes_old_and_narrows_survivors(tmp_path):
    old = tmp_path / "user_activity.log.2026-02-22"; _touch(old, 200)
    young = tmp_path / "user_activity.log.2026-09-20"; _touch(young, 2); os.chmod(young, 0o644)
    handler = _handler(tmp_path / "user_activity.log")
    try:
        handler.prune_expired()
    finally:
        handler.close()
    assert not old.exists()
    assert stat.S_IMODE(os.stat(young).st_mode) == 0o600

def test_base_file_is_opened_as_0600(tmp_path):
    base = tmp_path / "user_activity.log"
    base.write_text("", encoding="utf-8"); os.chmod(base, 0o644)
    _handler(base).close()
    assert stat.S_IMODE(os.stat(base).st_mode) == 0o600

def test_rollover_deletes_expired_files_and_reopens_as_0600(tmp_path):
    base = tmp_path / "user_activity.log"
    old = tmp_path / "user_activity.log.2026-02-22"; _touch(old, 200)
    handler = _handler(base)
    try:
        handler.rolloverAt = time.time() - 1
        handler.emit(logging.makeLogRecord({"msg": "after-midnight"}))
    finally:
        handler.close()
    assert not old.exists()
    assert stat.S_IMODE(os.stat(base).st_mode) == 0o600
    assert "after-midnight" in base.read_text(encoding="utf-8")

def test_late_worker_writes_to_new_base_after_other_worker_rotated(tmp_path):
    # 워커 두 개를 핸들러 두 개로 흉내 낸다. A 가 먼저 회전하면 B 는 표준 구현에서
    # 「이미 회전됨」으로 돌아가 어제 파일에 계속 쓴다.
    base = tmp_path / "user_activity.log"
    a, b = _handler(base), _handler(base)
    try:
        a.emit(logging.makeLogRecord({"msg": "a-day1"}))
        b.emit(logging.makeLogRecord({"msg": "b-day1"}))
        a.rolloverAt = b.rolloverAt = time.time() - 1
        a.emit(logging.makeLogRecord({"msg": "a-day2"}))
        b.emit(logging.makeLogRecord({"msg": "b-day2"}))
        b.emit(logging.makeLogRecord({"msg": "b-day2-again"}))
    finally:
        a.close(); b.close()
    today = base.read_text(encoding="utf-8")
    assert "b-day2" in today and "b-day2-again" in today
    assert b.rolloverAt > time.time()

def test_activity_logger_prunes_on_creation(tmp_path, monkeypatch):
    user_logger = logging.getLogger("user_activity")
    monkeypatch.setattr(user_logger, "handlers", [])
    old = tmp_path / "user_activity.log.2026-02-22"; _touch(old, 200)
    ActivityLogger(log_dir=str(tmp_path))
    for handler in list(user_logger.handlers):
        handler.close()
    assert not old.exists()
```

- [ ] **Step 2: 실패 확인** — `pytest tests/services/test_activity_logger_refactor.py -v` 가 import 오류로 실패한다.

- [ ] **Step 3: 최소 구현**

```python
ACTIVITY_LOG_RETENTION_DAYS = 30

class RetentionTimedRotatingFileHandler(TimedRotatingFileHandler):
    """회전 파일을 개수가 아니라 마지막 수정 시각으로 지우고 0600 으로 연다.

    워커가 여럿이면 늦게 회전하는 워커는 표준 구현에서 「이미 회전됨」으로 돌아가
    날짜가 붙은 어제 파일에 계속 쓴다. 그 경우 새 기준 파일을 다시 연다.
    """

    def prune_expired(self) -> None:
        cutoff = time.time() - ACTIVITY_LOG_RETENTION_DAYS * 86_400
        for path in self._rotated_files():
            try:
                if os.stat(path).st_mtime < cutoff: os.remove(path)
                else: os.chmod(path, 0o600)
            except FileNotFoundError:
                continue      # 다른 워커가 먼저 지웠다
            except OSError as error:
                logger.warning(...)

    def doRollover(self) -> None:
        super().doRollover()   # backupCount=0 이라 표준 구현은 지우지 않는다
        now = time.time()
        if self.rolloverAt <= now:   # 표준 구현이 「이미 회전됨」으로 조기 반환했다
            if self.stream:
                self.stream.close()
            self.stream = self._open()
            self.rolloverAt = self.computeRollover(int(now))
        self.prune_expired()

    def _open(self):
        stream = super()._open()
        try:
            os.chmod(self.baseFilename, 0o600)
        except OSError as error:
            logger.warning(...)
        return stream
```

`_rotated_files()` 는 같은 디렉터리에서 `f"{base_name}."` 로 시작하고 나머지가 `self.extMatch.fullmatch` 에 맞는 경로 목록이다. 3.11 의 `when='midnight'` 에서 `extMatch` 는 `(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)` 이므로 `fullmatch` 가 날짜 형식만 통과시킨다. `ActivityLogger.__init__` 는 `backupCount` 없이(기본 0) 핸들러를 만들고, 붙인 직후 `prune_expired()` 를 부른다. `getFilesToDelete` 는 덮어쓰지 않는다. `backupCount=0` 이면 표준 `doRollover` 가 부르지 않기 때문이다. 삭제를 표준 `doRollover` 의 `os.remove` 에 맡기지 않는 이유는 그 호출이 `FileNotFoundError` 를 잡지 않아 다른 워커와 겹치면 레코드를 잃기 때문이다.

- [ ] **Step 4: 통과 확인** — 같은 명령이 통과한다.

### Task 2: SQLite 파일 권한

**Files:**
- Modify: `services/sqlite_utils.py` (`connect_sqlite` 의 `_open_connection`)
- Test: `tests/services/test_sqlite_utils.py` (추가)

**Interfaces:**
- Produces: `_restrict_sqlite_file_mode(connect_path: str) -> None`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def test_connect_sqlite_creates_db_as_0600(tmp_path):
    db = tmp_path / "new.db"
    with sqlite_utils.connect_sqlite(str(db)) as conn:
        conn.execute("CREATE TABLE t (x)")
    assert stat.S_IMODE(os.stat(db).st_mode) == 0o600

def test_connect_sqlite_narrows_existing_db_and_wal_files(tmp_path):
    db = tmp_path / "old.db"
    with sqlite3.connect(db) as raw:
        raw.execute("PRAGMA journal_mode=WAL"); raw.execute("CREATE TABLE t (x)")
        for suffix in ("", "-wal", "-shm"):
            assert os.path.exists(f"{db}{suffix}")   # raw 연결이 열려 있어 -wal·-shm 이 남아 있다
            os.chmod(f"{db}{suffix}", 0o644)
        with sqlite_utils.connect_sqlite(str(db)) as conn:
            conn.execute("INSERT INTO t VALUES (1)")
        for suffix in ("", "-wal", "-shm"):
            assert stat.S_IMODE(os.stat(f"{db}{suffix}").st_mode) == 0o600

def test_connect_sqlite_new_wal_inherits_0600(tmp_path):
    db = tmp_path / "wal.db"
    with sqlite_utils.connect_sqlite(str(db), pragmas=("PRAGMA journal_mode=WAL",)) as conn:
        conn.execute("CREATE TABLE t (x)"); conn.execute("INSERT INTO t VALUES (1)")
        assert stat.S_IMODE(os.stat(f"{db}-wal").st_mode) == 0o600

def test_connect_sqlite_read_only_does_not_change_mode(tmp_path):
    db = tmp_path / "ro.db"
    sqlite3.connect(db).close(); os.chmod(db, 0o644)
    with sqlite_utils.connect_sqlite(str(db), read_only=True):
        pass
    assert stat.S_IMODE(os.stat(db).st_mode) == 0o644
```

- [ ] **Step 2: 실패 확인** — 새 테스트 셋이 0o644 로 실패하고 읽기 전용 테스트는 통과한다.

- [ ] **Step 3: 최소 구현**

```python
def _restrict_sqlite_file_mode(connect_path: str) -> None:
    db_key = _normalize_sqlite_filesystem_key(connect_path)
    if db_key is None:
        return
    try:
        if not os.stat(db_key).st_mode & 0o077:
            return
        # -wal·-shm 은 SQLite 가 DB 파일의 권한을 따라 만든다. 이미 있던 것만 함께 좁힌다.
        for path in (db_key, f"{db_key}-wal", f"{db_key}-shm"):
            if os.path.exists(path):
                os.chmod(path, 0o600)
    except OSError as error:
        # 다른 소유자의 파일처럼 영구히 실패하는 경우 연결마다 경고가 쌓이지 않게 경로당 한 번만 남긴다.
        if db_key not in _SQLITE_MODE_WARNED:
            _SQLITE_MODE_WARNED.add(db_key)
            logger.warning("SQLite 파일 권한을 좁히지 못했습니다(%s): %s", db_key, error)
```

`_SQLITE_MODE_WARNED: set[str] = set()` 은 모듈 수준에 둔다. `_open_connection` 에서 `sqlite3.connect` 성공 직후, `read_only` 가 아니면 호출한다. 연결마다 `stat` 한 번이 든다.

- [ ] **Step 4: 통과 확인** — `pytest tests/services/test_sqlite_utils.py -v`.

### Task 3: 챗봇 JSON 스냅샷 권한

**Files:**
- Modify: `chatbot/storage_history_helpers.py` (`atomic_write_json`)
- Test: `tests/chatbot/test_storage_history_helpers_refactor.py` (신규)

- [ ] **Step 1: 실패하는 테스트** — `atomic_write_json(tmp_path / "h.json", {"a": 1})` 뒤 권한이 0o600 이다. 기존 0o644 파일을 덮어쓴 경우에도 0o600 이다.
- [ ] **Step 2: 실패 확인**
- [ ] **Step 3: 구현** — 임시 파일을 `os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)` 로 만들고 `os.fdopen(fd, "w", encoding="utf-8")` 로 쓴다. `os.replace` 는 임시 파일의 권한을 그대로 옮긴다.
- [ ] **Step 4: 통과 확인**

### Task 4: 개인정보처리방침 문안

**Files:**
- Modify: `frontend/src/app/(legal)/privacy/page.tsx` (3항 활동 로그 행, 10항 안전성 목록, `EFFECTIVE_DATE`)
- Modify: `frontend/src/app/(legal)/legal-pages.test.tsx` (57-64행의 보관 기간 단언)

- [ ] **Step 1: 테스트 먼저 수정** — 옛 문장 두 개 단언을 지우고 다음을 고정한다: `'마지막 기록 후 30일이 지난 파일'`, `'날짜가 바뀐 뒤나 서버를 다시 시작한 뒤 처음 기록을 남길 때'`, 10항의 `'활동 로그와 데이터베이스 파일은 서버를 실행하는 계정만 읽고 쓸 수 있도록'`. 주석은 새 동작(수정 시각 기준, `services/activity_logger.py` 의 `ACTIVITY_LOG_RETENTION_DAYS`)으로 고친다.
- [ ] **Step 2: 실패 확인** — `cd frontend && npx vitest run src/app/\(legal\)/legal-pages.test.tsx`.
- [ ] **Step 3: 문안 수정**
  - 3항: 「활동 로그는 날짜별 파일로 나누어 저장하며, 마지막 기록 후 30일이 지난 파일은 날짜가 바뀐 뒤나 서버를 다시 시작한 뒤 처음 기록을 남길 때 자동으로 삭제됩니다. 삭제는 파일 단위로 이루어지므로 한 파일 안의 가장 오래된 기록은 30일보다 조금 더 남을 수 있습니다.」
  - 10항 파일 항목에 「활동 로그와 데이터베이스 파일은 서버를 실행하는 계정만 읽고 쓸 수 있도록 파일 권한을 제한합니다」를 덧붙인다. 범위를 이 두 가지로 좁히는 이유는 `logs/backend.log`·`logs/critical_errors.log`·`logs/gunicorn-access.log` 가 여전히 0644 이기 때문이다(TODO 로 이월).
  - `EFFECTIVE_DATE` 를 `'2026년 9월 23일'` 로 바꾼다. 보관 기간을 줄이는 변경이므로 12항의 30일 사전 고지 대상이 아니다.
- [ ] **Step 4: 통과 확인** — vitest 해당 파일, `npm run type-check`.

### Task 5: 전체 검증과 TODO 이월

- [ ] `pytest -q` 전체, `cd frontend && npm run test && npm run type-check`.
- [ ] 변이 확인: (a) `prune_expired` 의 비교를 파일 이름 날짜로 바꾸면, (a2) `doRollover` 의 재열기 갈래를 지우면, (a3) `doRollover` 의 `prune_expired()` 호출을 지우면 각각 Task 1 테스트가 실패, (b) `_restrict_sqlite_file_mode` 호출을 지우면 Task 2 테스트가 실패, (c) `atomic_write_json` 을 `open()` 으로 되돌리면 Task 3 테스트가 실패하는지 확인한다.
- [ ] `docs/dev-cycle/TODO.md` P2 에 0644 로 남는 다른 로그 세 개(`backend.log`·`critical_errors.log`·`gunicorn-access.log`)의 권한 항목을 등록한다.

전체 pytest 는 전역 `ActivityLogger` 를 만들 수 있고, 그러면 원본 `logs/` 의 30일 지난 회전 파일(2026-02~05, 아홉 개)이 지워진다. 사용자가 설계 단계에서 이 영향을 승인했다.
