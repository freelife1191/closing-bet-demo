# [FLOW-017] 결과·등급 필터를 전체 기간에 건다 — QA 시나리오

- 대상 화면: http://localhost:3717/dashboard/kr/cumulative (격리 Next). 백엔드는 격리 gunicorn http://127.0.0.1:5717
- 구성 근거: `[FLOW-017]` 의 QA 줄 + 설계 승인(순번은 원래 번호 유지, counts 는 필터와 무관) + 리뷰 L1·L2. 기대값은
  격리 Flask 의 `GET /api/kr/closing-bet/cumulative` 응답(필터 없음·`outcome=WIN` 1·2페이지·`grade=D`·`grade=D&outcome=WIN`)에서
  `counts`·`pagination`·각 행의 `no` 와 종목명을 읽어 정했다. 1단계 리포트 도구 대신 이 응답과 TODO 의 QA 줄에서
  시나리오를 만들었다(`[FLOW-016]` 과 같은 방식)
- 구성 2026-09-23 08:08 | 실행 2026-09-23 08:12~08:15 (1회차)
- 검증 기준 커밋: `7b808db` (첫 커밋). 사본의 `kr_market_data_ai_routes.py`·`CumulativeClientPage.tsx` 가 이 커밋의 파일과 바이트 단위로 같음을 `cmp` 로 확인했고 실행 중 범위 파일은 바뀌지 않았다
- QA 엔진(engine): Claude Code, 브라우저는 gstack `browse`. 원본 3500/5501·live 주소·원본 `.env` 는 쓰지 않는다.
  저장소 작업 트리를 scratchpad `qa-flow017/` 로 복사(`.env`·`.git`·`venv`·`logs` 제외, `frontend/node_modules` 는
  APFS clone)하고, 더미 값(`NEXTAUTH_SECRET=qa-nextauth-secret`, `INTERNAL_IDENTITY_SECRET=qa-identity-secret`,
  `ADMIN_EMAILS=qa-admin@example.com`, `SCHEDULER_ENABLED=false`)만 환경 변수로 준다. 이 화면은 조회 전용이며
  로그인이 필요 없다
- 단계(phase): 시나리오 구성 완료 | 실행 완료
- 반복(iteration): 1회
- 결과: 통과 (필수 6/6)
- 증거: 아래 각 시나리오의 「실제」 줄(browse `js`·`network` 출력 원문) · 스크린샷 scratchpad `flow017-s1.png`·`flow017-s2-p1.png`·`flow017-s2-p2.png`·`flow017-s3.png`(열어 확인)·`flow017-s4.png` · 격리 로그 `qa-flow017-flask.log`·`qa-flow017-next.log` · `/_next/mcp` 응답
- 정리(cleanup): browse 서버 정지, 격리 gunicorn(5717)·Next(3717) 종료 뒤 두 포트 리스너 0·사본 경로 프로세스 0, 사본 `qa-flow017/` 삭제. 스크린샷과 로그는 scratchpad 에만 있고 저장소에 없음. 저장소 루트 `node_modules/.vite` 없음. 원본 3500/5501 리스너 0(처음부터 떠 있지 않았고 건드리지 않음). 원본 `data/runtime_cache.db` 의 수정 시각이 실행 중인 08:13:16 으로 바뀌었다. 격리 백엔드가 절대 경로로 원본 캐시에 쓰는 `[INFRA-078]` 의 알려진 경로이며 이 항목의 변경과 무관하다(캐시 행이라 내용은 재계산 가능)
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
- 실제: `{"n":50,"first3":["234 삼성전기","233 디아이","232 SFA반도체"],"last":"185 삼성전자우","page":"Page 1 of 5","chips":["전체 (234)","성공 (86)","실패 (140)","보유 (8)","전체 (234)","S (19)","A (34)","B (174)","D (7)"],"label":false}` (종목명 뒤 코드 생략)
- 결과: 통과
- 증거: `flow017-s1.png`
- 정리(cleanup): 조회 전용이라 이 시나리오가 소유한 자료 없음

### S-2. 「성공」은 전체 86건을 1페이지부터 보여 주고 원래 번호를 유지한다 (회귀)
- 조작: 다음 페이지로 이동해 2페이지(첫 행 `184 에스피지`)를 확인한 뒤 「성공 (86)」을 누른다. 표를 읽고 다음 페이지로 이동해 다시 읽는다.
- 기대: 요청 `?page=1&limit=50&outcome=WIN` 200. 50행, 첫 행 `223 로보티즈`, 마지막 행 `94 현대모비스`, `Page 1 of 2`.
  다음 페이지는 36행, 첫 행 `93 현대글로비스`, 마지막 행 `1 우리금융지주`, `Page 2 of 2`. 결과 칸이 모두 「성공」.
- 필수 여부(required): 예
- 실제: 2페이지 `first3 [184 에스피지, 183 한화생명, 182 LG에너지솔루션]`, `Page 2 of 5` → 「성공 (86)」 클릭 → `GET /api/kr/closing-bet/cumulative?page=1&limit=50&outcome=WIN → 200 (28ms)`, `{"n":50,"first3":["223 로보티즈","218 SK이노베이션","210 한미반도체"],"last":"94 현대모비스","page":"Page 1 of 2"}`, 결과 칸이 「성공」이 아닌 행 0 → Next → `{"n":36,"first3":["93 현대글로비스","92 기아","89 대한항공"],"last":"1 우리금융지주","page":"Page 2 of 2"}`, 「성공」 아닌 행 0
- 결과: 통과
- 증거: `flow017-s2-p1.png`, `flow017-s2-p2.png`
- 정리(cleanup): 조회 전용이라 이 시나리오가 소유한 자료 없음

