## Code Review Summary

**Base:** `5252bec`
**Scope:** VCP-020, VCP-021, VCP-023, VCP-024 implementation and regression tests listed in `review-input.json`.
**Total Issues:** 1

### By Severity

- CRITICAL: 0
- HIGH: 0
- MEDIUM: 1
- LOW: 0

### Findings

- **[MEDIUM] Malformed same-day legacy payload can discard a valid date-specific AI map.** File: `services/kr_market_vcp_payload_service.py:303-311` calls `merge_legacy_ai_fields_into_map` after the legacy payload passes only the top-level date check. The implementation in `app/routes/kr_market_vcp_signal_helpers.py:347` iterates `legacy_payload.get("signals", [])`; when a same-day legacy payload has `signals=None` or another non-iterable malformed shape, it raises `TypeError`. The outer guard in `services/kr_market_vcp_payload_service.py:65-76` then catches the exception and skips the entire AI merge, including already valid date-specific recommendations in `ai_data_map`. The previous implementation isolated the legacy merge in its own `try/except` at `services/kr_market_vcp_payload_service.py:297-305`, so this is a regression. Fix by isolating legacy-map construction/merge in a narrow exception boundary or validating `signals` as a list before calling it; preserve and merge the valid date-specific map even when legacy data is malformed. Add a regression fixture with valid date-specific signals plus same-day `kr_ai_analysis.json` containing `signals=None`, asserting the date-specific recommendation survives.

- `services/kr_market_vcp_payload_service.py:269-350` resolves one strict ISO signal date for the complete signal set, selects only the date-specific payload, and permits generic legacy enrichment only for a current-day payload whose explicit `signal_date` matches. Missing, invalid, or mixed dates stop the merge. The `deep_copy=False` loader path and narrow `TypeError` compatibility fallback remain visible.
- `engine/vcp_ai_analyzer_helpers.py:553-610` distinguishes missing/non-finite values from real zero values through `safe_optional_float`. Incomplete evidence returns confidence 55 and avoids fabricated numeric evidence; complete inputs preserve the existing BUY/HOLD/SELL rules and confidence values. The tested partial-evidence SELL cases are explicit real negative evidence, not a default substitution.
- `engine/screener_result_builders.py:30-60` and `scripts/init_data.py:1633-1641,1877-1930` preserve missing one-day supply as `None` and persist the fields without converting absence to zero.
- `engine/vcp_ai_orchestration_helpers.py:13-18` owns the recommendation-field tuple, and consumers in the route, tracker, cache update, reanalysis, and initialization paths import it. This removes duplicated schema lists while preserving provider aliases and priority order.
- `services/kr_market_vcp_reanalysis_service.py:17-95,145-155` keeps GPT/Z.ai/OpenAI aliases and Perplexity mapping, with the shared tuple supplying field names. Required-key filtering still rejects unknown fields and preserves the early-return behavior.
- Tests cover historical/current/mixed/invalid date payloads, provider schema and alias behavior, missing versus zero one-day values, fallback confidence/action/reason, and cache/reanalysis contracts. The supplied targeted evidence reports 130 Python and 58 frontend tests passing.

No confirmed correctness, security, performance, or maintainability defect was found in the reviewed scope. No hardcoded secrets, unsafe broad fallback, fabricated missing numeric values, or external side effects were introduced.

The only residual review boundary is runtime data compatibility for untracked production `data/` files; this was intentionally excluded by the task safety contract and is covered by injected fixtures and existing static/targeted evidence.

### Recommendation

**REQUEST CHANGES**

Confidence: high for the reviewed source and fixture-backed contracts. Full repository checks and dynamic QA remain owned by the leader.

## Exact Scope SHA-256 Appendix

The hashes below match `review-input.json` and were recomputed from the current worktree:

