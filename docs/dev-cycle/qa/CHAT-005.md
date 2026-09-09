# UltraQA Report

- 항목: CHAT-005 — 미사용 프롬프트/래퍼 제거 및 종료 재초기화 중단
- engine: ultraqa
- lifecycle: app-adapted
- phase: baseline-complete
- iteration: 0
- same_failure_count: 0
- baseline: pytest2279/3skip, Vitest462/67files(build·tsc 포함), lint0errors/198warnings; 모두 exit0
- base: 4757dc354d37598fe0f53dd182eb67c458a3f115
- browser_applicability: not-applicable
- browser_driver: none
- 판정 근거: evidence/dead-code-20260909/scope.md의 호출부 범위. UI/API/응답 변화 없음.
- required: 예
- cleanup: 대기
- 범위/안전/상한: ../evidence/dead-code-20260909/scope.md

## 시나리오 행렬

| ID | 의도/모델 | setup·명령 | 기대 | 실제 | 수정 | 증거 | cleanup | required |
|---|---|---|---|---|---|---|---|---|
| S-1 | 정상 종료 | 격리 Python 하네스: 가짜 client와 종목 맵 reload 실패 spy로 close 실행 | close 위임 1회, client None, reload 0회 | 미실행 | 없음 | 실행 후 기록 | 대기 | 예 |
| S-2 | 반복 종료/오염 데이터 | 격리 Python 하네스: 동일 객체 close 두 번; 종목명에 명령형 합성 문자열 | 예외/추가 I/O 없음, 명령 실행 없음 | 미실행 | 없음 | 실행 후 기록 | 대기 | 예 |
| S-3 | 인접 호환 계약 | 격리 Python 하네스: 가짜 GenerativeModel로 실제 _run_legacy_model_chat 실행 | 모델명/메시지 전달 및 합성 답변 보존 | 미실행 | 없음 | 실행 후 기록 | 대기 | 예 |

잘못된 JSON·웹 권한·취소 UI는 삭제 대상/종료 함수의 입력 계약에 없어 적용 불가. 반복 종료·자료 속 지시·dirty 보존·30초 timeout·실제 assert/종료코드를 검사한다.

## 실행 결과

- 필수 통과: 0/3
- 미통과 필수: S-1, S-2, S-3 미실행
- 완료 판정: 검증 대기
