# [JONGGA-040] 종가베팅 최신 파일 단일 쓰기 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `run_screener` 가 이미 원자적으로 저장한 `jongga_v2_latest.json` 을 호출자 세 곳이 다시 쓰지 않게 한다.

**Architecture:** 저장의 단일 지점은 `engine/generator.py:170` 의 `save_result_to_json(result)` 이다. 이 함수는 `engine/generator_result_storage.py` 의 `atomic_write_text` 로 일자 파일과 최신 파일을 쓴다. 호출자 쪽 중복 쓰기만 지우고 엔진은 고치지 않는다.

**Tech Stack:** Python 3.11, pytest.

**Spec:** 별도 설계 문서 없음(bounded). 2026-09-23 대화에서 설계를 제시하고 사용자가 「응 진행해」로 승인했다. 요지는 `docs/dev-cycle/TODO.md` 의 `[JONGGA-040]` 설계 승인 줄에 있다.

## Global Constraints

- `engine/generator.py`·`engine/generator_result_storage.py` 는 고치지 않는다(위험 경로, 이번 결함과 무관).
- `create_jongga_v2_latest()` 의 반환 계약(결과가 있으면 True, None 이면 False, 예외면 False)과 완료 로그의 종목 수는 유지한다.
- 두 서비스의 `run_jongga_v2_background_pipeline` 은 상태 저장(True→False)과 알림 발송을 그대로 유지한다.
- `scripts/init_data.py` 는 위험 경로이므로 티어는 T3 이다.
- 수용한 동작 차이:
  1. 최신 파일의 `updated_at` 이 두 번째 쓰기 시각이 아니라 `run_screener` 의 저장 시각이 된다(차이는 수 초).
  2. `init_data` 가 쓰던 절대 경로 `BASE_DIR/data` 가 아니라 cwd 기준 `data/` 에만 쓰인다. 읽는 쪽(`app/routes/kr_market.py:92` `DATA_DIR = 'data'`)도 cwd 기준이고, 운영은 `restart_all.sh:7` 이 저장소 루트로 `cd` 하므로 같은 파일이다. 예외가 하나 있다. 스케줄러가 바로 뒤에 부르는 `send_jongga_notification`(`scripts/init_data.py:1701`, 호출은 `services/scheduler_jobs.py:66,122`)은 `BASE_DIR/data/jongga_v2_latest.json` 을 읽고 중복 알림 가드도 그 디렉터리에 둔다. 종전에는 두 번째 쓰기가 그 사본을 갱신했으므로, cwd 가 저장소 루트가 아니면 이제 알림이 옛 파일을 읽거나 파일이 없어 건너뛸 수 있다. 운영은 `restart_all.sh:7` 과 `run.py:14` 가 루트로 옮기므로 같은 파일이다. 이 경로 통일은 `[INFRA-082]` 의 목록에 `scripts/init_data.py` 의 `BASE_DIR/data` 사용처로 추가해 넘긴다(계획 검토 R1).
- `json`·`NumpyEncoder`·`datetime` import 는 `init_data.py` 의 다른 함수가 계속 쓰므로 지우지 않는다.

---

### Task 1: 회귀 테스트(RED)

**Files:**
- Create: `tests/scripts/test_jongga_latest_single_write.py`

- [ ] **Step 1: 테스트 작성**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[JONGGA-040] 종가베팅 최신 파일은 run_screener 의 원자적 저장 한 번으로만 쓰인다."""

from __future__ import annotations

import logging
import sys
import types
from datetime import date

import pytest

from scripts import init_data
from services import kr_market_jongga_runtime_service as runtime_service
from services import kr_market_route_service as route_service

LOGGER = logging.getLogger(__name__)


def _fake_result():
    return types.SimpleNamespace(
        date=date(2026, 9, 23), total_candidates=1, filtered_count=1, scanned_count=1,
        signals=[], by_grade={}, by_market={}, processing_time_ms=1,
        market_status={}, market_summary="", trending_themes=[],
    )


def _fake_generator(monkeypatch, save):
    async def _run_screener(*_a, **_k):
        return _fake_result()

    module = types.ModuleType("engine.generator")
    module.run_screener = _run_screener
    module.save_result_to_json = save
    monkeypatch.setitem(sys.modules, "engine.generator", module)


def test_create_jongga_v2_latest_does_not_rewrite_latest_file(monkeypatch, tmp_path):
    # BASE_DIR 과 cwd 를 모두 tmp_path 로 돌려, 어느 쪽 경로로 다시 써도 잡히게 한다.
    (tmp_path / "data").mkdir()
    monkeypatch.setattr(init_data, "BASE_DIR", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    saves = []
    _fake_generator(monkeypatch, saves.append)

    assert init_data.create_jongga_v2_latest() is True
    assert saves == []
    assert not (tmp_path / "data" / "jongga_v2_latest.json").exists()


@pytest.mark.parametrize("service", [route_service, runtime_service], ids=["route", "runtime"])
def test_background_pipeline_does_not_save_twice(monkeypatch, service):
    saves = []
    _fake_generator(monkeypatch, saves.append)
    monkeypatch.setattr(service, "_reload_engine_submodules", lambda: None)
    monkeypatch.setattr(service, "_send_jongga_notification_from_result", lambda *_a: None)
    status = []

    service.run_jongga_v2_background_pipeline(
        capital=50_000_000, markets=None, target_date=None,
        save_status=status.append, logger=LOGGER,
    )

    assert saves == []
    assert status == [True, False]
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/scripts/test_jongga_latest_single_write.py -q`
Expected: 3건 FAIL. init_data 는 파일이 생겨서, 두 서비스는 `saves` 에 결과가 한 건 들어가서 실패한다.

### Task 2: 중복 쓰기 제거(GREEN)

**Files:**
- Modify: `scripts/init_data.py:1659-1698` (쓰기는 1690-1692)
- Modify: `services/kr_market_route_service.py:91,102-104`
- Modify: `services/kr_market_jongga_runtime_service.py:116,127-129`

- [ ] **Step 1: `create_jongga_v2_latest` 의 직접 쓰기 제거**

```python
        # run_screener 가 일자·최신 파일을 원자적으로 저장한다. 여기서 다시 쓰지 않는다.
        result = asyncio.run(run_screener())

        if result:
            log(f"종가베팅 V2 분석 완료: {len(result.signals)} 종목 (SignalGenerator)", "SUCCESS")
            return True
        else:
            log("종가베팅 분석 결과 없음 (None returned)", "WARNING")
            return False
```

- [ ] **Step 2: 두 서비스의 두 번째 저장 제거**

두 파일 모두 같은 모양으로 바꾼다.

```python
        from engine.generator import run_screener

        result = _run_coro_in_fresh_loop(...)  # 기존 그대로

        if result:
            _send_jongga_notification_from_result(result, logger)
```

- [ ] **Step 3: 통과 확인**

Run: `pytest tests/scripts/test_jongga_latest_single_write.py tests/app/test_kr_market_helpers_contract.py tests/services/test_scheduler_jobs_refactor.py tests/scripts/ -q`
Expected: 전부 PASS.

### Task 3: 검증과 커밋

- [ ] 변이 확인: Task 2 의 세 변경을 하나씩 되돌리면 해당 테스트가 실패한다.
- [ ] 전체 pytest 는 사본에서 돌린다(`[INFRA-083]`).
- [ ] QA 문서 `docs/dev-cycle/qa/JONGGA-040.md` 를 만들고 첫 커밋 `fix(jongga): [JONGGA-040] write jongga_v2_latest.json once, atomically` 를 남긴다.
