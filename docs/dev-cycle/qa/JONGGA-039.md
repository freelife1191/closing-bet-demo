# [JONGGA-039] 저장분이 비어 있으면 「최신」 이 과거 리포트로 내려가지 않고, 배너가 표시 중인 사실을 감춘다 — QA 시나리오

- 대상: `services/kr_market_jongga_payload_latest.py` `build_jongga_latest_payload` 의 stale 갈래와
  `frontend/src/app/dashboard/kr/closing-bet/page.tsx` 의 「최신」 배너. 종가베팅 화면(`/dashboard/kr/closing-bet`)의 「최신」 탭
- 구성 근거: `[JONGGA-039]` 의 근거·범위 줄 + 설계 승인(「최근 유효 리포트로 대체」) + 등록 때의 로컬 재현(정상 stale 갈래는
  `[JONGGA-009]` 대로 시그널 8건을 표식과 함께 내려주고, 문제는 저장분이 빈 경우와 배너 문구 둘)
- 구성 2026-09-22 19:55 | 실행 2026-09-22 19:56~19:59 (1회차)
- 검증 기준 커밋: `4b8ee17` (첫 커밋). 실행은 그 커밋과 같은 작업 트리에서 했다
- QA 엔진(engine): Claude Code. 사용자 진입 흐름이 화면이므로 브라우저 실측을 필수로 두었다. `[VCP-032]` 의 격리 사본(scratchpad
  `jongga041-scratch`, 이번 변경을 rsync 로 다시 복사, `.env` 없음)에서 실제 Flask(gunicorn 1 worker, `SCHEDULER_ENABLED=false`,
  57831)와 Next(`API_URL` → 57831, 57821)를 띄웠다. 사본 `data/jongga_v2_latest.json`(2026-09-21, 8건)을 백업한 뒤 시그널을
  비워 「전날 실행이 0건」 상황을 만들고, 사본의 `jongga_v2_results_20260921.json`(8건)이 대체 후보가 되게 두었다. 원본 `data/`
  는 읽지도 쓰지도 않았다. 원본 3500·5501·운영 주소 접속 없음. 브라우저는 gstack `browse`(HeadlessChrome), `localhost` 로 열었다
- 단계(phase): 시나리오 구성 완료 | 실행 완료
- 반복(iteration): 1회
- baseline 상태: 고치기 전 같은 자료는 배너 제목 「오늘 종가베팅 데이터가 아직 없습니다.」 아래 stale_warning 이 보이고 목록은
  「분석된 종목이 없습니다」 였다(pytest RED: 종전 코드에서 `signals == []`, vitest RED: 새 제목 없음). 사본
  `jongga_v2_latest.json` 원본은 `.qa-backup` 으로 보존했다가 정리 때 되돌렸다
- 필수 여부(required): 예
- 결과: 통과 (필수 2/2, 인접 2/2)
- 증거: 아래 각 시나리오의 「실제」 줄(browse `js` 출력·curl 출력 원문) · 스크린샷 scratchpad `jongga039-s1-latest.png`(전체
  페이지, 배너와 카드 8장) · pytest 파일 9 통과 · closing-bet vitest 15파일 95 통과 · `npm run type-check` exit 0
- 정리(cleanup): 사본 `jongga_v2_latest.json` 을 백업에서 복원(2026-09-21, 8건), 격리 gunicorn(57831)·Next(57821) 종료, browse
  서버 정지. 저장소에는 이번 항목의 파일만 남음

## 검사 대상에 관한 전제

stale 갈래(오늘이 개장일인데 저장분 기준일이 과거)에서 저장분의 시그널이 비어 있으면, 종전에는 빈 목록에 stale 표식만 붙였다.
이제 일자 파일 가운데 시그널이 있는 가장 최근 리포트로 내려가고, 그 리포트의 날짜로 stale 표식을 다시 만들어 나중에 덮는다.
그래서 `message` 는 helper 의 「주말/휴일로 인해 …」 가 아니라 「오늘 분석이 아직 없어서 가장 최근 저장분을 그대로 보여주고
있습니다 …」 다. 유효한 일자 파일이 하나도 없을 때만 종전처럼 빈 응답을 낸다. 오늘 자 파일이 0건인 경우와 비개장일은 종전
그대로다. 배너는 시그널이 있으면 제목 「오늘 분석은 아직 없습니다. 최신 저장분(날짜)을 표시합니다.」 와 `message` 줄을, 없으면
종전 제목과 `stale_warning` 을 보인다.

## 시나리오

### S-1. 저장분이 비어 있어도 「최신」 이 최근 리포트를 표식과 함께 보인다 (회귀)
- 조작: 사본의 `jongga_v2_latest.json` 시그널을 비운 상태로 `localhost:57821/dashboard/kr/closing-bet` 을 연다.
- 기대: 배너 제목 「오늘 분석은 아직 없습니다. 최신 저장분(2026-09-21)을 표시합니다.」, 둘째 줄 「오늘 분석이 아직 없어서 가장
  최근 저장분을 그대로 보여주고 있습니다. …」, 카드 8장(첫 카드 삼성전기), 「분석된 종목이 없습니다」 없음, 종전 제목
  「오늘 종가베팅 데이터가 아직 없습니다.」 없음, 콘솔 오류 0건.
