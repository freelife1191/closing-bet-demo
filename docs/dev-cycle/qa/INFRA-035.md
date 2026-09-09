# UltraQA Report — INFRA-035

- QA 엔진(engine): Codex UltraQA
- lifecycle: app-adapted | phase: planning | iteration: 0 | same_failure_count: 0
- baseline: pytest 2279/3 skip, Vitest 459/67, Node build 3/0 skip, tsc 0, lint 0 errors/194 warnings 통과. 검증 소스 해시: ../evidence/test-isolation-20260909/review-input.json
- browser_applicability: not-applicable | browser_driver: none
- 호출부 근거: 수정은 npm/Node 검증 명령과 pytest DB fixture만 사용. 제품 UI·API·저장 계약 변경 없음.
- UltraQA Report: [묶음 범위 및 증거](../evidence/test-isolation-20260909/scope.md)
- 안전: 원본3500/5501/라이브·.env·data 쓰기 금지. 비밀 없는 scratch와 네트워크 차단 sandbox 사용.
- 목표: 기본 테스트와 빌드의 충돌 제거, 빌드/타입 검증 보존, 테스트 DB의 원본 경로 쓰기 방지.
- 중단: 같은 실패3회/최대5cycle. 명령 timeout60~300초, 소유 프로세스만 정리.

## 필수 행렬

| ID | 의도·사용자/공격자 | setup·명령 | 기대 신호 | 실제·결과 | 수정·증거 | cleanup |
|---|---|---|---|---|---|---|
| S-1 | 정상 개발자, 인접 회귀 | npm run test:build | 실제 빌드1회, 필수5경로, 타입 검사, Node3검사 exit0 | 미실행 | build.log | scratch 삭제 |
| S-2 | 동시 작업/반복 실행 | 같은 scratch에서 npm run test:build와 npx vitest run 동시 실행2회 | 빌드3검사와 Vitest459개 각각exit0, 중복빌드 충돌 없음 | 미실행 | concurrent 로그 | 소유 프로세스 종료 |
| S-3 | 성공문구로 위장한 실패 | 임시 npm 대역이 성공문구 출력 후exit7, 실제 Node검증 실행 | 검증exit비0, 성공으로 오인 안함 | 미실행 | misleading.log | 대역 삭제 |
| S-4 | DB 쓰기 경로 회귀 | scratch data 쓰기 차단 상태에서 pytest tests/services/test_paper_trading_service.py | 86개 통과, data DB/WAL/SHM 생성0 | 미실행 | target.log | 임시 DB 정리 |
| S-5 | dirty 원본/정리 | 원본 사용자package 해시·data WAL/SHM 이름해시 전후 대조, scratch프로세스 검사 | 불변, 소유프로세스0, scratch 제거 | 미실행 | cleanup.json | 완료 필요 |

모든 행 required=예. CLI에 사용자 JSON/프롬프트/권한상태 입력을 받는 경로가 없어 해당 적대적 분류는 적용 불가.
기존 data 누적 파일 삭제는 INFRA-035의 별도 미결 항목으로 보존하며 이번 검증 성공으로 삭제 결정을 대체하지 않음.

## 실행 결과

- 필수 통과: 0/5. 결과 미실행. cleanup 대기.
