# [INFRA-096] 남은 사용자 중단 플래그를 끈다 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 관리자가 수동 업데이트를 중단한 뒤 `STOP_REQUESTED` 가 켜진 채로 남는 결함을, 같은 워커의 파이프라인이 끝날 때와 스케줄러 리더 워커의 17:00 체인이 시작할 때 끄는 것으로 막는다. 파이프라인이 없는 비리더 워커에 닿은 중단 요청이 남긴 값은 풀리지 않으며 `[INFRA-097]` 에서 다룬다(critic 지적 1).

**Architecture:** 끄는 곳을 두 군데 더한다. (1) 중단의 대상인 `run_background_update_pipeline` 이 끝날 때(`finally`) 끈다. (2) 무인 경로인 `run_daily_closing_analysis` 가 시작할 때 켜져 있으면 경고 로그와 함께 끈다. 파이프라인이 다른 워커에서 돌 때 리더 워커에 닿은 중단 요청이 남긴 값은 (1) 로 풀리지 않기 때문이다. 이 함수는 스케줄러 락을 가진 리더 워커에서만 돈다.

**Tech Stack:** Python 3.11, pytest

**Spec:** 대화 설계(2026-09-24 22:29 승인, `docs/dev-cycle/TODO.md` `[INFRA-096]` 설계 승인 줄)

## Global Constraints

- 새 설정·모듈·헬퍼를 만들지 않는다. `engine.shared` 모듈의 전역 값을 그대로 쓴다.
- `run_jongga_v2_analysis` 에는 넣지 않는다(등록된 잡이 아니고 체인 안에서 불린다).
- 워커 사이 중단 전달은 `[INFRA-097]` 범위라 건드리지 않는다.
- 테스트와 QA 는 가짜 수집기만 쓴다. 실제 네트워크·KRX 로그인·LLM·원본 `data/` 쓰기는 금지.
- 운영 반영은 gunicorn 워커를 모두 재기동해야 한다(장 중 금지).

## Review Focus

- 중단 없이 끝난 파이프라인과 중단 없이 시작한 스케줄러 체인의 동작은 바뀌지 않아야 한다(값이 이미 `False`).
- 파이프라인이 예외로 끝나도 `finally` 에서 값이 꺼져야 한다. `finish_update()` 가 예외를 던져도 값은 꺼져야 한다(끄는 줄을 먼저 둔다).
- 수동 업데이트 중단과 17:00 체인 시작이 같은 워커에서 겹치면 스케줄러가 값을 꺼 수동 작업이 계속될 수 있다. 알려진 한계로 `ponytail:` 주석에 적는다.
- (critic 지적 2) 중단된 스레드가 끝나기 전에 새 업데이트를 시작해 다시 중단하면, 옛 스레드의 `finally` 가 새 중단을 지운다. 겹침 자체는 기존 결함(`stop_update` 가 `isRunning` 을 먼저 내림)이라 `ponytail:` 주석과 `[INFRA-097]` 에 적는다.
- 스케줄러의 휴장일 조기 반환 갈래는 값을 끄지 않는다(수집이 돌지 않으므로 끌 이유가 없다).
- `scripts/init_data.py` 가 `engine.shared` 를 가져오지 못하면 `MockShared` 를 쓰지만 운영 경로는 같은 모듈 객체를 본다. 스케줄러도 `engine.shared` 를 직접 가져와 같은 객체를 끈다.

---

### Task 1: 중단 플래그를 끄는 두 지점

**Files:**
- Modify: `services/common_update_service.py` (`run_background_update_pipeline` 의 `finally`)
- Modify: `services/scheduler_jobs.py` (`run_daily_closing_analysis` 의 휴장일 판정 뒤)
- Test: `tests/app/test_common_update_service.py`, `tests/services/test_scheduler_jobs_refactor.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/app/test_common_update_service.py` 의 `test_run_background_update_pipeline_honors_stop_request` 끝에 더한다.

```python
    # [INFRA-096] 중단된 작업이 끝나면 중단 요청도 끝난다
    assert shared_state.STOP_REQUESTED is False
```

`tests/services/test_scheduler_jobs_refactor.py` 에 추가한다.

```python
def test_run_daily_closing_analysis_clears_stale_stop_request(monkeypatch):
    # [INFRA-096] 앞선 수동 업데이트 중단이 남긴 플래그가 17:00 수집을 막지 않는다
    import engine.shared as shared_state

    monkeypatch.setattr(scheduler_jobs, "set_scheduler_runtime_status", lambda **_kwargs: None)
    monkeypatch.setattr(scheduler_jobs.MarketSchedule, "is_market_open", lambda _date: True)
    monkeypatch.setattr(shared_state, "STOP_REQUESTED", True)
    seen: list[bool] = []
    monkeypatch.setattr(
        scheduler_jobs,
        "_load_init_data_functions",
        lambda: {
            "create_daily_prices": lambda: seen.append(shared_state.STOP_REQUESTED) or True,
            "create_institutional_trend": lambda: True,
            "create_signals_log": lambda run_ai: True,
            "send_jongga_notification": lambda: None,
        },
    )
    monkeypatch.setattr(
        scheduler_jobs, "run_jongga_v2_analysis", lambda test_mode=False, send_notification=True: True
    )

    scheduler_jobs.run_daily_closing_analysis(test_mode=True)

    assert seen == [False]
```

- [ ] **Step 2: 실패 확인**

Run: `venv/bin/python -m pytest tests/app/test_common_update_service.py tests/services/test_scheduler_jobs_refactor.py -q`
Expected: 두 테스트 FAIL (`STOP_REQUESTED is True`, `seen == [True]`)

- [ ] **Step 3: 최소 구현**

`services/common_update_service.py`:

```python
    finally:
        # [INFRA-096] 중단의 대상이던 작업이 끝났으므로 중단 요청도 끝낸다. 남겨 두면 스케줄러와 개별 실행이 멈춘다
        shared_state.STOP_REQUESTED = False
        finish_update()
```

`services/scheduler_jobs.py` 의 `run_daily_closing_analysis`, 휴장일 반환 뒤 `set_scheduler_runtime_status(data_scheduling_running=True, ...)` 앞:

```python
    # [INFRA-096] 다른 워커에 닿은 중단 요청이 남긴 플래그가 무인 수집을 막지 않게 한다
    # ponytail: 같은 워커에서 수동 업데이트 중단과 17:00 시작이 겹치면 수동 작업이 계속된다. 워커 간 중단 전달은 [INFRA-097]
    import engine.shared as shared_state

    if shared_state.STOP_REQUESTED:
        logger.warning("[Scheduler] 남아 있던 사용자 중단 요청을 해제하고 정기 분석을 시작합니다.")
        shared_state.STOP_REQUESTED = False
```

> critic 반영으로 구현은 위 블록과 조금 다르다. 스케줄러 주석은 「이 리더 워커에 남은 중단 요청」으로 좁혔고, `common_update_service.py` 에는 옛 스레드 `finally` 경합을 적은 `ponytail:` 주석을 더했으며, Step 1 스케줄러 테스트의 효과 없는 `is_market_open` 패치는 지웠다.

- [ ] **Step 4: 통과 확인**

Run: `venv/bin/python -m pytest tests/app/test_common_update_service.py tests/services/test_scheduler_jobs_refactor.py -q`
Expected: 전부 PASS

- [ ] **Step 5: 전체 확인**

Run: `venv/bin/python -m pytest -q`
Expected: 실패 0
