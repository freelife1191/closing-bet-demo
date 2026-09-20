# 수집기 통합·수급 조회 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** INFRA-030과 FLOW-014를 연속 완료하고 개인 수급 표시와 과거 스크리닝의 대기 시간을 검증한다.

**Architecture:** 실사용 KRX 계약을 기존 패키지에 통합하고 공개 import를 유지한다. 개인 수급은
nullable 값으로 서비스·캐시·화면까지 전달한다. 과거 스크리닝의 수급 단계만 최대4개씩 실행하며
동일 참조 키 공유와 60초 실패 캐시를 사용한다.

**Tech Stack:** 기존 Python/pandas/pykrx/SQLite, concurrent.futures, React/Next.js, pytest/Vitest.

**Spec:** [수집기·수급 설계](../specs/2026-09-21-collector-supply-design.md)

## Global Constraints

- 범위는 INFRA-030과 FLOW-014, 공유 검토 T3. 다른 항목을 끼워 넣거나 완료 처리하지 않는다.
- 대량 참조 조회 최대4개, 실패 캐시60초/4096개, 프로세스 메모리만 사용한다.
- 첫 max_stocks행을 먼저 확정하며 가격 부족으로 빈자리가 나도 범위 밖 후보로 채우지 않는다.
- 기존 외국인·기관 점수, 날짜 정책, 순위, 정상 CSV의 외부 조회0회 계약을 보존한다.
- 개인 값은 실제0과 None을 구분한다. 기존 CSV 수집 스키마와 원본 저장 자료를 바꾸지 않는다.
- 원본3500/5501/live/.env/data에 접근하지 않고 새 의존성을 추가하지 않는다.
- 소스 편집은 develop의 지정 파일만, 실행은 비밀 없는 소유 scratch에서만 한다.
- 사용자 root package.json을 스테이징·이동·삭제하지 않는다. 기존 해시를 기록해 종료 시 대조한다.
- 테스트·import·컴파일·서버 기동은 부모가 격리 실행한다. 보조 에이전트는 소스 편집/읽기만 허용한다.
- UltraQA는 Codex App 대응, 브라우저는 ego-browser. OMX 런타임 상태를 활성화하거나 조작하지 않는다.
- 문서 설계 방향은 이전 사용자 「승인」, 문서 승인 근거는 직후 「연관된 라운드들 쭉 이어서 진행」 요청이다.
- 이 문서는 실행 전 검토용이다. 구현 계획 검토와 실행 방식 확인 전 제품 코드를 수정하지 않는다.

## Review Focus

1. 모듈 이동으로 BASE_DIR가 한 단계 바뀌거나 공개 경로와 하위 경로가 서로 다른 캐시를 쓰는 경우: Task1.
2. 문자열/NaN/inf/일부 날짜만 있는 개인 수급이 거짓0으로 변하는 경우: Task2.
3. clear 직전 성공한 요청이 SQLite를 늦게 저장하거나 owner 예외로 waiter가 영원히 남는 경우: Task3.
4. cutoff 안의 가격 부족과 중복 ticker 때문에 후보 보충·소비 단계 재조회가 일어나는 경우: Task4.
5. 페이지 새로고침 없이 상세 모달을 닫고 다시 열어 정상→자료 없음→복구를 볼 때 이전 숫자가 남는 경우: Task5.

## 준비와 실행 경계

기준은 문서 전용 커밋 b95ea7c이며 제품 기준은 b4a0ae5와 같다. 실행 직전에 git 상태와
대상 파일 SHA를 기록한다. 관련 없는 변경이 추가되면 그 파일을 덮지 않고 소유 범위를 확인한다.
기존 `docs/dev-cycle/evidence/quota-ticker-20260921/`의 격리 실행기/수명 관리 코드를
읽어 새 `collector-supply-20260921` namespace에 필요한 부분만 적용한다.
이전 scratch·PID·브라우저 Space를 재사용하지 않는다.

실행 때 생성할 증거 경로는 `docs/dev-cycle/evidence/collector-supply-20260921/`이다.
scratch는 git archive로 제품만 구성하고 실제 .env/data를 복사하지 않는다.
기존 venv는 의존성 읽기 전용으로 연결하고 frontend 의존성은 수정이 원본에 전파되지 않도록 복제한다.
whitelist 환경, dotenv 비활성화, 원본 쓰기 및 시크릿/자료 읽기 차단, 외부 통신 차단을 먼저 확인한다.
실행기는 임의 명령을 원본 cwd에서 재시도하지 않고 실패를 기록한다.

