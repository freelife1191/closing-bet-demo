# [FLOW-029]·[JONGGA-043] 수급 참조 캐시의 끝 날짜·거부 값과 Naver 상세 캐시의 영문자 코드 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** pykrx 참조가 기준일이 아닌 날로 끝나는 5일 값이나 거부될 값을 기준일 키로 영구 저장하지 않게 하고, 영문자로 끝나는 종목코드의 Naver 상세 결과도 캐시되게 한다.

**Architecture:** `_fetch_pykrx_reference_trend` 가 표의 마지막 날을 조회 끝 날짜와 대조해 다르면 None 을 돌려준다. `_get_reference_trend_cached` 는 `_reference_reject_reason` 에 걸리는 결과를 실패와 같이 60초 실패 캐시로만 다루고 메모리·SQLite 에 두지 않는다. 참조 SQLite 서명에 `v2` 를 넣어 예전 항목을 읽지 않는다. Naver `_normalize_stock_detail_payload` 는 숫자 여섯 자리 검사 대신 `normalize_ticker` 를 쓴다.

**Tech Stack:** Python 3.11, pandas, pytest

**Spec:** 대화 설계(bounded, spec 문서 없음). 승인 범위와 근거는 `docs/dev-cycle/TODO.md` 의 `[FLOW-029]`·`[JONGGA-043]` 「설계 승인」 줄(2026-09-25 23:26)이 정본이다.

## Global Constraints

- 위험 경로 `services/investor_trend_5day_service.py` 를 고치므로 묶음 전체가 T3 다. 리뷰 순서는 `/ponytail-review` → `closing-bet-reviewer` → `/review`. 인증·시크릿과 무관해 보안 리뷰는 넣지 않는다.
- 테스트는 `tmp_path` 와 메모리 프레임만 쓴다. 원본 `data/`·`.env`·네트워크·LLM 에 닿지 않는다. 실행은 `KRX_ID= KRX_PW= venv/bin/python -m pytest -q -p no:cacheprovider`.
- 실패 캐시 TTL 은 기존 `_REFERENCE_FAILURE_TTL`(60초)을 그대로 쓴다. 새 상수를 만들지 않는다.
- 거부된 결과도 그 호출과 같은 키를 기다리던 호출에는 그대로 돌려준다. 그래서 `_resolve_best_payload` 의 `discarded_references` 사유(`pykrx:zero_total` 등)는 조회한 호출에 남는다. 60초 안의 후속 호출은 실패 캐시의 None 을 받아 사유를 남기지 않는다(계획 검토 Minor-1). 기준일 실행에서는 `get_pykrx_trend_5day` 가 먼저 조회하므로 뒤이은 통합 서비스 호출의 `quality` 에는 pykrx 사유가 없다. `quality` 로 갈리는 판정이 없어 결과는 같다.
- 코드 주석·로그는 저장소 관례(한국어, `[FLOW-029]`·`[JONGGA-043]` 태그)를 따르고, `return` 앞에 로그를 둔다(`closing-bet-python`).

## Review Focus

1. 기준일 자료가 아직 없는 pykrx 표(마지막 날이 기준일 전날): 5일 값으로 쓰지도 저장하지도 않고 60초 뒤 다시 묻는다 (Task 1 `test_pykrx_reference_that_ends_before_the_target_is_rejected`, 기존 `test_reference_cache_does_not_pin_miss_result` 의 실패 경로).
2. 전부 0 이거나 NaN 인 날이 있는 참조: 조회한 호출의 사유는 남고(60초 안의 후속 호출에는 남지 않는다) SQLite 에 행이 생기지 않으며 60초 안에는 다시 묻지 않는다 (Task 1 `test_a_rejected_reference_is_not_cached_and_is_asked_again`, 기존 `test_toss_is_tried_when_the_pykrx_reference_is_discarded`).
3. 배포 전에 v1 서명으로 저장된 참조: 읽지 않고 새로 조회한 값이 같은 키를 덮어쓴다 (Task 1 `test_a_reference_saved_under_the_v1_signature_is_not_read`).
4. 정상 참조의 재사용: 메모리를 비워도 SQLite 에서 다시 읽는다 (기존 `test_get_investor_trend_5day_for_ticker_reuses_reference_sqlite_after_memory_clear`).
5. `00680K` 상세 조회: 두 번째 조회가 스크랩하지 않고 코드가 `00680K` 로 남는다. 숫자 코드 `5930` 은 종전대로 `005930` 이다 (Task 2 매개변수화 테스트).

---

### Task 1: 참조 캐시의 끝 날짜 대조·거부 값 비저장·v2 서명

**Files:**
- Modify: `services/investor_trend_5day_service.py` (`_reference_sqlite_context`, `_fetch_pykrx_reference_trend`, `_get_reference_trend_cached`)
- Test: `tests/services/test_investor_trend_5day_service.py`

**Interfaces:**
- Consumes: 없음
- Produces: 시그니처 변화 없음. `_fetch_pykrx_reference_trend` 가 끝 날짜 불일치에 None 을 돌려주고, `_get_reference_trend_cached` 가 거부 값을 캐시하지 않는다.

