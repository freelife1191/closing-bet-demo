# signals_log.csv 쓰기 잠금 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `data/signals_log.csv` 를 읽고 병합해 교체하는 다섯 경로가 프로세스와 워커를 넘어 서로의 행을 지우지 않게 한다.

**Architecture:** `fcntl.flock` 파일 잠금 `signals_log_lock(path)` 하나를 `write_vcp_signals_csv_atomic` 옆에 둔다. 창이 짧은 세 경로는 읽기부터 교체까지 잠그고, 느린 두 경로(시세 조회, AI 재분석)는 느린 작업을 잠금 밖에서 한 뒤 잠금 안에서 다시 읽어 병합·교체한다. 재분석 병합은 index 가 가리키는 행의 `ticker`·`signal_date` 가 다르면 덮지 않고 오류를 낸다.

**구현 메모:** 과잉설계 리뷰 지적에 따라 Task 1 의 자체 도우미 대신 `services/common_env_service.py` 의 `_env_file_lock` 을 `signals_log_lock` 별칭으로 import 해 재사용했다. 잠금 배타 단독 테스트는 지우고 `update_open_signals` 대기 검사를 더했다(`closing-bet-reviewer` L4).

**Tech Stack:** Python 3.11 표준 `fcntl`·`contextlib`, pandas, pytest.

**Spec:** 별도 spec 문서 없음(bounded). 승인 범위는 `docs/dev-cycle/TODO.md` 의 `[VCP-035]` 「설계 승인」 줄이 정본이다.

## Global Constraints

- 티어 T3(`scripts/init_data.py` 가 `tier-rules.md` §2 위험 경로). 리뷰 순서는 `/ponytail-review` → `closing-bet-reviewer` → `/review`.
- 잠금은 한 프로세스 안에서 중첩해 잡지 않는다. `flock` 은 열린 파일 기술자마다 따로 잡혀서, 같은 스레드가 두 번 잡으면 스스로 교착된다.
- `write_vcp_signals_csv_atomic` 자체는 잠금을 잡지 않는다. 다섯 경로 아홉 군데의 모든 호출자가 잠금 안에서 부른다(critic R5).
- 저장 형식(utf-8-sig, `index=False`)과 각 함수의 반환값·로그 문구는 바꾸지 않는다.
- 테스트는 `tmp_path` 만 쓰고 네트워크·LLM·원본 `data/` 에 닿지 않는다.
- 범위 밖: 수동 일회성 스크립트 `scripts/clean_signals.py`, `tests/test_vcp.py`(대화형 수동 도구), `VCP_STATUS` 의 확인·설정 비원자성.

## 파일

- Modify `services/kr_market_vcp_reanalysis_service.py`: `signals_log_lock` 추가, `_merge_reanalysis_updates_into_full_signals_frame` 에 행 일치 검사, `execute_vcp_failed_ai_reanalysis` 의 쓰기를 잠금 안으로.
- Modify `scripts/init_data.py`: `create_signals_log` 의 세 쓰기 갈래, `update_vcp_signals_recent_price` 의 재읽기·적용·원자적 쓰기.
- Modify `engine/signal_tracker_analysis_mixin.py`: `_append_to_log`, `update_open_signals`.
- Create `tests/services/test_vcp_signals_log_lock_refactor.py`: 잠금 배타, 재분석 행 일치 검사, 스레드 대기 도우미를 쓰는 세 경로의 대기 검사, 시세 갱신의 재읽기 검사.

테스트를 한 파일에 모으는 이유: 검사 대상이 「같은 잠금을 모든 쓰기 경로가 지나는가」 하나이고, 대기 도우미를 세 파일에 복제하지 않기 위해서다.

---

### Task 1: 잠금 도우미와 재분석 경로

**Files:**
- Modify: `services/kr_market_vcp_reanalysis_service.py` (import 절, `_merge_reanalysis_updates_into_full_signals_frame` 261-290, `write_vcp_signals_csv_atomic` 호출 688)
- Test: `tests/services/test_vcp_signals_log_lock_refactor.py`

