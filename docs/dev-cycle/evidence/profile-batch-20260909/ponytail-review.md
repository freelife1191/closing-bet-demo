## Ponytail Review — FE-022 / FE-039

**Scope:** the eight files and hashes listed in `docs/dev-cycle/evidence/profile-batch-20260909/review-input.json`, based on `2a37cfc`.

### Verdict

**APPROVE** — no overengineering or verification weakening found.

The profile behavior is consolidated into two small helpers in `frontend/src/app/components/chatHelpers.ts`: `normalizeUserProfile` owns malformed/default shape normalization, and `resolveUserProfile` owns session-display precedence while preserving persona from the saved profile. This avoids duplicating identity precedence in Sidebar and Chatbot and leaves edit/save state separate from authenticated display state.

`Sidebar.tsx` and `chatbot/page.tsx` consume the same resolver, while the `user-profile-updated` event only reloads the normalized local profile. This is a proportionate mechanism for the two existing independent entry surfaces; it does not add a state library or new persistence path.

`SettingsModal.tsx` derives custom-role mode from the persisted persona and keeps select, direct input, system persona, cancel/reopen, and name-only save behavior in the existing component. The changes remove the previous split `role`/`persona` state rather than layering another abstraction.

The added tests are focused regression contracts for session display, profile normalization, and persona restoration. No assertions were removed, no dependency or type suppression was introduced, and no production/authentication boundary was broadened.

One low-confidence observation: `resolveUserProfile` resolves name and email independently, so an authenticated session with only one populated field can display the other field from local profile. This matches the stated per-field fallback requirement and is not a blocker.

**Confidence:** high.

## Exact Scope SHA-256 Verification

All eight current worktree hashes match `review-input.json` exactly.

```text
2263a4614e0eda1642d4f6c3a63be3fd5124a83301c3bf554b5651d572da5458  frontend/src/app/chatbot/page.tsx
dbb1ce22d60ae9347350a771772cc95d7e4d02b7e44439931a8c36a3799cb67c  frontend/src/app/components/SettingsModal.tsx
fdd3a4cc24bef0972494d5e671056000262e5e5a94485e1a48c4125f7ca2a43e  frontend/src/app/components/Sidebar.session.test.tsx
ef43b8f938f061cae43b363113fc7e304b9b0002f9cd36e410b715757e40a4ea  frontend/src/app/components/Sidebar.tsx
713d2da325b558691bcc2de0fcd4f0dd545b7980be1a1c27c1df849bc49b53e7  frontend/src/app/components/chatHelpers.test.ts
7dd840d2fab21daa0a90b9eb04e67a4d5e0759ea31b22b2eb9c00a8d7d4341e4  frontend/src/app/components/chatHelpers.ts
9a5c8a0cf289b747be1144c52ad075b2f63d4a9eee6faee337a8aeff017beff4  frontend/src/app/chatbot/page.regression-chat-022.test.tsx
a98553ee152fbbc09df6f0480633c5d3a223781e18a7497815a0945a665bd529  frontend/src/app/components/SettingsModal.profile.test.tsx
```
