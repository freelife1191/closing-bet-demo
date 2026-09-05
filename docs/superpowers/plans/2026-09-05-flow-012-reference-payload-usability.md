# [FLOW-012] 참조 수급 자료 유효성 판정 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** CSV 에 이상징후가 붙었을 때 가져오는 참조 수급 자료가 쓸 만한 값인지 먼저 판정하고, 퇴화한 참조로 정확한 CSV 가 덮이지 않게 한다.

**Architecture:** 판정 함수 하나를 `services/investor_trend_5day_service.py` 에 두고, `_resolve_best_payload` 가 참조를 `references` 목록에 넣기 전에 그 함수를 통과시킨다. 걸러낸 참조는 버리지 않고 사유와 함께 `quality.discarded_references` 에 남겨 화면과 로그에서 원인을 알 수 있게 한다. CSV 대응값이 아예 없어(`missing_csv`) 참조 단독으로 채운 경우에는 `quality.reference_only` 표식을 붙인다.

**Tech Stack:** Python 3.11, pandas, pytest

**Spec:** `docs/dev-cycle/TODO.md` 의 `### [FLOW-012] 참조 수급 자료를 믿기 전에 쓸 만한 값인지 본다`

## Global Constraints

- 위험 경로: `services/investor_trend_5day_service.py` 는 티어 규칙 §2 의 「수급 집계」에 속한다. 티어는 T3 이며 하향하지 않는다.
- 기존 공개 API 세 개(`get_investor_trend_5day_for_ticker`, `has_csv_anomaly_flags`, `clear_investor_trend_5day_memory_cache`)의 시그니처를 바꾸지 않는다. 호출자가 `engine/screener.py`, `engine/collectors.py`, `engine/collectors/naver_pykrx_mixin.py`, `engine/collectors/krx_local_data_mixin.py`, `services/kr_market_stock_detail_service.py` 다섯 곳이다.
- `quality` 블록에 키를 더하기만 하고 기존 키(`csv_anomaly_flags`, `reference_sources`)의 의미를 바꾸지 않는다. `has_csv_anomaly_flags` 가 `csv_anomaly_flags` 만 읽으므로 다섯 호출자의 분기가 그대로 유지되어야 한다.
- 점수 산정 로직(`engine/screener_scoring_helpers.py`, `score_supply_from_toss_trend`)을 이번 사이클에서 바꾸지 않는다. 근거는 Task 3 에 적는다.
- 테스트는 `tests/services/test_investor_trend_5day_service.py` 에 이어 붙인다. 새 파일이나 픽스처 계층을 만들지 않는다.

---

### Task 1: 참조 유효성 판정 함수

**Files:**
- Modify: `services/investor_trend_5day_service.py`
- Test: `tests/services/test_investor_trend_5day_service.py`

**Interfaces:**
- Consumes: 기존 `_safe_int`(`:87`), `_extract_abs_total`(`:101`), `_CSV_EXTREME_ABS_TOTAL`(`:40`)
- Produces: `_reference_reject_reason(payload: dict[str, Any] | None) -> str | None`. 쓸 만하면 `None`, 아니면 사유 문자열 하나를 돌려준다. 사유는 `"not_a_dict"`, `"insufficient_days"`, `"zero_total"`, `"extreme_abs_total"` 넷이다. Task 2 가 이 반환값을 그대로 `quality.discarded_references` 의 문자열로 쓴다.

판정 세 가지의 근거를 각각 적어 둔다.

- `insufficient_days`: `details` 가 리스트이고 원소가 다섯이어야 한다. `_fetch_pykrx_reference_trend` 는 `len(trend_df) < 5` 에서 이미 걸러 내지만 `_fetch_toss_reference_trend` 가 거치는 `_normalize_external_trend_payload` 는 개수를 전혀 검사하지 않고 빈 `details` 에도 `days: 5` 를 붙여 돌려준다. `engine/screener_scoring_helpers.py` 의 `_score_supply_core` 가 `details[0]` 와 연속 부호로 25점까지 매기므로, 개수가 모자라면 점수가 조용히 왜곡된다.
- `zero_total`: 하루별 절대값의 총합이 0 인 경우다. 5일 **합계**만 0 인 경우는 매수와 매도가 상쇄된 정상 자료이므로 걸러 내면 안 된다. 거래정지 종목이나 파싱 실패로 전 항목이 0 이 된 경우만 잡아야 하므로 `details` 의 하루별 값을 절대값으로 더해 판정한다.
- `extreme_abs_total`: CSV 쪽에는 `_CSV_EXTREME_ABS_TOTAL`(20조) 상한이 있는데 참조 쪽에는 없다. Toss 가 비공식 API 라 응답 형태가 바뀌면 조용히 이상한 값이 들어온다. 같은 상한을 참조에도 적용해 두 자료의 기준을 맞춘다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`tests/services/test_investor_trend_5day_service.py` 끝에 붙인다.

