# [INFRA-098] 수동 업데이트 상태 파일의 워커 간 직렬화 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `data/update_status.json` 을 읽고-수정-쓰는 네 함수가 gunicorn 워커 사이에서도 직렬화되어, 다른 워커의 중단 요청이 사라지지 않고 대체된 옛 실행이 새 실행을 끝내지 않게 한다.

**Architecture:** 기존 `update_lock`(프로세스 안 `threading.Lock`) 안쪽에 `<상태 파일>.lock` 의 `fcntl.flock(LOCK_EX)` 를 건다. 저장소의 `services/file_backed_status.py` 와 같은 방식이다. 잠금 안에서는 `(mtime_ns, size)` 시그니처 캐시와 SQLite 스냅샷을 거치지 않고 파일을 직접 읽는다. `finish_update` 는 `start_time` 인자를 받아 잠금 안에서 비교하고, 파이프라인 `finally` 의 바깥 비교는 지운다.

**Tech Stack:** Python 3.11 stdlib `fcntl`, pytest

**Spec:** 대화 설계(2026-09-25 07:34 승인, `docs/dev-cycle/TODO.md` `[INFRA-098]` 설계 승인 줄)

## Global Constraints

- 위험 경로 `services/common_update_status_service.py` → T3. 리뷰는 과잉설계 → 코드(`closing-bet-reviewer`) → 심층(`/review`) 순서
- 폴링 GET(`/system/update-status`)의 캐시 경로는 바꾸지 않는다
- 잠금 파일은 상태 파일 옆 `update_status.json.lock`. `data/` 원본은 테스트·QA 에서 건드리지 않는다(`tmp_path`·격리 사본만)
- pytest 는 `venv/bin/python -m pytest -q -p no:cacheprovider`

## Review Focus

1. 상태 파일이 깨졌거나 없을 때: 잠금 안 직접 읽기가 예외 없이 기본값으로 떨어지고 저장이 진행돼야 한다. 파일이 없거나 깨졌으면 종전 `load_update_status` 처럼 SQLite 스냅샷으로 폴백한다(심층 리뷰 I-1 반영)
2. 잠금 파일을 열 수 없을 때(권한·디렉터리 없음): `OSError` 를 로그로 남기고 워커 안 잠금만으로 진행한다. 예외를 내면 중단·완료 요청이 500 이 되고 `isRunning` 이 고착된다 → `test_mutation_proceeds_when_lock_file_unavailable`
3. 같은 프로세스의 두 스레드가 서로 다른 `threading.Lock` 을 써도 `flock` 이 서로를 막는지(열기마다 별도 open file description) → Task 1 테스트가 전제로 확인
4. `finish_update(start_time=None)` 은 종전처럼 항상 끝낸다(`startTime` 을 모르는 실행이 `isRunning` 을 고착시키지 않음)
5. 잠금 안 저장 뒤 캐시가 새 값으로 갱신돼 폴링 GET 이 곧바로 새 값을 읽는지(`save_update_status` 가 이미 캐시를 씀)

---

### Task 1: 상태 변경 네 함수의 파일 잠금과 직접 읽기

**Files:**
- Modify: `services/common_update_status_service.py` (`start_update`·`update_item_status`·`stop_update`·`finish_update`, 새 `_status_file_lock`·`_read_status_file`)
- Test: `tests/services/test_common_update_status_service.py`

**Interfaces:**
- Produces: `finish_update(*, update_lock, update_status_file, logger, start_time: str | None = None) -> None`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def _slow_save_between_read_and_write(monkeypatch, entered: threading.Event, release: threading.Event):
    original_save = status_service.save_update_status

    def _save(**kwargs):
        if threading.current_thread().name == "worker-a":
            entered.set()
            release.wait(2)
        original_save(**kwargs)

    monkeypatch.setattr(status_service, "save_update_status", _save)


