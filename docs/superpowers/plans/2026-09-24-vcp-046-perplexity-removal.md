# [VCP-046] Perplexity 프로바이더 제거 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 분석기·설정·화면·문서에서 Perplexity 를 새로 호출하거나 설정하는 경로를 모두 없애고, 과거 캐시의 `perplexity_recommendation` 은 읽기 전용으로 남긴다.

**Architecture:** 두 번째 AI 는 GPT 하나로 확정한다(`resolve_effective_second_provider` 가 `perplexity` 설정을 `gpt` 로 바꾸고 경고). 오케스트레이션은 새 칸 목록 `VCP_AI_WRITTEN_FIELDS`(gemini·gpt)만 쓰고, 읽는 쪽은 세 칸짜리 `VCP_AI_RECOMMENDATION_FIELDS` 를 그대로 쓴다. 화면은 데이터가 있을 때만 Perplexity 열을 보이는 현재 로직을 유지한다.

**Tech Stack:** Python 3.11(pytest), Next.js 16 / React(vitest, tsc, eslint)

**Spec:** `docs/superpowers/specs/2026-09-24-vcp-046-perplexity-removal-design.md` (대화 설계 승인 12:46, 문서 승인 13:02)

## Global Constraints

- 티어 T3. 위험 경로 `engine/vcp_ai_*` 를 건드린다. 리뷰는 `/ponytail-review` → `closing-bet-reviewer` → `/review` 순서다.
- pytest 는 `venv/bin/python -m pytest` 로 돌린다. frontend 검증은 `cd frontend && npm run test && npm run type-check && npm run lint`.
- 스테이징 뒤 `git diff --cached --check` 를 다음 명령과 `&&` 로 잇는다.
- `data/`·`.env` 는 읽기 전용이다. 실제 LLM 호출, 설정 저장, Refresh, AI 재분석 실행은 하지 않는다.
- 원본 포트 3500·5501 에서 QA 하지 않는다.
- 파이썬 파일 머리글·로거·타입 힌트는 `CLAUDE.md` Code Style 을 따른다. 읽은 정본: `.claude/skills/closing-bet-python/SKILL.md`, `.claude/skills/closing-bet-nextjs/SKILL.md`, `frontend/node_modules/next/dist/docs/01-app/01-getting-started/05-server-and-client-components.md`(고치는 파일이 모두 `'use client'` 컴포넌트와 서버 페이지의 정적 문구다).
- 이력 문서(`docs/dev-cycle/archive/`·`evidence/`·`qa/`·`reviews/`·`audits/`, `docs/superpowers/plans/`·과거 `specs/`, `tests/curl_output.json`)는 고치지 않는다.
- 커밋 트레일러:
  ```
  Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01AeQQtEk7wbuVAnf9kCJmBN
  ```

## Review Focus

1. 운영 `.env` 가 `VCP_AI_PROVIDERS=gemini,perplexity`, `VCP_SECOND_PROVIDER=perplexity` 로 남은 경우: perplexity 는 목록에서 빠지고 gpt 가 목록에 없으므로 두 번째 AI 는 `None`, 경고 세 줄(목록에서 제거, perplexity 를 gpt 로 대체, 두 번째 자리 비움). Task 1 에 테스트를 둔다.
2. 과거 날짜 VCP 표: 캐시 행에 `perplexity_recommendation` 만 유효하면 API legacy 보강이 그 칸을 응답에 싣는다. 기존 `tests/app/test_kr_market_vcp_signal_helpers_refactor.py::test_legacy_merge_fills_the_same_three_provider_fields` 가 덮으며 이 테스트는 고치지 않는다. Task 2 에서 통과를 확인한다.
3. 과거 날짜 재분석: 분석기 `second_provider == "gpt"` 이면 필요한 칸은 `gemini_recommendation`·`gpt_recommendation` 이다. Task 4 의 서비스 테스트가 `perplexity` 스텁 대신 `gpt` 스텁으로 이것을 고정한다.
4. 강제 재분석 `force_provider="second"` 와 `skip_second`: 두 번째 자리가 gpt 일 때 GPT 만 부른다. 기존 `test_orchestrate_stock_analysis_skips_second_provider_when_flag_is_set` 를 gpt 로 바꿔 유지한다(Task 2).
5. 운영 `.env` 에 `PERPLEXITY_API_KEY` 값이 남은 채 설정 모달을 열고 저장: GET 이 그 키를 돌려주지 않고, 화면이 그 키를 보내지 않으며, 보내더라도 `update_env_file` 이 `unsupported_key` 로 거부한다. Task 5 의 백엔드 테스트로 고정한다.

---

### Task 1: 프로바이더 확정 규칙

**Files:**
- Modify: `engine/vcp_ai_provider_init_helpers.py:113-168`
- Test: `tests/engine/test_vcp_ai_provider_init_helpers_refactor.py:12-20, 127-245`

**Interfaces:**
- Produces: `drop_removed_providers(providers: list[str], logger) -> list[str]`, `resolve_effective_second_provider(providers: list[str], second_provider: str | None, logger) -> str | None`(인자 `perplexity_disabled` 없음). `resolve_perplexity_disabled` 는 사라진다.

- [ ] **Step 1: 테스트 교체**

import 목록에서 `resolve_perplexity_disabled` 를 빼고 `drop_removed_providers` 를 넣는다. 다음 테스트를 삭제한다: `test_resolve_perplexity_disabled_when_required_key_missing`, `test_resolve_effective_second_provider_falls_back_to_gpt`, `test_resolve_effective_second_provider_warns_when_gpt_is_not_listed`, `test_resolve_effective_second_provider_keeps_available_perplexity`, `test_resolve_effective_second_provider_allows_perplexity_backed_by_gpt_only`. 남는 두 테스트(`rejects_unsupported_provider`, `normalizes_aliases`)에서는 `perplexity_disabled=False,` 줄만 지운다. 그 자리에 추가한다:

```python
def test_resolve_effective_second_provider_maps_perplexity_to_gpt():
    """[VCP-046] 운영 .env 에 perplexity 가 남아 있어도 GPT 로 실행하고 그 사실을 남긴다."""
    logger = _Logger()

    assert (
        resolve_effective_second_provider(
            providers=["gemini", "gpt"],
            second_provider="perplexity",
            logger=logger,
        )
        == "gpt"
    )
    assert len(logger.warnings) == 1
    assert "perplexity" in logger.warnings[0]


def test_resolve_effective_second_provider_warns_twice_when_gpt_is_not_listed():
    """perplexity 를 gpt 로 바꿨는데 목록에 gpt 가 없으면 두 번째 자리를 비운다.

    `[VCP-003]` 때처럼 두 번째 열이 조용히 비지 않도록 비운 사실도 따로 경고한다.
    """
    logger = _Logger()

    assert (
        resolve_effective_second_provider(
            providers=["gemini"],
            second_provider="perplexity",
            logger=logger,
        )
        is None
    )
    assert len(logger.warnings) == 2
    assert "VCP_SECOND_PROVIDER" in logger.warnings[1]


def test_drop_removed_providers_ignores_perplexity_with_warning():
    logger = _Logger()

    assert drop_removed_providers(["gemini", "perplexity", "gpt"], logger) == ["gemini", "gpt"]
    assert len(logger.warnings) == 1
    assert drop_removed_providers(["gemini", "gpt"], _Logger()) == ["gemini", "gpt"]
```

- [ ] **Step 2: 실패 확인**

Run: `venv/bin/python -m pytest tests/engine/test_vcp_ai_provider_init_helpers_refactor.py -q`
Expected: ImportError(`drop_removed_providers`) 로 수집 실패

- [ ] **Step 3: 구현**

`resolve_effective_second_provider` 와 `resolve_perplexity_disabled` 를 아래로 바꾸고 `__all__` 에서 `resolve_perplexity_disabled` 를 빼고 `drop_removed_providers` 를 넣는다.

```python
def drop_removed_providers(providers: list[str], logger: Any) -> list[str]:
    """허용 목록에서 제거된 perplexity 를 빼고, 뺐으면 경고한다 [VCP-046].

    운영 .env 에 남아 있어도 기동은 계속한다.
    """
    kept = [provider for provider in providers if provider != "perplexity"]
    if len(kept) != len(providers):
        logger.warning("VCP_AI_PROVIDERS 의 perplexity 는 [VCP-046] 에서 제거되어 무시합니다")
    return kept


def resolve_effective_second_provider(
    providers: list[str],
    second_provider: str | None,
    logger: Any,
) -> str | None:
    """실제로 실행할 두 번째 provider 를 확정한다. 실행할 수 없으면 None 을 돌려준다.

    두 번째 자리는 GPT 하나다. 제거된 perplexity 설정은 GPT 로 바꾼다 [VCP-046]. 호출부가
    이 값을 캐시 키 판정에도 쓰므로, 실행 결과가 담기는 필드와 판정이 기다리는 필드가 갈리지 않는다.
    """
    normalized_providers = normalize_provider_list(providers)
    provider = normalize_provider_name(second_provider)

    if provider == "perplexity":
        logger.warning(
            f"VCP_SECOND_PROVIDER={second_provider} 는 [VCP-046] 에서 제거되어 gpt 로 실행합니다. "
            ".env 를 gpt 로 고치면 이 경고가 사라집니다"
        )
        provider = "gpt"

    if provider == "gpt" and "gpt" in normalized_providers:
        return "gpt"

    logger.warning(
        "두 번째 AI Provider를 실행할 수 없어 VCP 표의 두 번째 AI 열이 비게 됩니다 "
        f"(VCP_SECOND_PROVIDER={second_provider}, VCP_AI_PROVIDERS={normalized_providers})"
    )
    return None
```

- [ ] **Step 4: 통과 확인**

Run: `venv/bin/python -m pytest tests/engine/test_vcp_ai_provider_init_helpers_refactor.py -q`
Expected: 전부 PASS

Task 1 은 분석기가 아직 옛 시그니처를 부르므로 커밋하지 않고 Task 3 과 함께 커밋한다.

### Task 2: 오케스트레이션과 새 칸 목록

**Files:**
- Modify: `engine/vcp_ai_orchestration_helpers.py:13-56`
- Test: `tests/engine/test_vcp_ai_orchestration_helpers_refactor.py`

**Interfaces:**
- Produces: `VCP_AI_WRITTEN_FIELDS: tuple[str, str] = ("gemini_recommendation", "gpt_recommendation")`. `orchestrate_stock_analysis(*, stock_name, stock_data, providers, second_provider, build_prompt_fn, analyze_with_gemini_fn, analyze_with_gpt_fn, logger)` 에서 `analyze_with_perplexity_fn` 이 사라진다.

- [ ] **Step 1: 테스트 수정**

모든 테스트에서 `async def _perplexity(...)` 정의와 `analyze_with_perplexity_fn=_perplexity,` 인자를 지운다. 각 테스트를 다음처럼 바꾼다.
- `test_orchestrate_stock_analysis_merges_provider_results`: `VCP_AI_RECOMMENDATION_FIELDS == (...)` 단언은 그대로 두고(세 칸은 읽기 목록으로 남는다) 그 아래를 이렇게 바꾼다.
  ```python
  assert VCP_AI_WRITTEN_FIELDS == ("gemini_recommendation", "gpt_recommendation")
  assert set(result) == {"ticker", "stock_name", *VCP_AI_WRITTEN_FIELDS}
  ```
  import 에 `VCP_AI_WRITTEN_FIELDS` 를 더한다.
