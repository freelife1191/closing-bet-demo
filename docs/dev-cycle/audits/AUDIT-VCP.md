# AUDIT-VCP — VCP 시그널 감사

**감사 범위**: `engine/vcp_ai_analyzer.py`, `engine/vcp_ai_analyzer_helpers.py`,
`app/routes/kr_market_vcp_signal_helpers.py`, `frontend/src/app/dashboard/kr/vcp/`
**읽은 파일 수**: 담당 경로 10개 / 4,971줄. 호출 관계를 확인하기 위해 인접 파일
5개(`engine/vcp_ai_orchestration_helpers.py`, `engine/vcp_ai_provider_init_helpers.py`,
`services/kr_market_vcp_payload_service.py`, `services/kr_market_vcp_service.py`,
`app/routes/kr_market_signal_common.py`) 약 600줄을 함께 읽었습니다.

**감사일**: 2026-09-01 | **기준 커밋**: `a1470fd`

## 범위에 관한 주의 사항

`archive-format.md` §2 표가 지정한 VCP 담당 경로는 세 갈래입니다. 다만 실제 VCP 응답을
만드는 `services/kr_market_vcp_*.py` 여섯 파일은 어느 카테고리의 담당 경로에도 잡히지
않습니다. 이번 감사에서는 담당 경로 안의 함수가 어디에서 호출되는지 확인하는 목적으로만
읽었고, 지적은 모두 담당 경로에 속한 파일을 대상으로 적었습니다. 표의 빈칸 자체는 인프라
카테고리에서 다룰 사안이므로 여기서는 사실만 남깁니다.

`engine/vcp_ai_orchestration_helpers.py` 와 `engine/vcp_ai_provider_init_helpers.py` 는
`engine/vcp_ai_analyzer*` 라는 표의 표기와 정확히 일치하지는 않습니다. 그러나 두 파일은
`vcp_ai_analyzer.py` 가 자기 메서드 본문을 그대로 옮겨 놓은 분리 모듈이므로 같은 책임
덩어리로 보고 감사 대상에 포함했습니다.

---

## 1. 깨진 동작

### 1.1 AI 분석에 실패한 종목이 화면에 "관망" 추천으로 표시된다

- 위치: `app/routes/kr_market_vcp_signal_helpers.py:171-185`,
  `app/routes/kr_market_vcp_signal_helpers.py:123-125`,
  `frontend/src/app/dashboard/kr/vcp/page.tsx:923-944`
- 증상: AI 재분석이 실패한 종목이 VCP 표에서 노란색 `■ 관망` 배지를 답니다. 사용자는 이
  배지를 정상적으로 산출된 AI 의견으로 읽게 되지만, 실제로는 분석이 실패했다는 사실만
  기록되어 있는 상태입니다.
- 원인: 재분석이 실패하면 `_apply_vcp_reanalysis_updates` 가 `ai_action` 에 `"N/A"` 를,
  `ai_reason` 에 `"분석 실패"` 를 기록합니다(`:123-125`). 그런데 응답을 만드는
  `_build_vcp_gemini_recommendation` 은 `if not ai_action or not ai_reason` 만 검사하므로
  (`:177`), 두 값이 모두 비어 있지 않은 이 행을 정상으로 판정하고
  `gemini_recommendation` 객체를 만들어 냅니다. 프론트엔드의 `getAIBadge` 는 추천 객체가
  존재하면 배지를 그리고, `action` 이 `BUY` 도 `SELL` 도 아니면 기본값인 `관망` 을
  적용합니다(`page.tsx:926-938`).
- 같은 파일 `:30-48` 에 `_is_vcp_ai_analysis_failed` 가 있고, 이 함수는
  `_VALID_AI_ACTIONS` 와 `_is_meaningful_ai_reason` 으로 정확히 이 상황을 걸러냅니다.
  `_INVALID_AI_REASONS` 집합에 `"분석 실패"` 가 이미 들어 있습니다
  (`app/routes/kr_market_signal_common.py:12-29`). 판별 함수가 있는데도 응답 생성 경로가
  그 함수를 쓰지 않는 것이 원인입니다.
