## Code Review Summary

**Files Reviewed:**

- `frontend/src/app/dashboard/kr/closing-bet/page.tsx`
- `frontend/src/app/dashboard/kr/closing-bet/page.regression-jongga-037.test.tsx`
- `tests/engine/test_news_collector_refactor.py`

**Base:** `b503549`
**Requirements:** JONGGA-037 completion response/reload, JONGGA-032 polling cleanup and late-response invalidation, INFRA-069 cache isolation with unchanged expectations.

**Total Issues:** 0

### By Severity

- CRITICAL: 0
- HIGH: 0
- MEDIUM: 0
- LOW: 0

### Issues

No confirmed correctness, security, performance, or maintainability defect was found.

`frontend/src/app/dashboard/kr/closing-bet/page.tsx:1697-1774` now centralizes interval and timeout ownership, invalidates generations on stop, suppresses overlapping status requests, and rejects state updates from unmounted or stale generations. Completion clears UI state and calls `onRefresh()` exactly through the active polling generation. The `runUpdate` 200 and 409 paths both enter the same polling function, while late run responses after unmount are rejected by the mounted-state guard.

`frontend/src/app/dashboard/kr/closing-bet/page.regression-jongga-037.test.tsx` covers completion, 409 continuation, timeout with late status response, unmount with a late status response, and unmount with a late run response. The tests assert request counts, refreshed data, rendered status, timer cleanup, and absence of post-unmount polling. The reported targeted and full validation results support the changed behavior.

`tests/engine/test_news_collector_refactor.py:29-65` isolates only cache load/save for the two source aggregation tests. Existing fetch, merge, ordering, limit, and source-failure assertions remain intact; dedicated cache snapshot tests remain in the same file.

One low-confidence documentation observation: `page.tsx:1767` says “5 minutes” while the existing numeric timeout is `350000` ms (5 minutes 50 seconds). This value was retained and is outside the requested lifecycle change; it is not a blocker for the reviewed scope.

### Recommendation

**APPROVE**

**Confidence:** high for the supplied three-file scope and the stated validation evidence. This review used the installed code-reviewer prompt and is an independent review lane; no dedicated role invocation is claimed. Architecture review remains separate.

## Exact Scope SHA-256

```text
4cb5256c46fab18f2a519e1a57cee326c18ce4e57582a1f4fe63c5ab56c609d3  frontend/src/app/dashboard/kr/closing-bet/page.tsx
891a2ee863f70b7d1910bf9bc7300b59d1d0c78aa0c056f501d1c05766c0d7f9  frontend/src/app/dashboard/kr/closing-bet/page.regression-jongga-037.test.tsx
c5d0d74127545ce6188cc8ac9e7c0b0321d996664e6405e4f6f923038c30645c  tests/engine/test_news_collector_refactor.py
```
