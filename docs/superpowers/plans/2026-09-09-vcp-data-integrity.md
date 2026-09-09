# VCP 데이터 정합성 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** VCP 날짜별 AI 판정, 프로바이더 필드, 1일 수급, LLM 복구 폴백이 검증된 원본만 사용하고 정보 부족은 HOLD로 남긴다.

**Architecture:** 세 AI 추천 field의 유일한 정본은 기존 결과 뼈대 모듈 engine.vcp_ai_orchestration_helpers에 공개 tuple로 둔다. Payload는 유효한 단일 signal_date의 날짜 파일만 읽고, generic legacy는 현재 날짜와 legacy payload의 signal_date가 모두 맞을 때만 빈 field를 보강한다. 1일 수급은 screener에서 CSV와 두 prompt 입력 경로까지 optional value로 전달하며 rule fallback은 결측을 숫자로 바꾸지 않는다.

**Tech Stack:** Python, pandas, Flask test client, pytest, Next.js/React, Vitest, agent-browser.

**Spec:** docs/dev-cycle/TODO.md의 VCP-020, VCP-021, VCP-023, VCP-024 및 2026-09-09 사용자 승인.

## Global Constraints

- 범위는 VCP-020/021/023/024만이다. VCP-022, AI 공급자 정책 변경, UI 기능 확대, 신규 의존성은 포함하지 않는다.
- VCP_AI_RECOMMENDATION_FIELDS의 Gemini→GPT→Perplexity 순서와 완전 입력의 action/confidence 계산은 보존한다.
- None, 빈 문자열, NaN, inf, 숫자가 아닌 문자열은 실제 0과 다르다. 결측을 0·1.0·중립 문장으로 만들지 않는다.
- 과거 signals_log.csv에 1일 열이 없어도 조회·재분석 입력은 실패하지 않아야 한다.
- 이 라운드는 VCP 판정 위험 경로 T3이다. 원본 data, 실제 .env, 실행 중인 3500/5501, live service를 사용하지 않는다.
- QA의 LLM·재분석·수집·매수/매도·삭제·발송은 fake로 막는다. Browser는 isolated fixture의 GET과 과거 탭 선택만 허용한다.
- 모든 필수 QA가 통과하기 전에는 TODO 완료 처리와 archive를 만들지 않는다.

---

## File Structure

| 파일 | 책임 |
| --- | --- |
| engine/vcp_ai_orchestration_helpers.py | 세 recommendation field 정본과 결과 뼈대 |
| services/kr_market_vcp_payload_service.py | 날짜 검증 및 date-specific/legacy merge |
| app/routes/kr_market_vcp_signal_helpers.py | AI map을 API signal에 merge |
| services/kr_market_vcp_cache_update_service.py, services/kr_market_vcp_reanalysis_service.py | cache write/read와 second provider key |
| engine/signal_tracker_ai_helpers.py | batch 결과의 provider priority |
| engine/screener_result_builders.py, scripts/init_data.py | 1일 수급의 producer와 CSV persistence |
| engine/vcp_ai_analyzer_helpers.py | evidence-only rule fallback |
| tests/engine, tests/services, tests/app, tests/scripts | 날짜/CSV/fallback regression contract |

### Task 1: 프로바이더 추천 field 정본 통합 (VCP-021)

**Files:**
- Modify: engine/vcp_ai_orchestration_helpers.py:10-35
- Modify: app/routes/kr_market_vcp_signal_helpers.py:15-30,348-390
- Modify: engine/signal_tracker_ai_helpers.py:10-95
- Modify: services/kr_market_vcp_cache_update_service.py:10-35,90-112
- Modify: services/kr_market_vcp_reanalysis_service.py:16-155
- Modify: scripts/init_data.py:62-68,1721-1740
- Test: tests/engine/test_vcp_ai_orchestration_helpers_refactor.py
- Test: tests/app/test_kr_market_vcp_signal_helpers_refactor.py
- Test: tests/services/test_kr_market_vcp_cache_update_service.py
- Test: tests/services/test_kr_market_vcp_service.py