- `test_orchestrate_stock_analysis_skips_gemini_when_flag_is_set`: `calls` 키, `providers`, `second_provider` 의 `perplexity` 를 `gpt` 로, 가짜 함수 `_perplexity` 를 `_gpt`(같은 몸체, `calls["gpt"] += 1`, SELL 반환)로 바꾸고 `analyze_with_gpt_fn=_gpt` 로 넘긴다. 단언은 `calls["gpt"] == 1`, `result["gpt_recommendation"]["action"] == "SELL"`.
- `test_orchestrate_stock_analysis_skips_second_provider_when_flag_is_set`: 두 번째 자리가 perplexity 였다면 같은 방식으로 gpt 로 바꾼다.
- 헬퍼 `_run_with_second_provider`(`:183-215`): `_perplexity` 스텁과 `analyze_with_perplexity_fn=_perplexity,` 를 지우고, docstring 의 「세 스텁」을 「두 스텁」으로 고친다.
- `test_orchestrator_leaves_second_column_empty_when_provider_is_none`(`:218`): `_run_with_second_provider(None, ["gemini", "gpt"])` 로 바꾸고 `:224` 를 `assert "perplexity_recommendation" not in result` 로 바꾼다.
- `test_orchestrator_warns_when_no_provider_runs_at_all`(`:227`): `:244` `analyze_with_perplexity_fn=_unreachable_provider,` 줄을 지우고 `:251` 을 `assert "perplexity_recommendation" not in result` 로 바꾼다.
- `test_orchestrator_follows_resolved_provider_without_rechecking_providers`(`:260`): 의도(확정값을 providers 목록으로 다시 거르지 않는다)를 gpt 로 옮긴다.
  ```python
  def test_orchestrator_follows_resolved_provider_without_rechecking_providers():
      """확정값이 gpt 면 providers 목록에 gpt 가 없어도 다시 따지지 않고 그대로 실행한다.

      실행 가능 여부는 resolve_effective_second_provider 가 이미 판정했다. 여기서 한 번 더
      거르면 두 곳의 규칙이 갈려 `[VCP-003]` 과 같은 어긋남이 다시 생긴다.
      """
      result = _run_with_second_provider("gpt", ["gemini"])

      assert result["gpt_recommendation"]["action"] == "BUY"
  ```

- [ ] **Step 2: 실패 확인**

Run: `venv/bin/python -m pytest tests/engine/test_vcp_ai_orchestration_helpers_refactor.py -q`
Expected: ImportError(`VCP_AI_WRITTEN_FIELDS`)

- [ ] **Step 3: 구현**

```python
# AI 추천을 담는 칸. 세 번째 perplexity_recommendation 은 과거 캐시 읽기 전용이다.
# [VCP-046] 이후 새로 쓰지 않지만, 2026-02 캐시가 두 번째 판정을 이 칸에만 담고 있어
# legacy 보강과 수집 병합은 계속 세 칸을 읽는다.
VCP_AI_RECOMMENDATION_FIELDS = (
    "gemini_recommendation",
    "gpt_recommendation",
    "perplexity_recommendation",
)
# 새 분석 결과가 쓰는 칸
VCP_AI_WRITTEN_FIELDS = VCP_AI_RECOMMENDATION_FIELDS[:2]
```

`orchestrate_stock_analysis` 에서 `analyze_with_perplexity_fn` 인자와 `second_provider == "perplexity"` 갈래를 지우고, `results` 초기값을 `**dict.fromkeys(VCP_AI_WRITTEN_FIELDS)` 로 바꾼다. `elif not skip_second and second_provider == "gpt":` 는 `if` 로 바꾼다.

- [ ] **Step 4: 통과 확인**

Run: `venv/bin/python -m pytest tests/engine/test_vcp_ai_orchestration_helpers_refactor.py tests/app/test_kr_market_vcp_signal_helpers_refactor.py -q`
Expected: 전부 PASS(뒤 파일은 Review Focus 2 의 legacy 보강 확인)

Task 3 과 함께 커밋한다.

### Task 3: 분석기·헬퍼·설정 속성

**Files:**
- Modify: `engine/vcp_ai_analyzer.py` (import `:15-40`, 클래스 docstring `:89`, 생성자 `:91-123`, `_expire_session_blocks` `:624-668`, `analyze_stock` `:674-691`, `_analyze_with_perplexity` `:693-836` 삭제, `_build_perplexity_fallback_chain`·`_resolve_perplexity_fallback_providers`·`_fallback_from_perplexity` `:1175-1240` 삭제, `get_available_providers` `:1285-1295`)
- Modify: `engine/vcp_ai_analyzer_helpers.py:19-35, 731-840`
- Modify: `engine/config.py:239-271`
- Test: `tests/engine/test_vcp_ai_analyzer_refactor.py`, `tests/engine/test_vcp_ai_analyzer_helpers_refactor.py`

**Interfaces:**
- Consumes: Task 1 의 `drop_removed_providers`, `resolve_effective_second_provider(providers, second_provider, logger)`. Task 2 의 `orchestrate_stock_analysis`(perplexity 인자 없음).

- [ ] **Step 1: 테스트 수정**

`tests/engine/test_vcp_ai_analyzer_refactor.py`
- 삭제(대상 코드 제거): `test_get_available_providers_excludes_perplexity_when_disabled`, `test_analyze_with_perplexity_*` 아홉 개(`:119`~`:500`), `test_init_keeps_perplexity_when_key_is_present`.
- `_build_analyzer_without_clients` 에서 `has_perplexity_key` 인자와 `PERPLEXITY_API_KEY` 설정 줄을 지운다.
- `test_init_confirms_second_provider_with_fallback_applied`: `has_perplexity_key` 인자와 `perplexity_disabled` 단언을 지우고 `assert analyzer.second_provider == "gpt"` 만 남긴다. docstring 은 「생성자가 perplexity 설정을 gpt 로 확정한다」로 고친다.
- `test_init_leaves_second_provider_unset_when_nothing_can_run`: `has_perplexity_key` 만 지운다. `providers="gemini,perplexity"` 는 그대로 둬 Review Focus 1 을 덮는다. 아래 단언을 더한다.
  ```python
  assert analyzer.providers == ["gemini"]
  ```
