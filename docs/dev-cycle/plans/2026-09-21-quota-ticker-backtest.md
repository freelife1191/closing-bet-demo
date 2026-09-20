# Quota, ticker and backtest Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for the assigned tasks. Steps use checkboxes. User approved these three bounded existing-flow changes on 2026-09-21; this T3 implementation plan does not expand that scope.

**Goal:** FE-043 quota failures recover without JSON SyntaxError; JONGGA-030 uses consistent ticker keys; FLOW-006 removes redundant backtest exports.
**Architecture:** Reuse fetchAPI for both quota consumers. Move the existing signal ticker normalization contract to a dependency-light common helper, retain caller names where compatibility requires them, and use it for scalar and DataFrame price keys. Keep backtest_service as the single public facade and import implementation helpers directly beneath it.
**Tech Stack:** Existing Python/pandas/Flask, React/Next.js, pytest/Vitest. No new dependencies.
**Spec:** Approved in-chat design: FE-043 first, JONGGA-030 and FLOW-006 together, T3 reviews and full tests plus ego-browser QA.

## Global Constraints
- Original 3500/5501/live, original data and actual env values are outside execution scope. No real collection, LLM, auth, settings save, deletion, recharge, trading.
- Source edits on develop; preserve untracked root package.json. Tests/imports only in an owned scratch checkout under sandbox, dotenv disabled, sanitized environment, network denied except owned loopback/IPC.
- Browser driver ego-browser; UltraQA app-adapted, no OMX state commands. Only owned processes and scratch are cleaned.
- Review order: critic plan; ponytail; independent code/architect; deep review; static checks and dynamic matrix. Review stages bounded to 15 minutes each; individual tests 5 minutes, full round 90 minutes before checkpoint.

## Review Focus
1. Non-JSON 200 as well as HTML 404/502 and JSON 401/403/500 must yield controlled failures; test both consumer recovery and shared parser.
2. Stale response after logout/account change must not display another account's quota; test cancellation/identity boundaries.
3. Null, pandas missing, zero, date-like values and mixed alphanumeric tickers must not become another ticker; test explicit normalization matrix.
4. Old lowercase or padded cache keys must resolve consistently without rewriting original databases; test synthetic SQLite roundtrip and collisions.
5. Cached _ticker_padded Series and public backtest exports must retain documented reuse/output behavior; lock with regression tests and import tests.

## Resolved implementation contracts
- Latest quota GET failure clears the displayed value and shows exactly `사용량을 불러올 수 없습니다`. Initial pending displays `사용량 확인 중`; never imply default 10 remaining during failure. Recovery replaces error with real remaining count.
- Quota usage/remaining must be finite integer numbers >=0, limit finite integer >0; numeric strings rejected. Additional backend fields allowed; no sum-equality restriction because recharge semantics vary. Invalid shape raises `사용량 응답이 올바르지 않습니다`. HTML200 parser error becomes Error message `서버 응답이 올바른 JSON이 아닙니다`, status=200, data undefined; response body never included. Preserve AbortError timeout path.
- Sidebar GET keeps `{ headers: getAuthHeaders() }` and anonymous X-Session-Id regression. Settings remains authenticated-only.
- Quota consumer effects capture account identity (session status/email) plus request generation; cleanup invalidates generation. Identity changes clear previous quota and error before a new result can render. A→B and A→unauth delayed A responses are discarded. No external abort-signal API change is needed. Repeated quota updates accept only latest request.
- Realtime SQLite old keys: retain indexed exact-key lookup for canonical rows, add a bounded compatibility query for requested lowercase/unpadded forms using SQL UPPER/TRIM/padding and length guard, then validate every returned original ticker with the canonical helper. Merge only requested canonical keys, newest timestamp wins and equal timestamp prefers exact canonical spelling. No original DB rewrite or schema migration. Test collisions and invalid/truncated keys. JSON maps have no per-row timestamp; exact canonical spelling wins collisions, otherwise stable lexical original-key order.

