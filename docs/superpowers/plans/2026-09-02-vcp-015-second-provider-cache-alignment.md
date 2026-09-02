# [VCP-015] 두 번째 AI 프로바이더의 폴백 결과를 재분석 캐시 판정이 따라가게 한다

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 두 번째 AI 프로바이더를 확정하는 판정을 한 함수로 모아, 실행 경로와 재분석 캐시 판정이 같은 답을 보게 만든다.

**Architecture:** `[VCP-003]` 이 넣은 폴백은 `orchestrate_stock_analysis` 의 지역 변수만 바꿨다.
그래서 실행은 GPT 를 부르는데 캐시 판정은 설정값 그대로 Perplexity 를 기다린다.
판정을 `engine/vcp_ai_provider_init_helpers.resolve_effective_second_provider` 한 곳으로
끌어올리고, `VCPMultiAIAnalyzer.__init__` 이 그 결과를 `self.second_provider` 에 확정한다.
재분석 서비스는 설정값 대신 analyzer 가 확정한 값을 읽는다. 실행할 수 있는 두 번째
프로바이더가 없으면 `None` 이 되고, 그때는 캐시 판정에서 두 번째 열을 아예 보지 않는다.

**Tech Stack:** Python 3.11, pytest, Next.js 16.3.4 (프론트엔드 문구 한 줄)

**Spec:** `docs/dev-cycle/TODO.md` 의 `[VCP-015]` 항목

## Global Constraints

- 위험 경로 세 파일을 건드린다: `engine/vcp_ai_analyzer.py`,
  `engine/vcp_ai_orchestration_helpers.py`, `engine/vcp_ai_provider_init_helpers.py`.
  `tier-rules.md` §2 「VCP 판정」에 이미 등재되어 있으므로 §2 갱신은 필요 없다.
- 이 저장소의 `.env` 와 `.env.production` 은 `VCP_SECOND_PROVIDER=gpt`,
  `VCP_AI_PROVIDERS=gemini,gpt,z.ai`, `PERPLEXITY_API_KEY` 설정됨이다. 결함이 재현되는
  조합(`perplexity` + 키 없음)은 이 환경에 없으므로 검증은 pytest 로 한다.
- 새 프레임워크나 픽스처 계층을 들이지 않는다. 기존 `tests/**/test_*_refactor.py` 형식을 따른다.
- 실제 LLM API 호출을 일으키는 조작은 하지 않는다. 비용이 발생하고 사용자가 승인한
  자리가 아니다.

---

### Task 1: 두 번째 프로바이더 확정 함수

**Files:**
- Modify: `engine/vcp_ai_provider_init_helpers.py`
- Test: `tests/engine/test_vcp_ai_provider_init_helpers_refactor.py`

**Interfaces:**
- Produces: `resolve_effective_second_provider(providers, second_provider, perplexity_disabled, logger) -> str | None`
  — `"perplexity"`, `"gpt"`, 또는 실행할 수 없으면 `None`.

- [ ] **Step 1: 실패하는 검사를 먼저 쓴다**

```python
def test_resolve_effective_second_provider_falls_back_to_gpt():
    assert resolve_effective_second_provider(
        providers=["gemini", "gpt"],
        second_provider="perplexity",
        perplexity_disabled=True,
        logger=_Logger(),
    ) == "gpt"


def test_resolve_effective_second_provider_warns_when_nothing_can_run():
    logger = _Logger()
    assert resolve_effective_second_provider(
        providers=["gemini", "perplexity"],
        second_provider="perplexity",
        perplexity_disabled=True,
        logger=logger,
    ) is None
    assert len(logger.warnings) == 1
```

- [ ] **Step 2: 실패를 확인한다**

Run: `pytest tests/engine/test_vcp_ai_provider_init_helpers_refactor.py -q`
Expected: FAIL (ImportError: cannot import name 'resolve_effective_second_provider')

- [ ] **Step 3: 함수를 구현한다**

```python
def resolve_effective_second_provider(
    providers: list[str],
    second_provider: str | None,
    perplexity_disabled: bool,
    logger: Any,
) -> str | None:
    """실제로 실행할 두 번째 provider 를 확정한다. 실행할 수 없으면 None 을 돌려준다.

    Perplexity 를 쓸 수 없으면 GPT 로 넘긴다. 넘기지 않으면 두 번째 AI 열이 모든
    종목에서 빈 채로 남는다. 넘긴 뒤에도 실행할 수 없는 조합이면 경고를 남긴다.
    호출부가 이 값을 캐시 키 판정에도 쓰므로 실행 결과와 판정이 갈리지 않는다.
    """
    normalized_providers = normalize_provider_list(providers)
    provider = normalize_provider_name(second_provider)

    if provider == "perplexity" and perplexity_disabled:
        provider = "gpt"

    # perplexity 는 자체 폴백 체인(GPT·Z.ai)을 갖고 있어 providers 에 gpt 만 있어도 실행한다.
    if provider == "perplexity" and ("perplexity" in normalized_providers or "gpt" in normalized_providers):
        return "perplexity"
    if provider == "gpt" and "gpt" in normalized_providers:
        return "gpt"

    logger.warning(
        f"두 번째 AI Provider를 실행할 수 없습니다 "
        f"(VCP_SECOND_PROVIDER={second_provider}, VCP_AI_PROVIDERS={normalized_providers}). "
        f"VCP 표의 두 번째 AI 열이 비어 있게 됩니다."
    )
    return None
```

`__all__` 에 이름을 추가한다.

- [ ] **Step 4: 검사가 통과하는지 확인한다**

Run: `pytest tests/engine/test_vcp_ai_provider_init_helpers_refactor.py -q`
Expected: PASS

---

### Task 2: 오케스트레이터가 확정값만 받게 한다

**Files:**
- Modify: `engine/vcp_ai_orchestration_helpers.py`
- Modify: `engine/vcp_ai_analyzer.py`
- Test: `tests/engine/test_vcp_ai_orchestration_helpers_refactor.py`

**Interfaces:**
- Consumes: Task 1 의 `resolve_effective_second_provider`
- Produces: `orchestrate_stock_analysis` 에서 `perplexity_disabled` 인자가 사라지고
  `second_provider` 가 `str | None` 을 받는다. `VCPMultiAIAnalyzer.second_provider` 는
  원본 설정값이 아니라 확정값이다.

- [ ] **Step 1: 오케스트레이터의 폴백과 providers 판정을 걷어낸다**

```python
    # second_provider 는 resolve_effective_second_provider 가 확정한 값이다.
    # 실행할 수 없는 조합이면 None 이므로 두 번째 자리를 비운다.
    if not skip_second and second_provider == "perplexity":
        tasks.append(analyze_with_perplexity_fn(stock_name, stock_data, shared_prompt))
        providers_map.append("perplexity")
    elif not skip_second and second_provider == "gpt":
        tasks.append(analyze_with_gpt_fn(stock_name, stock_data, shared_prompt))
        providers_map.append("gpt")
```

시그니처에서 `perplexity_disabled: bool` 을 제거하고 `second_provider: str | None` 로 바꾼다.

- [ ] **Step 2: analyzer 가 확정값을 저장하게 한다**

`VCPMultiAIAnalyzer.__init__` 에서 `self.perplexity_disabled` 를 계산한 다음 줄에 넣는다.

```python
        configured_second_provider = normalize_provider_name(app_config.VCP_SECOND_PROVIDER)
        ...
        self.perplexity_disabled = resolve_perplexity_disabled(
            providers=self.providers,
            second_provider=configured_second_provider,
            has_api_key=bool(app_config.PERPLEXITY_API_KEY),
            logger=logger,
        )
        # 폴백까지 반영한 확정값. 재분석 서비스가 캐시 키를 정할 때 이 값을 읽는다.
        self.second_provider = resolve_effective_second_provider(
            providers=self.providers,
            second_provider=configured_second_provider,
            perplexity_disabled=self.perplexity_disabled,
            logger=logger,
        )
```

`analyze_stock` 의 `getattr(self, "second_provider", ...)` 폴백과 `perplexity_disabled=` 인자를
지우고 `second_provider=self.second_provider` 만 남긴다.

- [ ] **Step 3: 오케스트레이터 검사를 새 시그니처에 맞춘다**

`_run_second_provider_fallback` 헬퍼는 이제 폴백을 보지 않으므로 이름과 역할을 바꾼다.
Task 1 로 옮겨 간 검사 네 개는 지운다. 남기는 것은 오케스트레이터가 확정값을 그대로
따르는지 보는 검사다.