### S-3. 두 필터를 함께 걸고 풀 수 있다 (인접, 리뷰 L1)
- 조작: 「성공」이 켜진 채 등급 「D (7)」을 누른다. 이어서 결과 「전체 (234)」를 누른다.
- 기대: 요청 `outcome=WIN&grade=D` → 2행 `5 로킷헬스케어`·`1 우리금융지주`, 페이지 버튼 없음. 칩은 그대로
  `성공 (86)`·`D (7)` 이다(칩은 다른 축의 필터를 무시한 전체 건수라는 승인된 설계). 결과 「전체」 뒤 요청에서
  `outcome` 이 빠지고 7행 `15 현대지에프홀딩스` … `1 우리금융지주`.
- 필수 여부(required): 예
- 실제: 「D (7)」 클릭 → `?page=1&limit=50&outcome=WIN&grade=D → 200`, `{"n":2,"first3":["5 로킷헬스케어","1 우리금융지주"],"page":null}`, 칩 `성공 (86)`·`D (7)` 그대로 → 결과 「전체 (234)」 → `?page=1&limit=50&grade=D → 200`, `{"n":7,"first3":["15 현대지에프홀딩스","11 우리금융지주","7 삼영"],"last":"1 우리금융지주","page":null}`
- 결과: 통과
- 증거: `flow017-s3.png`(열어 확인: 두 칩 활성, # 칸 5·1, 결과 「성공」, 등급 D)
- 정리(cleanup): 조회 전용이라 이 시나리오가 소유한 자료 없음

### S-4. 두 필터를 모두 풀면 전체 목록으로 돌아간다 (인접, `[FLOW-016]` 회귀)
- 조작: 등급 「전체 (234)」를 누른다.
- 기대: 요청에 `outcome`·`grade` 가 없다. 첫 행 `234 삼성전기`, `Page 1 of 5`.
- 필수 여부(required): 예
- 실제: `?page=1&limit=50 → 200`, `{"n":50,"first3":["234 삼성전기","233 디아이","232 SFA반도체"],"last":"185 삼성전자우","page":"Page 1 of 5"}`
- 결과: 통과
- 증거: `flow017-s4.png`
- 정리(cleanup): 조회 전용이라 이 시나리오가 소유한 자료 없음

### S-5. 잘못된 필터 값은 400 이다 (인접, CLI)
- 조작: 격리 Flask 에 `curl` 로 `?outcome=All`, `?grade=C`, `?grade=S` 를 보낸다.
- 기대: 400, 400, 200. 화면이 보내지 않는 값이므로 브라우저 대상이 아니다.
- 필수 여부(required): 예
- 실제: `outcome=All 400`, `grade=C 400`, `grade=S 200`
- 결과: 통과
- 증거: 위 출력 원문
- 정리(cleanup): 조회 전용이라 이 시나리오가 소유한 자료 없음

### S-6. 콘솔 오류와 컴파일 문제가 없다 (인접)
- 조작: `console --clear` 뒤 S-1~S-4 를 마치고 `console --errors` 를 읽는다. `/_next/mcp` 에 `get_errors` 와
  `get_compilation_issues` 를 보낸다. 필터 클릭 뒤의 로딩 표시(리뷰 L2)를 관찰해 기록한다.
- 기대: 콘솔 오류 0, `/_next/mcp` 응답의 오류·컴파일 문제 목록이 비어 있다. L2 는 관찰만 기록한다.
- 필수 여부(required): 예
- 실제: `console --errors` → `(no console errors)`. `/_next/mcp` `get_errors` → `{"configErrors":[],"sessionErrors":[]}`, `get_compilation_issues` → `{"issues":[]}`. L2 관찰: 필터 요청은 28~44ms 에 끝나 전체 화면 로딩 표시는 순간적으로만 나타난다. 다만 로딩 중에는 페이지 전체가 스피너로 바뀌므로 응답이 느린 환경에서는 필터를 누를 때마다 화면이 비었다 돌아온다. 종전 페이지 이동과 같은 패턴이며 `[FLOW-021]` 로 이월
- 결과: 통과
- 증거: 위 출력 원문
- 정리(cleanup): 조회 전용이라 이 시나리오가 소유한 자료 없음

## 이월한 발견

- `[FLOW-021]`(P2): 필터·페이지 이동 때 전체 화면 로딩 표시가 표와 필터를 통째로 대체하고, 필터 결과가 0건일 때 빈 목록 문구가 「해당 기간에 대한 거래 내역이 없습니다」라 필터 탓임을 알리지 않는다(리뷰 L2·빈 결과 문구 관찰).
- 두 필터를 함께 켰을 때 칩 건수가 표 total 과 다른 것은 승인된 설계(리뷰 L1)이므로 이월하지 않는다. 등급 집합 밖 거래가 `counts.total` 에만 잡히는 것(리뷰 L4)은 `[FLOW-019]` 에 연결했다.