```python
def test_reference_reject_reason_accepts_a_complete_payload():
    payload = {
        "foreign": 1_000,
        "institution": 2_000,
        "details": [{"netForeignerBuyVolume": 200, "netInstitutionBuyVolume": 400}] * 5,
    }
    assert trend_service._reference_reject_reason(payload) is None


def test_reference_reject_reason_rejects_short_or_missing_details():
    assert trend_service._reference_reject_reason(None) == "not_a_dict"
    assert (
        trend_service._reference_reject_reason(
            {"foreign": 1_000, "institution": 0, "details": []}
        )
        == "insufficient_days"
    )
    assert (
        trend_service._reference_reject_reason(
            {
                "foreign": 1_000,
                "institution": 0,
                "details": [{"netForeignerBuyVolume": 1_000, "netInstitutionBuyVolume": 0}] * 4,
            }
        )
        == "insufficient_days"
    )


def test_reference_reject_reason_rejects_an_all_zero_payload():
    payload = {
        "foreign": 0,
        "institution": 0,
        "details": [{"netForeignerBuyVolume": 0, "netInstitutionBuyVolume": 0}] * 5,
    }
    assert trend_service._reference_reject_reason(payload) == "zero_total"


def test_reference_reject_reason_keeps_a_payload_whose_sum_cancels_out():
    """5일 합계가 0 이어도 하루별 값이 살아 있으면 정상 자료다."""
    payload = {
        "foreign": 0,
        "institution": 0,
        "details": [
            {"netForeignerBuyVolume": 500, "netInstitutionBuyVolume": -500},
            {"netForeignerBuyVolume": -500, "netInstitutionBuyVolume": 500},
            {"netForeignerBuyVolume": 300, "netInstitutionBuyVolume": -300},
            {"netForeignerBuyVolume": -300, "netInstitutionBuyVolume": 300},
            {"netForeignerBuyVolume": 0, "netInstitutionBuyVolume": 0},
        ],
    }
    assert trend_service._reference_reject_reason(payload) is None


def test_reference_reject_reason_rejects_an_extreme_total():
    payload = {
        "foreign": trend_service._CSV_EXTREME_ABS_TOTAL,
        "institution": 0,
        "details": [{"netForeignerBuyVolume": 1, "netInstitutionBuyVolume": 0}] * 5,
    }
    assert trend_service._reference_reject_reason(payload) == "extreme_abs_total"
```

- [ ] **Step 2: 테스트가 실패하는지 확인한다**

Run: `source venv/bin/activate && pytest tests/services/test_investor_trend_5day_service.py -k reference_reject_reason -v`
Expected: FAIL with `AttributeError: module 'services.investor_trend_5day_service' has no attribute '_reference_reject_reason'`

- [ ] **Step 3: 판정 함수를 구현한다**

`_detect_csv_anomaly_flags`(`:467`) 바로 앞에 둔다. 두 함수가 같은 일을 서로 다른 자료에 하므로 나란히 두면 기준이 어긋났을 때 눈에 띈다.

```python
_REFERENCE_REQUIRED_DETAIL_DAYS = 5


def _reference_reject_reason(payload: dict[str, Any] | None) -> str | None:
    """참조 페이로드를 쓸 수 없는 사유를 돌려준다. 쓸 만하면 None 이다.

    CSV 에 이상징후가 붙으면 참조가 CSV 를 통째로 대신하므로, 참조가 퇴화한
    값이면 정확한 CSV 가 그 값으로 덮인다. 판정 기준 세 가지의 근거는 계획 문서
    docs/superpowers/plans/2026-09-05-flow-012-reference-payload-usability.md 에 있다.
    """
    if not isinstance(payload, dict):
        return "not_a_dict"

    details = payload.get("details")
    if not isinstance(details, list) or len(details) < _REFERENCE_REQUIRED_DETAIL_DAYS:
        return "insufficient_days"

    day_abs_total = 0
    for detail in details[:_REFERENCE_REQUIRED_DETAIL_DAYS]:
        if not isinstance(detail, dict):
            return "insufficient_days"
        day_abs_total += abs(_safe_int(detail.get("netForeignerBuyVolume", 0)))
        day_abs_total += abs(_safe_int(detail.get("netInstitutionBuyVolume", 0)))

    if day_abs_total == 0:
        return "zero_total"

    if _extract_abs_total(payload) >= _CSV_EXTREME_ABS_TOTAL:
        return "extreme_abs_total"

    return None
```

