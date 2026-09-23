# [CHAT-035] HistoryManager 의 책임 분리 — QA 시나리오

- 대상 화면: http://localhost:3753/chatbot (격리 Next). 백엔드는 격리 gunicorn http://127.0.0.1:5753 을 운영과 같은
  `--workers 2 --threads 8` 로 띄운다. 워커가 둘이어야 다른 워커의 쓰기를 서명 변화로 다시 읽는 경로(`storage_signature`)와
  읽기 캐시 무효화가 실제로 돈다
- 구성 근거: TODO 의 QA 줄(대화 생성·메시지 송수신·삭제 후 새로고침 → 목록과 본문이 조작한 대로 남는다) + 이번 변경(레거시
  스냅샷·읽기 캐시·델타 장부를 부품으로 옮김, 동작 변화 0). 기대값은 이번 QA 가 보낸 메시지 자체이므로 원본 `data/` 를 읽지 않는다
- 구성 2026-09-23 17:55 | 실행 2026-09-23 17:58~18:02 (1회차)
- 검증 기준 커밋: `87c46cb` (첫 커밋, `code/` 는 `git archive 87c46cb0`). 사본의 범위 파일 두 개(`chatbot/storage.py`·`chatbot/storage_history_parts.py`)가 원본 작업 트리와 바이트 단위로 같음을 `cmp` 로 확인했다. 챗봇 DB 와 스냅샷은 `code/data/` 에 새로 생겼다(`HistoryManager` 의 기본 경로가 모듈 기준 `data/` 다)
- QA 엔진(engine): Claude Code, 브라우저는 gstack `browse`. 원본 3500/5501·live 주소·원본 `.env`·원본 `data/` 는 쓰지 않는다.
  `browser-notes.md` 「공통」 절에 따라 원본 PYTHONPATH 의 앱을 scratch cwd 로 띄우지 않는다
  - 코드 사본 `code/`(`git archive <첫 커밋>`). `.env`·`secrets/` 없음. 챗봇 DB 는 사본 안에 새로 생긴다
  - 실행 디렉터리 `run/`: 원본 `data/` 의 JSON·CSV 를 읽기 전용으로 복사(챗봇 저장소 파일은 복사하지 않아 빈 저장소에서 시작)
  - gunicorn: `env -i`, `code/` 를 `--pythonpath`, cwd `run/`, `SCHEDULER_ENABLED=false`, 더미 `INTERNAL_IDENTITY_SECRET`,
    쿼터 가드용 더미 `GOOGLE_GENAI_USE_VERTEXAI=true`·`GOOGLE_CLOUD_PROJECT=qa-stub`, `127.0.0.1:5753`. 진입점은 `run/` 에만 둔
    `qa_flask_app.py` 이며 `engine.genai_client.build_genai_client` 를 가짜 클라이언트로 바꾼다. 가짜 클라이언트는 LLM 을 부르지
    않고 「응답: <마지막 입력 일부>」를 한 청크로 돌려준다
  - Next: 첫 커밋의 `frontend/` 사본(`node_modules` 는 `cp -cR`), `API_URL=http://127.0.0.1:5753`, 더미 `NEXTAUTH_SECRET`·
    `INTERNAL_IDENTITY_SECRET`, 자기 세션에서 `npm run dev -- -p 3753`
- 금지 조작: 실제 LLM 호출, 설정 저장, Refresh VCP, 실패 AI 재분석, GEMINI 재분석, Refresh Market Gate, 모의 매수. 삭제는 이번
  QA 가 사본에서 만든 대화·메시지만 대상으로 한다
