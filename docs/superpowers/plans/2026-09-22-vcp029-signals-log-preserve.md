# [VCP-029] VCP 로그의 병합·정리 실패 갈래 보존 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `scripts/init_data.py` 의 `create_signals_log` 가 기존 `signals_log.csv` 를 읽거나 갱신하지 못했을 때 그 파일을 덮어쓰지 않고 `False` 를 돌려주게 한다.

**Architecture:** 같은 함수 안의 두 `except` 본문만 바꾼다. (가) 시그널이 있을 때의 병합 실패 갈래는 오늘 자 행만 쓰던 동작을 지우고 바로 `False` 를 돌려준다. (나) 시그널이 없을 때의 정리 실패 갈래는 빈 파일을 쓰던 동작을 지우고, 종전처럼 빈 최신 payload 를 쓴 뒤 `False` 를 돌려준다. 그 밖의 흐름과 열 목록, `[VCP-028]` 의 바깥 예외 갈래는 손대지 않는다.

**Tech Stack:** Python 3.11, pandas, pytest. 새 의존성 없음.

**Spec:** 설계 문서 없음(bounded). 범위는 `docs/dev-cycle/TODO.md` 의 `[VCP-029]` 항목이고, 승인은 2026-09-22 17:0x 사용자 「승인」 뒤 AskUserQuestion 「VCP-029 설계」에서 추천안 「두 갈래 모두 False」를 고른 것이다.

## Global Constraints

- 티어 T3. `scripts/init_data.py` 는 `tier-rules.md` §2 「스케줄러와 데이터 적재」 위험 경로다. 줄 수와 무관하게 `/ponytail-review` → `/code-review` → `/review`, pytest·vitest 전체, QA 2단계를 거친다.
- 건드리는 파일은 `scripts/init_data.py` 와 `tests/scripts/test_init_data_vcp_scheduler.py` 둘뿐이다. 다른 파일을 고치지 않는다.
- 원본 `data/` 는 읽기 전용이다. 테스트는 `tmp_path`, QA 는 scratchpad 사본에서만 실행한다. 운영 서버와 3500·5501 포트에 접근하지 않는다.
- 범위 밖: CSV 쓰기의 원자성(`to_csv` 가 중간에 죽으면 잘림), (가)에서 병합 실패 전에 이미 쓴 `vcp_signals_latest.json` 이 오늘 자 시그널을 담고 있는 불일치, Refresh VCP 상태창이 `False` 를 「완료: 조건 충족 종목 없음」으로 보이는 기존 동작(`services/kr_market_vcp_background_service.py:82`). 발견은 QA 문서의 「이월한 발견」에 적는다.
- 두 갈래 모두 반환값은 `False` 다. 호출자별 동작은 다음과 같다. 스케줄러(`services/scheduler_jobs.py:113-116`)는 「VCP 시그널 분석 실패 감지」를 ERROR 로그에 남기고 종가베팅 단계로 이어간다. 관리자 「Refresh Data」 파이프라인(`services/common_update_pipeline_steps.py:220` → `_run_update_step` `:108-111`)은 `False` 를 받으면 `update_item_status("VCP Signals", "error")` 를 불러 **데이터 갱신 화면의 「VCP Signals」 항목이 done 이 아니라 error 로 보인다.** 이것은 저장에 실패했다는 사실 그대로이며 의도한 동작이다. 반환값이 `None` 으로 바뀌어도 이어지는 AI Analysis 단계는 `isinstance(vcp_df, pd.DataFrame)` 을 요구하므로 종전 `True` 와 같은 대체 경로를 탄다(`services/common_update_ai_analysis_service.py:61`, `services/common_update_service.py:89-96`). 「Refresh VCP」(`services/kr_market_vcp_background_service.py:65-86`)는 `False` 를 `status="success"` 와 「완료: 조건 충족 종목 없음」으로 보인다. 종전에 이 두 갈래는 `True` 를 돌려주어 「완료: 성공」이었으므로 문구가 바뀌며, 시그널이 있었는데 저장만 실패한 경우까지 그 문구에 닿는다. 근본 원인은 그 파일의 `isinstance(result_df, pd.DataFrame)` 죽은 분기와 `False` → success 매핑이라 `[VCP-031]` 로 등록했다(심층 리뷰 M1). `scripts/init_data.py:2053`·`:2063` 의 CLI 명령과 `scripts/verify_collection_logic.py:21`·`scripts/verify_vcp_flow.py:44` 는 반환값을 출력만 하거나 무시한다.
- 이 변경 뒤에는 `False` 가 「빈 최신 payload 를 썼다」를 함의하지 않는다. (가)는 분석에 성공하고 저장만 실패한 경우라 이미 쓴 오늘 자 `vcp_signals_latest.json` 을 빈 payload 로 덮어쓰면 멀쩡한 결과를 파괴하므로 그대로 둔다. 호출자는 모두 불리언만 읽는다.
- 0바이트 파일은 `pd.read_csv` 가 `EmptyDataError` 를 내므로 이 변경 뒤에는 운영자가 손보기 전까지 매 실행이 「보존 + False」 갈래로 빠진다. 종전 코드가 덮어쓰기로 스스로 회복하던 자리다. 원자적 쓰기와 함께 `[VCP-030]` 으로 등록했고 이 항목의 범위에 넣지 않는다.

