# [JONGGA-041] 종가베팅 카드에 실제 시세로 그린 작은 차트를 되살린다 — QA 시나리오

- 대상: `frontend/src/app/dashboard/kr/closing-bet/MiniPriceChart.tsx`(신규)와 `page.tsx` 의 SignalCard. 종가베팅
  화면(`/dashboard/kr/closing-bet`)의 카드마다 있는 차트 상자
- 구성 근거: `[JONGGA-041]` 의 QA 시나리오 줄 + 코드 리뷰(feature-dev:code-reviewer, APPROVE)의 참고 사항(이 화면에서
  `/api/kr/stock-chart` 의 첫 호출자라는 점, 카드 수만큼 동시 요청)
- 구성 2026-09-22 18:33 | 실행 2026-09-22 18:31~18:35 (1회차)
- 검증 기준 커밋: `1029f2e` (첫 커밋). 실행은 그 커밋 직전 작업 트리에서 했고, 커밋까지 바뀐 것은
  `MiniPriceChart.tsx` 의 주석 두 줄(리뷰 참고 사항 반영)뿐이다
- QA 엔진(engine): Claude Code. 사용자 진입 흐름이 화면이므로 브라우저 실측을 필수로 두었다. 격리 사본(scratchpad 에
  rsync 한 작업 트리 + `node_modules` APFS clone, `.env` 계열·`data/`·`logs/`·`secrets/` 제외)에서
  `PORT=57821 API_URL=http://127.0.0.1:57822 npm run dev` 로 Next 를 띄우고, 합성 Flask fixture(scratchpad
  `jongga041_fixture.py`, 57822)가 로컬 `data/jongga_v2_latest.json` 을 읽기 전용으로 한 번 읽어 앞 4건을 돌려준다.
  fixture 의 `/api/kr/stock-chart/<code>` 는 시그널 순서대로 상승 20봉·하락 20봉·빈 응답·HTTP 500 을 돌려준다.
  브라우저는 gstack `browse`(HeadlessChrome 151). 원본 3500·5501 과 운영 주소에는 접속하지 않았다
- 단계(phase): 시나리오 구성 완료 | 실행 완료
- 반복(iteration): 1회
- baseline 상태: 원본 `data/` 는 fixture 가 읽기만 했고 파일 변경 없음. 격리 Next 의 `/_next/mcp`
  `get_compilation_issues` 가 `issues: []`
- 필수 여부(required): 예
- 결과: 통과 (필수 3/3, 인접 1/1)
- 증거: 아래 각 시나리오의 「실제」 줄(browse `js` 출력 원문과 fixture 요청 기록) · 스크린샷 scratchpad
  `jongga041-s1-desktop.png`(1280×900 전체 화면), `jongga041-s2-modal.png`, `jongga041-s4-mobile.png`(390×844) ·
  `npx vitest run` 전체 exit 0 · `npm run type-check` exit 0 · `pytest -q -p no:cacheprovider` 2582 통과 2 skipped
- 정리(cleanup): 격리 Next(57821)·fixture(57822) 프로세스 종료, agent-browser 세션 닫음, 격리 사본은 scratchpad 에
  두고 저장소에는 아무것도 남기지 않음. `git status --short` 에 이번 항목의 파일만 있음

## 검사 대상에 관한 전제

`[JONGGA-024]`(커밋 `d1163eb`)는 상승·하락 두 모양뿐인 가짜 polyline 을 지우고 「실제 차트 크게 보기」 버튼만 남겼다.
이번 변경은 그 자리를 VCP 화면의 확대 차트가 쓰는 `GET /api/kr/stock-chart/<code>?period=1m&end=<signal_date>` 로
받은 종가의 SVG 선 차트로 채운다. 상자 전체가 종전과 같은 「{종목} 차트 크게 보기」 버튼이라 확대 모달 진입은 그대로이고,
응답이 비거나 실패하면 종전 버튼 문구로 돌아간다. 이 화면의 확대 모달은 네이버 금융 이미지를 쓰므로 이 API 의
첫 호출자는 이 카드다. 백엔드 `load_csv_file` 은 파일 시그니처로 캐시하므로 카드 수만큼의 동시 요청이 CSV 를 매번
다시 읽지는 않는다.

실측 요령 기록: 격리 Next 를 `http://127.0.0.1:57821` 로 열면 문서는 200 이지만 Next 16 개발 서버의 origin 검사에 걸려
클라이언트가 수화되지 않아 카드가 영영 그려지지 않는다(콘솔 오류 없음, HMR 웹소켓만 실패). `http://localhost:57821`
로 열어야 한다. `browser-notes.md` 의 「과거 `127.0.0.1` origin 차단 사례」가 이 기기에서도 재현됐다.

## 시나리오

