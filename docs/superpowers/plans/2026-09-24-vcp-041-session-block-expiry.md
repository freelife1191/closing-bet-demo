# [VCP-041] VCP 분석기 세션 차단 플래그 시간 만료 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 429·503·쿼터 오류로 켜진 VCP 분석기의 세션 차단 플래그가 워커 수명 내내 남지 않고 10분 뒤 풀리게 한다.

**Architecture:** `VCPMultiAIAnalyzer` 는 프로세스 싱글톤(`get_vcp_analyzer`)이라 차단 플래그가 재기동 전까지 남는다. 모든 호출 경로(수집·signal_tracker·AI 갱신은 `analyze_batch` → `analyze_stock`, 재분석 진행률 경로는 `analyze_stock` 직접)가 지나는 `analyze_stock` 의 시작과 끝(`finally`)에서 `_expire_session_blocks()` 를 부르고, 플래그가 처음 관측된 시각에서 TTL 이 지나면 세 종류를 모두 비운다. 차단을 거는 기존 10여 곳은 건드리지 않는다.

**Tech Stack:** Python 3.11, pytest, 가짜 Gemini 클라이언트(`SimpleNamespace`), `time.monotonic` monkeypatch

**Spec:** 대화 설계(bounded, 2026-09-24 08:54 KST 사용자 승인 「승인, 진행」). 원인 확정 기록은 `docs/dev-cycle/qa/VCP-041.md`, 항목 원문은 `docs/dev-cycle/TODO.md` 의 `[VCP-041]`

## 계획 검토 반영 (critic REVISE, 2026-09-24)

아래 Task 1 의 코드는 원안이다. 구현은 critic 지적을 반영해 다음처럼 바뀌었으며, 실제 코드는 커밋 diff 가 정본이다.

- F1(필수): 시작 가드만 두면 배치의 **마지막 종목**에서 켠 차단은 시각이 기록되지 않아, 다음 날 첫 종목에서야 기록되고 그날 배치 전체가 다시 막힌다. `analyze_stock` 을 `try/finally` 로 감싸 종목이 끝날 때도 `_expire_session_blocks()` 를 부른다(가드 위치는 여전히 `analyze_stock` 한 곳)
- 테스트 1 교체: 손으로 부르던 만료 호출을 빼고 `analyze_stock`(가짜 orchestrate 가 `_analyze_with_gemini` 를 부름)으로 검증한다. `test_gemini_block_from_last_stock_of_batch_expires_before_next_day`(1일차 마지막 종목 차단 → 2일차 첫 종목 호출 1회)와 `test_gemini_block_holds_within_ttl`(599초에는 호출 0회)로 나눴다. 첫 테스트는 원안 코드에서 실패하고 반영 뒤 통과함을 확인했다
- 선택 채택: 제외 집합을 새로 만들지 않고 `.clear()` 로 비운다(진행 중인 호출이 같은 집합을 쥐므로 해제 뒤 받은 429 가 버려지지 않는다). import 별칭은 선례(`engine/phases_news_llm.py:14`)에 맞춰 `LLM_THRESHOLD`
- Step 2 기대 정정: 수정 전 코드에서 새 테스트 3건이 실패한다(`AttributeError` 만이 아니라 `AssertionError` 도 포함). TTL 유지 테스트는 수정 전에도 통과한다(영구 차단이므로)
- 참고(수용): 전역 `time.monotonic` 을 바꾸므로 테스트는 `asyncio.sleep`·`to_thread` 를 가짜로 둔다. GPT 402·Perplexity 401 도 10분마다 한 번 재시도한 뒤 폴백으로 넘어간다(승인 범위 안)

## Global Constraints

- 대상 플래그: `gemini_blocked_models`, `gpt_quota_exhausted`·`gpt_blocked_reason`, `perplexity_quota_exhausted`·`perplexity_blocked_reason`. 설정 기반 `perplexity_disabled` 는 대상이 아니다
- TTL: 600초. `engine/constants_market_system.py` 의 `LLMThresholds.SESSION_BLOCK_TTL_SECONDS` 에 둔다(리터럴 임계값을 코드에 두지 않는 저장소 규칙)
- 가드는 `analyze_stock` 한 곳. `analyze_batch` 에 별도 초기화를 두지 않는다
- VCP Gemini 호출의 출력 토큰 `config`·타임아웃 정렬은 범위 밖(승인 시 제외 결정)
- 테스트는 LLM 을 호출하지 않는다. `tests/engine/test_vcp_ai_analyzer_refactor.py` 의 `object.__new__` 패턴을 따른다
- pytest 는 `venv/bin/python -m pytest` 로 돌린다. 운영 반영은 gunicorn 워커 전부 재기동(장 중 금지)

## Review Focus

