# [INFRA-101] 대체된 옛 수동 업데이트가 새 실행의 항목 상태를 덮어쓰지 않게 한다 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 중단된 뒤 다른 워커의 새 실행에 대체된 옛 파이프라인이 남은 단계를 마치며 쓰는 `running`·`done`·`error` 가 새 실행의 같은 이름 항목에 쓰이지 않게 한다.

**Architecture:** `services/common_update_status_service.py` 의 `update_item_status` 에 선택 인자 `start_time=None` 을 둔다. 값이 있고 `update_lock` 안에서 읽은 상태의 `startTime` 과 다르면 저장하지 않고 INFO 로그만 남긴다. `app/routes/common.py` 의 `run_background_update` 는 진입 때 이 워커의 `shared_state.LOCAL_RUN_START_TIME`(직전 `start_update` 가 정한 이 실행의 값)을 읽어, 그 값을 묶은 인자 두 개짜리 콜백을 파이프라인에 넘긴다. 파이프라인과 단계 함수는 바뀌지 않는다.

**Tech Stack:** Python 3.11, pytest

**Spec:** 대화 설계(2026-09-25 06:30 승인), `docs/dev-cycle/TODO.md` `[INFRA-101]` 설계 승인 줄

## Global Constraints

- 파이프라인 콜백 계약(`Callable[[str, str], None]`)은 그대로다. `scripts/_run_full_update_test.py`, `scripts/init_data.py` 의 람다, 기존 테스트의 가짜 콜백을 고치지 않는다.
- 수동 API `api_update_item_status`(`app/routes/common_update_routes.py`)는 `start_time` 을 넘기지 않으므로 종전 동작이다.
- `LOCAL_RUN_START_TIME` 이 없으면(`None`) 확인하지 않는다(종전 동작).
- 프론트엔드 변경 없음. 해법 (b)(파이프라인이 콜백 전에 비교)는 범위 밖이다.
- 테스트와 QA 는 가짜 수집기만 쓴다. 실제 네트워크·KRX 로그인·LLM·원본 `data/` 쓰기는 금지.
- 운영 반영은 gunicorn 워커를 모두 재기동해야 한다(장 중 금지).

## Review Focus

- 비교와 쓰기는 같은 `update_lock` 안에서 한다. 잠금 밖에서 비교하면 해법 (b) 와 같아진다.
- `run_background_update` 는 `LOCAL_RUN_START_TIME` 을 콜백 호출마다가 아니라 진입 때 한 번 읽는다. 파이프라인 진입 뒤에는 `[INFRA-099]` 가 같은 워커의 새 시작을 거부하므로 값이 바뀌지 않지만, 진입 때 고정해 두면 그 가정에 기대지 않는다. 진입 전의 틈은 한계 3 이다.
- 새 실행이 같은 워커에서 시작돼 `startTime` 이 같아지는 경우는 없다(`[INFRA-099]` 거부). 옛 실행과 새 실행의 `startTime` 은 `datetime.now().isoformat()` 이라 마이크로초까지 같을 일은 사실상 없다.
- 거부된 쓰기는 `currentItem` 도 바꾸지 않아야 한다.
- `finish_update` 는 이미 `[INFRA-097]` 에서 `startTime` 으로 가려지므로 이 범위가 아니다.

## 알려진 한계

1. 워커 사이의 읽기-수정-쓰기는 직렬화되지 않는다(`update_lock` 은 프로세스 안 잠금). 옛 워커가 읽고 쓰는 수 ms 사이에 다른 워커의 `start_update` 가 쓰면 옛 워커의 저장이 새 실행 상태를 통째로 덮는다. `[INFRA-098]` 범위다.
2. 스케줄러 체인은 이 경로(`run_background_update`)를 거치지 않으며 항목 상태를 쓰지 않는다.
3. `start_update` 가 `True` 를 돌려준 뒤 스레드가 `run_background_update` 에 들어가기 전의 틈(`LOCAL_PIPELINE_ACTIVE` 는 파이프라인 진입 뒤에 켜진다)에서 다른 워커의 중단과 같은 워커의 재시작이 겹치면 `LOCAL_RUN_START_TIME` 이 새 실행 값으로 바뀌고, 옛 스레드도 그 값을 묶어 새 실행 항목에 쓴다. `services/common_update_service.py` 의 `_watch_stop_request` ponytail 주석이 인정한 틈과 같다. 막으려면 `start_update` 안에서 표시를 켜야 하며 승인 범위 밖이다(critic 지적 2).
4. 같은 실행 안의 중단 뒤 쓰기는 막지 않는다. `stop_update` 는 `startTime` 을 바꾸지 않으므로, 재시작이 없으면 옛 실행이 `cancelled`·`error` 를 `done` 으로 되돌리거나 `isRunning` 이 내려간 상태에 `currentItem` 을 다시 세울 수 있다. 수정 전과 같은 동작이며 QA 는 이것을 회귀로 보지 않는다(critic 지적 4).
5. 상태 파일과 SQLite 스냅샷이 모두 없으면 `startTime` 이 `None` 이라 `start_time` 이 있는 쓰기는 건너뛴다. 종전에는 빈 기본 상태를 저장했다. 이 실행이 상태의 주인임을 확인할 수 없는 경우라 해가 없는 쪽이다.

