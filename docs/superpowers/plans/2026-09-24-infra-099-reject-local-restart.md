# [INFRA-099] 같은 워커에 끝나지 않은 수동 업데이트가 있으면 새 시작을 거부한다 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 중단된 수동 업데이트가 아직 도는 워커에 새 시작 요청이 닿으면 그 요청을 거부해, 옛 실행이 `[INFRA-097]` 감시로 멈추고 두 실행이 함께 돌지 않게 한다.

**Architecture:** 워커(프로세스)마다 `engine.shared.LOCAL_PIPELINE_ACTIVE` 를 둔다. `run_background_update_pipeline` 이 진입 때 켜고 `finally` 에서 끈다. `start_update` 는 `update_lock` 안에서 이 값을 보고 켜져 있으면 상태를 바꾸지 않고 `False` 를 돌려준다. 시작 경로 둘은 `False` 를 받으면 각자의 기존 「실행 중」 응답을 돌려준다. 거부되면 상태의 `startTime` 은 옛 실행 것 그대로이고 `stopRequested` 는 `True` 로 남으므로, 옛 실행의 감시가 1초 안에 플래그를 켜 멈춘다.

**Tech Stack:** Python 3.11, pytest

**Spec:** 대화 설계(2026-09-24 23:11 승인), `docs/dev-cycle/TODO.md` `[INFRA-099]` 설계 승인 줄

## Global Constraints

- 프론트엔드 변경 없음. 응답 코드와 문구는 경로별 기존 「실행 중」 응답을 그대로 쓴다(`/system/start-update` 400 "Already running", `launch_background_update_job` 409 "Update already in progress").
- 해법 (b)(`stop_update` 가 `isRunning` 을 내리지 않음)는 범위 밖이다.
- 표시는 `start_update` 가 아니라 파이프라인 진입에서 켠다. 스레드가 뜨지 못해 표시가 켜진 채 남으면 그 워커는 재기동 전까지 시작을 모두 거부하기 때문이다.
- 테스트와 QA 는 가짜 수집기만 쓴다. 실제 네트워크·KRX 로그인·LLM·원본 `data/` 쓰기는 금지.
- 운영 반영은 gunicorn 워커를 모두 재기동해야 한다(장 중 금지).

## Review Focus

- 거부는 같은 워커의 실행에만 걸린다. 다른 워커로 간 재시작은 받아들여지고 옛 실행은 `[INFRA-097]` 의 대체 판정으로 멈춘다(바뀌지 않음).
- 파이프라인이나 `finish_update` 가 예외로 끝나도 표시를 끈다. 끄지 않으면 그 워커는 재기동 전까지 시작을 거부한다. 표시는 중첩한 `finally` 의 바깥에서 상태 정리(`finish_update`) 뒤에 끈다. 먼저 끄면 같은 워커의 새 시작이 끼어들어 옛 실행의 `finish_update` 가 새 실행 상태를 끝낼 수 있다(critic 지적 a).
- `start_update` 호출과 파이프라인 진입 사이의 틈: 그 사이의 같은 워커 시작은 공유 상태의 `isRunning=True` 로 호출자에서 먼저 거부된다. 그 틈에 중단까지 겹치면(ms 단위) 두 실행이 함께 돌 수 있다(알려진 한계).
- 호출자는 `is False` 로 거부를 판정한다. 기존 테스트의 가짜 `start_update` 가 `None` 을 돌려주므로 `not` 으로 판정하면 정상 시작이 거부로 바뀐다.
- 거부 뒤 상태 파일은 바뀌지 않아야 한다(`stopRequested` 가 남아야 옛 실행이 멈춘다).

## 알려진 한계

1. 시작 요청 처리와 스레드 진입 사이의 틈은 남는다. 호출자의 `isRunning` 검사가 `update_lock` 밖이라, 중단이 없어도 같은 워커에 시작 요청 둘이 몇 ms 차이로 오면 둘 다 받아들여진다(수정 전부터 있던 경합, critic 지적 c). 표시는 개수를 세지 않으므로 그렇게 두 실행이 돌면 먼저 끝난 쪽이 표시를 꺼 그 뒤 재시작이 다시 받아들여진다(critic 지적 d).
2. 사용자는 중단 직후 재시작이 같은 워커에 닿으면 「실행 중」 오류를 보고 옛 실행이 끝난 뒤 다시 눌러야 한다. 거부가 이어지는 시간은 1초가 아니라 옛 실행이 다음 중단 확인 지점에 닿을 때까지다. 한 단계가 돌아오지 않으면(타임아웃 없는 외부 호출, 긴 LLM 배치) 화면은 대기 상태인데 그 워커에 닿은 시작만 계속 거부되고, 워커가 둘이면 같은 버튼이 요청마다 성공·실패가 갈린다. 거부 때 `Update start refused` 경고를 남기며 복구 수단은 그 워커의 재기동이다(critic 지적 b). 수정 전에는 같은 워커 재시작이 받아들여졌으므로 이 경우는 새 동작이다. 데이터 상태 화면은 400 을 중복 모달이 아닌 일반 오류로 띄운다(`[INFRA-100]`).
3. 워커 사이 상태 파일 lost update 는 `[INFRA-098]`.

---

### Task 1: 같은 워커 재시작 거부

**Files:**
- Modify: `engine/shared.py` (`LOCAL_PIPELINE_ACTIVE = False`)
- Modify: `services/common_update_service.py` (진입 때 켜고 `finally` 에서 끔, `[INFRA-097]` 주석 정리)
- Modify: `services/common_update_status_service.py` (`start_update` 가 `bool` 반환)
- Modify: `app/routes/common.py` (`start_update` 가 결과를 돌려줌)
- Modify: `app/routes/common_update_routes.py` (`api_start_update` 거부 시 400)
- Modify: `services/kr_market_flow_service.py` (`launch_background_update_job` 거부 시 409)
- Test: `tests/app/test_common_update_service.py`, `tests/app/test_kr_market_flow_service.py`, `tests/app/test_admin_gated_routes.py`

- [x] **Step 1: 실패하는 테스트**

```python
def test_start_update_refuses_while_local_pipeline_active(tmp_path):
    # 표시가 켜져 있으면 False, 상태 파일(startTime·stopRequested·items) 그대로, LOCAL_RUN_START_TIME 그대로
    ...

def test_run_background_update_pipeline_marks_local_pipeline_active(monkeypatch):
    # 수집기 안에서 shared_state.LOCAL_PIPELINE_ACTIVE 가 True, 수집기 예외 뒤에도 끝나면 False
    ...

def test_run_background_update_pipeline_clears_local_pipeline_after_finish_even_if_it_fails(monkeypatch):
    # finish_update 가 불릴 때 표시는 아직 True, finish_update 가 예외를 내도 끝나면 False (critic 지적 a 로 추가)
    ...

def test_launch_background_update_job_rejects_when_start_update_refuses():
    # start_update 가 False 를 돌려주면 409, run_background_update 는 불리지 않음
    ...

def test_start_update_route_rejects_when_start_update_refuses(monkeypatch):
    # 관리자 요청, ctx.start_update 가 False → 400 "Already running", 스레드 없음
    ...
```

- [x] **Step 2: 실패 확인** — `venv/bin/python -m pytest <위 네 테스트> -q` 4 failed. critic 지적 a 의 순서 테스트는 추가 뒤 `assert [False] == [True]` 로 1 failed
- [x] **Step 3: 구현**

```python
# services/common_update_status_service.py
def start_update(...) -> bool:
    with update_lock:
        if getattr(shared_state, "LOCAL_PIPELINE_ACTIVE", False):
            return False
        ...  # 종전 그대로
        return True

# services/common_update_service.py (run_background_update_pipeline)
    try:
        shared_state.LOCAL_PIPELINE_ACTIVE = True
        ...
    finally:
        try:
            ...  # 종전 finally 그대로(감시 종료, 플래그 해제, finish_update)
        finally:
            shared_state.LOCAL_PIPELINE_ACTIVE = False

# 호출자
if ctx.start_update(items_list) is False:
    return jsonify({"status": "error", "message": "Already running"}), 400
```

- [x] **Step 4: 통과 확인과 변이 검사** — 관련 세 파일 53 passed. 표시 켜기·끄기·`start_update` 거부·두 호출자의 거부 분기를 각각 되돌리면 해당 테스트 1 failed
- [ ] **Step 5: 전체 확인** — `venv/bin/python -m pytest -q` 전부 통과
