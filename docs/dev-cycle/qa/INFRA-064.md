# UltraQA Report — INFRA-064

## 목표와 실행 경계

날짜 지정 Market Gate GET은 조회만 수행하고, 최신 GET 자동 분석은 워커 공통으로 실행 종료 후 300초간 재시작을 억제한다. 분석 중만 initializing을 반환한다.
원본 3500/5501·운영 URL·실제 .env·data는 사용하지 않는다. 소유한 독립 develop 사본, 임시 파일, 외부 수집 대역과 실제 Next/Flask/UI로 검증한다. 원본 미추적 package.json을 보존한다.

- engine: ultraqa
- lifecycle: app-adapted
- phase: planning
- iteration: 1
- same_failure_count: 0
- active: true
- 기준: c25e09b (첫 구현 커밋 확정 뒤 갱신)
- browser_applicability: required
- 근거: /dashboard/kr의 오늘/과거 날짜 화면과 /dashboard/kr/vcp가 변경 GET을 소비한다.
- browser_driver: agent-browser
- baseline: pytest 1965 passed/3 skipped(exit0), vitest 373 passed/57 files(exit0)
- timeout: 검사별 480초, 리뷰별 900초, 브라우저 실행별 900초. 최대 5회·동일 실패 3회.
- cleanup: 예정

## 시나리오 행렬

| ID | 의도·행위자 | setup·명령/하네스 | 기대 신호 | 실제 결과·수정·증거 | 정리 | 필수 |
|---|---|---|---|---|---|---|
| Q1 | 정상 최신 조회 | 임시 저장 자료와 실제 GET/분석 대역, pytest·브라우저 | 최신 자료 조회는 분석0; 낡은 자료 첫 요청1; 완료 후 값 표시 | 미실행 | 임시 자료 제거 | 예 |
| Q2 | 과거 날짜 남용 | 서로 다른 없는 날짜·빈/Unicode/특이 date를 실제 GET | date 지정 분석0, 저장된 과거 자료는 보존 | 미실행 | 임시 자료 제거 | 예 |
| Q3 | 반복·실패 재시도 | 실제 파일 잠금·시계 제어·분석/스레드 start 실패 | 종료 후 299초 억제, 300초 재실행; 실패도 동일 | 미실행 | 스레드 join·임시 파일 제거 | 예 |
| Q4 | 여러 워커·중단·잘못된 상태 | 실제 별도 프로세스/flock·잘못된 timestamp·잠금/I/O 불가 | 실행중 중복0; 다음 워커 쿨다운 공유; 불명확 상태 fail closed | 미실행 | 소유 프로세스 join·파일 제거 | 예 |
| Q5 | 사용자 UI 회귀 | agent-browser로 /dashboard/kr 오늘/과거 전환·재조회, VCP 진입 | 실제 GET과 화면값 일치; 쿨다운을 분석중으로 표시하지 않음 | 미실행 | 전용 세션 종료 | 예 |
| Q6 | 실패 UI | 격리 수집 실패 뒤 실제 UI 재조회 | 즉시 재실행0; 분석중 허위 표시0; console/page 오류 평가 | 미실행 | 전용 세션 종료 | 예 |
| Q7 | 검사·증거·정리 보장 | 전체 pytest/vitest, diff 검사, PID/port·원본 hash 대조 | 종료코드와 결과 일치; 필수 전부 통과; 소유 임시물 제거 | 미실행 | 완료 증거 기록 | 예 |

외부 자료 속 지시 실행은 이 GET의 기능이 아니므로 prompt injection 동적 행은 해당 없음. 특이 query는 코드/명령으로 평가하지 않는다. 인증 정책·관리자 강제 POST·스케줄러 변경은 범위 밖이며 실운영으로 실행하지 않는다. 하네스 setup 실패와 제품 실패를 구분해 재시도 횟수와 원인을 보존한다.

## 정적 검증

- TDD 첫 RED: 18 failed/2 passed. 날짜 조회·실패 재시도·멀티프로세스 상태·파일 오류를 재현.
- GREEN: 관련 54 passed. 손상된 미래 시각/긴 기록 복구 RED 2 failed/23 passed 후 최종 관련 59 passed.
- 전체 pytest: 1990 passed/3 skipped, exit0. 수동 Gemini 2개·격리 사본 .env 부재 1개 skip.
- 전체 vitest: 57 files/373 passed, exit0. Next build smoke 포함.
- AST: 수정 Python 4개 파싱 통과. 실제 실행/원문/종료코드는 evidence/INFRA-064 참조.
- 기존 날짜 기반 초기화 검사 하나는 승인한 새 계약에 맞춰 최신 조회의 초기화 검사로 변경하고, 별도 날짜 조회 금지 검사를 추가했다. 기대값만 낮춰 실패를 숨기지 않았다.

## 독립 리뷰 보완 이력

- 완료 기록 write 실패가 빈 파일을 남기는 root 재현: io-red 1FAIL → running 표식 및 write-first 적용 → io-green 26PASS.
- code-reviewer: 쿨다운 조회 자체의 flock 경합을 분석 중으로 오인. architect: 부분 flush 숫자를 만료 시각으로 오인. review-red 3FAIL 재현.
- exact running 판별과 cooldown:<timestamp>:end 완결 형식으로 보완. review-green은 **관련 65PASS(새 파일31개 포함)**, exit0. 이전54/59/62PASS는 중간 이력이며 최신 검사 수를 대신하지 않는다.
- type-check exit0, lint exit0(0 errors/199 warnings). 새 프론트 소스 변경 없음.

- 최종(리뷰 반영) 전체 pytest: **1996 passed/3 skipped**, exit0, 27.48초. pytest-reviewed가 최종 코드의 근거다.
- 표준 TextIOWrapper의 실제 FileIO.write ENOSPC 주입 후 close 검사: 예외28을 내면서도 wrapper/buffer/raw 모두 closed, fd는 EBADF9. 무효화된 임의 close mock과 실제 표준 IO 정리 계약을 구분했다.