- 영향: 사용자가 잘못된 투자 신호를 봅니다. 실패한 분석과 실제로 관망 의견이 나온 분석을
  화면에서 구별할 수 없습니다.

### 1.2 조회 날짜를 바꾸면 현재가 갱신이 이전 목록의 종목을 조회한다

- 위치: `frontend/src/app/dashboard/kr/vcp/page.tsx:563-604`
- 증상: 히스토리 날짜를 선택해 다른 날짜의 시그널을 불러온 뒤에도, 현재가 갱신 요청이
  이전 목록의 종목 코드를 계속 조회합니다. 새로 불러온 종목의 현재가와 수익률이 1분
  주기 갱신에서 빠집니다.
- 원인: 이 `useEffect` 의 의존성 배열이 `[signals.length, loading]` 입니다(`:604`).
  그런데 본문은 `signals.map(s => s.ticker)` 로 배열의 내용을 읽습니다(`:568`). 목록이
  통째로 교체되어도 길이가 같으면 effect 가 다시 실행되지 않아, 클로저가 이전 목록을
  계속 붙들고 있습니다. 목록 상한이 20으로 고정되어 있어서
  (`app/routes/kr_market_vcp_signal_helpers.py:245`,
  `services/kr_market_vcp_payload_service.py:63`) 길이가 일치하는 상황은 드물지 않습니다.
- `vercel-react-best-practices` 의 `rerender-dependencies` 규칙에 해당합니다. 원시값을
  의존성으로 쓰는 것 자체는 권장 사항이지만, 본문이 읽는 값과 어긋나면 안 됩니다.
- 영향: 장중에 화면을 열어 둔 사용자가 낡은 현재가와 수익률을 봅니다.

### 1.3 두 번째 프로바이더가 Perplexity 인데 키가 없으면 GPT 로 넘어가지 않는다

- 위치: `engine/vcp_ai_orchestration_helpers.py:45-51`
- 증상: `VCP_SECOND_PROVIDER=perplexity` 이고 `PERPLEXITY_API_KEY` 가 비어 있으면,
  `VCP_AI_PROVIDERS` 에 `gpt` 가 들어 있어도 두 번째 AI 분석이 통째로 실행되지 않습니다.
  VCP 표의 두 번째 AI 열이 모든 종목에서 비어 버립니다.
- 원인: `if` 절의 조건이 `("perplexity" in providers or "gpt" in providers)` 로
  되어 있어 `gpt` 를 이미 허용 대상에 넣어 두었습니다(`:45`). 그런데 그 안에서
  `perplexity_disabled` 이면 아무 task 도 추가하지 않고 끝나며, `elif` 로 이어지는
  GPT 분기까지 내려가지 않습니다(`:46-51`). `resolve_perplexity_disabled` 는 키가 없으면
  `True` 를 돌려주므로(`engine/vcp_ai_provider_init_helpers.py:122-125`), 키가 없는
  환경에서는 항상 이 경로를 탑니다.
- `engine/config.py:199` 의 `VCP_SECOND_PROVIDER` 기본값은 `gpt` 이지만,
  `.env.example:69` 는 `perplexity` 를 권장 값으로 적어 두었습니다. 두 문서가 어긋나
  있어서 실제로 이 조합이 만들어지기 쉽습니다.
- 영향: 두 번째 AI 의견이 화면에서 사라집니다. 프론트엔드의 `decideSecondaryAI` 는 이
  경우 안전 기본값인 `'gpt'` 를 고르므로(`frontend/.../aiHelpers.ts:16`), 빈 GPT 열이
  그대로 렌더링됩니다.

---

## 2. 중복

### 2.1 `vcp_ai_analyzer.py` 안에서 같은 코드가 세 벌, 네 벌씩 복제되어 있다

