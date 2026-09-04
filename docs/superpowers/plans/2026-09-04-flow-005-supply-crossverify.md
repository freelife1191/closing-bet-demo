# [FLOW-005] 수급 교차검증을 서비스 안에서 끝낸다 — 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** CSV 수급값을 참조 자료로 교체할지 판정하는 규칙이 실제로 판정하도록 고치고, 지금 도달 불가능한 불일치 판정 함수를 되살린다.

**Architecture:** `_resolve_best_payload` 의 교체 조건 한 줄이 문제의 전부다. 참조 자료는 CSV 이상징후 플래그가 있을 때만 조회되므로, 교체 조건이 `any(disagreement_flags) or bool(csv_flags)` 인 한 `csv_flags` 는 반드시 참이고 불일치 판정은 결과에 아무 영향을 주지 못한다. 이상징후 플래그를 「CSV 를 쓸 수 없음」과 「CSV 가 의심스러움」 두 갈래로 나누고, 뒤의 갈래에서만 `_is_large_disagreement` 로 판정하게 바꾼다. 새 함수나 새 진입점을 만들지 않는다. 「평소에는 CSV 로 답하고 이상징후일 때만 참조를 조회한다」는 정책은 `verify_with_references=True` 한 번 호출이 이미 수행하고 있으므로, 그 사실을 독스트링과 회귀 검사로 못박는 것으로 충분하다.

> **이 Architecture 문단의 뒷부분은 구현 도중 폐기되었다. 실제로 채택한 설계는 바로 아래 절에 있다.** 앞부분(교체 조건이 항상 참이라는 진단)은 그대로 유효하다.

---

## 실제로 채택한 설계 — Task 1 을 폐기한 이유

Task 1 은 `_is_large_disagreement` 를 되살려 「CSV 가 의심스러움」 갈래에서 CSV 와 참조를 견주게 하는 설계였다. codex 리뷰가 그 전제를 깨뜨려 폐기했다.

**견줄 수 없다는 것이 이유다.** 두 자료가 같은 기간을 잰다는 보장이 없다. `stale_csv` 는 정의상 CSV 가 참조와 다른 5거래일을 본다는 뜻이고 `insufficient_days` 는 CSV 가 불완전하다는 뜻이다. 그런 CSV 와 참조의 5일 합계가 비슷하더라도 하루별 값까지 같다고 볼 근거가 없다. `engine/screener_scoring_helpers.py` 의 `_score_supply_core` 는 `details[0]` 와 연속 부호로 25점까지 매기므로, 합계만 맞고 하루별이 어긋난 자료를 「일치한다」고 판정해 CSV 를 남기면 점수가 조용히 틀어진다.

그래서 규칙을 단순하게 만들었다. **이상징후가 붙었고 참조를 받아 왔으면 참조를 쓴다.** 견주는 단계 자체를 없앴으므로 `_is_large_disagreement` 와 전용 상수 두 개(`_DISAGREE_RATIO_THRESHOLD`, `_DISAGREE_SIGNIFICANT_SIDE`)는 되살리지 않고 제거했다. `_DISAGREE_SIGNIFICANT_TOTAL` 은 `_detect_csv_anomaly_flags` 의 하루 급등 판정에서만 쓰이므로 `_SPIKE_SIGNIFICANT_TOTAL` 로 이름을 바꿔 남겼다. `_UNUSABLE_CSV_FLAGS` 도 만들지 않았다.

**남은 문제는 `stale_csv` 의 오판이었다.** 견주기를 없앤 대가로 「연휴 직후 온 시장이 교체된다」는 증상이 그대로 남는다. 그것은 판정을 정확하게 해서 풀었다. 달력 날짜 대신 영업일로 세도록 `_CSV_STALE_DAYS` 를 `_CSV_STALE_BUSINESS_DAYS` 로 바꾸고, `np.busday_count` 에 `MarketSchedule.known_holidays()` 를 넘긴다. 그 조회 함수를 `engine/market_schedule.py` 에 새로 만들었다. `is_market_open` 은 하루를 판정하려고 pykrx 를 부를 수 있어 날짜 구간을 훑는 쪽이 쓸 수 없기 때문이다.

