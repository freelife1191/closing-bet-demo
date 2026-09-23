# [VCP-040] VCP AI 판정 폴백 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** VCP 수집 병합과 실패 재분석이 Gemini 가 비었을 때 유효한 GPT/Perplexity 추천을 CSV 판정으로 쓰게 한다.

**Architecture:** 판정 하나를 고르는 규칙을 `app/routes/kr_market_vcp_signal_helpers.py` 의 `_extract_vcp_ai_recommendation` 한 곳에 둔다. 필드는 `VCP_AI_RECOMMENDATION_FIELDS` 순서(gemini → gpt → perplexity)로 보고, 기준은 기존 `_is_valid_ai_recommendation` 이다. `scripts/init_data.py` 의 수집 병합은 자체 분기를 지우고 이 함수를 함수 안에서 import 해 부른다. 반환 형식 `(is_valid, action, confidence, reason)` 은 그대로 둔다.

**Tech Stack:** Python 3.11, pandas, pytest

**Spec:** 별도 spec 없음(bounded). 승인 범위는 `docs/dev-cycle/TODO.md` 의 `[VCP-040]` 「설계 승인」 줄, 원인 확정은 `docs/dev-cycle/qa/VCP-040.md`.

## Global Constraints

- 전부 실패하면 `(False, "N/A", None, "분석 실패")`. 확신도는 0 이 아니라 None 이다(`[JONGGA-008]` 계약).
- `_apply_vcp_reanalysis_updates` 의 `updated_recommendations` 에는 Gemini 추천이 유효한 종목만 넣는다. `update_vcp_ai_cache_files` 가 이 값을 캐시의 `gemini_recommendation` 칸에 덮어쓰기 때문이다. 다른 프로바이더 결과는 호출부가 함께 넘기는 `ai_results` 로 캐시의 제 칸에 들어간다.
- 재분석은 유효한 기존 CSV 판정을 실패한 재시도로 덮지 않는다(수집이 GPT 판정을 쓰기 시작하면서 생기는 회귀를 막는다).
- CSV 열을 추가하지 않는다. 기존 `data/` 행은 복구하지 않는다. `VCP_AI_PROVIDERS` 순서 정렬은 하지 않는다.
- `init_data.py` 는 `app` 패키지를 모듈 상단에서 import 하지 않는다(함수 안 import).
- pytest 는 `venv/bin/python -m pytest` 로 돌린다.

---

### Task 1: 선택 규칙과 재분석 경로

**Files:**
- Modify: `app/routes/kr_market_vcp_signal_helpers.py:94-156`
- Test: `tests/app/test_kr_market_vcp_signal_helpers_refactor.py`

**Interfaces:**
- Produces: `_extract_vcp_ai_recommendation(ai_results: Any, ticker: str) -> Tuple[bool, str, Optional[int], str]` (시그니처 불변, 폴백 추가)

- [ ] **Step 1: 실패하는 테스트 작성** (파일 끝에 추가)

```python
# [VCP-040] Gemini 가 비면 유효한 다른 프로바이더 추천을 판정으로 쓴다.
_GPT_OK = {"action": "hold", "confidence": "72", "reason": "수급은 긍정적이나 돌파 확인이 필요합니다."}
_GEMINI_OK = {"action": "BUY", "confidence": 68, "reason": "수축 비율과 동반 순매수가 확인됩니다."}


def test_extract_falls_back_to_gpt_when_gemini_is_missing():
    ai_results = {"033530": {"gemini_recommendation": None, "gpt_recommendation": _GPT_OK}}
    assert _extract_vcp_ai_recommendation(ai_results, "033530") == (True, "HOLD", 72, _GPT_OK["reason"])


def test_extract_prefers_gemini_when_both_are_valid():
    ai_results = {"033530": {"gemini_recommendation": _GEMINI_OK, "gpt_recommendation": _GPT_OK}}
    assert _extract_vcp_ai_recommendation(ai_results, "033530")[1:3] == ("BUY", 68)


def test_extract_fails_with_missing_confidence_when_every_provider_failed():
    failed = {"action": "N/A", "confidence": 0, "reason": "분석 실패"}
    ai_results = {"033530": {"gemini_recommendation": None, "gpt_recommendation": failed, "perplexity_recommendation": None}}
    assert _extract_vcp_ai_recommendation(ai_results, "033530") == (False, "N/A", None, "분석 실패")


def test_reanalysis_counts_gpt_fallback_but_keeps_it_out_of_the_gemini_cache_slot():
    signals_df = pd.DataFrame([{"ticker": "033530", "ai_action": "N/A", "ai_confidence": 0, "ai_reason": "분석 실패"}])
    ai_results = {"033530": {"gemini_recommendation": None, "gpt_recommendation": _GPT_OK}}

    updated, still_failed, recommendations = _apply_vcp_reanalysis_updates(
        signals_df, [(0, {"ticker": "033530"})], ai_results
    )

    assert (updated, still_failed) == (1, 0)
    assert signals_df.at[0, "ai_action"] == "HOLD"
    # update_vcp_ai_cache_files 가 이 dict 를 gemini_recommendation 칸에 덮어쓴다
    assert recommendations == {}
```