- 위치: `engine/vcp_ai_analyzer.py:152-168`, `:380-395`, `:842-857` (상태 코드 추출),
  `:120-135`, `:139-150`, `:927-941`, `:1034-1045` (JSON 출력 규약 프롬프트)
- 증상: HTTP 상태 코드를 예외 객체에서 꺼내는 로직이 메서드 하나와 지역 함수 두 개로
  세 벌 존재합니다. `:152-168` 과 `:380-395` 는 글자까지 동일하고, `:842-857` 은
  `code` 속성만 빠져 있습니다. 같은 파일의 세 사본 가운데 하나만 다르다는 사실 자체가
  이미 한쪽만 고쳐진 흔적입니다.
- 함께: `action`, `confidence`, `reason` 세 키의 출력 규약을 지시하는 시스템 프롬프트가
  GPT 본분석, GPT 보정, Z.ai 본분석, Z.ai 보정 네 곳에 각각 적혀 있습니다. `reason` 의
  최소 글자 수(90자)와 섹션 구조 지시가 네 곳에 흩어져 있어서, 규약을 한 번 바꾸려면
  네 곳을 모두 고쳐야 합니다.
- 영향: `_extract_status_code` 는 재시도 여부와 세션 차단 여부를 가르는 판정에 쓰이므로,
  세 사본이 어긋나면 프로바이더마다 다른 기준으로 차단됩니다.

### 2.2 마크다운 전처리기가 세 파일에 복제되어 있다

- 위치: `frontend/src/app/dashboard/kr/vcp/page.tsx:51-108`,
  `frontend/src/app/chatbot/page.tsx:110`, `frontend/src/app/components/ChatWidget.tsx:27`
- 증상: 한글과 마크다운 강조 표기가 붙어 나오는 문제를 고치는 `preprocessMarkdown` 이
  세 파일에 각각 정의되어 있습니다. 아홉 단계 정규식 치환이 통째로 복제된 형태입니다.
  `parseAIResponse` 도 `page.tsx:110-180` 과 `ChatWidget.tsx:86` 두 곳에 있습니다.
- 영향: AI 응답의 표기 오류를 고칠 때 세 곳을 함께 고치지 않으면 화면마다 다른 결과가
  나옵니다. 세 파일이 각각 VCP, 챗봇, 프론트엔드 공통 카테고리에 속해 있어서, 어느 한
  카테고리의 사이클에서 고치면 나머지 두 곳이 남습니다.

---

## 3. 과잉 설계

### 3.1 Perplexity 폴백 경로에 실행되지 않는 코드가 세 군데 있다

- 위치: `engine/vcp_ai_analyzer.py:1254-1269`, `:1170-1187`, `:1164-1167`, `:837`
- `_fallback_to_zai` (`:1254-1269`)는 "하위 호환용" 이라는 설명이 붙어 있으나 저장소
  전체에서 호출하는 곳이 없습니다. 테스트도 이 메서드를 부르지 않습니다.
- `_resolve_perplexity_fallback_providers` (`:1170-1187`)는 어떤 경로로 들어와도
  `self.perplexity_fallback_providers` 와 같은 값을 돌려줍니다. `__init__:109` 가
  `_build_perplexity_fallback_chain()` 의 결과를 그 속성에 넣기 때문에 `configured` 는
  항상 채워져 있고, 비교 대상인 `allowed_chain` 도 같은 함수가 만든 같은 목록입니다.
  결국 자기 자신을 자기 자신으로 거르는 필터입니다.
- `_build_perplexity_fallback_chain` 의 마지막 루프(`:1164-1167`)는 `gpt` 와 `zai` 만
  대상으로 삼는데, 그 두 키는 바로 앞의 두 `if` 문이 이미 추가했습니다. 이 루프는 한
  번도 항목을 추가하지 못합니다.
- `_analyze_with_zai` 의 `max_parse_attempts = 1` (`:837`)은 상수이므로 그 아래
  `for attempt in range(max_parse_attempts)` 는 항상 한 번만 돕니다. 재시도 횟수에 따라
  타임아웃을 늘리려던 `attempt_timeout = request_timeout + (attempt * 20.0)` (`:866`)도
  함께 죽어 있습니다.
