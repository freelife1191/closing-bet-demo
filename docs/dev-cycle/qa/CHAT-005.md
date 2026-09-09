# UltraQA Report

- 항목: CHAT-005 — 미사용 프롬프트/래퍼 제거 및 종료 재초기화 중단
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
| S-1 | 정상 종료 | 격리 Python 하네스: 가짜 client와 종목 맵 reload 실패 spy로 close 실행 | close 위임 1회, client None, reload 0회 | 통과: close 위임1회/client=None/reload0회 | 없음 | ../evidence/dead-code-20260909/probe.log.gz · cleanup.json | 완료 | 예 |
| S-2 | 반복 종료/오염 데이터 | 격리 Python 하네스: 동일 객체 close 두 번; 종목명에 명령형 합성 문자열 | 예외/추가 I/O 없음, 명령 실행 없음 | 통과: close2회 예외없음/reload0회/합성문자열 그대로 | 없음 | ../evidence/dead-code-20260909/probe.log.gz · cleanup.json | 완료 | 예 |
| S-3 | 인접 호환 계약 | 격리 Python 하네스: 가짜 GenerativeModel로 실제 _run_legacy_model_chat 실행 | 모델명/메시지 전달 및 합성 답변 보존 | 통과: test-model 및 합성메시지 전달/합성호환답변 일치, 삭제표면 없음 | 없음 | ../evidence/dead-code-20260909/probe.log.gz · cleanup.json | 완료 | 예 |

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