- `test_analyze_stock_builds_prompt_once_and_shares_to_providers` 등 `analyzer.perplexity_disabled = ...` 를 심는 줄은 모두 지운다.
- `test_analyze_stock_expires_gpt_and_perplexity_blocks` → 이름을 `test_analyze_stock_expires_gpt_blocks` 로 바꾸고 perplexity 두 줄(설정·단언)을 지운다.
- `test_analyze_stock_builds_prompt_once_and_shares_to_providers` 의 `:1260` `analyzer._analyze_with_perplexity = lambda *_a, **_k: None` 줄을 지운다.
- 새로 추가:
  ```python
  def test_get_available_providers_lists_only_initialized_clients():
      analyzer = object.__new__(VCPMultiAIAnalyzer)
      analyzer.gemini_client = object()
      analyzer.gpt_client = None
      analyzer.zai_client = object()

      assert analyzer.get_available_providers() == ["gemini", "zai"]
  ```

`tests/engine/test_vcp_ai_analyzer_helpers_refactor.py`: `test_perplexity_request_and_response_helpers`, `test_is_perplexity_quota_exceeded_detects_quota_like_errors` 를 삭제하고 import(`:18-24`)에서 `build_perplexity_request`·`extract_perplexity_response_text`·`is_perplexity_quota_exceeded` 세 함수를 뺀다.

- [ ] **Step 2: 실패 확인**

Run: `venv/bin/python -m pytest tests/engine -q`
Expected: 생성자가 `resolve_perplexity_disabled` 를 import 하므로 수집 오류

- [ ] **Step 3: 구현**

`engine/vcp_ai_analyzer.py`
- import 에서 `build_perplexity_request`, `classify_perplexity_error`, `extract_perplexity_response_text`, `is_perplexity_quota_exceeded`, `resolve_perplexity_disabled` 를 빼고 `drop_removed_providers` 를 넣는다. `httpx` 는 grep 으로 다른 사용처가 없으면 import 를 지운다.
- 생성자:
  ```python
  def __init__(self):
      self.providers = drop_removed_providers(
          normalize_provider_list(app_config.VCP_AI_PROVIDERS), logger
      )
      configured_second_provider = normalize_provider_name(app_config.VCP_SECOND_PROVIDER)

      logger.info(f"VCP MultiAI 분석기 초기화: {self.providers}")

      self.gemini_client = init_gemini_client(self.providers, app_config, logger)
      self.gpt_client = init_gpt_client(self.providers, app_config, logger)
      self.zai_client = init_zai_client(app_config, logger)

      # 폴백까지 반영한 확정값. 재분석 서비스가 캐시 키를 정할 때 이 값을 읽으므로,
      # 실행 결과가 담기는 필드와 재분석이 기다리는 필드가 갈리지 않는다.
      self.second_provider = resolve_effective_second_provider(
          providers=self.providers,
          second_provider=configured_second_provider,
          logger=logger,
      )
      self.gemini_blocked_models: set[str] = set()
      self.gpt_quota_exhausted = False
      self.gpt_blocked_reason: str | None = None
      self._session_blocks_since: float | None = None
  ```
- `_expire_session_blocks`: 플래그 이름 튜플에서 `"perplexity_quota_exhausted"`, `"perplexity_blocked_reason"` 을 지우고, 로그를 `"VCP 분석기 세션 차단 해제: gemini=%s, gpt=%s, zai=%s"` 와 세 인자로, 초기화 두 줄(`self.perplexity_* = ...`)을 지운다.
- `analyze_stock`: `analyze_with_perplexity_fn=self._analyze_with_perplexity,` 를 지우고 docstring 을 「(Gemini + GPT 동시 실행 - 병렬 처리)」로 고친다.
- `_analyze_with_perplexity`, `_build_perplexity_fallback_chain`, `_resolve_perplexity_fallback_providers`, `_fallback_from_perplexity` 를 삭제한다.
- `get_available_providers` 에서 perplexity 두 줄을 지운다.
- 모듈·클래스 docstring 의 「GPT/Perplexity」를 「GPT」로 고친다.

`engine/vcp_ai_analyzer_helpers.py`: `_PERPLEXITY_QUOTA_KEYWORDS`, `_PERPLEXITY_AUTH_KEYWORDS`, `build_perplexity_request`, `extract_perplexity_response_text`, `is_perplexity_quota_exceeded`, `classify_perplexity_error` 와 `__all__` 의 해당 이름을 지운다. 먼저 `git grep -n -E 'build_perplexity_request|extract_perplexity_response_text|is_perplexity_quota_exceeded|classify_perplexity_error|_PERPLEXITY_(QUOTA|AUTH)_KEYWORDS'` 로 호출자가 분석기·`scripts/llm_quality_harness.py`(Task 6)·테스트뿐인지 확인한다.

`engine/config.py`: `VCP_PERPLEXITY_MODEL`, `VCP_PERPLEXITY_API_TIMEOUT`, `PERPLEXITY_API_KEY` 속성을 지운다. `VCP_SECOND_PROVIDER` 속성에 주석이나 허용값 설명이 있으면 「gpt」로 고친다.

- [ ] **Step 4: 통과 확인**

Run: `venv/bin/python -m pytest tests/engine tests/app -q && git grep -n -i perplexity -- engine/`
Expected: pytest 전부 PASS. grep 은 `vcp_ai_orchestration_helpers.py` 의 읽기 전용 칸과 주석, `vcp_ai_provider_init_helpers.py` 의 perplexity 설정 처리, `signal_tracker_ai_helpers.py` 의 우선순위만 남는다.