**Interfaces:**
- Produces VCP_AI_RECOMMENDATION_FIELDS: tuple[str, str, str].
- Consumes existing result shape and resolve_vcp_second_recommendation_key(second_provider: str) -> str.
- Preserves openai/zai/z.ai→GPT and perplexity→Perplexity aliases.

- [ ] **Step 1: 정본 contract의 failing test를 작성한다.**

```
from engine.vcp_ai_orchestration_helpers import VCP_AI_RECOMMENDATION_FIELDS

assert VCP_AI_RECOMMENDATION_FIELDS == (
    "gemini_recommendation",
    "gpt_recommendation",
    "perplexity_recommendation",
)
assert set(result) >= set(VCP_AI_RECOMMENDATION_FIELDS)
assert resolve_vcp_second_recommendation_key("z.ai") == VCP_AI_RECOMMENDATION_FIELDS[1]
```

Existing legacy-merge test는 route private tuple 대신 공개 정본을 import한다. Cache-update fixture에는 GPT를 더해 세 field 모두 저장되는지 확인한다. Cache map test는 ticker filter와 required-key 조기 종료를 세 field fixture에서 유지한다.

- [ ] **Step 2: 현재 구현에서 RED를 확인한다.**

Run:

```
source venv/bin/activate && pytest \
  tests/engine/test_vcp_ai_orchestration_helpers_refactor.py \
  tests/app/test_kr_market_vcp_signal_helpers_refactor.py \
  tests/services/test_kr_market_vcp_cache_update_service.py \
  tests/services/test_kr_market_vcp_service.py -q
```

Expected: 공개 정본 import/contract에서 FAIL. 이미 있던 실패는 baseline으로 따로 기록한다.

- [ ] **Step 3: existing orchestration module에만 정본을 추가하고 소비자를 연결한다.**

```
# engine/vcp_ai_orchestration_helpers.py
VCP_AI_RECOMMENDATION_FIELDS = (
    "gemini_recommendation",
    "gpt_recommendation",
    "perplexity_recommendation",
)

results = {
    "ticker": stock_data.get("ticker", ""),
    "stock_name": stock_name,
    **dict.fromkeys(VCP_AI_RECOMMENDATION_FIELDS),
}
```

Route helper, cache update, reanalysis, signal tracker, init_data는 tuple을 import한다. 각 파일은 provider alias·실행 순서·priority 조립은 유지하고 field 문자열만 정본에서 얻는다. Signal tracker는 provider-name tuple과 zip으로 priority pair를 만들고, reanalysis는 tuple을 구조 분해해 alias map의 value와 GPT default를 만든다. Route의 _AI_RECOMMENDATION_FIELDS는 제거한다.

새 registry나 module은 만들지 않는다. 결과 schema를 이미 소유한 module 하나가 source of truth다.

- [ ] **Step 4: GREEN과 반복 tuple 제거를 확인한다.**

Run:

```
source venv/bin/activate && pytest \
  tests/engine/test_vcp_ai_orchestration_helpers_refactor.py \
  tests/app/test_kr_market_vcp_signal_helpers_refactor.py \
  tests/services/test_kr_market_vcp_cache_update_service.py \
  tests/services/test_kr_market_vcp_service.py -q
rg -n '"(gemini|gpt|perplexity)_recommendation"' \
  app/routes/kr_market_vcp_signal_helpers.py engine/signal_tracker_ai_helpers.py \
  services/kr_market_vcp_cache_update_service.py services/kr_market_vcp_reanalysis_service.py \
  scripts/init_data.py
```

Expected: pytest PASS. 검색에는 alias/individual access만 남고 세 field를 나열한 duplicate tuple은 없다.

- [ ] **Step 5: 정본 통합 commit을 만든다.**

```
git add engine/vcp_ai_orchestration_helpers.py engine/signal_tracker_ai_helpers.py \
  app/routes/kr_market_vcp_signal_helpers.py services/kr_market_vcp_cache_update_service.py \
  services/kr_market_vcp_reanalysis_service.py scripts/init_data.py \
  tests/engine/test_vcp_ai_orchestration_helpers_refactor.py \
  tests/app/test_kr_market_vcp_signal_helpers_refactor.py \
  tests/services/test_kr_market_vcp_cache_update_service.py tests/services/test_kr_market_vcp_service.py
git commit -m "refactor: centralize VCP recommendation fields"
```