- [ ] **Step 4: 테스트가 통과하는지 확인한다**

Run: `source venv/bin/activate && pytest tests/services/test_investor_trend_5day_service.py -k reference_reject_reason -v`
Expected: PASS (5 passed)

---

### Task 2: 걸러 낸 참조를 quality 에 남기고 CSV 를 살린다

**Files:**
- Modify: `services/investor_trend_5day_service.py` (`_attach_selection_metadata:788`, `_resolve_best_payload:804`)
- Test: `tests/services/test_investor_trend_5day_service.py`

**Interfaces:**
- Consumes: Task 1 의 `_reference_reject_reason`
- Produces: `quality` 블록에 키 두 개가 늘어난다.
  - `discarded_references: list[str]` — 걸러 낸 참조를 `"<source>:<reason>"` 형식으로 담는다. 예: `["pykrx:zero_total"]`. 걸러 낸 것이 없으면 빈 리스트다.
  - `reference_only: bool` — CSV 대응값이 없어 참조 단독으로 채운 경우에만 `True` 다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

```python
def test_a_zero_reference_does_not_overwrite_a_stale_but_real_csv(monkeypatch, tmp_path):
    """퇴화한 참조로 정확한 CSV 가 덮이지 않는다."""
    _write_trend_csv(
        tmp_path,
        ticker="005930",
        rows=[
            ("2026-08-01", 1_000, 2_000),
            ("2026-08-02", 1_100, 2_100),
            ("2026-08-03", 1_200, 2_200),
            ("2026-08-04", 1_300, 2_300),
            ("2026-08-05", 1_400, 2_400),
        ],
    )
    monkeypatch.setattr(
        trend_service,
        "_get_reference_trend_cached",
        lambda **kwargs: {
            "foreign": 0,
            "institution": 0,
            "details": [{"netForeignerBuyVolume": 0, "netInstitutionBuyVolume": 0}] * 5,
            "days": 5,
            "latest_date": "2026-09-04",
            "source": "pykrx",
        },
    )

    result = trend_service.get_investor_trend_5day_for_ticker(
        ticker="005930",
        data_dir=str(tmp_path),
    )

    assert result is not None
    assert result["source"] == "csv"
    assert result["foreign"] == 6_000
    assert result["quality"]["discarded_references"] == ["pykrx:zero_total"]
    assert result["quality"]["reference_sources"] == []


def test_missing_csv_with_only_a_bad_reference_returns_nothing(monkeypatch, tmp_path):
    _write_trend_csv(tmp_path, ticker="000660", rows=[("2026-08-01", 1_000, 2_000)])
    monkeypatch.setattr(
        trend_service,
        "_get_reference_trend_cached",
        lambda **kwargs: {
            "foreign": 5_000,
            "institution": 0,
            "details": [],
            "days": 5,
            "latest_date": "",
            "source": "toss",
        },
    )

    result = trend_service.get_investor_trend_5day_for_ticker(
        ticker="005930",
        data_dir=str(tmp_path),
    )

    assert result is None


def test_reference_only_marks_a_payload_built_without_any_csv(monkeypatch, tmp_path):
    _write_trend_csv(tmp_path, ticker="000660", rows=[("2026-08-01", 1_000, 2_000)])
    monkeypatch.setattr(
        trend_service,
        "_get_reference_trend_cached",
        lambda **kwargs: {
            "foreign": 7_000,
            "institution": 3_000,
            "details": [{"netForeignerBuyVolume": 1_400, "netInstitutionBuyVolume": 600}] * 5,
            "days": 5,
            "latest_date": "2026-09-04",
            "source": "pykrx",
        },
    )

    result = trend_service.get_investor_trend_5day_for_ticker(
        ticker="005930",
        data_dir=str(tmp_path),
    )

    assert result is not None
    assert result["source"] == "pykrx"
    assert result["quality"]["reference_only"] is True
    assert "missing_csv" in result["quality"]["csv_anomaly_flags"]


def test_reference_only_is_false_when_a_csv_row_existed(monkeypatch, tmp_path):
    """CSV 가 이상징후로 교체된 경우는 reference_only 가 아니다. 견줄 값이 남아 있다."""
    _write_trend_csv(
        tmp_path,
        ticker="005930",
        rows=[
            ("2026-08-01", 1_000, 2_000),
            ("2026-08-02", 1_100, 2_100),
            ("2026-08-03", 1_200, 2_200),
            ("2026-08-04", 1_300, 2_300),
            ("2026-08-05", 1_400, 2_400),
        ],
    )
    monkeypatch.setattr(
        trend_service,
        "_get_reference_trend_cached",
        lambda **kwargs: {
            "foreign": 7_000,
            "institution": 3_000,
            "details": [{"netForeignerBuyVolume": 1_400, "netInstitutionBuyVolume": 600}] * 5,
            "days": 5,
            "latest_date": "2026-09-04",
            "source": "pykrx",
        },
    )

    result = trend_service.get_investor_trend_5day_for_ticker(
        ticker="005930",
        data_dir=str(tmp_path),
    )

    assert result is not None
    assert result["source"] == "pykrx"
    assert result["quality"]["reference_only"] is False
```

