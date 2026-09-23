# [FLOW-021] 누적성과 필터·페이지 전환 중 화면 전체가 로딩 표시로 바뀐다 — QA 시나리오

- 대상 화면: http://localhost:3752/dashboard/kr/cumulative (격리 Next). 백엔드는 격리 gunicorn http://127.0.0.1:5752
- 구성 근거: TODO 의 QA 줄(필터 응답 대기 중 필터 버튼과 KPI 카드 유지, `D` + `보유` 0건 조합의 필터 문구) + 이번 변경(`loading && pagination === null`
  에서만 전체 스피너, 표 영역 `aria-busy`·`opacity-50`, `TradeTable` 의 `filtered` 문구)
- 구성 2026-09-23 | 실행 (미실행)
- 검증 기준 커밋: 첫 커밋(`code/` 는 `git archive <첫 커밋>`)
- QA 엔진(engine): Claude Code, 브라우저는 gstack `browse`. 원본 3500/5501·live 주소·원본 `.env`·원본 `data/` 는 쓰지 않는다.
  `browser-notes.md` 「공통」 절에 따라 원본 PYTHONPATH 의 앱을 scratch cwd 로 띄우지 않는다
  - 코드 사본 `code/`(`git archive <첫 커밋>`). `.env`·`secrets/` 없음
  - 실행 디렉터리 `run/`: 원본 `data/` 의 JSON·CSV 를 읽기 전용으로 복사
  - gunicorn: `code/` 를 `--pythonpath`, cwd `run/`, `SCHEDULER_ENABLED=false`, 더미 `INTERNAL_IDENTITY_SECRET`, 1 worker,
    `127.0.0.1:5752`. Next: 첫 커밋의 `frontend/` 사본(`node_modules` 는 `cp -cR`), `API_URL=http://127.0.0.1:5752`, 더미 비밀,
    `npm run dev -- -p 3752`
- 금지 조작: 설정 저장, Refresh VCP, 실패 AI 재분석, GEMINI 재분석, Refresh Market Gate, 챗봇 전송, 모의 매수, 삭제 계열. 화면은 GET 조회와
  필터·페이지 이동만 한다
- 단계(phase): 시나리오 구성 완료 | 실행 대기
- 반복(iteration): 0회
- 결과: (미실행)
- 필수 여부(required): 예
- browser_applicability: required. 사용자가 누적성과 표에서 필터를 눌러 목록을 좁히는 흐름이다. browser_driver: gstack `browse`
- 읽은 정본: `.claude/skills/closing-bet-nextjs/SKILL.md`, `.claude/skills/dev-cycle/references/frontend-skills.md` §2,
  `frontend/node_modules/next/dist/docs/01-app/01-getting-started/05-server-and-client-components.md`(순수 클라이언트 상태 변경),
  `.claude/skills/closing-bet-verify/SKILL.md`

## 시나리오

### S-1. 재조회 중 필터·KPI 가 남는다 (핵심)
- 조작: 첫 로딩 뒤 `fetch` 를 감싸 `/api/kr/closing-bet/cumulative` 응답을 1.5초 늦춘 상태에서 결과 필터 「성공」을 누르고, 대기 중 화면을 읽는다.
- 기대: 대기 중 「데이터 불러오는 중...」이 없고 필터 버튼·KPI 카드가 남아 있으며 표 영역이 `aria-busy="true"` 이다. 응답 뒤 `aria-busy="false"` 이고 행이 API 의 성공 건과 같다.
- 필수 여부(required): 예
- 실제:
- 결과:

### S-2. 필터 0건 문구
- 조작: 등급 `D` + 결과 `보유` 조합을 누른다(격리 API 로 0건인지 먼저 확인하고, 0건이 아니면 0건인 다른 조합을 고른다).
- 기대: 「선택한 필터에 해당하는 거래가 없습니다.」가 보인다. 필터를 모두 「전체」로 돌리면 행이 다시 보인다.
- 필수 여부(required): 예
- 실제:
- 결과:

### S-3. 화면 회귀 없음
- 조작: 페이지 이동(「Next」)을 한 번 하고, 콘솔 오류·`/_next/mcp get_errors`·gunicorn access 로그의 5xx 를 확인한다.
- 기대: 페이지 이동 중에도 전체 스피너가 없고, 5xx·콘솔 오류·프레임워크 오류 0. 무관한 오류는 원인과 함께 따로 적는다.
- 필수 여부(required): 예
- 실제:
- 결과:
