# [INFRA-116] 17시 스케줄러 체인의 종가베팅 분석이 수동 V2 실행과 실행권을 나눈다 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 스케줄러의 `run_jongga_v2_analysis` 와 관리자 수동 실행(`POST /api/kr/jongga-v2/run`)이 같은 시각에 종가베팅 분석을 두 번 돌리지 않게 한다. 체인이 도는 중의 수동 요청은 409, 수동 실행 중에 시작한 체인은 끝나기를 기다린 뒤 실행한다.

**Architecture:** 실행권의 정본을 기존 `data/v2_screener_status.json` 하나로 둔다. 수동 경로는 `[INFRA-115]` 에서 `_status_file_lock` 안의 캐시 없는 읽기(`read_v2_status_uncached`)로 확인·저장한다. 스케줄러도 같은 잠금·읽기로 `isRunning` False 일 때만 True 를 저장하고 `finally` 에서 False 로 내린다. 저장 함수는 라우트 클로저에서 `services/kr_market_jongga_runtime_service.py` 의 `write_v2_status` 로 옮겨 두 경로가 같은 형식(`isRunning`·`updated_at`·`ownerPid`·`ownerPpid`)을 쓴다. 라우트의 판정 코드는 바꾸지 않는다.

**Tech Stack:** Python 3.11, pytest

**Spec:** 대화 설계(2026-09-25 14:19 승인, 「이 설계로 진행 (Recommended)」: 수동 실행 중이면 최대 30분 기다린 뒤 실행), `docs/dev-cycle/TODO.md` `[INFRA-116]` 설계 승인 줄

## Global Constraints

- 티어 T3: `services/scheduler_jobs.py` 가 tier-rules §2 「스케줄러와 데이터 적재」에 있다.
- 경로는 `os.path.join("data", "v2_screener_status.json")` 이다. 라우트(`DATA_DIR = 'data'`)와 기동 초기화(`app/__init__.py`)가 모두 cwd 기준 `data` 를 쓰므로 같게 맞춘다.
- 대기는 10초 간격, 최대 30분이다. 초과하면 오류 로그를 남기고 `False` 를 돌려준다. 체인은 기존 분기대로 「종가베팅 부분 실패」를 기록하고 알림을 건너뛴다.
- 휴장일 분기는 실행권을 잡지 않는다(종전과 같이 곧바로 `False`).
- 테스트는 원본 `data/` 에 쓰지 않는다. 기존 `run_jongga_v2_analysis` 테스트도 `V2_STATUS_FILE` 을 `tmp_path` 로 돌린다.
- 공개 응답 계약 불변: `/api/kr/jongga-v2/status` 응답에 pid 가 나가지 않는다(기존 테스트가 고정).
- 운영 반영은 gunicorn 워커 전부 재기동(장 중 금지).

## Review Focus

- 분석 중 예외: `create_jongga_v2_latest` 가 던져도 `finally` 가 V2 상태를 False 로 되돌려야 한다. 실행권을 잡지 못한 경우에는 남의 True 를 지우면 안 된다.
- 대기 중에 수동 실행이 끝나면 다음 확인에서 실행권을 잡는다. 대기 로그는 한 번만 남긴다(10초마다 찍지 않는다).
- 스케줄러가 쥔 True 는 소유자 pid 가 리더 워커다. 다른 워커만 재기동되면 `[INFRA-114]` 판정으로 보존되고, 리더가 죽으면 기동 초기화가 내린다.
- 라우트 저장 경로가 바뀐 뒤에도 기존 라우트 테스트(원자적 저장, pid 기록, 상태 응답)가 그대로 통과해야 한다. 패치 대상 모듈만 옮긴다.
- 체인 대기 중 `is_jongga_scheduling_running` 은 이미 True 라 상태 조회는 「스케쥴링 진행 중」을 보인다(종전과 같음).

## 알려진 한계