- [ ] **Step 5: 커밋 (Task 1~3)**

```bash
git add engine/vcp_ai_provider_init_helpers.py engine/vcp_ai_orchestration_helpers.py engine/vcp_ai_analyzer.py engine/vcp_ai_analyzer_helpers.py engine/config.py tests/engine/ && git diff --cached --check && git commit -m "refactor(vcp): [VCP-046] remove Perplexity provider from VCP analyzer"
```
(메시지 끝에 Global Constraints 의 트레일러 두 줄)

### Task 4: 재분석 서비스와 수집 쪽 우선순위 주석

**Files:**
- Modify: `services/kr_market_vcp_reanalysis_service.py:28-40, 141, 572-574`
- Modify: `app/routes/kr_market_vcp_signal_helpers.py:27-31, 99`
- Modify: `engine/signal_tracker_ai_helpers.py:86-107` (주석만)
- Test: `tests/services/test_kr_market_vcp_service.py`, `tests/app/test_kr_market_vcp_signal_helpers_refactor.py`

**Interfaces:**
- Consumes: 분석기 `second_provider` 는 `"gpt"` 또는 `None` 이다.

- [ ] **Step 1: 테스트 수정**

`tests/services/test_kr_market_vcp_service.py` 의 분석기 스텁(`second_provider = "perplexity"`, `get_available_providers` 가 `["gemini", "perplexity"]` 를 돌려주는 곳, `:304`·`:406`·`:516`·`:603`·`:695`·`:1109`·`:1196`·`:1274`)을 `"gpt"`·`["gemini", "gpt"]` 로 바꾸고, 그 테스트들의 캐시·결과 fixture 에서 두 번째 판정 칸 `perplexity_recommendation` 을 `gpt_recommendation` 으로 바꾼다(`:319`·`:421`·`:531`·`:711`·`:743`·`:1092`·`:1285`). 다음은 그대로 둔다.
- `:70` `test_collect_missing_vcp_ai_rows_flags_gemini_or_second_missing`, `:115`, `:215`, `:748`: 칸 이름을 인자로 받는 순수 함수 검사이며 과거 캐시 읽기(Review Focus 3)의 근거다.
- `:772` `test_execute_vcp_failed_ai_reanalysis_cache_key_follows_analyzer_fallback`: `VCP_SECOND_PROVIDER=perplexity` 설정에서 GPT 칸을 기다린다는 검사로, [VCP-046] 뒤에도 같은 결론이다. 다만 대응표에서 perplexity 를 빼면 설정값도 `gpt_recommendation` 으로 풀리므로, 이 테스트는 「캐시 키를 app_config 에서 다시 읽는 회귀」를 더는 잡지 못한다. 그 회귀는 `:868` 테스트(분석기 `second_provider=None`, 설정 기본값 gpt)가 계속 잡는다. docstring 의 「키가 없어 GPT 로 확정」을 「perplexity 설정은 GPT 로 확정」으로, `:846-852` 주석을 「캐시 키 재읽기 회귀는 `:868` 테스트가 잡는다」로 고친다. `:670`·`:1084` 주석의 「second provider(perplexity)」도 「second provider(gpt)」로 고친다.

`tests/app/test_kr_market_vcp_signal_helpers_refactor.py` 에 과거 캐시 읽기 검사를 추가한다(설계 §4, Review Focus 2). 파일은 `vcp_helpers` 로 모듈을 import 한다(`:9`).
```python
def test_extract_reads_legacy_perplexity_only_row():
    # [VCP-046] 2026-02 캐시는 두 번째 판정을 perplexity 칸에만 담았다. 새로 쓰지 않아도 계속 읽는다
    ai_results = {
        "000001": {"perplexity_recommendation": {"action": "HOLD", "confidence": 60, "reason": "과거 캐시 판정"}}
    }

    assert vcp_helpers._extract_vcp_ai_recommendation(ai_results, "000001") == (True, "HOLD", 60, "과거 캐시 판정")
```

`tests/services/test_kr_market_vcp_service.py` 에 추가:
```python
def test_resolve_vcp_second_recommendation_key_no_longer_maps_perplexity():
    # [VCP-046] 분석기의 두 번째 자리는 perplexity 가 될 수 없다
    assert resolve_vcp_second_recommendation_key("perplexity") == "gpt_recommendation"
```

- [ ] **Step 2: 실패 확인**

Run: `venv/bin/python -m pytest tests/services/test_kr_market_vcp_service.py -q`
Expected: 새 서비스 테스트 FAIL(`perplexity_recommendation` 반환). 새 legacy 읽기 테스트는 지금도 PASS 여야 한다(현재 동작을 고정하는 검사다). `venv/bin/python -m pytest tests/app/test_kr_market_vcp_signal_helpers_refactor.py -q -k legacy_perplexity` 로 확인한다

- [ ] **Step 3: 구현**

`services/kr_market_vcp_reanalysis_service.py`
```python
_GEMINI_RECOMMENDATION_FIELD, _GPT_RECOMMENDATION_FIELD = VCP_AI_WRITTEN_FIELDS

_VCP_SECOND_RECOMMENDATION_KEY_MAP = {
    "gpt": _GPT_RECOMMENDATION_FIELD,
    "openai": _GPT_RECOMMENDATION_FIELD,
    "zai": _GPT_RECOMMENDATION_FIELD,
    "z.ai": _GPT_RECOMMENDATION_FIELD,
}
```
import 에 `VCP_AI_WRITTEN_FIELDS` 를 더한다. `recommendation_keys = VCP_AI_RECOMMENDATION_FIELDS`(`:162`, 캐시 읽기)는 그대로 둔다. `:141` docstring 은 과거 캐시에 `perplexity_recommendation` 이 있을 수 있다는 설명으로, `:572-574` 주석은 「설정값이 아니라 analyzer 가 확정한 provider 를 읽는다」만 남기고 Perplexity 예시를 지운다.