모든 아래 실행 명령의 cwd는 scratch다. frontend 명령은 scratch/frontend다.
소유 실행기에서 stdout/stderr·종료 코드·소스 SHA를 보존한다.

```text
pytest -q
frontend: npm exec -- vitest run
frontend: npm run type-check
frontend: npm run lint
frontend: npm run build
```

baseline을 새로 확보하고 실패가 있으면 제품 결함/환경 문제를 구분한다. 문서만 작성하는
현재 단계에서 이 명령을 실행하지 않는다.

## Task 1: KRX 실행 계약을 보존하는 패키지 통합

**Files:** Modify `engine/collectors/krx.py`, `engine/collectors/krx_data_mixin.py`,
`engine/collectors/krx_local_data_mixin.py`; Create `engine/collectors/__init__.py`;
Delete `engine/collectors.py` after parity; Test `tests/engine/test_collectors_refactor.py`,
`tests/engine/test_krx_local_cache_helpers_refactor.py`,
`tests/engine/test_collectors_unified_supply_service_refactor.py`,
`tests/engine/test_krx_data_mixin_refactor.py`, `tests/engine/test_naver_collector_refactor.py`,
`tests/engine/test_news_collector_refactor.py`.
Create `tests/engine/test_collectors_package_contract.py` for public import identity.

**Interfaces:** `from engine.collectors import KRXCollector, NaverFinanceCollector, EnhancedNewsCollector` 유지.
KRX preserves `async get_supply_data(self, code, target_date=None)` and existing public methods.
Naver's `engine.collectors.krx.KRXCollector(config=None)` and private supply-cache consumers remain callable.
기존 공개 생성자는 config를 받으며 통합 생성자는 `config=None`도 받아 Naver 내부 호출을 유지한다.
`_get_data_dir()`는 전달된 config.DATA_DIR를 루트 기준으로 해석한다. 모듈형 고정 data 경로를
그대로 선택하지 않는다. 기존 공급자 API를 새로 조사하거나 교체하지 않는다.

- [ ] 격리 baseline 전에 legacy KRX 메서드·시그니처·캐시 namespace와 모듈형 전용 호출자를
  `collector-contracts.md`에 대조한다. 기존 실사용 결과를 유지하며 모듈형 helper API는 실제 호출자가 필요한 경우 유지한다.
- [ ] Add this identity test and run it to prove current failure:

```python
def test_public_and_submodule_share_krx_class():
    from engine.collectors import KRXCollector
    from engine.collectors.krx import KRXCollector as SubmoduleKRX
    assert KRXCollector is SubmoduleKRX
```

- [ ] Run `pytest -q tests/engine/test_collectors_package_contract.py` (RED identity mismatch).
- [ ] Port legacy KRX methods into corresponding existing mixins/class; do not select modular behavior merely
  because it is newer. Top gainers goes into krx_data_mixin, local price/chart/supply and their caches into
  krx_local_data_mixin, class ownership/name/date state into krx.py. Remove shadowed methods after porting.
  Resolve BASE_DIR from actual module depth to the same repo root; preserve configured DATA_DIR semantics.
- [ ] Replace the file/module shim with this explicit package surface after implementation is present:

```python
from engine.collectors.krx import KRXCollector
from engine.collectors.naver import NaverFinanceCollector
from engine.collectors.news import EnhancedNewsCollector

__all__ = ["KRXCollector", "NaverFinanceCollector", "EnhancedNewsCollector"]
```

- [ ] Retarget test monkeypatches to the module owning the copied global lookup. Keep assertions, synthetic
  provider inputs, historical target dates and expected cache reuse counts unchanged. Add relative and absolute
  DATA_DIR cases and shared cache visibility through both imports. Run the six existing suites above plus new
  contract suite. Confirm no production code imports a removed implementation or relies on package-global test seams.
  패치 위치는 메서드 이동에 따라 `engine.collectors.krx_local_data_mixin` 또는 `krx`로 명시한다.
  Naver는 `engine.collectors.naver_pykrx_mixin`, 상세 서비스는 기존 서비스 모듈 binding을 패치한다.
- [ ] Record Task1 diff/review checkpoint. Commit only after the combined tier review/static gate below,
  per dev-cycle; do not create a premature completion archive.

## Task 2: 개인 수급 nullable 계약과 캐시 호환

