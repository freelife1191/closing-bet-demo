# FE-041 v2 — PONYTAIL + CODE REVIEW DELTA

**기준:** `c5f0ce9`

**입력:** `/var/folders/99/kpfx0mdj3fvbczqpbncjl0bm0000gn/T/closing-bet-notification-rounds-4s28gwie/041-input-v2.json`

**입력 무결성:** SettingsModal, Next env route, 두 회귀 파일, 계획의 SHA-256 5개가 현재 checkout과 모두 일치했다.

## Ponytail delta

**APPROVE — 과잉설계 이슈 0건**

- 제품 변경은 `frontend/src/app/components/SettingsModal.tsx:298`의 실패 설명 한 줄뿐이다. 별도 상태나 분기 없이 기존 모달 문구가 “저장 실패”를 단정하지 않고 “확인 불가·부분 반영 가능”을 정확히 알린다.
- `frontend/src/app/components/SettingsModal.notification.test.tsx:68-76,106-125`은 JSON의 기본 여섯 형태를 동일한 표로 저장·발송 양쪽에 적용하고, button 활성 상태도 같은 loop로 확인한다. 타입별 테스트 본문을 복제하지 않는다.
- 실패 후 재시도 검사는 기존 `saveReply`, `sendReply`, `calls` fixture를 그대로 사용한다. retry helper, fake state machine, 새 render harness가 없다.
- `frontend/src/app/api/system/env/route.test.ts:67-84`는 GET/POST를 `it.each`로 공유하며 fetch와 upstream response body-read 실패를 같은 고정 502 계약으로 검증한다.
- 테스트 증가는 architecture WATCH에서 지적한 경계인 unknown JSON, 재활성화·재시도, POST body-read를 직접 메운다. 구현 문구나 내부 함수 호출 횟수만 복제하는 테스트가 아니다.

## Code review delta

**Total Issues: 0**

- CRITICAL: 0
- HIGH: 0
- MEDIUM: 0
- LOW: 0

### Stage 1 — Spec compliance

**PASS**

- 저장 실패 문구는 HTTP 400의 부분 반영 계약과 일치한다. 저장 완료를 확인하지 못해 발송은 중단하지만 일부 정상 설정은 이미 반영됐을 수 있음을 사용자에게 알린다.
- null, number, boolean, string, array, 빈 object 저장 응답은 모두 `status: ok`가 아니므로 발송 전에 차단된다. 같은 여섯 발송 응답은 `status: success`가 아니므로 성공으로 표시되지 않는다.
- 저장 실패와 발송 network/JSON 실패 뒤에도 `finally`가 버튼을 다시 활성화하며, 저장을 수정한 두 번째 시도는 `save → save → send` 순서로 정상 진행한다.
- Next route의 동일 제품 코드는 GET·POST fetch 실패뿐 아니라 두 method의 upstream `response.text()` 실패도 고정 JSON 502/no-store로 처리함이 검증됐다.
- incoming `Request.text()` 실패는 이번 승인 계약이 아니며, POST upstream 응답 body-read 경계를 정확히 보강했다.

### Root-cause, security, quality

**PASS**

- unknown 응답을 성공으로 간주하는 fallback이 없다. 필요한 status가 없으면 fail closed다.
- 실패 뒤 UI가 영구 disabled 상태로 남는 workaround 없이 기존 `finally` 계약을 직접 검증한다.
- network/invalid JSON canary가 UI에 노출되지 않는다. route 502 body도 고정 객체로 정확히 대조한다.
- 제품 control flow, fetch 횟수, 인증 경계, 캐시 정책은 v1과 동일하다. 새 성능·유지보수 위험이 없다.

## Validation

- `041-input-v2.json`의 5개 SHA-256이 현재 checkout과 일치했다.
- v2 대상 회귀 **42 passed**(UI 25 + route 10 + 기존 7).
- backend는 변경되지 않았고 전체 pytest **2220 passed / 3 skipped** 증거가 유지된다.
- `git diff --check c5f0ce9` 통과.
- v2 전체 Vitest와 lint는 상위 레인에서 진행 중이다. 완료 결과를 받기 전에 통과로 기록하지 않는다. v1 기준은 Vitest **58 files / 389 passed**, typecheck exit 0, lint **0 errors / 기존 204 warnings**였다.
- 확정된 MCP `Transport closed` 상태 때문에 LSP/ast-grep을 재시도하지 않았다.
- 제품 코드·테스트를 수정하지 않았으며 실제 `.env`, `data`, `logs`, HTTP, 외부 발송, 설정 쓰기·삭제, 운영 서비스에 접근하지 않았다.

## Confidence

**높음 (0.97).** 제품 로직은 v1과 같고 새 회귀가 WATCH 공백을 직접 보강했다. v2 전체 frontend 정적 실행 결과만 상위 게이트에서 확인해야 한다.

## Recommendation

**code-reviewer: APPROVE**

v1 코드 판정을 유지한다. v2 제한 범위에 새 이슈가 없다. 전체 완료 판정은 진행 중인 v2 frontend 검증과 별도 아키텍처 레인이 합쳐서 내린다.