**Interfaces:**
- Produces: `signals_log_lock(signals_path: str) -> Iterator[None]` (contextmanager). Task 2·3 이 import 한다.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[VCP-035] signals_log.csv 를 쓰는 경로가 같은 파일 잠금을 지나는지 검사한다."""

import threading

import pandas as pd
import pytest

from services import kr_market_vcp_reanalysis_service as reanalysis
from services.kr_market_vcp_reanalysis_service import signals_log_lock


def _assert_waits_for_lock(signals_path, fn):
    """잠금을 쥔 동안 fn 이 끝나지 않고, 풀면 끝나는지 본다."""
    errors = []

    def _run():
        try:
            fn()
        except Exception as error:  # 스레드 예외를 본 스레드로 옮긴다
            errors.append(error)

    with signals_log_lock(str(signals_path)):
        # daemon: 구현이 잠금을 중첩해 스스로 교착되면 pytest 가 멈추지 않고 실패하게 한다(critic R2)
        worker = threading.Thread(target=_run, daemon=True)
        worker.start()
        worker.join(0.3)
        assert worker.is_alive(), "잠금을 쥔 동안 쓰기가 끝났다"
    worker.join(5)
    assert not worker.is_alive()
    assert not errors, errors


def test_signals_log_lock_excludes_second_holder(tmp_path):
    path = tmp_path / "signals_log.csv"
    entered = []

    def _enter():
        with signals_log_lock(str(path)):
            entered.append(True)

    _assert_waits_for_lock(path, _enter)
    assert entered == [True]


def test_reanalysis_merge_refuses_rows_that_moved():
    """다시 읽은 파일의 같은 index 에 다른 종목이 있으면 덮지 않는다."""
    full = pd.DataFrame(
        {"ticker": ["000660", "005930"], "signal_date": ["2026-09-22", "2026-09-22"], "ai_action": ["", ""]}
    )
    updated = pd.DataFrame(
        {"ticker": ["005930"], "signal_date": ["2026-09-22"], "ai_action": ["BUY"]},
        index=[0],
    )
    with pytest.raises(ValueError, match="ticker"):
        reanalysis._merge_reanalysis_updates_into_full_signals_frame(
            updated_signals_df=updated,
            signals_path="signals_log.csv",
            load_csv_file=lambda *_a, **_k: full,
        )


def test_reanalysis_merge_applies_when_rows_match():
    full = pd.DataFrame(
        {"ticker": ["005930"], "signal_date": ["2026-09-22"], "ai_action": [""]}
    )
    updated = full.copy()
    updated.loc[0, "ai_action"] = "BUY"
    merged = reanalysis._merge_reanalysis_updates_into_full_signals_frame(
        updated_signals_df=updated,
        signals_path="signals_log.csv",
        load_csv_file=lambda *_a, **_k: full,
    )
    assert merged.loc[0, "ai_action"] == "BUY"
```

`_VCP_REANALYSIS_UPDATED_COLUMNS` 는 `("ai_action", "ai_confidence", "ai_reason")` 이다(critic R1 로 확정).

- [ ] **Step 2: 실행해 실패 확인**

Run: `source venv/bin/activate && pytest tests/services/test_vcp_signals_log_lock_refactor.py -v`
Expected: import 단계에서 `ImportError: cannot import name 'signals_log_lock'`.

- [ ] **Step 3: 구현**

import 절에 `import fcntl`, `from contextlib import contextmanager`, `typing` 에 `Iterator` 를 더한다. `write_vcp_signals_csv_atomic` 바로 위에:

```python
@contextmanager
def signals_log_lock(signals_path: str) -> Iterator[None]:
    """signals_log.csv 의 읽기·병합·교체를 프로세스와 워커 사이에서 직렬화한다([VCP-035]).

    한 프로세스 안에서 중첩해 잡지 않는다. flock 은 열린 파일 기술자마다 따로 잡혀서 같은
    스레드가 두 번 잡으면 스스로 기다린다. 프로세스가 죽으면 OS 가 잠금을 푼다.
    """
    lock_path = f"{signals_path}.lock"
    os.makedirs(os.path.dirname(lock_path) or ".", exist_ok=True)
    with open(lock_path, "a+") as lock_fp:
        fcntl.flock(lock_fp.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_fp.fileno(), fcntl.LOCK_UN)
```

`_merge_reanalysis_updates_into_full_signals_frame` 의 index 개수 검사 뒤, 열 복사 앞에:

```python
    # 재분석은 AI 호출 동안 잠금을 쥐지 않는다. 그 사이 다른 쓰기가 파일을 다시 정렬했으면
    # 같은 index 가 다른 종목을 가리키므로, 덮지 않고 실패로 끝낸다([VCP-035]).
    for key in ("ticker", "signal_date"):
        if key not in merged.columns or key not in updated_signals_df.columns:
            continue
        current = merged.loc[target_index, key].astype(str).str.strip()
        expected = updated_signals_df.loc[target_index, key].astype(str).str.strip()
        if key == "ticker":
            current, expected = current.str.zfill(6), expected.str.zfill(6)
        if not current.equals(expected):
            raise ValueError(
                f"signals_log.csv rows moved during reanalysis ({key} mismatch). "
                "Another run rewrote the log; run the reanalysis again."
            )
```

688행의 쓰기를 잠금으로 감싼다(병합이 파일을 다시 읽으므로 재읽기·병합·교체가 한 잠금 안에 든다):

```python
        with signals_log_lock(signals_path):
            write_vcp_signals_csv_atomic(
                signals_df,
                signals_path,
                load_csv_file=load_csv_file_for_persist,
                logger=logger,
            )
```

- [ ] **Step 4: 통과 확인**

Run: `pytest tests/services/test_vcp_signals_log_lock_refactor.py tests/services/test_vcp_reanalysis_scope_refactor.py tests/services/test_kr_market_vcp_service.py -q`
Expected: 모두 통과.

### Task 2: `scripts/init_data.py` 의 두 함수

**Files:**
- Modify: `scripts/init_data.py` (import 72행, `create_signals_log` 1587-1625·1633-1644·1658-1660, `update_vcp_signals_recent_price` 1918-1992)
- Test: `tests/services/test_vcp_signals_log_lock_refactor.py`

**Interfaces:**
- Consumes: `signals_log_lock` (Task 1).

- [ ] **Step 1: 실패하는 테스트 추가**

`create_signals_log` 는 스크리너를 가짜로 바꾸는 기존 도우미가 `tests/scripts/test_init_data_vcp_scheduler.py` 에 있다(`_DummyScreener`, `_DummyMarketGate`). 그 두 클래스를 import 해서 쓴다.

```python
import sys
from types import SimpleNamespace

from scripts import init_data
from tests.scripts.test_init_data_vcp_scheduler import _DummyMarketGate, _DummyScreener


def test_create_signals_log_waits_for_lock(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    path = data_dir / "signals_log.csv"
    pd.DataFrame({"ticker": ["000660"], "signal_date": ["2026-09-21"], "score": [1]}).to_csv(path, index=False)
    monkeypatch.setattr(init_data, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr("engine.screener.SmartMoneyScreener", _DummyScreener)
    monkeypatch.setattr("engine.market_gate.MarketGate", _DummyMarketGate)

    _assert_waits_for_lock(path, lambda: init_data.create_signals_log(target_date="2026-02-19", run_ai=False))
    tickers = set(pd.read_csv(path, dtype={"ticker": str})["ticker"])
    assert {"000660", "005930"} <= tickers


def test_recent_price_update_keeps_rows_added_during_fetch(monkeypatch, tmp_path):
    """시세 조회 중 다른 쓰기가 더한 행을 시세 갱신이 지우지 않는다."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    path = data_dir / "signals_log.csv"
    pd.DataFrame(
        {"ticker": ["005930"], "signal_date": ["2026-09-22"], "entry_price": [100.0], "current_price": [100.0], "return_pct": [0.0]}
    ).to_csv(path, index=False)
    monkeypatch.setattr(init_data, "BASE_DIR", str(tmp_path))

    def _ohlcv(_start, _end, ticker):
        # 조회 도중 다른 경로가 행을 하나 더한 상황
        frame = pd.read_csv(path, dtype={"ticker": str})
        if "000660" not in set(frame["ticker"]):
            extra = pd.DataFrame({"ticker": ["000660"], "signal_date": ["2026-09-22"], "entry_price": [50.0], "current_price": [50.0], "return_pct": [0.0]})
            pd.concat([frame, extra]).to_csv(path, index=False)
        return pd.DataFrame({"종가": [110]})

    monkeypatch.setitem(sys.modules, "pykrx", SimpleNamespace(stock=SimpleNamespace(get_market_ohlcv=_ohlcv)))
    init_data.update_vcp_signals_recent_price()

    frame = pd.read_csv(path, dtype={"ticker": str}, encoding="utf-8-sig").set_index("ticker")
    assert "000660" in frame.index
    assert frame.loc["005930", "current_price"] == 110
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/services/test_vcp_signals_log_lock_refactor.py -k "create_signals_log or recent_price" -v`
Expected: 첫 테스트는 「잠금을 쥔 동안 쓰기가 끝났다」로, 둘째는 `000660` 이 없어서 실패한다.

- [ ] **Step 3: 구현**

72행 import 에 `signals_log_lock` 을 더한다: `from services.kr_market_vcp_reanalysis_service import signals_log_lock, write_vcp_signals_csv_atomic`.

`create_signals_log`:
- 시그널 갈래: `if os.path.exists(file_path):` 부터 `else: write_vcp_signals_csv_atomic(df_new, file_path)` 까지를 `with signals_log_lock(file_path):` 아래로 한 단계 들여쓴다. 내부의 `return False` 는 그대로 둔다.
- 시그널 없음 갈래: `cleaned = True` 다음의 `if os.path.exists(file_path): ... else: write_vcp_signals_csv_atomic(...)` 를 같은 방식으로 감싼다.
- 예외 갈래: `if not os.path.exists(file_path): write_vcp_signals_csv_atomic(...)` 두 줄을 감싼다(확인과 생성 사이에 다른 경로가 파일을 만들 수 있다).

`update_vcp_signals_recent_price`:
- 첫 `pd.read_csv` 는 티커 목록을 얻는 용도로 잠금 밖에 둔다. 시세 조회 루프도 잠금 밖이다.
- `log(f"{len(current_prices)}개 종목 현재가 확보 완료. 업데이트 적용 중...")` 다음부터 저장까지를 다음으로 바꾼다.

```python
        # 시세 조회는 잠금 밖에서 한다. 그동안 다른 경로가 쓴 행을 지우지 않도록 잠금 안에서
        # 다시 읽고 티커 기준으로 적용한다([VCP-035]).
        with signals_log_lock(file_path):
            df = pd.read_csv(file_path, dtype={'ticker': str})
            for idx, row in df.iterrows():
                ticker = row['ticker']
                if ticker in current_prices:
                    current_p = current_prices[ticker]
                    entry_p = row['entry_price']

                    df.at[idx, 'current_price'] = current_p
                    if entry_p > 0:
                        ret = ((current_p - entry_p) / entry_p) * 100
                        df.at[idx, 'return_pct'] = round(ret, 2)

                    updated_count += 1

            write_vcp_signals_csv_atomic(df, file_path)