**Files:** Modify `engine/models.py`, `engine/collectors/krx_local_data_mixin.py`,
`engine/collectors/naver_pykrx_mixin.py`, `engine/toss_collector_metric_parsers.py`,
`services/investor_trend_5day_service.py`, `services/kr_market_stock_detail_service.py`;
Test `tests/services/test_investor_trend_5day_service.py`,
`tests/services/test_kr_market_stock_detail_service_refactor.py`,
`tests/engine/test_toss_collector_parsers_refactor.py`, collector suites from Task1.

**Interfaces:** `SupplyData.retail_buy_5d: Optional[int] = None`;
normalized 5day payload and detail `investorTrend.individual` are integer or None.
Foreign/institution fields and score inputs retain existing types and rules.
Extend `_normalize_external_trend_payload(payload, *, source, from_cache: bool = False)`.
Fresh provider paths validate dates/amounts with from_cache=False; SQLite decode explicitly passes
from_cache=True and requires individual_schema==1 for personal availability. Memory receives normalized data.

- [ ] Add normalization regression using a complete 5day payload. Personal day detail key is
  `netIndividualsBuyVolume`; normalized details in this service carry existing monetary units despite the key name.

```python
import pytest
from services.investor_trend_5day_service import _normalize_external_trend_payload

@pytest.mark.parametrize("personal", [0, -500, 500, None])
def test_normalized_personal_value_is_not_fabricated(personal):
    dates = ["2026-09-18", "2026-09-17", "2026-09-16", "2026-09-15", "2026-09-14"]
    details = [{"date": day, "netForeignerBuyVolume": 10, "netInstitutionBuyVolume": 20,
                "netIndividualsBuyVolume": personal} for day in dates]
    payload = {"foreign": 50, "institution": 100, "individual": None if personal is None else personal * 5,
               "details": details, "latest_date": "2026-09-18", "days": 5, "individual_schema": 1}
    result = _normalize_external_trend_payload(payload, source="pykrx")
    assert result["individual"] == (None if personal is None else personal * 5)
```

- [ ] Run the new cases (RED current normalization drops personal). Add missing column, one bad day,
  bool, numeric string, NaN/inf and shorter-than-five cases; accepted numeric strings follow current source parser
  numeric conversion, bool/nonfinite/missing become None. Use complete explicit dates in provider-parser tests;
  reject personal availability when dates are absent, duplicate or outside the selected five trading dates.
- [ ] Implement at source boundaries: current CSV produces None; pykrx sums its selected five valid personal
  monetary values; Toss validates five raw dated personal-volume and close rows before multiplying and summing.
  Do not change foreign/institution conversion. Normalized cache stores monetary personal details and sum,
  so re-normalizing cache does not multiply prices again.
- [ ] Add a version marker (`individual_schema: 1`) to new reference/collector personal cache payloads.
  Producer normalization sets it only after validation. Legacy cache decode without this marker forces personal
  to None but retains foreign/institution. Never infer availability from an old nonzero personal total.
  The marker must survive memory/SQLite round trips. No CSV collection schema change or original data migration.
  Add separate unmarked fresh-provider and unmarked cached-payload cases: valid fresh dates can produce a
  personal value and marker; identical legacy cache input with from_cache=True must yield personal None.
  Normalized details retain the five date strings for validation after a round trip. Explicit from_cache use
  is required at SQLite decode, and collector supply-cache decoder independently checks the same marker.
  Stock-detail 완성 payload의 15분 메모리/SQLite 캐시도 포함한다. 새 `investorTrend`에는
  `individual_schema: 1`을 함께 보관하고, 캐시 hit decode에서 marker 없는 구형 객체의 personal만
  None으로 정규화한다. 다른 재무/외국인/기관 필드는 보존하고 캐시 미스로 바꾸어 외부 재조회를
  추가하지 않는다. 새로 만든 응답의 실제0은 marker와 함께 roundtrip해0으로 유지한다.
  상세 서비스 테스트에서 legacy 완성 snapshot의0→None, 새 snapshot의0→0을 각각 확인한다.
  `_normalize_stock_detail_payload`의 복사본에서 개인 필드만 변환하고, 현재 deepcopy로 바로
  반환하는 memory-hit도 이 함수를 거친다. 새 상세 응답 생성부가 marker를 전달하도록 한다.
