## Summary

CHAT-013/CHAT-015/FE-038 범위는 현재 구현과 요구사항이 일치하며 Architect 판정은 `CLEAR`입니다. 요청 token·mounted guard·session ownership을 결합해 중복 전송, 중단/언마운트 후 늦은 delta·JSON·오류·finally 적용을 차단하고, 신규 세션 자동 배정은 유지합니다. Parser 제목 보존/추천 제한과 Sidebar·ChatWidget의 공용 브라우저 세션 헤더 사용도 지정 범위와 맞습니다.

## Analysis

- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/chatbot/useChatStream.ts:80-105`
  - `isMountedRef`, `isSendingRef`, `requestTokenRef`, `activeSessionRef`, `streamSessionRef`가 요청 수명과 표시 세션을 분리해 소유합니다.
  - `invalidateRequest`는 token 증가, sending 해제, AbortController abort, loading 해제를 한 경로에서 수행합니다.
  - 중단 메시지를 추가할 때 현재 마지막 message가 streaming인 경우 먼저 `isStreaming=false`로 종료합니다.

- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/chatbot/useChatStream.ts:108-185`
  - `isSendingRef`를 동기 전송 guard로 사용해 React state 반영 전 두 번째 전송을 차단합니다.
  - 매 요청은 증가된 request token을 캡처하고, 이후 모든 결과 적용이 `isCurrentRequest()`를 통과해야 합니다.
  - unmount cleanup은 token 무효화와 abort를 수행해 진행 요청이 이후 UI를 만지지 못하게 합니다.

- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/chatbot/useChatStream.ts:224-317`
  - headers 도착, reader read 전후, chunk 적용, final message, JSON response, error, finally 모두 request token과 visible session 검사를 거칩니다.
  - 정상 응답은 token이 유효한 동안 그대로 커밋되고, `finally`에서만 sending/loading/ref를 정리합니다.
  - 무효화된 요청의 `finally`는 state/ref 정리를 수행하지 않아 새 요청 세대의 상태를 덮지 않습니다.
  - AbortError는 일반 오류 메시지를 만들지 않고 종료합니다.

- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/chatbot/useChatStream.ts:118-159,264-282`
  - `streamSessionRef`는 요청이 시작된 세션을 기억합니다.
  - 새 세션으로 전환되면 effect가 이전 요청을 무효화합니다.
  - 신규 세션에서 서버가 session id를 처음 배정하는 경우에는 `activeSessionRef`가 null인 상태를 허용하고, `onSessionAssigned`를 통해 같은 스트림으로 계속 진행합니다.
  - 기존 세션 A에서 B로 바뀐 뒤 A의 후속 chunk/session id가 오면 ownership 검사가 실패해 무효화됩니다.

- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/chatbot/useChatStream.regression-chat-013.test.tsx`
  - SSE 전체 동안 loading 유지, 동시 두 번째 전송 차단, 중단 메시지와 streaming 종료를 검증합니다.
  - 세션 전환 후 늦은 delta 차단, 신규 세션 배정 후 계속 읽기, unmount abort를 검증합니다.
  - 즉시 JSON과 종료 SSE의 마지막 delta가 `finally` 이후에도 보존되는 정상 경로를 검증합니다.

- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/chatbot/page.regression-chat-001.test.tsx`
  - 기존 새 세션 회귀 검사가 남은 chunk를 억지로 소비하지 않고, 세션 전환 후 선택된 세션 기록과 localStorage가 유지되는지 확인하도록 보강되었습니다.

- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/chatbot/chatMessageParser.ts:40-48,121-184`
  - dense numbered list 분리는 heading 줄을 건너뛰어 `### 1. 제목`을 보존합니다.
  - content와 reasoning 양쪽에 같은 분리 규칙을 적용합니다.
  - 추천 질문은 순서 유지, 최대 3개, 각 120 Unicode code point로 제한됩니다.
  - `Array.from`을 사용해 surrogate pair/이모지를 code point 단위로 자릅니다.

- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/components/ChatWidget.tsx:230-245`
  - 자체 `getBrowserSessionId` 생성을 제거하고 `getAuthHeaders()`를 재사용합니다.
  - 위젯 chatbot POST가 공용 브라우저 세션 헤더 계약을 사용합니다.

- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/components/Sidebar.tsx:7-12,112-129`
  - 프로필 저장 감사 요청도 동일한 `getAuthHeaders()`를 사용합니다.
  - FE-038의 widget/profile/log-event 세 요청이 같은 browser session id를 유지합니다.

- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/components/sessionHeaders.regression-fe-038.test.tsx`
  - 위젯 전송과 Sidebar profile/log-event 요청의 `X-Session-Id` 일치, `Content-Type`, 금지된 `X-User-Email` 부재를 검증합니다.

- 제공된 baseline:
  - pytest 2281 passed, 2 skipped
  - Vitest 460 passed
  - typecheck exit 0
  - lint 0 errors, 198 warnings
  - source hashes match

## Root Cause

기존 결함은 요청 생명주기를 `isLoading` state와 단일 abort ref에 의존해, React state 반영 전 중복 전송과 세션 전환 후 이전 응답의 state setter 적용을 막지 못한 점입니다. 현재 변경은 요청 token과 session ownership을 모든 async 경계에 적용해 각 응답이 어느 요청·세션에 속하는지 판정한 뒤 커밋합니다.

Parser 결함은 dense numbered list 분리가 heading 줄까지 일반 본문처럼 처리하고, 추천 질문 개수/길이 제한이 없었던 점입니다. 현재는 heading 보존과 Unicode-safe 제한을 parser 내부에서 일관되게 적용합니다.

FE-038 결함은 Sidebar와 ChatWidget이 공용 helper 대신 각자 browser session id를 만들던 점입니다. 현재 두 호출자가 `getAuthHeaders()`를 공유합니다.

## Strongest Counterargument

`reader.read()`가 실제 브라우저에서 abort 후 즉시 reject하지 않는 환경에서는 async 함수가 잠시 살아 있을 수 있다는 반론이 가능합니다. 그러나 reader 전후 모두 request token을 검사하고, unmount/session change 시 token을 먼저 무효화하므로 응답이 늦어도 UI/state/finally를 새 요청에 적용할 수 없습니다. 실제 네트워크 abort 자체까지 보장하는 계약은 아니지만, 요구된 stale response 차단 계약은 충족합니다.

또한 `streamOwnsVisibleSession()`이 `activeSessionRef === null`과 신규 서버 session id를 허용하는 것은 의도된 신규 세션 배정 예외입니다. 기존 세션 전환에는 이 예외가 적용되지 않습니다.

## Recommendations

1. `CLEAR`: 현재 CHAT-013/015/FE-038 구현은 승인된 범위와 회귀 테스트를 충족합니다.
2. AbortController의 transport-level 취소 여부를 별도로 보장하려면 fetch/reader adapter 계약을 확장해야 하며, 현재 범위에 추가할 필요는 없습니다.
3. lint warning 198건은 오류가 아니며 현재 범위의 blocker로 판단할 근거가 없습니다.

## Architectural Status

`CLEAR`

## File Hashes

- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/chatbot/chatMessageParser.test.ts`
  `2974a231dd7202cb17692a19c00ae7c917d671a6f0bd6a14bc3b5101012bbd9c`

- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/chatbot/chatMessageParser.ts`
  `76d8a3f379808f8c62fbb72fc2d9a228734ad8da1ad41bd32f2bc04034289b74`

- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/chatbot/page.regression-chat-001.test.tsx`
  `0f5e1877fac1815984c94e006e9344149933e7d8919b3750304594f2a86fc586`

- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/chatbot/useChatStream.ts`
  `18bef9c6cc62960c1bcb8f1d0d8195e181e233b7cfcc82d0c4c807b045a9f51b`

- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/components/ChatWidget.tsx`
  `30438033c19988f74f1bcacb56e803686a108974c8868ccfca05a9d3abddf92c`

- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/components/Sidebar.tsx`
  `1a920937315c5e97b6659faaa3ee643e7e7dc8a51537d58bb862802ac29401ec`

- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/chatbot/ChatMessage.regression-chat-015.test.tsx`
  `e9b4eba7bac63e35e806c04948ce7ef9c7118dcbbd73152c4492109715865a14`

- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/chatbot/useChatStream.regression-chat-013.test.tsx`
  `ca8ccddc747c5a12716f1c10e0e92b36be96b691ad3db369a96bc9149c20f2a8`

- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/components/sessionHeaders.regression-fe-038.test.tsx`
  `8295d9492f9c334d8c88879fe16f29eff6748d6661d3901e827c9127db1d6d7f`

## References

- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/docs/dev-cycle/evidence/chat-batch-20260909/review-input.json`
- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/docs/dev-cycle/evidence/chat-batch-20260909/scope.md`
- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/docs/dev-cycle/qa/CHAT-013.md`
- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/docs/dev-cycle/qa/CHAT-015.md`
- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/docs/dev-cycle/qa/FE-038.md`
- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/chatbot/useChatStream.ts:80-317`
- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/chatbot/chatMessageParser.ts:40-184`
- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/components/ChatWidget.tsx:230-245`
- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/components/Sidebar.tsx:112-129`
