# [CHAT-033] 챗봇 저장소의 스레드 동시성 확보 — QA 시나리오

- 대상 화면: http://localhost:3730/chatbot (격리 Next). 백엔드는 격리 gunicorn http://127.0.0.1:5730 을 운영과 같은
  `--workers 2 --threads 8` 로 띄운다
- 구성 근거: `[CHAT-033]` 의 QA 줄(같은 계정 두 탭에서 동시에 보낸 뒤 새로고침하면 두 대화와 메시지가 모두 남는다) + 설계
  승인(인스턴스 잠금, 폴백 제거) + 코드 리뷰 지적 1·2(실패 뒤 재적재). 기대값은 이번 QA 가 보낸 메시지 자체이므로 원본
  `data/` 를 읽지 않는다
- 구성 2026-09-23 09:20 | 실행 2026-09-23 09:28~09:33 (1회차)
- 검증 기준 커밋: `bd5adf1` (첫 커밋). 사본의 범위 파일 세 개(`storage.py`·`storage_memory_manager.py`·`storage_history_helpers.py`)가 이 커밋의 파일과 바이트 단위로 같음을 `cmp` 로 확인했다. 실행 중 범위 파일은 바뀌지 않았다
- QA 엔진(engine): Claude Code, 브라우저는 gstack `browse`. 원본 3500/5501·live 주소·원본 `.env` 는 쓰지 않는다. 챗봇 전송은
  LLM 비용과 기록이 남는 조작이므로 원본에서 하지 않는다. 작업 트리를 scratchpad `qa-chat033/` 로 복사(`.env*`·`.git`·
  `venv`·`logs` 제외, `frontend/node_modules` 는 APFS clone)하고, 사본에만 QA 전용 진입점 `qa_flask_app.py` 를 둔다. 이
  진입점은 `engine.genai_client.build_genai_client` 를 가짜 클라이언트로 바꾼다. 가짜 클라이언트는 3초 기다린 뒤 마지막
  사용자 문장을 「응답: <문장>」으로 돌려준다. 3초 지연은 두 탭의 요청이 서버 안에서 실제로 겹치게 하기 위해서다. 더미 값
  (`NEXTAUTH_SECRET`·`INTERNAL_IDENTITY_SECRET`·`ADMIN_EMAILS`, `SCHEDULER_ENABLED=false`, 쿼터 가드의 서버 키 판정용
  `GOOGLE_GENAI_USE_VERTEXAI=true`·`GOOGLE_CLOUD_PROJECT=qa-stub`)만 환경 변수로 준다. 저장소에서 git 이 추적하지 않는 `secrets/`
  (실제 자격 증명)는 사본에서 바로 지웠다. 사본 `data/` 에는 챗봇 저장소 파일이 없어 빈 저장소에서 시작했다
- 「같은 계정」의 대체: 격리 환경에서는 Google 로그인을 할 수 없다. 같은 브라우저의 두 탭은 같은 서명된 익명 신원을
  공유하고, `resolve_chatbot_owner_id` 는 로그인 이메일이 없으면 그 신원을 소유자로 쓴다. 따라서 두 탭은 같은 소유자의 두
  세션이다. 로그인 계정 자체의 경로는 이 QA 가 덮지 않는다
- 단계(phase): 시나리오 구성 완료 | 실행 완료
- 반복(iteration): 1회 (S-3 조작은 드라이버 문제로 두 번 다시 했다. 아래 S-3 참고)
- 결과: 통과 (필수 4/4)
- 증거: 각 시나리오의 「실제」 줄(browse `text`·`js` 출력, 사본 챗봇 SQLite 읽기 전용 조회, 격리 gunicorn 로그) · 스크린샷
  scratchpad `chat033-s1.png`·`chat033-s2.png`·`chat033-s3.png`(세 장 모두 열어 확인) · 격리 로그 `qa-chat033-flask.log`·
  `qa-chat033-next.log` · `/_next/mcp` 응답