```

`df.to_csv(file_path, index=False, encoding='utf-8-sig')` 줄은 지운다. `write_vcp_signals_csv_atomic` 이 같은 BOM·`index=False` 형식으로 쓰고 캐시도 무효화한다.

- [ ] **Step 4: 통과 확인**

Run: `pytest tests/services/test_vcp_signals_log_lock_refactor.py tests/scripts/test_init_data_vcp_scheduler.py tests/services/test_kr_market_vcp_background_service_refactor.py -q`
Expected: 모두 통과.

### Task 3: `SignalTracker` 두 메서드

**Files:**
- Modify: `engine/signal_tracker_analysis_mixin.py` (import 43행, `_append_to_log` 333-358, `update_open_signals` 360-394)
- Test: `tests/services/test_vcp_signals_log_lock_refactor.py`

- [ ] **Step 1: 실패하는 테스트 추가**

```python
from engine.signal_tracker import SignalTracker


def test_append_to_log_waits_for_lock(tmp_path):
    tracker = SignalTracker(data_dir=str(tmp_path))
    path = tmp_path / "signals_log.csv"
    pd.DataFrame({"ticker": ["000660"], "signal_date": ["2026-09-21"], "status": ["OPEN"]}).to_csv(path, index=False)
    new = pd.DataFrame({"ticker": ["005930"], "signal_date": ["2026-09-22"], "status": ["OPEN"]})

    _assert_waits_for_lock(path, lambda: tracker._append_to_log(new))
    assert {"000660", "005930"} <= set(pd.read_csv(path, dtype={"ticker": str})["ticker"])