지우는 검사와 그 이유(아카이브에 적을 내용):
- `test_disabled_perplexity_falls_back_to_gpt` — 폴백 판정이 Task 1 로 옮겨 갔다
- `test_disabled_perplexity_without_gpt_and_without_gemini_warns` — 같음
- `test_disabled_perplexity_without_gpt_leaves_second_column_silently_empty` —
  고정하던 침묵을 Task 1 이 없앴다
- `test_non_perplexity_second_provider_is_not_rerouted_to_gpt` — 같음
- `test_available_perplexity_wins_over_gpt_when_both_are_listed` — 같음

- [ ] **Step 4: 검사가 통과하는지 확인한다**

Run: `pytest tests/engine/ -q`
Expected: PASS

---

### Task 3: 재분석 캐시 판정이 확정값을 읽게 한다

**Files:**
- Modify: `services/kr_market_vcp_reanalysis_service.py`
- Test: `tests/services/test_kr_market_vcp_service.py`

**Interfaces:**
- Consumes: `VCPMultiAIAnalyzer.second_provider` (Task 2 의 확정값, `str | None`)
- Produces: `collect_missing_vcp_ai_rows` 의 `second_recommendation_key` 가 `str | None` 을 받는다.

- [ ] **Step 1: 실패하는 검사를 먼저 쓴다**

```python
def test_reanalysis_cache_key_follows_analyzer_fallback(monkeypatch):
    """설정이 perplexity 이고 키가 없으면 캐시 판정도 gpt_recommendation 을 봐야 한다.

    설정값만 읽으면 perplexity_recommendation 을 기다리는데 폴백이 만든 결과는
    gpt_recommendation 에 담긴다. 그러면 second_missing 이 모든 종목에서 항상 참이 되어
    재분석을 부를 때마다 스코프 전체가 다시 호출된다.
    """
```

`_DummyAnalyzer` 에 `second_provider = "gpt"` 를 두고, 캐시에 `gpt_recommendation` 만 있는
종목이 재분석 대상에서 빠지는지 본다.

- [ ] **Step 2: 실패를 확인한다**

Run: `pytest tests/services/test_kr_market_vcp_service.py -q`
Expected: FAIL

- [ ] **Step 3: 서비스가 analyzer 의 값을 읽게 한다**

`execute_vcp_failed_ai_reanalysis` 에서 `analyzer = get_vcp_analyzer()` 를
`second_recommendation_key` 계산보다 앞으로 옮기고, 뒤쪽의 재호출을 지운다.
`get_vcp_analyzer` 는 싱글턴이므로 객체는 같다. 503 검사는 원래 자리에 남겨
대상이 0건일 때의 200 응답 순서를 바꾸지 않는다.

```python
        analyzer = get_vcp_analyzer()
        second_recommendation_key = (
            resolve_vcp_second_recommendation_key(analyzer.second_provider)
            if analyzer.second_provider
            else None
        )
```

두 번째 프로바이더를 실행할 수 없으면 `None` 이 되고, 그때는 채울 수 없는 열을
기다리지 않도록 판정에서 뺀다. 세 자리를 고친다.

- `load_vcp_ai_cache_map` 의 `required_recommendation_keys` — gemini 만 넣는다
- `collect_missing_vcp_ai_rows` — 키가 없으면 `second_missing` 을 보지 않는다
- `is_second_only` / `is_gemini_only` 를 가르는 `has_cached_second` — 키가 없으면
  기다릴 것이 없으므로 참으로 둔다

- [ ] **Step 4: 기존 더미 analyzer 여덟 곳에 속성을 추가한다**

`tests/services/test_kr_market_vcp_service.py` 의 `_DummyAnalyzer` 정의마다
`second_provider = "perplexity"` 를 넣는다. 지금 이 검사들은 `VCP_SECOND_PROVIDER=perplexity`
환경 변수에 기대고 있는데, 서비스가 더는 그 변수를 읽지 않는다.

- [ ] **Step 5: 검사가 통과하는지 확인한다**

Run: `pytest -q`
Expected: PASS

---

### Task 4: 기준표 모달의 환경 변수 이름을 바로잡는다

