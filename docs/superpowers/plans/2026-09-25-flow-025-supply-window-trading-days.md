# [FLOW-025] 수급 5일 창을 모든 종목에 같은 최근 5거래일로 맞추기 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 수급 CSV 의 「5일 합계」가 실제로 모든 종목에 공통인 최근 5거래일의 합이 되게 하고, 그 5일 중 하루라도 행이 없는 종목은 5일 값을 내지 않게 한다.

**Architecture:** `services/kr_market_csv_utils.py` 에 날짜 열에서 최근 5거래일을 고르는 함수 하나를 두고, 통합 수급 서비스(`_build_trend_map`)와 시그널 추적기(`build_supply_score_frame`)가 종목별 `tail(5)` 대신 그 5일의 행만 쓴다. 최신 날짜의 행 수가 바로 전 날짜의 80% 에 못 미치면 수집이 덜 끝난 날로 보고 창에서 뺀다. 기준일을 준 호출에도 `stale_csv` 를 기준일 기준으로 판정한다.

**Tech Stack:** Python 3.11, pandas, numpy, pytest

**Spec:** 대화 설계(bounded, spec 문서 없음). 승인 범위와 근거는 `docs/dev-cycle/TODO.md` 의 `[FLOW-025]` 「설계 승인」 줄(2026-09-25 21:54, 권장안 (A)~(D))이 정본이다.

## Global Constraints

- 위험 경로 `services/investor_trend_5day_service.py` 를 고치므로 T3 다. 리뷰 순서는 `/ponytail-review` → `closing-bet-reviewer` → `/review`.
- 테스트는 `tmp_path` 와 메모리 프레임만 쓴다. 원본 `data/`·`.env`·네트워크·LLM 에 닿지 않는다. 실행은 `KRX_ID= KRX_PW= venv/bin/python -m pytest -q -p no:cacheprovider`.
- 빠진 종목은 map 에서 뺀다(플래그를 새로 만들지 않는다, 설계 (A)). SQLite 스냅숏 형식은 바꾸지 않는다.
- 부분 날짜 비율 0.8 은 `engine/constants_market_scoring.py` 의 `SupplyThresholds` 에 이름을 붙여 둔다(`closing-bet-python` 의 상수 규칙). 창 길이는 기존 `SUPPLY.LOOKBACK_DAYS`(5)를 쓴다.
- SQLite 스냅숏 키: 서비스 `::investor_trend_5day_unified` → `::investor_trend_5day_unified_v2`, 시그널 추적기 `::signal_tracker_supply_score_frame_v2` → `_v3`.
- 코드 주석·로그는 저장소 관례(한국어, `[FLOW-025]` 태그)를 따른다.

## 설계 대비 판단(Ruling)

- Ruling: 부분 날짜 판정의 비교 대상을 승인안 (C) 「최근 10개 날짜 중 최대 행 수」에서 「바로 전 날짜의 행 수」로 바꾼다 — 계획 작성 중 확인했다. 최대값 기준은 종목 목록이 20% 넘게 늘어난 날 그 이전 날짜가 모두 문턱 아래로 떨어져 창이 비고(로컬 모의: 09-22 에 700종목 추가 → 남는 종목 0), 종목 1개와 2개가 섞인 기존 검사 고정 자료(`test_trend_map_aggregates_with_latest_first_details`)도 깨진다. 전 날짜 기준은 최신 날짜만 일부 들어온 경우(승인 설계의 목적)를 같게 막고(300종목 모의 → 창 불변, 1,897종목 유지) 목록 증가에도 창을 유지한다(1,895종목). 비율 80% 는 승인대로다.
- Ruling(계획 검토 M2): 판정 범위도 「최근 10개 날짜 각각」에서 「끝에서부터 이어진 모자란 날짜」로 좁힌다 — 창 중간의 부분 날짜(예: 행 수 2000, 500, 1900)를 거래일에서 빼면 그날 행이 있는 종목은 6거래일에 걸친 합을 내어 이 항목의 결함이 되살아난다. 중간 부분 날짜는 창에 남고 그날 행이 없는 종목이 map 에서 빠진다(틀린 값 대신 결측). 창 안의 부분 날짜는 `scripts/init_data.py:1228-1240` 이 다음 실행에서 다시 받는다. 같은 내용을 `ponytail:` 주석으로 남긴다 — 틀렸다면 루프를 전체 날짜 필터로 바꿔야 한다(한 줄 되돌림이 아니다). 두 판단 모두 승인된 파라미터를 바꾼 것이므로 다음 정지 지점에서 사용자에게 보고한다.
- Ruling(Nit): `recent_trading_dates` 의 `count` 인자는 부르는 곳이 없어 두지 않고 `SUPPLY.LOOKBACK_DAYS` 를 직접 쓴다. 시그널 추적기 헬퍼는 모듈 수준에서 import 한다.
- 범위 밖 영향(계획 검토 M3): map 에서 새로 빠지는 종목은 verify=False 믹스인 두 곳에서 자기 pykrx 경로로 가며, pykrx 가 빈 프레임을 주면 0·0 이 요약 캐시에 저장되어 종가베팅 점수에 들어갈 수 있다. 결함 자체는 `[FLOW-026]` 범위이므로 고치지 않고 그 항목 「내용」에 한 줄 더한다.

## Review Focus

1. 최신 날짜가 일부 종목에만 들어온 CSV: 그 날짜를 창에서 빼고 모든 종목이 직전 5거래일을 쓴다. 그 날짜 행이 있는 종목의 합에도 그 날이 들어가지 않는다 (Task 1 Step 1 `..._ignores_a_latest_date_that_only_some_tickers_have`, 함수 검사 `..._drops_partial_latest_dates`).
2. 최신 날짜의 행이 전날보다 많은 경우(신규 상장·목록 증가): 이전 날짜를 버리지 않는다 (함수 검사 `..._keeps_a_latest_date_with_more_rows`, 기존 `test_trend_map_aggregates_with_latest_first_details`).
3. 기준일을 준 조회: 창은 기준일 이하의 행으로만 고르고, CSV 전체가 기준일보다 영업일 4일 넘게 낡으면 `stale_csv` 가 붙는다. 기준일이 CSV 범위 안이면 붙지 않는다 (Task 1 Step 1 `test_stale_flag_uses_the_target_date_when_given`, 기존 `test_trend_map_applies_target_date_filter`).
4. 창 안의 날짜 순서: 서비스의 `details[0]` 은 창의 마지막 날, 시그널 추적기의 외국인 연속 순매수일은 창 안의 날짜 순으로 센다 (Task 1 Step 1 `details[0]` 단언, Task 2 Step 1 점수 단언).
5. 창 밖의 오래된 행만 빠진 종목은 빼지 않는다 (Task 1 의 `000040`, Task 2 의 종목 `4`, 기존 `[FLOW-024]` 창 밖 빈 칸 검사).