- 영향: 폴백 경로를 읽는 사람이 실제로 동작하는 분기를 가려내는 데 시간을 씁니다.
  다음에 폴백 순서를 바꿀 때 죽은 코드를 고치고 동작이 바뀌지 않는 상황이 생깁니다.

### 3.2 헬퍼 열 개를 인자로 주고받는 주입 계층이 겹겹이 쌓여 있다

- 위치: `app/routes/kr_market_vcp_signal_helpers.py` 전체,
  `services/kr_market_vcp_payload_service.py:24-40`,
  `app/routes/kr_market_data_signals_routes.py:121-136`
- 증상: `_build_vcp_signals_from_dataframe`, `_sort_and_limit_vcp_signals`,
  `_build_ai_data_map` 등 담당 경로의 함수 여섯 개가 직접 호출되지 않습니다. 대신
  `kr_market_signal_helpers.py` 와 `kr_market_helpers.py` 두 층에서 재수출된 뒤
  `kr_market_dependency_builders.py` 가 만드는 `deps` 사전에 담기고, 라우트가 그 사전에서
  꺼내 `build_vcp_signals_payload` 에 열 개의 `Callable` 인자로 전달합니다.
- 각 이름의 구현체는 하나뿐이며, 다른 구현으로 바꿔 끼우는 호출자는 프로덕션 코드에
  존재하지 않습니다. 테스트도 모듈을 직접 import 해서 씁니다
  (`tests/app/test_kr_market_vcp_signal_helpers_refactor.py:9`).
- 함께: `_resolve_total_scanned_stocks_count` 는 인자를 받는 호출과 받지 않는 호출을
  `TypeError` 로 구분하는 하위 호환 분기를 두고 있고
  (`kr_market_vcp_payload_service.py:104-110`), `load_json_file` 호출도 같은 방식의
  분기를 두 번 반복합니다(`:255-258`, `:279-282`). 어느 쪽도 실제로 두 가지 시그니처가
  공존하지는 않습니다.
- 영향: 함수 하나의 동작을 따라가려면 파일 다섯 개를 거쳐야 합니다. 1.1 의 결함이
  오래 남아 있던 것도 응답 생성 경로가 이만큼 흩어져 있는 것과 무관하지 않습니다.

---

## 4. 비대한 파일

### 4.1 `page.tsx` 한 파일이 아홉 가지 책임을 지고 있다

- 위치: `frontend/src/app/dashboard/kr/vcp/page.tsx` (2,110줄)
- 한 파일 안에 다음이 모두 들어 있습니다. 시그널 목록 적재와 현재가 폴링(`:563-654`),
  마켓 게이트 조회(`:554-561`), 스크리너 실행과 진행 폴링(`:1188-1270`), 실패 AI
  재분석의 실행·중지·폴링(`:456-499`, `:669-708`), 차트 모달(`:842-869`), 챗봇 스트리밍과
  히스토리 관리(`:949-1127`, `:271-387`), 일괄 매수(`:719-840`), 날짜 히스토리
  전환(`:450-454`, `:656-667`), 마크다운 전처리 유틸(`:51-180`).
- 함께: `checkRunningStatus` 가 만드는 `setInterval` 핸들(`:531`)은 어떤 ref 에도 담기지
  않습니다. 언마운트 정리(`:501-505`)는 `clearReanalysisPolling` 만 부르므로, 사용자가
  다른 화면으로 이동해도 이 폴링은 2초마다 계속 돕니다. 책임이 한 파일에 몰려 있어서
  정리 대상이 빠진 것을 알아채기 어려운 구조입니다.