- 단계(phase): 시나리오 구성 완료 | 실행 완료
- 반복(iteration): 1회. S-2 의 첫 클릭은 모달을 열었는데 스냅샷 grep 이 모달 버튼을 보여 주지 않아 같은 버튼을 다시 눌렀고, 모달에 가려 시간 초과가 났다. 대상은 두 번 모두 index 2 였고 삭제 요청은 확인 버튼 한 번으로 1건만 나갔다(access 로그 DELETE 1건)
- 결과: 통과 (필수 4/4)
- 증거: 각 시나리오의 「실제」 줄(browse `js`·`snapshot` 출력, 사본 SQLite 읽기 전용 조회, 사본 JSON 스냅샷, gunicorn access 로그) · 스크린샷 scratchpad `chat035-s1.png`·`chat035-s2.png`·`chat035-s3.png`(세 장 모두 열어 확인) · 로그 사본 scratchpad `chat035-access.log`·`chat035-flask.log`·`chat035-next.log`
- 정리(cleanup): browse 서버 정지, 격리 gunicorn 마스터 TERM, 격리 Next 세션 그룹 TERM, 사본 경로에 남은 Next 텔레메트리 전송 프로세스 두 개 TERM. 3753/5753 과 원본 3500/5501 리스너 0, 사본 경로 프로세스 0, 사본 `qa-chat035/`(`qa_flask_app.py`·챗봇 DB·스냅샷 포함) 삭제. 루트 `node_modules/.vite` 없음, 작업 트리 변화 없음. 사본 구성 시각 이후 원본 `data/`·`logs/` 에서 수정 시각이 바뀐 파일 0개
- 필수 여부(required): 예
- browser_applicability: required. 사용자가 챗봇 화면에서 대화를 만들고 지운 뒤 새로고침으로 목록과 본문을 확인하는 흐름이다.
  browser_driver: gstack `browse`
- 읽은 정본: `.claude/skills/closing-bet-python/SKILL.md`, `.claude/skills/closing-bet-verify/SKILL.md`
- baseline 상태: 정적 검증은 리뷰 반영 뒤 `tests/chatbot` 271 passed, 원본 트리 전체 `pytest -q` 2701 passed 2 skipped exit 0. frontend 변경이
  없어 type-check·vitest 는 생략

## 시나리오

### S-1. 대화 두 개를 만들고 새로고침하면 목록과 본문이 그대로 남는다 (핵심: 델타 저장·재적재)
- 조작: `/chatbot` 에서 새 대화를 시작해 「QA35-A1」을 보내고 응답을 기다린 뒤 「QA35-A2」를 보낸다. 새 대화를 시작해
  「QA35-B1」을 보낸다. 새로고침한다.
- 기대: 사이드바에 「QA35-B1」·「QA35-A1」 제목의 대화 두 개가 최근 순으로 보인다. A 대화를 열면 사용자 두 줄과 「응답: …」 두
  줄이 순서대로 있다. 사본 SQLite 의 두 세션 메시지 수가 4·2 다.
- 필수 여부(required): 예
- 실제: 세 전송 모두 「응답: [사용자 메시지]: QA35-…」가 한 번에 도착했다. 새로고침 뒤 사이드바 순서 `QA35-B1`, `QA35-A1`. A 를 열면 `QA35-A1 / 응답: … QA35-A1 / QA35-A2 / 응답: … QA35-A2`. 사본 SQLite: `QA35-B1|2`, `QA35-A1|4`. 워커 두 개가 요청을 나눠 받았으므로 저장 워커와 읽기 워커가 다른 경우의 재적재 경로를 지났다(어느 요청이 어느 워커로 갔는지는 access 로그에 없어 요청별로 확정하지 않았다)
- 결과: 통과
- 증거: `chat035-s1.png`(A 대화 네 줄과 사이드바 두 대화)

### S-2. 메시지 하나를 지우면 새로고침 뒤에도 그 메시지만 빠진다 (메시지 캐시 무효화)
- 조작: A 대화에서 「QA35-A2」 메시지를 화면의 메시지 삭제 수단으로 지운다(`frontend/src/app/chatbot/page.tsx` 의
  `DELETE /api/kr/chatbot/history?session_id=…&index=…`). 새로고침한 뒤 A 대화를 연다.
