# [FLOW-023] 수급 5일 합계를 읽는 쪽에서 결측을 0 으로 채우지 않는다 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 수급 5일 합계를 읽는 경로가 빈 칸·모자란 일수·낡은 자료를 실제 0 이나 5일치 값처럼 내보내지 않게 한다. 5일치가 온전하지 않은 값은 참조(pykrx·Toss)로 대체하거나 값 없음(None)으로 둔다.

**Architecture:** 5일 규칙은 통합 서비스 `services/investor_trend_5day_service.py` 한 곳에만 둔다. CSV 는 최근 5행이 모두 숫자일 때만 map 에 들어가고, pykrx 참조의 NaN 은 None 으로 남아 `[FLOW-022]` 의 거부 판정(`insufficient_days`)을 지난다. 참조를 모두 버렸는데 CSV 가 낡았거나(`stale_csv`) 상한을 넘으면(`extreme_abs_total`) verify=True 호출은 None 을 받는다. 상세 API 의 레거시 CSV 집계는 지워 같은 규칙의 사본이 없게 한다. 상세 API 가 값을 넣지 않으면 모달은 `[FE-048]` 의 Toss 합계 「(N일)」로 물러선다.

**Tech Stack:** Python 3.11, pandas, pytest

**Spec:** 대화 설계(2026-09-25, 확인 시각 19:49, 사용자 `/effort high` 후 「다음 진행해」로 권장안 승인), `docs/dev-cycle/TODO.md` `[FLOW-023]`

## Global Constraints

- 티어 T3: `services/investor_trend_5day_service.py` 가 tier-rules §2 「수급 집계」에 있다.
- 실제 순매수 0 은 0 으로 남는다. 빈 칸·NaN·숫자 아님·무한대만 결측이다.
- `verify_with_references=False` 계약(플래그 붙은 CSV 를 돌려주고 참조를 조회하지 않음)은 바꾸지 않는다. 수집기 믹스인 두 곳이 기댄다.
- `single_day_spike` 만 붙은 CSV 는 참조를 모두 버려도 남는다(실제 대량 거래일 수 있다).
- SQLite 스냅숏 키 접미사(`::investor_trend_5day_unified`)는 올리지 않는다. 다음 CSV 갱신 때 파일 서명이 바뀌어 다시 만들어지고, 로컬 CSV 의 빈 칸은 0개다(설계 때 읽기 전용 집계).
- frontend 는 고치지 않는다.
- 원본 `data/`·`.env`·네트워크·LLM 에 닿지 않는다. pytest 는 `venv/bin/python -m pytest -q -p no:cacheprovider`.
- `docs/dev-cycle/evidence/*/fixture.py` 의 옛 시그니처 호출은 과거 증거라 고치지 않는다.

## 변경 목록

| 파일 | 변경 |
|---|---|
| `services/investor_trend_5day_service.py` | `_build_trend_map`: `fillna(0)` 두 줄 삭제, 반복문 except 에 `OverflowError` 추가. `_fetch_pykrx_reference_trend`: 하루 값 `optional_volume`, 합계는 값 있는 날만. `_resolve_best_payload`: 참조 없음 + verify=True + `stale_csv`/`extreme_abs_total` → None. `get_investor_trend_5day_for_ticker` docstring 정정 |
| `services/kr_market_stock_detail_service.py` | 레거시 전역 `_INVESTOR_TREND_5DAY_*`, 함수 `_get_or_build_investor_trend_5day_map`·`_build_investor_trend_5day_cache_key`·`_investor_trend_5day_sqlite_cache_key`·`_resolve_investor_trend_5day_sqlite_cache_context`·`_serialize_investor_trend_5day_map`·`_deserialize_investor_trend_5day_map`·`_build_investor_trend_5day_map` 삭제. `append_investor_trend_5day(payload, ticker_padded, logger, data_dir=None)`, `fetch_stock_detail_payload(ticker, logger, data_dir=None)`. 쓰지 않게 된 import 정리 |
| `services/kr_market_realtime_service.py` | 래퍼 `fetch_stock_detail_payload` 에서 `load_csv_file` 인자 삭제. 호출자가 없는 래퍼 `_append_investor_trend_5day` 와 그 import 는 삭제(critic 6) |
| `app/routes/kr_market_data_backtest_stock_routes.py` | `/stock-detail/<ticker>` 호출에서 `load_csv_file=` 삭제(백테스트 라우트의 `load_csv_file` 은 그대로) |
| `tests/services/test_investor_trend_5day_service.py` | 새 검사 3건, 기대값 변경 2건 |
| `tests/services/test_kr_market_stock_detail_service_refactor.py` | 레거시 검사 5건 삭제, 호출 시그니처 갱신, 새 검사 1건(3케이스) |