- 무거운 의존성을 모두 정적으로 import 합니다. `lightweight-charts`
  (`StockChart.tsx:3`), `react-markdown` 과 `remark-gfm`(`page.tsx:10-11`)은 모달을 열
  때만 쓰이는데도 첫 화면 번들에 포함됩니다. 저장소에 `next/dynamic` 사용 선례가
  있습니다(`frontend/src/app/components/StockTradeHistoryModal.tsx:4`).
  `vercel-react-best-practices` 의 `bundle-dynamic-imports` 규칙에 해당합니다.
- `'use client'` 자체는 타당합니다. 이 컴포넌트는 `useState` 와 `useEffect`, 브라우저
  API 를 쓰므로 서버 컴포넌트로 둘 수 없습니다. 다만 지금은 화면 전체가 하나의 클라이언트
  컴포넌트라서 경계를 리프로 밀 여지가 남아 있습니다.

### 4.2 `vcp_ai_analyzer.py` 는 이미 세 번 쪼갠 뒤에도 1,308줄이다

- 위치: `engine/vcp_ai_analyzer.py`
- 헬퍼를 세 파일로 분리했는데도 본체가 다음 책임을 함께 지고 있습니다. 프로바이더 네
  종류의 호출 로직(Gemini `:357-463`, GPT `:465-626`, Perplexity `:651-795`,
  Z.ai `:797-1152`), OpenAI 호환 API 의 파라미터 협상(`:184-315`), 시스템 프롬프트
  문안(`:118-150`), 오류 분류(`:152-182`), 폴백 체인 결정(`:1154-1269`), 배치 파사드
  (`:1271-1284`), 싱글톤(`:1300-1308`).
- `_analyze_with_zai` 한 메서드가 356줄입니다(`:797-1152`). 그 안에 지역 함수 두 개,
  모델 루프와 파싱 루프의 이중 중첩, 에코 응답 재시도, JSON 보정 재요청, 규칙 기반
  폴백이 모두 들어 있습니다.
- 영향: 이 파일은 `tier-rules.md` §2 의 위험 경로이므로 어느 줄을 고치든 T3 입니다.
  한 곳을 고치기 위해 치르는 비용이 파일 크기에 비례해 커집니다.

---

## 5. 검증 공백

### 5.1 응답을 만드는 라우트 헬퍼 다섯 개에 대응 테스트가 없다

- 위치: `app/routes/kr_market_vcp_signal_helpers.py:103-137`, `:171-185`, `:256-268`,
  `:271-290`, `:293-312`
- 테스트가 없는 함수는 다음과 같습니다. `_apply_vcp_reanalysis_updates`(재분석 결과 반영
  분기), `_build_vcp_gemini_recommendation`(1.1 의 결함이 있는 바로 그 함수),
  `_build_ai_data_map`, `_merge_legacy_ai_fields_into_map`, `_merge_ai_data_into_vcp_signals`.
  다섯 함수 모두 조건 분기를 담고 있습니다.
- 이 파일을 대상으로 삼는 테스트는 세 건뿐이며
  (`tests/app/test_kr_market_vcp_signal_helpers_refactor.py`), 셋 다
  `_sort_and_limit_vcp_signals` 와 `_build_vcp_signal_from_row` 의 점수 문턱만 봅니다.
- 대조: 같은 카테고리의 `_analyze_with_zai` 한 메서드에는
  `tests/engine/test_vcp_ai_analyzer_refactor.py` 의 테스트 12건이 붙어 있으며, 이 파일
  전체로는 27건입니다. 검증 밀도가 파일마다 크게 어긋나 있으며, 정작 사용자에게 보이는
  값을 만드는 쪽이 비어 있습니다.
- 프론트엔드에서는 `getAIBadge`(`page.tsx:906-945`)의 action 분기에 테스트가 없습니다.
  `decideSecondaryAI` 와 `calculateSMA` 는 각각 테스트를 가지고 있습니다.
- 영향: 1.1 의 결함이 회귀 테스트 없이 남아 있었고, 고친 뒤에도 같은 자리가 다시 깨질
  때 알아챌 방법이 없습니다.

---

## 요약