- 필수 여부(required): 예
- 실제: `bannerFound: true` · 배너 줄 `"오늘 분석은 아직 없습니다. 최신 저장분(2026-09-21)을 표시합니다."`, `"오늘 분석이 아직
  없어서 가장 최근 저장분을 그대로 보여주고 있습니다. [업데이트] 버튼을 눌러 오늘 분석을 실행해주세요."` · 카드 제목 삼성전기,
  디아이, SFA반도체, 와이씨, 삼현, 하나마이크론 …(`miniCharts: 8`) · `noDataText: false` · `oldTitle: false` · `newTitle: true`
  · `browse console --errors` → 「(no console errors)」. 스크린샷 `jongga039-s1-latest.png`.
- 결과: 통과
- 증거: browse `js`·`console --errors` 출력 원문, 스크린샷
- 정리(cleanup): 없음

### S-2. API 응답이 대체한 리포트의 날짜와 표식을 함께 낸다 (회귀)
- 조작: 같은 격리 백엔드에 `GET /api/kr/jongga-v2/latest` 를 직접 조회한다.
- 기대: `date` 2026-09-21, `is_stale` true, `status` stale, `latest_available_date` 2026-09-21, `signals` 8건, `stale_warning`
  에 「오늘(2026-09-22)」 과 「2026-09-21」, `message` 에 「주말/휴일」 없음.
- 필수 여부(required): 예
- 실제: `date "2026-09-21"` · `status "stale"` · `is_stale true` · `latest_available_date "2026-09-21"` · `filtered_count 8` ·
  `stale_warning "오늘(2026-09-22) 기준 종가베팅 데이터가 없습니다. 최신 저장 데이터는 2026-09-21입니다."` · `message "오늘 분석이
  아직 없어서 가장 최근 저장분을 그대로 보여주고 있습니다. [업데이트] 버튼을 눌러 오늘 분석을 실행해주세요."` · `signals: 8
  first: 삼성전기 signal_date: 2026-09-21` · `weekend text in message: False`.
- 결과: 통과
- 증거: curl 출력 원문
- 정리(cleanup): 없음

### S-3. 과거 날짜를 고르면 배너 없이 같은 리포트를 보인다 (인접)
- 조작: 날짜 선택기에서 2026-09-21 을 고른다(React 의 native setter 로 값을 넣고 `change` 를 보냄).
- 기대: 배너가 사라지고 카드 8장이 그대로다(배너는 `selectedDate === 'latest'` 일 때만).
- 필수 여부(required): 아니오 (인접)
- 실제: 선택 뒤 `bannerFound: false` · `miniCharts: 8` · `selectValue: "2026-09-21"`. 「최신」 으로 되돌리자
  `bannerFound: true` · 제목 「오늘 분석은 아직 없습니다. 최신 저장분(2026-09-21)을 표시합니다.」 · `miniCharts: 8`.
- 결과: 통과
- 증거: browse `js` 출력 원문
- 정리(cleanup): 「최신」 으로 되돌림

### S-4. 유효한 일자 파일이 하나도 없으면 빈 응답을 유지한다 (인접, 하네스)
- 조작: pytest `test_build_jongga_latest_payload_stale_without_any_valid_report_stays_empty` (임시 디렉터리에 0건 파일만 둠).
- 기대: `signals == []`, `is_stale` true, `date`·`latest_available_date` 2026-03-03.
- 필수 여부(required): 아니오 (인접)
- 실제: `1 passed in 0.86s`.
- 결과: 통과
- 증거: pytest 출력
- 정리(cleanup): 없음

## 프레임워크 관점

- `/_next/mcp` `get_compilation_issues` → `{"issues": []}` · `get_errors` → `{"configErrors": [], "sessionErrors": []}`
- Flask 기동 로그: `INTERNAL_IDENTITY_SECRET` 비어 있음 경고(격리 사본에 `.env` 가 없어서, 익명 조회만 검증)와 「Scheduler is
  disabled」 뿐

## 이월한 발견

- closing-bet vitest 디렉터리 실행을 `npm run type-check` 와 동시에 돌리자 15파일 가운데 14파일이 468ms 만에 실패로 끝났고,
  단독으로 다시 돌리자 95건 전부 통과했다(두 번). 동시 실행의 워커 충돌로 보이며 코드 문제가 아니라 기록만 남긴다.
- `npx vitest run` 을 `frontend/` 에서 돌려도 저장소 루트에 `node_modules/.vite` 캐시가 생긴다(`[VCP-032]` 사이클에서 리뷰
  에이전트가 겪은 것과 같음). 커밋 전에 지웠다.
