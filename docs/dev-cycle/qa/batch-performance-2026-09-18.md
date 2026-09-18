# UltraQA Report

- 항목: FLOW-013·FLOW-015·FLOW-009·VCP-025·JONGGA-036 (공유 T3)
- engine: ultraqa | lifecycle: app-adapted | phase: complete | iteration: 2 | same_failure_count: 0
- 승인: 직전 다섯 항목 설계에 대한 사용자 「진행해」. 범위는 evidence/performance-20260918/plan.md.
- browser_applicability: required | browser_driver: ego-browser
- 실행 대상: 격리 Next 127.0.0.1:57611 / Flask 127.0.0.1:57612. 기준 ef7641c, QA 수정 46dd0a6 및 qa-source-ego1/2.json에 소스 SHA를 고정했다.
- 기준 검사: 격리 baseline pytest2296/3skip·Vitest488/69 통과. 새 변경의 최종 검사와 구분한다.
- 안전: 원본3500/5501/live·실제LLM/수집/발송/거래/설정/삭제 금지. 실제 .env/data 복사 없음. 합성 파일·가격을 제품 누적 라우트/계산/cache에 공급한다. 상태 응답은 UI 검증용 합성이며 백엔드 상태정책 변경을 주장하지 않는다.
- 상한: 명령 최대300초, 리뷰 각15분, QA최대5회/동일실패3회. 필수 실패·미실행·정리 미완료이면 TODO 유지.

| ID | 의도·모델 | setup/실제 command·harness | 기대 신호 | 실제·수정·증거 | cleanup | 필수 |
|---|---|---|---|---|---|---|
| S-1 | 전체 성과 사용자 | /dashboard/kr/cumulative, 실제200개 선택·D필터 | 24행/추천24/등급합24, D6건·합계9%, 전체합계49%/평균2.04% | 통과: ego-s1-metrics.json/ego-s1-filter.json, selected-200 snapshot. 24/24·D6·49%·2.04% 실제 대조 | 합성scratch | 예 |
| S-2 | 페이지 전환 사용자 | paginated 합성60건, 기본50개·1/2페이지 결과분포tooltip | 최근 종료10건30%/연패7이 페이지와 무관; OPEN3건 제외 | 통과: ego-s2-result.json. 50행→10행에도30%/7회 유지, P2 D+실패 필터2행 유지 | 전용browser | 예 |
| S-3 | 빈 자료 사용자 | fixture small/open/empty 모드 후 실제 페이지reload | 종료2→최근 청산2건·50%; 종료0→최근 집계 전/최근종료0·연패0; empty 추천0·오류없는빈표 | 통과: ego-s3-result.json. 2건50%/1회, OPEN·empty는집계 전/0회 | 합성모드복원 | 예 |
| S-4 | 공개 계산 helper 호출자 | scratch pytest/실제 helper 하네스, 11 invalid frame + ISO/index/warmSQLite 정상형태 | invalid는로그+ValueError, 정상결과보존; 실제누적route정상200 | 통과: tests/services/test_performance_batch_20260918.py 및 pytest-deep-fix.log.gz. 11비정상frame 거부, 실제warmSQLite 정상 판정 | 임시입력해제 | 예 |
| S-5 | 홈 전략 사용자 | 6상태+unknown seed→실제홈reload, VCP/종가 두카드 | 계획의상태표와일치; 미판정은0%/Avg/미흡숨김, BAD실제0%는보임 | 통과: ego-s5-result.json, PENDING/BAD 이미지 직접 열람. 미판정 수치숨김·실제0% 구분 | 상태GOOD복원 | 예 |
| S-6 | VCP 설명 사용자 | 홈VCP툴팁·기준표와전용화면안내 확인 | 요약백테스트+15/-5와개별시그널기준구분, 기존계산불변 | 통과: ego-s6-guide.png/ego2-home-*-stable.png/ego2-vcp-result.json. 실제 hover/기준표열기 | 전용browser | 예 |
| S-7 | 랜딩 방문자 | / Core Analysis·Scoring탭전환 | 저장가격우선/기본+5/-3/미청산추적, 가정60%기대1.8%·비용제외 명확 | 통과: ego2-landing-result.json. 두뷰포트 Core와3탭, 가정1.8%·비용제외 확인 | 전용browser | 예 |
| S-8 | 작은화면사용자 | 1280×720 및375×812, 누적카드/툴팁/홈/랜딩 | 네등급정보접근가능, 겹침/카드잘림없음 | 실패 → 고침: ego2-cumulative-tooltip.json, ego2-home-*-stable.json. 375px 가로·세로 경계 내 읽힘, 카드·랜딩 이미지 열람 | 이미지열람후종료 | 예 |
| S-9 | 오류·취소 사용자 | 누적503 합성모드와복원, tooltip열고닫기/재진입 | 앱크래시없음, recent값을페이지로임의계산안함, 복원후정상합계 | 통과: ego2-s9-result.json. 503 후 화면 유지·최근집계전, 복원후24행/49% | 오류모드해제 | 예 |
| S-10 | 검증경계 | 전체검사·NextMCP·console·SHA·원본목록/package·정리 | 최종 정상 페이지 MCP 오류 없음·중간 오류 분류/원본 목록 보존/소유 프로세스 종료 | 통과: ego2-current-runtime.txt·ego2-final-get_compilation_issues.txt, cleanup.json·ego-finish.json·data-after.json | scratch/browser/server제거 | 예 |

