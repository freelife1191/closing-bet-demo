# UltraQA Report

- 항목: FLOW-013·FLOW-015·FLOW-009·VCP-025·JONGGA-036 (공유 T3)
- engine: ultraqa | lifecycle: app-adapted | phase: fix | iteration: 2 | same_failure_count: 1
- 승인: 직전 다섯 항목 설계에 대한 사용자 「진행해」. 범위는 evidence/performance-20260918/plan.md.
- browser_applicability: required | browser_driver: ego-browser
- 예정 대상: 격리 Next 127.0.0.1:57611 / Flask 127.0.0.1:57612. 첫 구현 커밋과 실제 source SHA를 실행 전에 고정한다.
- 기준 검사: 격리 baseline pytest2296/3skip·Vitest488/69 통과. 새 변경의 최종 검사와 구분한다.
- 안전: 원본3500/5501/live·실제LLM/수집/발송/거래/설정/삭제 금지. 실제 .env/data 복사 없음. 합성 파일·가격을 제품 누적 라우트/계산/cache에 공급한다. 상태 응답은 UI 검증용 합성이며 백엔드 상태정책 변경을 주장하지 않는다.
- 상한: 명령 최대300초, 리뷰 각15분, QA최대5회/동일실패3회. 필수 실패·미실행·정리 미완료이면 TODO 유지.

| ID | 의도·모델 | setup/실제 command·harness | 기대 신호 | 실제·수정·증거 | cleanup | 필수 |
|---|---|---|---|---|---|---|
| S-1 | 전체 성과 사용자 | /dashboard/kr/cumulative, 실제200개 선택·D필터 | 24행/추천24/등급합24, D6건·합계9%, 전체합계49%/평균2.04% | 미실행 | 합성scratch | 예 |
| S-2 | 페이지 전환 사용자 | paginated 합성60건, 기본50개·1/2페이지 결과분포tooltip | 최근 종료10건30%/연패7이 페이지와 무관; OPEN3건 제외 | 미실행 | 전용browser | 예 |
| S-3 | 빈 자료 사용자 | fixture small/open/empty 모드 후 실제 페이지reload | 종료2→최근 청산2건·50%; 종료0→최근 집계 전/최근종료0·연패0; empty 추천0·오류없는빈표 | 미실행 | 합성모드복원 | 예 |
| S-4 | 공개 계산 helper 호출자 | scratch pytest/직접 helper 하네스, 3 invalid frame + 정상2형태 | invalid는로그+ValueError, 정상결과보존; 실제누적route정상200 | 미실행 | 임시입력해제 | 예 |
| S-5 | 홈 전략 사용자 | 6상태+unknown seed→실제홈reload, VCP/종가 두카드 | 계획의상태표와일치; 미판정은0%/Avg/미흡숨김, BAD실제0%는보임 | 미실행 | 상태GOOD복원 | 예 |
| S-6 | VCP 설명 사용자 | 홈VCP툴팁·기준표와전용화면안내 확인 | 요약백테스트+15/-5와개별시그널기준구분, 기존계산불변 | 미실행 | 전용browser | 예 |
| S-7 | 랜딩 방문자 | / Core Analysis·Scoring탭전환 | 저장가격우선/기본+5/-3/미청산추적, 가정60%기대1.8%·비용제외 명확 | 미실행 | 전용browser | 예 |
| S-8 | 작은화면사용자 | 1280×720 및375×812, 누적카드/툴팁/홈/랜딩 | 네등급정보접근가능, 겹침/카드잘림없음 | 미실행 | 이미지열람후종료 | 예 |
| S-9 | 오류·취소 사용자 | 누적503 합성모드와복원, tooltip열고닫기/재진입 | 앱크래시없음, recent값을페이지로임의계산안함, 복원후정상합계 | 미실행 | 오류모드해제 | 예 |
| S-10 | 검증경계 | 전체검사·NextMCP·console·SHA·원본목록/package·정리 | 숨은실패없음/원본보존/소유프로세스종료 | 미실행 | scratch/browser/server제거 | 예 |