```text
00846f9cf4dc840c7d04b32ef8a5f26dbb82344877eefd77129e451a55dd5b71  app/routes/kr_market_vcp_signal_helpers.py
cbdc31bd81ff6111636e7227f8644e26baf3f6b078d190aa883fc2ed066b694e  engine/screener_result_builders.py
ec5d371bda71c53eb755a1874411e562e62b5fbf0185043fa499387d172b6a2e  engine/signal_tracker_ai_helpers.py
635fc222de6370c78397afb54fcfbc59e4525217e3b1ff5178e54a280cb389  engine/vcp_ai_analyzer_helpers.py
bc564d2aa7aea729e6e4f888f109ac5ca8679a8af7c83bbc091b34f4518ed19a  engine/vcp_ai_orchestration_helpers.py
c837e2c5940ec7c33c8af16f8e01288d17199b46ad210a36876f877381cd3f60  scripts/init_data.py
c91829821a82f9f52b10e7ad8d10daa4b4c7af7094dd0f94f6fe25807c5fb989  services/kr_market_vcp_cache_update_service.py
3a4a348853c6e9f732baa96fa06ebdd624681e7c47881c659ea360ccd47f76f0  services/kr_market_vcp_payload_service.py
da704bf0bf9a0d0c0179338764c70e4cf36e0f9a2e28c5a1d2d8ef202b90ccb9  services/kr_market_vcp_reanalysis_service.py
ca592fd2e9880b2462472e552d2ef09eff32f353108e992cba573122394f5bd4  tests/app/test_kr_market_data_signals_routes_refactor.py
351b5b4f27e2deb0edc4c83141fddbc41dc8a01b8f6eb60f535572376fe71e16  tests/app/test_kr_market_vcp_signal_helpers_refactor.py
10acfa698a2f5bf4229ee02e1d87ae406980c0814a1c73596996740297f9fd1f  tests/engine/test_screener_result_builders_refactor.py
3a91c78f1a61e78f0d4afe355f8602f73de3cf21d7643394d9c8f0340898bdc3  tests/engine/test_signal_tracker_ai_helpers_refactor.py
54409a03ae51fd123e25e7817fe56101dc76a272c8bf98d923c9419c3fe8b6c5  tests/engine/test_vcp_ai_analyzer_helpers_refactor.py
4372ff67b0ae5789c6e9964fbd9519d140cbb533dfcbbfaaa60e09c5ea8e25c8  tests/engine/test_vcp_ai_analyzer_refactor.py
ceef43429978b31e99096143daaf4b8d6e67bf83f63a7274079d024a2ff85c0e  tests/engine/test_vcp_ai_orchestration_helpers_refactor.py
810ecb6a9fa26dd812b4cfa99a81bc4dfbffbc0c2a1c348acdd208977ad73d5a  tests/scripts/test_init_data_vcp_scheduler.py
85dafaeb2a47201579d3944249e7b9e9e245624871425faa2edb380ba5c8e8e0  tests/services/test_kr_market_vcp_cache_update_service.py
e680788311d595df37531d96d00918c27e16bb6169f1c88e42cd977ad73d5a  tests/services/test_kr_market_vcp_payload_service_refactor.py
```

## Follow-up Review — Legacy Malformed Shape Fix

**Reviewed delta:** `services/kr_market_vcp_payload_service.py` and `tests/services/test_kr_market_vcp_payload_service_refactor.py` after the prior MEDIUM finding.

The fix isolates both legacy-map construction and legacy-field merge in a narrow exception boundary at `services/kr_market_vcp_payload_service.py:303-315`. A malformed same-day legacy `signals` shape can now be logged and ignored while the verified date-specific `ai_data_map` continues through `merge_ai_data_into_vcp_signals`. The added regression at `tests/services/test_kr_market_vcp_payload_service_refactor.py` covers `signals=None`; the loader failure/type-error compatibility path is also covered immediately above it. This restores the pre-regression failure boundary without reopening historical or date-unproven legacy fallback.

The supplied delta hashes were recomputed and match:

```text
8febf71a20415d9dff03a8a4cab0e674cabbc3fc834108df93200160f2ee420f  services/kr_market_vcp_payload_service.py
b2dc11252d9eadb5a3bb6c2cb47a0e63706d5da39f8c46a581304e211f0404c6  tests/services/test_kr_market_vcp_payload_service_refactor.py
```

**Delta issues:** 0
**Final recommendation after this delta:** **APPROVE**
