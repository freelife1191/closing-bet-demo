# [INFRA-090] 일별 가격 수집의 휴장일 0원 행 차단 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `create_daily_prices` 가 평일 휴장일에 pykrx 가 돌려주는 전 종목 0원 행을 저장하지 않고, 이미 저장된 0원 날짜는 다음 저장 때 파일에서 빠지게 한다.

**Architecture:** 한 날짜의 종가가 전부 0 이면 휴장일로 본다. 판정은 `scripts/init_data.py` 의 헬퍼 `_all_zero_close_dates(df)` 하나에 두고 두 곳에서 쓴다. (1) 기존 `daily_prices.csv` 를 읽은 직후 그 날짜들을 `existing_df` 에서 뺀다. 그러면 `max_date` 계산과 Skip 판정에서도 빠지고, 다음 저장(pykrx 경로나 yfinance 폴백 모두 `existing_df` 를 합쳐 파일 전체를 다시 쓴다) 때 파일에서 사라진다. (2) 날짜별 루프에서 받은 프레임이 그 조건이면 건너뛴다. 구간 안의 평일이 모두 휴장일로 건너뛰어졌으면 yfinance 폴백으로 가지 않고 `True` 로 끝낸다.

**Tech Stack:** Python 3.11, pandas, pytest, 가짜 pykrx 모듈(`sys.modules` monkeypatch)

**Spec:** 대화 설계(bounded, 2026-09-24 10:17 KST 확인, 사용자 선택 「저장 시 자동 정리 (권장)」). 원인 기록은 `docs/dev-cycle/qa/INFRA-088.md` 「휴장일 0원 행」, 항목 원문은 `docs/dev-cycle/TODO.md` 의 `[INFRA-090]`

## 계획 검토 반영 (critic REVISE, 2026-09-24)

아래 Task 1 은 원안이며 다음 지적을 모두 반영해 구현한다. 실제 코드와 테스트는 커밋 diff 가 정본이다.

- 테스트 2 대조 케이스: 빈 프레임만 주면 `holiday_days=0` 이라 `not missed_days` 를 잡지 못한다. 휴장일(0원)과 빈 결과가 **섞인** 구간에서 폴백 1회를 확인한다
- 테스트 1·2 구간 고정: 기존 파일이 없으면 구간이 90일이 된다(`:902`). 기존 파일에 직전 거래일 정상 행을 두고 `force=False` 로 돌려 구간을 1~2일로 만든다. 테스트 2 는 직전 거래일 행이 덮어써지지 않는지도 본다
- 테스트 1: 정상 거래일에 **종가 0** 인 종목을 하나 넣고 그 행이 저장되는지 본다(`.any()` 오구현을 잡는다)
- 제거 위치: `read_csv` 직후, `:907` 의 `if not existing_df.empty` 앞. 파일 전체가 0원이면 `max()` 가 NaN 이 되기 때문이다
- `STOP_REQUESTED` 로 끊긴 실행은 폴백 생략 대상이 아니다(종전 경로 유지)
- 로그 문구는 휴장일로 단정하지 않고 「전 종목 종가 0, 저장 생략」으로 쓴다
- 헬퍼의 `df is None` 가드는 호출자가 None 을 넘기지 않으므로 뺀다
- 의도한 변화: 구간 안 평일이 전부 휴장일이면 종전에는 yfinance 폴백으로 가서 직전 거래일을 일부 종목으로 덮어썼다(`[INFRA-088]` 3차). 이제 `True` 로 끝난다

## Global Constraints

- 휴장일 판정: 그 날짜의 **모든 행**의 종가(`close`)가 0 이다. 숫자로 바꿀 수 없는 값은 0 으로 본다. 거래정지 종목처럼 시가·고가·저가만 0 인 행은 판정에 쓰지 않는다
- 과거 0원 날짜 정리는 파일을 따로 고치지 않고 다음 저장에 맡긴다(승인 선택)
- 폴백 생략은 **건너뛴 평일이 전부 휴장일일 때만**이다. 빈 결과(`df.empty`)나 날짜별 예외가 하나라도 있으면 종전대로 yfinance 폴백으로 간다
- `fetch_prices_yfinance` 와 `[INFRA-088]` 범위(부분 저장, 죽은 분기)는 건드리지 않는다
- 테스트는 `tmp_path` 와 가짜 pykrx 만 쓴다. 네트워크·원본 `data/` 에 닿지 않는다
- pytest 는 `venv/bin/python -m pytest` 로 돌린다

## Review Focus

