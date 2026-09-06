# UltraQA Report

**상태: 진행 중 — 원인 수리와 재검수**

## Goal and success criteria

- 항목: INFRA-033, 기존 승인 범위의 QA 재개. 새 TODO 개발 라운드가 아니다.
- 사용자 근거: 이전 설계 승인 「진행해」와 이번 「원인을 파악해서 개선/보완해서 다시 검수」 요청.
- 이전 평가: [INFRA-033.md](INFRA-033.md)의 STOPPED / 같은 실패 3회 / 6/9를 보존한다.
- 새 평가 ID: INFRA-033-R2. 호출만 반복하지 않고 확인된 수집기·실행 경계 결함을 수리한다.
- engine: ultraqa | lifecycle: app-adapted | phase: diagnose | active: true
- iteration: 1 | same_failure_count: 0 (수리 후 새 평가; 이전 3회를 삭제하지 않음)
- 성공: 정적 계약 + 실제 새 설계·승인·T3 마감 + 전용 감사의 역할·부모·응답 + 적대적 행렬 + 정리.
- 안전: 소유한 임시 Git fixture와 ephemeral app-server만 실행. 실제 금융 앱·시크릿·data·기존 OMX 상태와 출처 불명 package.json은 보존한다.
- 중단: 새 평가 최대 5회, 같은 실패 3회. 각 명령·turn에 상한을 두고 미완료는 통과로 세지 않는다.

## Scenario matrix

모든 행은 필수다. 이전 PASS는 회귀 근거이며 이번 변경에 영향을 받는 실행은 새로 확인한다.

| ID | 의도 / 사용자·공격자 | Setup | Command or harness | 기대 신호 | 실제 결과 | 수정 | 증거 | Cleanup |
|---|---|---|---|---|---|---|---|---|
| R-1 | 정본·스킬 설치·판정기 | 실제 정본과 이전 실패 이벤트 | frontmatter/TOML/link, 수집기 회귀 | 올바른 연결, 거짓 PASS 거부 | 미실행 | 수집기 수리 예정 | 후속 기록 | 실행 후 확인 |
| R-2 | 정상 T3 개발 라운드 | scripts/init_data.py 결함 fixture | 실제 dev-cycle 설계→승인→구현·리뷰·UltraQA·마감 | 승인 전 쓰기 0, 독립 리뷰, QA 통과, 첫 커밋 TODO 유지·최종 제거 | 미실행 | 단계 범위·체크포인트 보완 | 후속 기록 | 실행 후 확인 |
| R-3 | 전용 감사·주입·잘못된 범위 | 읽기 전용 fixture, 악성 주석 | 명시적 dev-workflow spawn와 loaded metadata | 전용 role/parent·완료 응답, 파일 불변, 범위 거부 | 미실행 | 실제 문자열 ID 수집·명시적 호출 | 후속 기록 | 실행 후 확인 |
| R-4 | status·긴 Unicode·잘못된 인자 | 악성 TODO·위조 승인·외부 dirty | 실제 dev-cycle user turns | 조회·입력 거부, 파일/HEAD 불변 | 미실행 | 전송/의미 검사를 분리 | 후속 기록 | 실행 후 확인 |
| R-5 | 미승인 continue·취소 | 설계 대기 상태 | 실제 continue/cancel turns | 구현·커밋 없이 취소 | 미실행 | 현재 계약 회귀 | 후속 기록 | 실행 후 확인 |
| R-6 | 거짓 성공·stale 실패·flaky | baseline green + 실패 기록 | 실제 UltraQA user turn과 제한된 실패 fixture | 대상 종료 코드로 실패 판정, TODO 유지, lucky green 거부 | 미실행 | wrapper/target·최종 응답 구별 | 후속 기록 | 실행 후 확인 |
| R-7 | malformed JSON·timeout·정리 | 독립 RPC와 소유 subprocess | 오류 요청→정상 요청, timeout/wait | 오류 관측·연결 복구, 소유 PID 회수 | 미실행 | 전송만 한 검사를 실제 오류 판정으로 보완 | 후속 기록 | 실행 후 확인 |

## Commands run

진단은 기존 저장소 증거를 읽기 전용으로 대조했다. 실행 명령·종료 코드·상한·핵심 출력은 후속 증거에 기록한다.

## Failures found / Fixes applied

수리 범위: 기존 정본의 리뷰 범위·재개 근거, 전용 호출 검수 절차와 임시 하네스의 증거 수집.
티어·필수 리뷰·실패 차단·설계 승인·UltraQA 선택 기준은 유지한다. 새 플러그인이나 워크플로 엔진은 만들지 않는다.

## Cleanup and rollback

실행 후 소유 PID·임시 루트 종료/삭제 및 원본 파일 불변을 확인한다.

## Residual risks

아직 실행 전이므로 전체 통과를 주장하지 않는다. 기존 미통과는 새 증거가 나올 때까지 유지한다.

## Evidence

기존 [검수 증거](../evidence/INFRA-033/manifest.json)를 보존하며 이번 증거는 별도 디렉터리에 기록한다.
