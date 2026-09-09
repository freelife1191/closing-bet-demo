## Ponytail Review — CHAT-029 / CHAT-007

**Scope:** `frontend/src/app/chatbot/page.tsx` and `frontend/src/app/chatbot/page.regression-chat-007.test.tsx`, base `e6ab4ca`.

### Verdict

**APPROVE** — the T1 change is minimal and does not weaken verification.

The production diff adds exactly the two requested accessible names: the attachment removal button includes the concrete file name, and the response stop button has `aria-label="답변 중단"`. Existing click handlers and abort behavior are untouched.

The two regression tests directly exercise the user-facing contracts: removing one of two files preserves the other, and clicking the stop control aborts the pending fetch and renders the existing cancellation message. `afterEach` restores stubbed globals, preventing test leakage. No implementation abstraction, dependency, or unrelated assertion was added.

Low-confidence observation: the file-removal label uses the raw file name, so an unusual filename containing control-like characters could produce an awkward accessible label; this is browser-provided untrusted display text and is not a blocker for the bounded change.

**Confidence:** high.

## Exact Scope SHA-256

```text
6c912b2a48b7bcc7236e8eba9a3b0b565e99aa56f09acaec69f80f455f0c7f82  frontend/src/app/chatbot/page.tsx
5350227856f8b8e17b98485dd8583132198fd2a42b15a3f4c8a8eb3de55ef556  frontend/src/app/chatbot/page.regression-chat-007.test.tsx
```
