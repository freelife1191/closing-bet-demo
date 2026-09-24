# [INFRA-095] 수급 수집의 결측을 0 으로 저장하지 않기 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `data/all_institutional_trend_data.csv` 에 결측이 0 으로 들어가지 않게 한다. 결측이 있는 (날짜, 종목) 행은 저장하지 않고, 실제 0 은 그대로 저장한다.

**Architecture:** 파일의 계약을 「모든 `foreign_buy`·`inst_buy` 는 실제 숫자」로 유지하므로 읽는 쪽(시그널 추적·스크리너·Market Gate·챗봇·종목 상세·5일 추이)은 바꾸지 않는다. pykrx 경로는 두 프레임에 모두 있고 값이 NaN 이 아닌 종목만 저장한다(`[INFRA-094]` 가 재수집 날짜에만 쓰던 교집합을 첫 수집에도 쓴다). Toss 경로는 종가·순매수 수량을 `or 0` 없이 읽어 빈 값이면 그 행을 버린다.

**Tech Stack:** Python 3.11, pandas, pytest

**Spec:** 대화 설계(2026-09-25 07:56 승인, `docs/dev-cycle/TODO.md` `[INFRA-095]` 설계 승인 줄)

## Global Constraints

- 위험 경로 `scripts/init_data.py` → T3. 리뷰는 과잉설계 → 코드(`closing-bet-reviewer`) → 심층(`/review`) 순서
- 읽는 쪽 코드는 바꾸지 않는다. 빈 칸(NaN) 저장안은 기각했다
- 이미 저장된 결측 0 은 고치지 않는다(파일만으로 실제 0 과 구분할 수 없음)
- 테스트·QA 는 `tmp_path`·격리 사본만 쓴다. 원본 `data/` 와 실제 pykrx·Toss 는 부르지 않는다
- pytest 는 `venv/bin/python -m pytest -q -p no:cacheprovider`

## Review Focus

1. 휴장일: 두 프레임이 모두 빈 `DataFrame`(열 없음)이면 교집합이 비어 `KeyError` 없이 종전처럼 「데이터 없음 (휴장일?)」 DEBUG 로그로 끝나야 한다. 한쪽만 빈 경우의 경고가 휴장일에 찍히면 안 된다 → `test_create_institutional_trend_holiday_does_not_warn_one_frame_empty`(리뷰 low 2)
2. 한쪽 프레임만 비었을 때(한쪽 조회 실패): 교집합이 비어 그 날짜는 저장되지 않고 WARNING 을 남긴다(critic 권장 3). 그 날짜가 최신이면 Toss 백필·stale 판정으로 넘어간다 → `test_create_institutional_trend_warns_when_one_frame_is_empty`
3. 값이 NaN 인 종목: `int(NaN)` 이 `ValueError` 로 그 날짜 전체를 실패시키지 않고 그 종목만 건너뛴다
4. Toss 의 `nan`·`inf` 문자열: `float()` 는 통과하므로 `math.isfinite` 로 걸러야 한다. 거르지 않으면 `int(nan)` 예외가 그 종목의 5일치를 모두 잃게 한다
5. 실제 0 수량(순매수 0)은 저장된다

## 알려진 한계

1. 버린 (날짜, 종목) 은 그 날짜가 이미 파일에 있으므로 다음 실행에서 「Skip」된다. 그 날짜의 종목 수가 80% 아래로 떨어질 때만 `[INFRA-094]` 재수집 창이 다시 받는다
2. 한쪽 프레임에만 있는 종목의 실제 빈도는 운영에서 확인하지 않았다. 읽는 쪽의 `groupby(ticker).tail(5)`(`engine/signal_tracker_supply_helpers.py:52`, `services/kr_market_stock_detail_service.py:461`)는 「최근 5거래일」이 아니라 「기록된 최근 5행」이므로, 행이 빠지면 창이 누락일만큼 과거로 밀리고 연속 매수 판정은 누락일을 건너뛰어 이어진다(종전에는 가짜 0 이 연속을 끊었다). `services/investor_trend_5day_service.py` 는 5행 미만이면 그 종목을 생략한다(`closing-bet-reviewer` low 1)
3. 이미 저장된 0 은 남는다
4. 한쪽 조회가 통째로 비어 날짜 전체가 빠지면, 그 날짜는 파일에 없으므로 `[INFRA-094]` 의 종목 수 판정(파일에 있는 날짜만 셈)이 다시 받지 않고, 다음 실행은 `max_date+1` 부터 시작해 과거 날짜로 돌아가지 않는다. 종전에는 0 으로 채워졌던 날짜가 영구히 빈다. 이 경우는 WARNING 으로만 알린다(critic 권장 3, 재수집은 범위 밖)
5. pykrx 프레임에 중복 티커 인덱스가 있으면 `.loc` 가 Series 를 돌려 `pd.isna` 진리값 판정이 `ValueError` 를 내고 그 날짜가 저장되지 않는다. 종전 `int(Series)` 도 같이 실패했으므로 회귀가 아니다(리뷰 low 3)
6. Toss 가 당일 행을 종가는 채우고 순매수 수량은 집계 전 `0` 으로 준다면(확인 안 됨) 그 0 은 실제 0 으로 저장된다. `None` 이 아닌 0 은 구분할 수 없다. `source=toss` 이므로 창 안에서는 `[INFRA-094]` 재수집이 pykrx 값으로 덮지만, pykrx 가 주지 않는 종목은 0 이 남는다(심층 리뷰 M2)

