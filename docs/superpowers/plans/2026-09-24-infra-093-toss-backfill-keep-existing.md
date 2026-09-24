# [INFRA-093] Toss 백필이 기존 수급 행을 덮지 않게 한다 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `_backfill_institutional_trend_from_toss` 가 파일에 이미 있는 (date, ticker) 행(pykrx 의 정확한 `순매수거래대금`)을 근사값으로 덮지 않고 빈 칸만 채우게 한다.

**Architecture:** 공용 병합 함수 `_merge_save_csv(new_df, file_path)` 에 `keep: str = "last"` 인자 하나를 더해 `drop_duplicates(keep=...)` 에 넘긴다. 병합 순서가 `[잠금 안에서 다시 읽은 기존 파일, 새 행]` 이므로 백필이 `keep="first"` 로 부르면 기존 행이 이긴다. 다른 호출자 셋(가격 파일 두 곳, pykrx 수급)은 기본값 그대로다.

**Tech Stack:** Python 3.11, pandas, pytest

**Spec:** 대화 설계(2026-09-24 21:55 승인, `docs/dev-cycle/TODO.md` `[INFRA-093]` 설계 승인 줄)

## Global Constraints

- 새 함수·상수·설정을 만들지 않는다. 인자 하나와 호출 한 곳만 바꾼다.
- 기존 호출자(`scripts/init_data.py:832`, `:1108`, `:1305`)의 동작은 바뀌지 않아야 한다.
- 테스트와 QA 는 가짜 pykrx·Toss 만 쓴다. 실제 네트워크·KRX 로그인·원본 `data/` 쓰기는 금지.
- 운영 반영은 gunicorn 워커를 모두 재기동해야 한다(장 중 금지).

## Review Focus

- 겹친 실행: 백필이 수집하는 사이 다른 실행이 pykrx 로 저장한 행도 보존되어야 한다. 기존 파일을 잠금 안에서 다시 읽으므로 `keep="first"` 가 그 행도 지킨다. 테스트가 `on_fetch` 로 이 경우를 직접 만든다.
- 백필이 처음 채우는 (date, ticker) 는 종전처럼 저장되어야 한다(빈 칸 채움이 사라지면 회귀).
- 0원 날짜 제거(`_all_zero_close_dates`)는 `close` 열이 없는 수급 파일에 영향이 없어야 한다. 기존 동작 그대로다.
- 잔여 위험(범위 밖, critic R1): pykrx 경로는 과거 날짜에 행이 하나라도 있으면 그 날짜를 Skip 하므로(`scripts/init_data.py:1242-1248`), 한 번 저장된 Toss 근사값은 lookback 재수집이나 force 가 아니면 정확한 값으로 바뀌지 않는다. 수정 전부터 있던 동작이며 `[INFRA-094]` 로 이월한다.
- 백필 행끼리의 중복은 없다(한 종목의 Toss 상세는 날짜가 서로 다르다). `keep="first"` 가 새 행 사이에서 고르는 경우는 생기지 않는다.

---

### Task 1: 백필은 기존 행을 보존한다

**Files:**
- Modify: `scripts/init_data.py` (`_merge_save_csv` `:869-892`, 백필 호출 `:441`)
- Test: `tests/scripts/test_init_data_vcp_scheduler.py` (`test_toss_trend_backfill_keeps_rows_saved_by_overlapping_run` 뒤)

**Interfaces:**
- Consumes: `_run_trend_with_fake_krx(monkeypatch, tmp_path, on_fetch, toss_rows=None)` (기존 파일 09-21 에 `000001`·`069500` 이 `foreign_buy=1, inst_buy=2`, 기대 최신일 09-22)
- Produces: `_merge_save_csv(new_df, file_path, keep="last")`

- [ ] **Step 1: 실패하는 테스트 작성** (critic 검토 시점에 이미 작성됨. 중복 추가하지 않고 RED 만 확인한다)

```python
def test_toss_trend_backfill_does_not_overwrite_existing_rows(monkeypatch, tmp_path):
    # Toss 근사값은 빈 (date, ticker) 만 채우고 pykrx 로 저장된 값은 덮지 않는다([INFRA-093])
    file_path = tmp_path / "data" / "all_institutional_trend_data.csv"

    def _other_run_saves_exact_value():
        other = pd.read_csv(file_path, dtype={"ticker": str, "date": str})
        other.loc[len(other)] = ["2026-09-22", "000001", 30, 40]
        other.to_csv(file_path, index=False)

    toss_rows = [
        {"baseDate": d, "close": 1000, "netForeignerBuyVolume": 7, "netInstitutionBuyVolume": 9}
        for d in ("2026-09-22", "2026-09-21", "2026-09-18")
    ]
    result, _ = _run_trend_with_fake_krx(
        monkeypatch, tmp_path, _other_run_saves_exact_value, toss_rows=toss_rows
    )

    saved = pd.read_csv(file_path, dtype={"ticker": str, "date": str})
    values = {
        (d, t): (f, i)
        for d, t, f, i in zip(saved["date"], saved["ticker"], saved["foreign_buy"], saved["inst_buy"])
    }
    assert result is True
    assert values[("2026-09-21", "000001")] == (1, 2)
    assert values[("2026-09-22", "000001")] == (30, 40)
    assert values[("2026-09-18", "000001")] == (7000, 9000)
```

- [ ] **Step 2: 실패 확인**

Run: `venv/bin/python -m pytest tests/scripts/test_init_data_vcp_scheduler.py -k does_not_overwrite_existing_rows -q`
Expected: FAIL (`(7000, 9000) != (1, 2)`)

- [ ] **Step 3: 최소 구현**

`_merge_save_csv` 시그니처와 중복 제거:

```python
def _merge_save_csv(new_df: pd.DataFrame, file_path: str, keep: str = "last") -> pd.DataFrame:
    ...
        final_df = final_df.drop_duplicates(subset=["date", "ticker"], keep=keep)
```

docstring 에 한 문장 추가: `keep="first"` 이면 파일에 이미 있는 (date, ticker) 가 이긴다(Toss 백필, [INFRA-093]).

백필 호출:

```python
    # [INFRA-093] 근사값은 빈 칸만 채운다. pykrx 로 저장된 정확한 순매수거래대금을 덮지 않는다
    final_df = _merge_save_csv(pd.DataFrame(collected_rows), file_path, keep="first")
```

- [ ] **Step 4: 통과 확인**

Run: `venv/bin/python -m pytest tests/scripts/test_init_data_vcp_scheduler.py -q`
Expected: 전부 PASS

- [ ] **Step 5: 전체 확인**

Run: `venv/bin/python -m pytest -q`
Expected: 실패 0
