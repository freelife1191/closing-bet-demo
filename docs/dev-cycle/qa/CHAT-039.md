# [CHAT-039] 메시지 테이블 유실 뒤 JSON 스냅샷으로 메시지 되살리기 — QA 시나리오

- 대상 화면: http://localhost:3752/chatbot (격리 Next). 백엔드는 격리 gunicorn http://127.0.0.1:5752
- 구성 근거: TODO 설계(모든 세션의 메시지가 비면 `updated_at` 이 같은 세션만 스냅샷에서 되살리고 조건부로 DB 에 다시 쓴다)와 리뷰 반영(쓰기 실패는 읽기 실패로 다룸, 쓴 뒤 DB 재적재). 기대값은 이번 QA 가 보낸 질문 자체이므로 원본 `data/` 를 읽지 않는다
- 유실을 만드는 방법: 서버가 떠 있는 채로 사본 DB 에서 `chatbot_messages` 만 DROP 한다. 파일 서명이 바뀌므로 다음 요청의 재적재가 테이블을 복구하고 되살리기를 탄다
- 스냅샷 주기는 코드 기본값(15초)을 그대로 쓴다. 한 대화의 마지막 저장이 주기에 걸려 스냅샷에 들어가지 않은 판은 되살리지 못하는 것이 설계상 한계이며, S-1 이 그 경계를 함께 드러낸다
- 구성 2026-09-23 | 실행: (공란)
- 검증 기준 커밋: 첫 커밋(구현·계획·이 문서). `code/` 는 그 커밋의 `git archive`
- QA 엔진(engine): Claude Code, 브라우저는 gstack `browse`. 원본 3500/5501·live 주소·원본 `.env`·원본 `data/` 는 쓰지 않는다. 원본 PYTHONPATH 의 앱을 scratch cwd 로 띄우지 않는다
  - 코드 사본 `code/`, `.env`·`secrets/` 없음. 챗봇 DB 는 사본 안에 새로 생긴다
  - gunicorn: `env -i`, `code/` 를 `--pythonpath`, cwd `run/`, `SCHEDULER_ENABLED=false`, 더미 `INTERNAL_IDENTITY_SECRET`, 1 worker 8 threads, `127.0.0.1:5752`. 진입점은 `run/qa_flask_app.py`(가짜 LLM, `[CHAT-034]` 와 같은 방식)
  - Next: 첫 커밋의 `frontend/` 사본, `API_URL=http://127.0.0.1:5752`, 더미 `NEXTAUTH_SECRET`·`INTERNAL_IDENTITY_SECRET`, `npm run dev -- -p 3752`
- 금지 조작: 실제 LLM 호출, 설정 저장, Refresh VCP, 실패 AI 재분석, GEMINI 재분석, Refresh Market Gate, 모의 매수. 삭제는 이번 QA 가 사본에서 만든 대화만 대상
- 단계(phase): 시나리오 구성 완료 | 실행 대기
- 결과: (공란)
- 필수 여부(required): 예
- browser_applicability: required. 사용자가 챗봇 화면에서 대화 목록과 본문을 여는 흐름이 재적재·되살리기 경로를 지난다. browser_driver: gstack `browse`
- 읽은 정본: `.claude/skills/closing-bet-python/SKILL.md`, `.claude/skills/closing-bet-verify/SKILL.md`

## 시나리오

### 준비. 두 대화 만들기
- 조작: 「+ 새 채팅」에서 「되살릴 대화 A 첫 질문」, 이어 「되살릴 대화 A 둘째 질문」을 보낸다. 16초 이상 기다린 뒤 새 채팅에서 「대화 B 질문」을 보낸다(이 저장이 A 의 마지막 판을 스냅샷에 싣는다).
- 기대: 사본 DB 에 A 메시지 4개·B 메시지 2개. 사본 JSON 스냅샷의 A 는 메시지 4개이고 `updated_at` 이 DB 와 같다.

### S-1. 메시지 테이블이 사라진 뒤 새로고침하면 A 의 본문이 그대로 보인다 (핵심)
- 조작: 사본 DB 에서 `chatbot_messages` 를 DROP 한다(세션 행은 남음). 새로고침하고 사이드바의 A 를 연다.
- 기대: A 본문에 질문 두 개와 응답 두 개. 사본 DB 의 A 메시지 행 4개, 스냅샷의 A 메시지 4개 유지. error 로그에 `Restored messages of` 한 줄, `Failed to restore` 없음. B 는 마지막 저장이 스냅샷 주기에 걸렸다면 되살리지 않는다(설계 한계, 결과를 그대로 기록).
- 필수 여부(required): 예

### S-2. 되살린 뒤 쓰기가 막히지 않는다
- 조작: A 에 「되살린 뒤 질문」을 보내고 새로고침한다.
- 기대: 응답이 오고 새로고침 뒤에도 A 에 메시지 6개. 사본 DB 의 A 행 6개.
- 필수 여부(required): 예

### S-3. 화면 회귀 없음
- 조작: 콘솔 오류·`/_next/mcp get_errors`·gunicorn access 로그의 5xx 를 확인한다.
- 기대: 5xx·콘솔 오류·프레임워크 오류 0.
- 필수 여부(required): 예
