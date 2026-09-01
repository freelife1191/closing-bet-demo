# AUDIT-CHAT — 챗봇 감사

**감사 범위**: `chatbot/` (36개 파일, 7,401줄), `app/routes/kr_market_chatbot_routes.py`,
`app/routes/kr_market_chatbot_http_routes.py` (합계 362줄),
`frontend/src/app/chatbot/page.tsx` (1,718줄)

**읽은 파일 수**: 28개 / 총 9,481줄 (전문 22개, 구조 확인 6개)

**일련번호 근거**: `docs/dev-cycle/TODO.md` 와 `docs/dev-cycle/archive/` 어디에도 `CHAT` 약어를
쓰는 항목이 없습니다. `docs/superpowers/plans/2026-09-01-dev-cycle-system.md:700` 과
`.claude/agents/dev-workflow.md:80` 에 `CHAT-003` 이라는 문자열이 보이지만 둘 다 형식을
설명하는 예시일 뿐이고, `archive-format.md` §2 가 지정한 채번 대상(백로그와 아카이브)이
아닙니다. 따라서 이 리포트의 항목은 `CHAT-001` 부터 매깁니다.

**담당 경로 밖 관찰(참고용, 이 리포트에서 다루지 않음)**:
`services/kr_market_chatbot_stream_helpers.py:82` 는 SSE 청크에서 `usage_metadata` 를
기다리지만 챗봇 쪽이 그 키를 스트리밍 경로에서 한 번도 보내지 않습니다. 원인은 §1.2 에 있고
수정 지점도 챗봇 쪽입니다.

---

## 1. 깨진 동작

### 1.1 새 대화의 첫 응답 이후 다른 세션을 열면 이전 대화가 그대로 표시된다

- 위치: `frontend/src/app/chatbot/page.tsx:755-766`, `frontend/src/app/chatbot/page.tsx:406-417`
- 증상: 새 채팅에서 첫 질문을 보낸 뒤 사이드바에서 다른 세션을 클릭하면 그 세션의 대화가
  아니라 방금까지 보던 대화가 그대로 남습니다. 아울러 스트리밍이 진행되는 동안
  `/api/kr/chatbot/sessions` 요청이 델타마다 반복해서 발생합니다.
- 원인: `handleSend` 안의 SSE 루프가 비교에 쓰는 `currentSessionId` 는 이 함수가 만들어진
  시점의 렌더에 고정된 값입니다. 새 대화에서는 그 값이 계속 `null` 이므로,
  `services/kr_market_chatbot_stream_helpers.py:86` 이 모든 청크에 실어 보내는 `session_id`
  가 매번 `data.session_id !== currentSessionId` 를 만족합니다. 그 결과 세 가지가 함께
  일어납니다. 첫째로 `fetchSessions()` 가 청크 수만큼 호출됩니다. 둘째로 `else if
  (data.done)` 분기가 스트림이 끝날 때까지 한 번도 실행되지 않습니다. 셋째로
  `isCreatingSessionRef.current = true` 가 마지막 청크까지 다시 세워지는데, `setCurrentSessionId`
  는 같은 값이라 재렌더를 일으키지 않으므로 `useEffect` 가 그 플래그를 소비하지 못하고
  스트림이 끝난 뒤에도 `true` 로 남습니다. 이후 사용자가 다른 세션을 선택하면
  `page.tsx:408` 의 분기가 그 플래그를 보고 `fetchHistory` 를 건너뜁니다.
- 영향: 사용자에게 잘못된 대화 내용이 보입니다. 스트리밍 중 불필요한 세션 목록 요청이
  누적되어 응답 체감 속도도 함께 나빠집니다.

### 1.2 스트리밍 경로의 토큰 사용량이 항상 비어 있다