### S-1. 카드마다 신호일까지 한 달 종가로 선 차트를 그린다 (회귀)
- 조작: 격리 화면을 `localhost:57821/dashboard/kr/closing-bet` 로 열고 카드 4장의 차트 상자를 읽는다.
- 기대: 상승 종목(삼성전기)은 rose(`#fb7185`) 선, 하락 종목(디아이)은 blue(`#60a5fa`) 선이며 점이 20개다. 상자 높이 96px,
  「최근 1개월 종가」 표기. 차트 요청 4건이 모두 `period=1m&end=2026-09-21`(시그널의 `signal_date`)이다.
- 필수 여부(required): 예
- 실제: DOM 읽기 `삼성전기: polyline true, stroke #fb7185, pts 20, h 96` · `디아이: polyline true, stroke #60a5fa, pts 20`
  · 두 상자의 텍스트 「최근 1개월 종가크게 보기」(hover 힌트 포함). 브라우저 네트워크 기록
  `GET /api/kr/stock-chart/009150?period=1m&end=2026-09-21 → 200`, `003160 → 200`, `036540 → 200`, `232140 → 500`.
  스크린샷 `jongga041-s1-desktop.png` 에서 첫 카드는 오른쪽 위로 오르는 붉은 선, 둘째 카드는 내려가는 파란 선.
- 결과: 통과
- 증거: browse `js` 출력 원문, `browse network`, 스크린샷
- 정리(cleanup): 없음

### S-2. 차트 상자를 누르면 그 종목의 확대 차트가 열린다 (회귀)
- 조작: `snapshot -i` 로 「삼성전기 차트 크게 보기」 버튼 참조를 뽑아 누른 뒤 dialog 를 읽고, Escape 로 닫는다.
- 기대: dialog 제목 「삼성전기」, 본문에 `009150`, 이미지 alt 「삼성전기 009150 일봉 차트」, src 는 네이버 candle/day
  `009150.png`. Escape 뒤 dialog 없음.
- 필수 여부(required): 예
- 실제: `{dialog: true, title: "삼성전기", code: "009150", imgAlt: "삼성전기 009150 일봉 차트",
  imgSrc: "https://ssl.pstatic.net/imgfinance/chart/item/candle/day/009150.png"}` → Escape → `{dialogAfterEscape: false}`.
  스크린샷 `jongga041-s2-modal.png` 에 모달과 일봉 차트.
- 결과: 통과
- 증거: browse `js` 출력 원문, 스크린샷
- 정리(cleanup): Escape 로 닫음

### S-3. 응답이 비거나 실패한 종목은 종전 버튼 문구로 돌아간다 (회귀)
- 조작: S-1 과 같은 화면에서 셋째(빈 응답)·넷째(HTTP 500) 카드의 상자를 읽는다.
- 기대: polyline 없음, 텍스트 「실제 차트 크게 보기」, 버튼 이름 「{종목} 차트 크게 보기」 유지, 높이 96px 로 같은 자리.
- 필수 여부(required): 예
- 실제: `SFA반도체: polyline false, text "실제 차트 크게 보기", h 96` · `와이씨: polyline false, text "실제 차트 크게 보기",
  h 96`. 콘솔 오류는 그 500 응답의 「Failed to load resource」 뿐이고 페이지 오류 없음.
- 결과: 통과
- 증거: browse `js` 출력 원문, `browse console --errors`
- 정리(cleanup): 없음

### S-4. 모바일 폭에서 상자가 카드 밖으로 넘치지 않는다 (인접)
- 조작: `viewport 390x844` 로 바꾸고 다시 읽는다.
- 기대: `document.documentElement.scrollWidth` 가 `innerWidth`(390) 와 같고, 상자 4개의 오른쪽 끝이 390 안에 있다.
- 필수 여부(required): 아니오 (인접)
- 실제: `{innerWidth: 390, scrollWidth: 390, overflow: false}`, 상자 4개 모두 `w 316, h 96, right 353`.
  스크린샷 `jongga041-s4-mobile.png`.
- 결과: 통과
- 증거: browse `js` 출력 원문, 스크린샷
- 정리(cleanup): 없음

## 프레임워크 관점

- `/_next/mcp` `get_compilation_issues` → `{"issues": []}` · `get_errors` → `{"configErrors": [], "sessionErrors": []}`
  (브라우저 세션이 연결된 상태에서 호출)
- 콘솔 오류: 의도한 fixture 500(232140) 과 fixture 가 만들지 않은 `/api/kr/user/quota` 404 뿐. 둘 다 이번 변경과 무관

## 이월한 발견

- 없음. 리뷰 참고 사항 두 가지 가운데 주석 정정은 반영했고, `data-testid="mini-chart"` 는 브라우저 실측이 그 선택자를
  쓰므로 남겼다.