## Review Focus

- 빈 칸이 6번째 이전 행에만 있는 종목: 최근 5행은 온전하므로 map 에 남고 합계가 그대로여야 한다(`dropna` 로 행을 지우면 창이 과거로 밀리는 회귀가 생긴다).
- `extreme_abs_total` 은 과거 기준일(target_datetime)에서도 붙는다. 그 경우 pykrx 를 버리면 None 이다. 백테스트 소비처(`engine/screener.py:256`)는 None 을 MISSING_SUPPLY 로 읽는다. 20조 상한이라 실제 발생은 손상 자료뿐이다.
- 과거 기준일 + `single_day_spike` 만 붙은 CSV 는 기존 `test_historical_target_keeps_the_csv_when_the_pykrx_reference_is_discarded` 대로 CSV 가 남아야 한다.
- 상세 API 의 SQLite 상세 캐시(15분 슬롯)에는 수정 전 레거시 값이 든 페이로드가 남을 수 있다. 다음 슬롯에서 사라진다(기록만).
- 최신 창 스크리너의 Toss 실패 대체 경로(`engine/screener.py:367-374` → `_calculate_supply_score_csv`, verify=True)도 (3) 을 지난다. `stale_csv` CSV 에 참조까지 모두 실패하면 종전의 낡은 CSV 점수 대신 MISSING_SUPPLY 가 된다. 설계가 의도한 동작이며 코드는 고치지 않는다(closing-bet-reviewer F2).
- 참조 조회가 잠시 실패하면(실패 TTL 60초) `investorTrend5Day` 없는 상세 페이로드가 15분 슬롯 동안 캐시되어, 참조가 회복돼도 그동안 모달은 Toss 대체값을 그린다. 종전에는 레거시 CSV 가 그 자리를 채웠다(기록만, closing-bet-reviewer F9).
- 이미 저장된 pykrx 참조 캐시에 NaN→0 으로 읽힌 값이 남을 수 있다. 최신 창은 토큰(최신 거래일)이 바뀌면 사라지지만, 과거 기준일의 토큰은 그 날짜 자체라 만료되지 않고 `_REFERENCE_SQLITE_MAX_ROWS` 축출로만 사라진다(`:160-161`, `:203-205`). 그 저장분은 `from_cache=True` 정규화에서 0 으로 남아 채택된다. 빈도를 확인하지 않았으므로 코드는 고치지 않고 기록한다(critic 1).

---

### Task 1: 통합 서비스 (1)(3)(4)

**Files:**
- Modify: `services/investor_trend_5day_service.py:378-379, :408-414, :699-719, :948-955, :1071-1075`
- Test: `tests/services/test_investor_trend_5day_service.py`

**Interfaces:** 공개 함수 시그니처는 그대로다. `get_investor_trend_5day_for_ticker` 가 None 을 돌려주는 경우만 늘어난다.

- [ ] **Step 1: 실패 테스트 작성** — `_write_five_day_csv` 아래에 추가한다.