- [ ] Propagate None through SupplyData, KRX CSV/error/empty fallback, Naver initial and cached result,
  stock-detail defaults and response mapping. No `int(None)` and no `.get("individual") or 0`.
  Tests assert an empty upstream response differs from a valid zero-filled personal column.
- [ ] Run all listed Task2 suites plus Task1 collector suites. Ensure scorer results remain equal while
  personal availability intentionally changes. Record changed behavior separately from structural parity.

## Task 3: 참조 요청 공유·실패 TTL·clear 경합

**Files:** Modify `services/investor_trend_5day_service.py` only;
Create `tests/services/test_investor_trend_reference_concurrency.py`;
Modify `tests/services/test_investor_trend_5day_service.py` existing immediate-miss test.

**Interfaces:** Existing `_get_reference_trend_cached(*, data_dir, source, ticker, target_datetime)` and
`clear_investor_trend_5day_memory_cache()` remain unchanged. No new caller flag needed for failure TTL.

- [ ] Add a synthetic monotonic clock and monkeypatch `_fetch_pykrx_reference_trend` to count None results.
  Actual direct call regression:

```python
def test_failed_reference_retries_after_sixty_seconds(monkeypatch, tmp_path):
    import services.investor_trend_5day_service as service
    clock = [100.0]
    calls = []
    service.clear_investor_trend_5day_memory_cache()
    monkeypatch.setattr(service.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(service, "_fetch_pykrx_reference_trend", lambda **kw: calls.append(kw) or None)
    kwargs = dict(data_dir=str(tmp_path), source="pykrx", ticker="005930", target_datetime="2026-09-18")
    assert service._get_reference_trend_cached(**kwargs) is None
    clock[0] = 159.99
    assert service._get_reference_trend_cached(**kwargs) is None
    assert len(calls) == 1
    clock[0] = 160.0
    assert service._get_reference_trend_cached(**kwargs) is None
    assert len(calls) == 2
```

- [ ] Run the new test RED, separating absent planned `time` import from behavioral TTL failure.
  Use Events/barriers for same-key owner/waiter, different data_dir/provider/date, exception and clear tests;
  no scheduling assumptions based only on sleep. On clear, pause owner before publish then verify both
  SQLite save spy and memory cache receive no result from that old owner.
- [ ] Add monotonic failure OrderedDict and in-flight Futures keyed by `(generation, data_dir, source,
  normalized_ticker, target_key)`. Cache key without generation includes data_dir. Network runs outside the lock.
  Owner always settles its Future in finally/error handling; waiters receive detached payload copies so
  one consumer cannot mutate another's nested details. Catch ordinary provider failures, log and return None.
- [ ] Serialize generation check, memory update and successful SQLite publish against clear under existing
  reference lock. Never call network or wait on a Future while holding that lock. clear advances generation,
  clears memory maps and detaches old in-flight registry; existing waiters still hold their own Future.
  Failure TTL starts after fetch finishes. Trim to4096; do not persist failure records to SQLite.
- [ ] Adapt `test_reference_cache_does_not_pin_miss_result` to prove retry after60seconds, documenting the
  intentional contract change. Add successful cache/SQLite reuse and clear-during-failure tests.
  Run `pytest -q tests/services/test_investor_trend_reference_concurrency.py tests/services/test_investor_trend_5day_service.py`.

## Task 4: 과거 스크리닝의 수급 단계만 4개씩 실행

**Files:** Modify `engine/screener.py`, `services/investor_trend_5day_service.py`;
Create `tests/engine/test_screener_supply_batch.py`;
Test existing `tests/engine/test_screener_supply_unified_service_refactor.py`,
`tests/engine/test_screener_vcp_gate_refactor.py`, `tests/engine/test_screener_runtime_helpers_refactor.py`.

**Interfaces:** Add service `get_investor_trends_5day_for_tickers(*, tickers: list[str], data_dir: str,
target_datetime: datetime | pd.Timestamp | str | None) -> dict[str, dict[str, Any] | None]`.
Caller passes a chunk of at most4 eligible historical candidates. Service rejects >4 rather than making an
unbounded queue. It builds trend map once in caller thread, then submits `_resolve_best_payload` per distinct
key using its read-only CSV payload. Existing single-ticker API stays unchanged.
스크리너 내부 준비값은 `tuple[Dict, pd.DataFrame, VCPResult]`이며
`_prepare_stock_analysis(self, stock: Dict) -> tuple[Dict, pd.DataFrame, VCPResult] | None`,
`_finish_stock_analysis(self, prepared: tuple[Dict, pd.DataFrame, VCPResult], supply_result: Dict) -> Dict`다.