**Task 2~4 는 계획대로 진행했다.** 독스트링으로 중복 호출 패턴을 막고, 호출자 없는 `load_investor_trend_5day_map` 을 제거하고, 백로그를 정리했다. 아래의 Task 1 절은 폐기된 설계의 기록으로 남긴다. 실행하지 말 것.

**Tech Stack:** Python 3.11, pandas, pytest

**Spec:** `docs/dev-cycle/audits/AUDIT-FLOW.md` §1.2, §2.1, §3.1 / `docs/dev-cycle/TODO.md` 의 `[FLOW-005]`

## Global Constraints

- 티어는 T3 이다. `services/investor_trend_5day_service.py` 가 `tier-rules.md` §2 「수급 집계」 위험 경로이기 때문이며 줄 수와 무관하다.
- 리뷰는 `/ponytail-review` → `feature-dev:code-reviewer` → `/review` 순서로 돌린다. 순서를 바꾸지 않는다.
- 검증은 `source venv/bin/activate && pytest` 전체와 `cd frontend && npx vitest run` 전체다. 실행 코드를 바꾸므로 QA 2단계를 거친다.
- 공개 함수의 시그니처를 바꾸지 않는다. `get_investor_trend_5day_for_ticker` 의 호출자가 여섯 자리에 있다.
- 새 상수를 추가할 때 기존 상수 블록(31~43줄)의 명명 관례(`_` 접두사, 숫자는 언더스코어 구분)를 따른다.

---

## 조사로 확정한 사실

계획을 읽는 사람이 코드를 다시 뒤지지 않도록 여기에 모아 둔다.

### 1. 교체 조건이 항상 참인 이유

`services/investor_trend_5day_service.py:824-903` 의 `_resolve_best_payload` 는 다음 순서로 동작한다.

1. `csv_flags = _detect_csv_anomaly_flags(...)` (:838)
2. `if verify_with_references and csv_flags:` 안에서만 참조를 조회한다 (:845)
3. `if not references:` 이면 CSV 를 그대로 돌려준다 (:880)
4. 여기까지 왔다면 `references` 가 비어 있지 않고, 2번 조건 때문에 `csv_flags` 도 비어 있지 않다
5. `should_replace = any(disagreement_flags) or bool(csv_flags)` (:891) 에서 `bool(csv_flags)` 가 항상 참

따라서 `_is_large_disagreement`(:467-498)와 그 함수가 쓰는 세 상수 `_DISAGREE_RATIO_THRESHOLD`, `_DISAGREE_SIGNIFICANT_TOTAL`, `_DISAGREE_SIGNIFICANT_SIDE`(:41-43)는 계산은 되지만 결과에 반영되지 않는다. `_DISAGREE_SIGNIFICANT_TOTAL` 만은 `_detect_csv_anomaly_flags`(:531)에서도 쓰이므로 완전한 죽은 상수는 아니다.

### 2. 이상징후 플래그 다섯 가지와 그 성격

`_detect_csv_anomaly_flags`(:501-541)가 붙이는 플래그다.

| 플래그 | 뜻 | CSV 를 쓸 수 있는가 |
|---|---|---|
| `missing_csv` | 페이로드가 dict 가 아니다 | 못 쓴다 |
| `insufficient_days` | `details` 가 5일치가 안 된다 | 못 쓴다 |
| `single_day_spike` | 하루 절대값이 나머지 평균의 10배 이상이고 100억 이상 | 의심스럽다 |
| `extreme_abs_total` | 절대값 합계가 20조 이상 | 의심스럽다 |
| `stale_csv` | 최신 날짜가 오늘로부터 4일 초과로 지났다 | 의심스럽다 |

`stale_csv` 는 `target_datetime` 이 `None` 일 때만 붙는다(:534). 그리고 달력 날짜로 세므로 주말과 공휴일이 그대로 포함된다. 연휴 직후에는 CSV 가 실제로는 최신인데도 이 플래그가 붙고, 지금의 교체 조건에서는 그것만으로 모든 종목이 pykrx 로 교체된다. 이것이 감사 §1.2 가 지목한 증상이다.

### 3. 「단일 진입점」은 이미 존재한다

