# [INFRA-114] 기동 초기화가 살아 있는 다른 워커의 V2·스케줄러 실행 상태를 지우지 않게 한다 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** gunicorn 이 워커 하나만 다시 띄워도 다른 워커에서 도는 종가베팅 V2 수동 실행(`v2_screener_status.json`, 중복 실행 409 잠금)과 리더 워커의 스케줄러 체인 표시(`scheduler_runtime_status.json`)가 꺼지지 않게 한다. 전체 재기동·소유자 사망 때 초기화하는 종전 동작은 유지한다.

**Architecture:** `[INFRA-107]` 의 소유 pid 방식을 두 파일에 그대로 쓴다. 판정은 `services/common_update_status_service.py` 의 새 공개 함수 `owned_by_live_sibling(status)`(= `ownerPpid == os.getppid()` 이고 `_owner_process_alive(ownerPid)`) 하나로 모으고, 기존 `reset_orphaned_update_status` 도 이 함수를 쓴다. 쓰는 쪽(`_save_v2_status`, `set_scheduler_runtime_status`)이 `ownerPid`·`ownerPpid` 를 함께 기록하고, 기동 초기화는 원본 파일을 읽어 실행 중이고 형제가 소유하면 그대로 둔다.

**Tech Stack:** Python 3.11, pytest

**Spec:** 대화 설계(2026-09-25 11:13 확인 시각에 승인, 「소유 pid 방식 재사용, 두 상태 파일 모두 적용」), `docs/dev-cycle/TODO.md` `[INFRA-114]` 설계 승인 줄

## Global Constraints

- 티어 T3: `services/scheduler_runtime_status_service.py` 가 tier-rules §2 목록에 있다. 파일 형식은 JSON 필드 두 개 추가뿐이다.
- 공개 응답 계약 불변: `/api/kr/jongga-v2/status` 는 응답을 따로 만들고, `get_scheduler_runtime_status` 는 정규화로 세 플래그와 `updated_at` 만 돌려주므로 pid 가 나가지 않는다. 테스트로 고정한다.
- 전체 재기동(모든 옛 워커 사망) 결과는 종전과 같다: V2 `{"isRunning": false}`, 스케줄러 세 플래그 false.
- 원본 `data/`·네트워크에 닿지 않는다. 테스트는 `tmp_path` 와 실제 프로세스만 쓴다.
- 운영 반영은 gunicorn 워커를 모두 재기동해야 한다(장 중 금지). 반영 직후 기동은 옛 파일(pid 없음)을 종전처럼 초기화한다.

## Review Focus

- 깨진 V2·스케줄러 JSON: 로더가 `JSONDecodeError` 를 던진다. 초기화로 떨어져야 한다(종전과 같음).
- 스케줄러 상태는 세 플래그가 모두 false 이면 소유자와 관계없이 초기화 파일을 써도 무방하다. 하나라도 true 이고 형제 소유일 때만 보존한다.
- `set_scheduler_runtime_status` 의 `current` 는 정규화된 값이라 pid 키가 없다. 매 기록마다 다시 붙인다.
- V2 저장은 `launch_jongga_v2_screener` 의 요청 스레드와 백그라운드 스레드 `finally` 에서 불린다. 둘 다 같은 워커 프로세스라 `os.getpid()` 가 소유 워커다.
- 기동 초기화의 V2 읽기-쓰기 사이에는 잠금이 없다(종전에도 원자적 교체뿐). 형제가 그 사이 `False` 로 끝내도 결과는 `False` 라 같다. 형제가 그 사이 새로 `True` 를 쓰면 덮일 수 있으나 종전에는 항상 덮었다.

## 알려진 한계

1. `[INFRA-107]` 과 같다. 같은 마스터 안의 pid 재사용·graceful 재기동(HUP)의 옛 워커는 살아 있다고 본다. V2 는 해제 수단이 백그라운드 `finally` 뿐이라 그 경우 다음 전체 재기동까지 409 가 남는다. 스케줄러 플래그도 true 로 남지만 다음 체인이나 휴장일 분기의 `finally` 가 false 로 되돌려 하루 안에 풀리며, 그 사이 update-status 가 「전체 스케쥴링 작업 진행 중」을 보인다(critic 지적 2). `restart_all.sh` 는 HUP 를 쓰지 않는다.
2. 이 변경으로 V2 고착의 복구 경로가 좁아진다. 종전에는 아무 워커의 재기동이 풀었지만 이제는 소유 워커 사망이나 전체 재기동이 푼다. 그래서 `launch_jongga_v2_screener` 가 스레드를 먼저 시작하고 `True` 를 나중에 쓰던 순서(백그라운드가 곧바로 `False` 를 쓰면 `True` 가 덮여 굳음)는 이번에 바꾼다(critic 지적 1). 동시 요청 둘이 모두 통과하는 읽기-쓰기 경쟁은 범위 밖이며 TODO 에 새 항목으로 등록한다.
3. 기동 초기화의 읽기-쓰기 사이에 프로세스 사이 잠금이 없다. V2 는 원자적 교체뿐이고 스케줄러는 스레드 잠금뿐이다(critic 지적 3). 종전과 같은 수준이다.