```python
def test_trend_map_drops_a_ticker_with_a_blank_in_the_last_five_rows(tmp_path):
    """[FLOW-023] 최근 5행의 빈 칸·무한대는 0 이 아니라 결측이다. 더 오래된 행으로 창을 채우지 않는다."""
    rows = []
    for ticker, blank_at in (("005930", None), ("000660", "2026-02-23"), ("035720", "2026-02-19")):
        for day in ("2026-02-19", "2026-02-20", "2026-02-21", "2026-02-22", "2026-02-23", "2026-02-24"):
            rows.append({"ticker": ticker, "date": day,
                         "foreign_buy": "" if day == blank_at else 1, "inst_buy": 10})
    rows.append({"ticker": "051910", "date": "2026-02-20", "foreign_buy": 1, "inst_buy": 10})
    for day in ("2026-02-21", "2026-02-22", "2026-02-23", "2026-02-24"):
        rows.append({"ticker": "051910", "date": day, "foreign_buy": 1, "inst_buy": "inf" if day == "2026-02-24" else 10})
    pd.DataFrame(rows).to_csv(tmp_path / "all_institutional_trend_data.csv", index=False)

    trend_service.clear_investor_trend_5day_memory_cache()
    trend_map = trend_service._get_or_build_trend_map(
        data_dir=trend_service._normalize_data_dir(str(tmp_path)),
        filename=trend_service._TREND_FILENAME,
    )

    assert trend_map["005930"]["foreign"] == 5
    assert "000660" not in trend_map  # 최근 5행 안의 빈 칸
    assert trend_map["035720"]["foreign"] == 5  # 빈 칸이 6번째 이전 행에만 있다
    assert "051910" not in trend_map  # 무한대 한 칸이 map 전체를 깨뜨리지 않는다
```

```python
def test_pykrx_reference_with_a_nan_day_is_rejected_as_insufficient_days(monkeypatch):
    """[FLOW-023] pykrx 가 하루 값을 NaN 으로 주면 0 이 아니라 결측이므로 참조를 버린다."""
    days = pd.to_datetime(["2026-02-18", "2026-02-19", "2026-02-20", "2026-02-23", "2026-02-24"])
    frame = pd.DataFrame(
        {"기관합계": [10.0, 10.0, 10.0, 10.0, 10.0], "외국인합계": [1.0, 2.0, float("nan"), 4.0, 5.0]},
        index=days,
    )
    monkeypatch.setattr(pykrx_stock, "get_market_trading_value_by_date", lambda *a, **k: frame)

    payload = trend_service._fetch_pykrx_reference_trend(ticker="005930", target_datetime="2026-02-24")

    assert payload["foreign"] == 12  # 값 있는 날만 더한다
    assert [d["netForeignerBuyVolume"] for d in payload["details"]] == [5, 4, None, 2, 1]
    normalized = trend_service._normalize_external_trend_payload(payload, source="pykrx")
    assert trend_service._reference_reject_reason(normalized) == "insufficient_days"
```

```python
def test_extreme_csv_with_no_usable_reference_returns_nothing(monkeypatch, tmp_path):
    """[FLOW-023] 20조 상한을 넘은 CSV 는 참조가 없으면 값으로 쓰지 않는다. 과거 기준일에서도 같다."""
    pd.DataFrame(
        [{"ticker": "005930", "date": f"2026-02-{day}", "foreign_buy": 5_000_000_000_000, "inst_buy": 0}
         for day in ("20", "21", "22", "23", "24")]
    ).to_csv(tmp_path / "all_institutional_trend_data.csv", index=False)

    trend_service.clear_investor_trend_5day_memory_cache()
    monkeypatch.setattr(trend_service, "_fetch_pykrx_reference_trend", lambda **_kwargs: None)
    monkeypatch.setattr(trend_service, "_fetch_toss_reference_trend", lambda **_kwargs: None)

    assert trend_service.get_investor_trend_5day_for_ticker(
        ticker="005930", data_dir=str(tmp_path), target_datetime="2026-02-24"
    ) is None
    # verify=False 는 플래그 붙은 CSV 를 그대로 돌려준다(호출자가 자기 폴백으로 빠진다)
    kept = trend_service.get_investor_trend_5day_for_ticker(
        ticker="005930", data_dir=str(tmp_path), target_datetime="2026-02-24", verify_with_references=False
    )
    assert "extreme_abs_total" in kept["quality"]["csv_anomaly_flags"]
```

  기존 `test_a_zero_reference_does_not_overwrite_a_stale_but_real_csv` 는 이름을 `test_a_zero_reference_does_not_overwrite_a_stale_csv_and_nothing_is_returned` 로 바꾸고, docstring 에 「[FLOW-023] 낡은 CSV 도 최근 5일 값처럼 내보내지 않는다」를 더한 뒤 단언을 다음으로 바꾼다. 0 참조가 채택됐다면 `source == "pykrx"` 인 0 값이 나오므로 None 이 「덮지 않았다」도 함께 증명한다.