TODO 체크박스는 「이상징후 재조회를 서비스 내부에서 수행하는 단일 진입점 추가」를 요구한다. 그러나 `verify_with_references=True` 로 한 번 부르는 것이 정확히 그 진입점이다. `_resolve_best_payload` 가 `csv_flags` 가 비어 있으면 참조를 조회하지 않기 때문이다(:845).

호출자가 `verify_with_references=False` 로 먼저 부르고 플래그를 확인한 뒤 `True` 로 다시 부르는 패턴은, 첫 호출의 반환값을 버리는 중복 호출이다. 새 함수를 만들 이유가 없다.

### 4. 호출자 여섯 자리의 실태 — 감사 기록과 다른 부분

감사 §2.1 은 「두 번 호출 패턴이 다섯 곳에 복제」라고 적었다. 실측하면 다르다. `_has_csv_anomaly_flags` 헬퍼 정의가 다섯 곳에 복제된 것은 맞지만, **두 번 호출을 실제로 하는 곳은 두 곳뿐**이다.

| 위치 | 패턴 |
|---|---|
| `engine/screener.py:359-372` | 두 번 호출. 플래그가 있으면 `verify=True` 로 재호출 |
| `services/kr_market_stock_detail_service.py:231-267` | 두 번 호출. 플래그가 있으면 `verify=True` 로 재호출 |
| `engine/collectors.py:1695` | 두 번 호출이 아니다. 플래그가 있으면 **자기 pykrx fallback** 으로 빠진다 |
| `engine/collectors.py:2235` | 같음 |
| `engine/collectors/krx_local_data_mixin.py:1240` | 같음 |
| `engine/collectors/naver_pykrx_mixin.py:452` | 같음 |

뒤의 네 자리는 「이상징후면 서비스 대신 자기 경로를 쓴다」는 **다른 정책**이다. 한 번 호출로 바꾸면 서비스가 pykrx 교차검증을 하고, 그 뒤의 자체 fallback 코드가 도달 불가능해진다. 그것은 `engine/` 네 파일과 거기 딸린 테스트를 함께 옮기는 작업이며, 감사 자신이 「서비스 쪽 진입점을 먼저 만들고 호출자를 순차로 옮기는 순서가 필요합니다」라고 적었다. 이번 계획은 「먼저」에 해당하는 부분만 다루고 호출자 정리는 새 항목으로 넘긴다.

### 5. `load_investor_trend_5day_map` 의 존치 판단

프로덕션 호출자가 한 곳도 없다. 붙들고 있는 것은 테스트 세 건이다.

- `tests/services/test_investor_trend_5day_service.py:34` — 5일 합산과 최신일 우선 정렬
- `:59` — `target_datetime` 필터
- `:110`, `:120` — SQLite 스냅샷 재사용

함수 본문(:990-999)은 `_normalize_data_dir` → `_get_or_build_trend_map` → `dict()` 얕은 복사뿐이고 자체 계산이 없다.

같은 테스트 파일이 `_load_trend_df`, `_get_reference_trend_cached`, `_resolve_pykrx_latest_market_date`, `_sqlite_cache_key` 를 이미 직접 부르고 있다. 사적 함수를 겨냥하는 것이 이 파일의 관례이므로, 공개 함수를 지우고 테스트를 `_get_or_build_trend_map` 으로 옮겨도 관례에서 벗어나지 않는다.

주의할 점 하나. `_get_or_build_trend_map` 은 `data_dir` 을 정규화하지 않고 얕은 복사도 하지 않는다. 테스트를 옮길 때 `_normalize_data_dir` 을 함께 불러야 하고, 반환된 맵을 변형하면 메모리 캐시를 오염시킨다. 세 테스트 모두 읽기만 하므로 실제로는 문제가 없다.

**결정: 지운다.** 근거는 프로덕션 호출자가 0 이라는 것, 그리고 지웠을 때 테스트가 겨냥하는 자리가 이 파일의 기존 관례와 같아진다는 것이다.

---

## 파일 구조

| 파일 | 이번에 맡는 책임 |
|---|---|
| `services/investor_trend_5day_service.py` | 교체 규칙 수정, 플래그 분류 상수 추가, `verify_with_references` 독스트링 보강, `load_investor_trend_5day_map` 제거 |
| `tests/services/test_investor_trend_5day_service.py` | 교체 규칙 회귀 검사 추가, 제거한 공개 함수를 쓰던 검사 세 건의 겨냥점 이동 |
| `docs/dev-cycle/TODO.md` | `[FLOW-005]` 제거, 호출자 정리를 새 항목으로 추가 |