## 계획 검토 반영(critic ACCEPT-WITH-RESERVATIONS)

- 지적 1(중, 저장 순서): `save_v2_status(True)` 를 `thread.start()` 앞으로 옮기고 `test_launch_jongga_v2_screener_saves_running_before_thread_start` 를 더했다. 옛 순서에서 3회 모두 실패함을 확인했다.
- 지적 2·3: 알려진 한계 1·3 에 기록.
- 지적 4(`app/__init__.py` import 누락): 구현에 반영.
- 지적 5(테스트 공백): 「플래그 모두 false 면 형제가 살아 있어도 기본값」, 「옛 소유자 위에 set 이 pid 를 새로 기록」 두 테스트를 더했다.

---

### Task 1: 형제 소유 판정 공개와 두 상태 파일의 소유 pid 기록·보존

**Files:**
- Modify: `services/common_update_status_service.py` (새 `owned_by_live_sibling`, `reset_orphaned_update_status` 가 사용)
- Modify: `services/scheduler_runtime_status_service.py` (`set_scheduler_runtime_status` pid 기록, `reset_scheduler_runtime_status` 보존 판정)
- Modify: `app/routes/kr_market_jongga_execution_routes.py` (`_save_v2_status` pid 기록)
- Modify: `app/__init__.py` (V2 초기화 보존 판정)
- Test: `tests/app/test_app_startup_status_reset_refactor.py`, `tests/services/test_scheduler_runtime_status_service.py`, `tests/app/test_kr_market_jongga_execution_routes_refactor.py`

- [ ] **Step 1: 실패하는 테스트**

```python
# tests/app/test_app_startup_status_reset_refactor.py
def test_reset_startup_status_files_keeps_v2_and_scheduler_status_of_live_other_worker(monkeypatch, tmp_path: Path):
    # [INFRA-114] 살아 있는 다른 워커의 V2 실행(409 잠금)과 스케줄러 체인 표시를 지우지 않는다
    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    owner = {"ownerPid": os.getppid(), "ownerPpid": os.getppid()}
    # 이 테스트 프로세스의 부모를 형제 워커로 쓰려면 ownerPpid 가 os.getppid() 와 같아야 한다
    (data_dir / "v2_screener_status.json").write_text(json.dumps({"isRunning": True, **owner}), encoding="utf-8")
    (data_dir / "scheduler_runtime_status.json").write_text(
        json.dumps({"is_data_scheduling_running": True, "is_jongga_scheduling_running": False,
                    "is_vcp_scheduling_running": True, "updated_at": "x", **owner}), encoding="utf-8")

    app_module._reset_startup_status_files()

    assert json.loads((data_dir / "v2_screener_status.json").read_text(encoding="utf-8"))["isRunning"] is True
    sched = json.loads((data_dir / "scheduler_runtime_status.json").read_text(encoding="utf-8"))
    assert (sched["is_data_scheduling_running"], sched["is_vcp_scheduling_running"]) == (True, True)


def test_reset_startup_status_files_resets_v2_and_scheduler_when_not_live_sibling(monkeypatch, tmp_path: Path):
    # [INFRA-114] 소유자 사망·자기 pid·마스터 불일치·pid 없는 옛 파일·깨진 파일은 종전처럼 초기화한다
    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    cases = [
        {"ownerPid": dead.pid, "ownerPpid": os.getppid()},
        {"ownerPid": os.getpid(), "ownerPpid": os.getppid()},
        {"ownerPid": os.getppid(), "ownerPpid": -1},
        {},
        None,  # 깨진 JSON
    ]
    for owner in cases:
        for name, running in (("v2_screener_status.json", {"isRunning": True}),
                              ("scheduler_runtime_status.json", {"is_jongga_scheduling_running": True})):
            text = "{broken" if owner is None else json.dumps({**running, **owner})
            (data_dir / name).write_text(text, encoding="utf-8")
        app_module._reset_startup_status_files()
        assert json.loads((data_dir / "v2_screener_status.json").read_text(encoding="utf-8")) == {"isRunning": False}, owner
        sched = json.loads((data_dir / "scheduler_runtime_status.json").read_text(encoding="utf-8"))
        assert not any(sched[k] for k in ("is_data_scheduling_running", "is_jongga_scheduling_running", "is_vcp_scheduling_running")), owner
```