`app/routes/kr_market_vcp_signal_helpers.py:27-31` 주석을 다음으로 바꾼다.
```python
# AI 추천을 담는 세 필드. legacy 보강과 시그널 병합이 같은 목록을 봐야 한다. 두 번째
# 판정은 [VCP-046] 이후 gpt_recommendation 에만 쓰지만, data/ 의 2026-02-12~02-20
# 캐시는 perplexity_recommendation 에만 담고 있다. 그러므로 보강 목록이 부분집합이면
# 그 날짜의 두 번째 판정이 응답에 닿지 못한다.
```
`:99` docstring 의 순서 설명 뒤에 「Perplexity 는 과거 캐시에서만 읽힌다」를 더한다. `engine/signal_tracker_ai_helpers.py` 의 우선순위 docstring 에도 같은 한 줄을 더한다.

- [ ] **Step 4: 통과 확인**

Run: `venv/bin/python -m pytest tests/services tests/app tests/engine -q`
Expected: 전부 PASS

- [ ] **Step 5: 커밋**

```bash
git add services/kr_market_vcp_reanalysis_service.py app/routes/kr_market_vcp_signal_helpers.py engine/signal_tracker_ai_helpers.py tests/services/test_kr_market_vcp_service.py tests/app/test_kr_market_vcp_signal_helpers_refactor.py && git diff --cached --check && git commit -m "refactor(vcp): [VCP-046] second-AI cache key is GPT only, keep legacy Perplexity reads"
```

### Task 5: 설정 키와 화면 문구

**Files:**
- Modify: `services/common_env_service.py:127`
- Modify: `frontend/src/app/components/SettingsModal.tsx:797-830` (Perplexity `<section>` 삭제. `:282` 의 localStorage 정리 목록은 예전 값을 지우는 용도라 유지)
- Modify: `frontend/src/app/page.tsx:54, 80, 129, 234, 260`
- Modify: `frontend/src/app/components/VCPCriteriaModal.tsx:85-93`
- Modify: `frontend/src/app/(legal)/privacy/page.tsx:9, 233-247, 277-280`
- Modify: `frontend/src/app/dashboard/kr/vcp/page.tsx:552-557`, `frontend/src/app/dashboard/kr/vcp/aiHelpers.ts:3-15` (주석만)
- Test: `tests/app/test_common_env_service.py`, `frontend/src/app/components/SettingsModal.apikeys.test.tsx`, `SettingsModal.env-fields.test.tsx`, `settingsEnv.test.ts`, `frontend/src/app/(legal)/legal-pages.test.tsx`

- [ ] **Step 1: 테스트 수정**

백엔드: `tests/app/test_common_env_service.py` 에 추가한다(이미 `read_masked_env_vars`, `update_env_file` 을 import 한다).
```python
def test_perplexity_key_is_no_longer_editable(tmp_path: Path):
    # [VCP-046] 운영 .env 에 값이 남아 있어도 화면으로 읽거나 쓰지 않는다
    env_path = tmp_path / ".env"
    env_path.write_text("PERPLEXITY_API_KEY=pplx-secret-value-0000000000\n", encoding="utf-8")

    assert "PERPLEXITY_API_KEY" not in read_masked_env_vars(str(env_path))
    result = update_env_file(str(env_path), {"PERPLEXITY_API_KEY": "x"}, {})
    assert result["rejected"] == {"PERPLEXITY_API_KEY": "unsupported_key"}
    assert "pplx-secret-value" in env_path.read_text(encoding="utf-8")
```

frontend:
- `SettingsModal.apikeys.test.tsx`: `MASKED_PERPLEXITY` 상수와 응답의 `PERPLEXITY_API_KEY` 는 남긴다(서버에 값이 남은 배포를 흉내). 다음을 고친다.
  - `:67` `openApiTabWithStoredKeys` 의 `toHaveLength(2)` → `toHaveLength(1)`, `:75` 의 `inputs).toHaveLength(2)` → `toHaveLength(1)`.
  - `:49-55` docstring 에서 「두 필드가 같은 경로를 거쳤다는 증거」와 `pplx-...` 문장을 지우고 「필드가 STORED_HINT 를 갖는 것이 반영 완료의 신호다」만 남긴다. `:73` 테스트 이름의 「두 입력 어느 쪽에도」를 「입력에」로 고친다. 두 필드를 대조하던 검사가 사라진다는 사실은 아카이브에 적는다.
  - `:97`·`:99` 를 `expect(screen.queryByLabelText('PERPLEXITY_API_KEY')).toBeNull();` 한 줄로 바꾼다. `:106` 의 localStorage 단언은 그대로 둔다.
- `SettingsModal.env-fields.test.tsx:29`, `settingsEnv.test.ts:49`: 입력 fixture 이므로 그대로 둔다.
- `legal-pages.test.tsx:75`: `expect(text).toContain('OpenAI, L.L.C.');` 와 `expect(text).not.toContain('Perplexity');` 로 바꾼다.

- [ ] **Step 2: 실패 확인**

Run: `venv/bin/python -m pytest tests/app/test_common_env_service.py -q -k perplexity; cd frontend && npx vitest run src/app/components/SettingsModal.apikeys.test.tsx "src/app/(legal)/legal-pages.test.tsx"`
Expected: 새 백엔드 테스트 FAIL, frontend 두 파일 FAIL

- [ ] **Step 3: 구현**