```

`normalize_new_signals_for_log` 가 요구하는 열이 더 있으면 `tests/engine/test_signal_tracker_refactor.py` 의 `_append_to_log` 사례에서 쓰는 입력 형태를 그대로 옮긴다.

`update_open_signals` 는 가격 맵이 필요해 대기 검사 대신 Step 3 의 들여쓰기로 충분하다고 보고 별도 테스트를 두지 않는다. 기존 `tests/engine/test_signal_tracker_refactor.py` 의 `update_open_signals` 사례가 동작 회귀를 잡는다.

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/services/test_vcp_signals_log_lock_refactor.py -k append -v`
Expected: 「잠금을 쥔 동안 쓰기가 끝났다」로 실패.

- [ ] **Step 3: 구현**

43행 import 를 `from services.kr_market_vcp_reanalysis_service import signals_log_lock, write_vcp_signals_csv_atomic` 로 바꾼다.

`_append_to_log`: `working_new` 가 비었는지 확인하는 조기 반환 뒤, `if not os.path.exists(self.signals_log_path):` 부터 마지막 `logger.info` 까지를 `with signals_log_lock(self.signals_log_path):` 아래로 들여쓴다.

`update_open_signals`: 메서드 본문 전체(`if not os.path.exists(...)` 부터 마지막 `logger.info` 까지)를 `with signals_log_lock(self.signals_log_path):` 아래로 들여쓴다. 가격 맵은 생성자가 로컬 파일로 만들어 두므로 잠금 안에 네트워크 호출이 없다.