- 정리(cleanup): browse 서버 정지, 격리 gunicorn(5730)·Next(3730) 종료 뒤 3730/5730/3500/5501 리스너 0, 사본 경로 프로세스 0,
  사본 `qa-chat033/`(챗봇 저장소 포함) 삭제. 스크린샷과 로그는 scratchpad 에만 있다. 저장소 루트 `node_modules/.vite` 없음.
  원본 3500/5501 은 처음부터 떠 있지 않았고 건드리지 않았다. 원본 `data/runtime_cache.db` 수정 시각은 QA 전후 모두 09:26:29 다
  (09:26 의 변경은 QA 전 전체 pytest 실행 시각대로, `[INFRA-078]` 의 경로다)
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
- 실제: 두 전송 명령 사이 간격 0.54초. gunicorn 로그의 쿼터 차감 시각이 09:29:03.590 과 09:29:03.730 으로 0.14초 차이였으므로,
  3초 지연 동안 두 요청이 서버 안에서 겹쳐 처리되었다. 2회차도 09:29:22.584 와 .664 로 겹쳤다. 새로고침 뒤 두 탭의 사이드바가
  모두 `최근 대화 탭B-1 탭A-1`. 탭 A 에서 두 대화를 차례로 열면 `탭B-1 / 응답: [사용자 메시지]: 탭B-1 / 탭B-2 / 응답: … 탭B-2`,
  `탭A-1 / 응답: … 탭A-1 / 탭A-2 / 응답: … 탭A-2`. 사본 SQLite: 두 세션 모두 소유자 `anon_b228e152-…`(같은 익명 신원),
  메시지 4개씩 user/model 이 번갈아 순서대로 저장됨. 응답 문구의 `[사용자 메시지]: ` 접두는 가짜 클라이언트가 프롬프트 마지막
  줄을 그대로 되돌린 것이다
- 결과: 통과
- 증거: `chat033-s1.png`(탭 A 에서 연 「탭B-1」 대화, 네 줄과 사이드바 두 대화)
- 정리(cleanup): 격리 사본의 챗봇 저장소에만 남았고 사본 삭제로 정리

### S-2. 두 탭에서 동시에 넣은 메모리가 모두 남는다 (인접)
- 조작: 탭 A 에 `/memory add qa_a 1`, 곧바로 탭 B 에 `/memory add qa_b 2` 를 보낸 뒤 한 탭에서 `/memory view` 를 보낸다.
- 기대: `/memory view` 응답에 `qa_a` 와 `qa_b` 가 모두 있다.
- 필수 여부(required): 예
- 실제: 탭 A `✅ 메모리 저장: qa_a = 1`, 탭 B `✅ 메모리 저장: qa_b = 2`, 이어서 탭 B `/memory view` → `🧠 저장된 메모리` 아래
  `qa_a: 1`, `qa_b: 2`. 사본 SQLite `chatbot_memories`: `(anon_b228e152-…, qa_a, "1")`, `(anon_b228e152-…, qa_b, "2")`.
  두 명령은 수 밀리초 안에 끝나는 경로라 이 조작만으로 스레드 경합을 만들기는 어렵다. 경합 자체는
  `test_memory_update_survives_a_reload_from_another_thread` 가 결정적으로 고정하고, 이 시나리오는 사용자 흐름의 회귀만 확인한다.
  탭 A 는 그때 「탭B-1」 대화를 열고 있었으므로 두 명령의 문답은 모두 「탭B-1」 대화에 저장되었다(명령 문답도 대화에 남는 기존 동작)
- 결과: 통과
- 증거: `chat033-s2.png`
- 정리(cleanup): S-1 과 같다

### S-3. 삭제한 대화가 다른 탭의 전송으로 되살아나지 않는다 (인접, 폴백 제거)
- 조작: 탭 A 에서 「탭A-1」 대화를 삭제한다. 탭 B 에서 「탭B-1」 대화에 「탭B-3」을 보낸다. 두 탭을 새로고침한다.
- 기대: 두 탭의 대화 목록에 「탭A-1」 대화가 없고 「탭B-1」 대화에는 여섯 줄이 있다. 사본 SQLite 에 삭제한 세션 행이 없다.
  (S-2 의 명령 문답 여섯 줄이 「탭B-1」에 더해졌으므로 실제 기대 줄 수는 그만큼 늘어난다)