---

### Task 1: 공통 함수와 통합 수급 서비스

**Files:**
- Modify: `engine/constants_market_scoring.py` (`SupplyThresholds`)
- Modify: `services/kr_market_csv_utils.py` (함수 추가)
- Modify: `services/investor_trend_5day_service.py` (`_SQLITE_KEY_SUFFIX`, `_build_trend_map`, `_detect_csv_anomaly_flags`)
- Test: `tests/services/test_kr_market_csv_utils.py`, `tests/services/test_investor_trend_5day_service.py`

**Interfaces:**
- Produces: `services.kr_market_csv_utils.recent_trading_dates(dates: pd.Series) -> list[pd.Timestamp]` — 오래된 순, 최대 5개. `dates` 는 datetime 시리즈(행마다 한 값).
- Produces: `SUPPLY.PARTIAL_DATE_RATIO: float = 0.8`

- [ ] **Step 1: 실패하는 검사를 쓴다**

`tests/services/test_kr_market_csv_utils.py` 끝에 추가(import 에 `recent_trading_dates` 추가):

```python
def _dates(counts: dict[str, int]) -> pd.Series:
    return pd.to_datetime(pd.Series([day for day, n in counts.items() for _ in range(n)]))


def test_recent_trading_dates_drops_partial_latest_dates():
    """[FLOW-025] 최신 날짜가 전날 행 수의 80% 에 못 미치면 수집이 덜 끝난 날이다. 둘이 연달아 모자라도 뺀다."""
    dates = _dates({"2026-09-15": 10, "2026-09-16": 10, "2026-09-17": 10, "2026-09-18": 10,
                    "2026-09-21": 10, "2026-09-22": 7, "2026-09-23": 2})
    assert [d.strftime("%Y-%m-%d") for d in recent_trading_dates(dates)] == [
        "2026-09-15", "2026-09-16", "2026-09-17", "2026-09-18", "2026-09-21"]


def test_recent_trading_dates_keeps_a_latest_date_with_more_rows():
    """[FLOW-025] 신규 상장으로 행이 늘어난 날은 부분 날짜가 아니다. 이전 날짜도 버리지 않는다."""
    dates = _dates({"2026-09-16": 1, "2026-09-17": 1, "2026-09-18": 1, "2026-09-21": 1, "2026-09-22": 3})
    assert len(recent_trading_dates(dates)) == 5
```

`tests/services/test_investor_trend_5day_service.py` 의 `[FLOW-023]` 빈 칸 검사 뒤에 추가:

```python
def test_trend_map_drops_a_ticker_missing_a_day_inside_the_window(tmp_path):
    """[FLOW-025] 마지막 5행이 아니라 모든 종목에 공통인 최근 5거래일로 잰다.

    000020 은 02-20 행이 없어 마지막 5행이 02-17~02-24 의 6거래일에 걸치고, 000030 은 02-24 행이 없어 창이 하루 앞에서
    끝난다. 정상 종목을 여럿 두는 이유는 한 종목의 02-24 누락이 그날을 부분 날짜(전날의 80% 미만)로 만들지 않게 하려는 것이다.
    """
    days = ["2026-02-17", "2026-02-18", "2026-02-19", "2026-02-20", "2026-02-23", "2026-02-24"]
    rows = []
    normal = [(f"00001{n}", None) for n in range(5)]
    # 000040 은 창 밖(02-17) 행만 없으므로 남는다
    normal.append(("000040", "2026-02-17"))
    for ticker, missing in normal + [("000020", "2026-02-20"), ("000030", "2026-02-24")]:
        for index, day in enumerate(days, start=1):
            if day != missing:
                rows.append({"ticker": ticker, "date": day, "foreign_buy": index, "inst_buy": 10 * index})
    pd.DataFrame(rows).to_csv(tmp_path / "all_institutional_trend_data.csv", index=False)

    trend_service.clear_investor_trend_5day_memory_cache()
    trend_map = trend_service._get_or_build_trend_map(
        data_dir=trend_service._normalize_data_dir(str(tmp_path)),
        filename=trend_service._TREND_FILENAME,
    )

    assert sorted(trend_map) == [ticker for ticker, _ in normal]
    assert trend_map["000010"]["foreign"] == 2 + 3 + 4 + 5 + 6
    assert trend_map["000010"]["latest_date"] == "2026-02-24"
    assert trend_map["000010"]["details"][0] == {"netForeignerBuyVolume": 6, "netInstitutionBuyVolume": 60}


def test_trend_map_ignores_a_latest_date_that_only_some_tickers_have(tmp_path):
    """[FLOW-025] 최신 날짜가 일부 종목에만 들어왔으면 그날을 창에서 빼고 모두 직전 5거래일을 쓴다."""
    days = ["2026-02-17", "2026-02-18", "2026-02-19", "2026-02-20", "2026-02-23"]
    rows = [
        {"ticker": f"00001{n}", "date": day, "foreign_buy": 1, "inst_buy": 10}
        for n in range(5) for day in days
    ]
    rows.append({"ticker": "000010", "date": "2026-02-24", "foreign_buy": 1_000, "inst_buy": 1_000})
    pd.DataFrame(rows).to_csv(tmp_path / "all_institutional_trend_data.csv", index=False)

    trend_service.clear_investor_trend_5day_memory_cache()
    trend_map = trend_service._get_or_build_trend_map(
        data_dir=trend_service._normalize_data_dir(str(tmp_path)),
        filename=trend_service._TREND_FILENAME,
    )

    assert len(trend_map) == 5
    assert {payload["latest_date"] for payload in trend_map.values()} == {"2026-02-23"}
    assert trend_map["000010"]["foreign"] == 5


def test_stale_flag_uses_the_target_date_when_given():
    """[FLOW-025] 기준일을 준 호출도 CSV 의 마지막 날이 기준일보다 영업일 4일 넘게 앞서면 낡은 자료다."""
    payload = {
        "foreign": 5, "institution": 50, "latest_date": "2026-02-24",
        "details": [{"netForeignerBuyVolume": 1, "netInstitutionBuyVolume": 10}] * 5,
    }

    assert "stale_csv" in trend_service._detect_csv_anomaly_flags(payload, target_datetime="2026-03-10")
    assert "stale_csv" not in trend_service._detect_csv_anomaly_flags(payload, target_datetime="2026-02-25")
```

