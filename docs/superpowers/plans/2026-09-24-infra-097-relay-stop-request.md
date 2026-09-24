# [INFRA-097] 관리자 중단 요청을 작업이 도는 워커에 전달한다 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> 이 계획은 T3 판정이 첫 커밋(`3a87c29`) 뒤에 나와 **구현 뒤에 작성한 사후 계획**이다. Task 1 은 첫 커밋, Task 2 는 QA S-3 실패로 추가 승인받은 수정이다. 계획 검토(critic)와 `/review` 는 이 문서와 실제 diff 를 함께 본다.

**Goal:** 관리자 `stop-update` 요청이 어느 gunicorn 워커에 닿든, 수동 업데이트를 돌리는 워커의 `STOP_REQUESTED` 가 켜져 작업이 멈추고, 요청을 받은 워커에는 값이 남지 않게 한다.

**Architecture:** 중단 요청을 프로세스 메모리가 아니라 모든 워커가 함께 쓰는 업데이트 상태(`update_status.json` 과 SQLite 스냅샷)의 `stopRequested` 에 남긴다. 파이프라인을 돌리는 워커는 감시 스레드가 1초마다 상태를 읽어 자기 실행(같은 `startTime`)이 중단됐거나 다른 워커의 새 실행으로 대체됐으면 자기 플래그를 켠다. 플래그를 읽는 쪽(`init_data` 루프, 종가베팅 단계, VCP AI)은 고치지 않는다.

**Tech Stack:** Python 3.11, pytest

**Spec:** 대화 설계(2026-09-24 22:48 승인, 22:58 S-3 수정 추가 승인), `docs/dev-cycle/TODO.md` `[INFRA-097]` 설계 승인 줄

## Global Constraints

- 프론트엔드와 라우트 응답 형식은 바꾸지 않는다(상태 응답에 `stopRequested` 필드만 늘어난다).
- 중단 버튼은 수동 업데이트만 멈춘다. 17:00 체인은 상태 파일을 쓰지 않으므로 감시 대상이 아니다.
- 반영 지연은 감시 주기(`STOP_WATCH_INTERVAL_SECONDS = 1.0`)만큼이다.
- 상태를 읽지 못하면 종전 동작(감시 없음, 끝날 때 항상 `finish_update`)으로 돌아간다. `isRunning` 이 고착되면 재기동 전까지 모든 시작이 막히기 때문이다.
- 테스트와 QA 는 가짜 수집기만 쓴다. 실제 네트워크·KRX 로그인·LLM·원본 `data/` 쓰기는 금지.
- 운영 반영은 gunicorn 워커를 모두 재기동해야 한다(장 중 금지).

## Review Focus

- 옛 실행이 끝날 때 그 워커에 플래그가 남지 않아야 한다(`[INFRA-096]` 증상 재발 금지). `finally` 는 플래그를 조건 없이 끈다.
- 옛 실행이 다른 워커의 새 실행 상태를 끝내면 안 된다. `startTime` 이 다르면 `finish_update` 만 건너뛴다.
- 새 실행이 같은 워커에서 시작됐으면 플래그를 함께 쓰므로 옛 실행을 멈추려다 새 실행까지 멈추면 안 된다(`LOCAL_RUN_START_TIME` 으로 구분, 옛 실행은 계속 도는 알려진 한계).
- 감시 스레드가 `finally` 의 해제 뒤에 값을 다시 켜면 안 된다(`join`).
- 워커 사이 상태 파일 읽기-수정-쓰기 경합(lost update)은 기존 결함이며 `[INFRA-098]` 로 분리했다.
- 워커 기동 시 상태 초기화(`app/__init__.py:104-110`)는 `isRunning`·`items` 만 지우고 `startTime`·`stopRequested` 를 남긴다. 감시 판정은 깨지지 않지만, 도는 실행의 `isRunning` 을 내려 새 시작을 받아들이게 하므로 아래 한계 1 의 트리거가 된다(critic).
- 17:00 체인과의 상호작용: 체인은 감시 대상이 아니지만, 리더 워커에서 도는 옛 실행이 중단되거나 다른 워커의 새 실행에 대체되면 그 감시가 리더 워커의 플래그를 켜 체인도 옛 실행이 끝날 때까지 멈출 수 있다(`scheduler_jobs.py` 주석과 같음).
- 감시가 켠 플래그는 옛 실행이 끝날 때까지 그 워커의 VCP 백그라운드·종가베팅 개별 실행(`engine/phases_base.py:30`, `engine/kr_ai_analyzer.py:165`)도 막는다. 옛 실행이 중단 확인이 없는 긴 단계(LLM 배치, pykrx 요청)에 있으면 그 시간만큼 이어진다.

## 알려진 한계

