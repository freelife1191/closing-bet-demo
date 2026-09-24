# [VCP-045] Z.ai 비활성화 플래그 만료 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `zai_disabled_reason` 이 워커 수명 동안 남지 않고, 다른 세션 차단 플래그와 같은 10분 뒤에 풀리게 한다.

**Architecture:** `[VCP-041]` 의 `VCPMultiAIAnalyzer._expire_session_blocks` 가 이미 세 종류의 플래그를 한 시계로 관리한다. 감시 조건과 해제 대상에 `zai_disabled_reason` 하나를 더한다. 새 상수·시계·함수는 만들지 않는다.

**Tech Stack:** Python 3.11, pytest

**Spec:** 대화 설계(2026-09-24 10:43 승인, `docs/dev-cycle/TODO.md` `[VCP-045]` 설계 승인 줄)

## Global Constraints

- TTL 은 `LLM_THRESHOLD.SESSION_BLOCK_TTL_SECONDS`(600초)를 그대로 쓴다. 별도 TTL 을 두지 않는다.
- 해제 값은 `None` 이다. `_analyze_with_zai` 는 `str(... or "").strip()` 으로 읽으므로 `None` 이면 활성으로 본다.
- 실제 LLM 호출은 하지 않는다. 테스트와 QA 는 가짜 클라이언트와 가짜 시계만 쓴다.
- 운영 반영은 gunicorn 워커를 모두 재기동해야 한다(장 중 금지).

## Review Focus

- 해제 뒤 echo 가 다시 나오면 `_analyze_with_zai` 가 플래그를 다시 켜고, 다음 만료 판정이 새 시각을 기록해야 한다(10분마다 최대 체인 길이 × 3회 × `ANALYSIS_LLM_CONCURRENCY` 호출로 제한됨. 기본 동시성 1, 체인 최대 2모델이면 6회).
- Z.ai 플래그만 켜진 상태에서도 시계가 기록되어야 한다. 종전 `blocked` 판정이 이 플래그를 보지 않으면 영원히 `since=None` 으로 남는다. 이것이 핵심 회귀이므로 테스트가 이 경우를 직접 확인한다.
- `zai_disabled_reason` 속성이 없는 분석기(`object.__new__` 로 만든 테스트 객체)에서도 `getattr` 기본값으로 동작해야 한다.

---

### Task 1: `_expire_session_blocks` 에 Z.ai 플래그 추가

**Files:**
- Modify: `engine/vcp_ai_analyzer.py` (`_expire_session_blocks`, 624-661 무렵)
- Test: `tests/engine/test_vcp_ai_analyzer_refactor.py`

**Interfaces:**
- Consumes: `VCPMultiAIAnalyzer._expire_session_blocks()`, `self._session_blocks_since`
- Produces: 없음(동작만 바뀜)

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def test_expire_session_blocks_clears_zai_disabled_reason(monkeypatch):
    # Z.ai 메타 응답 비활성화도 다른 플래그처럼 10분 뒤 풀려야 한다 [VCP-045].
    clock = {"now": 0.0}
    monkeypatch.setattr("engine.vcp_ai_analyzer.time.monotonic", lambda: clock["now"])
    analyzer = object.__new__(VCPMultiAIAnalyzer)
    analyzer.zai_disabled_reason = "prompt-echo responses"

    analyzer._expire_session_blocks()
    assert analyzer._session_blocks_since == 0.0
    assert analyzer.zai_disabled_reason == "prompt-echo responses"

    clock["now"] = 600.0
    analyzer._expire_session_blocks()
    assert analyzer.zai_disabled_reason is None
    assert analyzer._session_blocks_since is None
```

- [ ] **Step 2: 실패 확인**

Run: `venv/bin/python -m pytest tests/engine/test_vcp_ai_analyzer_refactor.py -k zai_disabled_reason -q`
Expected: FAIL (`_session_blocks_since` 가 `None`)

기존 `test_analyze_stock_expires_gpt_and_perplexity_blocks` 에도 `analyzer.zai_disabled_reason = "prompt-echo responses"` 와 `assert analyzer.zai_disabled_reason is None` 을 더해 `analyze_stock` 진입 가드 경로를 함께 확인한다(계획 검토 보류 2).

- [ ] **Step 3: 최소 구현**

`blocked` 판정의 이름 튜플에 `"zai_disabled_reason"` 을 더하고, 해제 로그 형식에 `zai=%s` 와 `getattr(self, "zai_disabled_reason", None)` 을 더하고, 해제부에 `self.zai_disabled_reason = None` 을 더한다. docstring 의 「세 종류」 같은 표현이 있으면 맞춘다.

- [ ] **Step 4: 통과 확인**

Run: `venv/bin/python -m pytest tests/engine/test_vcp_ai_analyzer_refactor.py -q`
Expected: 전부 PASS

- [ ] **Step 5: 첫 커밋은 dev-cycle [3] 5번(정적 검증과 QA 행렬 뒤)에서 한다**

## 계획 검토 반영

- critic 판정: ACCEPT-WITH-RESERVATIONS. 보류 1(비용 상한에 동시성 누락)은 Review Focus 문구에 반영, 보류 2(`analyze_stock` 경로 확인)는 기존 테스트에 두 줄 추가로 반영. 미반영 없음