- 위치: `chatbot/chat_execution.py:78`, `chatbot/chat_execution.py:104`
- 증상: 활동 로그의 `token_usage` 가 실제 사용자 트래픽 전부에서 `{}` 로 남습니다.
- 원인: `run_stream_response` 는 `usage_metadata` 를 빈 딕셔너리로 초기화한 뒤 한 번도
  채우지 않고 그대로 반환합니다. 비스트리밍 경로인 `chat_execution.py:40` 이
  `extract_usage_metadata(response)` 를 호출하는 것과 대조됩니다. 그 결과
  `chatbot/chat_handlers.py:186` 의 `if usage_metadata:` 가 항상 거짓이 되어
  `usage_metadata` 이벤트 자체가 방출되지 않고, 이를 받아 적으려던
  `app/routes/kr_market_chatbot_http_routes.py:61` 의 `token_usage` 가 늘 비게 됩니다.
- 영향: 프런트엔드가 실제로 쓰는 경로는 SSE 스트리밍뿐이므로, 챗봇의 토큰 사용량 집계가
  사실상 전면 공백입니다. 비용 추적과 사용량 기반 판단의 근거가 사라집니다.

### 1.3 모든 슬래시 명령이 임시 명령으로 판정된다

- 위치: `chatbot/session_access.py:12`, `chatbot/session_access.py:15-25`
- 증상: `/clear`, `/model`, `/memory add` 같은 상태 변경 명령의 주고받은 내용이 대화
  히스토리에 남지 않습니다. 첫 메시지가 슬래시 명령이면 그 세션이 즉시 저장되지도 않습니다.
- 원인: 바로 위에 `_EPHEMERAL_COMMANDS = {"/status", "/help"}` 라는 상수가 선언되어 있는데
  함수 본문이 그 상수를 참조하지 않고 `stripped.startswith("/")` 만 검사합니다. 저장소
  전체에서 이 상수를 읽는 곳은 한 군데도 없습니다. 판정 결과는
  `chatbot/session_access.py:61` 의 `save_immediate` 와
  `chatbot/core_command_mixin.py:86` 의 히스토리 저장 여부를 동시에 좌우합니다.
- 영향: 사용자가 `/model` 로 모델을 바꾸거나 `/memory add` 로 메모리를 넣어도 대화 기록에
  흔적이 남지 않아, 나중에 그 세션을 다시 열었을 때 무엇을 했는지 확인할 수 없습니다.

### 1.4 의도 지시문이 종가베팅 질문에만 프롬프트에 실린다

- 위치: `chatbot/payload_service.py:103`
- 증상: 시장, 뉴스, VCP, 관심종목 질문에서 의도별 지시문이 모델에게 전달되지 않습니다.
- 원인: `build_content_parts` 가 `if jongga_context and intent_instruction:` 조건에서만
  지시문 섹션을 붙입니다. `jongga_context` 는 `chatbot/intent_context.py:53` 이 종가베팅
  의도일 때만 `True` 로 돌려주는 값입니다. 그런데 같은 파일의 `intent_context.py:57`,
  `intent_context.py:61`, `intent_context.py:65`, `intent_context.py:85` 는 나머지 네 의도에
  대해서도 지시문을 성실히 만들어 `build_additional_context` 까지 올려 보냅니다. 즉 다섯
  갈래 중 네 갈래의 지시문이 계산된 뒤 조용히 버려집니다.
- 영향: 의도별 답변 형식 유도가 종가베팅에서만 작동합니다. 나머지 의도에서는 지시문을
  만드는 코드가 전부 헛일이며, 어느 쪽이 의도한 동작인지 코드만 보고는 판단할 수 없습니다.
  참고로 `tests/chatbot/test_payload_service.py:97-104` 가 현재 동작을 그대로 못 박고 있으나,
  이 테스트는 사양에서 나온 것이 아니라 모듈 분할 리팩토링 커밋(`45ad2a6`)에서 현상을
  기록한 것입니다.

---

## 2. 중복

### 2.1 두 SQLite 캐시 모듈이 구조까지 같다