---

### Task 1: pykrx·Toss 경로에서 결측 행을 버리기

**Files:**
- Modify: `scripts/init_data.py` (`_collect_toss_trend_rows_for_ticker` 의 종가·수량 읽기, `create_institutional_trend` 의 프레임 병합 루프)
- Test: `tests/scripts/test_init_data_vcp_scheduler.py`

**Interfaces:**
- Consumes/Produces: 함수 서명은 바꾸지 않는다

- [ ] **Step 1: 실패하는 테스트 작성**

`_run_trend_with_fake_krx` 에 선택 인자 `frames`(투자자 → DataFrame)를 더한다. 주어지면 그 프레임을 돌려준다.

```python
def test_create_institutional_trend_skips_tickers_missing_from_one_frame(monkeypatch, tmp_path):
    # [INFRA-095] 한쪽 프레임에만 있는 종목의 다른 쪽은 결측이다. 0 으로 저장하지 않는다
    frames = {
        "외국인": pd.DataFrame({"순매수거래대금": [30, 40]}, index=["000001", "069500"]),
        "기관합계": pd.DataFrame({"순매수거래대금": [50]}, index=["000001"]),
    }
    result, file_path = _run_trend_with_fake_krx(monkeypatch, tmp_path, lambda: None, frames=frames)
    saved = pd.read_csv(file_path, dtype={"ticker": str, "date": str})
    new = saved[saved["date"] == "2026-09-22"]
    assert result is True
    assert list(zip(new["ticker"], new["foreign_buy"], new["inst_buy"])) == [("000001", 30, 50)]


def test_create_institutional_trend_skips_nan_value_but_keeps_real_zero(monkeypatch, tmp_path):
    frames = {
        "외국인": pd.DataFrame({"순매수거래대금": [30, float("nan")]}, index=["000001", "069500"]),
        "기관합계": pd.DataFrame({"순매수거래대금": [50, 60]}, index=["000001", "069500"]),
    }
    result, file_path = _run_trend_with_fake_krx(monkeypatch, tmp_path, lambda: None, frames=frames)
    saved = pd.read_csv(file_path, dtype={"ticker": str, "date": str})
    assert result is True
    assert list(saved.loc[saved["date"] == "2026-09-22", "ticker"]) == ["000001"]


def test_create_institutional_trend_skips_date_without_value_column(monkeypatch, tmp_path):
    frames = {
        "외국인": pd.DataFrame({"순매수거래량": [3]}, index=["000001"]),
        "기관합계": pd.DataFrame({"순매수거래대금": [50]}, index=["000001"]),
    }
    _, file_path = _run_trend_with_fake_krx(monkeypatch, tmp_path, lambda: None, frames=frames)
    saved = pd.read_csv(file_path, dtype={"ticker": str, "date": str})
    assert "2026-09-22" not in set(saved["date"])


def test_toss_trend_rows_drop_missing_fields_but_keep_real_zero(monkeypatch):
    details = [
        {"baseDate": "2026-09-22", "close": 1000, "netForeignerBuyVolume": 0, "netInstitutionBuyVolume": 2},
        {"baseDate": "2026-09-21", "close": None, "netForeignerBuyVolume": 1, "netInstitutionBuyVolume": 1},
        {"baseDate": "2026-09-18", "close": "", "netForeignerBuyVolume": 1, "netInstitutionBuyVolume": 1},
        {"baseDate": "2026-09-17", "close": 0, "netForeignerBuyVolume": 1, "netInstitutionBuyVolume": 1},
        {"baseDate": "2026-09-16", "close": 1000, "netInstitutionBuyVolume": 1},
        {"baseDate": "2026-09-15", "close": 1000, "netForeignerBuyVolume": "nan", "netInstitutionBuyVolume": 1},
        {"baseDate": "2026-09-14", "close": 1000, "netForeignerBuyVolume": 1, "netInstitutionBuyVolume": ""},
    ]
    # engine.toss_collector 를 가짜로 바꾸고 _collect_toss_trend_rows_for_ticker 를 직접 부른다
    ...
    assert [(r["date"], r["foreign_buy"], r["inst_buy"]) for r in rows] == [("2026-09-22", 0, 2000)]
```

