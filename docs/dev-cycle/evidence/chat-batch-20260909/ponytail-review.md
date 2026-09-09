## Ponytail Review — CHAT-013 / CHAT-015 / FE-038

**Scope:** nine exact files listed in `docs/dev-cycle/evidence/chat-batch-20260909/review-input.json`, base `99882b8b2697e8102a6cfc56f7549dfe63f08eb7`.

### Verdict

**APPROVE** — the implementation is bounded and the added lifecycle state is justified by the requested race/interruption contracts.

`frontend/src/app/chatbot/useChatStream.ts:86-177,224-356` uses explicit refs for mounted state, send lock, request token, active session, and stream session. Each has a distinct role: unmount/session changes invalidate late work, the synchronous send ref rejects duplicate submissions, and the token/session predicates guard every stream, JSON, error, and final setter. Abort remains the existing mechanism; no new transport or state library was introduced. The final-token and sending cleanup logic avoids treating an ordinary successful response as stale.

`chatMessageParser.ts` keeps the dense-numbered-list fix in a small helper and applies the existing suggestion cap of three entries and 120 Unicode code points. The heading guard avoids changing Markdown headings. This is a narrow parser repair rather than a new parser abstraction.

`ChatWidget.tsx` and `Sidebar.tsx` reuse the existing `getAuthHeaders` helper, removing duplicated browser-session header construction without changing request endpoints or bodies. This aligns the two callers with the established proxy identity contract.

The regression tests cover token/session interruption, abort, duplicate send prevention, stream completion, parser title/list behavior, suggestion limits, and shared auth headers. No assertions or existing behavior were removed to make tests pass. No dependency, type suppression, or unrelated UI/product path was added.

Low-confidence observation: `useChatStream.ts:175-182` permits the request to start before the effect that marks the component mounted has run, but user event handlers run after effects and the tests cover the interaction path; no runtime defect is indicated. Confidence: high.

This review used the installed `code-reviewer` prompt and codex review guidance as a substitute review lane; no dedicated role invocation is claimed.

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