1. 주인이 죽은 채 남은 `isRunning` True 는 종전처럼 전체 재기동으로만 풀린다. 그 경우 체인은 30분을 기다린 뒤 종가베팅을 건너뛴다.
2. 수동 실행이 30분을 넘기면 그날 체인의 종가베팅은 건너뛴다. 수동 실행이 끝나며 자기 알림을 보낸다(발송 가드는 같은 날짜·시그널의 중복만 막는다).
3. 수동 경로는 끝날 때 False 를 잠금 없이 두 번 쓴다. 대기 중인 체인이 그 사이에 실행권을 잡으면 두 번째 False 가 덮는다(critic 지적). 범위 밖이라 `[INFRA-118]` 로 등록했다.
4. 주인이 살아 있어 보이는 낡은 True(graceful 재기동의 옛 워커, 같은 마스터 안 pid 재사용)도 1과 같이 매일 체인의 종가베팅을 막는다. 종전에는 수동 409 만 굳었다(심층 리뷰 중간 1). `owned_by_live_sibling` 의 ponytail 주석을 갱신했고, `updated_at` 으로 낡은 값을 판정하는 선택지는 `[INFRA-118]` 설계로 넘긴다.
5. 스케줄러는 잡을 스레드 하나에서 동기로 돌리므로 대기 동안 Market Gate 동기화와 분당 가격 동기화 복구도 최대 30분 늦어진다(두 리뷰 low). 체인이 이미 그 스레드를 오래 붙잡고 있고 장 마감 뒤다.
6. 대기 중에도 `/jongga-v2/status` 는 「종가베팅 스케쥴링 진행 중인 상태」를 보인다(`isRunning` 은 어느 쪽이든 True).

## 계획 검토 반영(critic ACCEPT-WITH-RESERVATIONS)

- Step 2 기대값: autouse fixture 가 없는 속성을 패치하면 전 테스트가 ERROR 다 → `raising=False` 를 붙였다.
- 테스트 파일 import(`json`·`Path`·`itertools`·`logging`) 추가.
- 대기 테스트는 sleep 1회와 분석 중 True 를 확인한다. 한도 테스트는 `itertools.count(0, 600)` 와 sleep 2회를 확인한다(`range` 고갈의 StopIteration 이 `except Exception` 에 삼켜지는 거짓 통과 방지).
- 체인이 실행권을 쥔 동안 실제 `launch_jongga_v2_screener` 가 409 인지, 휴장일 분기가 파일을 만들지 않는지 확인하는 테스트를 더했다.
- 수동 경로의 이중 False: 알려진 한계 3, `[INFRA-118]`.

## 코드 리뷰 반영

- `closing-bet-reviewer` APPROVE(최고 low), T3 심층 리뷰(`oh-my-claudecode:code-reviewer`) 중간 1·낮음 3.
- 저장 실패인데 실행권을 잡은 것으로 처리(두 리뷰 low): `write_v2_status` 가 bool 을 돌려주고 `_claim_v2_run` 이 그 값을 쓴다. `test_run_jongga_v2_analysis_does_not_run_when_claim_write_fails` 수정 전 실패 확인.
- fixture `raising=False` 가 상수 개명 때 원본 `data/` 쓰기를 숨김(심층 low 4): 제거.
- 낡은 True 가 체인도 막음(심층 중간 1), 대기 동안 스케줄러 루프 정지(low), 대기 중 상태 문구(참고): 알려진 한계 4~6.

---

### Task 1: `write_v2_status` 를 런타임 서비스로 옮기고 라우트가 쓰게 한다

**Files:**
- Modify: `services/kr_market_jongga_runtime_service.py`
- Modify: `app/routes/kr_market_jongga_execution_routes.py:38-55`
- Test: `tests/app/test_kr_market_jongga_execution_routes_refactor.py` (`test_run_jongga_v2_screener_route_persists_status_with_atomic_writer` 의 패치 대상만 바꿈)