## Review Focus

1. (가)에서 `return False` 로 빠지면 「누적 저장」 SUCCESS 로그와 `return True` 를 건너뛰는지: Task 1.
2. (나)에서 빈 최신 payload 쓰기와 반환값이 `[VCP-028]` 의 바깥 예외 갈래와 같은 계약인지(파일 보존, 빈 payload, `False`): Task 2.
3. 회귀 테스트가 pandas 를 monkeypatch 하지 않고 실제 손상 파일(열 수가 다른 행)로 두 갈래에 들어가는지: Task 1·2.

---

### Task 1: 병합 실패 갈래(가)가 기존 로그를 보존한다

**Files:**
- Modify: `scripts/init_data.py:1608-1610`
- Test: `tests/scripts/test_init_data_vcp_scheduler.py` (파일 끝에 추가)

**Interfaces:**
- Consumes: 기존 고정물 `_DummyScreener`(시그널 1건 반환), `init_data.BASE_DIR` monkeypatch 관례.
- Produces: 모듈 상수 `_RAGGED_LOG`(Task 2 가 같은 것을 쓴다). `create_signals_log` 는 병합 실패 시 `False`.

- [ ] **Step 1: Write the failing test**

파일 끝에 추가한다. `_RAGGED_LOG` 는 세 번째 줄의 열 수가 헤더와 달라 `pd.read_csv` 가 `ParserError` 를 낸다(검증: 「Expected 5 fields in line 3, saw 8」).

```python
# [VCP-029] 세 번째 줄의 열 수가 헤더와 달라 pd.read_csv 가 ParserError 를 낸다.
_RAGGED_LOG = (
    "ticker,signal_date,status,score,is_vcp\n"
    "005930,2026-09-19,OPEN,80,True\n"
    "000660,2026-09-21,OPEN,81,True,extra,extra,extra\n"
)


def test_create_signals_log_keeps_unreadable_log_when_merge_fails(monkeypatch, tmp_path):
    """[VCP-029] 기존 로그를 읽지 못해 병합에 실패하면 파일을 그대로 두고 실패를 돌려준다."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    log_path = data_dir / "signals_log.csv"
    log_path.write_text(_RAGGED_LOG, encoding="utf-8")

    monkeypatch.setattr(init_data, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr("engine.screener.SmartMoneyScreener", _DummyScreener)

    result = init_data.create_signals_log(target_date="2026-09-22", run_ai=False)

    assert result is False
    assert log_path.read_text(encoding="utf-8") == _RAGGED_LOG
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest -q tests/scripts/test_init_data_vcp_scheduler.py -k merge_fails`
Expected: FAIL. 종전 코드는 `df_new.to_csv` 로 오늘 자 한 줄만 남기고 `True` 를 돌려주므로 두 assert 모두 어긋난다.

