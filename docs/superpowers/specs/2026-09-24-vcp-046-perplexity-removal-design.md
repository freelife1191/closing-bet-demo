# [VCP-046] Perplexity 프로바이더 제거 설계

- 항목: `docs/dev-cycle/TODO.md` 의 `[VCP-046]`
- 티어: T3 (`engine/vcp_ai_*` 위험 경로, 프로바이더 선택과 캐시 칸이라는 인터페이스 변경)
- 경로: architectural (대화 설계 → 이 문서 → 구현 계획)
- 대화 설계 승인: 2026-09-24 12:46 사용자 「좋아 진행해」

## 1. 배경과 목표

사용자 지시(2026-09-24 11:43): 「Gemini 와 GPT 가 메인이어야 하고 Perplexity 는 이제 사용하지
않으므로 제거해도 된다」. 챗봇 요약은 `[CHAT-046]` 에서 먼저 Perplexity 를 뺐다. 이 항목은
나머지 코드·설정·화면·문서에서 Perplexity 를 **새로 호출하거나 설정하는 경로**를 모두 없앤다.

성공 조건:

1. 어떤 설정으로도 분석기가 Perplexity API 를 호출하지 않는다.
2. 운영 `.env` 에 perplexity 설정이 남아 있어도 두 번째 AI 는 GPT 로 동작하고 기동 로그에
   경고가 한 줄 남는다.
3. 과거 캐시(2026-02 등)의 `perplexity_recommendation` 은 VCP 화면과 수집 병합에서 지금처럼
   읽힌다.
4. 설정 화면에 Perplexity 키 입력란이 없고, 랜딩·VCP 기준 모달·개인정보 페이지가 실제로 쓰는
   사업자(Gemini·GPT(OpenAI)·Z.ai)와 일치한다.

## 2. 사용자 결정 (2026-09-24 대화)

| 질문 | 결정 |
|---|---|
| 과거 캐시의 Perplexity 판정 | 읽기 전용 표시 유지 |
| `VCP_SECOND_PROVIDER=perplexity`·`VCP_AI_PROVIDERS` 의 perplexity | GPT 로 대체하고 경고 |
| 개인정보 처리방침 5절 | Perplexity 행을 OpenAI 행으로 교체, 시행일 갱신 |

## 3. 설계

### 3.1 실행 경로 (백엔드)

- `engine/vcp_ai_analyzer.py`
  - 삭제: `_analyze_with_perplexity`, `_build_perplexity_fallback_chain`,
    `_resolve_perplexity_fallback_providers`, `_fallback_from_perplexity`,
    `perplexity_client`·`perplexity_disabled`·`perplexity_quota_exhausted`·
    `perplexity_blocked_reason`·`perplexity_fallback_providers` 상태.
  - `_expire_session_blocks` 와 그 로그에서 Perplexity 칸을 뺀다(Gemini·GPT·Z.ai 는 유지).
  - `get_available_providers` 에서 Perplexity 갈래를 뺀다.
  - 오케스트레이션 호출에서 `analyze_with_perplexity_fn` 인자를 뺀다.
  - GPT 실패 시 Z.ai 폴백은 그대로 둔다.
- `engine/vcp_ai_analyzer_helpers.py`: `build_perplexity_request`,
  `extract_perplexity_response_text`, `is_perplexity_quota_exceeded`,
  `classify_perplexity_error`, `_PERPLEXITY_QUOTA_KEYWORDS`·`_PERPLEXITY_AUTH_KEYWORDS` 삭제.
  다른 호출자가 없는지 구현 전에 grep 으로 확인한다.
- `engine/vcp_ai_orchestration_helpers.py`: `analyze_with_perplexity_fn` 인자와 perplexity
  갈래 삭제. 새 결과 dict 에는 `gemini_recommendation`·`gpt_recommendation` 두 칸만 둔다.
- `engine/vcp_ai_provider_init_helpers.py`
  - `resolve_perplexity_disabled` 삭제.
  - `resolve_effective_second_provider(providers, second_provider, logger)`: `perplexity` 는
    경고를 남기고 `gpt` 로 바꾼 뒤 기존 규칙(`gpt` 가 providers 에 있으면 `gpt`, 아니면 `None`
    과 경고)을 적용한다. `perplexity_disabled` 인자는 없앤다.
  - `normalize_provider_list` 는 이름 정규화만 하고, 분석기 생성자에서 `perplexity` 가 목록에
    있으면 경고를 남기고 뺀다(경고는 기동마다 한 번).
- `engine/config.py`: `PERPLEXITY_API_KEY`·`VCP_PERPLEXITY_MODEL`·`VCP_PERPLEXITY_API_TIMEOUT`
  속성 삭제. 다른 참조가 없는지 grep 으로 확인한다.

### 3.2 읽기 경로 (과거 캐시 호환)

- `VCP_AI_RECOMMENDATION_FIELDS` 는 세 칸을 유지하고, 세 번째 칸에 「과거 캐시 읽기 전용.
  [VCP-046] 이후 새로 쓰지 않는다」 주석을 붙인다. 이 목록을 읽는 legacy 보강
  (`app/routes/kr_market_vcp_signal_helpers.py`), 수집 병합(`_extract_vcp_ai_recommendation`,
  `scripts/init_data.py`), 페이로드(`services/kr_market_ai_payload_service.py`), 병합
  (`services/common_update_ai_analysis_service.py`), `signal_tracker` 우선순위는 바꾸지 않는다.
- 새로 쓰는 칸은 `VCP_AI_WRITTEN_FIELDS = VCP_AI_RECOMMENDATION_FIELDS[:2]` 로 이름을 붙여
  오케스트레이션이 쓴다.
- `services/kr_market_vcp_reanalysis_service.py`: 두 번째 칸 대응표에서 `perplexity` 를 뺀다.
  분석기의 확정 두 번째 프로바이더가 더는 perplexity 가 될 수 없다. 과거 날짜를 재분석하면
  GPT 칸이 비어 있는 행이 재분석 대상이 되며, 이는 관리자가 명시적으로 부르는 동작이므로
  허용한다.
- 챗봇은 `[CHAT-046]` 대로 Gemini·GPT 만 본다(변경 없음).

### 3.3 화면 (frontend)

- VCP 페이지(`dashboard/kr/vcp/page.tsx`·`aiHelpers.ts`): 데이터가 있을 때만 Perplexity 열·탭을
  보이는 현재 로직을 유지한다. 새 파일에는 칸이 없으므로 과거 날짜에서만 나타난다. 주석만
  「과거 캐시」로 고친다. `lib/api.ts` 타입도 유지한다.
- 설정 모달(`SettingsModal.tsx`): `PERPLEXITY_API_KEY` 입력란과 헤더 전송 목록의 해당 키 삭제.
  백엔드 `services/common_env_service.py` 의 `EDITABLE_ENV_KEYS` 에서도 뺀다. 운영 `.env` 에
  이미 있는 값은 건드리지 않으며 코드가 읽지 않는다.
- 랜딩(`app/page.tsx`)·VCP 기준 모달(`VCPCriteriaModal.tsx`): 「Gemini + GPT」 문구로 바꾸고
  Perplexity 카드·항목을 삭제한다.
- 개인정보 페이지(`(legal)/privacy/page.tsx`) 5절: Perplexity AI, Inc. 행을 OpenAI, L.L.C.
  (이전 국가 미국, VCP 보조 분석을 위해 종목명과 시세 지표 전송, 개인정보·AI 상담 내용 미전송)
  행으로 바꾸고, 거부 방법 문장의 「Perplexity 와 Z.ai」를 「OpenAI 와 Z.ai」로 고친다.
  `EFFECTIVE_DATE` 를 배포 예정일로 올린다. 날짜는 구현 계획에서 정한다.

### 3.4 스크립트·문서

- 삭제: `scripts/test_perplexity_debug.py`, `scripts/test_perplexity_httpx.py`,
  `scripts/test_requests.py`(세 파일 모두 Perplexity API 전용 수동 스크립트).
- Perplexity 부분만 삭제: `scripts/llm_quality_harness.py`, `scripts/test_vcp_dual_ai.py`,
  `tests/verify_ai.py`.
- 현행 설명 수정: `.env.example`, `CLAUDE.md`, `AGENTS.md`, `README.md`, `deploy/README.md`,
  `docs/DEPLOYMENT_GUIDE.md`, `docs/vibe/ARCHITECTURE.md`,
  `.claude/skills/dev-cycle/references/tier-rules.md`.
- 손대지 않음: `docs/dev-cycle/archive/`·`evidence/`·`qa/`·`reviews/`·`audits/`,
  `docs/superpowers/plans/`·과거 `specs/`, `tests/curl_output.json`(과거 응답 기록).

## 4. 테스트

- 추가
  - `resolve_effective_second_provider` 가 `perplexity` 를 `gpt` 로 바꾸고 경고를 남기며,
    providers 에 gpt 가 없으면 `None` 을 돌려준다.
  - 분석기 생성자가 `VCP_AI_PROVIDERS` 의 perplexity 를 빼고 경고를 남긴다.
  - 과거 캐시 행(`perplexity_recommendation` 만 유효)이 legacy 보강과
    `_extract_vcp_ai_recommendation` 에서 계속 읽힌다(기존 테스트가 이미 덮으면 그것을 근거로
    적는다).
  - 오케스트레이션 결과에 `perplexity_recommendation` 칸이 없다.
- 삭제: 대상 코드가 사라지는 Perplexity 전용 테스트(요청 구성·오류 분류·폴백 체인·
  `resolve_perplexity_disabled`). 무엇을 검사하던 테스트였는지 아카이브에 적는다.
- frontend: 설정 모달·개인정보 페이지 테스트의 기대값을 새 문구에 맞추고, `aiHelpers.test.ts`
  는 유지한다.
- 정적 검증: `venv/bin/python -m pytest` 전체, `frontend` 의 `npm run test`·`type-check`·`lint`.

## 5. QA

- 하네스(격리 사본, LLM 호출 없음): 분석기 생성자를 `VCP_SECOND_PROVIDER=perplexity`,
  `VCP_AI_PROVIDERS=gemini,perplexity,gpt` 로 만들었을 때 `second_provider == "gpt"` 와 경고,
  재분석 대상 판정이 `gpt_recommendation` 을 기다리는지 확인한다.
- 브라우저(agent-browser, 격리 포트, 원본 3500·5501 금지): 과거 날짜(Perplexity 판정이 있는
  사본 data)의 VCP 표에 Perplexity 열이 나오고, 최신 날짜에는 GPT 열이 나온다. 설정 모달에
  Perplexity 키 입력란이 없다. 개인정보 페이지 5절에 OpenAI 행이 있고 Perplexity 가 없다.
- 금지: 설정 저장, Refresh, AI 재분석 실행, 실제 LLM 호출.

## 6. 운영 영향

- 반영에는 gunicorn 워커 전부 재기동이 필요하다(장 중 금지). 일부 워커만 재기동하면 워커마다
  두 번째 프로바이더가 다를 수 있다.
- 운영 `.env` 에 perplexity 설정이 남아 있어도 GPT 로 동작한다. 운영자는 편한 때
  `PERPLEXITY_API_KEY`·`VCP_PERPLEXITY_*` 를 지우고 `VCP_SECOND_PROVIDER=gpt` 로 고치면 경고가
  사라진다.