```python
# tests/services/test_scheduler_runtime_status_service.py
def test_set_scheduler_runtime_status_records_owner_but_get_hides_it(tmp_path):
    # [INFRA-114] 기동 초기화가 소유 워커를 판정하도록 pid 를 남기고, 조회 응답에는 싣지 않는다
    runtime_status_service.set_scheduler_runtime_status(data_dir=str(tmp_path), jongga_scheduling_running=True)
    raw = json.loads((tmp_path / "scheduler_runtime_status.json").read_text(encoding="utf-8"))
    assert (raw["ownerPid"], raw["ownerPpid"]) == (os.getpid(), os.getppid())
    status = runtime_status_service.get_scheduler_runtime_status(data_dir=str(tmp_path))
    assert "ownerPid" not in status and status["is_jongga_scheduling_running"] is True
```

```python
# tests/app/test_kr_market_jongga_execution_routes_refactor.py (기존 atomic_writer 테스트 끝에 추가)
    payload = json.loads(status_content)
    assert (payload["ownerPid"], payload["ownerPpid"]) == (os.getpid(), os.getppid())
    status_response = client.get("/api/kr/jongga-v2/status").get_json()
    assert "ownerPid" not in status_response
```

- [ ] **Step 2: 실패 확인**

Run: `venv/bin/python -m pytest -q -p no:cacheprovider tests/app/test_app_startup_status_reset_refactor.py tests/services/test_scheduler_runtime_status_service.py tests/app/test_kr_market_jongga_execution_routes_refactor.py`
Expected: keeps_v2_and_scheduler 는 `isRunning` False 로 FAIL, owner 기록 두 테스트는 KeyError 로 FAIL. resets_v2_and_scheduler 는 종전 동작과 같아 PASS(회귀 고정용).

- [ ] **Step 3: 구현**

```python
# services/common_update_status_service.py (_owner_process_alive 아래)
def owned_by_live_sibling(status: Any) -> bool:
    """[INFRA-114] 상태를 쓴 워커가 같은 마스터 아래 살아 있는 다른 워커인가. 전체 재기동은 마스터가 바뀌어 항상 거짓이다."""
    # ponytail: 같은 마스터 안의 pid 재사용과 graceful 재기동(HUP)의 옛 워커는 살아 있다고 본다
    return isinstance(status, dict) and status.get("ownerPpid") == os.getppid() and _owner_process_alive(status.get("ownerPid"))
```

`reset_orphaned_update_status` 의 조건을 `if owned_by_live_sibling(status):` 로 바꾸고 옮긴 주석은 지운다.

```python
# services/scheduler_runtime_status_service.py
_RUNNING_KEYS = ("is_data_scheduling_running", "is_jongga_scheduling_running", "is_vcp_scheduling_running")

# set_scheduler_runtime_status: current["updated_at"] 다음 줄
        # [INFRA-114] 기동 초기화가 소유 워커 생존을 판정하도록 남긴다. 조회는 정규화로 이 키를 버린다
        current["ownerPid"], current["ownerPpid"] = os.getpid(), os.getppid()

def reset_scheduler_runtime_status(*, data_dir: str = "data") -> dict[str, Any]:
    """기동 때 스케줄러 런타임 상태를 초기화한다. 살아 있는 다른 워커(리더)가 실행 중이면 그대로 둔다."""
    with _SCHEDULER_RUNTIME_STATUS_LOCK:
        status_file = _resolve_status_file_path(data_dir)
        try:
            raw = load_json_payload_from_path(status_file, deep_copy=False)
        except Exception:
            raw = None
        if isinstance(raw, dict) and any(raw.get(k) for k in _RUNNING_KEYS) and owned_by_live_sibling(raw):
            return _normalize_scheduler_runtime_status(raw)
        status = _build_default_status()
        ...종전과 같음
```

```python
# app/routes/kr_market_jongga_execution_routes.py _save_v2_status 페이로드
                        "isRunning": running,
                        "updated_at": datetime.now().isoformat(),
                        # [INFRA-114] 기동 초기화가 소유 워커 생존을 판정하도록 남긴다
                        "ownerPid": os.getpid(),
                        "ownerPpid": os.getppid(),
```

```python
# app/__init__.py _reset_startup_status_files 의 V2 블록
        # [INFRA-114] 살아 있는 다른 워커의 V2 실행(중복 실행 409 잠금)은 지우지 않는다
        try:
            v2_status = load_json_payload_from_path(v2_status_file, deep_copy=False)
        except Exception:
            v2_status = None
        if isinstance(v2_status, dict) and v2_status.get("isRunning") and owned_by_live_sibling(v2_status):
            print(f"[Startup] V2 reset skipped: run owned by live worker {v2_status.get('ownerPid')}")
        else:
            atomic_write_text(v2_status_file, json.dumps({'isRunning': False}, ensure_ascii=False, indent=2))
        reset_scheduler_runtime_status(data_dir=data_dir)
```

- [ ] **Step 4: 통과 확인**

Run: Step 2 명령
Expected: 모두 PASS

- [ ] **Step 5: 전체 회귀**

Run: `venv/bin/python -m pytest -q -p no:cacheprovider`
Expected: 실패 0