- `services/common_env_service.py`: `EDITABLE_ENV_KEYS` 에서 `"PERPLEXITY_API_KEY",` 삭제.
- `SettingsModal.tsx`: `:797` 의 `<section>`(제목 「Perplexity」)부터 그 `</section>` 까지 삭제.
- `page.tsx`(랜딩):
  - `:54` `Gemini + GPT + Perplexity 멀티 AI 엔진` → `Gemini + GPT 멀티 AI 엔진`
  - `:80` Perplexity 로고 `<div>` 한 줄 삭제
  - `:129` `Gemini + GPT + Perplexity` → `Gemini + GPT`
  - `:234` `Gemini 주분석 + GPT/Perplexity 보조 검증으로` → `Gemini 주분석 + GPT 보조 검증으로`
  - `:260` `Perplexity (Sub)` 항목을 담은 요소 삭제(주변 구조를 읽고 그 항목 하나만 지운다)
- `VCPCriteriaModal.tsx`: `:85` `(Gemini 우선 · GPT/Perplexity 보조)` → `(Gemini 우선 · GPT 보조)`, `:89` 의 `VCP_SECOND_PROVIDER` 설명을 「<span>GPT</span>가 2차 검증을 수행합니다」 취지로 줄이고, `:93` Perplexity `<li>` 삭제.
- `privacy/page.tsx`:
  - `EFFECTIVE_DATE = '2026년 9월 24일'`
  - Perplexity `<tr>` 를 다음으로 교체:
    ```tsx
    <tr>
      <td>
        OpenAI, L.L.C.
        <br />
        <span className="text-gray-500">이전 국가: 미국</span>
        <br />
        <span className="text-gray-500">연락처: https://openai.com/policies</span>
      </td>
      <td>
        VCP 시그널의 보조 분석을 위해 종목명과 시세 지표를 전송합니다. 이용자의 개인정보는
        전송하지 않으며 AI 상담의 대화 내용도 전송하지 않습니다.
        <br />
        보유·이용 기간: 분석하는 동안 처리하며, 그 이후의 보관은 해당 사업자의 정책을
        따릅니다.
      </td>
    </tr>
    ```
  - `:278` `Perplexity 와 Z.ai 로 가는 VCP 분석은` → `OpenAI 와 Z.ai 로 가는 VCP 분석은`
- `dashboard/kr/vcp/page.tsx:552-557`, `aiHelpers.ts:3-15`: 주석을 「Perplexity 열은 [VCP-046] 이전 캐시(2026-02 등)에 판정이 있을 때만 나타난다」로 고친다. 로직은 바꾸지 않는다.

- [ ] **Step 4: 통과 확인**

Run: `venv/bin/python -m pytest tests/app/test_common_env_service.py -q && cd frontend && npm run test && npm run type-check && npm run lint`
Expected: 전부 PASS, 종료 코드 0

- [ ] **Step 5: 커밋**

```bash
git add services/common_env_service.py tests/app/test_common_env_service.py frontend/src/app && git diff --cached --check && git commit -m "feat(ui): [VCP-046] drop Perplexity key field and copy, list OpenAI as VCP processor"
```

### Task 6: 스크립트와 문서

**Files:**
- Delete: `scripts/test_perplexity_debug.py`, `scripts/test_perplexity_httpx.py`, `scripts/test_requests.py`, `scripts/test_vcp_dual_ai.py`(파일 전체가 Perplexity 통합 확인이다. 설계 §3.4 는 「부분 삭제」로 적었으나 남는 내용이 없어 삭제로 바꾼다)
- Modify: `scripts/llm_quality_harness.py:8, 43, 140, 245-305, 459-520, 567, 576`, `tests/verify_ai.py:55`
- Modify: `.env.example:77, 121-127`, `CLAUDE.md:9, 189, 292-296`, `AGENTS.md:240`, `README.md`(Perplexity 줄 전부), `deploy/README.md:26`, `docs/DEPLOYMENT_GUIDE.md:51-53`, `docs/vibe/ARCHITECTURE.md:9, 108, 193, 241, 258, 291, 419, 427`, `.claude/skills/dev-cycle/references/tier-rules.md:219-222`

- [ ] **Step 1: 스크립트**

- 위 네 파일을 `git rm` 한다. 먼저 `git grep -n -E 'test_perplexity_debug|test_perplexity_httpx|test_requests\.py|test_vcp_dual_ai'` 로 참조가 이력 문서뿐인지 확인한다.
- `llm_quality_harness.py`: `PERPLEXITY_CASES`, `perplexity_availability_probe`, `run_perplexity_iteration`, `main_async` 의 Perplexity 블록(`:496-520`), `--perplexity-iters` 인자와 `main_async` 의 `perplexity_iters` 매개변수, 머리 docstring 의 Perplexity 줄, `build_perplexity_request` import 를 지운다.
- `tests/verify_ai.py:55`: `"perplexity_recommendation": "Hold",` 줄 삭제.
- Run: `venv/bin/python -c "import ast,sys; [ast.parse(open(p).read()) for p in ['scripts/llm_quality_harness.py','tests/verify_ai.py']]" && venv/bin/python scripts/llm_quality_harness.py --help`
  Expected: 종료 코드 0, 도움말에 `--perplexity-iters` 없음(네트워크 호출 없음. `--help` 가 import 시점에 LLM 을 부르지 않는지 먼저 파일 머리를 읽어 확인하고, 부르면 `ast.parse` 만 한다)

- [ ] **Step 2: 설정 예시와 문서**