- 기대: A 대화에서 「QA35-A2」 줄만 빠지고 나머지 세 줄이 남는다. 사본 SQLite 의 A 메시지 수가 3 이다.
- 필수 여부(required): 예
- 실제: 세 번째 메시지(index 2, 「QA35-A2」)의 「이 메시지 삭제」 → 모달 「이 메시지를 삭제하시겠습니까?」의 「삭제」. access 로그 `DELETE /api/kr/chatbot/history?session_id=edfcd46f-…&index=2 … 200`. 새로고침 뒤 A 를 열면 `QA35-A1 / 응답: … QA35-A1 / 응답: … QA35-A2` 로 「QA35-A2」 한 줄만 빠졌다. 사본 SQLite: `QA35-A1|3`, `QA35-B1|2`
- 결과: 통과
- 증거: `chat035-s2.png`(새로고침 뒤 A 대화 세 줄, 사이드바에 두 대화)

### S-3. 대화 하나를 지우면 새로고침 뒤에도 사라지고 다른 대화는 남는다 (삭제 장부·강제 스냅샷)
- 조작: 사이드바에서 B 대화를 삭제하고 확인한다. 새로고침한다.
- 기대: 사이드바에 A 대화 하나만 남는다. 사본 SQLite 에 B 세션 행과 메시지 행이 없다. 사본 레거시 스냅샷
  `chatbot_history.json` 에도 B 가 없다(삭제는 스냅샷을 강제로 쓴다).
- 필수 여부(required): 예
- 실제: 사이드바 「QA35-B1 삭제」 → 모달 「정말 이 대화를 삭제하시겠습니까?」의 「삭제」. 새로고침 뒤 사이드바 버튼은 `QA35-A1` 하나. 사본 SQLite(파이썬 `mode=ro`): 세션 `[('QA35-A1',)]`, 메시지 3, 세션 없는 메시지 0. 사본 `chatbot_history.json`: 제목 `['QA35-A1']`, 메시지 수 `[3]`. sqlite3 CLI 의 `-readonly` 조회는 이때 `unable to open database file (14)` 로 열리지 않았다. 체크포인트 뒤 wal·shm 이 없는 상태에서 읽기 전용으로 공유 메모리 파일을 만들 수 없었던 것으로 보이며, 같은 파일을 파이썬으로 읽어 판정했다
- 결과: 통과
- 증거: `chat035-s3.png`(사이드바 A 하나, A 본문 세 줄)

### S-4. 콘솔 오류·서버 오류가 없다 (인접)
- 조작: S-1~S-3 동안 `console --errors` 를 읽고, `/_next/mcp` 에 `get_errors` 를 보내며, gunicorn access 로그의 상태 코드와 오류
  로그의 `Traceback`·`ERROR`·`Failed to` 를 센다.
- 기대: 콘솔 오류 0, `/_next/mcp` 오류 목록 비어 있음, access 로그 5xx 0, 오류 로그 해당 문자열 0건.
- 필수 여부(required): 예
- 실제: `console --errors` 「(no console errors)」. `/_next/mcp` `get_errors` → `{"configErrors":[],"sessionErrors":[]}`. access 로그 38건 모두 200(4xx·5xx 0). gunicorn 오류 로그·표준 출력 로그의 `Traceback`·`ERROR`·`Failed to` 0건. Next 로그의 `error` 두 줄은 첫 로드 때 페이지를 연달아 두 번 열며 끊긴 NextAuth `CLIENT_FETCH_ERROR`(`/api/auth/session`, `Failed to fetch`)이며, 바로 다음 세션 요청은 200 이었다. 챗봇 저장소와 무관한 dev 서버의 관찰로 기록한다
- 결과: 통과
- 증거: 위 응답 원문, `chat035-next.log` 16~28행
