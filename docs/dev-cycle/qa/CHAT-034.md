# [CHAT-034] 챗봇 SQLite 누락 테이블 복구 래퍼 통합 — QA 시나리오

- 대상 화면: http://localhost:3752/chatbot (격리 Next). 백엔드는 격리 gunicorn http://127.0.0.1:5752
- 구성 근거: TODO 의 QA 줄(테이블이 없는 상태에서 질문을 보내면 답변이 오고 새 대화가 목록에 나타난다) + 이번 변경(열네 저장소 함수의 복구가 `run_chatbot_sqlite_with_recovery` 한 곳을 지난다). 기대값은 이번 QA 가 보낸 질문·이름 자체이므로 원본 `data/` 를 읽지 않는다
- 복구 경로를 실제로 타게 하는 방법: 사본 서버가 해당 DB 를 한 번 쓰게 해 스키마 게이트가 ready 를 기록한 **뒤에** 사본 DB 에서 테이블을 DROP 한다. 이 상태의 비강제 확인은 테이블을 만들지 않으므로, 조작 뒤 테이블이 다시 있으면 `force_recheck=True` 복구가 돈 것이다
- 구성 2026-09-23 13:20 | 실행 2026-09-23 13:23~13:28 (1회차)
- 검증 기준 커밋: `23a39f8` (첫 커밋, `code/` 는 `git archive 23a39f8b`). 사본의 범위 파일 세 개가 원본 작업 트리와 바이트 단위로 같음을 `cmp` 로 확인했다
- QA 엔진(engine): Claude Code, 브라우저는 gstack `browse`. 원본 3500/5501·live 주소·원본 `.env`·원본 `data/` 는 쓰지 않는다.
  `browser-notes.md` 「공통」 절에 따라 원본 PYTHONPATH 의 앱을 scratch cwd 로 띄우지 않았다
  - 코드 사본 `code/`(`git archive 23a39f8b`). `.env`·`secrets/` 없음. 챗봇 DB 는 `code/data/chatbot_storage.db` 로 사본 안에 새로 생겼다
  - 실행 디렉터리 `run/`: 원본 `data/` 의 JSON·CSV 를 읽기 전용으로 복사(챗봇 저장소 파일은 원본에 없어 복사하지 않음)
  - gunicorn: `env -i`, `code/` 를 `--pythonpath`, cwd `run/`, `SCHEDULER_ENABLED=false`, 더미 `INTERNAL_IDENTITY_SECRET`, 1 worker 8 threads, `127.0.0.1:5752`.
    진입점은 `run/` 에만 둔 `qa_flask_app.py` 이며, `engine.genai_client.build_genai_client` 를 가짜 클라이언트로 바꾼다(`[CHAT-031]`~`[CHAT-033]` 과 같은 방식).
    가짜 클라이언트는 LLM 을 부르지 않고 「응답: <마지막 입력 일부>」를 돌려준다. 쿼터 가드용으로 `GOOGLE_GENAI_USE_VERTEXAI=true`·`GOOGLE_CLOUD_PROJECT=qa-stub` 를 더미로 준다
  - Next: 첫 커밋의 `frontend/` 사본(`node_modules` 는 `cp -cR`), `API_URL=http://127.0.0.1:5752`, 더미 `NEXTAUTH_SECRET`·`INTERNAL_IDENTITY_SECRET`, `npm run dev -- -p 3752`