### Task 2: 날짜 증명 없는 AI/legacy merge 차단 (VCP-020)

**Files:**
- Modify: services/kr_market_vcp_payload_service.py:260-307
- Test: tests/services/test_kr_market_vcp_payload_service_refactor.py
- Test: tests/app/test_kr_market_data_signals_routes_refactor.py

**Interfaces:**
- Consumes _build_vcp_signals_from_dataframe output; normal date is YYYY-MM-DD.
- Produces same payload structure with only its date-specific recommendation.
- Preserves date-specific recommendation, date-proven same-day legacy 빈 field 보강, deep_copy=False loader 우선과 TypeError fallback.

- [ ] **Step 1: historical/missing/invalid/mixed-date tests를 쓴다.**

```
# Historical file이 없고 generic legacy에는 BUY가 있어도 merge하지 않는다.
assert merged_signal.get("gpt_recommendation") is None
assert loaded_names == ["ai_analysis_results_20260213.json"]

# Same-day이며 legacy payload.signal_date도 같으면 빈 GPT만 보강한다.
assert merged_signal["gpt_recommendation"]["action"] == "HOLD"

# 현재일 legacy는 읽어서 날짜를 검사하되 날짜가 어제/없음/invalid면 merge하지 않는다.
assert merged_signal.get("gpt_recommendation") is None

# signal date가 mixed/missing/invalid이면 date file과 legacy 모두 선택하지 않는다.
assert merged_count == 0
```

Payload test는 injected JSON loader와 merge callback으로 file name/final map을 capture한다. Flask client GET /api/kr/signals?date=2026-02-13 fixture는 과거 row에 최신 GPT/Perplexity verdict가 없는 API contract를 고정한다. 외부 loader는 쓰지 않는다.

- [ ] **Step 2: 무조건 legacy fallback이 RED인지 확인한다.**

Run:

```
source venv/bin/activate && pytest \
  tests/services/test_kr_market_vcp_payload_service_refactor.py \
  tests/app/test_kr_market_data_signals_routes_refactor.py -q
```

Expected: historical query가 kr_ai_analysis.json을 read 또는 merge해서 FAIL.

- [ ] **Step 3: payload service에 작은 날짜 proof helper를 구현한다.**

```
def _resolve_single_signal_date(signals: list[dict[str, Any]]) -> str | None:
    dates = {str(item.get("signal_date", "")) for item in signals if isinstance(item, dict)}
    if len(dates) != 1:
        return None
    try:
        return datetime.strptime(dates.pop(), "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        return None

def _payload_matches_signal_date(payload: Any, signal_date: str) -> bool:
    return isinstance(payload, dict) and payload.get("signal_date") == signal_date
```

_merge_ai_into_vcp_signals은 single date가 없으면 empty map을 merge하고 종료한다. Valid date이면 ai_analysis_results_YYYYMMDD.json만 먼저 읽는다. 과거 조회에서는 File이 없거나 signals가 비어도 generic으로 대체하지 않는다. 현재일 조회에서는 generic의 명시 signal_date가 정확히 같은 경우에만 날짜 파일 부재를 보완할 수 있다. Legacy read와 merge는 다음 양쪽 proof가 있을 때만 실행한다.

```
is_current_signal_date = signal_date == current_time.strftime("%Y-%m-%d")
if is_current_signal_date and _payload_matches_signal_date(legacy_json, signal_date):
    merge_legacy_ai_fields_into_map(ai_data_map, legacy_json)
```

첫 row만 보고 date를 정하지 않고, ai_analysis_results.json을 이 route에 추가하지 않는다.

- [ ] **Step 4: date-specific merge와 route contract를 GREEN으로 만든다.**

Run:

```
source venv/bin/activate && pytest \
  tests/services/test_kr_market_vcp_payload_service_refactor.py \
  tests/app/test_kr_market_data_signals_routes_refactor.py -q
```

Expected: historical/missing/invalid/mixed date는 fail-closed이며 verified same-date date file 및 legacy 보강은 PASS.

- [ ] **Step 5: 날짜 혼입 fix만 commit한다.**