**Files:**
- Modify: `frontend/src/app/components/VCPCriteriaModal.tsx:89`

- [ ] **Step 1: 변수 이름을 고친다**

두 번째 프로바이더를 정하는 변수는 `VCP_AI_PROVIDERS` 가 아니라 `VCP_SECOND_PROVIDER` 다.
`VCP_AI_PROVIDERS` 는 허용 목록이고, 그중 어느 것을 두 번째로 쓸지는 `VCP_SECOND_PROVIDER` 가 정한다.

- [ ] **Step 2: 타입 검사와 vitest 를 돌린다**

Run: `cd frontend && npm run type-check && npx vitest run --reporter=basic`
Expected: PASS

---

## 하지 않는 것과 그 이유

- **백엔드가 고른 프로바이더를 응답에 실어 표 헤더가 따라가게 하는 작업.**
  `[VCP-003]` 의 QA 실측이 "표 헤더는 `GPT` 로 고정" 이라고 적었으나 그 관찰이 틀렸다.
  `frontend/src/app/dashboard/kr/vcp/page.tsx:1457` 은
  `secondaryAI === 'perplexity' ? 'Perplexity' : 'GPT'` 이고, `secondaryAI` 는
  `decideSecondaryAI(hasPerplexity, hasGpt)` 가 실제 응답 데이터를 보고 정한다.
  실측에서 `GPT` 로 보인 것은 그 화면의 데이터에 Perplexity 추천이 없었기 때문이다.
  프론트엔드는 이미 실제 프로바이더를 따라가므로 백엔드에서 이름을 실어 보낼 이유가 없다.
- **재분석 셀렉트의 `Second 강제` 이름 변경.** 이것은 프로바이더 이름이 아니라 실행 모드
  이름이다. 백엔드 `normalize_vcp_force_provider` 도 `second|secondary|2nd` 를 모드로 받는다.
  프로바이더 이름을 넣으면 설정이 바뀔 때마다 어긋난다.
- **GPT 레이트 리밋 실측.** 실제 LLM 호출이 필요해 비용이 발생한다. 캐시 판정을 고치면
  호출량이 정상 범위로 돌아온다는 것이 성능 리뷰의 판단이므로, 재분석 대상 산정이
  올바른지를 Task 3 의 pytest 로 대신 확인한다.

---

## 리뷰 결과 (구현 종료 시점 기록)

압축 지점을 넘어도 마감 보고에 쓸 수 있도록 여기 남긴다.

### 반영한 지적

- **ponytail-review 2건.** `second_only` 집계에 넣었던 `None` 가드를 도로 걷어냈다.
  `dict.get(None)` 이 `None` 을 돌려주고 뒤따르는 `isinstance` 가 그대로 거르므로 가드가
  하는 일이 없었다. 그리고 `keeps_available_perplexity` 검사의 `providers` 에서 `gpt` 를
  빼, `or` 의 두 갈래를 두 검사가 각각 덮게 했다.
- **feature-dev:code-reviewer 1건.** `force_provider="second"` 인데 두 번째 provider 를
  실행할 수 없으면 `get_available_providers()` 검사를 통과한 뒤 스코프 전체가 대상으로
  잡히고, 오케스트레이터가 아무 태스크도 만들지 못해 전 종목이 조용히 실패로 집계되었다.
  503 가드와 검사를 더했다.
- **유지보수성 스페셜리스트 1건(변형 반영).** 새 검사의 `monkeypatch.setenv` 가 죽은
  setup 이라는 지적이었는데, 지우고 M5 변이를 돌려 보니 검사가 통과해 버렸다.
  `VCP_SECOND_PROVIDER` 의 기본값이 `gpt` 라서 설정을 비우면 되돌린 코드도 같은 키를 본다.
  삭제 대신 지우면 안 되는 이유를 주석으로 적었다.
- **테스트 스페셜리스트 3건.** `__init__` 배선 검사 3개, `tasks` 공백 경고 검사 1개,
  키가 `None` 인 통합 경로 검사 1개를 더했다. 특히 두 번째가 정확했다. 이 사이클에서 지운
  검사가 그 경고 분기를 유일하게 덮고 있었다.

### 반영하지 않은 지적과 그 이유