## Task 1 — FE-043
Files: frontend/src/lib/api.ts and api tests; frontend/src/app/components/Sidebar.tsx, SettingsModal.tsx and their tests. Read frontend/AGENTS.md, bundled fetching-data guide and vercel-react-best-practices.
- [ ] Add failing consumer tests using `new Response('<!doctype html>', {status: 502})`; assert no quota corruption and controlled error, then valid quota recovery. Include HTML200 and JSON401/403/500.
- [ ] Replace direct GET parsing with `fetchAPI<Quota>('/api/kr/user/quota')`; normalize successful non-JSON parser failures in fetchAPI without swallowing timeout/status. Validate numeric quota shape before display; distinguish unavailable state from zero and avoid stale account values.
- [ ] Run targeted Vitest red/green in scratch; typecheck/lint/full Vitest/build after integration.

## Task 2 — JONGGA-030
Files: new engine/ticker_utils.py; app/routes/kr_market_signal_common.py; services/kr_market_realtime_price_service.py, kr_market_realtime_price_cache.py, kr_market_realtime_service.py, kr_market_csv_utils.py, kr_market_data_cache_prices.py, paper_trading_price_fetchers.py, paper_trading_sync_service.py, kr_market_vcp_cache_update_service.py; engine/collectors/krx_data_mixin.py; backtest scenario/trade helpers; related tests. Additional direct producers/consumers only when required to prevent mismatched keys.
- [ ] Lock existing accepted prefix/suffix contract and input table in tests: `5930 -> 005930`, `0007c0 -> 0007C0`, `A005930 -> 005930`, `005930.KS -> 005930`, missing/zero/date -> empty. Preserve numeric integral CSV values, reject nonfinite/nonintegral inputs.
- [ ] Extract `normalize_ticker(value: Any) -> str` into dependency-light helper. Avoid importing Flask routes into services. Retain existing function names as imports/aliases where callers depend on them.
- [ ] Replace duplicated normalizers and digit-only fast path checks. Normalize price keys before filtering, skip empty keys in map/cache reads and writes. Update services.kr_market_csv_utils.get_ticker_padded_series and import it from both backtest helpers, including existing cache column semantics.
- [ ] Verify uppercase/lowercase synthetic SQLite keys, VCP price lookup and valid numeric behavior using targeted pytest; no schema changes or real data migration.

## Task 3 — FLOW-006
Files: services/kr_market_backtest_service.py, kr_market_backtest_calculators.py, kr_market_backtest_cumulative.py, kr_market_backtest_signal_stats.py; services/kr_market_analytics_service.py, kr_market_backtest_stats_helpers.py; app/routes/kr_market_backtest_helpers.py and tests/services/test_kr_market_backtest_service.py.
- [ ] Record callers via rg and lock exported results/import availability with existing tests.
- [ ] Keep service facade importing leaf helpers directly. Update internal callers to leaves, remove unused calculators/cumulative/signal_stats facade files. Preserve exported callable signatures and results.
- [ ] Verify no live import refers to removed paths and run backtest regression tests alongside Task2.

## Integration and completion
- [ ] Record exact diff/file hashes; ponytail then code/architect then deep review, repair findings in scope.
- [ ] Scratch full pytest, Vitest, typecheck, lint and build; retain exit codes/skips. Stage allowed files only and git diff --cached --check; initial implementation/QA matrix commit retains TODO entries.
- [ ] UltraQA matrix: quota initial failure, prior-success failure, recovery in Sidebar/settings; mixed ticker real price/backend calculations through VCP/closing/cumulative UI; adversarial invalid ticker and cache roundtrip; dirty-file and cleanup checks. Real UI, synthetic isolated backend with real changed functions. Inspect screenshots and Next MCP errors/compilation issues.
- [ ] Terminate only recorded owned processes, finish ego TaskSpace once, delete owned scratch. Archive only all required PASS; remove these three TODOs in final archive commit. Otherwise record exact unfinished phase.