- [ ] **Step 2: 실패를 확인한다**

Run(파일마다 따로): `KRX_ID= KRX_PW= venv/bin/python -m pytest -q -p no:cacheprovider tests/services/test_kr_market_csv_utils.py -k recent_trading_dates` 와 `... tests/services/test_investor_trend_5day_service.py -k "missing_a_day_inside or only_some_tickers or uses_the_target_date"`
Expected: 앞 명령은 수집 오류 `ImportError: cannot import name 'recent_trading_dates'`, 뒤 명령은 FAIL 3건 — `missing_a_day_inside` 는 map 에 `000020`·`000030` 이 남아서, `only_some_tickers` 는 `000010` 의 `latest_date` 가 02-24, `uses_the_target_date` 는 첫 단언에서 `stale_csv` 없음.

- [ ] **Step 3: 구현한다**

`engine/constants_market_scoring.py` 의 `SupplyThresholds` 에 추가:

```python
    LOOKBACK_DAYS: int = 5
    # [FLOW-025] 최신 날짜 행 수가 전날의 이 비율에 못 미치면 수집이 덜 끝난 날로 본다. scripts/init_data.py 의 부분 날짜 재수집 기준(0.8)과 같다
    PARTIAL_DATE_RATIO: float = 0.8
```

`services/kr_market_csv_utils.py`: import 에 `from engine.constants import SUPPLY` 를 `engine.ticker_utils` 옆에 두고 `get_ticker_padded_series` 뒤에 추가:

```python
def recent_trading_dates(dates: pd.Series) -> list[pd.Timestamp]:
    """행이 있는 날짜 가운데 최근 거래일 SUPPLY.LOOKBACK_DAYS 개를 오래된 순으로 돌려준다.

    최신 날짜의 행 수가 바로 전 날짜의 PARTIAL_DATE_RATIO 에 못 미치면 수집이 덜 끝난 날로 보고 뺀다([FLOW-025]).
    그 날을 창에 넣으면 그날 행이 없는 대다수 종목이 한꺼번에 5일 값을 잃는다.
    """
    per_date = dates.value_counts().sort_index()
    while len(per_date) > 1 and per_date.iloc[-1] < per_date.iloc[-2] * SUPPLY.PARTIAL_DATE_RATIO:
        per_date = per_date.iloc[:-1]
    # ponytail: 끝쪽의 모자란 날만 뺀다. 창 중간의 부분 날짜는 남겨 그날 행이 없는 종목이 빠진다(빼면 그날 행이 있는 종목이 6거래일 합을 낸다).
    # 중간 부분 날짜는 init_data 가 다음 실행에서 다시 받는다. CSV 전체에서 빠진 날은 알 수 없다(거래일 달력은 휴장일 목록을 손으로 채워야 해서 쓰지 않는다)
    return list(per_date.index[-SUPPLY.LOOKBACK_DAYS:])
```

`services/investor_trend_5day_service.py`:

1. import 줄을 `from services.kr_market_csv_utils import get_ticker_padded_series, recent_trading_dates` 로 바꾼다.
2. `_SQLITE_KEY_SUFFIX` 를 바꾼다:

```python
# [FLOW-025] 종목별 마지막 5행으로 만든 스냅숏을 다시 쓰지 않도록 v2 로 바꿨다
_SQLITE_KEY_SUFFIX = "::investor_trend_5day_unified_v2"
```

3. `_build_trend_map` 의 날짜 갈래에서 `working = working.sort_values(["ticker", "date"])` 앞에 창 필터를 넣는다:

```python
        if working.empty:
            return {}
        # [FLOW-025] 종목마다 마지막 5행을 쓰면 행이 빠진 종목은 6거래일 이상의 합이 5일 값이 된다. 모든 종목을 같은 최근 5거래일로 잰다
        window_dates = recent_trading_dates(working["date"])
        ticker_count = working["ticker"].nunique()
        working = working[working["date"].isin(window_dates)]
        working = working.sort_values(["ticker", "date"])
```

   반복문 뒤 `return trend_map` 앞에 로그 한 줄:

```python
    if has_date:
        logger.info(
            "수급 CSV 최근 5거래일 %s~%s: 5일 값 %d종목, 빠진 날·빈 칸으로 제외 %d종목",
            window_dates[0].strftime("%Y-%m-%d"), window_dates[-1].strftime("%Y-%m-%d"),
            len(trend_map), ticker_count - len(trend_map),
        )
```

4. `_detect_csv_anomaly_flags` 의 `if target_datetime is None:` 블록을 기준 시각으로 바꾼다(들여쓰기 한 단계 줄임, 주석은 유지):

```python
    latest_date = _parse_date_string(csv_payload.get("latest_date"))
    if latest_date is not None:
        # [FLOW-025] 기준일이 있으면 그날을 기준으로 잰다. 예전에는 기준일을 준 호출이 CSV 전체가 낡아도 플래그 없이 채택했다
        reference_day = _normalize_target_datetime(target_datetime) or datetime.now()
        # (기존 주석 유지) ...
        from engine.market_schedule import MarketSchedule

        business_gap = int(
            np.busday_count(
                latest_date.date(),
                reference_day.date(),
                holidays=MarketSchedule.known_holidays(),
            )
        )
        if business_gap > _CSV_STALE_BUSINESS_DAYS:
            flags.append("stale_csv")
```

- [ ] **Step 4: 통과와 인접 검사를 확인한다**

Run: 위 Step 2 두 명령
Expected: 2 passed, 3 passed