`_write_trend_csv` 는 기존 테스트 파일에 이미 있는 헬퍼를 쓴다. 이름이 다르면 그 파일의 실제 헬퍼 이름에 맞춘다. 새 헬퍼를 만들지 않는다.

- [ ] **Step 2: 테스트가 실패하는지 확인한다**

Run: `source venv/bin/activate && pytest tests/services/test_investor_trend_5day_service.py -k "zero_reference or reference_only or only_a_bad_reference" -v`
Expected: FAIL — `KeyError: 'discarded_references'` 와 `assert result["source"] == "csv"` 에서 `"pykrx"` 가 나온다

- [ ] **Step 3: `_attach_selection_metadata` 에 키 두 개를 더한다**

```python
def _attach_selection_metadata(
    payload: dict[str, Any],
    *,
    selected_source: str,
    csv_flags: list[str],
    reference_sources: list[str],
    discarded_references: list[str] | None = None,
    reference_only: bool = False,
) -> dict[str, Any]:
    enriched = dict(payload)
    enriched["source"] = selected_source
    enriched["quality"] = {
        "csv_anomaly_flags": list(csv_flags),
        "reference_sources": list(reference_sources),
        "discarded_references": list(discarded_references or []),
        "reference_only": bool(reference_only),
    }
    return enriched
```

- [ ] **Step 4: `_resolve_best_payload` 가 참조를 걸러 내게 한다**

참조를 `references` 에 넣는 자리 두 곳(pykrx, toss)을 한 헬퍼로 모은다. 두 곳에 같은 판정을 복제하면 한쪽만 고쳐지는 일이 생긴다.

```python
    references: list[dict[str, Any]] = []
    discarded_references: list[str] = []

    def _accept_reference(candidate: dict[str, Any] | None, *, source: str) -> bool:
        """쓸 만한 참조면 references 에 넣고 True 를 돌려준다."""
        if not candidate:
            return False
        reason = _reference_reject_reason(candidate)
        if reason is not None:
            discarded_references.append(f"{source}:{reason}")
            logger.debug(
                "Discarded %s reference trend for %s: %s",
                source,
                ticker,
                reason,
            )
            return False
        references.append(candidate)
        return True

    if verify_with_references and csv_flags:
        pykrx_ref = _get_reference_trend_cached(
            data_dir=data_dir,
            source="pykrx",
            ticker=ticker,
            target_datetime=target_datetime,
        )
        accepted_pykrx = _accept_reference(pykrx_ref, source="pykrx")

        # 기본 우선순위가 pykrx이므로 쓸 만한 pykrx 참조가 있으면 Toss 조회를 생략해
        # 지연을 줄인다. pykrx 를 걸러 냈다면 Toss 를 조회한다. 걸러 낸 참조는 없는
        # 것과 같으므로 대체 자료를 찾아야 한다.
        if not accepted_pykrx and is_latest_reference_window:
            toss_ref = _get_reference_trend_cached(
                data_dir=data_dir,
                source="toss",
                ticker=ticker,
                target_datetime=target_datetime,
            )
            _accept_reference(toss_ref, source="toss")
```

세 곳의 `_attach_selection_metadata` 호출에 `discarded_references=discarded_references` 를 더한다. `reference_only` 는 `normalized_csv is None` 인 갈래에서만 `True` 다. 나머지 두 갈래는 기본값 `False` 를 그대로 쓴다.

- [ ] **Step 5: 테스트가 통과하는지 확인한다**

Run: `source venv/bin/activate && pytest tests/services/test_investor_trend_5day_service.py -v`
Expected: PASS. 기존 21건과 새 9건이 모두 통과한다. 기존 테스트가 `quality` 를 딕셔너리 비교로 검사하고 있으면 새 키 때문에 깨지므로, 그 테스트는 키 단위 검사로 고친다.

