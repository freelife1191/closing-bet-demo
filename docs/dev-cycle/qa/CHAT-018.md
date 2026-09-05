# [CHAT-018] 채팅 전송 경로가 소유자 검사를 통째로 지나친다 — QA 시나리오

- 대상 화면: http://localhost:3500/chatbot, http://localhost:3500/dashboard/kr/vcp
- 구성 근거: /qa-only 리포트 (.gstack/qa-reports/qa-report-localhost-3500-2026-09-05.md)
  + 이번 사이클의 변경 다섯 파일
- 구성 2026-09-05 21:30 | 실행 (미정)

## 검사 방식에 관한 전제

이번 사이클이 고친 것은 **채팅 전송 경로**(`POST /api/kr/chatbot`)의 소유권 판정입니다.
그런데 그 경로를 화면에서 실제로 밟으려면 챗봇에 메시지를 보내야 하고, 그것은 Gemini
호출과 무료 사용량 소모를 일으킵니다. 슬래시 명령(`/help`, `/status`)도 예외가 아닙니다.
`services/kr_market_chatbot_quota_helpers.py` 의 `maybe_increment_chatbot_usage` 가
「응답이 성공이고 `usage_key` 가 있으면」 차감하므로, LLM 을 부르지 않는 명령도 사용량을
줄입니다. 그래서 **전송 경로의 회귀는 pytest 로 검사하고(S-1~S-3), 같은 판정 함수를 쓰는
조회 경로를 GET 요청으로 실측합니다(S-4~S-6).** 화면 시나리오는 비용이 들지 않는
자리(S-7~S-9)로 구성했습니다.

조회 경로를 회귀 검사로 삼는 근거는 판정이 한 곳에 모였다는 점입니다. 이번 변경으로
전송·조회·삭제 세 경로가 모두 `chatbot/storage_history_helpers.py` 의
`is_session_accessible_by_owner` 하나를 씁니다.

S-4~S-6 에 쓰는 세션 ID 는 2026-09-05 21:2x 에 `data/chatbot_storage.db` 를 읽기 전용으로
열어 뽑은 실제 값입니다. 세션 348건 가운데 레거시(`owner_id` 가 비어 있음)가 317건,
소유자가 있는 것이 31건입니다.

## 시나리오

### S-1. 남의 세션 ID 로 채팅을 보내도 그 세션을 가져가지 못한다 (회귀)
- 조작: `source venv/bin/activate && pytest tests/chatbot/test_session_access.py::test_ensure_session_access_never_hands_over_a_session_with_another_owner -v`
- 기대: 통과. 소유자가 `owner-a` 인 세션에 `owner-b` 가 접근하면 다른 세션 ID 가 돌아오고,
  원래 세션의 `owner_id` 는 `owner-a` 로 그대로 남으며, 새 세션의 소유자는 `owner-b` 이고,
  경고 로그가 남는다.
- 결과:

### S-2. 소유자를 모르는 요청이 남의 대화를 프롬프트에 싣지 못한다 (회귀)
- 조작: `source venv/bin/activate && pytest tests/chatbot/test_session_access.py::test_ensure_session_access_blocks_requests_without_an_owner -v`
- 기대: 통과. `owner_id=None` 으로 남의 세션 ID 를 보내면 다른 세션 ID 가 돌아오고, 그
  세션의 메시지 목록은 비어 있으며, 피해자 세션의 메시지는 그대로 남는다. 돌려받은 세션이
  비어 있다는 것이 곧 `build_api_history` 가 남의 대화를 싣지 못한다는 뜻이다.
- 결과:

### S-3. 레거시 세션은 이어받고 자기 세션은 그대로 쓴다 (회귀)
- 조작: `source venv/bin/activate && pytest tests/chatbot/test_session_access.py::test_ensure_session_access_keeps_legacy_and_own_sessions -v`
- 기대: 통과. 소유자가 비어 있는 세션은 같은 ID 를 돌려주며 소유자가 채워지고, 두 번째
  호출에서도 같은 ID 를 돌려주며 경고 로그가 하나도 남지 않는다.
- 결과:

### S-4. 남의 세션은 조회로도 열리지 않는다 (회귀)
- 조작: `curl -s -H "X-Session-Id: anon_7a87cbb0-d7ac-49bd-b23c-8e3db9f685e3" "http://localhost:5501/api/kr/chatbot/history?session_id=b8191686-3079-4f8a-85d1-594b882548c5"`
- 기대: `{"error": "Session not found"}` 가 돌아온다. 그 세션은 다른 익명 소유자의 것이며
  메시지 2건을 갖고 있다.
- 결과:

### S-5. 소유자 헤더가 없는 조회도 막힌다 (회귀)
- 조작: `curl -s "http://localhost:5501/api/kr/chatbot/history?session_id=b8191686-3079-4f8a-85d1-594b882548c5"`
- 기대: `{"error": "Session not found"}` 가 돌아온다. 헤더가 없다고 검사를 지나가지 않는다.
- 결과:

### S-6. 레거시 세션 조회는 계속 열려 있다 (인접)
- 조작: `curl -s -H "X-Session-Id: anon_7a87cbb0-d7ac-49bd-b23c-8e3db9f685e3" "http://localhost:5501/api/kr/chatbot/history?session_id=1b19ec82-c2d7-4750-a8f0-3cc7a6599456"`
- 기대: `history` 배열에 메시지 2건이 돌아온다. 첫 항목은 `role: "user"` 이고 본문이
  `/clear`, 둘째는 `role: "model"` 이고 본문이 「🧹 현재 대화 세션이 초기화되었습니다.」다.
  `[CHAT-016]` 이 정한 「소유자가 비어 있는 세션은 ID 를 아는 요청에 연다」는 설계가
  이번 변경으로 깨지지 않았음을 확인한다.
- 결과:

### S-7. 챗봇 화면이 빈 대화 목록을 정상적으로 그린다 (인접)
- 조작: http://localhost:3500/chatbot 을 연다. 모델 선택기(`FLASH`)를 누르고, 「새 채팅」을
  누른다.
- 기대: 사이드바에 「최근 대화」와 「저장된 대화가 없습니다.」가 보인다. 본문에
  「안녕하세요, 흑기사님」과 「무엇을 도와드릴까요?」가 보이고 추천 질문 카드가 넷이다.
  모델 선택기에 `gemini-3.5-flash-lite`, `gemini-3.7-flash`, `gemini-3.6-flash` 셋이 나온다.
  「새 채팅」을 눌러도 목록은 그대로이고 콘솔 오류가 0건이다.
- 결과:

### S-8. VCP 채팅 패널이 세션 키 없이 열린다 (인접)
- 조작: http://localhost:3500/dashboard/kr/vcp 을 열고 우하단 「AI 상담」을 누른다. 그다음
  `localStorage` 의 키 목록을 읽는다.
- 기대: 패널 머리에 「스마트 머니 봇」과 「Online」이 보이고, 추천 질문 카드가 넷이며,
  「보내기」 버튼이 `disabled` 다. `localStorage` 에 `vcp_chat_session_id_` 로 시작하는 키가
  하나도 없다. 세션 ID 는 첫 전송 때 만들어지므로 패널을 여는 것만으로는 생기지 않는다.
  콘솔 오류가 0건이다.
- 결과:

### S-9. 화면 전환과 뒤로 가기가 깨지지 않는다 (인접)
- 조작: VCP 화면에서 「과거」 탭을 누르고 나타난 「2026-05-05」를 누른다. 그다음 사이드바의
  「AI 상담」으로 이동하고 브라우저 뒤로 가기를 누른다.
- 기대: 「과거」 탭에서 「2026-05-05」 버튼이 나타나고 표에 「No signals found.」가 보인다.
  사이드바 이동 뒤 URL 이 `/chatbot` 이고, 뒤로 가기 뒤 URL 이 `/dashboard/kr/vcp` 다.
  전 과정에서 콘솔 오류가 0건이다.
- 결과:

## 이월한 발견

1단계 리포트가 Low 4건을 지적했는데 **새로 올릴 항목이 없습니다.** 셋은 기존 백로그가
이미 담고 있고, 하나는 항목으로 세울 만한 피해가 아닙니다.

- ISSUE-001 「챗봇 입력 영역 버튼 둘의 접근 가능한 이름이 비어 있다」 → `[CHAT-007]` 이
  이미 담고 있습니다. 그 항목의 체크박스가 「입력 영역의 버튼 넷에 `aria-label` 을 붙임
  (보내기·햄버거·파일 첨부·음성 입력)」입니다.
- ISSUE-002 「VCP 화면 상단 홈 아이콘 링크의 이름이 비어 있다」 → `[FE-029]` 가 이미
  담고 있습니다. 그 항목이 짚은 `frontend/src/app/components/Header.tsx:23` 의
  `<a href="/">` 가 이 링크이며, VCP 화면도 같은 헤더를 씁니다.
- ISSUE-004 「VCP 「과거」 탭의 안내와 결과가 어긋난다」 → `[VCP-008]` 이 이미 담고
  있습니다. 그 항목이 원인까지 밝혀 두었습니다. 날짜 목록은 종가 계열 파일에서 만들어지고
  시그널 조회는 VCP 파일을 찾는데 `vcp_signals_results_20260505.json` 이 없습니다.
- ISSUE-003 「챗봇 화면 DOM 에 모델 선택기가 두 벌 존재한다」 → 항목으로 세우지 않습니다.
  데스크톱용과 모바일용을 함께 두고 CSS 로 하나를 숨기는 것은 흔한 반응형 구현이고,
  스크린 리더가 목록을 두 번 읽는 것 말고는 피해가 없습니다. 관찰로만 남깁니다.

## 실행 결과

(미실행)
