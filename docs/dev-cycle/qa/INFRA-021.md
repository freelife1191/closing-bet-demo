# UltraQA Report

- 항목: INFRA-021 — 미사용 성과 리포트 제거 및 유지된 집계 경로 회귀
- engine: ultraqa
- lifecycle: app-adapted
- phase: complete
- iteration: 1
- same_failure_count: 0
- baseline: pytest2279/3skip, Vitest462/67files(build·tsc 포함), lint0errors/198warnings; 모두 exit0
- base: 4757dc354d37598fe0f53dd182eb67c458a3f115
- browser_applicability: not-applicable
- browser_driver: none
- 판정 근거: evidence/dead-code-20260909/scope.md의 호출부 범위. UI/API/응답 변화 없음.
- required: 예
- cleanup: 완료 — 소유 scratch·프로세스·임시 로그 제거, 원본 보존
- 범위/안전/상한: ../evidence/dead-code-20260909/scope.md

## 시나리오 행렬

| ID | 의도/모델 | setup·명령 | 기대 | 실제 | 수정 | 증거 | cleanup | required |
|---|---|---|---|---|---|---|---|---|
| S-1 | 제거 표면 | 격리 Python 하네스: 실제 SignalTracker 클래스 import | get_performance_report 없음 | 통과: 실제 클래스에 get_performance_report 없음 | 없음 | ../evidence/dead-code-20260909/probe.log.gz · cleanup.json | 완료 | 예 |
| S-2 | 인접 유지 동작 | 격리 Python 하네스: 실제 SignalTracker.calculate_vcp_score에 정상/빈 입력 | 20.0/0.0, 유지된 KPI totalRoi=45/profitFactor=null 및 strict JSON 직렬화 | 통과: score0/20, totalRoi45, profitFactor=null, allow_nan=False 직렬화 성공 | 없음 | ../evidence/dead-code-20260909/probe.log.gz · cleanup.json | 완료 | 예 |
| S-3 | dirty 및 정리 | 격리 Python 하네스: 하네스 전후 root package hash 대조/임시 디렉터리 확인 | 사용자 파일 동일, 임시 fixture 없음 | 통과: 사용자 package 해시동일/소스동일/ps·lsof 소유프로세스0/scratch삭제 | 없음 | ../evidence/dead-code-20260909/probe.log.gz · cleanup.json | 완료 | 예 |

잘못된 JSON·웹 권한·취소 UI는 삭제 대상/종료 함수의 입력 계약에 없어 적용 불가. 반복 종료·자료 속 지시·dirty 보존·30초 timeout·실제 assert/종료코드를 검사한다.

## 실행 결과

- 필수 통과: 3/3
- 미통과 필수: 없음
- 완료 판정: 완료 가능

- QA source commit: 8487e7d665ef08ad0ae7e46cebe7062d6aa1b8ed

- 실행·갱신: 2026-09-09 20:21
- UltraQA Report: [묶음 보고서](../reviews/batch-dead-code-2026-09-09.md)
- baseline 명령·exit·timeout: ../evidence/dead-code-20260909/pytest.json · vitest.json · lint.json
- 동적 명령: python3 docs/dev-cycle/evidence/dead-code-20260909/run_check.py probe (30초, exit0, 1.42초); 실제 격리 소스는 qa-source.json의 8487e7d과 일치.
- 동적 한도: 최대5회/동일실패3회; 실제1회. baseline 환경보완 실패는 scope 및 원문 로그에 별도 보존.

ULTRAQA COMPLETE: Goal met after 1 cycles