- 필수 여부(required): 예
- 실제: 조작을 세 번 했다. 1회: 삭제 아이콘 → 확인 모달 「정말 이 대화를 삭제하시겠습니까?」의 「삭제」 버튼 클릭이 선택자 중복
  (접근성 이름이 「탭A-1 삭제」와도 맞음)으로 실패해 삭제되지 않았고, 탭 B 의 「탭B-3」만 「탭B-1」에 저장되었다. 2회: 탭 B 가
  새로고침 뒤 「탭A-1」 대화를 열고 있어 「탭B-4」가 그 대화에 들어갔고 확인 클릭은 다시 실패했다. 3회: 탭 B 에서 「탭B-1」을
  먼저 열어 고정하고, 탭 A 에서 삭제 아이콘 → 모달이 뜬 상태에서 탭 B 에 「탭B-5」 전송 → 탭 A 에서 JS 로 텍스트가 정확히
  「삭제」인 버튼 클릭. 결과: 새로고침 뒤 두 탭 사이드바 `최근 대화 탭B-1` 만 남음. 사본 SQLite 세션 1개, 삭제한 세션
  `fe588d18…`(「탭B-4」 포함)의 메시지 행 0. 「탭B-1」은 메시지 14개(탭B-1·2, 명령 3쌍, 탭B-3, 탭B-5 와 각 응답)로, 삭제와 겹쳐
  보낸 「탭B-5」와 그 응답이 남았다. 새 페이지에서 「탭B-1」을 열면 `탭B-1 탭B-2 탭B-3 탭B-5` 가 보인다. 1·2회의 실패는
  브라우저 드라이버 조작의 문제이며 앱 동작의 실패가 아니다. 앱은 매번 요청받은 대로만 저장했다
- 결과: 통과
- 증거: `chat033-s3.png`(사이드바 「탭B-1」 하나, 대화 끝부분 `탭B-3`·`탭B-5` 와 응답)
- 정리(cleanup): S-1 과 같다

### S-4. 콘솔 오류와 컴파일 문제가 없다 (인접)
- 조작: `console --clear` 뒤 S-1~S-3 을 마치고 `console --errors` 를 읽는다. `/_next/mcp` 에 `get_errors` 와
  `get_compilation_issues` 를 보낸다. 격리 gunicorn 로그에서 `Traceback`·`KeyError`·`delta save failed` 를 찾는다.
- 기대: 콘솔 오류 0, `/_next/mcp` 목록 비어 있음, 로그 세 문자열 0건.
- 필수 여부(required): 예
- 실제: S-3 3회차 직후 browse 서버가 스스로 다시 시작되어(`[browse] Starting server...`, `Tab 2 not found`) S-1~S-3 동안의 콘솔
  버퍼를 읽지 못했다. 대신 새 페이지에서 `/chatbot` 을 열고 「탭B-1」 대화를 연 뒤 `console --errors` → `(no console errors)`.
  `/_next/mcp` `get_errors` → `{"configErrors":[],"sessionErrors":[]}`, `get_compilation_issues` → `{"issues":[]}`. 격리 Next 로그의
  `error`·`⨯` 0건. 격리 gunicorn 로그의 `Traceback`·`KeyError`·`delta save failed`·`refusing to write` 0건
- 결과: 통과 (콘솔은 S-1~S-3 전 구간이 아니라 재시작 뒤 페이지 기준. 전 구간의 서버 쪽 오류는 두 로그가 덮는다)
- 증거: 위 응답 원문
- 정리(cleanup): 조회뿐이라 소유한 자료 없음
- 범위 밖 관찰: 빈 사본에서 gunicorn 워커 두 개가 동시에 뜰 때 `Activity logger unavailable: [Errno 17] File exists: 'logs'`
  경고가 한 번 났다. `logs/` 가 없는 트리에서 두 워커가 함께 만들려는 경합이다. 운영은 `restart_all.sh` 가 기동 전에
  `mkdir -p logs` 를 하므로 닿지 않아 TODO 로 올리지 않는다