**Interfaces:**
- Produces: `write_v2_status(v2_status_file: str, running: bool, logger: logging.Logger) -> None`

- [ ] **Step 1: 기존 테스트의 패치 대상을 새 모듈로 바꾼다**

```python
    import services.kr_market_jongga_runtime_service as runtime_module
    ...
    monkeypatch.setattr(runtime_module, "atomic_write_text", _atomic_write)
```

- [ ] **Step 2: 실행해 실패를 확인한다**

Run: `venv/bin/python -m pytest -q -p no:cacheprovider tests/app/test_kr_market_jongga_execution_routes_refactor.py -k atomic_writer`
Expected: FAIL (`runtime_module` 에 `atomic_write_text` 가 없어 AttributeError)

- [ ] **Step 3: 구현**

```python
# services/kr_market_jongga_runtime_service.py
from services.kr_market_data_cache_service import atomic_write_text

def write_v2_status(v2_status_file: str, running: bool, logger: logging.Logger) -> None:
    """[INFRA-116] 수동 실행과 스케줄러 체인이 같은 형식으로 V2 실행권을 기록한다."""
    try:
        atomic_write_text(
            v2_status_file,
            json.dumps(
                {
                    "isRunning": running,
                    "updated_at": datetime.now().isoformat(),
                    # [INFRA-114] 기동 초기화가 소유 워커 생존을 판정하도록 남긴다
                    "ownerPid": os.getpid(),
                    "ownerPpid": os.getppid(),
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception as error:
        logger.error(f"Failed to save V2 status: {error}")
```

라우트의 `_save_v2_status` 본문은 `write_v2_status(v2_status_file, running, logger)` 한 줄로 바꾸고, 쓰지 않게 된 import 를 지운다.

- [ ] **Step 4: 라우트·런타임 테스트 통과 확인**

Run: `venv/bin/python -m pytest -q -p no:cacheprovider tests/app/test_kr_market_jongga_execution_routes_refactor.py tests/services/test_kr_market_jongga_runtime_service_refactor.py`
Expected: PASS

### Task 2: 스케줄러가 V2 실행권을 기다려 잡고 끝나면 내린다

**Files:**
- Modify: `services/scheduler_jobs.py`
- Test: `tests/services/test_scheduler_jobs_refactor.py`

**Interfaces:**
- Consumes: `write_v2_status`, `read_v2_status_uncached`, `_status_file_lock`
- Produces: 모듈 상수 `V2_STATUS_FILE`, `V2_WAIT_SECONDS = 30 * 60`, `V2_POLL_SECONDS = 10`

- [ ] **Step 1: 실패하는 테스트 세 건과 autouse 경로 치환**