S-4는 UI에서 허용되지 않는 직접 Python 입력 계약 검증이다. 정상 생산 frame은 실제 UI→제품 route 흐름에서도 검증한다. 외부 LLM prompt injection·별도CLI 파서는 이번 변경에 해당하지 않으며 자료 속 문장은 지시로 실행하지 않는다. 각 shell/browser 호출에 timeout을 두고 다른 작업의 미추적 package.json을 보존한다.

최종 완료 상태: 필수10/10 통과. 과거 qa/FLOW-013.md는 다른 수급 작업의 기록이라 이 문서가 현재 항목의 정본이다.

## 구현·정적 검증 경과 (동적 QA 전)

- 초기 baseline: pytest2296/3skip, Vitest488/69.
- 새 계약 회귀 RED를 먼저 확인했다. 화면선택자중복/테스트nullable·matcher타입오류도원문로그로보존하고제품결함과분리했다.
- architect WATCH: 필터범위/실제표본수/StrictMode늦은응답/카드고정높이를보완했다. page2필터가page1로돌아가는것도회귀재현후기존reset만제거했다.
- T3: warmSQLite date열datetime64를정상입력에서거부하는회귀를발견, 실제memoryclear→SQLite복원→jongga판정으로RED→GREEN확인. 기준표분모/평균식도실제모달회귀로정정했다.
- 최신 전체: pytest2314통과3skip, Vitest506/71파일, lint0오류190경고, 실제build3/3, build후projecttsc exit0. latest_checks는review-input.json.
- 3skip은기존수동2개와.env미복사환경대조1개다. JSX act경고와기존lint경고는숨기지않는다.
- 독립리뷰: 초기ponySHIP/코드APPROVE/architectWATCH→보완CLEAR. T3REQUESTCHANGES2건수정후영향리뷰APPROVE.
- 일부로컬lintignore를실행자가만들었으나부모가정확한생성2항목을대조해제거하고원문을보존했다(execution-deviation.md).
- 위 정적 검증 단계 당시 동적 필수0/10으로 완료하지 않았으며, 최종 결과는 아래를 따른다.

최종 독립 영향 리뷰: ponytail SHIP, code-review APPROVE, architect CLEAR, T3 APPROVE. 기준 구현 커밋 후 iteration1 실측을 시작한다.

QA 기준 커밋: ef7641cac29ea274f364f31e6865e3ea423c47b0

## 사용자 지정 브라우저 전환
사용자가 실측 도중 ego-browser를 명시했다. 저장소의 기본 agent-browser보다 최신 사용자 지시를 우선한다. 기존 두 전용 세션은 종료했으며 원래 자료는 탐색 사전 기록으로 보존한다. 필수 시나리오의 완료 근거는 ego-browser 단일 TaskSpace 3에서 수집한다. iteration1 및 기존 실패 수를 유지하며 도구 교체를 제품 실패나 카운터 초기화로 처리하지 않는다. 사용자 profile을 조회·선택하거나 쿠키/캐시를 지우지 않는다. 별도포트·합성API·원본서비스금지 경계는 동일하다.