새 파일을 만들지 않는다. 파일을 쪼개지 않는다. 감사 §4.1 이 이 파일의 분해를 따로 지적하고 있으나 그것은 `[FLOW-005]` 의 범위가 아니다.

---

### Task 1 (폐기): 교체 규칙을 두 갈래로 나눈다

> **이 Task 는 실행하지 않았다.** 폐기 사유는 위의 「실제로 채택한 설계」 절에 있다. 아래는 무엇을 하려 했는지 남기는 기록이다.

**Files:**
- Modify: `services/investor_trend_5day_service.py:41-43`(상수 블록), `:824-903`(`_resolve_best_payload`)
- Test: `tests/services/test_investor_trend_5day_service.py`

**Interfaces:**
- Consumes: `_is_large_disagreement(base_payload, reference_payload) -> bool` (:467), `_detect_csv_anomaly_flags(csv_payload, *, target_datetime) -> list[str]` (:501)
- Produces: 모듈 상수 `_UNUSABLE_CSV_FLAGS: frozenset[str]`. `_resolve_best_payload` 의 시그니처와 반환 모양은 그대로 둔다

- [ ] **Step 1: 실패하는 검사 두 건을 먼저 쓴다**

`tests/services/test_investor_trend_5day_service.py` 의 `test_get_investor_trend_5day_for_ticker_skips_reference_when_csv_is_normal`(:242) 바로 뒤에 붙인다.

```python
def test_stale_csv_is_kept_when_the_reference_agrees(monkeypatch, tmp_path):
    """오래된 CSV 라도 참조가 같은 값을 말하면 CSV 를 그대로 쓴다.

    stale_csv 는 달력 날짜로 판정하므로 연휴 직후에는 CSV 가 실제로 최신인데도 붙는다.
    그것만으로 교체하면 연휴마다 모든 종목이 pykrx 로 갈아치워진다.
    """
    pd.DataFrame(
        [
            {"ticker": "005930", "date": "2026-02-20", "foreign_buy": 1_000_000_000, "inst_buy": 800_000_000},
            {"ticker": "005930", "date": "2026-02-21", "foreign_buy": 1_000_000_000, "inst_buy": 800_000_000},
            {"ticker": "005930", "date": "2026-02-22", "foreign_buy": 1_000_000_000, "inst_buy": 800_000_000},
            {"ticker": "005930", "date": "2026-02-23", "foreign_buy": 1_000_000_000, "inst_buy": 800_000_000},
            {"ticker": "005930", "date": "2026-02-24", "foreign_buy": 1_000_000_000, "inst_buy": 800_000_000},
        ]
    ).to_csv(tmp_path / "all_institutional_trend_data.csv", index=False)

    trend_service.clear_investor_trend_5day_memory_cache()
    monkeypatch.setattr(
        trend_service,
        "_fetch_pykrx_reference_trend",
        lambda **_kwargs: {
            "foreign": 5_000_000_000,
            "institution": 4_000_000_000,
            "details": [
                {"netForeignerBuyVolume": 1_000_000_000, "netInstitutionBuyVolume": 800_000_000}
                for _ in range(5)
            ],
            "latest_date": "2026-02-24",
            "source": "pykrx",
        },
    )

    result = trend_service.get_investor_trend_5day_for_ticker(
        ticker="005930",
        data_dir=str(tmp_path),
    )

    assert result is not None
    assert "stale_csv" in result["quality"]["csv_anomaly_flags"]
    assert result["source"] == "csv"
    assert result["foreign"] == 5_000_000_000


def test_stale_csv_is_replaced_when_the_reference_disagrees(monkeypatch, tmp_path):
    """참조가 크게 다른 값을 말하면 오래된 CSV 를 버린다.

    부호가 반대이고 양쪽 모두 유의미한 규모이므로 _is_large_disagreement 가 참이다.
    """
    pd.DataFrame(
        [
            {"ticker": "005930", "date": "2026-02-20", "foreign_buy": 1_000_000_000, "inst_buy": 800_000_000},
            {"ticker": "005930", "date": "2026-02-21", "foreign_buy": 1_000_000_000, "inst_buy": 800_000_000},
            {"ticker": "005930", "date": "2026-02-22", "foreign_buy": 1_000_000_000, "inst_buy": 800_000_000},
            {"ticker": "005930", "date": "2026-02-23", "foreign_buy": 1_000_000_000, "inst_buy": 800_000_000},
            {"ticker": "005930", "date": "2026-02-24", "foreign_buy": 1_000_000_000, "inst_buy": 800_000_000},
        ]
    ).to_csv(tmp_path / "all_institutional_trend_data.csv", index=False)

    trend_service.clear_investor_trend_5day_memory_cache()
    monkeypatch.setattr(
        trend_service,
        "_fetch_pykrx_reference_trend",
        lambda **_kwargs: {
            "foreign": -5_000_000_000,
            "institution": -4_000_000_000,
            "details": [
                {"netForeignerBuyVolume": -1_000_000_000, "netInstitutionBuyVolume": -800_000_000}
                for _ in range(5)
            ],
            "latest_date": "2026-02-26",
            "source": "pykrx",
        },
    )

    result = trend_service.get_investor_trend_5day_for_ticker(
        ticker="005930",
        data_dir=str(tmp_path),
    )

    assert result is not None
    assert result["source"] == "pykrx"
    assert result["foreign"] == -5_000_000_000
```

