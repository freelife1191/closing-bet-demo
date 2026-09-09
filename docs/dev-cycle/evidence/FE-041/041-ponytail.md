# FE-041 Task 5 — ponytail review

**기준:** `c5f0ce9`

**입력:** `/var/folders/99/kpfx0mdj3fvbczqpbncjl0bm0000gn/T/closing-bet-notification-rounds-4s28gwie/041-input.json`

**입력 무결성:** SettingsModal, Next env route, 두 회귀 파일, 계획의 SHA-256 5개가 현재 checkout과 모두 일치했다.

## 판정

**APPROVE — 과잉설계 이슈 0건**

## 근거

- `frontend/src/app/components/SettingsModal.tsx:277-316`의 안쪽 저장 `try`는 HTTP·JSON·body status 실패를 같은 「설정 저장 실패」로 묶고 발송 전에 return한다. 바깥 `try/finally`는 발송 실패를 별도로 표시하면서 모든 반환 경로에서 `isTesting`을 해제한다. 두 catch를 합치면 실패 단계 구분이나 조기 발송 차단 중 하나를 잃으므로 필요한 구조다.
- 저장 응답과 발송 응답은 `unknown`으로 받은 뒤 필요한 `status` 필드만 inline 검사한다. 각 형식은 한 호출에서만 쓰이고 검증도 짧아 interface, schema dependency, type guard helper를 추가하지 않은 것이 더 작다.
- 발송 실패 문구는 기존 `testModal` 상태를 재사용하고, 원격 `message`가 문자열일 때만 표시한다. 새 상태 머신, reducer, mutation hook이 없다.
- `frontend/src/app/api/system/env/route.ts:42-67`은 기존 proxy의 fetch와 `response.text()`를 한 try로 감싸 고정 502/no-store를 반환한다. retry, fallback upstream, 별도 error class 또는 response adapter가 없다.
- `frontend/src/app/components/SettingsModal.notification.test.tsx:45-83`은 HTTP 저장 실패 세 상태, 네트워크, 거짓 성공 두 형태, 순서, 발송 실패 세 상태를 `it.each`와 두 응답 factory로 압축한다. 10개 실제 계약을 별도 fixture 계층 없이 검증한다.
- `frontend/src/app/api/system/env/route.test.ts:62-100`은 GET/POST fetch 실패를 매개변수화하고 body read 실패, 상태 전달, 익명 upstream 0회를 각각 한 번 검증한다. 기존 auth 테스트를 재사용한다.

## Frontend guidance

저장소 매핑에 따라 설치된 Next 16.3.4 번들 문서 `15-route-handlers.md`와 앞서 읽은 `07-mutating-data.md`를 대조했다. GET/POST route는 기본 비캐시 동작 위에 명시적 `no-store` 응답을 유지하고, 인증 뒤 서버 전용 upstream으로 전달하는 기존 경계를 바꾸지 않는다.

## Validation

- RED **10 failed / 9 passed**에서 대상 회귀 **26 passed**로 전환된 상위 증거를 확인했다.
- 전체 pytest, Vitest, lint는 상위 레인에서 진행 중이며 이 검토에서 반복하지 않았다.
- `git diff --check c5f0ce9` 통과.
- 확정된 MCP `Transport closed` 상태 때문에 진단 도구를 재시도하지 않았다.
- 제품 코드·테스트를 수정하지 않았고 실제 `.env`, `data`, `logs`, HTTP, 외부 발송, 설정 쓰기·삭제, 운영 서비스에 접근하지 않았다.

## Recommendation

**APPROVE**

두 단계 부수효과와 오류 종류를 구분하는 데 필요한 최소 control flow만 추가했으며 제거하거나 합칠 불필요한 구조가 없다.