회귀 방지 테스트도 함께 둔다. 수정 뒤 수집은 CSV 에 GPT 판정을 쓰지만 캐시 `gemini_recommendation` 은 비어 있으므로, 다음 재분석이 그 행을 `is_gemini_only` 로 잡아 Gemini 만 다시 부른다(`services/kr_market_vcp_reanalysis_service.py:650-668`). 그 호출이 또 실패해도 유효한 기존 판정을 「분석 실패」로 덮지 않아야 한다.

```python
def test_reanalysis_keeps_an_existing_valid_verdict_when_the_retry_fails():
    signals_df = pd.DataFrame([{"ticker": "033530", "ai_action": "HOLD", "ai_confidence": 72, "ai_reason": _GPT_OK["reason"]}])
    row = signals_df.iloc[0].to_dict()

    updated, still_failed, recommendations = _apply_vcp_reanalysis_updates(
        signals_df, [(0, row)], {"033530": {"gemini_recommendation": None, "gpt_recommendation": None}}
    )

    assert (updated, still_failed, recommendations) == (0, 1, {})
    assert (signals_df.at[0, "ai_action"], signals_df.at[0, "ai_confidence"]) == ("HOLD", 72)
```

필요하면 파일 머리 import 에 `_apply_vcp_reanalysis_updates`, `_extract_vcp_ai_recommendation`, `pandas as pd` 를 더한다.

- [ ] **Step 2: 실패 확인**

Run: `venv/bin/python -m pytest tests/app/test_kr_market_vcp_signal_helpers_refactor.py -k "extract or gemini_cache" -q`
Expected: 폴백 두 건과 재분석 한 건 FAIL(Gemini 만 봄), 우선순위 한 건은 PASS

- [ ] **Step 3: 구현**

`_extract_vcp_ai_recommendation` 의 Gemini 한 필드 조회를 다음으로 바꾸고 docstring 첫 줄을 「Gemini → GPT → Perplexity 순서로 유효한 첫 추천」으로 고친다.

```python
    recommendation = next(
        (
            ai_res.get(field)
            for field in VCP_AI_RECOMMENDATION_FIELDS
            if _is_valid_ai_recommendation(ai_res.get(field))
        ),
        None,
    )
    if recommendation is None:
        return False, "N/A", None, "분석 실패"

    return (
        True,
        _normalize_text(recommendation.get("action")).upper(),
        safe_confidence(recommendation.get("confidence")),
        _normalize_text(recommendation.get("reason")),
    )
```

`_apply_vcp_reanalysis_updates` 의 `if is_valid:` 블록은 카운트와 CSV 갱신은 그대로 두고, `updated_recommendations[ticker] = ...` 만 Gemini 가 유효할 때로 좁힌다.