- [ ] **Step 1: 실패하는 테스트 셋을 파일 끝에 추가한다**

```python
def _complete_reference(value: int) -> dict:
    return {
        "foreign": value * 5, "institution": value * 5, "latest_date": "2026-02-24", "source": "pykrx",
        "details": [{"netForeignerBuyVolume": value, "netInstitutionBuyVolume": value}] * 5,
    }


def test_pykrx_reference_that_ends_before_the_target_is_rejected(monkeypatch):
    """[FLOW-029] 기준일 자료가 아직 없어 전날로 끝나는 표는 기준일의 5일 값이 아니다."""
    days = pd.to_datetime(["2026-02-17", "2026-02-18", "2026-02-19", "2026-02-20", "2026-02-23"])
    frame = pd.DataFrame({"기관합계": [10.0] * 5, "외국인합계": [1.0] * 5}, index=days)
    monkeypatch.setattr(pykrx_stock, "get_market_trading_value_by_date", lambda *a, **k: frame)

    assert trend_service._fetch_pykrx_reference_trend(ticker="005930", target_datetime="2026-02-24") is None
    assert trend_service._fetch_pykrx_reference_trend(ticker="005930", target_datetime="2026-02-23")["foreign"] == 5


def test_a_rejected_reference_is_not_cached_and_is_asked_again(monkeypatch, tmp_path):
    """[FLOW-029] 거부될 참조는 메모리·SQLite 에 두지 않고 실패처럼 60초 뒤 다시 묻는다."""
    trend_service.clear_investor_trend_5day_memory_cache()
    clock = [100.0]
    monkeypatch.setattr(trend_service.time, "monotonic", lambda: clock[0])
    replies = [_complete_reference(0), _complete_reference(300)]
    calls = []
    monkeypatch.setattr(trend_service, "_fetch_pykrx_reference_trend", lambda **_k: calls.append(1) or replies[len(calls) - 1])
    kwargs = {"data_dir": str(tmp_path), "source": "pykrx", "ticker": "005930", "target_datetime": "2026-02-24"}

    first = trend_service._get_reference_trend_cached(**kwargs)
    sqlite_key, signature = trend_service._reference_sqlite_context(
        data_dir=str(tmp_path), source="pykrx", ticker="005930", target_datetime="2026-02-24",
    )

    assert trend_service._reference_reject_reason(first) == "zero_total"  # 이 호출은 사유를 남길 수 있다
    assert sqlite_payload_cache.load_json_payload_from_sqlite(filepath=sqlite_key, signature=signature)[0] is False
    assert trend_service._get_reference_trend_cached(**kwargs) is None  # 60초 안에는 다시 묻지 않는다
    clock[0] += 60.0
    assert trend_service._get_reference_trend_cached(**kwargs)["foreign"] == 1_500
    assert len(calls) == 2
    trend_service.clear_investor_trend_5day_memory_cache()


def test_a_reference_saved_under_the_v1_signature_is_not_read(monkeypatch, tmp_path):
    """[FLOW-029] v1 참조 캐시에는 NaN 을 0 으로 저장한 값과 끝 날짜가 어긋난 값이 있을 수 있어 읽지 않는다."""
    trend_service.clear_investor_trend_5day_memory_cache()
    sqlite_key, _ = trend_service._reference_sqlite_context(
        data_dir=str(tmp_path), source="pykrx", ticker="005930", target_datetime="2026-02-24",
    )
    v1_signature = (trend_service._stable_token_to_int("20260224"), trend_service._stable_token_to_int("pykrx"))
    sqlite_payload_cache.save_json_payload_to_sqlite(filepath=sqlite_key, signature=v1_signature, payload=_complete_reference(999))
    monkeypatch.setattr(trend_service, "_fetch_pykrx_reference_trend", lambda **_k: _complete_reference(300))

    result = trend_service._get_reference_trend_cached(
        data_dir=str(tmp_path), source="pykrx", ticker="005930", target_datetime="2026-02-24",
    )

    assert result["foreign"] == 1_500
    trend_service.clear_investor_trend_5day_memory_cache()
```

- [ ] **Step 2: 실패를 확인한다**

Run: `KRX_ID= KRX_PW= venv/bin/python -m pytest -q -p no:cacheprovider tests/services/test_investor_trend_5day_service.py -k "ends_before_the_target or rejected_reference_is_not_cached or v1_signature"`
Expected: 3 failed. 첫째는 None 대신 dict, 둘째는 SQLite 에 행이 있어 `True`, 셋째는 v1 행의 4_995 를 읽음.

- [ ] **Step 3: 구현한다**

`_reference_sqlite_context` 의 서명:

```python
    # [FLOW-029] v1 에는 NaN 을 0 으로 저장한 값(930525be 이전)과 끝 날짜가 기준일이 아닌 값이 남아 있을 수 있다
    signature = (_stable_token_to_int(token), _stable_token_to_int(f"{source}:v2"))
```

`_fetch_pykrx_reference_trend` 의 `if len(trend_df) < 5: return None` 바로 뒤:

```python
    last_day = pd.Timestamp(trend_df.index[-1]).normalize()
    if last_day != pd.Timestamp(end_dt).normalize():
        # [FLOW-029] 끝 날짜의 자료가 아직 없으면 전날까지의 5일이다. 끝 날짜 키로 저장되지 않게 버린다
        logger.debug("pykrx reference for %s ends on %s, not %s", ticker, last_day.date(), end_dt.date())
        return None
```

`_get_reference_trend_cached` 의 `finally` 안 분기 조건:

```python
            if generation == _REFERENCE_GENERATION:
                # [FLOW-029] 거부될 값도 실패로 다룬다. 저장하면 같은 키로 다시 묻지 않는다
                if result is not None and _reference_reject_reason(result) is None:
```

- [ ] **Step 4: 통과를 확인한다**

Run: Step 2 와 같은 명령, 이어서 `tests/services/test_investor_trend_5day_service.py tests/engine/test_collectors_refactor.py` 전체.
Expected: 3 passed, 두 파일 전체 통과.

### Task 2: Naver 상세 캐시의 영문자 코드

**Files:**
- Modify: `engine/collectors/naver.py` (`_normalize_stock_detail_payload`, import)
- Test: `tests/engine/test_naver_collector_refactor.py` (`test_get_stock_detail_info_reuses_sqlite_snapshot_after_memory_clear`)

**Interfaces:**
- Consumes: `engine.ticker_utils.normalize_ticker(value) -> str` (유효하지 않으면 빈 문자열)
- Produces: 시그니처 변화 없음

- [ ] **Step 1: 기존 테스트를 두 코드로 매개변수화한다**

```python
@pytest.mark.parametrize(("first_code", "second_code", "expected"), [("5930", "005930", "005930"), ("00680K", "00680K", "00680K")])
def test_get_stock_detail_info_reuses_sqlite_snapshot_after_memory_clear(monkeypatch, tmp_path, first_code, second_code, expected):
    """[JONGGA-043] 영문자로 끝나는 코드도 상세 결과를 캐시해 두 번째 조회가 스크랩하지 않는다."""
```

본문의 `get_stock_detail_info("5930")`·`("005930")` 을 `first_code`·`second_code` 로, `== "005930"` 단언 둘을 `== expected` 로 바꾸고 파일 머리에 `import pytest` 를 더한다.

- [ ] **Step 2: 실패를 확인한다**

Run: `KRX_ID= KRX_PW= venv/bin/python -m pytest -q -p no:cacheprovider tests/engine/test_naver_collector_refactor.py -k reuses_sqlite_snapshot`
Expected: `00680K` 경우만 실패. 가짜 `_request` 의 AssertionError 는 `get_stock_detail_info` 의 `except Exception` 이 삼켜 None 이 되므로 `assert second is not None` 에서 멈춘다(계획 검토 Nit-1).

- [ ] **Step 3: 구현한다**

```python
from engine.ticker_utils import normalize_ticker
...
        code_value = normalize_ticker(payload.get("code"))
        if not code_value:
            logger.debug("Naver detail payload has no valid code: %r", payload.get("code"))
            return None
```

- [ ] **Step 4: 통과를 확인한다**

Run: Step 2 와 같은 명령, 이어서 파일 전체.
Expected: 2 passed, 파일 전체 통과.

## 알려진 한계(계획 검토 반영)

- Minor-2: 끝 날짜가 휴장일이면 pykrx 참조를 늘 거부하고 60초마다 다시 묻는다. 관리자가 휴장일 기준일을 직접 주거나, `_resolve_pykrx_latest_market_date` 가 지수 조회에 실패해 평일 `now` 로 물러나 그날 SQLite 에 저장된 경우다. 과거 휴장일의 「직전 거래일까지 5일」은 틀린 값이 아니므로 결과를 버리는 쪽의 보수적 동작이다. 최신 창은 Toss, 기준일 실행은 CSV 경로로 넘어간다. 「끝 날짜가 오늘 이후일 때만 거부」로 좁히는 것은 승인 범위를 바꾸므로 하지 않고 아카이브에 한계로 적는다.
- Minor-3: 늘 거부되는 참조(전부 0 인 거래정지 종목, 하루가 빈 Toss 참조)는 하루 한 번이 아니라 요청마다 60초 간격으로 다시 조회한다. 승인된 절충이며 QA 문서의 비용 항목에 적는다.
- Info-1: `get_stock_detail_info` 의 유일한 호출자 `fetch_stock_detail_payload` 가 Naver 결과를 자기 15분 슬롯 캐시에 저장하므로 수정 전에도 「모달을 열 때마다」가 아니라 15분 슬롯마다 한 번 스크랩했다. 수정 뒤에는 Naver 60분 슬롯까지 재사용된다. 브라우저 QA 는 모달이 정상으로 그려지는지를 보고, 캐시 재사용은 CLI 하네스로 Naver 캐시 행을 확인한다.

### 마감(이 계획 밖 절차)

리뷰 셋 → pytest·vitest 전체 → 첫 커밋(TODO 유지) → QA(`docs/dev-cycle/qa/FLOW-029.md`, CLI 하네스 + 브라우저) → 아카이브. `dev-cycle` 스킬을 따른다.