- [ ] **Step 2: 검사가 실패하는 것을 확인한다**

Run: `source venv/bin/activate && pytest tests/services/test_investor_trend_5day_service.py::test_stale_csv_is_kept_when_the_reference_agrees -v`

Expected: FAIL. `result["source"]` 가 `"csv"` 가 아니라 `"pykrx"` 로 나온다. 지금은 플래그가 있으면 무조건 교체하기 때문이다.

두 번째 검사는 지금도 통과한다. 무조건 교체가 우연히 같은 결과를 내기 때문이다. 그것이 정상이며, 이 검사는 규칙을 바꾼 뒤에도 교체가 일어나는지 지키는 자리다.

- [ ] **Step 3: 상수를 추가한다**

`services/investor_trend_5day_service.py` 의 `_DISAGREE_SIGNIFICANT_SIDE = 3_000_000_000` 줄(:43) 바로 뒤에 붙인다.

```python
# CSV 를 아예 쓸 수 없다는 뜻의 플래그. 이 경우에는 참조가 있으면 그대로 교체한다.
# 나머지 플래그(single_day_spike, extreme_abs_total, stale_csv)는 CSV 를 의심할
# 근거일 뿐이므로, 참조와 실제로 크게 다를 때만 교체한다.
_UNUSABLE_CSV_FLAGS = frozenset({"missing_csv", "insufficient_days"})
```

- [ ] **Step 4: 교체 조건을 바꾼다**

`_resolve_best_payload` 의 다음 세 줄(:886-891)을

```python
    disagreement_flags = [
        _is_large_disagreement(normalized_csv, reference_payload)
        for reference_payload in references
    ]
    should_replace = any(disagreement_flags) or bool(csv_flags)
```

이렇게 바꾼다.

```python
    # CSV 를 쓸 수 없는 플래그면 참조로 바로 간다. 의심 플래그뿐이면 참조와 실제로
    # 크게 어긋날 때만 교체한다. 앞서 이 자리는 `or bool(csv_flags)` 를 달고 있었는데,
    # 참조 조회 자체가 플래그가 있을 때만 일어나므로 그 항이 언제나 참이었고 불일치
    # 판정이 결과에 닿지 못했다.
    should_replace = bool(_UNUSABLE_CSV_FLAGS.intersection(csv_flags)) or any(
        _is_large_disagreement(normalized_csv, reference_payload)
        for reference_payload in references
    )
```

- [ ] **Step 5: 검사가 통과하는 것을 확인한다**

Run: `source venv/bin/activate && pytest tests/services/test_investor_trend_5day_service.py -v`

Expected: 15건 전부 PASS. 기존 13건 가운데 `test_get_investor_trend_5day_for_ticker_replaces_anomalous_csv_with_pykrx`(:138)가 특히 중요하다. 이 검사의 CSV 는 마지막 날 500억·400억으로 튀어 `single_day_spike` 가 붙고, 참조는 100억·80억이라 비율이 2.5배를 넘으므로 새 규칙에서도 교체된다.

