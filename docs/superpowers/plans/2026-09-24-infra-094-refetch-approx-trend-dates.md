# [INFRA-094] 수급 근사·부분 날짜를 pykrx 로 다시 받는다 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Toss 백필이 저장한 근사값과 일부 종목만 저장된 날짜를, 최근 `lookback_days` 창 안에 있는 동안 다음 수급 수집이 pykrx 의 정확한 `순매수거래대금` 으로 바꾸게 한다.

**Architecture:** 백필 행에 `source="toss"` 열을 붙인다(pykrx 행은 빈 칸). `create_institutional_trend` 는 기존 파일을 읽은 뒤 창(`end - lookback_days` ~ `end`) 안에서 Toss 행이 있거나 행 수가 종목 수의 80% 미만인 날짜를 `refetch_dates` 로 모은다. 있으면 시작일을 그 가장 이른 날로 당기고, 날짜 루프의 「데이터 존재 (Skip)」에서 그 날짜를 뺀다. pykrx 결과는 기존 `_merge_save_csv(keep="last")` 로 근사값을 덮는다.

**Tech Stack:** Python 3.11, pandas, pytest

**Spec:** 대화 설계(2026-09-24 22:06 승인, `docs/dev-cycle/TODO.md` `[INFRA-094]` 설계 승인 줄)

## Global Constraints

- 새 설정·상수를 만들지 않는다. 기준 80% 는 같은 함수의 최신일 판정(`last_date_tickers < len(tickers_set) * 0.8`)과 같다.
- 창 밖 날짜는 재수집하지 않는다. `# ponytail:` 주석으로 한계를 적는다.
- 결측 0(pykrx 한쪽 프레임, Toss `or 0`)은 `[INFRA-095]` 범위라 건드리지 않는다.
- 테스트와 QA 는 가짜 pykrx·Toss 만 쓴다. 실제 네트워크·KRX 로그인·원본 `data/` 쓰기는 금지.
- 운영 반영은 gunicorn 워커를 모두 재기동해야 한다(장 중 금지).

## Review Focus

- `source` 열이 없는 기존 파일(운영의 현재 파일)도 행 수 기준만으로 동작해야 한다.
- pykrx 가 재수집 날짜에 또 빈 응답이면 파일은 그대로이고 `True` 로 끝나야 한다(최신일이 기대일 이상이므로 백필·stale 오류로 가지 않는다).
- 재수집으로 덮인 행은 `source` 가 빈 칸이 되어 다음 실행에서 다시 대상이 되지 않아야 한다. pykrx 가 주지 않는 종목(ETF 등)의 Toss 행은 남아 창을 벗어날 때까지 그 날짜를 매 실행 다시 묻는다(critic 지적 2, 비용 한계로 수용하고 `ponytail:` 주석에 명시).
- (critic 지적 1 반영) 과거 날짜 재수집으로 `new_data_list` 가 비지 않아도 최신일이 기대일보다 이르면 Toss 백필·stale 판정을 타야 한다. 저장 뒤 최신일을 확인해 이르면 빈 응답 분기와 같은 꼬리로 넘긴다. 테스트 `test_create_institutional_trend_backfills_latest_date_after_refetching_past_dates`.
- 수급 CSV 를 읽는 곳(`engine/market_gate_fetchers_local.py:150` 의 `usecols`, 스크리너·시그널 추적·챗봇)은 열 이름으로 고르므로 열 추가에 영향이 없어야 한다.
- 재수집 대상이 없을 때 pykrx 호출 수는 수정 전과 같아야 한다. 결과는 한 경우에 달라진다(리뷰 반영, 의도한 계약 변경): 수집한 날짜가 있어도 최신일이 기대일보다 이르면 수정 전은 `True`, 수정 뒤는 Toss 백필을 시도하고 그것도 실패하면 `False`(stale). 주 호출자 `run_institutional_trend_step` 는 원래 stale 을 따로 검증해 실패로 봤고, 스케줄러는 `False` 를 로그에만 남긴다.
- (리뷰 반영) 다시 받는 날짜는 두 프레임에 모두 있는 종목만 덮는다. 한쪽 프레임 누락의 0 기본값(`[INFRA-095]`)이 기존 정확값·근사값을 지우지 않게 한다. 새 날짜의 동작은 그대로다.
- (리뷰 반영) 사용자 중단 뒤에는 Toss 백필을 시작하지 않고 `False` 로 끝난다.
- 알려진 비용: 시작일을 당기면 그 사이 파일에 없는 날짜(평일 휴장일 포함)도 창 안에 있는 동안 매 실행 조회한다(날짜당 2회).

---

### Task 1: 창 안의 근사·부분 날짜 재수집