```python
    assert result is None
```

  기존 `test_a_toss_reference_missing_one_day_does_not_replace_the_csv` 는 CSV 를 오늘 기준 최근 날짜(낡지 않음)와 하루 급등(`single_day_spike`)으로 바꿔 「CSV 가 남는다」를 계속 확인한다. `_write_five_day_csv(...)` 줄을 아래로 바꾸고 단언을 고친다.

```python
    today = datetime.now().date()
    recent = [(today - pd.Timedelta(days=offset)).strftime("%Y-%m-%d") for offset in (4, 3, 2, 1, 0)]
    pd.DataFrame(
        [{"ticker": "005930", "date": day, "foreign_buy": 50_000_000_000 if day == recent[-1] else 1_000, "inst_buy": 0}
         for day in recent]
    ).to_csv(tmp_path / "all_institutional_trend_data.csv", index=False)
    ...
    assert result["source"] == "csv"
    assert result["foreign"] == 50_000_004_000
    assert result["quality"]["csv_anomaly_flags"] == ["single_day_spike"]
    assert result["quality"]["discarded_references"] == ["toss:insufficient_days"]
```

- [ ] **Step 2: 실패 확인**

Run: `venv/bin/python -m pytest -q -p no:cacheprovider tests/services/test_investor_trend_5day_service.py`
Expected: 새 검사 3건과 이름 바꾼 0 참조 검사가 FAIL(빈 칸 종목이 map 에 있음, pykrx `details` 에 0, extreme CSV 가 반환됨, 낡은 CSV 가 반환됨). 급등으로 바꾼 Toss 검사는 수정 전에도 PASS 가 정상이다(급등 CSV 는 원래 남는다).

- [ ] **Step 3: 구현**

`_build_trend_map`:

```python
    # [FLOW-023] 빈 칸은 NaN 으로 남겨 아래 반복문이 그날을 건너뛰게 한다. 0 으로 채우면 순매수 0 으로 읽힌다
    working["foreign_buy"] = pd.to_numeric(working["foreign_buy"], errors="coerce")
    working["inst_buy"] = pd.to_numeric(working["inst_buy"], errors="coerce")
```

  반복문 except 를 `except (TypeError, ValueError, OverflowError):` 로 바꾼다(`int(float("nan"))` 은 ValueError, 무한대는 OverflowError).

`_fetch_pykrx_reference_trend` 의 반복문:

```python
    for day, (foreign_value, inst_value) in zip(ordered.index, ordered[[foreign_col, inst_col]].itertuples(index=False, name=None)):
        # [FLOW-023] NaN 은 0 이 아니라 결측이다. None 으로 남겨 _reference_reject_reason 이 버리게 한다
        foreign_int, inst_int = (None if v is None else int(v) for v in (optional_volume(foreign_value), optional_volume(inst_value)))
        foreign_sum += foreign_int or 0
        inst_sum += inst_int or 0
```

  `details: list[dict[str, int]]` 의 타입은 `list[dict[str, Any]]` 로 바꾼다.

`_resolve_best_payload` 의 `if not references:` 갈래:

```python
    if not references:
        # [FLOW-023] 낡았거나 상한을 넘은 CSV 는 참조로 확인하지 못하면 최근 5일 값으로 내보내지 않는다
        if verify_with_references and {"stale_csv", "extreme_abs_total"} & set(csv_flags):
            logger.debug("Dropped unverified CSV trend for %s: flags=%s discarded=%s", ticker, csv_flags, discarded_references)
            return None
        return _attach_selection_metadata(...)  # 기존 그대로
```

  docstring 의 「그 경우 플래그가 붙은 CSV 가 그대로 남는다. 플래그가 stale_csv 나 extreme_abs_total 이면 남는 CSV 도 정확하다고 볼 수 없다.」를 「그 경우 single_day_spike·insufficient_days 만 붙은 CSV 는 그대로 남고, stale_csv·extreme_abs_total 이 붙은 CSV 는 참조로 확인하지 못했으므로 None 을 돌려준다(verify_with_references=False 는 플래그 붙은 CSV 를 그대로 돌려준다).」로 바꾼다.