## ego-browser iteration1 결과
S1(24/200보기/D6),S2(50/10페이지recent30%/7·P2D+실패유지),S3(소표본2/50·미청산·빈자료),S5(6상태+unknown 두카드) 실측통과. S4는실제함수·warmSQLite회귀통과. S6홈정책/기준표통과,전용화면확인미완료. S7/S9미실행. S8모바일horizontal popup클립실패: 누적left194/right514,홈left92/right399 (width375). 이미지직접열람. 두각각localTooltip정렬/anchor만수정하고영향검증후iteration2로이어간다. 공통Tooltip재설계·계산로직변경없음. S10은최종정리후판정.

하네스정정: 실제Sidebar quota경로 /api/kr/user/quota를fixture에누락하여404 HTML JSONparse오류가났다. 원문MCP/요청기록보존후해당합성GET만추가하고소유backend만재기동했다. 제품버그로세지않는다. ego는CDPviewport가라운드사이에유지되지않아각viewport검사호출내에서설정+실제innerWidth/Height확인한다. CDP뒤stale ref와이름없는role locator오류도원문결과로관측했고,관측된CSSselect로수정했다.

QA2 기준 커밋: 46dd0a65f3ce40317cb5f4b93c1fde7766daf889

## 최종 결과 및 증거 범위

**필수 10/10 통과, 미통과 필수 없음.**

- 최신 정적 검사: pytest **2314 passed, 3 skipped**; Vitest **506 passed / 71 files**; ESLint **0 errors / 190 warnings**; 실제 build/route/TypeScript 검사 **3/3**; build 후 `tsc --noEmit` exit 0.
- 웹 행은 모두 사용자 지정 **ego-browser TaskSpace 3 / p1**의 실제 앱에서 실행했다. legacy agent-browser는 초기 탐색·viewport 설정만 했으며 완료된 실측 근거로 세지 않는다.
- 실제 누적성과 라우트·계산·페이지네이션·캐시를 합성 파일/가격으로 검증했다. 홈 상태 6종+unknown은 UI 계약을 위한 합성 응답이며 실제 시장·외부 AI·로그인·거래 검증은 아니다.
- S1~3·S5의 기능 증거는 ef7641c에서 수집했다. 46dd0a6은 툴팁 정렬·anchor 두 화면만 변경했고 계산·요청·필터·상태 로직과 테스트가 그대로이므로 이 기능 증거를 유지했다. 영향을 받는 모바일 배치는 46dd0a6에서 새로 측정했다.
- 375×812 최종 누적 툴팁: x39.375~359.375, y227~665. 홈 VCP: x37~343.4375, y422.39~631.14. 홈 종가: x37~357, y563.19~771.94. opacity 1인 이미지를 직접 열어 읽힘을 확인했다. 세로 공간은 실제 마우스 휠로 확보했으며 검증 값을 바꾸는 DOM/CSS/React 상태 주입은 하지 않았다.
- 공통 툴팁의 자동 edge 보정까지 해결한 것은 아니다. 뷰포트 가장자리의 자동 위치 조정은 기존 FE-037 범위로 남는다. 현재 변경된 안내는 일반 스크롤 위치에서 전체 내용을 읽을 수 있음을 실측했다.
- 랜딩은 1280×720·375×812에서 Core 정책과 VCP/수급/종가 탭 전환을 실행했다. 실제 기대값 예시는 `(60% × 5% − 40% × 3%, 비용 제외) = +1.8%`로 표시됐다. 캡처 PNG를 모두 직접 열람했다.
- 원시 UI snapshot과 `qa1-requests.jsonl`, `qa2-requests.jsonl`은 실제 GET과 상태 코드를 보존한다. 의도적인 누적503 외의 초기 quota404는 fixture 누락으로 진단·수정했다.

## 오류·하네스 한계