def test_stop_from_other_worker_survives_item_update(monkeypatch, tmp_path: Path):
    # [INFRA-098] 워커마다 update_lock 이 따로다. 항목 저장 중에 끼어든 다른 워커의 중단이 덮이지 않아야 한다
    status_service.clear_update_status_cache()
    path = str(tmp_path / "update_status.json")
    status_service.save_update_status(
        status={"isRunning": True, "startTime": "run-1", "items": [{"name": "A", "status": "pending"}]},
        update_status_file=path,
        logger=_logger(),
    )
    entered, release = threading.Event(), threading.Event()
    _slow_save_between_read_and_write(monkeypatch, entered, release)

    a = threading.Thread(
        name="worker-a",
        target=lambda: status_service.update_item_status(
            name="A", status_code="running", update_lock=threading.Lock(),
            update_status_file=path, logger=_logger(), start_time="run-1",
        ),
    )
    a.start()
    assert entered.wait(2)
    b = threading.Thread(
        target=lambda: status_service.stop_update(update_lock=threading.Lock(), update_status_file=path, logger=_logger()),
    )
    b.start()
    time.sleep(0.2)  # 잠금이 없으면 b 는 이 사이에 저장을 끝낸다
    release.set()
    a.join(2)
    b.join(2)

    status_service.clear_update_status_cache()
    final = status_service.load_update_status(update_status_file=path, logger=_logger())
    assert final["stopRequested"] is True
    assert final["isRunning"] is False


def test_finish_from_replaced_run_leaves_new_run(tmp_path: Path):
    # [INFRA-098] 옛 실행의 finish 는 잠금 안에서 startTime 을 보고 새 실행을 끝내지 않는다
    status_service.clear_update_status_cache()
    path = str(tmp_path / "update_status.json")
    status_service.save_update_status(
        status={"isRunning": True, "startTime": "run-2", "items": []}, update_status_file=path, logger=_logger(),
    )
    status_service.finish_update(update_lock=threading.Lock(), update_status_file=path, logger=_logger(), start_time="run-1")
    assert status_service.load_update_status(update_status_file=path, logger=_logger())["isRunning"] is True
    status_service.finish_update(update_lock=threading.Lock(), update_status_file=path, logger=_logger(), start_time="run-2")
    assert status_service.load_update_status(update_status_file=path, logger=_logger())["isRunning"] is False


def test_mutation_reads_file_not_stale_signature_cache(tmp_path: Path):
    # [INFRA-098] 시그니처가 같은 옛 캐시가 있어도 상태 변경은 파일의 현재 값에서 출발한다
    status_service.clear_update_status_cache()
    path = tmp_path / "update_status.json"
    status_service.save_update_status(
        status={"isRunning": True, "startTime": "run-1", "stopRequested": False, "items": []},
        update_status_file=str(path), logger=_logger(),
    )
    signature = status_service._status_file_signature(str(path))
    stale = {"isRunning": True, "startTime": "run-0", "stopRequested": False, "items": []}
    with status_service._UPDATE_STATUS_CACHE_LOCK:
        status_service._UPDATE_STATUS_CACHE[status_service._normalize_update_status_file_key(str(path))] = (signature, stale)
    status_service.finish_update(update_lock=threading.Lock(), update_status_file=str(path), logger=_logger(), start_time="run-1")
    assert json.loads(path.read_text(encoding="utf-8"))["isRunning"] is False
```

- [ ] **Step 2: 실패 확인**

Run: `venv/bin/python -m pytest -q -p no:cacheprovider tests/services/test_common_update_status_service.py -k "other_worker or replaced_run or stale_signature"`
Expected: 3 FAIL (첫째 A 의 저장이 중단을 덮어 `stopRequested` 키 없음 — 단언은 `.get` 으로 쓴다, 둘째·셋째 `start_time` 인자 TypeError)

- [ ] **Step 3: 구현** (아래 코드는 첫 계획이다. 실제 구현은 끝의 「계획 검토 반영」·「리뷰 반영」 절이 우선한다: `logger` 인자, 잠금 파일 열기 `OSError` 처리, 스냅샷 폴백)

```python
import fcntl
from contextlib import contextmanager