- `.env.example`: `PERPLEXITY_API_KEY` 줄과 `VCP_PERPLEXITY_MODEL`·`VCP_PERPLEXITY_API_TIMEOUT` 줄을 지운다. `VCP_AI_PROVIDERS` 주석은 `(gemini, gpt, zai)`, `VCP_SECOND_PROVIDER=gpt` 주석은 「두 번째 AI. gpt 만 지원한다. perplexity 는 [VCP-046] 에서 제거되어 gpt 로 실행된다」.
- `CLAUDE.md`: `:9` 「(Gemini 3.7 Flash, GPT via Z.ai, Perplexity)」를 「(Gemini 3.7 Flash, GPT with Z.ai fallback)」로 고친다. GPT(OpenAI)가 먼저 돌고 실패하면 Z.ai 로 넘어가는 실제 구조에 맞춘다. `:189` 예시 줄 삭제. `:292-296` 문단을 다음으로 바꾼다.
  > `VCP_AI_PROVIDERS` 와 `VCP_SECOND_PROVIDER` 는 `VCPMultiAIAnalyzer` 가 만들어질 때 한 번 읽혀 두 번째 AI 프로바이더를 확정합니다. 두 번째 자리는 GPT 하나이며, `[VCP-046]` 이후 perplexity 값은 경고와 함께 GPT 로 바뀝니다. 확정한 값은 실행 경로와 재분석 캐시 판정이 함께 씁니다. 그래서 `.env` 에서 이 값을 바꾸면 워커를 모두 재기동해야 반영됩니다. gunicorn 이 워커별로 이 값을 따로 확정하므로, 일부 워커만 재기동하면 같은 요청이 어느 워커에 닿느냐에 따라 다르게 동작합니다.
- `AGENTS.md:240`: 「Z.ai 와 Perplexity 가 빠른 배치를」 → 「GPT(실패 시 Z.ai)가 보조 검증을」.
- `README.md`: `git grep -n -i perplexity README.md` 의 각 줄을 「Gemini + GPT」 구조로 고치거나 지운다. 환경 변수 예시(`:99`, `:118-124`)는 `VCP_AI_PROVIDERS=gemini,gpt`, `VCP_SECOND_PROVIDER=gpt` 로, AI 역할 표(`:562`)의 Perplexity 행은 삭제, 폴백 설명(`:581-583`)은 GPT→Z.ai 폴백만 남기고 「과거 캐시(2026-02)의 `perplexity_recommendation` 은 읽기 전용으로 표시된다」 한 줄을 더한다.
- `deploy/README.md:26`: `VCP_PERPLEXITY_API_TIMEOUT` 를 목록에서 빼고 키 개수 문구를 맞춘다(주변 문장을 읽고 고친다).
- `docs/DEPLOYMENT_GUIDE.md:51-53`: `PERPLEXITY_API_KEY` 행 삭제, `VCP_AI_PROVIDERS` 예시를 `gemini,gpt` 로.
- `docs/vibe/ARCHITECTURE.md`: 각 줄에서 Perplexity 를 빼거나 GPT 로 바꾸고, `:241` 표의 행과 `:291` `perplexity` API 줄, `:419` 예시 줄을 삭제, `:427` 을 `gemini,gpt` 로.
- `tier-rules.md:219-222`: 「`resolve_perplexity_disabled` 가 그 분기의 입력을 만든다」 → 「`resolve_effective_second_provider` 가 그 분기의 입력을 만든다」.

- [ ] **Step 3: 확인**

Run: `git grep -n -i perplexity -- ':!docs/dev-cycle' ':!docs/superpowers/plans' ':!docs/superpowers/specs/2026-0[2-8]*' ':!docs/superpowers/specs/2026-09-0*' ':!tests/curl_output.json'`
Expected: 남는 것은 (1) 읽기 전용 칸과 그 주석(`engine/vcp_ai_orchestration_helpers.py`, `signal_tracker_ai_helpers.py`, `app/routes/kr_market_vcp_signal_helpers.py`, `services/kr_market_vcp_reanalysis_service.py`, `services/kr_market_ai_payload_service.py` 등), (2) `vcp_ai_provider_init_helpers.py` 의 perplexity 설정 처리와 경고, (3) frontend VCP 페이지·`aiHelpers.ts`·`lib/api.ts` 의 과거 캐시 표시, (4) `SettingsModal.tsx` 의 localStorage 정리 목록, (5) 테스트 fixture, (6) CLAUDE.md·README 의 제거 안내 문장, (7) 이번 설계 문서. 이 밖의 줄이 있으면 고친다.

- [ ] **Step 4: 커밋**

```bash
git add -A scripts tests/verify_ai.py .env.example CLAUDE.md AGENTS.md README.md deploy/README.md docs/DEPLOYMENT_GUIDE.md docs/vibe/ARCHITECTURE.md .claude/skills/dev-cycle/references/tier-rules.md && git diff --cached --check && git commit -m "docs(vcp): [VCP-046] remove Perplexity scripts and docs"
```

### Task 7: 전체 검증과 사이클 이후 단계

- [ ] **Step 1:** `venv/bin/python -m pytest -q` 전체, 종료 코드와 passed/skipped 수를 기록한다.
- [ ] **Step 2:** `cd frontend && npm run test && npm run type-check && npm run lint`, 종료 코드를 기록한다.
- [ ] **Step 3:** 리뷰: `/ponytail-review`(과잉설계) → `closing-bet-reviewer`(`Agent`, `name` 지정) → `/review`(T3 심층). 지적과 반영 여부를 TODO `[VCP-046]` 체크에 적는다.
- [ ] **Step 4:** QA 계획 `docs/dev-cycle/qa/VCP-046.md`(설계 §5): 하네스 필수 2건(perplexity 설정 → gpt 확정·경고, 재분석 필요 칸), 브라우저 필수 3건(과거 날짜 Perplexity 열 표시, 설정 모달 입력란 없음, 개인정보 5절 OpenAI 행). 격리 사본·격리 포트, 사본의 `secrets/`·`data/`·`.env` 는 지우고 필요한 캐시만 fixture 로 만든다.
- [ ] **Step 5:** 첫 커밋(구현은 Task 3~6 커밋, QA 계획과 TODO 진행 기록은 별도 커밋), QA 실행, 기록, 마감 아카이브.