1. 중단 뒤 옛 실행이 끝나기 전에 **같은 워커**에서 새 실행이 시작되면 옛 실행은 멈추지 않고 새 실행과 함께 돈다(같은 CSV 동시 쓰기, AI 단계면 LLM 비용 중복). 수정 전에는 같은 워커 중단이 플래그를 곧바로 켰으므로 재시작 전에 중단 확인 지점을 지나면 멈췄지만, 이제는 1초 감시 주기 안에 재시작하면 멈추지 않는다. `[INFRA-099]` (critic 지적 1, QA S-4).
2. 두 워커가 거의 동시에 시작을 받아들이는 경합(시작 확인이 워커 사이에 원자적이지 않음)은 남는다. 파이프라인은 자기 `startTime` 을 `LOCAL_RUN_START_TIME` 에서 먼저 읽으므로(critic 지적 2·`/review` 지적 2 반영) 두 실행이 같은 신원을 갖지 않고, 먼저 쓴 쪽이 대체된 것으로 보여 멈춘다(마지막 쓰기가 이긴다).
3. 중단 없이 `startTime` 이 바뀌는 경우(위 2, 워커 재기동 뒤 새 시작)에도 옛 실행이 멈추며 로그는 「Background Update Stopped」로 사용자 중단과 구분되지 않는다(코드 리뷰 low).
4. 워커 사이 상태 파일 lost update 는 `[INFRA-098]`.

---

### Task 1: 공유 상태로 중단 요청 전달 (커밋 `3a87c29`)

**Files:**
- Modify: `services/common_update_status_service.py` (`start_update` 가 `stopRequested=False`, `stop_update` 가 `stopRequested=True` 를 쓰고 메모리 플래그를 켜지 않음, 쓰지 않는 `shared_state` 인자 삭제)
- Modify: `services/common_update_service.py` (`_read_start_time`, `_watch_stop_request`, `run_background_update_pipeline(load_update_status=...)`, `finally` 의 `join`·무조건 해제·`startTime` 가드)
- Modify: `app/routes/common.py` (`load_update_status` 배선, `stop_update_impl` 인자)
- Modify: `services/scheduler_jobs.py` (주석만)
- Test: `tests/app/test_common_update_service.py`, `tests/app/test_admin_gated_routes.py`(독스트링)

- [x] **Step 1: 실패하는 테스트** — `test_stop_update_records_request_in_shared_status_not_local_flag`, `test_run_background_update_pipeline_sees_stop_request_from_other_worker`, `test_run_background_update_pipeline_superseded_run_leaves_new_run_alone`
- [x] **Step 2: 실패 확인** — `3 failed, 5 passed`
- [x] **Step 3: 구현**
- [x] **Step 4: 리뷰 반영** — `test_run_background_update_pipeline_without_start_time_still_finishes` 추가
- [x] **Step 5: 통과 확인** — `venv/bin/python -m pytest -q` 2759 passed, 2 skipped

### Task 2: 감시가 읽기 전에 대체된 실행도 멈춘다 (QA S-3, 22:58 추가 승인)

**Files:**
- Modify: `engine/shared.py` (`LOCAL_RUN_START_TIME = None`)
- Modify: `services/common_update_status_service.py` (`start_update` 가 `shared_state.LOCAL_RUN_START_TIME` 기록)
- Modify: `services/common_update_service.py` (`_watch_stop_request` 의 대체 판정)
- Test: `tests/app/test_common_update_service.py`

- [x] **Step 1: 실패하는 테스트**

```python
def test_run_background_update_pipeline_stops_when_superseded_by_other_worker(monkeypatch):
    assert _run_superseded_before_first_poll(monkeypatch, local_run_start_time="run-1") == [True]


def test_run_background_update_pipeline_superseded_by_local_run_keeps_shared_flag(monkeypatch):
    assert _run_superseded_before_first_poll(monkeypatch, local_run_start_time="run-2") == [False]
```

- [x] **Step 2: 실패 확인** — `2 failed, 9 passed`
- [x] **Step 3: 구현**

```python
        current = status.get("startTime")
        if current == start_time:
            stopped = bool(status.get("stopRequested"))
        else:
            stopped = current is not None and current != getattr(shared_state, "LOCAL_RUN_START_TIME", None)
        if stopped:
            shared_state.STOP_REQUESTED = True
```

- [x] **Step 4: 통과 확인** — `venv/bin/python -m pytest tests/app/test_common_update_service.py -q` 11 passed, 변이 검사 두 갈래 각각 FAIL
- [x] **Step 5: 전체 확인** — `venv/bin/python -m pytest -q` 2761 passed, 2 skipped. critic·`/review` 반영(LOCAL 우선 읽기, 테스트 셋) 뒤 2764 passed, 2 skipped