- 설계 대화와의 차이: 설계 때는 「챗봇 전송은 금지 조작이라 LLM 을 부르지 않는 세션 생성 경로로 대체」한다고 했다. 실측해 보니 세션 목록은 의미 있는 사용자 메시지가 있는 세션만 보여 준다(`chatbot/storage.py` `get_all_sessions`). 그래서 빈 세션 생성으로는 사이드바를 검증할 수 없어, 가짜 LLM 진입점으로 원래 TODO 의 「질문 전송 → 사이드바」를 그대로 실행했다. 실제 LLM 호출과 비용은 0 이다
- 금지 조작: 실제 LLM 호출, 설정 저장, Refresh VCP, 실패 AI 재분석, GEMINI 재분석, Refresh Market Gate, 모의 매수. 삭제는 이번 QA 가 사본에서 만든 세션만 대상으로 했다
- 단계(phase): 시나리오 구성 완료 | 실행 완료
- 반복(iteration): 1회. 다만 S-2 는 첫 조작을 무효로 하고 다시 했다(아래 S-2 참고)
- 결과: 통과 (필수 4/4)
- 증거: 각 시나리오의 「실제」 줄(browse `snapshot`·`js` 출력, 사본 SQLite 조회, gunicorn access·error 로그) · 스크린샷 scratchpad `chat034-s1.png`·`chat034-s2.png`·`chat034-s3.png`(세 장 모두 열어 확인) · 로그 사본 scratchpad `chat034-access.log`·`chat034-flask.log`
- 정리(cleanup): browse 서버 정지, 격리 gunicorn 마스터 TERM, 격리 Next 세션 그룹 TERM. 3752/5752 와 원본 3500/5501 리스너 0, 사본 경로 프로세스 0, 사본 `qa-chat034/`(`qa_flask_app.py`·챗봇 DB 포함) 삭제. 루트 `node_modules/.vite` 없음, 작업 트리 변화 없음. 사본 구성 시각(13:23:06) 이후 원본 `data/`·`logs/` 에서 수정 시각이 바뀐 파일 0개. venv 의 `.pth` 에 원본 저장소를 가리키는 줄이 없음을 확인했다
- 필수 여부(required): 예
- browser_applicability: required. 사용자가 챗봇 화면에서 질문하고, 대화 목록을 보고, 대화를 지우고, 프로필을 저장하는 흐름이 이 저장소 함수들을 지난다. browser_driver: gstack `browse`
- 읽은 정본: `.claude/skills/closing-bet-python/SKILL.md`, `.claude/skills/closing-bet-verify/SKILL.md`, `.claude/skills/dev-cycle/references/tier-rules.md` §2·§3

## 시나리오

### 준비. 게이트 ready 만들기
- 조작: `/chatbot` 을 열고 입력창에 「기준 질문 하나」를 보낸다.
- 실제: 「응답: …」이 표시되고 사본 DB 에 세션 1개·메시지 2개가 저장됐다. 이 쓰기로 게이트가 사본 DB 를 ready 로 기록했다. (그 앞에 `X-Session-Id` 없이 `POST /api/kr/chatbot/sessions` 를 보낸 빈 세션 두 개는 목록 조건을 확인하려던 시도이며, 아래 DROP 과 함께 사라져 판정에 쓰지 않았다)

### S-1. 대화 테이블이 없는 상태에서 질문하면 답변이 오고 목록에 보인다 (핵심)
- 조작: 서버가 떠 있는 채로 사본 DB 에서 `chatbot_messages`·`chatbot_sessions` 를 DROP 한다(남은 테이블 `chatbot_memories` 확인). 「+ 새 채팅」 뒤 「복구 질문 둘」을 보내고 새로고침한다.
- 기대: 오류 없이 답변이 온다. 새로고침 뒤 사이드바에 그 대화가 보인다. 두 테이블이 다시 있고 그 세션의 메시지가 2개다. 백엔드 로그에 `Failed to ... SQLite` 가 없다.
- 필수 여부(required): 예
- 실제: 「응답: …」 1건 표시. 새로고침 뒤 사이드바 「최근 대화」에 「복구 질문 둘」 하나(스크린샷 `chat034-s1.png`). 사본 DB 테이블 `chatbot_memories,chatbot_sessions,chatbot_messages`, 「복구 질문 둘」 메시지 2개. DROP 이전의 「기준 질문 하나」는 DROP 으로 행이 사라졌으므로 목록에 없다(예상대로). error 로그에 fail·error·schema 0건
- 결과: 통과