- `object.__new__` 로 만든 분석기(테스트·하네스)에는 `_session_blocks_since` 속성이 없다 → `getattr` 기본값으로 읽어 AttributeError 가 나지 않아야 한다 (Task 1 테스트가 `object.__new__` 로 검증)
- 플래그가 없을 때 `_session_blocks_since` 가 남아 있으면 다음 차단이 즉시 만료된다 → 플래그가 비어 있으면 시각을 `None` 으로 되돌린다 (Task 1 테스트 3)
- TTL 직전(599초)에는 차단이 유지되어 429 폭주 중 재호출하지 않아야 한다 (Task 1 테스트 1)
- 재분석 진행률 경로는 `analyze_batch` 를 거치지 않는다 → 가드가 `analyze_stock` 에 있어야 한다 (Task 1 테스트 2)
- 진행 중인 다른 코루틴이 옛 `gemini_blocked_models` 집합을 쥔 채 모델을 추가하면 그 추가는 새 집합에 반영되지 않는다. 다음 429 에서 다시 차단되므로 수용한다(테스트 없음, `ponytail:` 주석으로 표시). **반영 뒤 해소:** 구현은 `.clear()` 로 같은 집합을 비우므로 이 손실이 없다

---

### Task 1: 세션 차단 플래그 만료

**Files:**
- Modify: `engine/constants_market_system.py` (`LLMThresholds`)
- Modify: `engine/vcp_ai_analyzer.py` (import, `analyze_stock`, 새 메서드 `_expire_session_blocks`)
- Test: `tests/engine/test_vcp_ai_analyzer_refactor.py`

**Interfaces:**
- Produces: `VCPMultiAIAnalyzer._expire_session_blocks(self) -> None`, `LLMThresholds.SESSION_BLOCK_TTL_SECONDS: int = 600`, 인스턴스 속성 `_session_blocks_since: float | None`

- [ ] **Step 1: 실패하는 테스트 작성** (`tests/engine/test_vcp_ai_analyzer_refactor.py` 끝에 추가)

```python
def _gemini_analyzer_with_clock(monkeypatch, generate_content):
    clock = {"now": 0.0}
    monkeypatch.setattr("engine.vcp_ai_analyzer.time.monotonic", lambda: clock["now"])

    async def _fake_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    async def _no_sleep(_seconds):
        return None

    monkeypatch.setattr("engine.vcp_ai_analyzer.asyncio.to_thread", _fake_to_thread)
    monkeypatch.setattr("engine.vcp_ai_analyzer.asyncio.sleep", _no_sleep)
    analyzer = object.__new__(VCPMultiAIAnalyzer)
    analyzer.gemini_client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    analyzer._build_vcp_prompt = lambda *_args, **_kwargs: "prompt"
    return analyzer, clock


def test_gemini_blocked_models_expire_after_ttl(monkeypatch):
    # [VCP-041] 한 번의 429 폭주로 체인 전체가 막혀도 TTL 뒤에는 다시 호출한다.
    state = {"fail": True, "calls": 0}

    def _generate_content(*, model, contents):
        del model, contents
        state["calls"] += 1
        if state["fail"]:
            raise RuntimeError("429 resource_exhausted")
        return SimpleNamespace(text='{"action":"BUY","confidence":70,"reason":"ok"}')

    analyzer, clock = _gemini_analyzer_with_clock(monkeypatch, _generate_content)
    assert asyncio.run(analyzer._analyze_with_gemini("A", {"ticker": "000001"})) is None
    assert analyzer.gemini_blocked_models
    state.update(fail=False, calls=0)

    analyzer._expire_session_blocks()  # t=0 첫 관측
    clock["now"] = 599.0
    analyzer._expire_session_blocks()
    assert asyncio.run(analyzer._analyze_with_gemini("B", {"ticker": "000002"})) is None
    assert state["calls"] == 0

    clock["now"] = 601.0
    analyzer._expire_session_blocks()
    result = asyncio.run(analyzer._analyze_with_gemini("C", {"ticker": "000003"}))
    assert result is not None and result["action"] == "BUY"
    assert state["calls"] == 1


def test_analyze_stock_expires_gpt_and_perplexity_blocks(monkeypatch):
    # 재분석 진행률 경로는 analyze_batch 를 거치지 않으므로 가드는 analyze_stock 에 있어야 한다.
    monkeypatch.setattr("engine.vcp_ai_analyzer.time.monotonic", lambda: 601.0)

    async def _fake_orchestrate(**_kwargs):
        return {}

    monkeypatch.setattr("engine.vcp_ai_analyzer.orchestrate_stock_analysis_impl", _fake_orchestrate)
    analyzer = object.__new__(VCPMultiAIAnalyzer)
    analyzer.providers, analyzer.second_provider = ["gemini", "gpt"], "gpt"
    analyzer.gemini_blocked_models = {"gemini-x"}
    analyzer.gpt_quota_exhausted, analyzer.gpt_blocked_reason = True, "quota-like-402"
    analyzer.perplexity_quota_exhausted, analyzer.perplexity_blocked_reason = True, "429"
    analyzer._session_blocks_since = 0.0

    asyncio.run(analyzer.analyze_stock("A", {"ticker": "000001"}))

    assert analyzer.gemini_blocked_models == set()
    assert analyzer.gpt_quota_exhausted is False and analyzer.gpt_blocked_reason is None
    assert analyzer.perplexity_quota_exhausted is False and analyzer.perplexity_blocked_reason is None
    assert analyzer._session_blocks_since is None


def test_expire_session_blocks_resets_clock_when_nothing_blocked(monkeypatch):
    # 빈 상태에서 옛 시각이 남으면 다음 차단이 곧바로 풀린다.
    monkeypatch.setattr("engine.vcp_ai_analyzer.time.monotonic", lambda: 1000.0)
    analyzer = object.__new__(VCPMultiAIAnalyzer)
    analyzer._session_blocks_since = 0.0
    analyzer._expire_session_blocks()
    assert analyzer._session_blocks_since is None
```