```python
        if is_valid:
            ai_res = ai_results.get(ticker) if isinstance(ai_results, dict) else None
            # update_vcp_ai_cache_files 가 이 값을 gemini_recommendation 칸에 덮어쓴다.
            # 다른 프로바이더 결과는 ai_results 로 제 칸에 들어간다([VCP-040]).
            if isinstance(ai_res, dict) and _is_valid_ai_recommendation(ai_res.get("gemini_recommendation")):
                updated_recommendations[ticker] = {...기존 dict...}
            updated_count += 1
```

(critic REVISE 반영) 가드는 자동 모드에만 둔다. 강제 Gemini 모드는 「처리했지만 실패한 행은 실패로 기록한다」는 `[VCP-039]` 계약(`tests/services/test_vcp_reanalysis_cancel_refactor.py:63`)을 유지한다. `_apply_vcp_reanalysis_updates` 에 키워드 인자 `keep_valid_verdicts: bool = False` 를 더하고, 서비스(`services/kr_market_vcp_reanalysis_service.py:711`)가 `keep_valid_verdicts=normalized_force_provider is None` 으로 넘긴다. 루프 맨 앞(행에 쓰기 전)에 가드를 둔다. `row` 는 재분석 서비스가 넘기는 행 dict 이며 `ai_action`·`ai_reason` 을 담는다(`_VCP_REANALYSIS_SIGNAL_USECOLS`). 위 회귀 테스트는 `keep_valid_verdicts=True` 로 부르고, 같은 입력을 기본값으로 부르면 실패 문구로 덮는다는 검사를 하나 더 둔다.

```python
        if keep_valid_verdicts and not is_valid and not _is_vcp_ai_analysis_failed(row):
            # 이미 유효한 판정을 실패한 재시도로 덮지 않는다([VCP-040])
            still_failed_count += 1
            continue
```

- [ ] **Step 3b: 화면 라벨(critic REVISE 반영)** — `_build_vcp_gemini_recommendation` 은 CSV 판정으로 `gemini_recommendation` 을 만든다. 이제 CSV 판정이 GPT 일 수 있으므로, `_merge_ai_data_into_vcp_signals` 에서 캐시 gemini 칸이 유효하지 않고 다른 추천 하나라도 유효하면 `signal["gemini_recommendation"] = None` 으로 둔다. 캐시가 없거나 모든 칸이 무효이면 CSV 판정을 그대로 둔다(판정 출처를 알 수 없으므로 종전 동작). 테스트 두 건: (가) CSV 판정 HOLD + 캐시 gemini None·gpt 유효 → 병합 뒤 gemini None, gpt 는 캐시 값 (나) 캐시 gemini·gpt 모두 None → CSV 판정 유지. 화면(`frontend/src/app/dashboard/kr/vcp/page.tsx:1779-1782`)은 GPT·Gemini 를 다른 열로 그리므로 프론트 수정은 없다

- [ ] **Step 4: 통과 확인**

Run: `venv/bin/python -m pytest tests/app tests/services -q`
Expected: 전부 PASS(기존 `test_kr_market_helpers_contract.py`, `test_ai_confidence_missing_value.py` 포함)

### Task 2: 수집 병합

**Files:**
- Modify: `scripts/init_data.py:1556-1576`
- Test: `tests/scripts/test_init_data_vcp_scheduler.py`

**Interfaces:**
- Consumes: Task 1 의 `_extract_vcp_ai_recommendation`

- [ ] **Step 1: 실패하는 테스트 작성** (`test_vcp_no_provider_result_does_not_log_save_success` 뒤, 같은 더미 사용)