```
git add services/kr_market_vcp_payload_service.py \
  tests/services/test_kr_market_vcp_payload_service_refactor.py \
  tests/app/test_kr_market_data_signals_routes_refactor.py
git commit -m "fix: restrict VCP AI merge to proven signal dates"
```

### Task 3: 1일 수급을 producer에서 CSV·prompt까지 보존 (VCP-024)

**Files:**
- Modify: engine/screener_result_builders.py:13-60
- Modify: scripts/init_data.py:62-68,1623-1638,1721-1740,1862-1884,1906-1930
- Test: tests/engine/test_screener_result_builders_refactor.py
- Test: tests/scripts/test_init_data_vcp_scheduler.py
- Test: tests/engine/test_signal_tracker_ai_helpers_refactor.py
- Test: tests/app/test_kr_market_vcp_signal_helpers_refactor.py
- Test: tests/app/test_kr_market_data_signals_routes_refactor.py

**Interfaces:**
- Consumes foreign_net_1d and inst_net_1d, each finite number or absent.
- Produces foreign_1d and inst_1d in CSV; existing AI_PROMPT_NUMERIC_FIELDS forwards finite values to batch and reanalysis prompts.
- Preserves actual zero as 0.0; old CSV omits only missing prompt keys and remains valid.

- [ ] **Step 1: producer-to-prompt failing tests를 쓴다.**

```
signal = build_signal_item(row_with_1d_values, "2026-02-19")
assert signal["foreign_1d"] == 11
assert signal["inst_1d"] == -7

assert init_data.create_signals_log(target_date="2026-02-19", run_ai=False) is True
saved = pd.read_csv(tmp_path / "data" / "signals_log.csv")
assert saved.loc[0, "foreign_1d"] == 11_111_111
assert saved.loc[0, "inst_1d"] == 22_222_222

payload = build_ai_batch_payload(saved)[0]
assert payload["foreign_1d"] == 11_111_111.0
assert payload["inst_1d"] == 22_222_222.0
```

Existing test_create_signals_log_persists_detected_signal dummy screener와 tmp_path를 reuse한다. Source 1d가 absent면 builder가 None/empty cell을 보존하고 batch payload와 _build_vcp_stock_payload가 key를 만들지 않는지 검사한다. Source 0은 key 0.0으로 남는 test를 별도로 둔다. Route loader fixture에 1d columns 없는 old frame을 넣고 injected reanalysis service까지 200으로 도달하는지 확인한다.

- [ ] **Step 2: 새 CSV assertion이 RED인지 확인한다.**

Run:

```
source venv/bin/activate && pytest \
  tests/engine/test_screener_result_builders_refactor.py \
  tests/scripts/test_init_data_vcp_scheduler.py \
  tests/engine/test_signal_tracker_ai_helpers_refactor.py \
  tests/app/test_kr_market_vcp_signal_helpers_refactor.py \
  tests/app/test_kr_market_data_signals_routes_refactor.py -q
```

Expected: create_signals_log output에 두 column이 없어 FAIL.

- [ ] **Step 3: optional-value propagation을 구현한다.**

```
# engine/screener_result_builders.py
"foreign_net_1d": supply_result.get("foreign_1d"),
"inst_net_1d": supply_result.get("inst_1d"),

# build_signal_item
"foreign_1d": getattr(row, "foreign_net_1d", None),
"inst_1d": getattr(row, "inst_net_1d", None),
```

init_data는 safe_optional_float를 import한다. create_signals_log의 signal dict와 kr_ai_signals에서 1d value가 finite일 때만 key를 넣고, missing이면 key를 생략한다. 무신호/exception empty DataFrame schema에는 두 header를 추가한다. 새 CSV missing은 empty cell, actual zero는 0.0이다.

AI_PROMPT_NUMERIC_FIELDS, build_ai_batch_payload, _build_vcp_stock_payload는 이미 finite optional fields를 전달하므로 logic을 복제하지 않는다. old usecols ValueError는 existing load_csv_readonly full-frame fallback으로 처리한다.

- [ ] **Step 4: producer·old CSV·두 prompt path를 GREEN으로 만든다.**

Run:

```
source venv/bin/activate && pytest \
  tests/engine/test_screener_result_builders_refactor.py \
  tests/scripts/test_init_data_vcp_scheduler.py \
  tests/engine/test_signal_tracker_ai_helpers_refactor.py \
  tests/app/test_kr_market_vcp_signal_helpers_refactor.py \
  tests/app/test_kr_market_data_signals_routes_refactor.py -q
```

Expected: isolated CSV에는 real 1d values; missing/zero는 구분; old CSV는 reanalysis service에 도달한다.

- [ ] **Step 5: 1일 수급 전달만 commit한다.**

```
git add engine/screener_result_builders.py scripts/init_data.py \
  tests/engine/test_screener_result_builders_refactor.py \
  tests/scripts/test_init_data_vcp_scheduler.py \
  tests/engine/test_signal_tracker_ai_helpers_refactor.py \
  tests/app/test_kr_market_vcp_signal_helpers_refactor.py \
  tests/app/test_kr_market_data_signals_routes_refactor.py
git commit -m "fix: preserve VCP one-day supply through AI inputs"
```

### Task 4: 결측을 지어내지 않는 rule fallback (VCP-023)

**Files:**
- Modify: engine/vcp_ai_analyzer_helpers.py:518-597
- Test: tests/engine/test_vcp_ai_analyzer_helpers_refactor.py
- Test: tests/engine/test_vcp_ai_analyzer_refactor.py

**Interfaces:**
- Consumes build_vcp_rule_based_recommendation(stock_name: str, stock_data: dict[str, Any]) -> dict[str, Any].
- Produces unchanged action/confidence/reason keys; action is BUY/SELL/HOLD.
- Preserves complete numeric data's existing BUY/HOLD/SELL and confidence formulas.

- [ ] **Step 1: missing/invalid/zero/complete-data tests를 쓴다.**

```
unknown_1d = build_vcp_rule_based_recommendation(
    stock_name="A",
    stock_data={"score": 83, "contraction_ratio": 0.72, "foreign_5d": 100, "inst_5d": 20},
)
assert "1일 수급" not in unknown_1d["reason"]

insufficient = build_vcp_rule_based_recommendation(stock_name="B", stock_data={"foreign_1d": "nan"})
assert insufficient["action"] == "HOLD"
assert "정보가 부족" in insufficient["reason"]
assert all(token not in insufficient["reason"].lower() for token in ("nan", "점수 0.0", "수축비율 1.00"))

actual_zero = build_vcp_rule_based_recommendation(
    stock_name="C",
    stock_data={"score": 69, "contraction_ratio": 0.90, "foreign_5d": 10, "inst_5d": -5,
                "foreign_1d": 0, "inst_1d": 0},
)
assert "1일 수급은 중립입니다" in actual_zero["reason"]
```

Existing complete BUY/HOLD/SELL test remains. Run analyzer fallback tests too so parser callers retain dict schema and never call a live provider.

- [ ] **Step 2: existing defaults make the new tests RED인지 확인한다.**

Run:

```
source venv/bin/activate && pytest \
  tests/engine/test_vcp_ai_analyzer_helpers_refactor.py \
  tests/engine/test_vcp_ai_analyzer_refactor.py -q
```

Expected: missing 1d becomes zero and emits neutral reason; sparse input fabricates score/ratio.

- [ ] **Step 3: evidence-only optional numeric logic을 구현한다.**

```
from engine.pandas_utils_safe import safe_optional_float

score = safe_optional_float(stock_data.get("score"))
contraction_ratio = safe_optional_float(stock_data.get("contraction_ratio"))
foreign_5d = safe_optional_float(stock_data.get("foreign_5d"))
inst_5d = safe_optional_float(stock_data.get("inst_5d"))
foreign_1d = safe_optional_float(stock_data.get("foreign_1d"))
inst_1d = safe_optional_float(stock_data.get("inst_1d"))
flow_5d = foreign_5d + inst_5d if foreign_5d is not None and inst_5d is not None else None
flow_1d = foreign_1d + inst_1d if foreign_1d is not None and inst_1d is not None else None
```

BUY requires real score, contraction_ratio, flow_5d and current threshold. BUY also requires a real flow_1d >= 0; a missing 1-day sum never satisfies that gate. SELL requires actual score <= 62 or both existing flow sums negative. Other cases are HOLD; missing core VCP/5-day evidence adds 정보가 부족 to reason.