Run: `KRX_ID= KRX_PW= venv/bin/python -m pytest -q -p no:cacheprovider tests/services/test_investor_trend_5day_service.py tests/services/test_kr_market_csv_utils.py tests/services/test_kr_market_stock_detail_service_refactor.py tests/services/test_common_update_pipeline_steps_refactor.py tests/engine/test_collectors_refactor.py tests/engine/test_collectors_unified_supply_service_refactor.py tests/engine/test_naver_collector_refactor.py tests/engine/test_screener_data_cache_refactor.py tests/engine/test_screener_supply_batch.py tests/engine/test_screener_supply_unified_service_refactor.py tests/chatbot/test_stock_context.py tests/scripts/test_init_data_vcp_scheduler.py tests/engine/test_collectors_package_contract.py tests/services/test_investor_personal_flow.py tests/services/test_investor_trend_reference_concurrency.py` (`test_collectors_package_contract` 가 순환 import 회귀를 subprocess 로 확인한다)
Expected: 전부 통과. 종목마다 날짜가 다른 고정 자료나 기준일보다 오래된 CSV 를 쓰는 기존 검사가 실패하면, 그 검사가 무엇을 지키는지 읽고 (a) 고정 자료가 우연히 창 조건을 어긴 것이면 고정 자료를 고치고 (b) 옛 동작(마지막 5행·기준일 무시)을 고정한 것이면 기대값을 새 동작으로 바꾸며, 어느 쪽인지 TODO 체크에 적는다.

- [ ] **Step 5: 커밋하지 않는다** — T3 첫 커밋은 리뷰·정적 검증·QA 행렬 뒤에 한 번 만든다(dev-cycle [3] 5번).

### Task 2: 시그널 추적기와 스크리너 문서

**Files:**
- Modify: `engine/signal_tracker_supply_helpers.py` (`build_supply_score_frame`)
- Modify: `engine/signal_tracker_analysis_mixin.py:63-64` (키 접미사)
- Modify: `engine/screener.py` (`_calculate_supply_score_csv` docstring)
- Test: `tests/engine/test_signal_tracker_supply_helpers_refactor.py`

**Interfaces:**
- Consumes: `recent_trading_dates` (Task 1)

- [ ] **Step 1: 실패하는 검사를 쓴다**

`tests/engine/test_signal_tracker_supply_helpers_refactor.py` 끝에 추가:

```python
def test_build_supply_score_frame_drops_tickers_missing_a_day_in_the_window():
    """[FLOW-025] 마지막 5행 대신 모든 종목에 공통인 최근 5거래일을 쓴다. 하루라도 행이 없으면 점수에서 뺀다."""
    dates = ["2026-09-17", "2026-09-18", "2026-09-21", "2026-09-22", "2026-09-23", "2026-09-24"]

    def _rows(ticker, skip=None):
        return [
            {"ticker": ticker, "date": day, "foreign_buy": 600_000_000, "inst_buy": 300_000_000}
            for day in dates if day != skip
        ]

    raw_df = pd.DataFrame(
        _rows("1", skip="2026-09-22")  # 창 안의 하루가 빠져 마지막 5행이 6거래일에 걸친다
        + _rows("2", skip="2026-09-24")  # 최신 날짜가 빠져 창이 하루 앞에서 끝난다
        + _rows("3")
        + _rows("4", skip="2026-09-17")  # 창 밖 날짜만 빠졌다
        # 정상 종목을 더 둔다. 2 의 09-24 누락 하나가 그날을 부분 날짜(전날의 80% 미만)로 만들지 않게 한다
        + [row for n in range(5, 9) for row in _rows(str(n))]
    )

    result = build_supply_score_frame(
        raw_df,
        foreign_min=1,
        count_consecutive_positive=_count_consecutive_positive,
        logger=logging.getLogger(__name__),
    )

    assert sorted(result["ticker"]) == [f"00000{n}" for n in (3, 4, 5, 6, 7, 8)]
    assert set(result["foreign_net_buy_5d"]) == {3_000_000_000}
    assert set(result["supply_demand_index"]) == {100}
```

- [ ] **Step 2: 실패를 확인한다**

Run: `KRX_ID= KRX_PW= venv/bin/python -m pytest -q -p no:cacheprovider tests/engine/test_signal_tracker_supply_helpers_refactor.py -k missing_a_day`
Expected: FAIL — 결과 종목에 `000001`·`000002` 가 들어 있다.

- [ ] **Step 3: 구현한다**

`tests/engine/test_signal_tracker_supply_helpers_refactor.py:27-58` `test_build_supply_score_frame_filters_by_score_and_foreign_min` 의 고정 자료를 고친다(계획 검토 M1). 종목 3 이 02-05 행만 없어 날짜별 행 수가 3,3,3,3,2 가 되고, 새 규칙이 02-05 를 부분 날짜로 빼 모든 종목이 사라진다. 종목 3 의 빠진 날을 가장 오래된 날로 옮겨 02-02~02-05 를 두면(행 수 2,3,3,3,3) 창 5일이 유지되고 종목 3 은 여전히 4행이라 빠진다. 단언은 바꾸지 않는다.

`engine/signal_tracker_supply_helpers.py`: 모듈 머리 import 에 `from services.kr_market_csv_utils import recent_trading_dates` 를 추가하고 창 줄을 바꾼다:

```python
    working = working.sort_values(["ticker", "date"])
    # [FLOW-025] 종목마다 마지막 5행을 쓰면 행이 빠진 종목은 6거래일 이상의 합이 된다. 모든 종목에 같은 최근 5거래일을 쓴다
    recent = working[working["date"].isin(recent_trading_dates(working["date"]))]
    scored = recent.groupby("ticker", sort=False).agg(
```

   `scored = scored.reset_index()` 뒤, `[FLOW-024]` 주석 앞에 로그를 넣는다:

```python
    missing = working["ticker"].nunique() - int((scored["window_count"] >= 5).sum())
    if missing:
        logger.info(f"   최근 5거래일에 빠진 날이 있어 점수에서 제외: {missing}개 종목")
```

`engine/signal_tracker_analysis_mixin.py`:

```python
# [FLOW-024] 빈 칸 제외, [FLOW-025] 최근 5거래일 창 이전에 계산한 프레임을 다시 쓰지 않도록 올린다
_SUPPLY_SCORE_FRAME_SQLITE_CACHE_KEY_SUFFIX = "::signal_tracker_supply_score_frame_v3"
```

`engine/screener.py` `_calculate_supply_score_csv` docstring 의 둘째 문단 끝에 한 문장을 잇는다:

```
        [FLOW-025] 부터는 최근 5거래일 중 하루라도 행이 없는 종목도 CSV 에서 빠지므로 정상 자료에서도
        비용이 0 이 아니다(2026-09-21 로컬 파일 기준 2,002종목 중 약 100개).
```

- [ ] **Step 4: 통과와 인접 검사를 확인한다**

Run: `KRX_ID= KRX_PW= venv/bin/python -m pytest -q -p no:cacheprovider tests/engine/test_signal_tracker_supply_helpers_refactor.py tests/engine/test_signal_tracker_refactor.py`
Expected: 전부 통과(새 검사와 고정 자료를 고친 `filters_by_score_and_foreign_min` 포함).

