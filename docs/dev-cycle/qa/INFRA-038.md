# UltraQA Report

- item: INFRA-038
- engine: ultraqa
- lifecycle: app-adapted
- phase: qa-ready
- iteration: 1
- same_failure_count: 0
- active: true
- cleanup: pending
- browser_applicability: required
- browser_driver: agent-browser
- namespace: devcycle-errors-k6-l42b8
- source: 54078ca 이후 해당 범위의 첫 구현 커밋으로 고정 예정

실제 Next UI·proxy와 실제 Flask factory/오류 처리기를 사용한다. 기동 스케줄러/원본 자료 접근·외부 LLM·발송은 차단하고 fake env/계정 및 비대상 조회 fixture를 쓴다. 원본3500/5501/live 접근 금지.

| ID | 의도·사용자/공격자 | setup·명령/하네스 | 기대 신호 | 실제 결과 | 수정 | 증거 | cleanup | 필수 |
|---|---|---|---|---|---|---|---|---|
| N1 | 사용자/공격자: 관리자 설정 모달 열기 | 격리 factory/Next + agent-browser 또는 명시된 pytest | env GET200, 기존 마스킹 | 미실행 | 없음 | 실행 후 연결 | pending | 필수 |
| A1 | 사용자/공격자: env 읽기 경계 OSError 주입 후 모달 재진입 | 격리 factory/Next + agent-browser 또는 명시된 pytest | GET500 고정오류, UI에 내부경로 없음 | 미실행 | 없음 | 실행 후 연결 | pending | 필수 |
| A2 | 사용자/공격자: 일반 미처리 예외에 경로/지시문 canary 주입 | 격리 factory/Next + agent-browser 또는 명시된 pytest | 500 고정오류, 예외종류/원문 비노출, 내부 로그는 원인 유지 | 미실행 | 없음 | 실행 후 연결 | pending | 필수 |
| A3 | 사용자/공격자: 장애 해제 후 설정 모달 재진입, 비관리자 확인 | 격리 factory/Next + agent-browser 또는 명시된 pytest | 정상200복구, 비관리자403/관리자탭 없음 | 미실행 | 없음 | 실행 후 연결 | pending | 필수 |

정상 baseline: pytest 전체·Vitest 전체(실제 build 포함). malformed/특이경로, 오류문구 지시문은 비신뢰 데이터로만 취급. dirty root package.json SHA 불변, 타임아웃480초/브라우저60초, 모든 exit 확인. 소유 프로세스 종료와 임시자료 삭제가 완료 조건이다. 중단 최대5회·동일실패3회. 제품에 resume/cancel 작업상태 API가 없으므로 그 분류는 비적용; 작업 재개 증거는 본 문서와 입력 해시로 대조한다.

## 정적·리뷰 증거

pytest baseline2220/3skip → 최종2232/3skip. Vitest405/58files(실제build 포함), frontend 변경없어 같은 검증 재사용. typecheck0,lint0errors/204existingwarnings. 증거: ../evidence/http-errors-2026-09-09/. ponytail/code-review APPROVE, architect v1 BLOCK → wrapper HTTPException 재발생 및400/415 회귀2건 → v2 CLEAR. LSP Transport closed로 미실행, AST/실제실행검증은 통과.

INFRA017 A3에 실제 log-event wrapper malformedJSON400/form415, customHTTP response 본문/임의헤더 보존 probe를 포함한다. 038 A2는 실제 data-status 화면 조회에 미처리 예외를 주입한다. 행렬 구체화만 추가되었고 승인 요구사항/검토한 제품4파일은 그대로다.
