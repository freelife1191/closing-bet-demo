# [CHAT-007] 사이드바 대화 항목을 키보드로 열 수 있게 만든다 — QA 시나리오

- 대상 화면: http://localhost:3500/chatbot (데스크톱 1280x800, 모바일 390x844)
- 구성 근거: /qa-only 리포트 (.gstack/qa-reports/qa-report-localhost-3500-2026-09-07-chat-007.md, 건강 97)
  + 이번 사이클의 변경 두 파일(`frontend/src/app/chatbot/page.tsx`,
  `frontend/src/app/chatbot/page.regression-chat-007.test.tsx`) + 구현 단계 실측 로그
  (`.gstack/qa-reports/chat007-qa-only-2026-09-07.log`)
- 구성 2026-09-07 08:19 | 실행 (미실행)
- QA 엔진(engine): Claude Code `/qa-only` → `/qa`
- 단계(phase): 시나리오 구성 완료 | 실행 대기
- 반복(iteration): 0회
- baseline 상태: 기준값 수집 완료 (`.gstack/qa-reports/baseline-chat-007.json`)
- 필수 여부(required): 예
- 결과: (미실행)
- 증거: (실행 후 기록)
- 정리(cleanup): 이 사이클이 띄운 gunicorn(5501)·Next dev(3500)·browse 데몬·agent-browser 세션을
  실행 뒤 내린다. 구현 단계 실측 3 에서 만든 빈 fixture 세션 1건은 같은 신원의 DELETE 로 즉시 지웠다.

## 검사 대상에 관한 전제

대화 항목은 `GET /api/kr/chatbot/sessions` 가 돌려주는 세션에서만 그려지는데, 그 목록은
사용자 메시지가 있는 세션만 담는다(`chatbot/storage.py` 의 `has_meaningful_user_message`).
사용자 메시지를 만드는 유일한 경로는 실제 LLM 호출이라 QA 에서 실행하지 않고, 다른 소유자의
`browser_session_id` 로 바꿔 넣는 것은 `browser-notes.md` 가 금지한다. 따라서 S-1·S-2 는
실제 페이지 컴포넌트를 세션 하나와 함께 렌더하는 vitest 하네스
(`page.regression-chat-007.test.tsx`)를 검사 대상으로 삼고, 브라우저에서는 그 밖의 시나리오를
실행한다. 실행하지 못한 브라우저 조작을 실행했다고 적지 않는다.

## 시나리오

### S-1. 대화 항목이 제목을 이름으로 가진 버튼이고 누르면 그 대화가 열린다 (회귀)
- 조작: vitest 하네스에서 세션 `sess-a11y-001`(제목 「삼성전자 수급 질문」) 하나를 목으로 주고
  페이지를 렌더한다. `getByRole('button', { name: '삼성전자 수급 질문' })` 로 항목을 찾아 누른다.
- 기대: 항목이 버튼으로 잡히고, 누르기 전에는 히스토리 요청이 0건, 누른 뒤
  `/api/kr/chatbot/history?session_id=sess-a11y-001` 요청이 정확히 1건이며 항목의
  `aria-current` 가 `true` 가 된다.
- 필수 여부(required): 예
- 실제: (실행 후 기록)
- 결과: (미실행)
- 증거: (실행 후 기록)
- 정리(cleanup): 하네스 자체 목. 잔여 자료 없음

### S-2. 삭제는 「<제목> 삭제」 이름의 형제 버튼이고 누르면 확인 모달만 뜬다 (회귀)
- 조작: 같은 하네스에서 `getByRole('button', { name: '삼성전자 수급 질문 삭제' })` 를 찾아 누른다.
- 기대: 삭제 버튼의 `parentElement` 가 항목 버튼의 `parentElement` 와 같고(형제), 누르면
  `role=dialog` 에 「대화 삭제」가 뜨며 히스토리 요청은 0건이다.
- 필수 여부(required): 예
- 실제: (실행 후 기록)
- 결과: (미실행)
- 증거: (실행 후 기록)
- 정리(cleanup): 하네스 자체 목. 잔여 자료 없음

### S-3. 아이콘 전용 버튼이 이름을 갖고 문서에 중첩 버튼이 없다 (회귀)
- 조작: 데스크톱에서 `/chatbot` 을 열고 접근성 트리(`snapshot -i`)를 읽는다. 입력창에
  「테스트 입력」을 넣되 보내지 않고 「보내기」 버튼을 찾은 뒤 입력을 비운다.
  `document.querySelectorAll("button button").length` 와 이름 없는 버튼 수를 읽는다.
- 기대: `[button] "스마트머니봇"`, `[button] "프로필 설정 열기"`, `[button] "파일 첨부"`,
  `[button] "음성 입력"` 이 있고, 입력 후 `button[aria-label="보내기"]` 가 존재하며,
  중첩 버튼 0, 이름 없는 버튼 0. 하네스에서도 「메뉴 열기·파일 첨부·음성 입력·프로필 설정
  열기·스마트머니봇·보내기」 여섯 이름이 잡히고 `button button` 이 없다.