- [ ] **Step 6: 회귀를 심어 검사가 실제로 잡는지 확인한다**

`_UNUSABLE_CSV_FLAGS.intersection(csv_flags)` 를 `bool(csv_flags)` 로 되돌린 뒤 같은 명령을 돌린다.

Expected: `test_stale_csv_is_kept_when_the_reference_agrees` **하나만** 실패하고 나머지 14건은 통과한다. 다른 검사까지 함께 무너지면 새 검사가 겨냥하는 자리가 흐릿하다는 뜻이므로 검사를 다시 손본다. 확인한 뒤 원복한다.

---

### Task 2: 단일 진입점이 이미 있음을 독스트링과 검사로 못박는다

**Files:**
- Modify: `services/investor_trend_5day_service.py:1002-1031`(`get_investor_trend_5day_for_ticker` 의 독스트링)
- Test: `tests/services/test_investor_trend_5day_service.py`

**Interfaces:**
- Consumes: Task 1 이 고친 `_resolve_best_payload`
- Produces: 없다. 공개 시그니처를 바꾸지 않는다

- [ ] **Step 1: 검사를 쓴다**

Task 1 에서 추가한 두 검사 뒤에 붙인다.

```python
def test_verify_with_references_does_not_fetch_when_csv_is_clean(monkeypatch, tmp_path):
    """verify_with_references=True 한 번이 곧 「이상징후일 때만 참조 조회」다.

    호출자가 verify=False 로 먼저 부르고 플래그를 본 뒤 verify=True 로 다시 부르는
    패턴은 첫 호출의 반환값을 버리는 중복이다. 이 검사가 그 사실을 못박는다.
    """
    today = datetime.now().date()
    recent_dates = [
        (today - pd.Timedelta(days=offset)).strftime("%Y-%m-%d")
        for offset in (4, 3, 2, 1, 0)
    ]
    pd.DataFrame(
        [
            {"ticker": "005930", "date": date, "foreign_buy": 10, "inst_buy": 20}
            for date in recent_dates
        ]
    ).to_csv(tmp_path / "all_institutional_trend_data.csv", index=False)

    trend_service.clear_investor_trend_5day_memory_cache()
    monkeypatch.setattr(
        trend_service,
        "_fetch_pykrx_reference_trend",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("reference fetch should be skipped")),
    )
    monkeypatch.setattr(
        trend_service,
        "_fetch_toss_reference_trend",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("reference fetch should be skipped")),
    )

    result = trend_service.get_investor_trend_5day_for_ticker(
        ticker="005930",
        data_dir=str(tmp_path),
        verify_with_references=True,
    )

    assert result is not None
    assert result["source"] == "csv"
    assert result["quality"]["csv_anomaly_flags"] == []
```

- [ ] **Step 2: 검사를 돌린다**

Run: `source venv/bin/activate && pytest tests/services/test_investor_trend_5day_service.py::test_verify_with_references_does_not_fetch_when_csv_is_clean -v`

Expected: PASS. 이 검사는 처음부터 통과한다. 새 동작을 요구하는 것이 아니라 이미 있는 계약을 고정하는 자리이기 때문이다.

- [ ] **Step 3: 독스트링을 고친다**

`get_investor_trend_5day_for_ticker` 의 독스트링(:1010-1015)을 이렇게 바꾼다.

```python
    """
    단일 ticker의 5거래일 수급 합산 데이터를 반환한다.

    verify_with_references=True 는 그 자체가 「평소에는 CSV 로 답하고 이상징후일 때만
    참조를 조회한다」는 정책이다. CSV 에 이상징후 플래그가 붙지 않으면 참조를 조회하지
    않으므로, 호출자가 verify_with_references=False 로 먼저 부르고 플래그를 확인한 뒤
    True 로 다시 부를 필요가 없다. 그 패턴은 첫 호출의 반환값을 버리는 중복 호출이다.

    참조를 조회한 뒤 CSV 를 교체할지는 플래그의 성격이 가른다. missing_csv 와
    insufficient_days 는 CSV 를 쓸 수 없다는 뜻이므로 참조가 있으면 교체하고,
    single_day_spike·extreme_abs_total·stale_csv 는 의심할 근거일 뿐이므로 참조와
    실제로 크게 어긋날 때만 교체한다.
    """
```

