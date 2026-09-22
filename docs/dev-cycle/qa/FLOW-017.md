# [FLOW-017] 결과·등급 필터를 전체 기간에 건다 — QA 시나리오

- 대상 화면: http://localhost:3717/dashboard/kr/cumulative (격리 Next). 백엔드는 격리 gunicorn http://127.0.0.1:5717
- 구성 근거: `[FLOW-017]` 의 QA 줄 + 설계 승인(순번은 원래 번호 유지, counts 는 필터와 무관) + 리뷰 L1·L2. 기대값은
  격리 Flask 의 `GET /api/kr/closing-bet/cumulative` 응답(필터 없음·`outcome=WIN` 1·2페이지·`grade=D`·`grade=D&outcome=WIN`)에서
  `counts`·`pagination`·각 행의 `no` 와 종목명을 읽어 정했다. 1단계 리포트 도구 대신 이 응답과 TODO 의 QA 줄에서
  시나리오를 만들었다(`[FLOW-016]` 과 같은 방식)
- 구성 2026-09-23 | 실행 (공란)
- 검증 기준 커밋: (첫 커밋 뒤 기록)
- QA 엔진(engine): Claude Code, 브라우저는 gstack `browse`. 원본 3500/5501·live 주소·원본 `.env` 는 쓰지 않는다.
  저장소 작업 트리를 scratchpad `qa-flow017/` 로 복사(`.env`·`.git`·`venv`·`logs` 제외, `frontend/node_modules` 는
  APFS clone)하고, 더미 값(`NEXTAUTH_SECRET=qa-nextauth-secret`, `INTERNAL_IDENTITY_SECRET=qa-identity-secret`,
  `ADMIN_EMAILS=qa-admin@example.com`, `SCHEDULER_ENABLED=false`)만 환경 변수로 준다. 이 화면은 조회 전용이며
  로그인이 필요 없다
- 단계(phase): 시나리오 구성 완료
- baseline 상태: 고치기 전 동작은 vitest RED 3건과 라우트 pytest RED 3건으로 고정했다(「성공」 칩이 현재 페이지 안의
  건수, 필터 클릭이 요청을 보내지 않음, 라우트가 `outcome`·`grade`·`counts`·`no` 를 모름). 사본 `data/` 기준 전체 234건
- 필수 여부(required): 예
- browser_applicability: required. 사용자가 필터 버튼을 누르고 표와 페이지 표기를 읽는 흐름이다. browser_driver: gstack `browse`
- 읽은 정본: `.claude/skills/closing-bet-python/SKILL.md`, `.claude/skills/closing-bet-nextjs/SKILL.md`,
  `.claude/skills/closing-bet-verify/SKILL.md`, `frontend-skills.md` §2, Next 번들 문서 `05-server-and-client-components.md`

## 시나리오

### S-1. 버튼 건수가 전체 목록 기준이다 (회귀)
- 조작: 화면을 열어 결과·등급 버튼의 라벨을 읽는다.
- 기대: 결과 `전체 (234)`·`성공 (86)`·`실패 (140)`·`보유 (8)`, 등급 `전체 (234)`·`S (19)`·`A (34)`·`B (174)`·`D (7)`.
  「현재 페이지 내」 문구가 없다. 하단 `Page 1 of 5`.
- 필수 여부(required): 예

### S-2. 「성공」은 전체 86건을 1페이지부터 보여 주고 원래 번호를 유지한다 (회귀)
- 조작: 다음 페이지로 이동해 2페이지(첫 행 `184 에스피지`)를 확인한 뒤 「성공 (86)」을 누른다. 표를 읽고 다음 페이지로 이동해 다시 읽는다.
- 기대: 요청 `?page=1&limit=50&outcome=WIN` 200. 50행, 첫 행 `223 로보티즈`, 마지막 행 `94 현대모비스`, `Page 1 of 2`.
  다음 페이지는 36행, 첫 행 `93 현대글로비스`, 마지막 행 `1 우리금융지주`, `Page 2 of 2`. 결과 칸이 모두 「성공」.
- 필수 여부(required): 예

### S-3. 두 필터를 함께 걸고 풀 수 있다 (인접, 리뷰 L1)
- 조작: 「성공」이 켜진 채 등급 「D (7)」을 누른다. 이어서 결과 「전체 (234)」를 누른다.
- 기대: 요청 `outcome=WIN&grade=D` → 2행 `5 로킷헬스케어`·`1 우리금융지주`, 페이지 버튼 없음. 칩은 그대로
  `성공 (86)`·`D (7)` 이다(칩은 다른 축의 필터를 무시한 전체 건수라는 승인된 설계). 결과 「전체」 뒤 요청에서
  `outcome` 이 빠지고 7행 `15 현대지에프홀딩스` … `1 우리금융지주`.
- 필수 여부(required): 예

### S-4. 두 필터를 모두 풀면 전체 목록으로 돌아간다 (인접, `[FLOW-016]` 회귀)
- 조작: 등급 「전체 (234)」를 누른다.
- 기대: 요청에 `outcome`·`grade` 가 없다. 첫 행 `234 삼성전기`, `Page 1 of 5`.
- 필수 여부(required): 예

### S-5. 잘못된 필터 값은 400 이다 (인접, CLI)
- 조작: 격리 Flask 에 `curl` 로 `?outcome=All`, `?grade=C`, `?grade=S` 를 보낸다.
- 기대: 400, 400, 200. 화면이 보내지 않는 값이므로 브라우저 대상이 아니다.
- 필수 여부(required): 예

### S-6. 콘솔 오류와 컴파일 문제가 없다 (인접)
- 조작: `console --clear` 뒤 S-1~S-4 를 마치고 `console --errors` 를 읽는다. `/_next/mcp` 에 `get_errors` 와
  `get_compilation_issues` 를 보낸다. 필터 클릭 뒤의 로딩 표시(리뷰 L2)를 관찰해 기록한다.
- 기대: 콘솔 오류 0, `/_next/mcp` 응답의 오류·컴파일 문제 목록이 비어 있다. L2 는 관찰만 기록한다.
- 필수 여부(required): 예

## 이월한 발견

(실행 뒤 기록)