- [ ] **Step 4: 통과 확인**

Run: `venv/bin/python -m pytest -q -p no:cacheprovider tests/services/test_investor_trend_5day_service.py`
Expected: 전부 PASS. 다른 검사가 새로 깨지면(낡은 CSV 를 기대하는 검사) 의도한 변경인지 판정해 ledger 에 기록한다.

- [ ] **Step 5: 수급 소비처 회귀**

Run: `venv/bin/python -m pytest -q -p no:cacheprovider tests/engine tests/services -k "supply or trend or screener or collector"`
Expected: PASS.

### Task 2: 상세 API 레거시 CSV 경로 제거

**Files:**
- Modify: `services/kr_market_stock_detail_service.py:14-43, :223-472, :558-592`
- Modify: `services/kr_market_realtime_service.py:391-425`
- Modify: `app/routes/kr_market_data_backtest_stock_routes.py:59-64`
- Test: `tests/services/test_kr_market_stock_detail_service_refactor.py`

**Interfaces:**
- Produces: `append_investor_trend_5day(payload: dict, ticker_padded: str, logger: logging.Logger, data_dir: str | None = None) -> None`, `fetch_stock_detail_payload(ticker: str, logger: logging.Logger, data_dir: str | None = None) -> dict`. realtime 래퍼도 같은 모양. 라우트는 키워드 인자로 부른다.

- [ ] **Step 1: 실패 테스트 작성**

```python
@pytest.mark.parametrize(
    "service, data_dir",
    [
        (lambda **_k: None, "/tmp/unused"),  # 통합 서비스가 자료 없음
        (lambda **_k: (_ for _ in ()).throw(RuntimeError("boom")), "/tmp/unused"),  # 통합 서비스 예외
        (lambda **_k: (_ for _ in ()).throw(AssertionError("must not be called")), None),  # data_dir 없음
    ],
)
def test_append_investor_trend_5day_leaves_the_key_out_without_a_unified_value(monkeypatch, service, data_dir):
    """[FLOW-023] 통합 서비스가 값을 주지 않으면 키를 넣지 않는다. 모달은 Toss 합계 「(N일)」로 물러선다."""
    import services.kr_market_stock_detail_service as stock_detail_service

    monkeypatch.setattr(stock_detail_service, "get_investor_trend_5day_for_ticker", service)
    payload: dict[str, object] = {}

    append_investor_trend_5day(
        payload=payload,
        ticker_padded="005930",
        logger=type("L", (), {"warning": lambda *_a, **_k: None, "debug": lambda *_a, **_k: None})(),
        data_dir=data_dir,
    )

    assert "investorTrend5Day" not in payload
```

  세 번째 케이스는 `except Exception` 이 AssertionError 도 삼키므로, 실제 구현에서는 호출 기록 리스트를 두고 `calls == []` 로 「부르지 않았다」를 단언한다(critic 5). `import pytest` 를 추가한다.

- [ ] **Step 2: 실패 확인**

Run: `venv/bin/python -m pytest -q -p no:cacheprovider tests/services/test_kr_market_stock_detail_service_refactor.py -k leaves_the_key_out`
Expected: FAIL(`load_csv_file` 필수 인자 누락 TypeError).

- [ ] **Step 3: 구현과 테스트 정리**

  `append_investor_trend_5day` 본문은 통합 서비스 갈래만 남긴다.

