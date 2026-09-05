# [CHAT-017] 챗봇 메모리를 소유자별로 나눈다 — QA 시나리오

- 대상 화면: http://localhost:3500/chatbot
- 구성 근거: `/qa-only` 리포트 (`.gstack/qa-reports/qa-report-localhost-3500-chatbot-2026-09-05.md`)
  \+ 이번 사이클의 변경 여덟 파일과 신규 검사 하나
- 구성 2026-09-05 22:45 | 실행 (미실행)

## 이 항목의 검증 구조

이번 변경이 실제로 고친 두 경로는 **화면에서 밟을 수 없습니다.** 시스템 프롬프트 구성과
`/memory` 명령이 모두 `POST /api/kr/chatbot` 을 거치는데, 그 경로는 실제 Gemini 호출과
무료 사용량 차감을 일으키기 때문입니다. 슬래시 명령도 예외가 아닙니다
(`services/kr_market_chatbot_quota_helpers.py` 의 `maybe_increment_chatbot_usage` 가
성공 응답이면 무조건 차감합니다).

그래서 검증을 셋으로 나누었습니다. 소유자 격리 자체는 pytest 로, 저장소의 실제 상태는
읽기 전용 SQLite 조회로, 화면 회귀는 비용이 들지 않는 GET 경로와 브라우저 렌더링으로
확인합니다.

기대값은 모두 2026-09-05 22:35~22:41 에 실측한 값입니다. 서버는 22:37:36 에
`kill -HUP` 으로 gunicorn 워커를 재기동해 이번 변경을 반영한 상태입니다.

## 시나리오

### S-1. 챗봇 화면의 인사말이 프로필 이름을 그대로 그린다 (회귀)
- 조작: `http://localhost:3500/chatbot` 을 1440×900 뷰포트로 연다. 중앙 상단의 인사말과
  우측 상단 아바타의 문구를 읽는다.
- 기대: 인사말은 `안녕하세요, 흑기사님`, 그 아래는 `무엇을 도와드릴까요?`, 우측 상단
  아바타는 `흑기`. 이 이름은 DB 값이 아니라 `chatbot/runtime_setup_service.py` 의
  `DEFAULT_PROFILE` 이다. `user_profile` 행이 저장소에 없어 기본값이 나오며, 이번 변경
  이후에도 공용 영역에 그 행이 없으므로 같은 값이 유지되어야 한다.
- 결과:

### S-2. 프로필 조회가 소유자 없이도 같은 값을 돌려준다 (회귀)
- 조작: `curl -s http://localhost:5501/api/kr/chatbot/profile`
- 기대: `{"profile": {"name": "흑기사", "persona": "주식 투자를 배우고 있는 열정적인 투자자"}}`.
  이 경로는 소유자를 아예 받지 않으므로 `memory.get("user_profile")` 이 공용을 본다.
  공용에 그 행이 없어 기본값이 나오는 것이 정상이다.
- 결과:

### S-3. 세션 목록이 소유자 헤더와 무관하게 같은 값을 돌려준다 (회귀)
- 조작: 헤더 없이 한 번, `-H "X-Session-Id: qa-owner-a"` 를 붙여 한 번
  `http://localhost:5501/api/kr/chatbot/sessions` 를 GET 한다.
- 기대: 두 경우 모두 `{"sessions": []}`. 이번 변경은 `chatbot_sessions` 를 건드리지
  않았으므로 세션 쪽 동작이 달라지면 안 된다. 메모리의 `owner_id = ''` 는 「공용」이지만
  세션의 `owner_id IS NULL` 은 「레거시」라 의미가 정반대이며, 그 둘을 섞지 않았음을
  이 검사가 지킨다.
- 결과:

### S-4. 모델 목록이 그대로다 (회귀)
- 조작: `curl -s http://localhost:5501/api/kr/chatbot/models`
- 기대: `current` 는 `gemini-3.7-flash`, `models` 는
  `["gemini-3.5-flash-lite", "gemini-3.7-flash", "gemini-3.6-flash"]`.
- 결과:

### S-5. 저장소의 기본 키가 (owner_id, memory_key) 로 옮겨졌고 legacy 테이블이 남지 않았다 (리포트)
- 조작: `data/chatbot_storage.db` 를 **읽기 전용**(`file:...?mode=ro`)으로 열어
  `chatbot_memories` 의 `sqlite_master.sql` 과 전체 행, 그리고
  `sqlite_master WHERE name LIKE 'chatbot_memories%'` 를 읽는다.
- 기대: 스키마에 `owner_id TEXT NOT NULL DEFAULT ''` 와 `PRIMARY KEY (owner_id, memory_key)`
  가 있다. 행은 두 건이며 둘 다 `owner_id` 가 빈 문자열이다
  (`daily_suggestions_default_empty` 724바이트, `interest` 6바이트). 테이블 목록에
  `chatbot_memories` 하나만 있고 `chatbot_memories_legacy` 는 없다. legacy 가 남아 있으면
  마이그레이션이 중간에 끊긴 것이며 그 상태에서는 다음 실행이 컬럼 확인에서 건너뛰어
  데이터를 영영 잃는다.