- [ ] **Step 3: Write minimal implementation**

`scripts/init_data.py:1608-1610` 의 `except` 본문을 바꾼다.

```python
                except Exception as e:
                    # 기존 로그를 버리지 않는다([VCP-029]). 오늘 자 시그널은 CSV 에 남지 않으므로
                    # 실패로 돌려주고, 파일은 운영자가 이 경고를 보고 손본다.
                    log(f"기존 로그 병합 실패: {e}. {file_path} 를 보존하고 오늘 자 결과를 저장하지 않습니다. 파일을 고친 뒤 다시 실행하십시오.", "WARNING")
                    return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/python -m pytest -q tests/scripts/test_init_data_vcp_scheduler.py -k merge_fails`
Expected: PASS

- [ ] **Step 5: 커밋은 Task 2 와 함께 한다** (dev-cycle [3] 5 의 첫 커밋)

### Task 2: 정리 실패 갈래(나)가 기존 로그를 보존한다

**Files:**
- Modify: `scripts/init_data.py:1620-1636`
- Test: `tests/scripts/test_init_data_vcp_scheduler.py` (Task 1 의 테스트 뒤에 추가)

**Interfaces:**
- Consumes: Task 1 의 `_RAGGED_LOG`, 기존 고정물 `_EmptyScreener`(빈 DataFrame 반환). 테스트 파일은 이미 `json` 을 import 한다.
- Produces: `create_signals_log` 는 정리 실패 시 빈 최신 payload 를 쓰고 `False`.

- [ ] **Step 1: Write the failing test**

```python
def test_create_signals_log_keeps_unreadable_log_when_cleanup_fails(monkeypatch, tmp_path):
    """[VCP-029] 시그널이 없고 기존 로그를 읽지 못하면 빈 파일로 바꾸지 않고 실패를 돌려준다."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    log_path = data_dir / "signals_log.csv"
    log_path.write_text(_RAGGED_LOG, encoding="utf-8")

    monkeypatch.setattr(init_data, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr("engine.screener.SmartMoneyScreener", _EmptyScreener)

    result = init_data.create_signals_log(target_date="2026-09-22", run_ai=False)

    assert result is False
    assert log_path.read_text(encoding="utf-8") == _RAGGED_LOG
    latest = json.loads((data_dir / "vcp_signals_latest.json").read_text(encoding="utf-8"))
    assert latest["date"] == "2026-09-22"
    assert latest["signals"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest -q tests/scripts/test_init_data_vcp_scheduler.py -k cleanup_fails`
Expected: FAIL. 종전 코드는 빈 23열 파일을 쓰고 `True` 를 돌려준다.

- [ ] **Step 3: Write minimal implementation**

`scripts/init_data.py:1620-1636` 을 아래로 바꾼다. 바뀌는 것은 `cleaned` 변수 도입, `except` 본문, 마지막 `return` 뿐이다.

```python
            cleaned = True
            if os.path.exists(file_path):
                try:
                    existing_df = pd.read_csv(file_path, dtype={'ticker': str, 'signal_date': str})
                    if 'signal_date' in existing_df.columns:
                        existing_df = existing_df[existing_df['signal_date'].astype(str) != current_date]
                    existing_df.to_csv(file_path, index=False, encoding='utf-8-sig')
                except Exception as e:
                    # 기존 로그를 버리지 않는다([VCP-029]). 오늘 자 옛 행을 걷어내지 못했으므로 실패로 돌려준다.
                    log(f"기존 VCP 로그 정리 실패: {e}. {file_path} 를 보존합니다. 파일을 고친 뒤 다시 실행하십시오.", "WARNING")
                    cleaned = False
            else:
                pd.DataFrame(columns=_SIGNALS_LOG_COLUMNS).to_csv(file_path, index=False, encoding='utf-8-sig')
            _write_vcp_signals_latest_payload(
                target_date=target_date,
                signals=[],
            )
            if cleaned:
                log("VCP 조건 충족 종목 없음 - 빈 결과 저장", "INFO")
            return cleaned
```