- [ ] First test 4 missing-CSV keys with a barrier provider and assert all4 enter before release; original
  sequential path cannot satisfy this. Add duplicate ticker with one physical query and two preserved candidate
  results, valid CSV with zero external calls, mixed CSV/reference and a None result consumed without re-query.
- [ ] Add run_screening cutoff regression: first3 candidates include one with19 price rows, fourth has20;
  max_stocks3 must never query fourth. Verify VCP false still gets supply just as before. Verify latest-date
  normal path never creates the new executor and preserves Toss-first behavior.
  Also test max_stocks0 and negative values: both produce no analyzed candidates as before; do not use
  pandas head(negative), which would incorrectly include almost the whole universe.
- [ ] Split existing `_analyze_stock` into `_prepare_stock_analysis(stock)` (price eligibility and VCP result)
  and `_finish_stock_analysis(prepared, supply_result)` (unchanged volume/score/result building). Keep
  `_analyze_stock(stock)` as a wrapper using the original single supply path for existing callers.
  In historical run_screening, take first max_stocks candidates before preparing chunks. Preserve current
  exception handling per candidate and skip behavior. Do not introduce an is_vcp prefilter.
- [ ] Call the batch service with eligible tickers and score the returned values using the existing
  `score_supply_from_toss_trend`; None uses the same existing zero-score dictionary without another fetch.
  Consume prepared candidates in original order. Do not store per-run result maps on long-lived screener state.
  Service deduplicates only network keys, not output candidates. `ThreadPoolExecutor(max_workers=4)` lives in
  service chunk scope and is joined on exit; future errors are observed. Global shutdown or original PIDs are forbidden.
  핵심 batch 서비스는 다음 형태로 기존 resolver만 재사용한다. 초과4 검사는 정규화/중복제거 전에 한다.

```python
def get_investor_trends_5day_for_tickers(*, tickers, data_dir, target_datetime):
    if len(tickers) > 4:
        raise ValueError("At most four candidates are allowed")
    directory = _normalize_data_dir(data_dir)
    trend_map = _get_or_build_trend_map(
        data_dir=directory, filename=_TREND_FILENAME, target_datetime=target_datetime,
    )
    keys = list(dict.fromkeys(filter(None, (normalize_ticker(ticker) for ticker in tickers))))
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            key: pool.submit(
                _resolve_best_payload, data_dir=directory, csv_payload=trend_map.get(key),
                ticker=key, target_datetime=target_datetime, verify_with_references=True,
            ) for key in keys
        }
        return {key: future.result() for key, future in futures.items()}
```

  `normalize_ticker`는 기존 `engine.ticker_utils`에서 가져온다. 실제 코드에는 위 인터페이스의
  타입 힌트를 적용하고 스크리너에서 유효하지 않은 key를 None 결과로 소비한다.
  서비스 참조 캐시 함수도 같은 정규화를 사용하여 batch와 단일 호출의 키를 맞춘다.
- [ ] Run new/old screener and service suites. Add fixed-data before/after complete result equality test.
  Counter must distinguish public service calls from actual provider fetch calls.
- [ ] Performance harness in owned evidence measures600 eligible candidates, each provider sleeping50ms,
  three sequential and three batch runs with fresh isolated data_dir/cache reset every run. Require equal
  outputs, no extra fetches, maximum concurrent fetches4, batch median <=50% sequential median. Save all six
  timings. Each individual command has a60second guard; report fixture timing rather than real market speed.

## Task 5: 실제0·자료 없음 표시와 통합 검수

**Files:** Modify `frontend/src/app/dashboard/kr/closing-bet/page.tsx`;
Modify `frontend/src/app/dashboard/kr/closing-bet/page.regression-jongga-022.test.tsx`;
Create `docs/dev-cycle/qa/INFRA-030.md`, `docs/dev-cycle/qa/FLOW-014.md`,
`docs/dev-cycle/qa/batch-collector-supply-2026-09-21.md` during implementation.

**Interfaces:** Detail type `investorTrend.individual: number | null`; missing legacy API field maps to null.
Other fields, existing definitive `investorTrend5Day` foreign/institution preference and labels remain unchanged.

- [ ] Read frontend AGENTS and Next bundle `01-app/01-getting-started/06-fetching-data.md` before source edits.
  Use `vercel-react-best-practices` if editing the detail mapping useMemo; no new cache framework or dependencies.
