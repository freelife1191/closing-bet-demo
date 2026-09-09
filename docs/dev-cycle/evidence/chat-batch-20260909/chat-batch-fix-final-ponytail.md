## Final Ponytail Re-review — CHAT-015 reasoning heading fix

**Scope:** `frontend/src/app/components/ThinkingProcess.tsx` and `frontend/src/app/chatbot/ChatMessage.regression-chat-015.test.tsx`, base `212c7194dc2d18cf6f4c315bf629c7ba0fd8a296`.

### Verdict

**APPROVE** — the follow-up correction preserves the existing normalization order and adds the requested contract regression without overengineering.

`ThinkingProcess.tsx:15-35` first performs heading-aware, line-wise dense-number separation, joins the transformed lines, and then re-splits before the existing ordered-marker loop. This specifically avoids the intermediate-newline regression where a `1)첫째 2)둘째` transformation could bypass the marker processing. The original `1.` and `1)` marker support remains in the unchanged ordered-marker regex, and heading lines remain excluded from dense conversion.

The test file now covers both the observed empty-h3 case and the existing dense numbering contract, including the no-space `1)` form. The additional case is a regression guard; the supplied evidence reports 5/5 targeted tests, typecheck pass, and lint quiet.

No production behavior outside this parser normalization was changed, no assertions were weakened, and no dependency or abstraction was added. The no-space `1)` scenario was not observed as a pre-existing product failure; it is correctly treated as contract coverage rather than a defect claim.

**Confidence:** high.

## Exact Scope SHA-256

```text
49a25550e5e11149b5643c91f1f8b357ceddbdbb3bb14242709e72af917d008c  frontend/src/app/components/ThinkingProcess.tsx
2b1ee68e4fa2d35d1a24bbd2f2ed04c55153c6144e7d51aa30131280f5776106  frontend/src/app/chatbot/ChatMessage.regression-chat-015.test.tsx
```