정리에 실패했을 때 성공처럼 읽히는 INFO 를 WARNING 뒤에 붙이지 않으려고 INFO 를 `if cleaned:` 아래에 둔다(계획 검토 R7).

- [ ] **Step 4: Run the whole test module**

Run: `venv/bin/python -m pytest -q tests/scripts/test_init_data_vcp_scheduler.py`
Expected: 전부 PASS (기존 건 + 새 2건).

- [ ] **Step 5: 정적 검증과 첫 커밋**

Run: `source venv/bin/activate && pytest -q` 와 `cd frontend && npx vitest run`. 리뷰 세 단계(`/ponytail-review` → `feature-dev:code-reviewer` → `/review`)를 마친 뒤 QA 계획 문서 `docs/dev-cycle/qa/VCP-029.md` 와 함께 첫 커밋을 남긴다. TODO 항목은 유지한다.

```bash
git add scripts/init_data.py tests/scripts/test_init_data_vcp_scheduler.py docs/dev-cycle/qa/VCP-029.md docs/dev-cycle/TODO.md docs/superpowers/plans/2026-09-22-vcp029-signals-log-preserve.md
git diff --cached --check
git commit -F - <<'MSG'
fix(vcp): [VCP-029] keep the signals log when merging or cleaning it fails

<본문: 무엇이 왜 바뀌었는지, 리뷰와 검증 결과>

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AeQQtEk7wbuVAnf9kCJmBN
MSG
```

최근 커밋(`6399577`, `4b187c2`)과 같이 본문과 두 트레일러를 단다(계획 검토 R8).

### Task 3: QA 재현(scratchpad)

**Files:**
- Create: `<scratchpad>/vcp029_qa.py` (저장소 밖. 커밋하지 않는다)
- Record: `docs/dev-cycle/qa/VCP-029.md`

**Interfaces:**
- Consumes: 원본 `data/signals_log.csv` 를 `shutil.copyfile` 로 복사한 사본, `init_data.BASE_DIR` 교체, `engine.screener.SmartMoneyScreener` 교체, `services.common_update_pipeline_steps._run_update_step`(S-4).
- Produces: 시나리오 S-1·S-2·S-4(필수)·S-3(인접) 의 출력 원문과 원본 `data/` 스냅샷 비교.

S-4 는 계획 검토 R3 을 반영한 것이다. `run_vcp_signals_step` 을 그대로 부르면 그 안의 `SignalTracker()` 가 저장소의 `data/` 를 직접 열어 원본을 건드리므로, 상태 전환을 결정하는 래퍼 `_run_update_step` 에 같은 함수를 넣어 「VCP Signals」 가 error 로 바뀌는 것만 확인한다. S-3 은 원본에 오늘 자 행이 있어도 깨지지 않도록 과거 행 수를 기준으로 단언한다(R5). 스크립트 끝에서 원본 `data/` 최상위 파일의 크기·mtime 을 앞뒤로 비교해 격리 보증 범위를 드러낸다(R6).

- [ ] **Step 1: 스크립트를 scratchpad 에 둔다**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[VCP-029] QA 재현. 원본 data/ 는 읽기만 하고 사본으로 실행한다.

