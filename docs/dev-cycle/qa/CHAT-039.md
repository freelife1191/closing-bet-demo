# [CHAT-039] 메시지 테이블 유실 뒤 JSON 스냅샷으로 메시지 되살리기 — QA 시나리오

- 대상 화면: http://localhost:3752/chatbot (격리 Next). 백엔드는 격리 gunicorn http://127.0.0.1:5752
- 구성 근거: TODO 설계(모든 세션의 메시지가 비면 `updated_at` 이 같은 세션만 스냅샷에서 되살리고 조건부로 DB 에 다시 쓴다)와 리뷰 반영(쓰기 실패는 읽기 실패로 다룸, 쓴 뒤 DB 재적재). 기대값은 이번 QA 가 보낸 질문 자체이므로 원본 `data/` 를 읽지 않는다
- 유실을 만드는 방법: 서버가 떠 있는 채로 사본 DB 에서 `chatbot_messages` 만 DROP 한다. 파일 서명이 바뀌므로 다음 요청의 재적재가 테이블을 복구하고 되살리기를 탄다
- 스냅샷 주기는 코드 기본값(15초)을 그대로 쓴다. 한 대화의 마지막 저장이 주기에 걸려 스냅샷에 들어가지 않은 판은 되살리지 못하는 것이 설계상 한계이며, S-1 이 그 경계를 함께 드러낸다
- 구성 2026-09-23 13:45 | 실행 2026-09-23 13:50~13:53 (1회차)
- 검증 기준 커밋: `182b67e` (첫 커밋, `code/` 는 `git archive 182b67e3`). 사본의 범위 파일 세 개(`chatbot/storage.py`·`storage_sqlite_history.py`·`storage_sqlite_helpers.py`)가 원본 작업 트리와 바이트 단위로 같음을 `cmp` 로 확인했다
- QA 엔진(engine): Claude Code, 브라우저는 gstack `browse`. 원본 3500/5501·live 주소·원본 `.env`·원본 `data/` 는 쓰지 않는다. 원본 PYTHONPATH 의 앱을 scratch cwd 로 띄우지 않는다
  - 코드 사본 `code/`, `.env`·`secrets/` 없음. 챗봇 DB 는 사본 안에 새로 생긴다
  - gunicorn: `env -i`, `code/` 를 `--pythonpath`, cwd `run/`, `SCHEDULER_ENABLED=false`, 더미 `INTERNAL_IDENTITY_SECRET`, 1 worker 8 threads, `127.0.0.1:5752`. 진입점은 `run/qa_flask_app.py`(가짜 LLM, `[CHAT-034]` 와 같은 방식)
  - 실행 디렉터리 `run/`: 원본 `data/` 의 JSON·CSV 를 읽기 전용으로 복사(`chatbot*` 제외). 챗봇 DB·스냅샷은 사본 `code/data/` 에 새로 생겼다
  - Next: 첫 커밋의 `frontend/` 사본(`node_modules` 는 `cp -cR`), `API_URL=http://127.0.0.1:5752`, 더미 `NEXTAUTH_SECRET`·`INTERNAL_IDENTITY_SECRET`, python `os.setsid` 로 자기 세션에서 `npm run dev -- -p 3752`
- 금지 조작: 실제 LLM 호출, 설정 저장, Refresh VCP, 실패 AI 재분석, GEMINI 재분석, Refresh Market Gate, 모의 매수. 삭제는 이번 QA 가 사본에서 만든 대화만 대상
- 단계(phase): 시나리오 구성 완료 | 실행 완료
- 반복(iteration): 1회
- 결과: 통과 (필수 3/3)
- 증거: 각 시나리오의 「실제」 줄(browse `snapshot`·`js` 출력, 사본 SQLite·JSON 조회, gunicorn access 로그) · 스크린샷 scratchpad `chat039-s1.png`·`chat039-s2.png`(두 장 모두 열어 확인) · 로그 사본 scratchpad `chat039-access.log`·`chat039-flask.log`
- 정리(cleanup): browse 서버 정지, 격리 gunicorn 마스터 TERM, 격리 Next 세션 그룹 TERM. 3752/5752 와 원본 3500/5501 리스너 0, 사본 경로 프로세스 0, 사본 `qa-chat039/`(`qa_flask_app.py`·챗봇 DB·스냅샷 포함) 삭제. 루트 `node_modules/.vite` 없음, 작업 트리 변화 없음. 사본 구성 시각 이후 원본 `data/`·`logs/` 에서 수정 시각이 바뀐 파일 0개. venv 의 `.pth` 에 원본 저장소를 가리키는 줄 없음
- 필수 여부(required): 예
- browser_applicability: required. 사용자가 챗봇 화면에서 대화 목록과 본문을 여는 흐름이 재적재·되살리기 경로를 지난다. browser_driver: gstack `browse`
- 읽은 정본: `.claude/skills/closing-bet-python/SKILL.md`, `.claude/skills/closing-bet-verify/SKILL.md`

