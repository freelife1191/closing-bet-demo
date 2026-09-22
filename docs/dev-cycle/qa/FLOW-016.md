# [FLOW-016] 누적성과 표의 순번을 전체 기준으로 매긴다 — QA 시나리오

- 대상 화면: http://localhost:3716/dashboard/kr/cumulative (격리 Next). 백엔드는 격리 gunicorn http://127.0.0.1:5716
- 구성 근거: `[FLOW-016]` 의 QA 줄 + 설계 승인(필터 중 원래 번호 유지) + 이번 변경 한 파일
  (`CumulativeClientPage.tsx`). 기대값은 격리 Flask 의 `GET /api/kr/closing-bet/cumulative` 응답에서
  `pagination` 과 행 순서를 읽어 `total - (page - 1) * limit - idx` 로 계산했다. 1단계 리포트 도구 대신
  이 응답과 TODO 의 QA 줄에서 시나리오를 만들었다(`[FE-045]` 와 같은 방식)
- 구성 2026-09-23 07:56 | 실행 2026-09-23 07:56~07:57 (1회차)
- 검증 기준 커밋: `8b0534f` (첫 커밋). 사본의 `CumulativeClientPage.tsx` 가 이 커밋의 파일과 바이트 단위로 같음을 `cmp` 로 확인했고 실행 중 범위 파일은 바뀌지 않았다
- QA 엔진(engine): Claude Code, 브라우저는 gstack `browse`. 원본 3500/5501·live 주소·원본 `.env` 는 쓰지 않는다.
  저장소 작업 트리를 scratchpad `qa-flow016/` 로 복사(`.env`·`.git`·`venv`·`logs` 제외, `frontend/node_modules` 는
  APFS clone)하고, 더미 값(`NEXTAUTH_SECRET=qa-nextauth-secret`, `INTERNAL_IDENTITY_SECRET=qa-identity-secret`,
  `ADMIN_EMAILS=qa-admin@example.com`, `SCHEDULER_ENABLED=false`)만 환경 변수로 준다. 이 화면은 조회 전용이며
  로그인이 필요 없다
- 단계(phase): 시나리오 구성 완료 | 실행 완료
- 반복(iteration): 1회
- baseline 상태: 고치기 전 동작은 vitest RED 2건으로 고정했다(2페이지 첫 행이 184 가 아니라 3, 필터 뒤 남은 행이
  183 이 아니라 1). 사본 `data/` 기준 전체 234건, 50개씩 5페이지
- 필수 여부(required): 예
- 결과: 통과 (필수 5/5)
- 증거: 아래 각 시나리오의 「실제」 줄(browse `js` 출력 원문) · 스크린샷 scratchpad `flow016-s1-p1.png`·`flow016-s1-p2.png`·`flow016-s2.png`·`flow016-s3.png`·`flow016-s4.png`(`s1-p2`·`s2` 를 열어 확인) · 격리 로그 `qa-flow016-flask.log`·`qa-flow016-next.log` · `/_next/mcp` 응답
- 정리(cleanup): browse 서버 정지, 격리 gunicorn(5716)·Next(3716) 종료 뒤 두 포트 리스너 0·사본 경로 프로세스 0, 사본 `qa-flow016/` 삭제. 스크린샷과 로그는 scratchpad 에만 있고 저장소에 없음. 저장소 루트 `node_modules/.vite` 없음. 원본 3500/5501 리스너 0(처음부터 떠 있지 않았고 건드리지 않음)
- browser_applicability: required. 사용자가 표의 # 칸을 읽고 페이지를 넘기는 흐름이다. browser_driver: gstack `browse`
- 읽은 정본: `.claude/skills/closing-bet-nextjs/SKILL.md`, `.claude/skills/closing-bet-verify/SKILL.md`,
  `frontend-skills.md` §2, Next 번들 문서 `05-server-and-client-components.md`

## 시나리오

### S-1. 1페이지와 2페이지의 순번이 이어진다 (회귀)
- 조작: 화면을 열어 표의 첫 행과 마지막 행의 # 과 종목명을 읽는다. 표 아래 다음 페이지 버튼을 눌러 같은 값을 읽는다.
- 기대: 1페이지 첫 행 `234 삼성전기`, 마지막 행 `185`. 2페이지 첫 행 `184 에스피지`, 마지막 행 `135 효성중공업`.
  하단 표기 `Page 2 of 5`.
