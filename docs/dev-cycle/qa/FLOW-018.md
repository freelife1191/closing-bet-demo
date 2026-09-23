# [FLOW-018] 누적성과가 추천 단위로 센다는 것을 화면에 적는다 — QA 시나리오

- 대상 화면: http://localhost:3750/dashboard/kr/cumulative (격리 Next). 백엔드는 격리 gunicorn http://127.0.0.1:5750
- 구성 근거: TODO 의 QA 시나리오 줄(누적 추천수·승률·손익비 툴팁과 가이드 모달 승률 카드에 재추천 집계 문구가 보이고 KPI 값은
  수정 전과 같다) + 이번 변경(`TOOLTIP_CONTENT` 의 `totalSignals.criteria`·`winRate.desc`·`profitFactor.desc`, 가이드 모달 한 줄).
  `renderStatTooltip` 은 승률에서 `desc`·코멘트·`criteria` 를, 손익비에서 `desc`·코멘트만, 누적 추천수에서 `desc`·`interpretation`·
  `criteria` 를 그리므로 문구는 그 필드에 넣었다
- 구성 2026-09-23 12:38 | 실행 2026-09-23 12:38~12:40 (1회차)
- 검증 기준 커밋: `7263a18` (첫 커밋, `code/` 는 `git archive 7263a184`). 백엔드 코드는 바뀌지 않았으므로 KPI 값의 기준은 같은 격리 백엔드의 API 응답이다
- QA 엔진(engine): Claude Code, 브라우저는 gstack `browse`. 원본 3500/5501·live 주소·원본 `.env`·원본 `data/` 는 쓰지 않는다.
  `browser-notes.md` 「공통」 절에 따라 원본 PYTHONPATH 의 앱을 scratch cwd 로 띄우지 않는다
  - 코드 사본 `code/`(`git archive <첫 커밋>`). `.env`·`secrets/` 없음
  - 실행 디렉터리 `run/`: 원본 `data/` 의 JSON·CSV 를 읽기 전용으로 복사
  - gunicorn: `code/` 를 `--pythonpath`, cwd `run/`, `SCHEDULER_ENABLED=false`, 더미 `INTERNAL_IDENTITY_SECRET`, 1 worker,
    `127.0.0.1:5750`. Next: 첫 커밋의 `frontend/` 사본(`node_modules` 는 `cp -cR`), `PORT=3750 API_URL=http://127.0.0.1:5750`,
    더미 비밀, `npm run dev -- -p 3750`
- 금지 조작: 설정 저장, Refresh VCP, 실패 AI 재분석, GEMINI 재분석, Refresh Market Gate, 챗봇 전송, 모의 매수, 삭제 계열. 화면은 GET 조회와
  툴팁 호버·가이드 모달 열기만 한다
- 단계(phase): 시나리오 구성 완료 | 실행 완료
- 반복(iteration): 1회
- 결과: 통과 (필수 3/3)
- 증거: 각 시나리오의 「실제」 줄(browse `hover`·`js`·`console --errors`, `/_next/mcp get_errors`, gunicorn access 로그) · 스크린샷 scratchpad
  `flow018-tooltip-winrate.png`(승률 툴팁, 열어 확인)·`flow018-guide.png`(가이드 모달, 열어 확인) · access 로그 사본 scratchpad `flow018-access.log`
- 정리(cleanup): browse 서버 정지, 격리 gunicorn 마스터 TERM, 격리 Next 세션 그룹 TERM. 3750/5750 과 원본 3500/5501 리스너 0, 사본 경로 프로세스 0,
  사본 `qa-flow018/` 삭제. 루트 `node_modules/.vite` 없음, 작업 트리 변화 없음. 사본 구성 시각(12:38:13) 이후 원본 `data/`·`logs/` 에서 수정 시각이
  바뀐 파일 0개. 정적 검증의 전체 pytest 는 저장소 사본에서 돌렸다(`[INFRA-083]`). 첫 Next 기동은 macOS 에 `setsid` 가 없어 실패했고
  python `os.setsid()` 로 다시 띄웠다