Run: `KRX_ID= KRX_PW= venv/bin/python -m pytest -q -p no:cacheprovider` (백그라운드, 출력은 scratchpad `flow025/pytest-full.txt`)
Expected: 0 failed, 「KRX 로그인」 출력 0회.

- [ ] **Step 5: 커밋하지 않는다** — 리뷰(`/ponytail-review` → effort 조정 정지 → `closing-bet-reviewer` → `/review`) 뒤 정적 검증·QA 행렬과 함께 첫 커밋.

---

## 묶음 추가: [FLOW-026]·[FLOW-027]·[FLOW-028] (2026-09-25 22:26 승인)

**Spec:** 대화 설계(bounded·T3 공유 검토). 승인 범위는 `docs/dev-cycle/TODO.md` 의 각 항목 「설계 승인」 줄이 정본이다. Task 1~2 는 끝났고(구현·`/ponytail-review`·pytest 전체 2859 passed) 그 뒤에 태스크 셋을 잇는다. 리뷰(`closing-bet-reviewer` → `/review`)는 네 항목을 함께 한 번 받는다.

### 묶음 Global Constraints

- 위 Global Constraints 를 그대로 따른다. 새 위험 경로는 `engine/grade_decider.py`(신호와 등급 결정)다.
- 테스트의 가짜 pykrx 는 `monkeypatch.setitem(sys.modules, "pykrx", fake)` 로 넣는다. 서비스 전역 참조 캐시를 쓰는 검사는 앞뒤로 `clear_investor_trend_5day_memory_cache()` 를 부른다.
- 운영 SQLite 의 옛 `pykrx_supply_5d` 파일은 지우지 않는다. 읽는 코드만 없앤다.
- 테스트 삭제는 대상 코드가 없어진 경우만이며, 지운 검사가 무엇을 지켰는지 아카이브에 적는다.

### 묶음 Review Focus

1. 기준일을 준 `get_supply_data`(정규 종가베팅)에서 pykrx 프레임이 4행·NaN 인 날·빈 프레임이면 CSV(검증 규칙 통과분)로 넘어가고, CSV 도 없으면 None 이다. 0·0 이나 부분합이 나오지 않는다 (Task 5 Step 1).
2. pykrx 가 정상 5행이면 CSV 값이 있어도 pykrx 를 쓴다(기존 우선순위 유지, 기존 `test_get_supply_data_prefers_pykrx_for_explicit_historical_target`).
3. 수급 None 인 종목이 등급 판정에서 예외 없이 등급 없음이 된다 (Task 5 `_has_dual_buy` 검사).
4. `00680K` 와 `000680` 이 다른 키가 되고, 숫자 여섯 자리·접두 `A`·접미 `.KS`·날짜·8자리 숫자의 기존 정규화 결과는 그대로다 (Task 3, 기존 파라미터 검사).
5. 기준일 없이 부르는 Naver 투자자 동향은 값이 없으면 기본값을 건드리지 않고 pykrx 를 직접 부르지 않는다 (Task 5 Step 1).

### Task 3: [FLOW-028] 영문자로 끝나는 종목코드 보존

**Files:**
- Modify: `engine/ticker_utils.py:15`
- Test: `tests/engine/test_ticker_utils.py`

- [ ] **Step 1: 실패하는 검사를 쓴다** — 파라미터 목록의 `("0007c0", "0007C0"),` 다음 줄에 추가:

```python
        # [FLOW-028] 마지막 자리가 영문자인 코드. 예전에는 숫자만 남겨 000088·000220 이 되어 다른 종목과 섞였다
        ("00088K", "00088K"),
        ("0220wl", "0220WL"),
        ("00680K.KS", "00680K"),
```

- [ ] **Step 2: 실패를 확인한다**

Run: `KRX_ID= KRX_PW= venv/bin/python -m pytest -q -p no:cacheprovider tests/engine/test_ticker_utils.py`
Expected: 3 failed(`000088`·`000220`·`000680` 을 돌려줌).

- [ ] **Step 3: 구현한다**

```python
# [FLOW-028] 마지막 자리도 영문자를 받는다. 옛 우선주(00088K)와 새 형식(0220WL)을 숫자만 남겨 읽으면 다른 종목 키가 된다
_TICKER_PATTERN = re.compile(r"(?<![0-9])[0-9][0-9A-Z]{5}(?![0-9])")
```

- [ ] **Step 4: 통과와 인접 검사를 확인한다**

Run: `KRX_ID= KRX_PW= venv/bin/python -m pytest -q -p no:cacheprovider tests/engine/test_ticker_utils.py tests/services/test_kr_market_csv_utils.py tests/services/test_investor_trend_5day_service.py tests/app/test_kr_market_jongga_helpers_refactor.py`
Expected: 전부 통과.

### Task 4: [FLOW-027] 호출자 없는 CSV 수급 점수 경로 삭제

**Files:**
- Modify: `engine/screener_scoring_helpers.py` (`score_supply_from_csv`, `__all__` 항목, `from datetime import datetime`)
- Modify: `engine/screener_supply_helpers.py` (`calculate_supply_score_from_csv`, `__all__`)
- Modify: `engine/screener.py:96`·`:179` (`_inst_by_ticker`)
- Test: `tests/engine/test_screener_helpers_refactor.py`(2건과 import), `tests/engine/test_screener_supply_helpers_refactor.py`(2건과 import), `tests/engine/test_screener_data_cache_refactor.py:24`

- [ ] **Step 1: 삭제한다** — 함수 둘과 테스트 넷, 속성 초기화·대입 두 줄, 고정 자료의 `inst._inst_by_ticker = {}` 한 줄을 지운다. `__all__` 은 `["calculate_supply_score_with_toss"]` 와 `score_supply_from_csv` 를 뺀 목록이 된다. `datetime` 을 더 쓰지 않으면 import 도 지운다.
- [ ] **Step 2: 남은 참조가 없는지 확인한다**

Run: `grep -rn 'score_supply_from_csv\|calculate_supply_score_from_csv\|_inst_by_ticker' --include='*.py' engine services app tests scripts`
Expected: 출력 없음.

Run: `KRX_ID= KRX_PW= venv/bin/python -m pytest -q -p no:cacheprovider tests/engine/test_screener_helpers_refactor.py tests/engine/test_screener_supply_helpers_refactor.py tests/engine/test_screener_data_cache_refactor.py tests/engine/test_screener_vcp_gate_refactor.py tests/engine/test_screener_runtime_helpers_refactor.py tests/engine/test_screener_supply_unified_service_refactor.py`
Expected: 전부 통과.