### S-2. 메시지 테이블이 없는 상태에서 화면에서 대화를 지운다
- 조작: 테이블이 있는 상태에서 「삭제 대상 셋」 대화를 만든다(세션 1·메시지 2). 사본 DB 에서 `chatbot_messages` 만 DROP 한다(세션 행은 남겨 지울 대상이 있게 한다). 사이드바의 「삭제 대상 셋 삭제」를 누르고 확인 대화상자의 「삭제」를 누른 뒤 새로고침한다.
- 기대: `DELETE` 요청이 200 이고 목록에서 사라진다. 두 테이블이 모두 있고 그 세션 행이 0개다. `Failed to ... SQLite` 로그가 없다.
- 필수 여부(required): 예
- 실제: 첫 시도(두 테이블 모두 DROP, 「복구 질문 둘」 대상)는 무효로 했다. access 로그에 `DELETE` 가 없었다. 확인 대화상자의 「삭제」 버튼이 DOM 에 두 개 있어 드라이버의 ref 클릭이 「Selector matched multiple elements」로 실패했기 때문이다. 목록에서 사라진 것은 DROP 으로 세션 행이 없어진 결과였다. 다시 한 조작에서는 보이는 「삭제」 버튼을 `js` 로 눌렀다. `DELETE /api/kr/chatbot/history?session_id=dcda6ecd-…` 200, 뒤이은 `GET /api/kr/chatbot/sessions` 200. 삭제 직후와 새로고침 뒤 모두 화면에 「삭제 대상 셋」 없음, 사이드바 「저장된 대화가 없습니다.」(스크린샷 `chat034-s2.png`). 사본 DB 테이블 세 개 모두 있음, 해당 세션 행 0. error 로그 fail·error·schema 0건
- 결과: 통과

### S-3. 메모리 테이블이 없는 상태에서 프로필이 저장되고 다시 읽힌다
- 조작: 사본 DB 에서 `chatbot_memories` 를 DROP 한다. 「프로필 설정 열기」에서 이름을 「QA복구사용자」로 바꾸고 「저장」을 누른 뒤 새로고침하고 다시 연다.
- 기대: 저장 요청이 200, 새로고침 뒤 조회가 그 이름을 돌려준다. `chatbot_memories` 가 다시 있고 행이 생겼다. `Failed to ... SQLite` 로그가 없다.
- 필수 여부(required): 예
- 실제: `POST /api/kr/chatbot/profile` 200. 사본 DB 에 `chatbot_memories` 가 다시 생겼고 소유자 있는 `user_profile` 행 `{"name":"QA복구사용자","persona":""}`. 새로고침 뒤 `GET /api/kr/chatbot/profile` 200 `{"profile":{"name":"QA복구사용자","persona":""}}`, 설정 모달의 이름 칸도 「QA복구사용자」(스크린샷 `chat034-s3.png`). error 로그 fail·error·schema 0건
- 결과: 통과

### S-4. 화면 회귀 없음
- 조작: 콘솔 오류·`/_next/mcp get_errors`·gunicorn access 로그의 5xx 를 확인한다.
- 기대: 5xx·콘솔 오류·프레임워크 오류 0. 무관한 오류는 원인과 함께 따로 적는다.
- 필수 여부(required): 예
- 실제: `console --errors` 「no console errors」, `/_next/mcp get_errors` `configErrors:[]`·`sessionErrors:[]`. access 로그 66건(GET 59·POST 6·DELETE 1) 모두 2xx, 4xx·5xx 0. error 로그에 Traceback·ERROR·Failed to 0건
- 결과: 통과

## 범위 밖 관찰
- 확인 대화상자의 「삭제」 버튼이 접근성 트리에 두 번 잡힌다(같은 ref 두 줄). 사람의 클릭에는 영향이 없고 드라이버 조작에만 걸렸으므로 이번 판정과 무관하다. 원인은 확인하지 않았다
- 프로필 이름을 바꾼 뒤에도 빈 대화 화면의 인사말은 「User님」이다. 인사말이 어느 값을 읽는지는 이번 범위에서 확인하지 않았다