- 거래정지 종목 몇 개만 종가 0 인 정상 거래일은 저장되어야 한다 (Task 1 테스트 1)
- 휴장일 하루만 있는 구간(연휴 중 17:00 실행)은 yfinance 폴백을 부르지 않아야 한다. 부르면 직전 거래일을 일부 종목으로 덮어쓴다 (Task 1 테스트 2)
- 기존 파일의 0원 날짜가 마지막 날짜이면 `max_date` 가 그 앞 날짜로 돌아가 그 날짜를 다시 조회하고, 다시 휴장일로 건너뛴다 (Task 1 테스트 3)
- 기존 파일에 `close` 열이 없거나 파일이 비어 있으면 헬퍼가 예외 없이 빈 목록을 돌려야 한다 (Task 1 테스트 4)
- 휴장일과 빈 결과가 섞인 구간은 종전대로 폴백해야 한다 (Task 1 테스트 2 의 대조 케이스)

---

### Task 1: 휴장일 판정 헬퍼와 두 적용 지점

**Files:**
- Modify: `scripts/init_data.py` (헬퍼 추가는 `_should_abort_daily_pykrx_bulk_fetch` 바로 뒤, 적용은 `create_daily_prices` 의 기존 파일 로드 직후와 날짜별 루프, 저장 분기)
- Test: `tests/scripts/test_init_data_vcp_scheduler.py` (기존 `test_create_daily_prices_switches_to_yfinance_on_known_pykrx_error` 의 가짜 pykrx 패턴을 따른다)

**Interfaces:**
- Produces: `_all_zero_close_dates(df: pd.DataFrame) -> List[str]` — `date`·`close` 열이 없으면 `[]`

- [ ] **Step 1: 실패하는 테스트 작성**

가짜 pykrx `get_market_ohlcv(date_str, market="ALL")` 는 날짜별로 미리 만든 프레임(index=티커, 열 `시가·고가·저가·종가·거래량·거래대금`)을 돌려준다. `get_last_trading_date` 와 `fetch_prices_yfinance` 는 monkeypatch 로 대체하고, `log` 는 목록에 모은다.

1. `test_create_daily_prices_skips_holiday_zero_close_but_keeps_suspended_ticker`: 2026-09-22(정상, 한 종목은 시가·고가·저가 0·종가 1000), 2026-09-23(휴장, 전 종목 0). `force=True, lookback_days=1`, 기준일 09-23. 저장 파일에 09-22 두 종목이 있고 09-23 은 없다
2. `test_create_daily_prices_holiday_only_range_does_not_fall_back`: 기준일 09-24, 전 종목 0. 반환 `True`, 폴백 호출 0회. 대조: 같은 구간에 빈 프레임을 주면 폴백 1회
3. `test_create_daily_prices_drops_stored_holiday_rows_on_next_save`: 기존 파일에 09-21(정상)·09-22(전 종목 0) 을 두고 기준일 09-23(정상)으로 `force=False` 실행. 가짜 pykrx 는 09-22 에 0원 프레임, 09-23 에 정상 프레임을 준다. 저장 파일의 날짜는 09-21·09-23 이다
4. `test_all_zero_close_dates_handles_missing_columns`: 빈 프레임과 `close` 없는 프레임에 `[]`

- [ ] **Step 2: 실패 확인** — `venv/bin/python -m pytest tests/scripts/test_init_data_vcp_scheduler.py -k "holiday or zero_close" -v`. 1·2·3 은 실패(0원 행 저장, 폴백 호출), 4 는 `AttributeError`

- [ ] **Step 3: 최소 구현**

```python
def _all_zero_close_dates(df: pd.DataFrame) -> List[str]:
    """종가가 전 종목 0 인 날짜. pykrx 는 평일 휴장일에 이런 행을 돌려준다([INFRA-090])."""
    if df is None or df.empty or "date" not in df.columns or "close" not in df.columns:
        return []
    zero = pd.to_numeric(df["close"], errors="coerce").fillna(0).eq(0).groupby(df["date"]).all()
    return [str(d) for d in zero[zero].index]
```

- 기존 파일 로드 직후: 목록이 있으면 WARNING 로그를 남기고 `existing_df = existing_df[~existing_df["date"].isin(dates)]`
- 날짜별 루프: `df["date"] = cur_date_fmt` 뒤 `_all_zero_close_dates(df)` 가 있으면 INFO 로그, `holiday_days += 1`, `processed_days += 1`, `continue`. `df.empty` 분기와 예외 분기에서는 `missed_days += 1`
- 저장 분기의 `else`: `start > end` 검사 다음에 `if holiday_days and not missed_days:` 로그 후 `return True`

- [ ] **Step 4: 통과 확인** — 같은 명령, 이어서 `venv/bin/python -m pytest tests/scripts -q`

- [ ] **Step 5: 커밋** — `fix(data): [INFRA-090] skip KRX holiday zero-price rows in daily collection`