@contextmanager
def _status_file_lock(update_status_file: str):
    """[INFRA-098] update_lock 은 워커 안에서만 듣는다. 상태를 읽고-수정-쓰는 동안 워커 사이도 막는다."""
    _ensure_parent_dir(update_status_file)
    with open(update_status_file + ".lock", "a+") as lock_fp:
        fcntl.flock(lock_fp.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_fp.fileno(), fcntl.LOCK_UN)


def _read_status_file(update_status_file: str, logger) -> Dict[str, Any]:
    """잠금 안에서 쓰는 읽기. (mtime, size) 캐시는 같은 틱의 다른 워커 저장을 놓치므로 파일을 직접 읽는다."""
    try:
        with open(update_status_file, "r", encoding="utf-8") as handle:
            loaded = json.load(handle)
    except FileNotFoundError:
        return default_update_status()
    except Exception as error:
        logger.error(f"Failed to load update status: {error}")
        return default_update_status()
    return loaded if isinstance(loaded, dict) else default_update_status()
```

네 함수는 `with update_lock:` 바로 안쪽에 `with _status_file_lock(update_status_file):` 를 두고, `load_update_status(...)` 호출을 `_read_status_file(update_status_file, logger)` 로 바꾼다. `finish_update` 에 `start_time: str | None = None` 을 더하고 읽은 뒤 `if start_time is not None and status.get("startTime") not in (None, start_time): return` 를 둔다(로그 한 줄).

- [ ] **Step 4: 통과 확인**

Run: 같은 명령
Expected: 3 passed

- [ ] **Step 5: 변이 확인** — `_status_file_lock` 의 `flock` 줄을 지우면 첫 테스트만 FAIL, `_read_status_file` 대신 `load_update_status` 를 쓰면 셋째만 FAIL 인지 본 뒤 복원

### Task 2: 파이프라인 `finally` 의 바깥 비교 제거와 호출부 연결

**Files:**
- Modify: `services/common_update_service.py` (`finally` 블록), `app/routes/common.py` (`finish_update` 에 `start_time` 전달)
- Test: `tests/app/test_common_update_service.py`

**Interfaces:**
- Consumes: Task 1 의 `finish_update(..., start_time=...)`
- 파이프라인이 받는 `finish_update` 는 종전처럼 인자 없는 콜러블이다. `app/routes/common.py` 의 `run_background_update` 가 `lambda: finish_update(start_time=run_start_time)` 로 넘긴다(`update_item_status` 와 같은 방식)

- [ ] **Step 1:** `test_run_background_update_pipeline_superseded_run_leaves_new_run_alone` 은 파이프라인이 판정을 하지 않게 되므로 `finished == [True]`(파이프라인은 항상 부르고 판정은 `finish_update` 가 한다)로 바꾸고, 판정 자체는 Task 1 의 `test_finish_from_replaced_run_leaves_new_run` 이 맡는다고 주석으로 남긴다. `STOP_REQUESTED is False` 단언은 유지
- [ ] **Step 2:** `finally` 를 `finish_update()` 한 줄로 바꾼다. `_read_start_time` 은 감시 스레드의 기준값에 계속 쓰므로 남긴다
- [ ] **Step 3:** `app/routes/common.py`: `finish_update(start_time=None)` 로 인자를 받게 하고 `run_background_update` 에서 `finish_update=lambda: finish_update(start_time=run_start_time)`. `/system/finish-update` 라우트는 인자 없이 부르므로 종전처럼 무조건 끝낸다
- [ ] **Step 4:** `venv/bin/python -m pytest -q -p no:cacheprovider tests/app/test_common_update_service.py tests/services/test_common_update_status_service.py tests/app/test_admin_gated_routes.py` → 전부 통과
- [ ] **Step 5:** pytest 전체, 커밋(구현·계획·TODO·QA 행렬)

## 알려진 한계

1. 폴링 GET 은 여전히 시그니처 캐시로 읽는다. 같은 틱·같은 크기의 저장을 놓치면 다음 저장까지 옛 값을 보여 줄 수 있다. 읽기 전용이라 상태를 되돌리지는 않는다
2. `fcntl` 은 POSIX 전용이다. 저장소가 이미 `services/file_backed_status.py` 에서 쓰며 운영은 Linux 다
3. `start_update` 의 `LOCAL_PIPELINE_ACTIVE` 판정은 워커별이다. 서로 다른 워커의 동시 시작은 이 잠금으로 직렬화되지만 둘 다 받아들여지는 것은 종전과 같다(늦게 쓴 쪽이 주인이 되고 옛 실행은 감시가 멈춘다)
4. (심층 리뷰 I-1 로 해소) 처음 계획은 잠금 안 읽기가 SQLite 스냅샷을 거치지 않았다. 파일이 없으면 `startTime` 없는 기본값에 중단을 저장해 실행 중인 워커의 감시가 중단을 알아보지 못했으므로 스냅샷 폴백을 넣었다
5. 감시 스레드(`_watch_stop_request`)도 시그니처 캐시로 읽는다. 같은 틱·같은 크기의 중단 저장을 놓치면 다음 항목 저장이 파일을 읽고 캐시를 갱신할 때까지 한 단계 늦게 멈춘다
6. `app/__init__.py` 의 `_reset_startup_status_files` 는 잠금 없이 읽고-수정-쓴다. 더 큰 문제는 새로 기동한 워커가 다른 워커에서 도는 실행의 `isRunning` 을 내린다는 점이어서 잠금으로 풀리지 않는다. `[INFRA-107]` 로 분리했다
7. 라우트가 `finish_update` 에 묶는 값은 `LOCAL_RUN_START_TIME` 이다. 이 값이 없으면 무조건 끝낸다. 종전 파이프라인은 그때 파일의 `startTime` 을 기준으로 삼았다. 현재 호출 경로(`api_start_update`·`kr_market_flow_service`)는 모두 `start_update` 를 먼저 부르므로 닿지 않는다
8. `flock` 을 쥔 채 fsync 와 SQLite 스냅샷 저장(busy timeout 5초)을 하고 `flock` 에는 타임아웃이 없다. 기다리는 워커는 `update_lock` 도 쥐므로 같은 워커의 폴링 GET 도 함께 기다린다. 평소 ms 단위이며, 폴링 지연이 관측되면 스냅샷 저장을 잠금 밖으로 뺀다

## 계획 검토 반영 (critic REVISE, 2026-09-25)

- 필수 1(잠금 파일 열기 실패가 예외로 올라감) → `OSError` 를 로그로 남기고 잠금 없이 진행, 실패 테스트 추가
- 필수 2(finish 와 다른 워커 start 의 경합을 지키는 테스트 없음, 변이 M3·M5 통과) → `test_finish_does_not_revert_start_from_other_worker` 추가, M3·M5 가 FAIL
- 권장 3(옛 캐시 테스트가 finish 만 봄, M4 통과) → finish·item·stop 세 경우로 parametrize
- 권장 4·5, 참고 6 → 알려진 한계 4·5·6, 참고 7 → Step 2 기대 문구 수정
- 구현 중 결정: 중첩 `with` 를 `with update_lock, _status_file_lock(...)` 한 줄로 합쳐 네 함수 본문의 들여쓰기 변경을 없앰

## 리뷰 반영 (2026-09-25)

- 코드 리뷰(closing-bet-reviewer): APPROVE, max low. low 1(`LOCAL_RUN_START_TIME` 없을 때 무조건 finish) → 한계 7, low 2(계획 코드 블록이 구현과 다름) → Step 3 에 우선 순위 주석, info 2건(무타임아웃 flock, 깨진 JSON) → 한계 8·I-1 로 해소
- 심층 리뷰(oh-my-claudecode:code-reviewer, opus): Critical 0, Important 1, Minor 4. I-1(파일 없을 때 중단이 전달되지 않음) → `_read_status_file` 이 스냅샷으로 폴백, `test_stop_without_status_file_keeps_run_identity_from_snapshot` RED→GREEN. M-1(`except` 안 `yield` 의 예외 연결) → 밖에서 `yield`. M-2(무타임아웃) → 한계 8. M-3(스레드 생존 미단언) → `is_alive` 단언. M-4(`start_time=None` 계약 테스트 없음) → 기존 테스트에 한 단계 추가