- 필수 여부(required): 예
- browser_applicability: required. 사용자가 누적성과 화면에서 KPI 카드에 마우스를 올려 집계 정의를 읽는 흐름이다. browser_driver: gstack `browse`
- 읽은 정본: `.claude/skills/closing-bet-nextjs/SKILL.md`, `.claude/skills/closing-bet-python/SKILL.md`,
  `.claude/skills/closing-bet-verify/SKILL.md`, `.claude/skills/dev-cycle/references/browser-notes.md`,
  `frontend/node_modules/next/dist/docs/01-app/01-getting-started/05-server-and-client-components.md`(순수 클라이언트 문구 변경이라
  `frontend-skills.md` §2 표의 여섯 줄에 맞지 않음)

## 시나리오

### S-1. KPI 카드 툴팁 세 개에 재추천 집계 문구가 보인다 (핵심)
- 조작: 누적 추천수·승률·손익비 카드에 차례로 마우스를 올리고 툴팁 본문을 읽는다.
- 기대: 누적 추천수 툴팁의 기준 줄에 「보유 중 같은 종목이 다시 추천되어도 각각 한 건」, 승률·손익비 툴팁의 설명에 「추천 단위로 세므로 …
  같은 가격 움직임이 겹쳐 반영될 수 있습니다」가 보인다.
- 필수 여부(required): 예
- 실제: 누적 추천수 툴팁 「기준: 전체 기간 동안 발생한 모든 매수 신호 포함; 보유 중 같은 종목이 다시 추천되어도 각각 한 건」. 승률 툴팁 「설명: … 비율입니다.
  추천 단위로 세므로, 앞선 추천이 청산되기 전 같은 종목이 다시 추천되면 각각 한 건이 되어 같은 가격 움직임이 겹쳐 반영될 수 있습니다.」. 손익비 툴팁 설명에
  같은 문장. 스크린샷에서 승률 툴팁이 카드 위에 펼쳐져 문장이 보인다
- 결과: 통과

### S-2. 가이드 모달 승률 카드에 문구가 보인다
- 조작: 「누적 성과 지표 가이드」 모달을 열어 승률 카드를 읽는다.
- 기대: 계산식 아래에 「추천 단위로 셉니다. 앞선 추천이 청산되기 전 같은 종목이 다시 추천되면 각각 한 건입니다.」가 보인다.
- 필수 여부(required): 예
- 실제: 「성과 가이드」 단추로 모달을 열었다(모달만 여는 조작). 승률 카드 본문 「… 계산식: (익절 횟수 / (익절 + 손절 횟수)) * 100 추천 단위로 셉니다.
  앞선 추천이 청산되기 전 같은 종목이 다시 추천되면 각각 한 건입니다.」. 스크린샷에서 계산식 아래 줄로 보인다
- 결과: 통과

### S-3. KPI 값 불변과 화면 회귀 없음
- 조작: 같은 격리 백엔드의 `GET /api/kr/closing-bet/cumulative` 응답 `kpi` 와 카드에 그려진 누적 추천수·승률·손익비를 대조하고, 콘솔 오류·
  `/_next/mcp get_errors`·gunicorn access 로그의 5xx 를 확인한다.
- 기대: 카드 값이 API 의 `totalSignals`·`winRate`·`profitFactor` 와 같고 5xx·콘솔 오류·프레임워크 오류 0. 무관한 오류는 원인과 함께 따로 적는다.
- 필수 여부(required): 예
- 실제: API `kpi` 는 totalSignals 234·winRate 38.1·profitFactor 1.02(wins 86, losses 140). 카드는 누적 추천수 234·승률 38.1%·손익비 1.02 로 같다.
  `console --errors` 「no console errors」, `/_next/mcp get_errors` `configErrors:[]`·`sessionErrors:[]`, access 로그 4건 모두 200
  (`GET /api/kr/closing-bet/cumulative` 3, `GET /api/kr/user/quota` 1). POST 0건
- 결과: 통과