## 시나리오

### 준비. 두 대화 만들기
- 조작: 「+ 새 채팅」에서 「되살릴 대화 A 첫 질문」, 이어 「되살릴 대화 A 둘째 질문」을 보낸다. 16초 이상 기다린 뒤 새 채팅에서 「대화 B 질문」을 보낸다(이 저장이 A 의 마지막 판을 스냅샷에 싣는다).
- 기대: 사본 DB 에 A 메시지 4개·B 메시지 2개. 사본 JSON 스냅샷의 A 는 메시지 4개이고 `updated_at` 이 DB 와 같다.
- 실제: A 의 두 질문 직후 스냅샷의 A 는 첫 판(제목 없음, 메시지 0, `13:51:19`)에 머물렀다. 두 번째 저장이 15초 주기에 걸렸기 때문이다. 17초 뒤 B 를 보내자 스냅샷의 A 가 메시지 4개·`updated_at 13:51:26.041725` 로 DB 와 같아졌고, 이번에는 B 가 첫 판(메시지 0, `13:51:57.288494`)에 머물렀다. DB 는 A 4개·B 2개

### S-1. 메시지 테이블이 사라진 뒤 새로고침하면 A 의 본문이 그대로 보인다 (핵심)
- 조작: 사본 DB 에서 `chatbot_messages` 를 DROP 한다(세션 행은 남음). 새로고침하고 사이드바의 A 를 연다.
- 기대: A 본문에 질문 두 개와 응답 두 개. 사본 DB 의 A 메시지 행 4개, 스냅샷의 A 메시지 4개 유지. error 로그에 `Restored messages of` 한 줄, `Failed to restore` 없음. B 는 마지막 저장이 스냅샷 주기에 걸렸다면 되살리지 않는다(설계 한계, 결과를 그대로 기록).
- 필수 여부(required): 예
- 실제: DROP 뒤 남은 테이블 `chatbot_sessions,chatbot_memories`. 새로고침 뒤 사이드바 「최근 대화」에 A 하나. A 를 열자 본문에 질문 두 개와 「응답: …」 두 개(스크린샷 `chat039-s1.png`). 사본 DB 테이블 세 개 모두 있음, A 메시지 행 4, 스냅샷의 A 메시지 4 유지. B 는 DB 메시지 0 이고 사용자 메시지가 없어 목록에서 빠졌다. 스냅샷의 B 가 첫 판이라 `updated_at` 이 달라 되살리지 않은 것이며 설계 한계대로다. access 로그의 `GET /api/kr/chatbot/sessions`·`/history` 모두 200. 기대에 적은 `Restored messages of` 로그 줄은 관측하지 못했다: 이 격리 구성에서 앱 logger 의 WARNING 은 gunicorn `--error-logfile` 로 오지 않는다(파일에 기동 4줄만 있음). 그래서 되살리기의 증거는 DB 행 수와 화면으로 삼았다
- 결과: 통과

### S-2. 되살린 뒤 쓰기가 막히지 않는다
- 조작: A 에 「되살린 뒤 질문」을 보내고 새로고침한다.
- 기대: 응답이 오고 새로고침 뒤에도 A 에 메시지 6개. 사본 DB 의 A 행 6개.
- 필수 여부(required): 예
- 실제: `POST /api/kr/chatbot` 200. 새로고침 뒤 A 를 열자 「응답: …」 3개와 「되살린 뒤 질문」 표시(스크린샷 `chat039-s2.png`). 사본 DB 의 A 메시지 행 6. 되살린 뒤 쓰기가 막히지 않았다
- 결과: 통과

### S-3. 화면 회귀 없음
- 조작: 콘솔 오류·`/_next/mcp get_errors`·gunicorn access 로그의 5xx 를 확인한다.
- 기대: 5xx·콘솔 오류·프레임워크 오류 0.
- 필수 여부(required): 예
- 실제: `console --errors` 「no console errors」, `/_next/mcp get_errors` `configErrors:[]`·`sessionErrors:[]`. access 로그 31건(GET 27·POST 4) 모두 2xx, 4xx·5xx 0. gunicorn 오류 로그에 Traceback·ERROR·Failed to 0건
- 결과: 통과

## 범위 밖 관찰
- 앱 logger 의 경고가 격리 gunicorn 오류 로그에 오지 않아, `[CHAT-034]` QA 의 「error 로그 fail·error·schema 0건」 판정도 같은 제약 아래 있었다. 운영 구성의 로그 경로(`logs/backend.log`)와 다른지 확인하지 않았다