### Task 5: [FLOW-026] 수집기의 pykrx 수급을 서비스 검증 경로로 교체

**Files:**
- Modify: `services/investor_trend_5day_service.py` (`get_pykrx_trend_5day` 추가, `has_csv_anomaly_flags` 삭제, `__all__`)
- Modify: `engine/collectors/krx_local_data_mixin.py` (`get_supply_data`, pykrx 요약 캐시 메서드 넷, import)
- Modify: `engine/collectors/krx.py` (`_pykrx_supply_*` 클래스 속성 넷)
- Modify: `engine/collectors/naver_pykrx_mixin.py` (`_get_investor_trend`, import)
- Modify: `engine/grade_decider.py:119-121` (`_has_dual_buy`)
- Test: `tests/services/test_investor_trend_5day_service.py`, `tests/engine/test_collectors_unified_supply_service_refactor.py`, `tests/engine/test_collectors_refactor.py`, `tests/engine/test_naver_collector_refactor.py`, `tests/engine/test_grade_classifier_refactor.py`, `tests/services/test_investor_personal_flow.py`, `tests/engine/test_krx_local_cache_helpers_refactor.py`

**Interfaces:**
- Produces: `services.investor_trend_5day_service.get_pykrx_trend_5day(*, ticker: str, data_dir: str, target_datetime=None) -> dict | None` — `_normalize_external_trend_payload` 형식(`foreign`·`institution`·`individual`·`details`…). 거부 사유가 있으면 None.

- [ ] **Step 1: 실패하는 검사를 쓴다**

서비스(`tests/services/test_investor_trend_5day_service.py` 끝):

```python
def _fake_pykrx_frame(foreign, inst):
    index = pd.bdate_range("2026-02-26", periods=len(foreign))
    return pd.DataFrame({"외국인합계": foreign, "기관합계": inst}, index=index)


@pytest.mark.parametrize(
    ("foreign", "inst", "expected"),
    [
        ([1, 2, 3, 4, 5], [10, 20, 30, 40, 50], (15, 150)),
        ([1, 2, 3, 4], [10, 20, 30, 40], None),  # 4행
        ([1, np.nan, 3, 4, 5], [10, 20, 30, 40, 50], None),  # NaN 인 날
        ([], [], None),
    ],
)
def test_get_pykrx_trend_5day_returns_only_complete_windows(monkeypatch, tmp_path, foreign, inst, expected):
    """[FLOW-026] 수집기가 쓰는 pykrx 5일 값은 참조와 같은 거부 판정을 거친다. 부분합이나 0 을 돌려주지 않는다."""
    trend_service.clear_investor_trend_5day_memory_cache()
    fake = types.ModuleType("pykrx")
    fake.stock = types.SimpleNamespace(get_market_trading_value_by_date=lambda *_a: _fake_pykrx_frame(foreign, inst))
    monkeypatch.setitem(sys.modules, "pykrx", fake)

    result = trend_service.get_pykrx_trend_5day(ticker="005930", data_dir=str(tmp_path), target_datetime="2026-03-04")

    trend_service.clear_investor_trend_5day_memory_cache()
    assert (None if result is None else (result["foreign"], result["institution"])) == expected
```

(파일 머리에 `import numpy as np` 를 더한다. `sys`·`types` 는 이미 있다.)

수집기(`tests/engine/test_collectors_unified_supply_service_refactor.py` 를 새 계약으로 다시 쓴다. 기존 두 검사는 `verify_with_references=False` 와 지워질 요약 캐시를 고정한 것이다):

```python
def _stub(monkeypatch, *, pykrx=None, unified=None):
    calls: dict[str, dict] = {}

    def _fake_pykrx(**kwargs):
        calls["pykrx"] = kwargs
        return pykrx

    def _fake_unified(**kwargs):
        calls["unified"] = kwargs
        return unified

    monkeypatch.setattr("engine.collectors.krx_local_data_mixin.get_pykrx_trend_5day", _fake_pykrx)
    monkeypatch.setattr("engine.collectors.krx_local_data_mixin.get_investor_trend_5day_for_ticker", _fake_unified)
    return calls


def test_get_supply_data_without_target_uses_the_verified_unified_service(monkeypatch, tmp_path):
    calls = _stub(monkeypatch, unified={"foreign": 123, "institution": 456})

    supply = asyncio.run(KRXCollector(_Config(str(tmp_path))).get_supply_data("5930"))

    assert (supply.foreign_buy_5d, supply.inst_buy_5d, supply.retail_buy_5d) == (123, 456, None)
    assert calls["unified"]["ticker"] == "005930"
    assert calls["unified"].get("verify_with_references", True) is True
    assert "pykrx" not in calls


def test_get_supply_data_with_target_prefers_complete_pykrx(monkeypatch, tmp_path):
    calls = _stub(monkeypatch, pykrx={"foreign": 7, "institution": 8, "individual": -15}, unified={"foreign": 1, "institution": 2})

    supply = asyncio.run(KRXCollector(_Config(str(tmp_path))).get_supply_data("005930", target_date="20260304"))

    assert (supply.foreign_buy_5d, supply.inst_buy_5d, supply.retail_buy_5d) == (7, 8, -15)
    assert calls["pykrx"]["target_datetime"] == "20260304"
    assert "unified" not in calls


def test_get_supply_data_with_target_falls_back_to_the_verified_service(monkeypatch, tmp_path):
    """[FLOW-026] pykrx 가 5일 값을 주지 못하면 검증 켠 서비스로 넘어간다. 그것도 없으면 0·0 대신 None."""
    calls = _stub(monkeypatch, pykrx=None, unified={"foreign": 1, "institution": 2})
    supply = asyncio.run(KRXCollector(_Config(str(tmp_path))).get_supply_data("005930", target_date="20260304"))
    assert (supply.foreign_buy_5d, supply.inst_buy_5d) == (1, 2)
    assert calls["unified"]["target_datetime"] == "20260304"
    assert calls["unified"].get("verify_with_references", True) is True

    _stub(monkeypatch, pykrx=None, unified=None)
    assert asyncio.run(KRXCollector(_Config(str(tmp_path))).get_supply_data("005930", target_date="20260304")) is None
```