- 위치: `chatbot/runtime_stock_map_cache.py` (484줄), `chatbot/stock_context_cache.py` (465줄)
- 내용: 두 파일은 상수 집합과 함수 파이프라인이 접두어만 다를 뿐 동일합니다. 준비 상태
  조건 변수, 알려진 키 집합과 그 상한, 메모리 최대 엔트리, SQLite 최대 행 수, 타임아웃,
  재시도 횟수와 지연, 강제 프루닝 주기, 저장 카운터와 그 락이 하나씩 짝을 이룹니다. 함수도
  `_is_missing_table_error`(`runtime_stock_map_cache.py:110` 대 `stock_context_cache.py:101`),
  `_recover_*_schema`, `_ensure_*_sqlite`, `_save_*_memory_entry`, `_mark_*_seen`,
  `_should_force_*_prune`, `_load_*_from_sqlite`, `_save_*_to_sqlite`, `load_*`, `save_*`,
  `clear_*` 가 그대로 대응합니다. 실질적인 차이는 테이블 이름과 저장하는 페이로드의 모양뿐입니다.
- 영향: 949줄이 한 덩어리로 함께 움직여야 하는데 물리적으로 갈라져 있습니다. 스키마 복구
  로직이나 프루닝 조건을 한쪽에서만 고치면 다른 쪽이 조용히 어긋납니다. 공용 기반인
  `services/sqlite_utils.py` 가 이미 커넥션, 재시도, 프루닝, 누락 테이블 판별을 제공하므로
  2단 캐시 골격 자체를 그 위로 올릴 수 있습니다.

### 2.2 추론과 답변을 가르는 파서가 파이썬과 타입스크립트에 따로 있다

- 위치: `chatbot/markdown_utils.py:16-23`, `chatbot/markdown_utils.py:35-60`,
  `frontend/src/app/chatbot/page.tsx:187-188`, `frontend/src/app/chatbot/page.tsx:230`
- 내용: 백엔드는 `REASONING_START_REGEX` 와 `ANSWER_HEADER_REGEX` 로 `[추론 과정]` 과
  `[답변]` 헤더를 찾아 스트림을 `reasoning_chunk` 와 `answer_chunk` 로 이미 분리해서
  보냅니다(`chatbot/response_flow_stream.py:301-342`). 그런데 프런트엔드는 그 결과를 받아
  쓰면서도 `extractSuggestions` 안에서 `reasonStartRegex`, `reasonEndRegex`,
  `reasoningHeaderRegex` 라는 자체 정규식으로 같은 헤더를 한 번 더 해석합니다. 헤더 표기가
  바뀌면 두 파일을 동시에 고쳐야 합니다.
- 영향: 한쪽만 고치면 추론 영역이 답변에 섞이거나 답변이 통째로 숨습니다. 게다가
  `preprocessMarkdown` 과 `extractSuggestions` 는 `messages.map` 안에서 메모이제이션 없이
  호출되므로(`page.tsx:1364`, `page.tsx:1463`), 스트리밍 델타가 도착할 때마다 대화에
  있는 모든 메시지에 대해 열 개가 넘는 정규식 치환이 다시 실행됩니다.

---

## 3. 과잉 설계

### 3.1 프롬프트 모듈의 죽은 상수와 호출자 없는 래퍼

- 위치: `chatbot/prompts.py:184-254`, `chatbot/prompts.py:257-287`,
  `chatbot/core_data_access_mixin.py:53`, `chatbot/core_data_access_mixin.py:148`,
  `chatbot/core_payload_mixin.py:100`
- 내용: `INTENT_PROMPTS`(7개 의도, 71줄), `VCP_EXPERT_PERSONA`(22줄),
  `VCP_EXPERT_SUGGESTIONS`(7줄)를 읽는 코드가 저장소에 없습니다. `prompts.py` 305줄 가운데
  약 100줄이 이에 해당합니다. 정작 실제로 쓰이는 의도 지시문은
  `chatbot/intent_context.py` 와 `chatbot/intent_detail_service.py` 에 별도 문자열로 다시
  적혀 있어, 프롬프트 문구의 출처가 둘로 갈라져 있습니다. 래퍼 쪽에서는
  `_fetch_mock_data`(`data_service.get_cached_data` 가 모듈 함수를 직접 부르므로 래퍼는
  경유하지 않습니다), `_detect_stock_query_from_stock_map`(주석이 "사실상 단일 경로"라고
  스스로 밝히고 있습니다), `_fallback_response` 가 런타임 호출자 없이 테스트에서만
  불립니다.
