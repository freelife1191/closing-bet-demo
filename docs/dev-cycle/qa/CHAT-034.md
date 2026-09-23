# [CHAT-034] 챗봇 SQLite 누락 테이블 복구 래퍼 통합 — QA 시나리오

- 대상 화면: http://localhost:3752/chatbot (격리 Next). 백엔드는 격리 gunicorn http://127.0.0.1:5752
- 구성 근거: TODO 의 QA 줄(격리 사본에서 테이블이 없는 상태로 LLM 을 부르지 않는 세션 목록·생성·삭제 경로 실측) + 이번 변경(열네 저장소 함수의 복구가 `run_chatbot_sqlite_with_recovery` 한 곳을 지난다)
- 복구 경로를 실제로 타게 하는 방법: 서버가 떠서 스키마 게이트가 해당 DB 를 ready 로 기록한 **뒤에** 사본 DB 에서 테이블을 DROP 한다. 이 상태의 비강제 확인은 테이블을 만들지 않으므로, 조작 뒤 테이블이 다시 있으면 `force_recheck=True` 복구가 돈 것이다. 서버 기동 전에 지우면 게이트가 처음부터 만들어 복구 경로를 타지 않는다
- 구성 2026-09-23 | 실행 (미실행)
- 검증 기준 커밋: (첫 커밋 뒤 기입)
- QA 엔진(engine): Claude Code, 브라우저는 gstack `browse`. 원본 3500/5501·live 주소·원본 `.env`·원본 `data/` 는 쓰지 않는다.
  `browser-notes.md` 「공통」 절에 따라 원본 PYTHONPATH 의 앱을 scratch cwd 로 띄우지 않는다
  - 코드 사본 `code/`(`git archive <첫 커밋>`). `.env`·`secrets/` 없음
  - 실행 디렉터리 `run/`: 원본 `data/` 의 JSON·CSV 를 읽기 전용으로 복사. `chatbot_storage.db` 는 복사하지 않고 사본 서버가 새로 만든다
  - gunicorn: `code/` 를 `--pythonpath`, cwd `run/`, `SCHEDULER_ENABLED=false`, 더미 `INTERNAL_IDENTITY_SECRET`, 1 worker, `127.0.0.1:5752`. Next: 첫 커밋의 `frontend/` 사본, `API_URL=http://127.0.0.1:5752`, 더미 비밀, `npm run dev -- -p 3752`
- 금지 조작: 챗봇 질문 전송(LLM 호출), 설정 저장, Refresh VCP, 실패 AI 재분석, GEMINI 재분석, Refresh Market Gate, 모의 매수. 세션 생성은 화면 버튼이 질문 전송과 묶여 있으므로 브라우저 `fetch` 로 `POST /api/kr/chatbot/sessions` 를 보낸다(LLM 을 부르지 않는 저장소 경로). 삭제는 격리 사본 안의 세션만 대상으로 한다
- 단계(phase): 시나리오 구성 완료 | 실행 대기
- 반복(iteration): 0회
- 결과: (미실행)
- 필수 여부(required): 예
- browser_applicability: required. 사용자가 챗봇 화면의 대화 목록을 열고 대화를 지우는 흐름이 이 저장소 함수들을 지난다. browser_driver: gstack `browse`
- 읽은 정본: `.claude/skills/closing-bet-python/SKILL.md`, `.claude/skills/closing-bet-verify/SKILL.md`, `.claude/skills/dev-cycle/references/tier-rules.md` §2·§3

## 시나리오

### S-1. 대화 테이블이 없는 상태에서 새 대화가 생기고 목록에 보인다 (핵심)
- 조작: `/chatbot` 을 한 번 연다(게이트 ready). 사본 DB 에서 `chatbot_sessions`·`chatbot_messages` 를 DROP 한다. 브라우저에서 `POST /api/kr/chatbot/sessions` 를 보내고 화면을 새로고침한다.
- 기대: POST 가 200 과 `session_id` 를 돌려준다. 새로고침 뒤 사이드바 목록에 그 세션이 보인다. 사본 DB 에 두 테이블이 다시 있고 세션 행이 1개다. 백엔드 로그에 `Failed to ... SQLite` 가 없다.
- 필수 여부(required): 예
- 실제:
- 결과:

### S-2. 대화 테이블이 다시 없어진 뒤 화면에서 대화를 지운다
- 조작: S-1 의 세션이 목록에 있는 상태에서 사본 DB 의 두 테이블을 다시 DROP 한다. 화면에서 그 대화의 삭제를 누르고 확인한다.
- 기대: 삭제 요청이 200 이고 목록에서 사라진다. 두 테이블이 다시 있고 세션 행이 0개다. `Failed to ... SQLite` 로그가 없다.
- 필수 여부(required): 예
- 실제:
- 결과:

### S-3. 메모리 테이블이 없는 상태에서 프로필이 저장되고 다시 읽힌다
- 조작: 사본 DB 에서 `chatbot_memories` 를 DROP 한다. 브라우저에서 `POST /api/kr/chatbot/profile`(`name`·`persona`)을 보낸 뒤 `GET /api/kr/chatbot/profile` 을 읽는다.
- 기대: POST 200, GET 이 보낸 이름을 돌려준다. `chatbot_memories` 가 다시 있고 행이 생겼다. `Failed to ... SQLite` 로그가 없다.
- 필수 여부(required): 예
- 실제:
- 결과:

### S-4. 화면 회귀 없음
- 조작: 콘솔 오류·`/_next/mcp get_errors`·gunicorn access 로그의 5xx 를 확인한다.
- 기대: 5xx·콘솔 오류·프레임워크 오류 0. 무관한 오류는 원인과 함께 따로 적는다.
- 필수 여부(required): 예
- 실제:
- 결과:
