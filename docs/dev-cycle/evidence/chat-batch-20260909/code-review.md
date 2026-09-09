## CODE REVIEW REPORT

**Scope:** CHAT-013 / CHAT-015 / FE-038, base `99882b8b2697e8102a6cfc56f7549dfe63f08eb7`, exact nine files in `docs/dev-cycle/evidence/chat-batch-20260909/review-input.json`.

**Files Reviewed:** 9
**Total Issues:** 0

### Severity

- CRITICAL: 0
- HIGH: 0
- MEDIUM: 0
- LOW: 0

### Findings

No confirmed correctness, security, performance, or maintainability defect was found.

- `frontend/src/app/chatbot/useChatStream.ts:88-128` uses a single invalidation path for stop, unmount, and session changes. It increments the request token and aborts the active controller, so stale stream chunks, JSON responses, errors, and `finally` cleanup cannot mutate current UI state.
- `frontend/src/app/chatbot/useChatStream.ts:151-185,227-349` keeps the synchronous send lock for the full request/stream lifetime, guards each read and setter with both request ownership and visible-session ownership, and preserves normal JSON/SSE results before `finally`. The parent/finally bug is addressed by checking the request token rather than relying on `isSendingRef` being true at commit time; invalidation already clears the lock and aborts the controller.
- `frontend/src/app/chatbot/useChatStream.regression-chat-013.test.tsx` covers full-stream busy state, duplicate send rejection, stop/abort, session switch late delta suppression, new-session assignment, unmount abort, immediate JSON persistence, and final SSE delta persistence. The prior assumption that every consumer must drain chunks is removed in favor of controlled result assertions.
- `frontend/src/app/chatbot/chatMessageParser.ts:40-47,121-128,167-181` isolates dense-list splitting while preserving heading lines and applies the bounded suggestion contract using Unicode code points. The parser tests cover title preservation and recommendation limits.
- `frontend/src/app/components/ChatWidget.tsx:230-243` and `frontend/src/app/components/Sidebar.tsx:112-124` reuse `getAuthHeaders`, preserving existing endpoints and request bodies while removing duplicated browser-session identity construction. This matches the established proxy signing boundary.
- Reported validation is pytest 2281 passed/2 skipped, targeted 32 planned, Vitest 460, typecheck green, and lint with zero errors. No new dependency or type suppression is present.

Low-confidence observation: `streamOwnsVisibleSession()` permits a null active session to accept a newly assigned stream session (`useChatStream.ts:173-176`); this is intentional for automatic session assignment and is covered by the corresponding regression test. No blocker.

No secret exposure, authentication bypass, URL identity leakage, unbounded process, or unsafe external side effect was introduced.

### Recommendation

**APPROVE**

Confidence: high. This is an independent code-reviewer lane using the installed code-reviewer prompt and code-review task card; architecture review remains separate and no dedicated role invocation is claimed.

## Exact Scope SHA-256

```text
2974a231dd7202cb17692a19c00ae7c917d671a6f0bd6a14bc3b5101012bbd9c  frontend/src/app/chatbot/chatMessageParser.test.ts
76d8a3f379808f8c62fbb72fc2d9a228734ad8da1ad41bd32f2bc04034289b74  frontend/src/app/chatbot/chatMessageParser.ts
0f5e1877fac1815984c94e006e9344149933e7d8919b3750304594f2a86fc586  frontend/src/app/chatbot/page.regression-chat-001.test.tsx
18bef9c6cc62960c1bcb8f1d0d8195e181e233b7cfcc82d0c4c807b045a9f51b  frontend/src/app/chatbot/useChatStream.ts
30438033c19988f74f1bcacb56e803686a108974c8868ccfca05a9d3abddf92c  frontend/src/app/components/ChatWidget.tsx
1a920937315c5e97b6659faaa3ee643e7e7dc8a51537d58bb862802ac29401ec  frontend/src/app/components/Sidebar.tsx
e9b4eba7bac63e35e806c04948ce7ef9c7118dcbbd73152c4492109715865a14  frontend/src/app/chatbot/ChatMessage.regression-chat-015.test.tsx
ca8ccddc747c5a12716f1c10e0e92b36be96b691ad3db369a96bc9149c20f2a8  frontend/src/app/chatbot/useChatStream.regression-chat-013.test.tsx
8295d9492f9c334d8c88879fe16f29eff6748d6661d3901e827c9127db1d6d7f  frontend/src/app/components/sessionHeaders.regression-fe-038.test.tsx
```