S-4는 UI에서 허용되지 않는 직접 Python 입력 계약 검증이다. 정상 생산 frame은 실제 UI→제품 route 흐름에서도 검증한다. 외부 LLM prompt injection·별도CLI 파서는 이번 변경에 해당하지 않으며 자료 속 문장은 지시로 실행하지 않는다. 각 shell/browser 호출에 timeout을 두고 다른 작업의 미추적 package.json을 보존한다.

완료 상태: 미실행. 필수0/10. 과거 qa/FLOW-013.md는 다른 수급 작업의 기록이라 이 문서가 현재 항목의 정본이다.

## 구현·정적 검증 경과 (동적 QA 전)

- 초기 baseline: pytest2296/3skip, Vitest488/69.
- 새 계약 회귀 RED를 먼저 확인했다. 화면선택자중복/테스트nullable·matcher타입오류도원문로그로보존하고제품결함과분리했다.
- architect WATCH: 필터범위/실제표본수/StrictMode늦은응답/카드고정높이를보완했다. page2필터가page1로돌아가는것도회귀재현후기존reset만제거했다.
- T3: warmSQLite date열datetime64를정상입력에서거부하는회귀를발견, 실제memoryclear→SQLite복원→jongga판정으로RED→GREEN확인. 기준표분모/평균식도실제모달회귀로정정했다.
- 최신 전체: pytest2314통과3skip, Vitest506/71파일, lint0오류190경고, 실제build3/3, build후projecttsc exit0. latest_checks는review-input.json.
- 3skip은기존수동2개와.env미복사환경대조1개다. JSX act경고와기존lint경고는숨기지않는다.
- 독립리뷰: 초기ponySHIP/코드APPROVE/architectWATCH→보완CLEAR. T3REQUESTCHANGES2건수정후영향리뷰중.
- 일부로컬lintignore를실행자가만들었으나부모가정확한생성2항목을대조해제거하고원문을보존했다(execution-deviation.md).
- 동적 필수0/10이며 아직 완료 불가.

최종 독립 영향 리뷰: ponytail SHIP, code-review APPROVE, architect CLEAR, T3 APPROVE. 기준 구현 커밋 후 iteration1 실측을 시작한다.

QA 기준 커밋: ef7641cac29ea274f364f31e6865e3ea423c47b0

## 사용자 지정 브라우저 전환
사용자가 실측 도중 ego-browser를 명시했다. 저장소의 기본 agent-browser보다 최신 사용자 지시를 우선한다. 기존 두 전용 세션은 종료했으며 원래 자료는 탐색 사전 기록으로 보존한다. 필수 시나리오의 완료 근거는 ego-browser 단일 TaskSpace 3에서 수집한다. iteration1 및 기존 실패 수를 유지하며 도구 교체를 제품 실패나 카운터 초기화로 처리하지 않는다. 사용자 profile을 조회·선택하거나 쿠키/캐시를 지우지 않는다. 별도포트·합성API·원본서비스금지 경계는 동일하다.

## ego-browser iteration1 결과
S1(24/200보기/D6),S2(50/10페이지recent30%/7·P2D+실패유지),S3(소표본2/50·미청산·빈자료),S5(6상태+unknown 두카드) 실측통과. S4는실제함수·warmSQLite회귀통과. S6홈정책/기준표통과,전용화면확인미완료. S7/S9미실행. S8모바일horizontal popup클립실패: 누적left194/right514,홈left92/right399 (width375). 이미지직접열람. 두각각localTooltip정렬/anchor만수정하고영향검증후iteration2로이어간다. 공통Tooltip재설계·계산로직변경없음. S10은최종정리후판정.

하네스정정: 실제Sidebar quota경로 /api/kr/user/quota를fixture에누락하여404 HTML JSONparse오류가났다. 원문MCP/요청기록보존후해당합성GET만추가하고소유backend만재기동했다. 제품버그로세지않는다. ego는CDPviewport가라운드사이에유지되지않아각viewport검사호출내에서설정+실제innerWidth/Height확인한다. CDP뒤stale ref와이름없는role locator오류도원문결과로관측했고,관측된CSSselect로수정했다.