Naver(`tests/engine/test_naver_collector_refactor.py`): `..._prefers_unified_service` 의 `assert captured["verify_with_references"] is False` 를 `assert captured.get("verify_with_references", True) is True` 로 바꾸고, `..._uses_sqlite_summary_cache` 를 아래로 바꾼다(지워질 요약 캐시를 고정한 검사):

```python
def test_naver_pykrx_investor_trend_keeps_defaults_when_unified_has_no_value(monkeypatch):
    """[FLOW-026] 통합 서비스가 값을 주지 못하면 기본값을 그대로 두고 pykrx 를 직접 부르지 않는다."""
    collector = NaverFinanceCollector(config=SimpleNamespace(DATA_DIR="data"))
    monkeypatch.setattr(pykrx_mixin_module, "get_investor_trend_5day_for_ticker", lambda **_kwargs: None)
    fake_pykrx = types.ModuleType("pykrx")
    fake_pykrx.stock = types.SimpleNamespace(
        get_market_trading_value_by_date=lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("pykrx 를 직접 부르면 안 된다"))
    )
    monkeypatch.setitem(sys.modules, "pykrx", fake_pykrx)

    result = collector._create_empty_result_dict("005930")
    asyncio.run(collector._get_investor_trend("5930", result))

    assert result["investorTrend"]["foreign"] == 0
    assert result["investorTrend"]["institution"] == 0
    assert result["investorTrend"]["individual"] is None
```

등급(`tests/engine/test_grade_classifier_refactor.py` 끝):

```python
def test_classify_none_without_supply():
    """[FLOW-026] 수급이 없으면 양매수를 확인할 수 없으므로 예외 없이 등급이 없다."""
    stock = _build_stock(change_pct=10.0, trading_value=1_200_000_000_000)
    grade = GradeClassifier().classify(stock=stock, score=ScoreDetail(total=10, news=1), score_details={}, supply=None)
    assert grade is None
```

- [ ] **Step 2: 실패를 확인한다**

Run: `KRX_ID= KRX_PW= venv/bin/python -m pytest -q -p no:cacheprovider tests/services/test_investor_trend_5day_service.py -k pykrx_trend_5day`
Expected: 수집 오류가 아닌 AttributeError(`get_pykrx_trend_5day` 없음) 4 failed.

Run: `KRX_ID= KRX_PW= venv/bin/python -m pytest -q -p no:cacheprovider tests/engine/test_collectors_unified_supply_service_refactor.py tests/engine/test_naver_collector_refactor.py tests/engine/test_grade_classifier_refactor.py`
Expected: 수집기 세 검사(모듈에 `get_pykrx_trend_5day` 없음), Naver 두 검사(False 전달·pykrx 직접 호출), 등급 한 검사(AttributeError) 실패.

- [ ] **Step 3: 구현한다**

서비스, `has_csv_anomaly_flags` 자리에(그 함수와 `__all__` 항목은 지운다. 호출자가 믹스인 둘뿐이다):

```python
def get_pykrx_trend_5day(
    *,
    ticker: str,
    data_dir: str,
    target_datetime: datetime | pd.Timestamp | str | None = None,
) -> dict[str, Any] | None:
    """pykrx 5거래일 합계를 참조와 같은 판정(_reference_reject_reason)을 거쳐 돌려준다.

    [FLOW-026] 수집기가 자기 pykrx 경로에서 5행 미만이나 NaN 인 날을 건너뛴 부분합, 빈 프레임의 0 을 5일 값으로
    썼다. 5일치가 모이지 않았거나 하루라도 수량이 비었거나 전부 0 이면 None 이다.
    """
    payload = _get_reference_trend_cached(
        data_dir=_normalize_data_dir(data_dir), source="pykrx", ticker=ticker, target_datetime=target_datetime,
    )
    return payload if _reference_reject_reason(payload) is None else None
```

`__all__` 에 `"get_pykrx_trend_5day"` 를 더한다.

`engine/collectors/krx_local_data_mixin.py` `get_supply_data` 본문(데이터 디렉터리 계산 뒤):

```python
            normalized_target_date = self._normalize_top_gainers_target_token(
                str(target_date) if target_date is not None else None
            )
            target_datetime = None if normalized_target_date == "latest" else normalized_target_date
            ticker = str(code).zfill(6)
            trend_data = None
            if target_datetime is not None:
                # 기준일을 준 실행(정규 종가베팅 포함)은 수급 CSV 수집이 실패해도 돌므로 pykrx 를 먼저 본다.
                # [FLOW-026] 예전 자체 경로는 부분합과 빈 프레임의 0 을 5일 값으로 써서 요약 캐시에 남겼다
                trend_data = get_pykrx_trend_5day(ticker=ticker, data_dir=data_dir, target_datetime=target_datetime)
            if trend_data is None:
                trend_data = get_investor_trend_5day_for_ticker(
                    ticker=ticker, data_dir=data_dir, target_datetime=target_datetime,
                )
            if not isinstance(trend_data, dict):
                return None
            return SupplyData(
                foreign_buy_5d=int(trend_data["foreign"]),
                inst_buy_5d=int(trend_data["institution"]),
                retail_buy_5d=trend_data.get("individual"),
            )
        except Exception as e:
            logger.error(f"수급 데이터 조회 실패 ({code}): {e}")
            return None
```

같은 파일에서 `_pykrx_supply_sqlite_context`·`_deserialize_pykrx_supply_payload`·`_load_cached_pykrx_supply_summary`·`_save_cached_pykrx_supply_summary` 를 지우고, import 를 `from services.investor_trend_5day_service import get_investor_trend_5day_for_ticker, get_pykrx_trend_5day` 로 바꾸며 쓰지 않게 된 `cached_personal_value`·`personal_flow_total` import 를 지운다. `engine/collectors/krx.py` 의 `_pykrx_supply_cache_lock`·`_pykrx_supply_cache`·`_pykrx_supply_memory_max_entries`·`_pykrx_supply_sqlite_max_rows` 를 지운다.

`engine/collectors/naver_pykrx_mixin.py` `_get_investor_trend`:

```python
    async def _get_investor_trend(self, code: str, result: Dict) -> None:
        """통합 5일 합산 서비스(검증 켬)로 채운다. 값이 없으면 기본값을 둔다([JONGGA-042])."""
        normalized_code = str(code).zfill(6)
        investor_trend = result.setdefault("investorTrend", {})
        investor_trend["individual"] = None
        investor_trend["individual_schema"] = 1

        try:
            # [FLOW-026] 예전에는 이상징후가 붙으면 자체 pykrx 경로로 빠져 부분합과 빈 프레임의 0 을 표시하고 저장했다
            trend_data = get_investor_trend_5day_for_ticker(
                ticker=normalized_code,
                data_dir=self._resolve_data_dir(getattr(self, "config", None)),
            )
        except Exception as error:
            logger.debug("투자자 동향 통합 서비스 조회 실패 (%s): %s", normalized_code, error)
            return
        if isinstance(trend_data, dict):
            investor_trend["foreign"] = int(trend_data["foreign"])
            investor_trend["institution"] = int(trend_data["institution"])
            investor_trend["individual"] = trend_data.get("individual")
```

import 에서 `has_csv_anomaly_flags`·`personal_flow_total` 을 뺀다(다른 곳에서 쓰지 않는지 grep).

`engine/grade_decider.py`:

```python
    @staticmethod
    def _has_dual_buy(supply: Optional[SupplyData]) -> bool:
        """외인+기관 동반 매수 여부. [FLOW-026] 수급이 없으면 확인할 수 없으므로 아니다"""
        return supply is not None and supply.foreign_buy_5d > 0 and supply.inst_buy_5d > 0
```

기존 검사 정리:
- `tests/engine/test_collectors_refactor.py`: `test_get_supply_data_reuses_pykrx_sqlite_snapshot_after_memory_clear` 삭제(요약 캐시가 없어짐, 참조 SQLite 재사용은 서비스의 `test_get_investor_trend_5day_for_ticker_reuses_reference_sqlite_after_memory_clear` 가 지킴). `..._uses_explicit_target_date_for_pykrx_window`·`..._prefers_pykrx_for_explicit_historical_target` 는 요약 캐시 monkeypatch 를 지우고 앞뒤로 서비스 메모리 캐시를 비우며, 가짜 프레임에 `index=pd.bdate_range("2026-02-26", periods=5)` 를 준다(단언 유지). `test_naver_finance_investor_trend_prefers_unified_service` 의 `is False` 단언은 `captured.get("verify_with_references", True) is True` 로 바꾼다.
- `tests/services/test_investor_personal_flow.py`: `test_collector_cache_bad_personal_value_keeps_foreign_and_institution` 삭제(대상 `_deserialize_pykrx_supply_payload` 가 없어짐).
- `tests/engine/test_krx_local_cache_helpers_refactor.py`: 공유 캐시 검사 대상을 `_pykrx_chart_cache` 로 바꾼다.
- `tests/services/test_investor_trend_5day_service.py`: `has_csv_anomaly_flags` 검사 둘을 지우고, verify=False 검사의 `has_csv_anomaly_flags(result) is True` 는 `result["quality"]["csv_anomaly_flags"]` 가 비어 있지 않다는 단언으로 바꾼다.

- [ ] **Step 4: 통과와 인접 검사를 확인한다**

Run: `grep -rn 'has_csv_anomaly_flags\|pykrx_supply_summary\|_pykrx_supply_\|_deserialize_pykrx_supply_payload' --include='*.py' engine services app tests scripts`
Expected: 출력 없음.

Run: `KRX_ID= KRX_PW= venv/bin/python -m pytest -q -p no:cacheprovider tests/services/test_investor_trend_5day_service.py tests/services/test_investor_personal_flow.py tests/engine/test_collectors_refactor.py tests/engine/test_collectors_unified_supply_service_refactor.py tests/engine/test_naver_collector_refactor.py tests/engine/test_krx_local_cache_helpers_refactor.py tests/engine/test_grade_classifier_refactor.py tests/engine/test_phases_analysis_refactor.py tests/services/test_kr_market_stock_detail_service_refactor.py`
Expected: 전부 통과(없는 파일은 목록에서 뺀다).

Run: `KRX_ID= KRX_PW= venv/bin/python -m pytest -q -p no:cacheprovider` (백그라운드, 출력 scratchpad `flow025/pytest-full-bundle.txt`)
Expected: 0 failed, 「KRX 로그인」 출력 0회.

- [ ] **Step 5: 커밋하지 않는다** — `/ponytail-review` → effort 정지 → 묶음 리뷰 → 정적 검증·QA 행렬 → 첫 커밋.

### 묶음 계획 검토 반영(critic REVISE, 2026-09-25)

위 태스크 본문보다 이 절이 우선한다.

- M1: `tests/engine/test_collectors_refactor.py` 의 `test_naver_finance_investor_trend_uses_pykrx_sqlite_summary_cache`(:1154)도 지울 요약 캐시를 monkeypatch 하므로 삭제한다. 대체 검사는 `test_naver_collector_refactor.py` 의 새 검사다.
- M2: 새 Naver 검사는 가짜 pykrx 가 던지는 대신 호출을 리스트에 기록하고 `assert calls == []` 로 확인한다. 옛 코드가 원본 `data/` 에 쓰지 않도록 `krx_module.KRXCollector._get_latest_market_date` 를 고정 날짜 람다로, `engine.collectors.krx_local_data_mixin.BASE_DIR` 를 `tmp_path` 로 돌린다. Step 2 기대값: Naver 는 `prefers_unified` 와 새 검사 둘 다 실패(새 검사는 옛 코드가 pykrx 를 부르므로).
- L1: `test_collectors_refactor.py` 에 실제 서비스를 쓰는 검사를 하나 둔다. `tmp_path` 에 그 종목이 없는 수급 CSV 를 두고, 가짜 pykrx 가 호출 수를 세며 4행·NaN 두 경우에 `supply is None` 과 호출 1회를 단언한다.
- L2: Task 3 Step 4 에 `tests/services/test_paper_trading_*`·`test_kr_market_realtime_price_*` 를 더한다. 보고·QA 에 「영문자로 끝나는 우선주 보유 종목의 평가 가격이 자기 코드로 조회됨」을 적는다.
- L3: 서비스 파라미터 검사에 `([0] * 5, [0] * 5, None)`(전부 0) 을 더한다.
- Nit: `"5930KS"` → `"5930KS"` 는 호출처 근거가 없어 고정하지 않는다. 낡은 docstring 둘(`test_investor_trend_5day_service.py:756-761`, `krx_local_data_mixin.py` `get_supply_data`)을 고친다. `:799` 의 `has_csv_anomaly_flags` 단언은 지운다(:800 이 `stale_csv` 를 단언). 쓰지 않게 된 import 를 지운다. pykrx 참조가 끝 날짜를 기준일과 대조하지 않는 것은 범위 밖으로 TODO 에 등록한다.