- 필수 여부(required): 예
- 실제: (실행 후 기록)
- 결과: (미실행)
- 증거: (실행 후 기록)
- 정리(cleanup): 입력창을 비운다. 전송하지 않는다

### S-4. 상단 바 두 버튼이 키보드로 동작한다 (회귀)
- 조작: 「새 채팅」에 초점을 두고 Tab 을 두 번 누른다. 「스마트머니봇」에서 Enter 를 두 번 누른다.
  「프로필 설정 열기」에서 Enter 를 누른 뒤 대화상자의 닫기(×) 버튼을 누른다. 「저장」은 누르지 않는다.
- 기대: Tab 순서 새 채팅 → 스마트머니봇(`aria-expanded="false"`) → 프로필 설정 열기.
  Enter 마다 `aria-expanded` 가 true → false. 「프로필 설정 열기」 Enter 로 `role=dialog`
  「설정」이 열리고 닫기(×)로 닫힌다. (초점이 대화상자 안으로 가지 않고 Escape 로 닫히지
  않는 것은 기존 `[FE-030]` 이라 이 시나리오의 판정에 넣지 않는다.)
- 필수 여부(required): 예
- 실제: (실행 후 기록)
- 결과: (미실행)
- 증거: (실행 후 기록)
- 정리(cleanup): 대화상자를 닫은 상태로 둔다

### S-5. 모바일 사이드바를 키보드로 열고 접고 닫는다 (회귀)
- 조작: 뷰포트 390x844 에서 `/chatbot` 을 열고 `[button] "메뉴 열기"` 를 누른다. 「메뉴」에
  초점을 두고 Enter, 「메뉴 닫기」에 초점을 두고 Enter.
- 기대: 「메뉴 열기」 뒤 사이드바에 `[button] "메뉴"` (`aria-expanded="true"`)·
  `[button] "메뉴 닫기"`·「새 채팅」이 보이고, Enter 로 `aria-expanded` 가 false 가 되며,
  「메뉴 닫기」 Enter 로 `button[aria-label="메뉴 닫기"]` 가 사라진다.
- 필수 여부(required): 예
- 실제: (실행 후 기록)
- 결과: (미실행)
- 증거: (실행 후 기록)
- 정리(cleanup): 뷰포트를 1280x800 으로 되돌린다

### S-6. 콘솔·런타임·컴파일 오류와 링크 상태 (인접)
- 조작: `console --clear` 뒤 데스크톱·모바일에서 각각 다시 로드하고 `console --errors` 를 읽는다.
  `/_next/mcp` 의 `get_errors`·`get_compilation_issues` 를 호출하고 같은 출처 링크에 HEAD 를 보낸다.
- 기대: 콘솔 오류 0, `{"configErrors":[],"sessionErrors":[]}`, `{"issues":[]}`, 링크 7개 모두 200.
- 필수 여부(required): 예
- 실제: (실행 후 기록)
- 결과: (미실행)
- 증거: (실행 후 기록)
- 정리(cleanup): 없음

### S-7. 정적 검증이 통과한다 (인접)
- 조작: `(cd frontend && npx vitest run)` 과 `(cd frontend && npm run type-check)` 를 실행한다.
- 기대: vitest 45 파일 288 테스트 통과 종료 코드 0, `tsc` 종료 코드 0.
- 필수 여부(required): 아니오 (첫 커밋 전 정적 검증과 같은 명령. QA 실행 뒤 코드가 바뀌면 필수로 올린다)
- 실제: (실행 후 기록)
- 결과: (미실행)
- 증거: (실행 후 기록)
- 정리(cleanup): 없음

## 이월한 발견

- ISSUE-001 「설정 모달이 열려도 초점이 옮겨 가지 않고 Escape 로 닫히지 않는다」 → 기존 `[FE-030]`.
  모달 초점 관리는 `SettingsModal` 소관이라 이번 범위를 넘는다.
- ISSUE-002 「접힌 「메뉴」 안의 링크가 탭 순서에 남는다」, ISSUE-003 「「메뉴 닫기」 뒤 초점이 본문으로
  떨어진다」 → 신규 `[CHAT-030]`. 초점 이동과 `inert` 는 승인 범위(이름과 버튼화) 밖이다.
- ISSUE-004 「공용 사이드바 「+」 버튼 이름이 「+」뿐」 → 기존 `[FE-029]` 에 한 줄 추가. `Sidebar.tsx` 소관.
- 코드 리뷰 발견 「첨부 파일 제거·답변 중단 버튼의 이름」 → 신규 `[CHAT-029]`. 승인 범위가 다섯 버튼으로
  명시되어 있어 이월했다.

## 실행 결과

- 필수 시나리오: (실행 후 기록)
- 미통과 필수: (실행 후 기록)
- 재개 판정: (실행 후 기록)
- 시나리오 밖에서 새로 발견: (실행 후 기록)