- [ ] Extend existing real page/modal fixture tests with null,0,positive,negative. Scope assertions to the
  personal row. Example display decision to test and implement inline:

```tsx
const personal = detail.investorTrend.individual;
const personalLabel = personal === null
  ? '자료 없음'
  : personal === 0 ? '0' : `${personal > 0 ? '+' : ''}${formatMarketAmount(personal, '-')}`;
```

- [ ] Run the new null/zero cases RED, remove `individual || 0`, guard nullable comparisons, and run GREEN.
  Add missing-field response and same-page modal close/reopen from positive→null→negative, asserting old text
  disappears and unrelated institutional row remains intact. The current modal fetches on mount/code change;
  do not add a refresh button, polling or a new modal refetch prop. Reuse existing fixture setup, no new global mocks.
- [ ] Run full pytest/Vitest/typecheck/lint/build in scratch. Perform ponytail, code-review and T3 deep review
  against frozen source hashes, repair findings and rerun affected checks. Keep initial failures and reviews.
- [ ] Build required UltraQA matrix with the following rows before runtime execution:
  Q1 package/public identity and historical KRX data; Q2 signed/zero/missing personal API values;
  Q3 legacy reference/collector/complete-detail cache and SQLite roundtrip; Q4 TTL/same-key/clear race; Q5 cutoff and mixed CSV batch;
  Q6 six-run performance; Q7 browser0/positive/negative/missing; Q8 browser same-screen recovery;
  Q9 Next errors/compilation and final cleanup. All required, no skipped row counts as PASS.
- [ ] Commit reviewed product code, plan and QA matrix as first implementation commit; keep both backlog entries.
  Stage allowlisted files and run `git diff --cached --check` as a standalone successful command before commit.
- [ ] Run UltraQA App-adapted in a new scratch/browser namespace using real changed services and real UI.
  Gateway/Next/fixture use separately checked owned loopback ports (proposed57940/57941/57942 only if free).
  Fixture replaces network providers/authentication, not expected product computations. Restrict allowed routes;
  no original account, LLM, settings write, trades, collection or deletes. Record exact substitution boundaries.
  Use ego-browser skill current API, inspect screenshots directly, compare screen and API personal values.
  Read Next get_errors/get_compilation_issues after navigation. Capture failure and recovery without full reload:
  close modal, switch only owned fixture provider state and invalidate only its synthetic detail cache, then
  reopen the same stock. This exercises real mount fetch; do not claim same-mounted-modal auto-refresh.
- [ ] Freeze final source SHA, preserve logs/exit codes/images/request audit. Close owned browser task once,
  verify PID/cwd identity before terminating only owned processes, confirm ports closed, remove owned scratch,
  retain original venv and package hash. Required failures stop completion (max5cycles/samefailure3).
- [ ] Independently verify both IDs' criteria. Update their QA reports, archive each with nonduplicated file
  counts and actual implementation commit; remove only passed IDs from backlog. Commit archive/evidence.
  Final report names actual QA scope, counts, known HTTP deadline limitation and remaining10items only if both passed.

## 자체 검토와 실행 방식

설계의 import/nullable/과거날짜/cutoff/clear/성능/실측/정리 요구를 Tasks1~5에 배정했다.
캐시 Task3와 병렬 Task4는 같은 서비스 파일을 수정하므로 순차 실행한다. Task2의 개인 계약을
Task5가 소비한다. 인터페이스와 fixture가 강하게 연결되어 있어 부모가 직접 구현하는
Native 실행 후 독립 리뷰를 권장한다. 파일별 병렬 구현으로 공유 서비스 충돌을 만들지 않는다.
본 문서 검토 후 선택한 방식으로 구현·리뷰·QA·마감을 연속 진행한다.

## 독립 계획 검토 기록

2026-09-21 native critic 초기 REJECT 사유를 반영했다.
날짜 없는 개인 값 예시와 fresh/cache 판별 모순은 명시 날짜 및 from_cache 경계로 수정했다.
상세 완성 payload 캐시의 구형0 우회는 marker-aware decode와 별도 회귀 검사에 포함했다.
존재하지 않는 동일 모달 자동 재조회 시나리오는 실제 닫기/재열기 경로로 정정했다.
최종 재검토는 `OKAY`. 이는 계획 판정이며 제품 구현·테스트·실측 통과를 뜻하지 않는다.