- 영향: 프롬프트를 고치러 온 사람이 어느 문자열이 실제로 모델에 전달되는지 판단하는 데
  시간을 씁니다. 죽은 상수가 살아 있는 것처럼 보이면 잘못된 곳을 고칠 위험도 있습니다.

### 3.2 순수 위임 믹스인 계층과 레거시 호환 경로

- 위치: `chatbot/core_command_mixin.py` (182줄), `chatbot/core_data_access_mixin.py` (191줄),
  `chatbot/core_intent_context_mixin.py` (124줄), `chatbot/core_payload_mixin.py` (108줄),
  `chatbot/core_data_context_mixin.py` (20줄), `chatbot/core.py:27-37`,
  `chatbot/core.py:203-217`, `chatbot/core.py:77-88`, `chatbot/core.py:155-169`
- 내용: 믹스인 다섯 개 625줄은 거의 전부가 같은 이름의 `_impl` 함수를 그대로 호출하는
  한 줄짜리 메서드입니다. `core_data_context_mixin.py` 는 다른 믹스인 셋을 상속만 하는
  빈 클래스입니다. 레거시 쪽에는 `_CompatGenerativeModel` 셔임, `model_name` 인자가 올 때만
  타는 `_run_legacy_model_chat` 우회 경로, `DATA_DIR` 을 묶어 주기 위한
  `MemoryManager` / `HistoryManager` 재정의, 그리고
  `app/routes/kr_market_chatbot_http_routes.py:139-144` 의 `legacy_sync_mode` 가 있습니다.
  `close()` 는 클라이언트를 정리한 뒤에도 `__init__` 에서 옮겨 온 것으로 보이는 코드가
  남아 있어, 종료 시점에 종목 맵 CSV 를 다시 읽습니다(`core.py:168`).
- 영향: 호출 한 번을 따라가려면 믹스인과 서비스 모듈을 왕복해야 해서 흐름 파악이 느려집니다.
  `close()` 의 잔재는 프로세스 종료 경로에서 불필요한 파일 입출력을 일으킵니다.

---

## 4. 비대한 파일

### 4.1 챗봇 페이지 한 파일이 여덟 가지 책임을 진다

- 위치: `frontend/src/app/chatbot/page.tsx` (1,718줄)
- 내용: 한 파일이 마크다운 교정(`page.tsx:110-167`), 추론과 추천 질문 파싱
  (`page.tsx:169-243`), SSE 스트림 수신과 이벤트 분기(`page.tsx:676-785`), 세션 목록과
  히스토리 관리(`page.tsx:484-518`, `page.tsx:836-974`), 파일 첨부, 음성 인식
  (`page.tsx:986-1043`), 모달 다섯 종, 사이드바 두 벌(모바일과 데스크톱)을 모두 담고
  있습니다. 상태 훅만 20개가 넘습니다. 이 페이지는 사용자 입력과 브라우저 API 에 전면적으로
  의존하므로 `'use client'` 자체는 타당하며, 이 항목은 지시문이 말하는 과잉 설계가 아니라
  책임 분리 문제입니다.
- 영향: 1.1 처럼 SSE 분기 한 곳을 고치려 해도 파일 전체를 훑어야 합니다. 리렌더 범위도
  파일 전체가 되어 2.2 의 파서 재실행 비용을 키웁니다.

---

## 5. 검증 공백

### 5.1 챗봇 화면과 명령 판정에 회귀 테스트가 없다

