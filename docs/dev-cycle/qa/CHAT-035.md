# [CHAT-035] HistoryManager 의 책임 분리 — QA 시나리오

- 대상 화면: http://localhost:3753/chatbot (격리 Next). 백엔드는 격리 gunicorn http://127.0.0.1:5753 을 운영과 같은
  `--workers 2 --threads 8` 로 띄운다. 워커가 둘이어야 다른 워커의 쓰기를 서명 변화로 다시 읽는 경로(`storage_signature`)와
  읽기 캐시 무효화가 실제로 돈다
- 구성 근거: TODO 의 QA 줄(대화 생성·메시지 송수신·삭제 후 새로고침 → 목록과 본문이 조작한 대로 남는다) + 이번 변경(레거시
  스냅샷·읽기 캐시·델타 장부를 부품으로 옮김, 동작 변화 0). 기대값은 이번 QA 가 보낸 메시지 자체이므로 원본 `data/` 를 읽지 않는다
- 구성 2026-09-23 | 실행: (공란)
- 검증 기준 커밋: (첫 커밋 뒤 기록)
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
- 단계(phase): 시나리오 구성 완료 | 실행 (공란)
- 반복(iteration): (공란)
- 결과: (공란)
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
- 실제:
- 결과:
- 증거:

### S-2. 메시지 하나를 지우면 새로고침 뒤에도 그 메시지만 빠진다 (메시지 캐시 무효화)
- 조작: A 대화에서 「QA35-A2」 메시지를 화면의 메시지 삭제 수단으로 지운다(`frontend/src/app/chatbot/page.tsx` 의
  `DELETE /api/kr/chatbot/history?session_id=…&index=…`). 새로고침한 뒤 A 대화를 연다.
- 기대: A 대화에서 「QA35-A2」 줄만 빠지고 나머지 세 줄이 남는다. 사본 SQLite 의 A 메시지 수가 3 이다.
- 필수 여부(required): 예
- 실제:
- 결과:
- 증거:

### S-3. 대화 하나를 지우면 새로고침 뒤에도 사라지고 다른 대화는 남는다 (삭제 장부·강제 스냅샷)
- 조작: 사이드바에서 B 대화를 삭제하고 확인한다. 새로고침한다.
- 기대: 사이드바에 A 대화 하나만 남는다. 사본 SQLite 에 B 세션 행과 메시지 행이 없다. 사본 레거시 스냅샷
  `chatbot_history.json` 에도 B 가 없다(삭제는 스냅샷을 강제로 쓴다).
- 필수 여부(required): 예
- 실제:
- 결과:
- 증거:

### S-4. 콘솔 오류·서버 오류가 없다 (인접)
- 조작: S-1~S-3 동안 `console --errors` 를 읽고, `/_next/mcp` 에 `get_errors` 를 보내며, gunicorn access 로그의 상태 코드와 오류
  로그의 `Traceback`·`ERROR`·`Failed to` 를 센다.
- 기대: 콘솔 오류 0, `/_next/mcp` 오류 목록 비어 있음, access 로그 5xx 0, 오류 로그 해당 문자열 0건.
- 필수 여부(required): 예
- 실제:
- 결과:
- 증거:
