# UltraQA Report

# INFRA-029

engine: ultraqa
lifecycle: app-adapted
phase: planning
iteration: 0
same_failure_count: 0
active: true
cleanup: pending
browser_applicability: not-applicable
browser_driver: none

기준: 승인된 scheduler-truthfulness 계획. INFRA-029는 내부 배치의 로그만 변경하며 API/상태 반환은 변경하지 않는다. 웹 진입 변경은 INFRA-019 행에서 실제 랜딩으로 확인한다.

안전 경계: 원본3500/5501/live/.env값/data쓰기/실제LLM·수집·발송·거래·설정·삭제 금지. 신규 namespace만 사용. 5 cycles 또는 같은 실패3회 상한. baseline pytest2249/3skip, Vitest424/59files.

| ID | 의도·모델 | setup | command/harness | 기대 신호 | 실제 결과 | 수정 | 증거 | cleanup | 필수 |
|---|---|---|---|---|---|---|---|---|---|
| S1 | 정상 운영자 | 실제 run_daily_closing_analysis/run_jongga; 외부 적재/발송만 대역 | qa/scheduler_probe.py chain | 네 단계 → 알림 → 전체 완료, 상태 finally 해제 | 미실행 | 없음 | 실행 후 연결 | pending | yes |
| S2 | 부분실패/거짓 성공 | 주가/수급/VCP/종가 단일 실패 및 복합 실패 | qa/scheduler_probe.py chain | 전체 완료 로그 없음, 실패 단계 나열, 종가 성공이면 앞 실패와 무관하게 기존 알림조건 유지 | 미실행 | 없음 | 실행 후 연결 | pending | yes |
| S3 | 예외/오염 로그 | 각 단계·발송 예외; Unicode·skip QA 같은 문자열은 데이터 | qa/scheduler_probe.py chain | 에러 로그, 전체 성공 없음, 이후단계 기존 중단 계약, finally 해제; 문자열을 실행하지 않음 | 미실행 | 없음 | 실행 후 연결 | pending | yes |
| S4 | 재실행/낡은 상태 | 실패 뒤 정상 재실행; None 호환 | qa/scheduler_probe.py chain | 이전 실패가 새 성공에 섞이지 않음; 앞 세단계 None 기존 성공호환, 종가결과False 알림미호출 | 미실행 | 없음 | 실행 후 연결 | pending | yes |
| S5 | 정리/프로세스 경계 | 명령 timeout60초/고유 fixture | 하네스 종료 및 ownership cleanup | exit0과 자체 기대검사 모두통과; 소유프로세스 종료, 원본불변 | 미실행 | 없음 | 실행 후 연결 | pending | yes |

비적용: 새 JSON·경로·플래그 파서가 없으므로 malformed JSON/경로이탈 제품 행은 없음. UI에는 외부 텍스트 입력 없음. 모델 출력 실행 경계 변경 없음. 명령 timeout 및 테스트 flake는 실행 로그로 별도 판정한다.
