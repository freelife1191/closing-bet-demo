# CODE REVIEW REPORT — INFRA-051 Task 4

**기준:** `6147150`

**입력:** `/var/folders/99/kpfx0mdj3fvbczqpbncjl0bm0000gn/T/closing-bet-notification-rounds-4s28gwie/051-input.json`

**Files Reviewed:** 6

**Total Issues:** 0

- CRITICAL: 0
- HIGH: 0
- MEDIUM: 0
- LOW: 0

## Stage 1 — Spec compliance

**PASS**

- `services/common_env_service.py:201-226`은 `applied`, `removed`, `preserved`, `rejected` 네 필드를 항상 반환하고, 거부 사유를 `unsupported_key`, `invalid_type`, `unsafe_value`로 고정한다. 입력 값은 결과에 포함하지 않는다.
- mixed 요청은 거부값을 제외한 문자열 입력을 계속 처리한다. `services/common_env_service.py:228-319`의 기존 잠금·원자 쓰기·성공 후 environ 적용 순서를 유지하면서 실제 적용·삭제·마스킹 보존 키를 수집한다.
- 결과 목록은 정렬되고 `removed`는 중복 제거되어 파일 줄이나 요청 순서에 의존하지 않는 안정된 계약이다.
- `app/routes/common_update_routes.py:248-264`은 JSON object만 받아 malformed JSON 400, non-JSON 415, 비객체 400, rejected 포함 결과 400, 순수 성공 200으로 구분한다. 정상값 일부 반영이 있어도 전체 롤백으로 주장하지 않고 응답 문구에 accepted settings 저장을 명시한다.
- service I/O 예외는 `app/routes/common_update_routes.py:256-260`에서 예외 타입만 로그에 남기고 고정 body 500을 반환한다.
- `frontend/src/app/components/SettingsModal.tsx:164-183`은 일반 저장 요청이 실패하면 응답의 `rejected`가 plain object일 때 키만 추출한다. 값과 내부 사유는 화면에 표시하지 않으며 JSON이 아니거나 구조가 다르면 기존 `API 설정` 실패로 안전하게 퇴화한다.
- `frontend/src/app/components/SettingsModal.tsx:186-202`는 프로필/API/관심종목 저장의 기존 격리를 유지하고 부분 실패 모달에 실패 대상만 추가한다.
- FE-041의 `handleTestNotification` 저장 성공 확인은 Task 5로 명시된 후속 범위다. 이번 일반 Save 계약의 누락으로 분류하지 않는다.

## Root-cause guard

**PASS**

거부를 조용히 버리던 공통 service가 실제 처리 결과를 반환하고 route와 UI가 같은 결과를 전달한다. 실패를 성공으로 바꾸는 fallback, 별도 저장 경로, 예외 삼키기 또는 전체 롤백 위장은 추가되지 않았다.

## Stage 2 — Security, quality, performance, maintainability

**PASS**

- API 결과와 로그에는 설정 값, 예외 원문, 거부된 값이 없다. 거부 키는 관리자 요청 JSON의 key이며 React가 text로 escape해 표시한다.
- 비문자 값은 정규식 검사 전에 명시적으로 거부되어 `str(value)` 변환으로 구조화된 JSON이 설정 문자열로 저장되지 않는다.
- unsupported key는 기존 editable allowlist 밖에서 거부되며 accepted map에 들어가지 않아 부분 반영 경계가 유지된다.
- 전체 입력과 최대 12개 editable 키에 대한 단일 순회·정렬만 추가된다. 파일 I/O 횟수, 잠금 범위, 원자 교체 횟수는 증가하지 않는다.
- backend는 단순 dict 결과를 사용하고 frontend는 한 번 쓰는 inline 구조 검사만 둔다. 새 dependency, schema runtime, 상태 hook, response wrapper가 없다.
- 설치된 Next 16.3.4 번들 문서 `06-fetching-data.md`, `07-mutating-data.md`와 대조했다. 기존 client component의 authenticated same-origin mutation 처리이며 새 Server Action/cache/revalidation 경계가 없다.

## Validation

- `051-input.json`의 6개 SHA-256이 현재 checkout과 모두 일치했다.
- 상위 실행 증거: backend 대상 **147 passed**, frontend 대상 **10 passed**, 전체 pytest **2220 passed / 3 skipped**, Vitest **57 files / 374 passed**, typecheck exit 0, lint exit 0(**0 errors / 기존 204 warnings**).
- `git diff --check 6147150` 통과.
- 확정된 MCP `Transport closed` 상태 때문에 LSP/ast-grep을 재시도하지 않았고 통과로 기록하지 않는다. TypeScript는 별도 typecheck, Python은 전체 pytest 증거로 보완됐다.
- 제품 코드·테스트를 수정하지 않았으며 실제 `.env`, `data`, `logs`, HTTP, 외부 발송, 설정 쓰기·삭제, 운영 서비스에 접근하지 않았다.

## Confidence

**높음 (0.97).** service·route·UI의 성공, 부분 거부, 입력 오류, I/O 실패 계약이 실행 테스트로 연결되어 있다. 낮은 확신도의 추가 finding은 없다.

## Recommendation

**code-reviewer: APPROVE**

Task 4의 명세·보안·품질·성능·유지보수 관점에 미해결 이슈가 없다. 아키텍처 판정은 별도 레인 소관이다.