---

### Task 1: 항목 상태 쓰기를 자기 실행으로 한정

**Files:**
- Modify: `services/common_update_status_service.py` (`update_item_status` 에 `start_time` 인자와 비교)
- Modify: `app/routes/common.py` (`update_item_status` 래퍼가 `start_time` 을 넘김, `run_background_update` 가 묶은 콜백을 넘김)
- Test: `tests/app/test_common_update_service.py`

- [ ] **Step 1: 실패하는 테스트**

```python
def test_update_item_status_skips_write_for_replaced_run(tmp_path):
    # [INFRA-101] 상태의 startTime 이 다른 실행 것이면 항목·currentItem·파일을 바꾸지 않는다
    # 새 실행 B 의 상태를 저장 → update_item_status(..., start_time=A) 로 done·running 을 써도 상태(currentItem 포함)가 그대로
    # 같은 호출을 start_time=B 로 하면 바뀌고, start_time 없이 하면 바뀐다(종전 동작)
    ...

def test_route_run_background_update_binds_local_start_time(monkeypatch):
    # [INFRA-101] 래퍼가 진입 때의 LOCAL_RUN_START_TIME 을 묶은 콜백을 넘긴다
    # run_background_update_pipeline 을 가로채 받은 콜백을 부르고, update_item_status_impl 이 받은 start_time 을 확인
    # 콜백을 부르기 전에 LOCAL_RUN_START_TIME 을 바꿔도 진입 때 값이 넘어간다
    ...
```

- [ ] **Step 2: 실패 확인** — `venv/bin/python -m pytest tests/app/test_common_update_service.py -q -k "replaced_run or binds_local_start_time"`
  Expected: 2 failed (`TypeError: unexpected keyword argument 'start_time'` 등)

- [ ] **Step 3: 구현**

```python
# services/common_update_status_service.py
def update_item_status(*, name, status_code, update_lock, update_status_file, logger, start_time=None) -> None:
    with update_lock:
        status = load_update_status(update_status_file=update_status_file, logger=logger)
        if start_time is not None and status.get("startTime") != start_time:
            # [INFRA-101] 다른 워커의 새 실행에 대체된 옛 실행이다. 같은 이름의 새 항목에 쓰지 않는다
            logger.info(f"Item status skipped for replaced run: {name} -> {status_code}")
            return
        ...

# app/routes/common.py
def update_item_status(name, status_code, start_time=None):
    update_item_status_impl(..., start_time=start_time)

def run_background_update(target_date, selected_items=None, force=False):
    run_start_time = getattr(shared_state, "LOCAL_RUN_START_TIME", None)
    run_background_update_pipeline(
        ...,
        update_item_status=lambda name, status_code: update_item_status(name, status_code, start_time=run_start_time),
        ...
    )
```

- [ ] **Step 4: 통과 확인** — 같은 명령. Expected: 2 passed. 이어 `tests/app/test_common_update_service.py tests/services/test_common_update_status_service.py tests/app/test_admin_gated_routes.py` 통과
- [ ] **Step 5: 변이 검사** — 비교 분기 삭제, 래퍼가 `start_time` 을 넘기지 않음, 콜백이 호출 때 값을 읽음 세 변이마다 해당 테스트 FAIL 확인 뒤 복원
- [ ] **Step 6: pytest 전체** — `venv/bin/python -m pytest -q -p no:cacheprovider` exit 0

### QA (계획만, 실행은 dev-cycle [3])

`[INFRA-099]` QA S-3 실행기(`[INFRA-097]` 의 두 프로세스 하네스, 실제 `app.routes.common` 배선, 사본 `data/` 공유, 가짜 수집기, 소켓 차단)로 다른 워커 중단·재시작을 재현한다. 수정 전 사본은 새 실행의 `Daily Prices` 가 옛 실행 때문에 `done` 으로 보이고, 수정 뒤 사본은 새 실행의 항목이 새 실행 자신이 쓴 값만 가진다. 판정은 새 실행 `startTime` 아래의 항목으로 한정한다(한계 4). 옛 실행이 멈추는 시간(약 1초)과 최종 `isRunning`·`startTime` 은 회귀로 함께 본다.
