# [VCP-030] signals_log.csv 원자적 쓰기와 빈 파일 회복 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `create_signals_log` 가 `signals_log.csv` 를 자르고 쓰지 않게 하고, 0바이트 파일에서 스스로 회복하게 한다.

**Architecture:** 쓰기 다섯 곳을 이미 있는 `services/kr_market_vcp_reanalysis_service.write_vcp_signals_csv_atomic(df, path)` 로 바꾼다. 이 함수는 `"\ufeff" + df.to_csv(index=False)` 를 `atomic_write_text`(임시 파일 → fsync → `os.replace` → 캐시 무효화)로 쓴다. 종전 `to_csv(..., encoding='utf-8-sig')` 와 바이트가 같다. 기존 로그를 읽는 두 곳은 새 도우미 `_read_signals_log` 를 거쳐 `EmptyDataError` 를 빈 로그로 바꾼다.

**Tech Stack:** Python 3.11, pandas, pytest.

**Spec:** 별도 설계 문서 없음(bounded). 2026-09-23 대화에서 설계를 제시하고 사용자가 「응 진행해」로 승인했다. 요지는 `docs/dev-cycle/TODO.md` 의 `[VCP-030]` 설계 승인 줄에 있다.

## Global Constraints

- `scripts/init_data.py` 는 위험 경로이므로 티어는 T3 이다.
- `create_signals_log` 의 반환 계약은 유지한다. 시그널 저장 성공과 당일 정리 성공은 True, 병합·정리 실패와 예외는 False 이다.
- `[VCP-028]`(예외 갈래는 기존 로그를 건드리지 않음)과 `[VCP-029]`(병합·정리 실패 시 기존 로그 보존 + False)를 유지한다.
- 열 수가 어긋난 파일(`ParserError`)은 이번에도 보존 + False 이다. `.corrupt-<시각>` 격리는 하지 않는다(사용자 결정).
- `write_vcp_signals_csv_atomic` 은 고치지 않는다. `load_csv_file` 인자를 넘기지 않으므로 재분석용 병합 경로는 타지 않는다.
- 파일 저장 형식(UTF-8 BOM, 인덱스 없음, 줄바꿈 `\n`)은 종전과 같다.

## 수용한 동작 차이와 기록할 사실

1. 쓰기 뒤 `invalidate_file_cache` 가 불린다. 스케줄러가 도는 워커의 CSV 메모리 캐시가 바로 비워지고, 같은 디렉터리의 `runtime_cache.db`(`services/kr_market_data_cache_sqlite_payload.py:92-94` 의 `resolve_payload_sqlite_db_path` 가 `dirname(signals_log.csv)` 로 정함)의 해당 경로 행에 DELETE 가 간다. 다른 워커는 종전처럼 파일 서명(mtime·size)으로 새 파일을 알아챈다. 테스트에서는 `tmp_path/data/runtime_cache.db` 가 새로 생길 뿐 원본에는 닿지 않는다(계획 검토 R2). 전체 pytest 를 사본에서 돌리는 것은 `[INFRA-083]` 의 다른 이유 때문이다.
2. 쓰는 쪽과 읽는 쪽의 관용도 차이(TODO 의 M2·m4): 쓰는 쪽은 전체 열을 읽으므로 열 수가 어긋난 파일에서 `ParserError` 로 멈춘다. 읽는 쪽(`services/kr_market_vcp_payload_service.py:169-173`, `app/routes/kr_market_data_signals_routes.py:65-71`)은 `usecols` 로 읽어 예외 없이 옛 행을 계속 보인다. 이번 변경은 이 차이를 없애지 않는다. 원자적 쓰기 뒤로 코드가 그런 파일을 만들 경로는 없고, 남는 원인은 사람의 편집이나 스키마 변경뿐이다.
3. 0바이트 파일일 때 데이터 상태 화면이 「오늘」로 보이던 문제(`services/common_data_status_service.py:71`)는 이번 변경으로 다음 실행이 파일을 다시 쓰면서 해소된다. 대체 로직 자체는 고치지 않는다.
4. 헤더만 있는 파일은 지금도 빈 DataFrame 으로 읽히므로 따로 처리하지 않는다.
5. 파일 권한이 0644 에서 0600 으로 바뀐다. `NamedTemporaryFile` 이 0600 으로 만들고 `os.replace` 가 그 권한을 옮긴다. 운영 `data/signals_log.csv` 도 다음 실행부터 0600 이다. 다른 사용자로 이 파일을 읽는 소비자는 저장소에 없고, 재분석 경로가 이미 같은 함수로 쓰고 있어 종전에도 0600 이 섞였을 수 있다(계획 검토 R3).
6. 디스크가 가득 찼고(ENOSPC) 로그 파일이 없을 때, 새 파일 갈래가 실패하면 바깥 except 로 넘어가고 거기서 빈 파일 쓰기도 실패해 `create_signals_log` 가 False 대신 `OSError` 를 던진다. 종전에는 잘린 파일이 남아 빈 파일 쓰기를 건너뛰었다. 두 호출자(`services/kr_market_vcp_background_service.py:77`, `services/common_update_pipeline_steps.py:220`)가 모두 예외를 받아 실패로 처리하므로 결과는 같다(계획 검토 m1, 기록만 함). 이때 예외 갈래의 `_write_vcp_signals_latest_payload` 도 불리지 않아 `vcp_signals_latest.json` 이 갱신되지 않는다. 종전 `to_csv` 도 같은 자리에서 실패할 수 있었으므로 새 회귀는 아니다(코드 리뷰 지적 2).
7. 원자성은 `create_signals_log` 의 쓰기에만 해당한다. 같은 파이프라인에서 바로 뒤에 도는 `SignalTracker`(`engine/signal_tracker_analysis_mixin.py:339,387,423`)는 여전히 `to_csv` 로 같은 파일을 자르고 쓴다. 이 세 곳은 `[VCP-034]` 로 넘긴다(코드 리뷰 지적 1).
8. 운영 `data/signals_log.csv` 가 symlink 라면 `os.replace` 가 링크를 일반 파일로 바꾼다. 이 기기에서 `data/` 를 열지 않으므로 확인하지 않았고, 재분석 경로가 이미 같은 함수로 쓰고 있다(심층 리뷰 평가 불가 항목).