- 위치: `frontend/src/app/chatbot/` (테스트 파일 없음),
  `tests/chatbot/test_session_access.py:47-51`, `tests/chatbot/test_chat_execution.py:152`,
  `tests/chatbot/test_chat_execution.py:176`
- 내용: `frontend/src/app/chatbot/` 아래에는 `page.tsx` 한 개뿐이고 테스트 파일이 없습니다.
  다른 화면에는 `page.regression-001.test.tsx`, `page.regression-004.test.tsx` 처럼 회귀
  테스트가 붙어 있는 것과 대비됩니다. 그래서 §1.1 의 세션 전환 결함과 §2.2 의 파서
  분기를 잡아낼 장치가 없습니다. 백엔드 쪽에서는
  `test_is_ephemeral_command_detects_lightweight_commands` 가 `/status` 와 `/help` 만
  확인하므로 `/clear` 나 `/model` 이 임시 명령으로 오판정되는 §1.3 을 통과시킵니다. 또한
  `test_chat_execution.py` 의 두 단언은 스트리밍 `usage_metadata` 가 `{}` 라는 사실을
  기대값으로 고정하고 있어 §1.2 를 결함이 아니라 사양처럼 보이게 만듭니다.
- 영향: 위 네 지점을 고칠 때 무엇이 통과 기준인지 코드가 알려주지 않습니다. 고친 뒤에도
  같은 자리가 다시 무너지는 것을 막을 수 없습니다.

---

## 요약

| 관점 | 발견 | 그중 P0 | P1 | P2 |
|---|---|---|---|---|
| 깨진 동작 | 4 | 1 | 3 | 0 |
| 중복 | 2 | 0 | 2 | 0 |
| 과잉 설계 | 2 | 0 | 0 | 2 |
| 비대한 파일 | 1 | 0 | 1 | 0 |
| 검증 공백 | 1 | 0 | 1 | 0 |
| **합계** | **10** | **1** | **7** | **2** |

---

# 2부: TODO 항목 초안

### [CHAT-001] 새 대화 스트리밍의 세션 전환 결함 수정
- 카테고리: 챗봇 | 티어: T2 | 근거: AUDIT-CHAT §1.1
- 티어 판정: 건드릴 파일은 `frontend/src/app/chatbot/page.tsx` 하나이고 `tier-rules.md` §2 의
  위험 경로에 닿지 않습니다. SSE 수신 블록(`page.tsx:676-785`)의 구조와 세션 전환
  `useEffect`(`page.tsx:406-417`)를 함께 손봐야 하므로 60줄에서 90줄 사이로 봅니다.
- [ ] SSE 루프의 세션 비교를 렌더 고정 값 대신 최신 값을 보는 방식으로 교체
- [ ] 세션 갱신 분기와 `done` 분기를 서로 배타적이지 않게 분리
- [ ] `isCreatingSessionRef` 가 스트림 종료 후 남지 않도록 소비 시점 정리
- [ ] 스트리밍 중 `fetchSessions()` 가 세션이 실제로 바뀔 때만 호출되는지 확인
- [ ] 회귀 테스트 추가 (`page.regression-*.test.tsx` 관례를 따름)

### [CHAT-002] 계산해 놓고 버려지는 세 값 복구
- 카테고리: 챗봇 | 티어: T2 | 근거: AUDIT-CHAT §1.2, §1.3, §1.4
- 티어 판정: `chatbot/chat_execution.py`, `chatbot/chat_handlers.py`,
  `chatbot/payload_service.py`, `chatbot/intent_context.py`, `chatbot/session_access.py` 는
  모두 위험 경로 밖입니다. 세 건 합계 150줄에서 250줄로 봅니다.
- [ ] 스트리밍 응답에서 `usage_metadata` 를 실제로 수집해 이벤트로 방출
- [ ] 의도 지시문을 종가베팅 외 네 의도에도 실을지, 네 의도의 지시문 생성을 걷어낼지 결정하고
      한쪽으로 통일