- **성능 스페셜리스트: `get_vcp_analyzer()` 의 무잠금 싱글턴(신뢰도 5.5/10).**
  `threading.Lock` 을 넣지 않았다. 이번 변경이 만든 결함이 아니고, `__init__` 이 네트워크를
  타지 않아 경합해도 가벼운 객체가 중복 생성될 뿐이다. 스페셜리스트 본인도 급하지 않다고
  판단했다. CLAUDE.md 의 "의도한 지름길은 표시한다" 규칙대로 `ponytail:` 주석으로 한계와
  해소 조건만 남겼다.
- **Red Team: 워커별로 `second_provider` 가 다르게 고정된다(CRITICAL, 신뢰도 5.5/10).**
  TTL 캐시를 넣지 않았다. 워커별 편차는 이번 변경 이전에도 있었다. `perplexity_disabled` 가
  이미 `__init__` 시점에 고정되어 실행 경로를 정하고 있었고, 이번 변경은 캐시 판정을 그
  같은 고정값에 묶어 실행과 판정이 갈라지던 것을 붙였다. 배포 중 워커가 엇갈릴 때 나오는
  503 도 그전의 원인 불명 전패보다 낫다. 대신 Red Team 의 두 번째 제안을 받아 CLAUDE.md 에
  `.env` 를 바꾸면 워커를 모두 재기동해야 한다는 주의를 적었다.

### 변이 검사 열 갈래

각각 최소 한 건의 검사를 실패시켰다.

1. 폴백 줄 제거 → 2건
2. 미실행 경고 제거 → 2건
3. GPT 허용 목록 검사 제거 → 1건
4. `None` 키 가드 제거(단위) → 1건
5. 캐시 키를 `app_config` 로 되돌림 → 4건
6. 오케스트레이터의 GPT 분기 차단 → 6건
7. Second 강제 가드 제거 → 1건
8. `perplexity` 허용 목록 갈래 축소 → 1건
9. `__init__` 을 설정값 그대로 넣던 방식으로 되돌림 → 2건
10. `tasks` 공백 경고 제거 → 1건

### 지운 검사와 그 이유

`tests/engine/test_vcp_ai_orchestration_helpers_refactor.py` 에서 다섯 개를 지웠다. 모두
폴백 판정이 오케스트레이터 안에 있던 시절의 검사이고, 그 판정은
`resolve_effective_second_provider` 로 옮겨 갔다. 옮겨 간 자리의 새 검사 여섯 개가 같은
판정을 덮는다.

- `test_disabled_perplexity_falls_back_to_gpt`
- `test_disabled_perplexity_without_gpt_and_without_gemini_warns`
- `test_disabled_perplexity_without_gpt_leaves_second_column_silently_empty`
- `test_non_perplexity_second_provider_is_not_rerouted_to_gpt`
- `test_available_perplexity_wins_over_gpt_when_both_are_listed`

두 번째 것이 덮던 `tasks` 공백 경고 분기는 새 검사
`test_orchestrator_warns_when_no_provider_runs_at_all` 이 이어받는다.

### 검증 결과

- `pytest -q` → 1576 passed, 2 skipped
- `npm run type-check` → 오류 없음
- `npx vitest run` → 23파일 168건 통과, exit 0

### 남은 일

`/qa-only http://localhost:3500/dashboard/kr/vcp --quick` 을 돌린 뒤 [4] 마감으로 간다.
Flask 5501 과 Next.js 3500 은 응답을 확인했고 `browse` 도 빌드되어 있다.

`[VCP-015]` 의 체크박스 여섯 개 가운데 넷은 완료, 둘은 `[~]` 로 두었다. 다섯째(GPT 레이트
리밋 실측)는 실제 LLM 비용이 발생해 돌리지 않았고 재분석 대상 산정을 pytest 로 대신
확인했다. 여섯째(화면 이름 통일)는 전제가 틀렸다. 표 헤더는 고정이 아니라
`decideSecondaryAI` 가 응답 데이터를 보고 정한다. 남은 실질 불일치였던 기준표 모달의
환경 변수 이름은 이 사이클에서 고쳤고, 랜딩 페이지 두 문단은 `[FE-020]` 로 등록했다(처음 `[FE-017]` 로 적었으나 그 번호를 이미 쓰는 항목이 있어 마감 때 바꿨다).