Call _describe_vcp_state only with real score+ratio and _describe_flow_state only with a real sum. Never create 1-day phrase if either 1-day component is missing. Sparse HOLD uses conservative fixed confidence; full input retains current confidence formula and wording.

- [ ] **Step 4: T3 fallback tests를 GREEN으로 만든다.**

Run:

```
source venv/bin/activate && pytest \
  tests/engine/test_vcp_ai_analyzer_helpers_refactor.py \
  tests/engine/test_vcp_ai_analyzer_refactor.py -q
```

Expected: complete behavior is unchanged; missing/NaN/inf has no fabricated 0/1.0/neutral fact and insufficient evidence is HOLD.

- [ ] **Step 5: fallback safety commit을 만든다.**

```
git add engine/vcp_ai_analyzer_helpers.py \
  tests/engine/test_vcp_ai_analyzer_helpers_refactor.py \
  tests/engine/test_vcp_ai_analyzer_refactor.py
git commit -m "fix: keep unknown VCP fallback inputs out of verdicts"
```

### Task 5: T3 통합 검증, review, isolated browser QA, 완료 기록

**Files:**
- Modify after every gate passes: docs/dev-cycle/TODO.md, docs/dev-cycle/archive/2026-09.md, docs/dev-cycle/qa/VCP-020.md, docs/dev-cycle/qa/VCP-021.md, docs/dev-cycle/qa/VCP-023.md, docs/dev-cycle/qa/VCP-024.md
- Verify: Tasks 1-4 source and existing VCP frontend regression suites.

**Interfaces:**
- Verifies GET /api/kr/signals?date=<historical-date> never contains another date's verdict.
- Stop condition: targeted/full tests, static checks, review, UltraQA, agent-browser evidence pass and are recorded ID-by-ID.

- [ ] **Step 1: targeted integration과 frontend regression을 실행한다.**

Run:

```
source venv/bin/activate && pytest \
  tests/services/test_kr_market_vcp_payload_service_refactor.py \
  tests/services/test_kr_market_vcp_cache_update_service.py \
  tests/services/test_kr_market_vcp_service.py \
  tests/app/test_kr_market_data_signals_routes_refactor.py \
  tests/app/test_kr_market_vcp_signal_helpers_refactor.py \
  tests/engine/test_vcp_ai_orchestration_helpers_refactor.py \
  tests/engine/test_vcp_ai_analyzer_helpers_refactor.py \
  tests/engine/test_vcp_ai_analyzer_refactor.py \
  tests/engine/test_screener_result_builders_refactor.py \
  tests/engine/test_signal_tracker_ai_helpers_refactor.py \
  tests/scripts/test_init_data_vcp_scheduler.py -q
(cd frontend && npx vitest run src/app/dashboard/kr/vcp/page.regression-vcp-002.test.tsx src/app/dashboard/kr/vcp/page.regression-vcp-010.test.tsx src/app/dashboard/kr/vcp/page.regression-vcp-011.test.tsx src/app/dashboard/kr/vcp/page.regression-jongga-008.test.tsx)
(cd frontend && npm run type-check)
```

Expected: PASS. Failures are diagnosed by date/schema/optional-value contract; expectations are not weakened.

- [ ] **Step 2: ponytail → code-review → review T3 reviews를 실행하고 findings를 반영한다.**

Review focus: no new registry/dependency; self-proven signal date; mixed/invalid fail-closed; generic legacy never substitutes a historical missing date file; current same-date explicit proof permits fallback; old CSV fallback; missing/zero separation; full-data verdict preservation; cache writer/reader/UI share same three fields. Fix findings and rerun Tasks 1-4 suites.

- [ ] **Step 3: UltraQA scenario matrix를 isolated fixture로 실행한다.**

Matrix: historical date with current legacy GPT/Perplexity; same-date verified legacy; missing/invalid legacy date; mixed signal dates; 1d positive/negative/zero/missing/NaN; old CSV missing 1d; complete BUY/HOLD/SELL. Oracles are API field, action/reason fact, CSV/prompt-key presence. LLM/news/collection/trade functions are injected fakes.

