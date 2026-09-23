# [FLOW-020] 「최고가」 열이 값을 숨기지 않게 한다 — QA 시나리오

- 대상 화면: http://localhost:3751/dashboard/kr/cumulative (격리 Next). 백엔드는 격리 gunicorn http://127.0.0.1:5751
- 구성 근거: TODO 의 QA 줄(2026-09-01 삼성생명 행의 최고가 열에 `-1.5%`) + 이번 변경(`trade.days > 0` 이면
  `formatSignedPercent(trade.maxHigh)`, 아니면 `-`). 기대값은 같은 격리 백엔드의 `GET /api/kr/closing-bet/cumulative` 응답에서 읽는다
- 구성 2026-09-23 13:00 | 실행 2026-09-23 13:00~13:04 (1회차)
- 검증 기준 커밋: `4f47dd1` (첫 커밋, `code/` 는 `git archive 4f47dd13`). 백엔드 코드는 바뀌지 않았으므로 기대값의 기준은 같은 격리 백엔드의 API 응답이다
- QA 엔진(engine): Claude Code, 브라우저는 gstack `browse`. 원본 3500/5501·live 주소·원본 `.env`·원본 `data/` 는 쓰지 않는다.
  `browser-notes.md` 「공통」 절에 따라 원본 PYTHONPATH 의 앱을 scratch cwd 로 띄우지 않는다
  - 코드 사본 `code/`(`git archive <첫 커밋>`). `.env`·`secrets/` 없음
  - 실행 디렉터리 `run/`: 원본 `data/` 의 JSON·CSV 를 읽기 전용으로 복사
  - gunicorn: `code/` 를 `--pythonpath`, cwd `run/`, `SCHEDULER_ENABLED=false`, 더미 `INTERNAL_IDENTITY_SECRET`, 1 worker,
    `127.0.0.1:5751`. Next: 첫 커밋의 `frontend/` 사본(`node_modules` 는 `cp -cR`), `PORT=3751 API_URL=http://127.0.0.1:5751`,
    더미 비밀, `npm run dev -- -p 3751`
- 금지 조작: 설정 저장, Refresh VCP, 실패 AI 재분석, GEMINI 재분석, Refresh Market Gate, 챗봇 전송, 모의 매수, 삭제 계열. 화면은 GET 조회와
  페이지 이동만 한다
- 단계(phase): 시나리오 구성 완료 | 실행 완료
- 반복(iteration): 1회
- 결과: 통과 (필수 3/3)
- 증거: 각 시나리오의 「실제」 줄(browse `js`·`console --errors`, `/_next/mcp get_errors`, API 전 페이지 대조, gunicorn access 로그) · 스크린샷 scratchpad
  `flow020-row177.png`(2쪽, 177번 삼성생명 행 강조, 열어 확인) · access 로그 사본 scratchpad `flow020-access.log`
- 정리(cleanup): browse 서버 정지, 격리 gunicorn 마스터 TERM, 격리 Next 세션 그룹 TERM. 3751/5751 과 원본 3500/5501 리스너 0, 사본 경로 프로세스 0,
  사본 `qa-flow020/` 삭제. 루트 `node_modules/.vite` 없음, 작업 트리 변화 없음. 사본 구성 시각(12:59:22) 이후 원본 `data/`·`logs/` 에서 수정 시각이
  바뀐 파일 0개. 격리 백엔드는 `env -i` 에 cwd `run/`, `--pythonpath code/` 로 띄웠고 venv 의 `.pth` 에 원본 저장소를 가리키는 줄이 없음을 확인했다
- 필수 여부(required): 예
- browser_applicability: required. 사용자가 누적성과 표에서 종목별 최고 상승률을 읽는 흐름이다. browser_driver: gstack `browse`
- 읽은 정본: `.claude/skills/closing-bet-nextjs/SKILL.md`, `.claude/skills/dev-cycle/references/frontend-skills.md` §2,
  `frontend/node_modules/next/dist/docs/01-app/01-getting-started/05-server-and-client-components.md`(순수 클라이언트 표기 변경),
  `.claude/skills/dev-cycle/references/tier-rules.md` §1·§2·§3

## 시나리오

### S-1. 음수 최대 상승률이 부호와 함께 보인다 (핵심)
- 조작: 표에서 2026-09-01 삼성생명(032830) 행을 찾아 최고가 칸을 읽는다(필요하면 페이지를 넘긴다).
- 기대: API 의 그 거래 `maxHigh`(감사 실측 -1.5)와 `days > 0` 을 확인하고, 칸에 `-1.5%` 처럼 부호가 붙은 값이 보인다. 하이픈이 아니다.
- 필수 여부(required): 예
- 실제: 격리 API 2쪽 177번 삼성생명(032830) 2026-09-01 은 `entry` 307000·`maxHigh` -1.5·`days` 1·LOSS. 화면 2쪽 같은 행 최고가 칸 `-1.5%`(클래스 `text-gray-500`, 색상 규칙 불변). 스크린샷에서 강조한 행에 `-1.5%` 가 보인다
- 결과: 통과

### S-2. 양수는 `+` 가 붙고, 일봉이 없는 거래만 하이픈이다
- 조작: 같은 페이지의 모든 행에서 API 의 `maxHigh`·`days` 와 화면 최고가 칸을 대조한다.
- 기대: `days > 0` 인 행은 `formatSignedPercent(maxHigh)`(양수 `+x%`, 0 은 `0%`), `days == 0` 인 행만 `-`. 불일치 0건.
- 필수 여부(required): 예
- 실제: 「Next」로 5쪽을 넘기며 234행의 최고가 칸을 읽어 API 234건과 번호로 대조했다. 불일치 0건. 하이픈 8행은 모두 `days` 0(1쪽 227~234번, 보유일 `0일`), 음수 40행, `+` 186행. `days > 0` 이면서 `maxHigh` 가 정확히 0 인 거래는 실자료에 없어 `0%` 표기는 vitest 로만 확인된다
- 결과: 통과

### S-3. 화면 회귀 없음
- 조작: 콘솔 오류·`/_next/mcp get_errors`·gunicorn access 로그의 5xx 를 확인한다.
- 기대: 5xx·콘솔 오류·프레임워크 오류 0. 무관한 오류는 원인과 함께 따로 적는다.
- 필수 여부(required): 예
- 실제: `console --errors` 「no console errors」, `/_next/mcp get_errors` `configErrors:[]`·`sessionErrors:[]`, access 로그 26건 모두 200, POST 0건
- 결과: 통과
