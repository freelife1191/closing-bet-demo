## Summary

이번 QA2 두 파일 수정은 `CLEAR`입니다. `quota-updated`를 SSE `done` 프레임이 아니라 현재 요청의 실제 종료 뒤 한 번 발행하므로, 서버 차감 확정 전 조회 경합을 피하면서 Sidebar를 즉시 갱신합니다. CHAT-008·009 전체의 기존 비차단 `WATCH`는 유지합니다.

## Analysis

- 서버는 마지막 SSE 프레임을 내보낸 뒤 생성기의 `finally`에서 쿼터 후처리를 실행합니다. 따라서 클라이언트가 `done` 프레임에서 바로 조회하면 차감 전 값을 읽을 수 있지만, body EOF 뒤에는 서버 후처리가 끝난 상태입니다. `services/kr_market_chatbot_stream_helpers.py:69-94`
- 새 이벤트는 reader가 EOF를 반환해 스트림 루프를 빠져나온 뒤 `finally`에서 발행됩니다. 프레임 처리 중 `data.done`은 세션 목록만 갱신하며 쿼터 이벤트를 보내지 않습니다. `frontend/src/app/chatbot/useChatStream.ts:243-284`, `frontend/src/app/chatbot/useChatStream.ts:338-349`
- 중단·언마운트·세션 전환은 요청 토큰을 증가시킵니다. `finally`의 `isCurrentRequest()` 가드 때문에 무효화된 요청이 뒤늦게 Sidebar 쿼터를 갱신하지 않습니다. `frontend/src/app/chatbot/useChatStream.ts:88-128`, `frontend/src/app/chatbot/useChatStream.ts:162-176`, `frontend/src/app/chatbot/useChatStream.ts:338-349`
- 회귀 검사는 `done` 전달 시 이벤트 0회, EOF 뒤 정확히 1회를 확인합니다. 이벤트 리스너도 `finally`에서 제거해 검사 간 누수를 막습니다. `frontend/src/app/chatbot/useChatStream.regression-chat-013.test.tsx:162-176`
- 두 파일 SHA는 manifest와 격리 사본에서 일치합니다. `docs/dev-cycle/evidence/slash-batch-20260909/review-input.json:16-17`, `docs/dev-cycle/evidence/slash-batch-20260909/review-input.json:37-45`
- RED는 신규 검사 1실패·기존 6통과였고, 수정 후 전체 Vitest는 67파일·461검사 통과했습니다. typecheck exit 0, lint 0 errors·194 warnings입니다. `docs/dev-cycle/evidence/slash-batch-20260909/stream-red.log`, `docs/dev-cycle/evidence/slash-batch-20260909/vitest-qa-fix2.json:2-15`, `docs/dev-cycle/evidence/slash-batch-20260909/typecheck-qa-fix2.json`, `docs/dev-cycle/evidence/slash-batch-20260909/lint-qa-fix2.json`
- 별도 LSP 인터페이스는 제공되지 않아 실행하지 못했습니다. 최신 전체 Vitest와 typecheck를 대체 증거로 확인했습니다.

## Root Cause

전용 챗봇 화면의 스트림 훅에는 Sidebar가 구독하는 쿼터 갱신 이벤트가 없었습니다. 이벤트를 단순히 `done` 처리에 추가하면 서버가 응답 프레임을 보낸 뒤 수행하는 쿼터 확정과 경쟁하므로, 요청 수명주기의 완료 경계가 올바른 결합 지점입니다.

## Recommendations

1. 이벤트를 현재의 요청 `finally` 가드 안에 유지합니다.
2. `data.done` 분기로 옮기지 않습니다. 서버 쿼터 후처리보다 먼저 실행될 수 있습니다.
3. 오류·무료 명령에서도 이벤트가 발행돼 쿼터 GET이 한 번 더 발생하는 현재 정책을 유지해도 됩니다. 클라이언트는 실제 차감 여부를 신뢰성 있게 알 수 없으므로, 종료 뒤 재조회가 더 안전합니다.

## Architectural Status

- 이번 QA2 두 파일 수정: `CLEAR`
- CHAT-008·009 전체: `WATCH` 유지

최강 반론은 실제 차감된 요청에만 이벤트를 발행해야 불필요한 GET을 줄일 수 있다는 것입니다. 하지만 차감 여부는 서버의 스트림 후처리가 결정하며 클라이언트 프레임만으로 확정할 수 없습니다. 현재 요청 종료마다 한 번 재조회하는 방식이 약간의 조회 비용으로 상태 일관성을 보장합니다. 기존 `WATCH` 사유인 HTTP 쿼터 계층과 챗봇 코어의 모델 경로 판정 중복은 이번 수정과 무관합니다.