- [ ] **Step 6: 커밋은 [4] 마감에서 한다**

dev-cycle 절차상 첫 커밋은 [3] 검증의 5번에서 시나리오 문서와 함께 만든다. 여기서 커밋하지 않는다.

---

### Task 3: 점수 경로에 감점을 두지 않는 결정을 기록한다

**Files:**
- Modify: `services/investor_trend_5day_service.py` (`get_investor_trend_5day_for_ticker` 독스트링)

TODO 항목의 마지막 체크박스는 「표식을 남긴다면 `_grade_from_score` 로 흘러가는 경로에서 그 값에 상한이나 감점을 둘지 **검토**」다. 검토 결과는 **두지 않는다**이며 근거가 셋이다.

1. `reference_only` 는 값이 덜 정확하다는 뜻이 아니다. 기본 참조인 pykrx 는 KRX 공식 자료이고, `missing_csv` 는 우리 CSV 수집이 그 종목을 담지 못했다는 뜻이다. 정확한 값에 벌을 주게 된다.
2. 감점을 넣으려면 `engine/screener_scoring_helpers.py` 의 `_score_supply_core` 를 고쳐야 한다. 그 파일이 매기는 점수는 등급 결정으로 바로 이어지므로, 관측 자료 없이 계수를 정하면 근거 없는 왜곡이 된다.
3. 표식을 남기는 것 자체가 이 항목이 요구한 완화책이다. 실제로 `reference_only` 가 얼마나 자주 붙는지 운영에서 관측한 뒤에 감점 여부를 정하는 것이 순서다.

- [ ] **Step 1: 독스트링에 결정을 적는다**

`get_investor_trend_5day_for_ticker` 독스트링 끝에 문단 하나를 더한다.

```
    quality.reference_only 는 CSV 대응값이 없어 참조 단독으로 채운 값이라는 표식이다.
    이 표식에 점수 감점이나 상한을 두지 않는다. 기본 참조인 pykrx 는 KRX 공식 자료라
    표식이 붙었다는 사실만으로 값이 덜 정확하다고 볼 근거가 없고, 감점을 넣으려면
    등급으로 바로 이어지는 engine/screener_scoring_helpers.py 의 계수를 관측 자료
    없이 정해야 하기 때문이다. 이 표식이 실제로 얼마나 붙는지 관측한 뒤에 정한다.
```

- [ ] **Step 2: 정적 검증을 돌린다**

Run: `source venv/bin/activate && pytest`
Expected: PASS. 실패가 남으면 고치고 다시 돌린다.

---

## Self-Review

**1. Spec coverage** — TODO 항목의 체크박스 여섯 개를 모두 덮는다.

| 체크박스 | 담당 |
|---|---|
| 참조 페이로드 유효성 기준을 정함 | Task 1 |
| 유효하지 않은 참조는 `references` 에 넣지 않음 | Task 2 Step 4 |
| 버린 사실을 `quality` 에 남김 | Task 2 Step 3·4 (`discarded_references`) |
| 퇴화한 참조로 CSV 가 덮이지 않는지 회귀 검사 | Task 2 Step 1 의 첫 테스트 |
| 참조 단독 값에 표식을 남길지 정함 | Task 2 (`reference_only`, 남긴다) |
| 점수 경로에 상한이나 감점을 둘지 검토 | Task 3 (두지 않는다, 근거 셋) |

**2. Placeholder scan** — 모든 단계에 실제 코드와 실행 명령이 들어 있다.

**3. Type consistency** — `_reference_reject_reason` 의 반환형 `str | None` 이 Task 2 의 `discarded_references.append(f"{source}:{reason}")` 와 맞는다. `_attach_selection_metadata` 의 새 매개변수 두 개는 기본값이 있어 기존 호출 세 곳이 그대로 동작한다.

**범위 밖으로 두는 것**

- `_get_reference_trend_cached` 의 SQLite 캐시 경로에는 판정을 넣지 않는다. 그 경로도 결국 `_resolve_best_payload` 를 거치므로 이번 판정 한 자리로 함께 막힌다. 캐시에 담긴 값 자체를 검사하는 일은 `[FLOW-013]` 의 범위다.
- TODO 항목이 확신도 4 로 함께 적어 둔 `ticker` 경로 관찰은 이번 사이클에서 고치지 않는다. `[FLOW-011]` 이 만든 것이 아니고 지금 도달할 수 없는 경로라고 항목이 이미 적고 있다.