- [ ] **Step 4: agent-browser read-only historical flow를 실행한다.**

Temporary data dir contains signals_log.csv, ai_analysis_results_20260213.json, and newer kr_ai_analysis.json. Start local frontend/backend against that dir only; never reuse original 3500/5501 or live URL.

```text
1. Open /dashboard/kr/vcp.
2. Click "과거" and choose fixture date 2026-02-13.
3. Open its row and inspect Gemini/GPT/Perplexity badge and reason.
4. Confirm ticker/date/reason match 2026-02-13 fixture and no newer legacy verdict appears.
5. Record console errors and failed requests.
```

Do not click Refresh VCP, failed-AI reanalysis, buy, chat send, delete, or save. If UI fails, compare isolated API response and Task 2 contract first; do not invent frontend scope.

- [ ] **Step 5: full checks, archive, docs commit을 수행한다.**

Run:

```
source venv/bin/activate && pytest
(cd frontend && npx vitest run)
(cd frontend && npm run type-check)
git diff --check
git status --short
```

Expected: all PASS and no .env, original data, log, lockfile, or dependency diff. Record T3 review/UltraQA/browser evidence by ID in docs/dev-cycle/qa/VCP-020.md, docs/dev-cycle/qa/VCP-021.md, docs/dev-cycle/qa/VCP-023.md, docs/dev-cycle/qa/VCP-024.md. Only then archive the four IDs using archive-format.

```bash
git add docs/dev-cycle/TODO.md docs/dev-cycle/archive/2026-09.md docs/dev-cycle/qa/VCP-020.md, docs/dev-cycle/qa/VCP-021.md, docs/dev-cycle/qa/VCP-023.md, docs/dev-cycle/qa/VCP-024.md
git commit -m "docs: archive completed VCP data integrity work"
```

## Self-Review

- **Spec coverage:** VCP-020 is Task 2; VCP-021 Task 1; VCP-024 Task 3's supply_result → result → signal dict → CSV → batch/reanalysis prompt; VCP-023 Task 4.
- **Safety coverage:** Task 2 tests historical/missing/invalid/mixed dates. Tasks 3-4 separately test actual zero and missing. Task 5 uses isolated fixture and read-only browser actions.
- **Type consistency:** recommendation fields remain tuple[str, str, str] and values dict[str, Any] | None; 1d supply is float | None, CSV number/empty cell, prompt finite float/key absent.
- **Placeholder scan:** Each task names files, contracts, failure oracle, implementation boundary, commands, and expected result.


## 리더 통합 보완
- task별 commit 예시는 독립 실행 시의 제안이다. 이번 승인된 묶음에서는 구현+행렬을 T3 리뷰/정적검증 후 첫 커밋으로 묶고, QA 후 ID별 기록과 월별·일별 archive를 한 번에 커밋한다.
- 상수 그 자체 문자열 동등성 검사를 새로 늘리지 않는다. 실제 세 provider의 orchestration→cache write/read→merge 소비 동작을 회귀 검사한다.
- BUY는 누락된 1일수급을 0으로 보거나 조건을 생략하지 않는다. 여섯 필수 숫자가 실재해야 기존 BUY 조건을 평가한다. SELL은 실제 낮은 score 또는 실재하는 두 음수합으로만 판정하며 점수 부재 때 confidence에 임의점수를 넣지 않는다. 충분하지 않은 근거는 HOLD/정보부족.
- 날짜파일 자체의 명시된 날짜가 요청날짜와 충돌하면 해당 AI도 제외한다. 날짜없음은 날짜지정 filename의 근거로 허용하며 generic은 signal_date가 일치해야 한다.
- 검증 매트릭스 전체 항목별 정상/결측/zero/invalid/날짜/legacy/옛CSV를 준비한다. 브라우저는 실제 Next UI+합성HTTP경계로, 변경한 실제Python함수 결과와 연결하며 전체운영서비스검증으로 표현하지 않는다.
- 각review 15분/전체검증10분/브라우저명령60초, QA5회/동일실패3회 상한.

- legacy 로더뿐 아니라 병합 callback의 잘못된 shape 예외도 격리하여 날짜파일의 유효한 판정을 보존한다. 기존 예외격리 계약의 회귀를 막는다.