---

### Task 1: 회귀 테스트(RED)

**Files:**
- Modify: `tests/scripts/test_init_data_vcp_scheduler.py` (끝에 세 건 추가, 기존 `_DummyScreener`·`_DummyMarketGate`·`_EmptyScreener` 재사용)

- [ ] **Step 1: 테스트 작성**

```python
def test_create_signals_log_recovers_from_empty_log_with_signals(monkeypatch, tmp_path):
    """[VCP-030] 0바이트 로그가 있어도 오늘 자 시그널을 저장한다."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "signals_log.csv").write_bytes(b"")

    monkeypatch.setattr(init_data, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr("engine.screener.SmartMoneyScreener", _DummyScreener)
    monkeypatch.setattr("engine.market_gate.MarketGate", _DummyMarketGate)

    assert init_data.create_signals_log(target_date="2026-02-19", run_ai=False) is True

    raw = (data_dir / "signals_log.csv").read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    df = pd.read_csv(data_dir / "signals_log.csv", dtype={"ticker": str})
    assert df["ticker"].tolist() == ["005930"]


def test_create_signals_log_recovers_from_empty_log_without_signals(monkeypatch, tmp_path):
    """[VCP-030] 0바이트 로그에서 시그널이 없으면 헤더만 있는 로그로 바꾸고 성공한다."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "signals_log.csv").write_bytes(b"")

    monkeypatch.setattr(init_data, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr("engine.screener.SmartMoneyScreener", _EmptyScreener)
    monkeypatch.setattr("engine.market_gate.MarketGate", _DummyMarketGate)

    assert init_data.create_signals_log(target_date="2026-03-06", run_ai=False) is True

    df = pd.read_csv(data_dir / "signals_log.csv")
    assert df.empty
    assert "signal_date" in df.columns


@pytest.mark.parametrize("screener", [_DummyScreener, _EmptyScreener], ids=["merge", "cleanup"])
def test_create_signals_log_keeps_log_bytes_when_write_fails(monkeypatch, tmp_path, screener):
    """[VCP-030] 병합·당일 정리 쓰기가 도중에 실패해도 기존 로그가 잘리지 않는다."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    log_path = data_dir / "signals_log.csv"
    pd.DataFrame(
        [{"ticker": "000660", "signal_date": "2026-02-18", "score": 70}]
    ).to_csv(log_path, index=False, encoding="utf-8-sig")
    before = log_path.read_bytes()

    def _failing_fsync(_fd):
        raise OSError("forced fsync failure")

    monkeypatch.setattr(init_data, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr("engine.screener.SmartMoneyScreener", screener)
    monkeypatch.setattr("engine.market_gate.MarketGate", _DummyMarketGate)
    monkeypatch.setattr("services.kr_market_data_cache_core.os.fsync", _failing_fsync)

    assert init_data.create_signals_log(target_date="2026-02-19", run_ai=False) is False
    assert log_path.read_bytes() == before
    assert [p.name for p in data_dir.iterdir() if p.name.startswith("signals_log.csv.")] == []
```

