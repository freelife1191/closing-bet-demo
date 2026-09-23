# [INFRA-078] runtime_cache.db 경로를 cwd 기준 data/ 로 — QA 시나리오

- 대상 화면: http://localhost:3748/dashboard/kr (격리 Next). 백엔드는 격리 gunicorn http://127.0.0.1:5748
- 구성 근거: `[INFRA-078]` 의 QA 줄(원본 코드를 `data/` 사본 cwd 로 띄워 대시보드를 연 뒤 원본 DB 가 그대로이고 사본 DB 에
  캐시 행이 생긴다). 기대값은 이번에 바꾼 다섯 상수와, 그 상수를 쓰는 캐시가 만드는 SQLite 테이블이다
- 구성 2026-09-23
- 검증 기준 커밋: 첫 커밋(아래 「실행」에 해시 기록). 비교 대상은 수정 전 커밋 `56f351d6`
- QA 엔진(engine): Claude Code, 브라우저는 gstack `browse`. 원본 3500/5501·live 주소·원본 `.env`·원본 `data/` 는 쓰지 않는다.
  `browser-notes.md` 「공통」 절에 따라 원본 PYTHONPATH 의 앱을 scratch cwd 로 띄우지 않는다. 대신 같은 구조를 사본 안에서
  재현한다.
  - 코드 사본 `code-before/`(`git archive 56f351d6`)·`code-after/`(`git archive <첫 커밋>`). `.env` 없음. 각 사본의
    `data/` 에는 표식 DB `runtime_cache.db`(빈 SQLite) 하나만 둔다. 이 파일이 VCP-026 의 「원본 `data/runtime_cache.db`」
    자리다
  - 실행 디렉터리 `run-before/`·`run-after/`: 원본 `data/` 의 JSON·CSV 만 읽기 전용으로 복사한 `data/` 를 담고
    `runtime_cache.db` 는 두지 않는다. gunicorn 의 cwd 이며 `--pythonpath` 로 코드 사본을 가리킨다
  - gunicorn: `SCHEDULER_ENABLED=false`, 더미 `INTERNAL_IDENTITY_SECRET`, 1 worker, `127.0.0.1:5748`. venv 는 저장소 것을
    쓴다(읽기만 함)
  - Next: 작업 트리 `frontend/` 를 scratchpad 로 rsync(`node_modules`·`.next` 제외, `node_modules` 는 `cp -cR`),
    `PORT=3748 API_URL=http://127.0.0.1:5748`, 더미 `NEXTAUTH_SECRET`·`INTERNAL_IDENTITY_SECRET`, `npm run dev -- -p 3748`
- 금지 조작: 설정 저장, Refresh VCP, 실패 AI 재분석, GEMINI 재분석, Refresh Market Gate, 챗봇 전송, 모의 매수, 삭제 계열. GET 화면
  조회만 한다
- 단계(phase): 시나리오 구성 완료
- 필수 여부(required): 예
- browser_applicability: required. 대시보드 조회가 데이터 상태·누적 성과·백테스트 요약 API 를 불러 이번에 바꾼 캐시를 쓰는 흐름이다.
  browser_driver: gstack `browse`
- 읽은 정본: `.claude/skills/closing-bet-python/SKILL.md`, `.claude/skills/closing-bet-verify/SKILL.md`,
  `.claude/skills/dev-cycle/references/browser-notes.md`

## 시나리오

### S-1. 수정 전 코드는 코드 사본의 `data/runtime_cache.db` 에 쓴다 (대조군)
- 조작: `code-before` + `run-before` 로 gunicorn 을 띄우고, 격리 Next 로 대시보드를 연다. 서버를 내린 뒤 두 DB 를 비교한다.
- 기대: 코드 사본의 표식 DB 에 캐시 테이블이 생기거나 해시가 바뀐다. 이것이 VCP-026 에서 원본에 기록된 현상의 재현이다.
- 필수 여부(required): 예 (대조군이 재현되지 않으면 S-2 의 통과가 수정의 증거가 되지 못한다)

### S-2. 수정 후 코드는 cwd 의 `data/runtime_cache.db` 에만 쓴다 (핵심)
- 조작: `code-after` + `run-after` 로 S-1 과 같은 화면 조작을 한다.
- 기대: 코드 사본의 표식 DB 는 해시와 수정 시각이 그대로다. `run-after/data/runtime_cache.db` 가 새로 생기고, 조작이 부른 캐시의
  테이블이 그 안에 있다. 어느 캐시가 불렸는지는 gunicorn access 로그의 요청 경로로 대조한다.
- 필수 여부(required): 예

### S-3. 대시보드가 정상으로 그려진다 (회귀)
- 조작: S-2 의 대시보드에서 데이터 상태·누적 성과 영역을 읽고 콘솔·`/_next/mcp get_errors` 를 확인한다.
- 기대: 캐시 경로 변경으로 생긴 API 오류(5xx)가 없고 화면에 값이 그려진다. 외부 시세 조회 실패처럼 이번 변경과 무관한 오류는
  원인과 함께 따로 적는다.
- 필수 여부(required): 예