```python
@pytest.fixture(autouse=True)
def _isolated_v2_status(monkeypatch, tmp_path):
    # 원본 data/ 에 쓰지 않는다
    monkeypatch.setattr(scheduler_jobs, "V2_STATUS_FILE", str(tmp_path / "v2_screener_status.json"))


def _open_market_scheduler(monkeypatch, create):
    monkeypatch.setattr(scheduler_jobs, "set_scheduler_runtime_status", lambda **_kwargs: None)
    monkeypatch.setattr(scheduler_jobs.MarketSchedule, "is_market_open", lambda _date: True)
    monkeypatch.setattr(
        scheduler_jobs,
        "_load_init_data_functions",
        lambda: {"create_jongga_v2_latest": create, "send_jongga_notification": lambda: None},
    )


def _v2_running() -> bool:
    return json.loads(Path(scheduler_jobs.V2_STATUS_FILE).read_text(encoding="utf-8"))["isRunning"]


def test_run_jongga_v2_analysis_holds_v2_run_claim_during_analysis(monkeypatch):
    seen = []

    def _create():
        seen.append(_v2_running())
        raise RuntimeError("boom")

    _open_market_scheduler(monkeypatch, _create)
    assert scheduler_jobs.run_jongga_v2_analysis(send_notification=False) is False
    assert seen == [True]
    assert _v2_running() is False


def test_run_jongga_v2_analysis_waits_for_manual_run_then_runs(monkeypatch):
    Path(scheduler_jobs.V2_STATUS_FILE).write_text('{"isRunning": true}', encoding="utf-8")
    calls = {"analyze": 0}

    def _manual_finishes(_seconds):
        Path(scheduler_jobs.V2_STATUS_FILE).write_text('{"isRunning": false}', encoding="utf-8")

    monkeypatch.setattr(scheduler_jobs.time, "sleep", _manual_finishes)
    _open_market_scheduler(monkeypatch, lambda: calls.__setitem__("analyze", 1) or True)
    assert scheduler_jobs.run_jongga_v2_analysis(send_notification=False) is True
    assert calls["analyze"] == 1
    assert _v2_running() is False


def test_run_jongga_v2_analysis_skips_after_wait_limit_and_keeps_manual_claim(monkeypatch):
    Path(scheduler_jobs.V2_STATUS_FILE).write_text('{"isRunning": true}', encoding="utf-8")
    clock = iter(range(0, 10_000, 600))  # 한 번 확인할 때마다 10분 흐른다
    monkeypatch.setattr(scheduler_jobs.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(scheduler_jobs.time, "sleep", lambda _seconds: None)
    calls = {"analyze": 0}
    _open_market_scheduler(monkeypatch, lambda: calls.__setitem__("analyze", 1) or True)
    assert scheduler_jobs.run_jongga_v2_analysis(send_notification=False) is False
    assert calls["analyze"] == 0
    assert _v2_running() is True  # 남의 실행권을 지우지 않는다
```

- [ ] **Step 2: 실행해 세 건 실패 확인**

Run: `venv/bin/python -m pytest -q -p no:cacheprovider tests/services/test_scheduler_jobs_refactor.py`
Expected: 새 세 건 FAIL (`V2_STATUS_FILE` 없음), 기존 건 PASS

- [ ] **Step 3: 구현**

```python
V2_STATUS_FILE = os.path.join("data", "v2_screener_status.json")
V2_WAIT_SECONDS = 30 * 60
V2_POLL_SECONDS = 10


def _claim_v2_run() -> bool:
    """[INFRA-116] 수동 V2 실행과 같은 잠금·파일로 실행권을 잡는다."""
    with _status_file_lock(V2_STATUS_FILE, logger):
        if read_v2_status_uncached(V2_STATUS_FILE).get("isRunning", False):
            return False
        write_v2_status(V2_STATUS_FILE, True, logger)
        return True


def _wait_and_claim_v2_run() -> bool:
    if _claim_v2_run():
        return True
    logger.warning("[Scheduler] 수동 종가베팅 실행이 진행 중이라 끝나기를 기다립니다 (최대 30분).")
    deadline = time.monotonic() + V2_WAIT_SECONDS
    while time.monotonic() < deadline:
        time.sleep(V2_POLL_SECONDS)
        if _claim_v2_run():
            return True
    logger.error("[Scheduler] 수동 종가베팅 실행이 30분 안에 끝나지 않아 정기 종가베팅 분석을 건너뜁니다.")
    return False
```

`run_jongga_v2_analysis` 의 `try` 첫 줄에서 `claimed = _wait_and_claim_v2_run()` 을 부르고 False 면 `return False`. `finally` 에서 `if claimed: write_v2_status(V2_STATUS_FILE, False, logger)` 를 스케줄러 플래그 해제 앞에 둔다. `claimed = False` 는 `try` 앞에서 초기화한다.

- [ ] **Step 4: 통과 확인과 pytest 전체**

Run: `venv/bin/python -m pytest -q -p no:cacheprovider tests/services/test_scheduler_jobs_refactor.py` → PASS
Run: `venv/bin/python -m pytest -q -p no:cacheprovider` → 실패 0