S-1 (필수): 손상 사본 + 시그널 있음 → 병합 실패 갈래. 파일 보존, False.
S-2 (필수): 손상 사본 + 시그널 없음 → 정리 실패 갈래. 파일 보존, False, 빈 최신 payload.
S-3 (인접): 온전한 사본 + 시그널 있음 → 정상 병합. 과거 행 보존 + 오늘 자 1행.
S-4 (필수): 손상 사본 + Refresh Data 의 단계 래퍼 → 「VCP Signals」 상태가 error.
보증 범위: 원본 signals_log.csv 의 md5 와 원본 data/ 최상위 파일의 크기·mtime 스냅샷.
"""

import hashlib
import logging
import shutil
import sys
import types
from pathlib import Path

import pandas as pd

REPO = Path("/Users/freelife/vibe/lecture/hodu/closing-bet-demo")
SCRATCH = Path(__file__).resolve().parent / "vcp029-qa"
DATA = SCRATCH / "data"
TODAY = "2026-09-22"
sys.path.insert(0, str(REPO))

# 원본의 열 수(23)와 다르게 26개 필드를 넣어 pd.read_csv 가 ParserError 를 확실히 낸다.
_RAGGED_LINE = "000660,2026-09-21,OPEN,81," + ",".join(["extra"] * 22) + "\n"


def md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def snapshot(directory: Path) -> dict[str, tuple[int, int]]:
    return {
        entry.name: (entry.stat().st_size, entry.stat().st_mtime_ns)
        for entry in directory.iterdir()
        if entry.is_file()
    }


def fresh_copy(source: Path, target: Path, *, corrupt: bool) -> None:
    shutil.copyfile(source, target)
    if corrupt:
        with target.open("a", encoding="utf-8") as handle:
            handle.write(_RAGGED_LINE)


class _SignalScreener:
    def __init__(self, target_date=None):
        self.target_date = target_date

    def run_screening(self, max_stocks=600):
        return pd.DataFrame([{
            "ticker": "005930", "name": "삼성전자", "score": 65.0, "market": "KOSPI",
            "entry_price": 70000, "contraction_ratio": 0.62, "foreign_net_5d": 1, "inst_net_5d": 1,
            "foreign_net_1d": 1, "inst_net_1d": 1, "vcp_score": 8, "is_vcp": True,
        }])


class _EmptyScreener(_SignalScreener):
    def run_screening(self, max_stocks=600):
        return pd.DataFrame()


def main() -> int:
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    DATA.mkdir(parents=True)
    source = REPO / "data" / "signals_log.csv"
    target = DATA / "signals_log.csv"
    source_md5 = md5(source)
    data_before = snapshot(REPO / "data")

    from scripts import init_data
    import engine.screener
    from services.common_update_pipeline_steps import _run_update_step

    init_data.BASE_DIR = str(SCRATCH)
    failures = 0

    # S-1
    fresh_copy(source, target, corrupt=True)
    before = md5(target)
    engine.screener.SmartMoneyScreener = _SignalScreener
    r1 = init_data.create_signals_log(target_date=TODAY, run_ai=False)
    same1 = md5(target) == before
    ok1 = r1 is False and same1
    failures += 0 if ok1 else 1
    print(f"S-1 result={r1} md5_same={same1} -> {'통과' if ok1 else '실패'}")

    # S-2
    fresh_copy(source, target, corrupt=True)
    before = md5(target)
    engine.screener.SmartMoneyScreener = _EmptyScreener
    r2 = init_data.create_signals_log(target_date=TODAY, run_ai=False)
    latest = (DATA / "vcp_signals_latest.json").read_text(encoding="utf-8")
    same2 = md5(target) == before
    empty_latest = '"signals": []' in latest and f'"date": "{TODAY}"' in latest
    ok2 = r2 is False and same2 and empty_latest
    failures += 0 if ok2 else 1
    print(f"S-2 result={r2} md5_same={same2} empty_latest={empty_latest} -> {'통과' if ok2 else '실패'}")

    # S-3
    fresh_copy(source, target, corrupt=False)
    before_df = pd.read_csv(target, dtype=str, keep_default_na=False)
    past_rows = int((before_df["signal_date"] != TODAY).sum())
    engine.screener.SmartMoneyScreener = _SignalScreener
    r3 = init_data.create_signals_log(target_date=TODAY, run_ai=False)
    after = pd.read_csv(target, dtype=str, keep_default_na=False)
    today_rows = int((after["signal_date"] == TODAY).sum())
    ok3 = r3 is True and len(after) == past_rows + 1 and today_rows == 1
    failures += 0 if ok3 else 1
    print(f"S-3 result={r3} past_rows={past_rows} rows_after={len(after)} today_rows={today_rows} -> {'통과' if ok3 else '실패'}")

    # S-4: Refresh Data 파이프라인의 단계 래퍼가 False 를 error 상태로 옮기는지.
    # run_vcp_signals_step 은 SignalTracker() 가 저장소 data/ 를 직접 열므로 부르지 않는다.
    fresh_copy(source, target, corrupt=True)
    before = md5(target)
    engine.screener.SmartMoneyScreener = _SignalScreener
    statuses: list[tuple[str, str]] = []
    r4 = _run_update_step(
        step_name="VCP Signals",
        execute_fn=lambda: init_data.create_signals_log(target_date=TODAY, run_ai=False),
        update_item_status=lambda name, status: statuses.append((name, status)),
        shared_state=types.SimpleNamespace(STOP_REQUESTED=False),
        logger=logging.getLogger("vcp029-qa"),
    )
    same4 = md5(target) == before
    ok4 = r4 is None and statuses == [("VCP Signals", "running"), ("VCP Signals", "error")] and same4
    failures += 0 if ok4 else 1
    print(f"S-4 result={r4} statuses={statuses} md5_same={same4} -> {'통과' if ok4 else '실패'}")

    data_after = snapshot(REPO / "data")
    changed = sorted(name for name in set(data_before) | set(data_after) if data_before.get(name) != data_after.get(name))
    print("원본 signals_log.csv md5 유지:", md5(source) == source_md5)
    print("원본 data/ 최상위 변경 파일:", changed if changed else "없음")
    shutil.rmtree(SCRATCH)
    return failures


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: 실행하고 출력 원문을 QA 문서에 옮긴다**

Run: `venv/bin/python <scratchpad>/vcp029_qa.py`
Expected: S-1·S-2·S-3·S-4 모두 「통과」, `원본 signals_log.csv md5 유지: True`, 종료 코드 0. 「원본 data/ 최상위 변경 파일」 줄에 무엇이 찍히든 QA 문서에 그대로 적는다. 손상 줄은 원본의 열 수(23)와 다르게 26개 필드를 넣어 `ParserError` 를 확실히 낸다.

## 심층 리뷰 반영

`oh-my-claudecode:critic`(`vcp029-deep-review`) ACCEPT-WITH-RESERVATIONS. m1 에 따라 두 WARNING 문구에 `file_path` 와 다음 행동을 넣었고, m2 에 따라 `[VCP-028]` 갈래의 주석 「정상 갈래」를 「「시그널 없음」 갈래」로 고쳤다. M1 은 `[VCP-031]`, M2·m4 는 `[VCP-030]` 범위 확장으로 이월했다. m3 은 확신도 낮음·현실 경로 없음으로 기록만 남겼다.

## Self-Review

- 범위 대조: TODO 의 (가)·(나) 두 갈래 → Task 1·2. QA 시나리오 줄(사본 + 예외 → 행 수·md5 보존) → Task 3.
- 자리표시자 없음. 코드 블록은 실제로 넣을 내용이다.
- 이름 일치: `_RAGGED_LOG` 는 Task 1 이 만들고 Task 2 가 쓴다. `cleaned` 는 Task 2 안에서만 쓴다.
