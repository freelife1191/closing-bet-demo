## Ponytail Review — JONGGA-037 / JONGGA-032

**Scope:** `frontend/src/app/dashboard/kr/closing-bet/page.tsx` polling block, with the companion regression test being added separately.

### Verdict

**APPROVE** — the change is proportionate to the failure modes and does not show overengineering.

The five refs have distinct responsibilities: interval ownership, timeout ownership, generation invalidation, in-flight request suppression, and mounted-state protection. Together they address the stale-closure and async-unmount cases described by the task. `stopPolling` centralizes cleanup and invalidates late completions; the `finally` path releases the in-flight guard only for the current generation. Completion, timeout, and unmount all use the same cleanup boundary.

The implementation keeps the existing 2-second polling cadence and status endpoint. It does not introduce a new abstraction, dependency, data path, or UI behavior beyond the requested lifecycle safety. Removing the old `updating` closure dependency is the minimal repair for the stale state decision. Error handling remains visible through `console.error` for the active generation and does not suppress current failures.

The timeout remains the existing 350000ms operational bound; the comment says five minutes while the numeric value is five minutes fifty seconds, which is pre-existing behavior and outside this ponytail-only review. It should be reconciled by the full code-review lane if the contract requires exact five minutes.

**Confidence:** high for scope and design proportionality. Full code review and the pending unmount regression test remain separate gates.