`os.fsync` 패치는 `services.kr_market_data_cache_core` 모듈의 `os` 이름에 걸지만, 그 이름은 전역 `os` 모듈과 같은 객체이므로 테스트 동안에는 모든 fsync 가 실패한다. 먼저 불리는 `_write_vcp_signals_latest_payload`(`scripts/init_data.py:470-471`)는 `open` 과 `json.dump` 로만 쓰고 fsync 를 부르지 않으므로(2026-09-23 확인) 영향이 없다.

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/scripts/test_init_data_vcp_scheduler.py -q -k "recovers_from_empty or keeps_log_bytes"`
Expected: 4건 FAIL(세 테스트, 마지막 테스트는 merge·cleanup 두 경우). 앞의 두 건은 `EmptyDataError` 때문에 False 를 돌려받는다. 마지막 테스트는 `to_csv` 가 fsync 를 부르지 않아 쓰기가 성공하므로 True 를 돌려받는다. 테스트 파일에 `import pytest` 가 없으면 추가한다.

### Task 2: 구현(GREEN)

**Files:**
- Modify: `scripts/init_data.py` (import 한 줄, `_SIGNALS_LOG_COLUMNS` 아래 도우미, `create_signals_log` 1567-1650 의 읽기 두 곳·쓰기 다섯 곳)

- [ ] **Step 1: import 와 읽기 도우미**

```python
from services.kr_market_vcp_reanalysis_service import write_vcp_signals_csv_atomic
```

```python
def _read_signals_log(file_path: str) -> pd.DataFrame:
    """누적 로그를 읽는다. 0바이트·BOM 만 든 파일은 기존 로그가 없는 것으로 본다([VCP-030])."""
    try:
        return pd.read_csv(file_path, dtype={'ticker': str, 'signal_date': str})
    except pd.errors.EmptyDataError:
        log(f"{file_path} 가 비어 있어 기존 로그 없이 이어갑니다.", "WARNING")
        return pd.DataFrame(columns=_SIGNALS_LOG_COLUMNS)
```

- [ ] **Step 2: 읽기 두 곳을 `_read_signals_log(file_path)` 로, 쓰기 다섯 곳을 `write_vcp_signals_csv_atomic(<df>, file_path)` 로 바꾼다.** 병합(`df_combined`), 새 파일(`df_new`), 당일 정리(`existing_df`), 시그널 없음 빈 파일, 예외 갈래 빈 파일이다. 예외 처리의 모양과 로그 문구는 그대로 둔다.

- [ ] **Step 3: 통과 확인**

Run: `pytest tests/scripts/test_init_data_vcp_scheduler.py tests/scripts/test_init_data_module_contract.py tests/services/test_kr_market_vcp_background_service_refactor.py tests/services/test_scheduler_jobs_refactor.py tests/app/test_common_update_service.py -q`
Expected: 전부 PASS.

### Task 3: 검증과 커밋

- [ ] 변이 확인: 읽기 도우미의 `except` 를 지우면 앞의 두 테스트가, 병합 쓰기를 `to_csv` 로 되돌리면 `keeps_log_bytes[merge]` 가, 당일 정리 쓰기를 `to_csv` 로 되돌리면 `keeps_log_bytes[cleanup]` 이 실패한다(계획 검토 R1).
- [ ] 전체 pytest 는 사본에서 돌린다(`[INFRA-083]`).
- [ ] QA 문서 `docs/dev-cycle/qa/VCP-030.md` 를 만들고 첫 커밋 `fix(vcp): [VCP-030] write signals_log.csv atomically and recover from an empty log` 를 남긴다.
