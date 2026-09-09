# UltraQA Report

- 항목: JONGGA-012
- engine: ultraqa
- lifecycle: app-adapted
- phase: cleanup
- iteration: 2
- same_failure_count: 0
- active: true
- cleanup: pending
- browser_applicability: required
- browser_driver: agent-browser
- namespace: devcycle-jongga-rl9kpa8c / session: viewer
- 대상: http://127.0.0.1:57262/dashboard/kr/closing-bet 및 /dashboard/kr, /dashboard/kr/cumulative
- source_commit: ba91b8eadf96f5586a3849733a1bb09a1411e5e2
- 첫 구현/행렬 커밋: 252568c; QA 모바일 수정: ba91b8e
- baseline: 기준pytest2232/3기존skip·Vitest418/58 → 구현후pytest2249/3기존skip·Vitest424/59 (sandbox IPC·실패캐시 보완 이력 보존).
- 안전: 합성 자료/가짜NextAuth/격리서버만 사용. 원본3500/5501/live/시크릿/data변경 및 실제 외부호출 없음.
- 대역: HTTP 응답 구성은 fixture. 변경한 가격 정규화·백테스트 계산은 실제 checkout 함수를 사용한다. 과거 조회는 실제 Flask history route를 내부 test client로 실행한다. 파일 로더·등급재산정·정렬은 대역이며 실제 Flask 앱 전체의 검증으로 세지 않는다.
- 상한: 5cycles/동일실패3, browser명령60초.
- UltraQA Report: [JONGGA-012.md](JONGGA-012.md)

## Scenario matrix

| ID | 의도/사용자·공격자 | Setup / command | 기대 신호 | 실제 결과 | 수정 | 증거 | Cleanup | 필수 |
|---|---|---|---|---|---|---|---|---|
| S-1 | 기본가격·누락값 | agent-browser 종가 카드와 점수표/전략안내 | entry100000 target105000 stop97000; +5/-3 | 통과: 105000/97000, +5/-3; 점수표와 Tips 일치 | — | cycle1-normal-prices, cycle1-criteria-exit, cycle1-tips, cycle1-missing-latest | 런타임 정리 완료 | 예 |
| S-2 | 명시가격·과거자료 | agent-browser custom 모드 및 과거 날짜 선택 종가 카드 | target108000 stop96000; +8/-4; 원본fixture 불변 | 통과: 108000/96000, +8/-4 보존; 실제 history route 누락값105000/97000 | — | cycle1-custom-history, cycle2-custom-prices, cycle2-missing-history | 런타임 정리 완료 | 예 |
| S-3 | 성과계산 연결 | agent-browser 홈 및 누적성과 정상target/stop | 실제 backend 계산과 화면의 WIN+5 / LOSS-3 일치 | 통과: 홈100%/Avg+5와누적성공/+5.0%; 손절은양쪽-3% | — | cycle2-overview-win, cycle2-cumulative-win-row, cycle2-cumulative-stored-stophit | 런타임 정리 완료 | 예 |
| S-4 | 경계·OPEN | agent-browser 동시hit/OPEN 모드 홈·누적성과 | 같은 일봉 손절 우선, 미도달 OPEN; 승률에 미청산 불포함 | 통과: 같은봉LOSS/-3; 미도달은보유/+5.0반올림이나승률0% | — | cycle2-cumulative-stored-sameday, cycle2-cumulative-stored-open, cycle2-overview-stored-open | 런타임 정리 완료 | 예 |
| S-5 | custom 성과 | agent-browser custom 가격 모드 홈·누적성과 | 기본5/-3이 아닌 저장8/-4 도달 판정 | 통과: custom WIN+8/LOSS-4, 홈·누적일치 | — | cycle2-cumulative-custom-targethit, cycle2-cumulative-custom-stophit, cycle2-performance-results.json | 런타임 정리 완료 | 예 |
| S-6 | 모바일·복구 | agent-browser 375x812 종가카드/점수표,1280x900 복귀 | 가격·출처 읽기 가능, 새오류 없음 | 통과: 1회차겹침46.171875px²→2회차0;375px1열/1280px2열 | 모바일1열 보완 | cycle1-mobile-source-check, cycle2-mobile-fixed, cycle2-mobile-criteria, cycle2-resized-desktop, cycle2-mobile-geometry.json | 런타임 정리 완료 | 예 |

## 적대적 분류

누락/비정상숫자/원단위경계는 실제 함수 회귀검사와 위 브라우저 행을 연결한다. 깨진 JSON/CLI flag/traversal은 변경하는 입력 경계가 아니므로 적용 불가. 중단·재개는 이 기록과 소스해시 대조로 수행한다. dirty보존/timeout/exit검증/정리는 전체 공통 필수조건이다. skip은 기존3건으로 통과수에 넣지 않는다.

## 실행 결과

- 필수 통과: 6/6
- 미통과 필수: 없음
- 남은 단계: 검증된 커밋 통합·임시 clone 제거 후 최종 완료 기록.

## 1회차 실패와 보완

375px에서 기준일 span과 체크리스트 badge의 교차 면적46.171875px²를 관측했다. 모바일1열/sm이상2열로 수정하고 2회차에서 재측정한다. 원문증거 qa-cycle1-failure.json 및 cycle1-mobile-source-check.png.

## 실행 증거와 제한

- 증거 루트: [jongga-exits-2026-09-09](../evidence/jongga-exits-2026-09-09/qa-verification.json). 표의 파일명은 이 디렉터리이며 화면 이름은 `.png`/`.json`/`.snapshot.txt`와 연결된다.
- 화면조작은 agent-browser 전용namespace에서 snapshot/ref click/select/scroll로 수행했다. before/after DOM·CLI 명령·응답은 browser-commands.jsonl.gz, 요청/응답은 requests.jsonl.gz에 있다.
- 실제 계산은 checkout normalizer·shared trade·stats·KPI이며 과거 조회는 실제 Flask history route를 내부 test client로 실행했다. 외부 데이터·파일로더·등급재산정·정렬은 합성 대역이다. 전체 Flask factory나 실제 공급자 연결의 실측으로 세지 않는다.
- GET166건 모두200, 변경메서드0. 브라우저 page/console 오류0; Next get_compilation_issues와get_errors 모두빈배열.
- 35개 screenshot을 view_image로 열었다. 1회차실패이미지도보존. 외부CDN 아이콘글꼴을차단하여 일부아이콘시각검증제한이있다. 홈기준문구는DOM으로대조했으며그screenshot은성과카드수치를검증한다. 합성score88은이입력에대한가격UI검사용으로등급결정검증으로세지않는다.
- 준비실패: Netscape파일을cookies --curl에주어거부→가짜Cookie curl파일로수리; heading ref의추가속성정규식과매매원칙제목2개매칭을수리. 제품결함과구분하며harness-failures.json에남긴다.
- 정적: pytest2249통과/기존skip3, Vitest424통과/59(실제build·TS포함), lint0오류/201기존경고. 기존chat004 타이머경합1회실패는원문보존후원인대조·단독2통과·전체424통과, INFRA068이월.
- 독립리뷰: 전용code-reviewer APPROVE, architect WATCH(생산계약밖frame); 합성COMMENT를APPROVE로바꾸지않았다. QA CSS delta는전용ponytail/code-reviewer/architect CLEAR. T3심층체크리스트는develop/baseSHA에맞춘App대응으로수행했다.
- 런타임 정리: 소유57261/57262/63173 종료, 전용브라우저·namespace·profile·가짜env/쿠키제거. clone 제거는 통합 후 최종 기록한다.