- [ ] **Step 2: RED 확인** — `venv/bin/python -m pytest -q -p no:cacheprovider tests/scripts/test_init_data_vcp_scheduler.py -k "missing_from_one_frame or nan_value or without_value_column or real_zero"`
  Expected: 한쪽 프레임·NaN·열 없음·Toss 가 FAIL(0 저장, `ValueError` 로 날짜 실패, 빈 필드 0 행)

- [ ] **Step 3: 구현**

pykrx 병합 루프:

```python
                # [INFRA-095] 한쪽 프레임에만 있거나 값이 비면 결측이다. 0 으로 채우지 않고 저장하지 않는다
                target_intersect = set(df_foreign.index) & set(df_inst.index) & tickers_set

                for ticker in target_intersect:
                    f_val = df_foreign.loc[ticker, '순매수거래대금']
                    i_val = df_inst.loc[ticker, '순매수거래대금']
                    if pd.isna(f_val) or pd.isna(i_val):
                        continue
                    combined_rows.append({...int(f_val)...int(i_val)...})
```

`[INFRA-094]` 의 재수집 날짜 전용 교집합 갈래는 이 교집합에 흡수되므로 지운다.

실행 기록(Ruling): 처음에는 `순매수거래대금` 열이 없으면 경고를 남기고 그 날짜를 비우는 검사를 두었으나, 변이 c(검사 제거)가 살아남았다. 열이 없으면 `loc` 이 `KeyError` 를 내고 날짜 루프의 기존 `except` 가 「수급 데이터 날짜별 수집 실패」 경고와 함께 그 날짜를 저장 없이 건너뛰므로 결과가 같다. 검사를 지우고 주석으로 그 경로를 적었다. 변이 e(종가 `or 0` 복원)도 살아남는데, 0 이 된 종가를 `close > 0` 이 거르므로 동등 변이다.

Toss 행:

```python
        # [INFRA-095] 빈 종가·순매수 수량을 0 으로 채우지 않는다. 실제 0 수량은 저장한다
        try:
            close = float(item["close"])
            foreign_volume = float(item["netForeignerBuyVolume"])
            institution_volume = float(item["netInstitutionBuyVolume"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (close > 0 and math.isfinite(close) and math.isfinite(foreign_volume) and math.isfinite(institution_volume)):
            continue
```

- [ ] **Step 4: GREEN 확인** — Step 2 명령, 이어서 `tests/scripts/test_init_data_vcp_scheduler.py` 전체. Expected: 전부 PASS. 기존 `refetch_keeps_rows_missing_from_one_frame` 도 PASS(교집합이 같은 결과)

- [ ] **Step 5: 변이 확인(격리 사본에서만)** — (a) 교집합을 합집합으로 (b) `pd.isna` 건너뜀 제거 (d) Toss `isfinite` 종가·외국인·기관 각각 제거 (f) Toss 외국인·기관 수량 `or 0` 복원 (g) 한쪽 빈 프레임 경고 제거, `close > 0` 제거. 각각 해당 테스트 FAIL 을 확인한다. (c) 열 없음 검사는 Ruling 대로 지웠고 (e) 종가 `or 0` 복원은 동등 변이라 대상에서 뺀다

실행 기록: 첫 변이 확인(07:58)은 저장소 작업 트리에서 돌려 되돌렸다. critic 이 그 사이 변이 상태를 관찰해 지적했으므로, 재확인(08:0x)은 스크래치 사본 `m095`(`data/`·`.env`·`secrets/` 제외)에서 했다. 결과: 9종 모두 FAIL, 기준 53 passed

- [ ] **Step 6: pytest 전체** — `venv/bin/python -m pytest -q -p no:cacheprovider`. Expected: exit 0
