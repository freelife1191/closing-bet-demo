# [FLOW-021] 누적성과 필터·페이지 전환 중 화면 전체가 로딩 표시로 바뀐다 — QA 시나리오

- 대상 화면: http://localhost:3752/dashboard/kr/cumulative (격리 Next). 백엔드는 격리 gunicorn http://127.0.0.1:5752
- 구성 근거: TODO 의 QA 줄(필터 응답 대기 중 필터 버튼과 KPI 카드 유지, `D` + `보유` 0건 조합의 필터 문구) + 이번 변경(`loading && pagination === null`
  에서만 전체 스피너, 표 영역 `aria-busy`·`opacity-50`, `TradeTable` 의 `filtered` 문구)
- 구성 2026-09-23 13:05 | 실행 2026-09-23 13:06~13:10 (1회차)
- 검증 기준 커밋: `bb95a95` (첫 커밋, `code/` 는 `git archive bb95a95e`). 백엔드 코드는 바뀌지 않았으므로 기대값의 기준은 같은 격리 백엔드의 API 응답이다
- QA 엔진(engine): Claude Code, 브라우저는 gstack `browse`. 원본 3500/5501·live 주소·원본 `.env`·원본 `data/` 는 쓰지 않는다.
  `browser-notes.md` 「공통」 절에 따라 원본 PYTHONPATH 의 앱을 scratch cwd 로 띄우지 않는다
  - 코드 사본 `code/`(`git archive <첫 커밋>`). `.env`·`secrets/` 없음
  - 실행 디렉터리 `run/`: 원본 `data/` 의 JSON·CSV 를 읽기 전용으로 복사
  - gunicorn: `code/` 를 `--pythonpath`, cwd `run/`, `SCHEDULER_ENABLED=false`, 더미 `INTERNAL_IDENTITY_SECRET`, 1 worker,
    `127.0.0.1:5752`. Next: 첫 커밋의 `frontend/` 사본(`node_modules` 는 `cp -cR`), `API_URL=http://127.0.0.1:5752`, 더미 비밀,
    `npm run dev -- -p 3752`
- 금지 조작: 설정 저장, Refresh VCP, 실패 AI 재분석, GEMINI 재분석, Refresh Market Gate, 챗봇 전송, 모의 매수, 삭제 계열. 화면은 GET 조회와
  필터·페이지 이동만 한다
- 단계(phase): 시나리오 구성 완료 | 실행 완료
- 반복(iteration): 1회
- 결과: 통과 (필수 3/3)
- 증거: 각 시나리오의 「실제」 줄(browse `js`·`console --errors`, `/_next/mcp get_errors`, API 대조, gunicorn access 로그) · 스크린샷 scratchpad
  `flow021-busy.png`(재조회 대기 중, KPI·필터가 남고 표만 흐림, 열어 확인)·`flow021-empty.png`(`보유`+`D` 0건 문구, 열어 확인) · access 로그 사본 scratchpad `flow021-access.log`
- 정리(cleanup): browse 서버 정지, 격리 gunicorn 마스터 TERM, 격리 Next 세션 그룹 TERM. 3752/5752 와 원본 3500/5501 리스너 0, 사본 경로 프로세스 0,
  사본 `qa-flow021/` 삭제. 루트 `node_modules/.vite` 없음, 작업 트리 변화 없음. 사본 구성 시각(13:06:07) 이후 원본 `data/`·`logs/` 에서 수정 시각이
  바뀐 파일 0개. 격리 백엔드는 `env -i` 에 cwd `run/`, `--pythonpath code/` 로 띄웠고 venv 의 `.pth` 에 원본 저장소를 가리키는 줄이 없음을 확인했다
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
- 실제: 첫 로딩 50행 뒤 브라우저의 `window.fetch` 를 감싸 누적성과 요청만 1.5초 늦추고 「성공」을 눌렀다. 0.4초 뒤(대기 중) 「데이터 불러오는 중」 없음, 표 영역 `aria-busy="true"`, 필터 버튼 7개와 「누적 추천수」 카드가 그대로, 이전 50행이 흐리게 남음. 응답 뒤 `aria-busy="false"`, 첫 다섯 행 번호 223·218·210·208·207 은 격리 API `outcome=WIN` 1쪽과 같고 결과 열 값은 한 종류. 스크린샷에서 KPI·필터가 남고 표만 흐리다
- 결과: 통과

### S-2. 필터 0건 문구
- 조작: 등급 `D` + 결과 `보유` 조합을 누른다(격리 API 로 0건인지 먼저 확인하고, 0건이 아니면 0건인 다른 조합을 고른다).
- 기대: 「선택한 필터에 해당하는 거래가 없습니다.」가 보인다. 필터를 모두 「전체」로 돌리면 행이 다시 보인다.
- 필수 여부(required): 예
- 실제: 격리 API `grade=D&outcome=OPEN` 은 `total` 0. 화면에서 「보유」와 「D」를 누르자 행 0개, 「선택한 필터에 해당하는 거래가 없습니다.」가 보이고 기존 문구 「해당 기간에 대한 거래 내역이 없습니다.」는 없음. 두 필터를 「전체」로 돌리자 50행이 돌아오고 필터 문구가 사라졌다. 스크린샷에서 `보유 (8)`·`D (7)` 가 선택된 채 표 안에 새 문구가 보인다
- 결과: 통과

### S-3. 화면 회귀 없음
- 조작: 페이지 이동(「Next」)을 한 번 하고, 콘솔 오류·`/_next/mcp get_errors`·gunicorn access 로그의 5xx 를 확인한다.
- 기대: 페이지 이동 중에도 전체 스피너가 없고, 5xx·콘솔 오류·프레임워크 오류 0. 무관한 오류는 원인과 함께 따로 적는다.
- 필수 여부(required): 예
- 실제: 같은 1.5초 지연 상태에서 「Next」를 누르자 0.4초 뒤 스피너 없음·`aria-busy="true"`, 응답 뒤 `Page 2 of 5`·첫 행 184(격리 API 2쪽 첫 행 184 와 같음). `console --errors` 「no console errors」, `/_next/mcp get_errors` `configErrors:[]`·`sessionErrors:[]`, access 로그 11건 모두 200, POST 0건
- 결과: 통과
