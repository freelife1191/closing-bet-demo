# INFRA-051 Task 4 — ponytail review

**기준:** `6147150`

**입력:** `/var/folders/99/kpfx0mdj3fvbczqpbncjl0bm0000gn/T/closing-bet-notification-rounds-4s28gwie/051-input.json`

**입력 무결성:** backend 서비스·route·테스트, frontend 컴포넌트·테스트, 계획의 SHA-256 6개가 현재 checkout과 모두 일치했다.

## 판정

**APPROVE — 과잉설계 이슈 0건**

## 근거

- `services/common_env_service.py:201-226`은 기존 필터 comprehension을 한 번의 명시적 loop로 풀어 `accepted`와 세 고정 거부 사유를 동시에 수집한다. 부분 반영과 거부 보고를 함께 만족하려면 필요한 최소 상태이며 validator class나 결과 객체를 새로 만들지 않았다.
- 결과는 `applied`, `removed`, `preserved`, `rejected` 네 필드뿐이다. `services/common_env_service.py:231-284`의 기존 `applied`·`removed` 상태를 그대로 사용하고, 마스킹 보존 보고에만 `preserved` set을 추가한다.
- `services/common_env_service.py:315-319`의 정렬은 최대 12개 editable 키를 파일 줄·요청 순서와 무관하게 결정적으로 보고한다. `removed`의 set 변환은 중복 기존 줄에서도 같은 키를 한 번만 반환하므로 별도 정규화 helper보다 작다.
- `app/routes/common_update_routes.py:248-264`는 기존 route 안에서 JSON 타입, service 결과, I/O 예외를 바로 HTTP 계약으로 옮긴다. 공용 `_execute_update_route`는 다른 endpoint에서 예외 원문을 쓰므로 이를 확장하거나 새 response class를 도입하지 않고 env POST만 고정 오류문으로 좁힌 선택이 적절하다.
- `frontend/src/app/components/SettingsModal.tsx:148-202`는 기존 `failed` 배열과 결과 모달을 재사용한다. 실패 응답에서 `rejected`가 plain object인지 확인해 키만 기존 실패 문자열에 넣으며 새 state, hook, schema library 또는 response adapter를 만들지 않았다.
- inline 응답 확인은 한 호출에서만 쓰이고 짧다. 이를 위해 interface/helper를 추가하면 현재보다 코드 경계와 이름만 늘어난다.
- backend 회귀는 부분 반영, 잘못된 body, rejected 유형, 빈 요청, malformed/non-JSON, I/O 실패, 삭제·마스킹 결과라는 실제 분기를 한 파일에서 검증한다. frontend는 기존 저장 격리 테스트에 거부 키 표시 사례 하나만 추가했다.
- FE-041의 테스트 발송 전 저장 확인은 `handleTestNotification`의 별도 흐름이며 아직 구현하지 않았다. Task 4에서 미리 공통 mutation 계층으로 합치지 않은 것이 승인된 라운드 분리와 YAGNI에 맞는다.

## Frontend guidance

저장소 매핑에 따라 설치된 Next 16.3.4 번들 문서 `06-fetching-data.md`와 `07-mutating-data.md`를 확인했다. 변경은 기존 client component의 인증된 same-origin POST 처리와 UI 오류 표시에 머물며 Server Action, cache, revalidation 또는 새 server/client 경계를 도입하지 않는다.

## Validation

- RED backend **9 failed / 2 passed**, frontend **1 failed / 3 passed**에서 대상 backend **147 passed**, frontend **10 passed**로 전환된 상위 증거를 확인했다.
- 상위 정적 검증은 전체 pytest **2220 passed / 3 skipped**, Vitest **57 files / 374 passed**, typecheck exit 0, lint exit 0(**0 errors / 기존 204 warnings**)로 완료됐다. 이 레인에서 반복하지 않았다.
- `git diff --check 6147150` 통과.
- 확정된 MCP `Transport closed` 상태 때문에 진단 도구를 재시도하지 않았다.
- 제품 코드·테스트를 수정하지 않았고 실제 `.env`, `data`, `logs`, HTTP, 외부 발송, 설정 쓰기·삭제, 운영 서비스에 접근하지 않았다.

## Recommendation

**APPROVE**

현재 함수·route·UI 상태를 재사용해 승인된 결과 계약만 추가했으며 제거하거나 합칠 불필요한 구조가 없다.