- [ ] `is_ephemeral_command` 가 `_EPHEMERAL_COMMANDS` 를 실제로 참조하도록 수정
- [ ] `tests/chatbot/test_chat_execution.py` 의 `usage_metadata == {}` 단언 갱신
- [ ] `tests/chatbot/test_payload_service.py:97` 의 지시문 테스트를 결정된 사양에 맞게 갱신
- [ ] `/clear`, `/model` 이 히스토리에 남는지 확인하는 회귀 테스트 추가

### [CHAT-003] 두 SQLite 캐시 모듈을 공용 골격으로 통합
- 카테고리: 챗봇 | 티어: T3 | 근거: AUDIT-CHAT §2.1
- 티어 판정: 949줄을 다루므로 300줄을 확실히 넘습니다. 공용 골격을
  `services/sqlite_utils.py` 에 두는 방안을 택하면 파일명에 `sqlite` 가 들어가 위험 경로에도
  닿으므로, 어느 쪽으로 가든 `T3` 입니다.
- [ ] 두 모듈의 실제 차이(테이블 이름, 페이로드 모양, 서명 계산)를 목록으로 확정
- [ ] 2단 캐시 골격을 한 곳으로 모으고 차이 부분만 주입받도록 정리
- [ ] `runtime_stock_map_cache` 와 `stock_context_cache` 의 공개 함수 시그니처 유지
- [ ] 기존 두 회귀 테스트가 그대로 통과하는지 확인
- [ ] 스키마 복구와 프루닝 동작이 양쪽에서 동일한지 검증하는 테스트 추가

### [CHAT-004] 챗봇 페이지 분할과 응답 파서 단일화
- 카테고리: 챗봇 | 티어: T3 | 근거: AUDIT-CHAT §2.2, §4.1, §5.1
- 티어 판정: 1,718줄 파일을 쪼개므로 300줄을 넘습니다. 선행 조건으로 `[CHAT-001]` 이
  끝나 있어야 합니다. 같은 SSE 블록을 두 항목이 동시에 건드리면 충돌합니다.
- [ ] 마크다운 교정과 추론·추천 질문 파싱을 별도 모듈로 분리
- [ ] 백엔드가 이미 나눠 보내는 `reasoning_chunk` / `answer_chunk` 를 신뢰하고, 프런트의
      중복 헤더 파싱 범위를 히스토리 복원 경로로 한정
- [ ] SSE 수신, 세션 관리, 음성 입력을 각각 훅이나 컴포넌트로 분리
- [ ] 파서 호출을 메모이제이션해 스트리밍 중 전체 메시지 재파싱을 제거
- [ ] 분리한 파서와 SSE 처리에 vitest 테스트 추가

### [CHAT-005] 죽은 프롬프트 상수와 레거시 경로 정리
- 카테고리: 챗봇 | 티어: T2 | 근거: AUDIT-CHAT §3.1, §3.2
- 티어 판정: 삭제 위주이며 위험 경로에 닿지 않습니다. 170줄에서 250줄 사이로 보지만,
  구현 후 `git diff --stat` 이 300줄을 넘으면 `tier-rules.md` §3-6 에 따라 `T3` 으로
  올립니다. 위임 믹스인 다섯 개를 평탄화하는 작업은 규모가 따로여서 이 항목에 넣지
  않았습니다.
- [ ] `INTENT_PROMPTS`, `VCP_EXPERT_PERSONA`, `VCP_EXPERT_SUGGESTIONS` 제거
- [ ] 호출자 없는 래퍼 세 개(`_fetch_mock_data`, `_detect_stock_query_from_stock_map`,
      `_fallback_response`) 처리 방향 결정 후 정리
- [ ] `close()` 에 남은 초기화 잔재 제거 (종료 시 종목 맵 재로드 중단)
- [ ] `_CompatGenerativeModel` 과 `_run_legacy_model_chat` 이 아직 필요한지 확인 후 정리
- [ ] 삭제한 심볼을 참조하던 테스트 정리 및 pytest 전체 통과 확인