- [ ] **Step 2: 실패 확인**

Run: `venv/bin/python -m pytest tests/engine/test_vcp_ai_analyzer_refactor.py -k "expire" -v`
Expected: 3건 FAIL (`AttributeError: ... '_expire_session_blocks'`)

- [ ] **Step 3: 상수 추가** (`engine/constants_market_system.py` 의 `LLMThresholds`, `BASE_RETRY_DELAY` 다음 줄)

```python
    # 429·503·쿼터 오류로 켠 VCP 분석기 세션 차단을 푸는 시간(초) [VCP-041]
    SESSION_BLOCK_TTL_SECONDS: int = 600
```

- [ ] **Step 4: 구현** (`engine/vcp_ai_analyzer.py`)

import 에 추가(로컬 import 묶음, `from engine.config import app_config` 다음):

```python
from engine.constants import LLM as LLM_THRESHOLDS
```

`analyze_stock` 본문 첫 줄:

```python
        self._expire_session_blocks()
```

`_parse_json_response` 앞에 새 메서드:

```python
    def _expire_session_blocks(self) -> None:
        """세션 차단 플래그를 처음 관측한 시각에서 TTL 이 지나면 모두 비운다 [VCP-041].

        싱글톤 분석기가 워커 수명 동안 살아 있어 차단이 재기동 전까지 남던 것을 막는다.
        """
        # ponytail: 만료는 종목 단위로 판정하므로 실제 차단은 TTL + 종목 하나의 분석 시간까지 늘 수 있고,
        # 진행 중인 코루틴이 옛 제외 집합에 추가한 모델은 버려진다. 다음 429 에서 다시 막히므로 수용한다.
        blocked = bool(getattr(self, "gemini_blocked_models", None)) or any(
            getattr(self, name, None)
            for name in (
                "gpt_quota_exhausted",
                "gpt_blocked_reason",
                "perplexity_quota_exhausted",
                "perplexity_blocked_reason",
            )
        )
        if not blocked:
            self._session_blocks_since = None
            return
        now = time.monotonic()
        since = getattr(self, "_session_blocks_since", None)
        if since is None:
            self._session_blocks_since = now
            return
        if now - since < LLM_THRESHOLDS.SESSION_BLOCK_TTL_SECONDS:
            return
        logger.info(
            "VCP 분석기 세션 차단 해제: gemini=%s, gpt=%s, perplexity=%s",
            sorted(getattr(self, "gemini_blocked_models", None) or []),
            getattr(self, "gpt_blocked_reason", None),
            getattr(self, "perplexity_blocked_reason", None),
        )
        self.gemini_blocked_models = set()
        self.gpt_quota_exhausted = False
        self.gpt_blocked_reason = None
        self.perplexity_quota_exhausted = False
        self.perplexity_blocked_reason = None
        self._session_blocks_since = None
```

`__init__` 끝(`self.gpt_blocked_reason: str | None = None` 다음)에 `self._session_blocks_since: float | None = None` 을 둔다.

- [ ] **Step 5: 통과 확인**

Run: `venv/bin/python -m pytest tests/engine/test_vcp_ai_analyzer_refactor.py -v`
Expected: 전부 PASS (기존 `test_analyze_with_gemini_429_blocks_model_for_session` 포함. 같은 배치 안 두 종목은 TTL 안이므로 여전히 한 번만 부른다)

- [ ] **Step 6: 전체 테스트**

Run: `venv/bin/python -m pytest -q`
Expected: 실패 0

- [ ] **Step 7: 커밋** (dev-cycle [3] 5번의 첫 커밋. QA 행렬 문서와 TODO 진행 체크를 함께 담는다)

```bash
git add engine/constants_market_system.py engine/vcp_ai_analyzer.py tests/engine/test_vcp_ai_analyzer_refactor.py docs/superpowers/plans/2026-09-24-vcp-041-session-block-expiry.md docs/dev-cycle/qa/VCP-041.md docs/dev-cycle/TODO.md && git diff --cached --check && git commit -m "fix(vcp): [VCP-041] expire analyzer session blocks after 10 minutes"
```
