# UltraQA Report

- 항목: JONGGA-012
- engine: ultraqa
- lifecycle: app-adapted
- phase: ready
- iteration: 0
- same_failure_count: 0
- active: true
- cleanup: pending
- browser_applicability: required
- browser_driver: agent-browser
- namespace: devcycle-jongga-rl9kpa8c / session: viewer
- 대상: http://127.0.0.1:57262/dashboard/kr/closing-bet 및 /dashboard/kr, /dashboard/kr/cumulative
- 기준: 구현 첫 커밋 후 실제 SHA를 기록한다.
- baseline: 기준pytest2232/3기존skip·Vitest418/58 → 구현후pytest2249/3기존skip·Vitest424/59 (sandbox IPC·실패캐시 보완 이력 보존).
- 안전: 합성 자료/가짜NextAuth/격리서버만 사용. 원본3500/5501/live/시크릿/data변경 및 실제 외부호출 없음.
- 대역: HTTP 응답 구성은 fixture. 변경한 가격 정규화·백테스트 계산은 실제 checkout 함수를 사용한다. 과거 조회는 실제 Flask history route를 내부 test client로 실행한다. 파일 로더·등급재산정·정렬은 대역이며 실제 Flask 앱 전체의 검증으로 세지 않는다.
- 상한: 5cycles/동일실패3, browser명령60초.
- UltraQA Report: [JONGGA-012.md](JONGGA-012.md)

## Scenario matrix

| ID | 의도/사용자·공격자 | Setup / command | 기대 신호 | 실제 결과 | 수정 | 증거 | Cleanup | 필수 |
|---|---|---|---|---|---|---|---|---|
| S-1 | 기본가격·누락값 | agent-browser 종가 카드와 점수표/전략안내 | entry100000 target105000 stop97000; +5/-3 | 미실행 | — | 실행 후 기록 | 대기 | 예 |
| S-2 | 명시가격·과거자료 | agent-browser custom 모드 및 과거 날짜 선택 종가 카드 | target108000 stop96000; +8/-4; 원본fixture 불변 | 미실행 | — | 실행 후 기록 | 대기 | 예 |
| S-3 | 성과계산 연결 | agent-browser 홈 및 누적성과 정상target/stop | 실제 backend 계산과 화면의 WIN+5 / LOSS-3 일치 | 미실행 | — | 실행 후 기록 | 대기 | 예 |
| S-4 | 경계·OPEN | agent-browser 동시hit/OPEN 모드 홈·누적성과 | 같은 일봉 손절 우선, 미도달 OPEN; 승률에 미청산 불포함 | 미실행 | — | 실행 후 기록 | 대기 | 예 |
| S-5 | custom 성과 | agent-browser custom 가격 모드 홈·누적성과 | 기본5/-3이 아닌 저장8/-4 도달 판정 | 미실행 | — | 실행 후 기록 | 대기 | 예 |
| S-6 | 모바일·복구 | agent-browser 375x812 종가카드/점수표,1280x900 복귀 | 가격·출처 읽기 가능, 새오류 없음 | 미실행 | — | 실행 후 기록 | 대기 | 예 |

## 적대적 분류

누락/비정상숫자/원단위경계는 실제 함수 회귀검사와 위 브라우저 행을 연결한다. 깨진 JSON/CLI flag/traversal은 변경하는 입력 경계가 아니므로 적용 불가. 중단·재개는 이 기록과 소스해시 대조로 수행한다. dirty보존/timeout/exit검증/정리는 전체 공통 필수조건이다. skip은 기존3건으로 통과수에 넣지 않는다.

## 실행 결과

- 필수 통과: 0 (미실행)
- 재개: 정적 검증·첫 커밋 후 QA 실행.