- [ ] **Step 4: 전체 검사를 돌린다**

Run: `source venv/bin/activate && pytest tests/services/test_investor_trend_5day_service.py -v`

Expected: 16건 전부 PASS.

---

### Task 3: 호출자 없는 `load_investor_trend_5day_map` 을 제거한다

**Files:**
- Modify: `services/investor_trend_5day_service.py:971-999`(함수 정의), `:1044-1048`(`__all__`)
- Test: `tests/services/test_investor_trend_5day_service.py:34, 59, 110, 120`

**Interfaces:**
- Consumes: `_normalize_data_dir(data_dir) -> str` (:60), `_get_or_build_trend_map(*, data_dir, filename, target_datetime) -> dict[str, dict[str, Any]]` (:905)
- Produces: 없다. 공개 API 하나가 사라진다

- [ ] **Step 1: 테스트 세 건의 겨냥점을 옮긴다**

`tests/services/test_investor_trend_5day_service.py` 에서 `trend_service.load_investor_trend_5day_map(...)` 을 부르는 네 자리를 바꾼다. `_get_or_build_trend_map` 은 `data_dir` 을 정규화하지 않으므로 `_normalize_data_dir` 을 함께 부른다.

`:34` 는

```python
    trend_map = trend_service.load_investor_trend_5day_map(data_dir=str(tmp_path))
```

에서

```python
    trend_map = trend_service._get_or_build_trend_map(
        data_dir=trend_service._normalize_data_dir(str(tmp_path)),
        filename="all_institutional_trend_data.csv",
    )
```

로 바꾼다. `:59` 는 `target_datetime=datetime(2026, 2, 23)` 인자를 함께 넘긴다.

```python
    trend_map = trend_service._get_or_build_trend_map(
        data_dir=trend_service._normalize_data_dir(str(tmp_path)),
        filename="all_institutional_trend_data.csv",
        target_datetime=datetime(2026, 2, 23),
    )
```

`:110` 과 `:120` 도 `:34` 와 같은 형태로 바꾼다. 변수 이름은 각각 `first` 와 `second` 를 유지한다.

- [ ] **Step 2: 검사가 통과하는 것을 확인한다**

Run: `source venv/bin/activate && pytest tests/services/test_investor_trend_5day_service.py -v`

Expected: 16건 전부 PASS. 아직 함수를 지우지 않았으므로 이 단계는 옮긴 겨냥점이 같은 것을 검사하는지 확인하는 자리다.

- [ ] **Step 3: 함수와 `__all__` 항목을 지운다**

`services/investor_trend_5day_service.py` 의 `def load_investor_trend_5day_map(` 부터 그 함수의 마지막 줄 `return dict(trend_map)` 까지를 지운다. `__all__` 에서 `"load_investor_trend_5day_map",` 한 줄도 함께 지운다.

- [ ] **Step 4: 남은 참조가 없는지 확인한다**

Run: `grep -rn "load_investor_trend_5day_map" --include="*.py" .`

Expected: 출력이 없다. 한 줄이라도 남으면 그 자리를 함께 고친다.

- [ ] **Step 5: 전체 검사를 돌린다**

Run: `source venv/bin/activate && pytest`

Expected: 1616건 이상 PASS, 2건 SKIP. 새 검사 세 건이 늘었으므로 1619건 이상이다.

---

### Task 4: 백로그를 정리하고 커밋한다

**Files:**
- Modify: `docs/dev-cycle/TODO.md`

**Interfaces:**
- Consumes: Task 1~3 의 변경
- Produces: 새 백로그 항목 `[FLOW-011]`

- [ ] **Step 1: `[FLOW-005]` 블록을 지우고 새 항목을 추가한다**

`docs/dev-cycle/TODO.md` 의 `### [FLOW-005]` 블록을 통째로 지운다. 같은 자리(P1 의 맨 앞)에 다음을 넣는다.