| 관점 | 발견 | 그중 P0 | P1 | P2 |
|---|---|---|---|---|
| 깨진 동작 | 3 | 1 | 2 | 0 |
| 중복 | 2 | 0 | 1 | 1 |
| 과잉 설계 | 2 | 0 | 0 | 2 |
| 비대한 파일 | 2 | 0 | 1 | 1 |
| 검증 공백 | 1 | 0 | 1 | 0 |
| 합계 | 10 | 1 | 5 | 4 |

### 이미 해결된 사항으로 확인하여 지적하지 않은 것

`git log` 를 확인한 결과 다음 두 건은 최근에 처리되었으므로 감사 대상에서 제외했습니다.

- `1832ef1`, `309e396`: VCP 화면의 `stale_warning` 배너 노출. 현재
  `page.tsx:623` 이 백엔드 값을 그대로 상태에 반영하고 있으며 회귀 테스트도 있습니다.
- `1aa8e34`, `72c8df1`, `edb628c`: outcome 대소문자 비교와 칩 집계 범위. VCP 경로의
  `status` 값은 `engine/signal_tracker_analysis_mixin.py:283` 에서 대문자 `OPEN` 으로
  정규화되므로 `kr_market_vcp_signal_helpers.py:195` 의 비교에는 같은 문제가 없습니다.

### 다른 카테고리에서 관찰한 사실

- `frontend/src/app/chatbot/page.tsx` 와 `frontend/src/app/components/ChatWidget.tsx` 가
  §2.2 의 마크다운 전처리기 사본을 하나씩 가지고 있습니다. 챗봇과 프론트엔드 공통
  카테고리의 감사에서 같은 사실이 나올 것으로 예상합니다.

---

# 2부: TODO 항목 초안

일련번호는 `docs/dev-cycle/` 전체와 저장소의 Markdown 문서를 검색해 확인한 결과 VCP 약어를
쓰는 실제 항목이 하나도 없으므로 `VCP-001` 부터 매겼습니다. `archive-format.md:67` 과
`docs/superpowers/plans/2026-09-01-dev-cycle-system.md:313` 에 나오는 `VCP-001` 은 둘 다
형식을 설명하는 예시 문구이며 백로그 항목이 아닙니다.

### [VCP-001] AI 분석 실패 시그널이 관망 추천으로 표시되는 결함 수정
- 카테고리: VCP 시그널 | 티어: T2 | 우선순위: P0 | 근거: AUDIT-VCP §1.1
- 티어 근거: 건드릴 파일이 `tier-rules.md` §2 의 위험 경로에 닿지 않고 구현 변경도 50줄
  안쪽으로 예상되지만, 화면에 보이는 배지가 바뀌므로 실측이 필요합니다. T1 의 검증 열은
  실측을 포함하지 않으므로 T2 로 올립니다. Next.js 가 16.1.6 이라 `next-dev-loop` 은
  쓸 수 없고 agent-browser 를 직접 씁니다(`frontend-skills.md` §3).
- [ ] `_build_vcp_gemini_recommendation` 이 `_is_vcp_ai_analysis_failed` 와 같은 기준으로
      실패 행을 걸러내도록 수정
- [ ] `getAIBadge` 가 알 수 없는 action 을 관망으로 표시하지 않고 미분석 상태로 구분하도록 수정
- [ ] 실패 행이 추천 객체를 만들지 않는지 확인하는 pytest 회귀 테스트 추가
- [ ] 미분석 종목의 배지 표기를 확인하는 vitest 추가
- [ ] agent-browser 로 VCP 화면에서 실패 종목의 표기를 실측

### [VCP-002] VCP 화면의 현재가 갱신 대상과 폴링 정리 결함 수정
- 카테고리: VCP 시그널 | 티어: T2 | 우선순위: P1 | 근거: AUDIT-VCP §1.2, §4.1
- 티어 근거: `frontend/src/app/dashboard/kr/vcp/page.tsx` 한 파일이며 위험 경로가
  아닙니다. 변경은 30줄 안쪽으로 예상되지만 장중 갱신 동작이 바뀌므로 실측이 필요해
  T2 로 올립니다.