**Files:**
- Modify: `scripts/init_data.py` (`_collect_toss_trend_rows_for_ticker` 의 행 dict, `create_institutional_trend` 의 시작일 결정 뒤와 Skip 분기)
- Test: `tests/scripts/test_init_data_vcp_scheduler.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def test_create_institutional_trend_refetches_approx_and_partial_dates_in_window(monkeypatch, tmp_path):
    # 창 안의 Toss 근사 날짜와 종목이 모자란 날짜는 pykrx 로 다시 받고, 나머지는 Skip 한다([INFRA-094])
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"ticker": "000001"}]).to_csv(data_dir / "korean_stocks_list.csv", index=False)
    file_path = data_dir / "all_institutional_trend_data.csv"
    rows = [
        ("2026-09-14", "000001", 1, 1, None),  # 창 밖 부분 날짜
        ("2026-09-17", "000001", 3, 4, None),  # 창 안 부분 날짜
        ("2026-09-18", "000001", 1, 2, None),
        ("2026-09-18", "069500", 1, 2, None),
        ("2026-09-21", "000001", 7000, 9000, "toss"),
        ("2026-09-21", "069500", 7000, 9000, "toss"),
        ("2026-09-22", "000001", 5, 6, None),
        ("2026-09-22", "069500", 5, 6, None),
    ]
    pd.DataFrame(rows, columns=["date", "ticker", "foreign_buy", "inst_buy", "source"]).to_csv(
        file_path, index=False, encoding="utf-8-sig"
    )
    called = []

    class _Stock:
        @staticmethod
        def get_market_net_purchases_of_equities_by_ticker(start, _end, _market, investor):
            if investor == "외국인":
                called.append(start)
            value = 100 if investor == "외국인" else 200
            return pd.DataFrame({"순매수거래대금": [value, value]}, index=["000001", "069500"])

    fake_pykrx = types.ModuleType("pykrx")
    fake_pykrx.stock = _Stock
    monkeypatch.setitem(sys.modules, "pykrx", fake_pykrx)
    monkeypatch.setattr(init_data, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr(init_data, "shared_state", types.SimpleNamespace(STOP_REQUESTED=False))
    monkeypatch.setattr(init_data.time, "sleep", lambda _s: None)
    monkeypatch.setattr(
        init_data,
        "get_last_trading_date",
        lambda reference_date=None: ("20260922", datetime.datetime(2026, 9, 22)),
    )

    result = init_data.create_institutional_trend(target_date="2026-09-22")

    saved = pd.read_csv(file_path, dtype={"ticker": str, "date": str})
    values = {
        (d, t): (f, i, s)
        for d, t, f, i, s in zip(
            saved["date"], saved["ticker"], saved["foreign_buy"], saved["inst_buy"], saved["source"].fillna("")
        )
    }
    assert result is True
    assert called == ["20260917", "20260921"]
    assert values[("2026-09-14", "000001")] == (1, 1, "")
    assert values[("2026-09-17", "000001")] == (100, 200, "")
    assert values[("2026-09-17", "069500")] == (100, 200, "")
    assert values[("2026-09-18", "000001")] == (1, 2, "")
    assert values[("2026-09-21", "000001")] == (100, 200, "")
    assert values[("2026-09-22", "069500")] == (5, 6, "")
```

기존 `test_create_institutional_trend_uses_toss_backfill_when_pykrx_is_empty` 의 행 기대에 `"source": "toss"` 를 더한다(백필 행 표시가 설계 범위다).

- [ ] **Step 2: 실패 확인**

Run: `venv/bin/python -m pytest tests/scripts/test_init_data_vcp_scheduler.py -k "refetches_approx or uses_toss_backfill" -q`
Expected: 두 테스트 FAIL (`called == []`, `source` 키 없음)

- [ ] **Step 3: 최소 구현**

`_collect_toss_trend_rows_for_ticker` 의 행 dict 에 `"source": "toss",` 를 더한다.

`create_institutional_trend` 에서 `start_date = start_date_obj.strftime('%Y%m%d')` 바로 앞:

```python
        # [INFRA-094] 창 안의 Toss 근사 날짜와 종목이 모자란 날짜는 pykrx 로 다시 받는다
        # ponytail: lookback_days 창 밖의 근사·부분 날짜는 남는다. 먼 과거 복구가 필요하면 재수집 범위를 넓힌다
        refetch_dates = set()
        if not existing_df.empty and 'date' in existing_df.columns:
            window_start = (end_date_obj - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
            in_window = existing_df[existing_df['date'].between(window_start, end_date_obj.strftime('%Y-%m-%d'))]
            counts = in_window.groupby('date').size()
            refetch_dates = set(counts[counts < len(tickers_set) * 0.8].index)
            if 'source' in in_window.columns:
                refetch_dates |= set(in_window.loc[in_window['source'] == 'toss', 'date'])
        if refetch_dates:
            log(f"수급 데이터: 근사·부분 날짜 {len(refetch_dates)}개를 다시 수집합니다: {sorted(refetch_dates)}", "WARNING")
            start_date_obj = min(start_date_obj, datetime.strptime(min(refetch_dates), '%Y-%m-%d'))
```

Skip 분기 조건을 `if cur_date_fmt in existing_df['date'].values and cur_date_fmt not in refetch_dates:` 로 바꾼다.

- [ ] **Step 4: 통과 확인**

Run: `venv/bin/python -m pytest tests/scripts/test_init_data_vcp_scheduler.py -q`
Expected: 전부 PASS

- [ ] **Step 5: 전체 확인**

Run: `venv/bin/python -m pytest -q`
Expected: 실패 0