- 필수 여부(required): 예
- 실제: `{"n":50,"first3":["234 삼성전기","233 디아이","232 SFA반도체"],"last":"185 삼성전자우","page":"Page 1 of 5"}` → Next → `{"n":50,"first3":["184 에스피지","183 한화생명","182 LG에너지솔루션"],"last":"135 효성중공업","page":"Page 2 of 5"}`
- 결과: 통과
- 증거: `flow016-s1-p1.png`, `flow016-s1-p2.png`
- 정리(cleanup): 조회 전용이라 이 시나리오가 소유한 자료 없음

### S-2. 결과 필터가 켜져도 남은 행이 원래 번호를 유지한다 (회귀)
- 조작: 2페이지에서 결과 필터 「성공」을 누르고 표의 # 과 종목명을 읽는다.
- 기대: 16행이 남고 첫 세 행이 `179 메리츠금융지주`, `176 삼성증권`, `174 한온시스템`. 번호가 1부터 다시 매겨지지
  않는다. 필터 클릭으로 `/api/kr/closing-bet/cumulative` 요청이 새로 나가지 않는다.
- 필수 여부(required): 예
- 실제: 「성공 (16)」 클릭 → `{"n":16,"first3":["179 메리츠금융지주","176 삼성증권","174 한온시스템"],"last":"151 현대차","page":"Page 2 of 5"}`. 클릭 직전 `network --clear` 뒤 `closing-bet/cumulative` 요청 0건. 같은 기록이 뒤이은 페이지 이동의 `page=3`·`4`·`5` 요청 200 을 잡았으므로 기록 자체는 동작했다
- 결과: 통과
- 증거: `flow016-s2.png`(열어 확인: # 칸 179·176·174… 151, `Page 2 of 5`)
- 정리(cleanup): 조회 전용이라 이 시나리오가 소유한 자료 없음

### S-3. 마지막 페이지는 1번으로 끝난다 (인접)
- 조작: 필터를 「전체」로 되돌리고 5페이지까지 이동해 첫 행과 마지막 행을 읽는다.
- 기대: 34행, 첫 행 `34 삼성전기`, 마지막 행 `1 우리금융지주`.
- 필수 여부(required): 예
- 실제: 「전체」로 되돌린 뒤 Next 3회 → `{"n":34,"first3":["34 삼성전기","33 한화오션","32 삼성전자"],"last":"1 우리금융지주","page":"Page 5 of 5"}`. 요청 `GET /api/kr/closing-bet/cumulative?page=5&limit=50 → 200`
- 결과: 통과
- 증거: `flow016-s3.png`
- 정리(cleanup): 조회 전용이라 이 시나리오가 소유한 자료 없음

### S-4. 페이지당 건수를 바꾸면 그 크기로 다시 매긴다 (인접)
- 조작: 「페이지당」을 100개로 바꾼다(1페이지로 돌아간다). 첫 행을 읽고 다음 페이지로 이동해 첫 행과 마지막 행을 읽는다.
- 기대: 1페이지 첫 행 `234`. 2페이지 첫 행 `134 두산`, 마지막 행 `35 에코프로`, 표기 `Page 2 of 3`.
- 필수 여부(required): 예
- 실제: 「페이지당」 100 → `{"n":100,"first3":["234 삼성전기",…],"last":"135 효성중공업","page":"Page 1 of 3"}` → Next → `{"n":100,"first3":["134 두산","133 삼성물산","132 현대차2우B"],"last":"35 에코프로","page":"Page 2 of 3"}`
- 결과: 통과
- 증거: `flow016-s4.png`
- 정리(cleanup): 조회 전용이라 이 시나리오가 소유한 자료 없음

### S-5. 콘솔 오류와 컴파일 문제가 없다 (인접)
- 조작: `console --clear` 뒤 화면을 다시 열고 S-1~S-4 를 마친 뒤 `console --errors` 를 읽는다. 격리 Next 의
  `/_next/mcp` 에 `get_errors` 와 `get_compilation_issues` 를 보낸다.
- 기대: 콘솔 오류 0, `/_next/mcp` 응답의 오류·컴파일 문제 목록이 비어 있다.
- 필수 여부(required): 예
- 실제: `console --clear` 뒤 다시 연 화면에서 S-1~S-4 를 마친 뒤 `console --errors` → `(no console errors)`. `/_next/mcp` `get_errors` → `{"configErrors":[],"sessionErrors":[]}`, `get_compilation_issues` → `{"issues":[]}`
- 결과: 통과
- 증거: 위 출력 원문
- 정리(cleanup): 조회 전용이라 이 시나리오가 소유한 자료 없음

## 이월한 발견

없음. 필터가 현재 페이지 안에서만 걸리는 것은 `[FLOW-017]` 이 이미 다룬다.