```python
def test_create_signals_log_uses_gpt_verdict_when_gemini_is_missing(monkeypatch, tmp_path):
    """[VCP-040] Gemini 가 비고 GPT 가 성공하면 CSV 에 GPT 판정이 남는다."""
    (tmp_path / "data").mkdir()
    monkeypatch.setattr(init_data, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr("engine.screener.SmartMoneyScreener", _DummyScreener)
    monkeypatch.setattr("engine.market_gate.MarketGate", _DummyMarketGate)
    results = {
        "005930": {"gemini_recommendation": None,
                   "gpt_recommendation": {"action": "HOLD", "confidence": "72", "reason": "돌파 확인이 필요합니다."}},
    }

    class Analyzer:
        async def analyze_batch(self, stocks):
            return results

    class News:
        def __init__(self, *args): pass
        async def get_stock_news(self, *args, **kwargs): return []

    monkeypatch.setattr("engine.vcp_ai_analyzer.get_vcp_analyzer", Analyzer)
    monkeypatch.setattr("engine.collectors.EnhancedNewsCollector", News)
    monkeypatch.setattr("pykrx.stock.get_index_ohlcv", lambda *args: pd.DataFrame())

    assert init_data.create_signals_log("2026-09-21", run_ai=True) is True
    row = pd.read_csv(tmp_path / "data" / "signals_log.csv", dtype={"ticker": str}, keep_default_na=False).iloc[0]
    assert (row["ai_action"], int(row["ai_confidence"]), row["ai_reason"]) == ("HOLD", 72, "돌파 확인이 필요합니다.")


def test_create_signals_log_leaves_confidence_blank_when_every_provider_failed(monkeypatch, tmp_path):
    """[VCP-040] 전부 실패하면 확신도는 0 이 아니라 결측이다."""
    ...위와 같은 준비, results = {"005930": {"gemini_recommendation": None, "gpt_recommendation": None}}...
    assert init_data.create_signals_log("2026-09-21", run_ai=True) is True
    row = pd.read_csv(tmp_path / "data" / "signals_log.csv", dtype={"ticker": str}).iloc[0]
    assert row["ai_reason"] == "분석 실패"
    assert pd.isna(row["ai_confidence"])
```

두 테스트의 공통 준비는 작은 헬퍼 `_patch_vcp_collect(monkeypatch, tmp_path, results)` 하나로 묶는다.

- [ ] **Step 2: 실패 확인**

Run: `venv/bin/python -m pytest tests/scripts/test_init_data_vcp_scheduler.py -k "gpt_verdict or every_provider" -q`
Expected: 두 건 FAIL(`N/A`/0)

- [ ] **Step 3: 구현** — 1556-1576 의 블록을 다음으로 바꾼다.

```python
        # AI 판정을 CSV 행에 병합한다. 선택 규칙은 실패 재분석과 같은 함수 하나다([VCP-040])
        if run_ai and signals and 'ai_results' in locals() and ai_results:
            try:
                from app.routes.kr_market_vcp_signal_helpers import _extract_vcp_ai_recommendation

                for signal in signals:
                    if signal['ticker'] in ai_results:
                        _, signal['ai_action'], signal['ai_confidence'], signal['ai_reason'] = (
                            _extract_vcp_ai_recommendation(ai_results, signal['ticker'])
                        )
            except Exception as e:
                log(f"AI 결과 병합 중 오류: {e}", "WARNING")
```

- [ ] **Step 4: 통과 확인**

Run: `venv/bin/python -m pytest tests/scripts tests/app -q`
Expected: 전부 PASS

### Task 3: 리뷰·전체 검증·QA 행렬

- [ ] `venv/bin/python -m pytest -q` 전체 통과, 명령과 종료 코드 기록
- [ ] T3 리뷰: `/ponytail-review`(별도 에이전트) → `closing-bet-reviewer`(`name` 지정) → `/review`(critic 경로). 지적 반영은 TODO 체크에 기록
- [ ] `docs/dev-cycle/qa/VCP-040.md` 에 QA 행렬 추가: 격리 사본에서 가짜 분석기(원인 확정 실행 1 의 실제 응답에서 gemini 만 None)로 `create_signals_log` 와 재분석 라우트를 돌려 CSV 가 GPT 판정을 담는지, 전부 실패 시 확신도가 비는지, 캐시 `gemini_recommendation` 칸에 GPT 값이 들어가지 않는지 본다. 사본에서 backend·frontend 를 대체 포트로 띄워 agent-browser 로 VCP 화면을 열고 GPT 열에 GPT 판정이, Gemini 열에는 판정이 없음을 스크린샷으로 남긴다. LLM 호출 없음
- [ ] 허용 경로만 스테이징하고 `git diff --cached --check && git commit` (첫 커밋, TODO 유지)