- 결과:

### S-6. 소유자 격리 검사 17건이 통과한다 (회귀)
- 조작: `source venv/bin/activate && pytest tests/chatbot/test_memory_owner_access.py -q`
- 기대: 17건 전부 통과. 이 파일이 화면에서 밟을 수 없는 경로를 대신 지킨다. 마이그레이션이
  기존 행을 공용으로 옮기는 것, 실패 시 원자적으로 되돌아가는 것, 다른 워커가 먼저 끝냈으면
  되돌리지 않는 것, 서로 다른 소유자가 같은 키를 각자 갖는 것, `format_for_prompt` 가 남의
  것과 공용을 모두 배제하는 것, `/memory view` 가 요청자 것만 보여 주는 것, 소유자를 모르면
  거부하는 것이 여기에 들어 있다.
- 결과:

### S-7. 저장소와 명령 계층의 기존 검사가 회귀하지 않는다 (회귀)
- 조작: `source venv/bin/activate && pytest`
- 기대: 1,696건 통과, 2건 skip, 실패 0건.
- 결과:

### S-8. 프런트엔드 검사가 회귀하지 않는다 (인접)
- 조작: `(cd frontend && npx vitest run)`
- 기대: 279건 통과. 이번 사이클은 `frontend/` 를 한 줄도 바꾸지 않았으므로 값이 그대로여야
  한다. `--root frontend` 를 주면 69건이 실패하므로 반드시 서브셸로 `cd` 한다.
- 결과:

### S-9. 화면을 여는 동안 콘솔 오류와 실패 요청이 없다 (회귀)
- 조작: 네트워크 기록을 비우고 `/chatbot` 을 새로고침한 뒤 콘솔 로그와 요청 목록을 읽는다.
- 기대: 콘솔에 오류가 없다(Next.js 개발 모드의 `[HMR] connected` 와 React DevTools 안내만
  나온다). 요청 32건이 전부 200 이며 실패가 0건이다. 챗봇 API 는 `models` 와 `sessions`
  만 호출되고 `suggestions` 는 호출되지 않는다. `suggestions` 는 캐시가 비면 Gemini 를
  부르므로 호출되지 않는 것이 정상이자 안전한 상태다.
- 결과:

### S-10. 추천 질문 카드와 빠른 조회 버튼이 모두 있고 모바일에서 겹치지 않는다 (회귀)
- 조작: 1440×900 과 375×812 두 뷰포트에서 화면 구조를 읽는다. **카드와 버튼을 누르지
  않는다.** 누르면 메시지가 전송되어 실제 비용이 발생한다.
- 기대: 추천 질문 카드 넷(`마켓게이트 상태와 투자 전략`, `AI 분석 기반 매수 추천 종목`,
  `오늘의 S/A급 종가베팅 추천`, `최근 주요 뉴스와 시장 영향`)과 빠른 조회 버튼
  다섯(`시장 현황`, `VCP 추천`, `종가 베팅`, `뉴스 분석`, `내 관심종목`)이 모두 있다.
  좌측 목록에는 `저장된 대화가 없습니다.` 가 나온다. 375×812 에서는 카드가 2×2 로
  재배치되고 버튼이 두 줄로 감기며 서로 겹치지 않는다.
- 결과:

## 이월한 발견

`/qa-only` 리포트가 지적했지만 이번 변경과 무관한 기존 결함이라 고치지 않은 것들입니다.

- **ISSUE-001** 「낮은 뷰포트에서 빠른 조회 버튼이 추천 질문 카드를 가린다」 → `[CHAT-024]`
  로 새로 올렸습니다. 1280×577 에서 재현되며 카드 하단이 잘린 채 스크롤도 되지 않습니다.
  `frontend/src/app/chatbot/page.tsx` 의 레이아웃 문제라 이번 백엔드 변경의 범위를 넘습니다.
- **ISSUE-002** 「모바일 햄버거 메뉴 버튼에 접근성 이름이 없다」 → 이미 `[CHAT-007]` 의
  체크박스 「입력 영역의 버튼 넷에 `aria-label` 을 붙임 (보내기·햄버거·파일 첨부·음성 입력)」
  에 들어 있어 새 항목을 세우지 않았습니다. 다만 오늘 실측에서는 파일 첨부와 음성 입력의
  `title` 이 접근성 이름으로 계산되어 이름 없는 버튼이 햄버거 하나로 줄었습니다. 그 관찰을
  `[CHAT-007]` 에 한 줄 덧붙였습니다.
- **ISSUE-003** 「`/api/kr/chatbot/models` 와 `/sessions` 를 각각 두 번씩 호출한다」 →
  항목으로 세우지 않았습니다. 개발 모드의 React StrictMode 가 효과를 두 번 실행하는 특성일
  가능성이 높고, 그렇다면 프로덕션 빌드에서는 존재하지 않는 현상입니다. 확인 자체가 별도
  작업이 되므로 리포트 기록으로만 남깁니다.

## 실행 결과

(미실행)