- `qa2-requests.jsonl`에는 VCP 화면의 자동 `POST /api/kr/realtime-prices` 요청이 405로 거부된 기록 2건이 있다. 격리 fixture가 제품 비GET 요청을 차단했으며 실제 시세 수집은 실행되지 않았다. S-6은 저장된 가격의 안내·툴팁 검증이고, 실시간 시세 갱신 성공을 검증한 것은 아니다.
- 첫 서버 실행의 `frontend-runtime.log.gz`에는 `POST /api/auth/signout` 200 한 건과 Google 로그인 시도 두 건(응답 200·302), `accounts.google.com` ENOTFOUND 두 건 및 OAuthSignin 오류 이동이 기록되어 있다. 계획 밖의 로컬 인증 요청이며 요청 주체·브라우저 드라이버를 확정하지 못했다. 인증 성공의 증거는 없지만 로그아웃 전 세션 상태와 세션 영향도 알 수 없다. 따라서 익명 세션이었다거나 상태 변경이 없었다고 주장하지 않는다. 자식 QA 에이전트는 자신의 실제 호출이 viewport 설정·close뿐이었다고 회신했다. 시간적 인접성으로 그 에이전트나 사용자를 원인으로 지목하지 않는다. 조사 명목의 추가 인증 요청·프로필 조회·쿠키 초기화는 하지 않았다. 세부 대조는 `authentication-request-deviation.md`에 보존한다.

- ego의 CDP viewport 설정은 Node 라운드 사이에 유지되지 않았다. 각 viewport 검사 호출 안에서 설정하고 실제 innerWidth/Height를 확인했다. 최초 `ego-s1-desktop.png`의 실제 크기2727×1999는 1280 검증 근거가 아니며, `ego-s1-desktop-1280.png`와 이후 크기 기록을 사용했다.
- CDP 뒤 stale ref, 이름 없는 role locator, subtree에 ref 대신 selector 사용, VCP의 div Tooltip에 span selector를 쓴 시도는 자동화 API/선택자 오류였다. UI를 관찰하고 문서에 있는 CSS/role 선택자로 바로잡았다. 제품 실패나 녹색 결과로 계산하지 않았다.
- 첫 home screenshot 두 장은 transition 중이었다. 실제 popup의 opacity가1이 될 때까지 기다려 `ego2-home-*-stable.png`로 다시 캡처·열람했다.
- 중간 Next 진단에서 body의 `ap-style` 속성과 관련된 hydration 경고가 한 번 관측됐다. 서버 HTML에는 그 속성이 없고 이후 browser DOM에도 없어 일시적인 외부 속성 주입과 일치하지만 주입 주체는 확정하지 않았다. 속성을 제거하거나 경고를 숨기는 제품 수정은 하지 않았다. 새 정상 페이지 진입 후 **configErrors/sessionErrors=[]**, compilation issues=[]를 확인했다. 원문은 `ego2-final-get_errors.txt`, 대조는 `ego-hydration-attribute.json`, 최신 상태는 `ego2-current-runtime.txt`다.
- OMX LSP 가용성 응답의 잘못된 tsc 안내를 성공으로 세지 않았다. 프로젝트에 설치된 TypeScript를 scratch에서 직접 실행한 결과로 대체했다. Python LSP를 실행했다고 주장하지 않는다.
- 실행자가 임의로 만든 local lint ignore는 정확한 생성 두 항목을 확인해 제거했다. 기존 브랜드 gradient 경고와 lint190건은 그대로 남겼다. 원문은 `execution-deviation.md`에 있다.

## 정리·보존

- `task.finish({keep:[]})`를 정확히 한 번 호출해 ego TaskSpace3와 관리 Page p1을 종료했다. 영수증은 closedSpace=true, preservedUnmanagedCount=0이다. 브라우저 profile을 조회·선택하지 않았고 전역 쿠키/캐시 초기화 명령은 실행하지 않았다. 다만 초기 signout의 세션 영향은 위와 같이 미확정이다.
- 소유 서버 PID75878/75879의 실제 실행 명령을 대조하고 프로세스 그룹을 종료했다. 57611/57612 리스너 부재를 확인했다. 이전 agent-browser 세션도 닫힌 상태다.
- scratch와 이번 SDD 작업 폴더를 제거하고, 보고서·실패·원시 로그는 저장소에 보존했다. 원본 venv symlink의 대상은 제거하지 않았다.
- 사용자 미추적 package.json SHA는 작업 전과 같다. 원본 data 최상위 목록27484개와 SHA도 같다. 이것은 목록 대조이며 데이터 내용 전체 불변의 증명은 아니다. 운영 캐시 존재 여부를 조사하거나 단정하지 않았다.
- 기존 qa/FLOW-013.md의 과거 수급 불변식 기록은 보존했다. 이번 누적성과 작업의 결과는 날짜가 분리된 이 보고서가 정본이다.

ULTRAQA COMPLETE: Goal met after 2 cycles