- [ ] 현재가 갱신 effect 가 목록 내용 변화를 반영하도록 의존성 수정
- [ ] `checkRunningStatus` 가 만드는 `setInterval` 핸들을 ref 에 담아 언마운트에서 정리
- [ ] 날짜를 바꿔도 개수가 같을 때 갱신 대상이 따라 바뀌는지 확인하는 vitest 추가
- [ ] agent-browser 로 날짜 전환 후 현재가 갱신을 실측

### [VCP-003] 두 번째 AI 프로바이더 폴백 누락 수정
- 카테고리: VCP 시그널 | 티어: T1 | 우선순위: P1 | 근거: AUDIT-VCP §1.3
- 티어 근거: `engine/vcp_ai_orchestration_helpers.py` 한 파일이며 `tier-rules.md` §2 의
  위험 경로 목록에 없습니다. 구현 변경은 다섯 줄 안팎입니다. 다만 이 파일이 VCP 판정
  경로인데도 위험 경로 목록에서 빠져 있다는 점은 별도로 확인이 필요하므로 체크박스에
  넣었습니다.
- [ ] Perplexity 가 비활성일 때 GPT 분기로 이어지도록 조건 수정
- [ ] `.env.example` 의 `VCP_SECOND_PROVIDER` 권장 값과 `engine/config.py:199` 의 기본값이
      어긋난 상태를 정리
- [ ] 키가 없는 환경에서 GPT 가 두 번째 프로바이더로 선택되는지 확인하는 pytest 추가
- [ ] `engine/vcp_ai_orchestration_helpers.py` 를 `tier-rules.md` §2 위험 경로에 넣을지
      판단하고, 넣는다면 같은 커밋에서 목록을 갱신

### [VCP-004] VCP 응답 생성 헬퍼의 검증 공백 메우기
- 카테고리: VCP 시그널 | 티어: T2 | 우선순위: P1 | 근거: AUDIT-VCP §5.1
- 티어 근거: 테스트 파일만 바꾸므로 `tier-rules.md` §1 의 제외 조항을 적용할 수 없고,
  추가되는 줄 수를 그대로 셉니다. 다섯 함수 분량이면 300줄 안쪽으로 예상됩니다.
- 선행 조건: `[VCP-001]` 이 끝난 뒤에 착수합니다. 지금 상태를 그대로 고정하는 테스트를
  먼저 쓰면 결함을 정답으로 굳히게 됩니다.
- [ ] `_apply_vcp_reanalysis_updates` 의 성공·실패 분기 테스트 추가
- [ ] `_build_ai_data_map` 과 `_merge_legacy_ai_fields_into_map` 의 병합 규칙 테스트 추가
- [ ] `_merge_ai_data_into_vcp_signals` 의 필드 덮어쓰기 동작 테스트 추가
- [ ] pytest 전체 통과 확인

### [VCP-005] `vcp_ai_analyzer.py` 의 죽은 폴백 코드와 중복 헬퍼 정리
- 카테고리: VCP 시그널 | 티어: T3 | 우선순위: P2 | 근거: AUDIT-VCP §3.1, §2.1
- 티어 근거: `engine/vcp_ai_analyzer.py` 는 `tier-rules.md` §2 의 "VCP 판정" 위험 경로에
  올라 있으므로 줄 수와 무관하게 T3 입니다. 리뷰는 `/ponytail-review` → `/simplify` →
  `/code-review` → `/review` 순서를 지킵니다.
- [ ] 호출자가 없는 `_fallback_to_zai` 제거
- [ ] `_resolve_perplexity_fallback_providers` 와 `_build_perplexity_fallback_chain` 의
      실행되지 않는 분기 정리
- [ ] `_extract_status_code` 세 사본을 하나로 통합
- [ ] `max_parse_attempts = 1` 로 죽어 있는 재시도 구조 정리
- [ ] 기존 27건의 Z.ai 테스트가 그대로 통과하는지 확인