```python
def append_investor_trend_5day(
    payload: dict[str, Any],
    ticker_padded: str,
    logger: logging.Logger,
    data_dir: str | None = None,
) -> None:
    """통합 서비스의 확정 5일 합계를 붙인다. 값이 없으면 키를 넣지 않는다([FLOW-023])."""
    normalized_ticker = str(ticker_padded).zfill(6)
    normalized_data_dir = (data_dir or "").strip()
    if not normalized_data_dir:
        return
    try:
        trend_data = get_investor_trend_5day_for_ticker(
            ticker=normalized_ticker,
            data_dir=normalized_data_dir,
            verify_with_references=True,
        )
    except Exception as error:
        logger.debug("Unified 5-day trend service failed (%s): %s", normalized_ticker, error)
        return
    if not isinstance(trend_data, dict):
        return
    ...  # 기존 quality 로그와 payload 설정 그대로
```

  레거시 전역·함수 7개를 지우고, 쓰지 않게 된 import(`Callable`, `pandas`, `is_datetime64_any_dtype`, `_get_padded_ticker_series`, `_load_csv_readonly`, 필요 없어진 것만)를 정리한다. `fetch_stock_detail_payload` 와 realtime 래퍼 두 개, 라우트 호출에서 `load_csv_file` 을 뺀다.

  테스트 파일: `test_append_investor_trend_5day_aggregates_recent_five_rows`, `test_append_investor_trend_5day_falls_back_to_csv_when_unified_service_has_no_data`, `test_append_investor_trend_5day_skips_when_required_columns_missing`, `test_investor_trend_5day_map_cache_reuses_sqlite_metadata_across_shallow_copies`, `test_investor_trend_5day_map_reuses_sqlite_snapshot_after_memory_clear` 를 지운다(대상 코드 삭제). 남는 검사의 `load_csv_file=` 인자를 지우고 `_should_not_read_csv` 보조 함수와 `calls["csv"]` 단언도 지운다. `_get_padded_ticker_series` 는 `services.kr_market_csv_utils.get_ticker_padded_series` 에서 가져오고, 파일 머리의 `_get_or_build_investor_trend_5day_map` import 도 지운다(남기면 수집 단계 ImportError, critic 7).

- [ ] **Step 4: 통과 확인**

Run: `venv/bin/python -m pytest -q -p no:cacheprovider tests/services/test_kr_market_stock_detail_service_refactor.py tests/app`
Expected: PASS. `git grep -n "load_csv_file" -- services/kr_market_stock_detail_service.py` 결과 0줄, `git grep -n "_build_investor_trend_5day_map\|_INVESTOR_TREND_5DAY" -- '*.py' ':!docs'` 결과 0줄.

## 검증과 QA

- 정적: `venv/bin/python -m pytest -q -p no:cacheprovider` 전체 통과와 `cd frontend && npm run test` 전체 통과(tier-rules T3 는 pytest·vitest 전체를 요구한다, critic 3). frontend 파일을 고치지 않으므로 tsc 는 돌리지 않는다.
- 리뷰: `/ponytail-review` → `closing-bet-reviewer` → `/review`(T3).
- QA(`/qa-only` → `/qa`): 격리 사본(`secrets/`·`data/`·`.env` 제거, 포트 3500·5501 이외)에서 실제 Flask 라우트와 Next 를 띄우고 Toss HTTP·pykrx 만 대역으로 바꾼다. 종가베팅 상세 모달을 브라우저로 열어 1~4행 종목, 낡은 CSV 종목, 빈 칸 종목, 정상 종목의 `investorTrend5Day` 유무와 모달 표시를 기록한다.
- 운영 반영: gunicorn 재기동이 필요하다. 장 중에는 재기동하지 않는다.

## 계획 검토 반영(critic ACCEPT-WITH-RESERVATIONS)

- (1) 중: 과거 기준일 pykrx 참조 캐시는 만료되지 않는다 → Review Focus 정정, 코드 불변, 아카이브에 기록
- (2) 중·범위 밖: `engine/signal_tracker_supply_helpers.py:51-58` 의 `tail(5)` + `sum` 이 NaN 을 건너뛰어 4일 합을 5일 값으로 점수화 → TODO 새 항목으로 등록, 이번 라운드에서 고치지 않음
- (3) 하: T3 는 vitest 전체도 요구 → 정적 검증에 추가
- (4) 하: 새 검사 건수 4→3 정정
- (5) 하: `data_dir` 없음 케이스는 호출 기록으로 단언
- (6) 하·ponytail: 호출자 없는 realtime 래퍼 `_append_investor_trend_5day` 삭제
- (7) 하: 테스트 파일의 레거시 import 삭제 명시