- [ ] **Step 4: 통과 확인**

Run: `pytest tests/services/test_vcp_signals_log_lock_refactor.py tests/engine/test_signal_tracker_refactor.py tests/test_run_menu_refactor.py -q`
Expected: 모두 통과.

### Task 4: 교착 점검과 전체 회귀

- [ ] **Step 1: 중첩 호출이 없는지 확인**

Run: `grep -n "signals_log_lock" -r scripts services engine app`
Expected: 잠금 안에서 부르는 함수(`write_vcp_signals_csv_atomic`, `_read_signals_log`, `append_signals_log`, `update_open_signals_frame`, `_refresh_signals_log_source_cache`, `_merge_reanalysis_updates_into_full_signals_frame`)가 스스로 잠금을 잡지 않는다. 호출 순서가 순차인지 확인한다: `run_vcp_background_pipeline`(생성 → 시세 갱신), `run_vcp_signals_step`(생성 → 열린 시그널 갱신), `init_data` 의 `__main__` 메뉴.

- [ ] **Step 2: 전체 회귀**

Run: `source venv/bin/activate && pytest -q`
Expected: exit 0. `[INFRA-083]` 의 세션 끝 검사(원본 `data/`·`logs/` 불변) 포함.

### Task 5: QA 하네스(격리 사본)

화면에서 이 경로에 들어가려면 Refresh VCP 나 실패 AI 재분석을 눌러야 하고 둘 다 금지 조작이다. 그래서 `closing-bet-verify` 의 서비스 하네스 등급으로 검사하고 근거를 `docs/dev-cycle/qa/VCP-035.md` 에 적는다.

- scratchpad 의 `git archive` 사본 두 개(기준 커밋과 구현 커밋)에서 같은 스크립트를 돌린다. 스크립트는 `tmp` 디렉터리의 `signals_log.csv` 에 대해 `multiprocessing` 으로 프로세스 네 개를 띄우고, 각자 서로 다른 티커 25개를 `SignalTracker._append_to_log` 로 하나씩 더한다.
- 기대: 기준 커밋에서는 최종 행 수가 100 보다 작은 회차가 나온다(유실 재현). 구현 커밋에서는 10회 모두 100 이다. 유실이 기준에서 재현되지 않으면 그 사실을 그대로 적고 구현 커밋의 100 만 증거로 쓴다.
- 원본 `data/` 와 서버 포트를 쓰지 않는다. 끝나면 사본을 지운다.

## critic 검토 반영 (2026-09-23, ACCEPT-WITH-RESERVATIONS)

- R1: 재분석 테스트의 열을 `ai_action` 으로 확정했다.
- R2: 대기 검사 스레드를 daemon 으로 두었다.
- R3: `create_signals_log`·`_append_to_log` 대기 검사에서, 잠금을 쥔 동안 본 스레드가 표지 행을 파일에 쓰고 풀린 뒤 그 행이 남았는지 단언한다. 재읽기가 잠금 뒤에 일어났음을 사후 조건으로 확인한다.
- R4: 재분석 중에 생성이 끝나면 `create_signals_log` 의 재정렬로 index 가 밀려 재분석이 항상 오류로 끝나고, AI 결과는 CSV·캐시에 남지 않는다. 승인 범위(덮지 않고 오류)와 맞으므로 동작은 유지하고, 오류 문구에 재실행 안내를 넣었다. QA 문서에도 기록한다.
- R5: Global Constraints 의 호출자 수 서술을 정정했다.
