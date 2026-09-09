# CODE REVIEW REPORT — FE-041 Task 5

**기준:** `c5f0ce9`

**입력:** `/var/folders/99/kpfx0mdj3fvbczqpbncjl0bm0000gn/T/closing-bet-notification-rounds-4s28gwie/041-input.json`

**Files Reviewed:** 5

**Total Issues:** 0

- CRITICAL: 0
- HIGH: 0
- MEDIUM: 0
- LOW: 0

## Stage 1 — Spec compliance

**PASS**

- `frontend/src/app/components/SettingsModal.tsx:277-303`은 알림 설정 저장이 HTTP 성공이고 JSON body의 `status`가 정확히 `ok`일 때만 notification send 요청으로 진행한다. 400/403/502, fetch 거부, JSON 파싱 실패, 거짓 성공 body는 모두 발송 전에 return한다.
- 저장 실패는 `frontend/src/app/components/SettingsModal.tsx:294-302`에서 「설정 저장 실패」로 표시하고 발송 실패는 `:320-344`에서 「발송 실패」로 구분한다.
- 발송 성공은 `frontend/src/app/components/SettingsModal.tsx:315-327`에서 HTTP 성공과 body `status: success`를 동시에 요구한다. HTTP 200이어도 error status이면 실패다.
- 안쪽 저장 catch의 return도 바깥 `finally`를 지나 `frontend/src/app/components/SettingsModal.tsx:345-347`에서 `isTesting`을 해제한다.
- `frontend/src/app/api/system/env/route.ts:42-67`은 인증된 upstream fetch와 `response.text()`를 같은 try 경계에 두고 둘 중 하나가 실패하면 값·예외 원문 없는 고정 JSON 502와 `Cache-Control: no-store`를 반환한다.
- `frontend/src/app/api/system/env/route.ts:37-46`의 admin token 판정은 upstream try 앞에 있어 익명·비관리자·토큰 미설정 요청이 fetch를 시작하지 않는다.
- 정상 upstream 응답은 status와 body를 그대로 전달하고 no-store를 유지한다. GET/POST method와 POST body 전달도 기존 계약과 같다.

## Root-cause guard

**PASS**

저장 실패 뒤에도 무조건 발송하던 순차 흐름을 저장 응답 검증 경계에서 직접 중단한다. 성공처럼 보이는 fallback body, 재시도, 대체 upstream 또는 오류 삼키기 분기가 없다. upstream 실패도 예외 원문을 우회 전달하지 않고 route boundary에서 고정 502로 닫는다.

## Stage 2 — Security, quality, performance, maintainability

**PASS**

- 설정 저장 실패에서는 upstream body의 message·rejected 값·예외를 UI나 console에 출력하지 않는다.
- 발송 응답은 object와 string message 여부를 확인한 뒤 React text로 표시하며, 비정상 JSON은 고정 실패 문구로 처리한다.
- 인증 실패 응답과 upstream 실패 응답 모두 no-store다. 성공/검증 실패 upstream 응답도 proxy가 no-store로 다시 만든다.
- 실패한 저장에서 notification transport 요청이 0회이므로 잘못된 자격 증명이나 이전 설정으로 외부 발송하는 부수효과가 사라진다.
- 추가 network roundtrip, retry, cache 또는 병렬 요청이 없다. 저장과 발송은 승인된 순서대로 한 번씩만 실행된다.
- 두 한정된 `unknown` guard와 한 route try만 추가했으며 dependency, schema validator, hook, 상태 머신이 없다.
- 설치된 Next 16.3.4 번들 문서 `15-route-handlers.md`와 `07-mutating-data.md`를 확인했다. POST route의 요청 시 실행, 인증, 비캐시 응답 계약과 일치한다.

## Test coverage

- `frontend/src/app/components/SettingsModal.notification.test.tsx:45-83`은 저장 HTTP 400/403/502, 저장 network 실패, body error/invalid JSON, 실제 저장 완료 전 send 0회, 성공 순서, 발송 502/503/200-error를 검증한다.
- `frontend/src/app/api/system/env/route.test.ts:62-100`은 GET/POST fetch 거부, body stream read 실패, upstream 400 body/status 전달, 익명 fetch 0회를 검증한다.
- 기존 `resolveAdminToken` 네 검사가 세션 없음, 비관리자, 관리자, token 없음 경계를 계속 고정한다.

## Validation

- `041-input.json`의 5개 SHA-256이 현재 checkout과 모두 일치했다.
- 상위 실행 증거: 대상 회귀 **26 passed**, 전체 pytest **2220 passed / 3 skipped**, Vitest **58 files / 389 passed**, typecheck exit 0, lint exit 0(**0 errors / 기존 204 warnings**).
- `git diff --check c5f0ce9` 통과.
- 확정된 MCP `Transport closed` 상태 때문에 LSP/ast-grep을 재시도하지 않았고 통과로 기록하지 않는다. TypeScript typecheck와 Vitest가 대체 증거다.
- 제품 코드·테스트를 수정하지 않았으며 실제 `.env`, `data`, `logs`, HTTP, 외부 발송, 설정 쓰기·삭제, 운영 서비스에 접근하지 않았다.

## Confidence

**높음 (0.98).** 저장 취소·순서·응답 검증·upstream 오류·인가 경계가 모두 실행 테스트로 덮였고 typecheck도 통과했다. 낮은 확신도의 추가 finding은 없다.

## Recommendation

**code-reviewer: APPROVE**

Task 5의 명세·보안·품질·성능·유지보수 관점에 미해결 이슈가 없다. 아키텍처 판정은 별도 레인 소관이다.
