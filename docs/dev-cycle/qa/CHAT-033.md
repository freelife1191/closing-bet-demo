# [CHAT-033] 챗봇 저장소의 스레드 동시성 확보 — QA 시나리오

- 대상 화면: http://localhost:3730/chatbot (격리 Next). 백엔드는 격리 gunicorn http://127.0.0.1:5730 을 운영과 같은
  `--workers 2 --threads 8` 로 띄운다
- 구성 근거: `[CHAT-033]` 의 QA 줄(같은 계정 두 탭에서 동시에 보낸 뒤 새로고침하면 두 대화와 메시지가 모두 남는다) + 설계
  승인(인스턴스 잠금, 폴백 제거) + 코드 리뷰 지적 1·2(실패 뒤 재적재). 기대값은 이번 QA 가 보낸 메시지 자체이므로 원본
  `data/` 를 읽지 않는다
- 구성 2026-09-23 | 실행 (미실행)
- 검증 기준 커밋: (첫 커밋 뒤 기록)
- QA 엔진(engine): Claude Code, 브라우저는 gstack `browse`. 원본 3500/5501·live 주소·원본 `.env` 는 쓰지 않는다. 챗봇 전송은
  LLM 비용과 기록이 남는 조작이므로 원본에서 하지 않는다. 작업 트리를 scratchpad `qa-chat033/` 로 복사(`.env*`·`.git`·
  `venv`·`logs` 제외, `frontend/node_modules` 는 APFS clone)하고, 사본에만 QA 전용 진입점 `qa_flask_app.py` 를 둔다. 이
  진입점은 `engine.genai_client.build_genai_client` 를 가짜 클라이언트로 바꾼다. 가짜 클라이언트는 3초 기다린 뒤 마지막
  사용자 문장을 「응답: <문장>」으로 돌려준다. 3초 지연은 두 탭의 요청이 서버 안에서 실제로 겹치게 하기 위해서다. 더미 값
  (`NEXTAUTH_SECRET`·`INTERNAL_IDENTITY_SECRET`·`ADMIN_EMAILS`, `SCHEDULER_ENABLED=false`, 쿼터 가드의 서버 키 판정용
  `GOOGLE_GENAI_USE_VERTEXAI=true`·`GOOGLE_CLOUD_PROJECT=qa-stub`)만 환경 변수로 준다
- 「같은 계정」의 대체: 격리 환경에서는 Google 로그인을 할 수 없다. 같은 브라우저의 두 탭은 같은 서명된 익명 신원을
  공유하고, `resolve_chatbot_owner_id` 는 로그인 이메일이 없으면 그 신원을 소유자로 쓴다. 따라서 두 탭은 같은 소유자의 두
  세션이다. 로그인 계정 자체의 경로는 이 QA 가 덮지 않는다
- 단계(phase): 시나리오 구성 완료 | 실행 대기
- 반복(iteration): 0회
- 결과: (미실행)
- 필수 여부(required): 예
- browser_applicability: required. 사용자가 챗봇 화면의 두 탭에서 대화하고 새로고침으로 목록을 확인하는 흐름이다.
  browser_driver: gstack `browse`
- 읽은 정본: `.claude/skills/closing-bet-python/SKILL.md`, `.claude/skills/closing-bet-verify/SKILL.md`
- baseline 상태: 고치기 전 코드에서 새 테스트 `tests/chatbot/test_storage_concurrency.py` 가운데 메모리 update·델타 실패
  뒤 다른 워커 세션 보존·읽기 실패 뒤 이관 금지 세 건은 결정적으로 실패했다(리뷰어 재실행 6/6). 히스토리 스레드 테스트는
  확률적이다(작성자 3/4, 리뷰어 2/6 실패). 이 한 건은 회귀 방지 장치로서 약하며, 나머지 결정적 테스트가 설계의 핵심 갈래를
  고정한다. 리뷰 반영분 세 건(실패 뒤 서명 비움, 재적재 실패 중 쓰기 거부, 기동 시점 읽기 실패)은 변이 실험으로 각 테스트가 실패함을 확인했다. 정적 검증: 전체 `pytest -q` 2629 passed 2 skipped exit 0, `tests/chatbot` 236 passed. frontend 변경이 없어 type-check·vitest 는 생략

## 시나리오

### S-1. 같은 소유자의 두 탭에서 동시에 보낸 대화가 모두 남는다 (핵심)
- 조작: 탭 A·B 에서 각각 `/chatbot` 을 열고 새 대화를 시작한다. 탭 A 에 「탭A-1」, 곧바로 탭 B 에 「탭B-1」을 보낸다(3초
  지연 안에 겹친다). 두 답변이 끝나면 같은 방식으로 「탭A-2」·「탭B-2」를 한 번 더 보낸다. 두 탭을 새로고침한다.
- 기대: 두 탭 모두 사이드바 대화 목록에 「탭A-1」·「탭B-1」 제목의 대화 두 개가 보인다. 각 대화를 열면 사용자 두 줄과
  「응답: …」 두 줄, 모두 네 줄이 순서대로 있다. 사본 SQLite 의 두 세션 메시지 수가 각각 4 다.
- 필수 여부(required): 예

### S-2. 두 탭에서 동시에 넣은 메모리가 모두 남는다 (인접)
- 조작: 탭 A 에 `/memory add qa_a 1`, 곧바로 탭 B 에 `/memory add qa_b 2` 를 보낸 뒤 한 탭에서 `/memory view` 를 보낸다.
- 기대: `/memory view` 응답에 `qa_a` 와 `qa_b` 가 모두 있다.
- 필수 여부(required): 예

### S-3. 삭제한 대화가 다른 탭의 전송으로 되살아나지 않는다 (인접, 폴백 제거)
- 조작: 탭 A 에서 「탭A-1」 대화를 삭제한다. 탭 B 에서 「탭B-1」 대화에 「탭B-3」을 보낸다. 두 탭을 새로고침한다.
- 기대: 두 탭의 대화 목록에 「탭A-1」 대화가 없고 「탭B-1」 대화에는 여섯 줄이 있다. 사본 SQLite 에 삭제한 세션 행이 없다.
- 필수 여부(required): 예

### S-4. 콘솔 오류와 컴파일 문제가 없다 (인접)
- 조작: `console --clear` 뒤 S-1~S-3 을 마치고 `console --errors` 를 읽는다. `/_next/mcp` 에 `get_errors` 와
  `get_compilation_issues` 를 보낸다. 격리 gunicorn 로그에서 `Traceback`·`KeyError`·`delta save failed` 를 찾는다.
- 기대: 콘솔 오류 0, `/_next/mcp` 목록 비어 있음, 로그 세 문자열 0건.
- 필수 여부(required): 예
