# [INFRA-107] 기동 초기화가 살아 있는 다른 워커의 수동 업데이트 상태를 지우지 않게 한다 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** gunicorn 이 워커 하나만 다시 띄워도 다른 워커에서 실제로 돌고 있는 수동 업데이트의 `isRunning`·`items` 가 지워지지 않게 한다. 서버 전체 재기동 때 고착 상태를 푸는 종전 동작은 유지한다.

**Architecture:** `start_update` 가 상태에 `ownerPid = os.getpid()` 와 `ownerPpid = os.getppid()`(gunicorn 마스터)를 함께 저장한다. 기동 초기화는 `services/common_update_status_service.py` 의 새 함수 `reset_orphaned_update_status` 로 옮겨 `_status_file_lock` 안에서 읽고, `isRunning` 이어도 `ownerPpid` 가 자기 마스터와 같고 `ownerPid` 가 자기 pid 가 아니며 `os.kill(pid, 0)` 으로 살아 있으면 그대로 둔다. 그 밖(소유자 사망, `ownerPid` 없는 옛 파일, 자기 pid, 정수가 아닌 값)은 종전처럼 `isRunning=False`·`items=[]` 로 저장한다. `app/__init__.py` 의 `_reset_startup_status_files` 는 이 함수를 부르기만 한다.

**Tech Stack:** Python 3.11, pytest

**Spec:** 대화 설계(2026-09-25 10:56 확인 시각에 승인, 「ownerPid 기록 + 기동 때 소유 워커 생존 판정」), `docs/dev-cycle/TODO.md` `[INFRA-107]` 설계 승인 줄

## Global Constraints

- 티어 T3: `services/common_update_status_service.py` 가 tier-rules §2 「저장소 스키마」 목록에 있다. 테이블 스키마(`update_status_snapshot`)는 바꾸지 않는다. `ownerPid` 는 JSON 페이로드의 필드 하나다.
- `v2_screener_status.json` 과 스케줄러 런타임 상태의 무조건 초기화는 이번 범위 밖이다. 새 TODO 항목으로 등록한다.
- 서버 전체 재기동(모든 옛 워커 사망) 때의 결과는 종전과 같아야 한다: `isRunning=False`, `items=[]`.
- 테스트는 `tmp_path` 와 실제 프로세스(`os.getppid()`, 끝난 자식 프로세스)만 쓴다. 원본 `data/`·네트워크에 닿지 않는다.
- 운영 반영은 gunicorn 워커를 모두 재기동해야 한다(장 중 금지). 반영 직후의 기동은 옛 파일(`ownerPid` 없음)을 종전처럼 초기화한다.

## Review Focus

- `ownerPid` 가 `True` 같은 bool 이면 `isinstance(pid, int)` 가 통과해 pid 1(항상 살아 있음)로 읽힌다. `type(pid) is int` 로 거른다.
- `os.kill(pid, 0)` 의 `PermissionError` 는 프로세스가 존재한다는 뜻이다(다른 사용자). 살아 있음으로 본다. 그 밖의 `OSError` 는 죽음으로 본다.
- 상태 파일이 없고 SQLite 스냅샷만 `isRunning` 이면 `_read_status_file` 이 스냅샷을 돌려주므로 초기화된 파일이 새로 생긴다. 종전에는 파일이 없으면 아무것도 하지 않았다. 고착된 스냅샷을 푸는 쪽이라 받아들인다.
- 깨진 JSON 은 종전에 예외를 잡고 넘어갔다. 새 경로는 `_read_status_file` 이 스냅샷 또는 기본값으로 대신한다. 기본값이면 `isRunning` 이 거짓이라 쓰지 않는다. 기존 테스트 `test_reset_startup_status_files_handles_corrupt_update_status` 가 이 길을 지킨다.
- 초기화 저장이 `atomic_write_text` 직접 쓰기에서 `save_update_status` 로 바뀌어 캐시·SQLite 스냅샷도 함께 갱신된다.

## 알려진 한계

1. 같은 마스터 안에서 죽은 소유자의 pid 를 다른 프로세스가 재사용하면 초기화를 건너뛴다. 그 경우 `isRunning` 이 관리자 중단 요청이나 다음 전체 재기동까지 남는다. 마스터가 pid 1 로 고정되는 컨테이너에서는 재부팅 뒤에도 같은 일이 생길 수 있다. `# ponytail:` 주석으로 표시한다.
2. graceful 재기동(HUP, max-requests)은 새 워커를 먼저 띄운 뒤 옛 워커를 끝내므로, 새 워커는 살아 있는 옛 소유자를 보고 보존한다. 옛 워커가 끝나며 파이프라인이 죽으면 상태가 관리자 중단 요청까지 남는다. 종전 코드는 이 경우 초기화했다. `restart_all.sh` 는 HUP 를 쓰지 않는다(critic 지적 2).
3. 소유 워커가 살아 있지만 파이프라인 스레드만 죽은 경우는 이 판정으로 구분하지 못한다. 종전에도 같은 상태가 남았다.

## 계획 검토 반영(critic ACCEPT-WITH-RESERVATIONS)

- 지적 1(재부팅 뒤 pid 재사용): `ownerPpid` 를 기록하고 보존 조건에 마스터 일치를 더했다. 주석은 「관리자 중단 요청이 푼다」로 고쳤다.
- 지적 2(HUP): 알려진 한계 2 로 기록.
- 지적 3(`OverflowError`): `except (OSError, OverflowError)` 로 막고 `2**40` 경우를 테스트에 넣었다.
- 지적 4(계획과 구현 불일치): 아래 스니펫을 `try/except` 를 유지한 구현에 맞췄다.
- 지적 5(잠금 미검증): `test_reset_orphaned_update_status_waits_for_status_file_lock` 을 더했다. 격리 사본에서 잠금을 지우면 이 테스트만 실패함을 확인했다.

---

### Task 1: ownerPid 기록과 소유자 생존 판정 초기화

**Files:**
- Modify: `services/common_update_status_service.py` (`start_update`, 새 `_owner_process_alive`·`reset_orphaned_update_status`)
- Modify: `app/__init__.py` (`_reset_startup_status_files` 의 update_status 블록)
- Test: `tests/app/test_app_startup_status_reset_refactor.py`, `tests/app/test_common_update_service.py`

- [ ] **Step 1: 실패하는 테스트**

```python
# tests/app/test_app_startup_status_reset_refactor.py
def _write_running_status(data_dir: Path, owner_pid) -> None:
    (data_dir / "update_status.json").write_text(
        json.dumps({"isRunning": True, "startTime": "2026-09-25T09:00:00", "ownerPid": owner_pid,
                    "items": [{"name": "Daily Prices", "status": "running"}]}),
        encoding="utf-8",
    )


def test_reset_startup_status_files_keeps_running_status_of_live_other_worker(monkeypatch, tmp_path: Path):
    # [INFRA-107] 워커 하나만 다시 뜨면 살아 있는 다른 워커의 실행을 지우지 않는다
    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_running_status(data_dir, os.getppid())

    app_module._reset_startup_status_files()

    status = json.loads((data_dir / "update_status.json").read_text(encoding="utf-8"))
    assert status["isRunning"] is True
    assert status["items"] == [{"name": "Daily Prices", "status": "running"}]


def test_reset_startup_status_files_resets_when_owner_dead_or_self(monkeypatch, tmp_path: Path):
    # [INFRA-107] 소유 워커가 죽었거나(전체 재기동) 자기 pid 이거나 bool 이면 종전처럼 초기화한다
    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()

    for owner_pid in (dead.pid, os.getpid(), True):
        _write_running_status(data_dir, owner_pid)
        app_module._reset_startup_status_files()
        status = json.loads((data_dir / "update_status.json").read_text(encoding="utf-8"))
        assert (status["isRunning"], status["items"]) == (False, []), owner_pid
```

```python
# tests/app/test_common_update_service.py (기존 start_update 테스트 옆)
def test_start_update_records_owner_pid(tmp_path):
    # [INFRA-107] 기동 초기화가 소유 워커 생존을 판정하도록 실행한 워커 pid 를 남긴다
    ...기존 kwargs 구성과 같은 방식으로 start_update 호출...
    assert json.loads(Path(status_file).read_text())["ownerPid"] == os.getpid()
```

- [ ] **Step 2: 실패 확인**

Run: `venv/bin/python -m pytest -q -p no:cacheprovider tests/app/test_app_startup_status_reset_refactor.py tests/app/test_common_update_service.py -k "owner or live_other"`
Expected: live_other 는 `isRunning` False 로 FAIL, owner_pid 는 KeyError 로 FAIL. dead_or_self 는 종전 동작과 같아 PASS 할 수 있다(회귀 고정용).

- [ ] **Step 3: 구현**

```python
# services/common_update_status_service.py
def _owner_process_alive(pid: Any) -> bool:
    """[INFRA-107] 상태를 연 워커가 아직 살아 있는가. 자기 pid 는 방금 뜬 워커이므로 옛 실행의 주인이 아니다."""
    if type(pid) is not int or pid <= 0 or pid == os.getpid():
        return False
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def reset_orphaned_update_status(*, update_status_file: str, logger) -> bool:
    """기동 때 주인이 사라진 실행 상태만 내린다. 다른 워커가 살아서 돌리는 실행은 그대로 둔다."""
    with _status_file_lock(update_status_file, logger):
        status = _read_status_file(update_status_file, logger)
        if not status.get("isRunning", False):
            return False
        # ponytail: pid 재사용이면 죽은 주인을 살아 있다고 본다. 그때는 중단 요청이나 다음 재기동이 푼다
        if status.get("ownerPpid") == os.getppid() and _owner_process_alive(status.get("ownerPid")):
            logger.info(f"Startup reset skipped: update owned by live worker {status.get('ownerPid')}")
            return False
        status["isRunning"] = False
        status["items"] = []
        save_update_status(status=status, update_status_file=update_status_file, logger=logger)
        return True
```

`start_update` 의 `status["startTime"] = ...` 다음 줄에 `status["ownerPid"] = os.getpid()` 와 `status["ownerPpid"] = os.getppid()` 를 더한다.

`app/__init__.py` 의 `if os.path.exists(common_status_file): ...` 블록을 다음으로 바꾼다.

```python
        # [INFRA-107] gunicorn 이 워커 하나만 다시 띄우면 다른 워커의 실행 중 상태를 지우지 않는다
        try:
            if reset_orphaned_update_status(
                update_status_file=common_status_file, logger=logging.getLogger(__name__)
            ):
                print("[Startup] 🧹 Reset stuck update_status.json")
        except Exception as error:
            print(f"[Startup] Error reading/writing update_status.json: {error}")
```

- [ ] **Step 4: 통과 확인**

Run: 위 Step 2 명령과 `tests/app/test_app_startup_status_reset_refactor.py` 전체
Expected: 모두 PASS

- [ ] **Step 5: 전체 회귀**

Run: `venv/bin/python -m pytest -q -p no:cacheprovider`
Expected: 실패 0