```markdown
### [FLOW-011] 수급 조회 호출자를 서비스의 교차검증 하나로 모은다
- 카테고리: 수급·백테스트 | 티어: T3 | 근거: AUDIT-FLOW §2.1, `[FLOW-005]` 사이클의 실측
- `[FLOW-005]` 가 서비스 안의 교체 규칙을 고쳤다. 남은 것은 호출자 쪽이다. 감사가 「두 번
  호출 패턴이 다섯 곳」이라고 적었으나 실측하면 두 가지가 섞여 있다.
  - 두 번 호출: `engine/screener.py:359-372`,
    `services/kr_market_stock_detail_service.py:231-267`. `verify_with_references=True`
    한 번으로 대체할 수 있다. 서비스가 이미 「플래그가 있을 때만 참조 조회」를 한다
  - 자체 fallback: `engine/collectors.py:1695`, `:2235`,
    `engine/collectors/krx_local_data_mixin.py:1240`,
    `engine/collectors/naver_pykrx_mixin.py:452`. 이상징후면 서비스를 다시 부르지 않고
    자기 pykrx 경로로 빠진다. 서비스가 이미 pykrx 로 교차검증하므로 같은 일을 두 번 한다
- 동작 변화가 따른다. `verify=True` 한 번 호출은 CSV 에 아예 없는 종목도 `missing_csv`
  플래그를 거쳐 pykrx 로 채운다. 지금은 그 경우 `None` 이 돌아가 호출자의 fallback 으로
  간다. screener 는 대량 종목을 돌리므로 네트워크 호출 증가를 먼저 재어 본다
- [ ] 두 번 호출하는 두 자리를 한 번 호출로 바꾸고 그 자리의 `_has_csv_anomaly_flags` 제거
- [ ] 자체 fallback 네 자리의 동작 변화를 재고 옮길지 결정. 옮기면 도달 불가능해지는
      fallback 코드를 함께 정리
- [ ] screener 경로의 pykrx 호출 횟수가 늘지 않는지 확인
- [ ] `_has_csv_anomaly_flags` 복제 다섯 벌 가운데 남은 것을 정리
```

- [ ] **Step 2: 첫 커밋을 만든다**

QA 시나리오 문서를 함께 담는다. 시나리오 문서는 dev-cycle [3] 검증의 4번에서 작성한다.

```bash
git add services/investor_trend_5day_service.py \
        tests/services/test_investor_trend_5day_service.py \
        docs/dev-cycle/TODO.md \
        docs/dev-cycle/qa/FLOW-005.md \
        docs/superpowers/plans/2026-09-04-flow-005-supply-crossverify.md
git commit -m "fix(수급): [FLOW-005] 수급 교차검증이 불일치를 실제로 판정하게 한다"
```

---

## 자체 점검

**1. 백로그 체크박스 대조**

| 체크박스 | 다루는 Task |
|---|---|
| `_resolve_best_payload` 의 교체 조건을 다시 정의해 `_is_large_disagreement` 가 실제로 판정에 쓰이도록 | Task 1 |
| `stale_csv` 단독으로 무조건 교체하던 동작을 의도한 규칙으로 고침 | Task 1 |
| 이상징후 재조회를 서비스 내부에서 수행하는 단일 진입점 추가 | Task 2. 새로 만들지 않고 이미 있음을 확인해 못박는다 |
| 호출자 다섯 곳을 그 진입점으로 교체 | Task 4 에서 `[FLOW-011]` 로 분리. 근거는 위 「조사로 확정한 사실」 4번 |
| 호출자가 없는 `load_investor_trend_5day_map` 의 존치 여부 결정 | Task 3. 지우기로 결정 |
| 교체 규칙 회귀 테스트 추가 (일치·불일치·지연 각 경우) | Task 1 의 두 검사가 지연·일치와 지연·불일치를 덮고, 기존 `:138` 검사가 급등·불일치를 덮는다 |

**2. 자리 표시자 점검**

「적절한 오류 처리를 추가한다」류의 문장이 없다. 모든 코드 단계에 실제 코드가 들어 있다.

**3. 이름 일관성**

`_UNUSABLE_CSV_FLAGS` 는 Task 1 Step 3 에서 정의하고 Step 4 에서만 쓴다. `_get_or_build_trend_map` 과 `_normalize_data_dir` 은 Task 3 에서 쓰며 둘 다 기존 함수다. 새로 만드는 이름은 상수 하나뿐이다.
