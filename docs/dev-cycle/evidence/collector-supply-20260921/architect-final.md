# Architecture review — final

Scope: this is an independent, read-only architecture review of the collector-supply round. It is unrelated to the earlier quota-ticker fixture work. The evidence target is the final file-hash set in `review-frozen.json` (SHA `aee99f0321cee7d56b5cbe8ce07f9ab989ce7cb588f929bb816cae88875f11a3`). No source import, test, compile, server, environment/data access, or external request was run by this reviewer.

## Result

`CLEAR` for the frozen architecture. The previous `056080` fallback BLOCK was retracted in `architect-initial.md`: it belonged to a non-production modular KRX implementation, while the public legacy KRX did not provide that mapping.

## Evidence

1. **Personal flow preserves the selected five-day contract.** `services/investor_trend_5day_service.py:456-488` preserves parseable dates in the foreign/institution detail rows, accepts personal data only when all five selected dates exist and exactly equal the personal-date set, then separately checks the latest date. `engine/investor_personal_flow.py:8-43` rejects short, duplicated, boolean, non-finite, and malformed personal rows while preserving a genuine numeric zero.
2. **Detail and collector caches now share one personal-value contract.** `engine/investor_personal_flow.py:12-25` accepts only an exact integer schema marker plus finite, non-boolean, integral numeric values; it converts an integral float to `int` and returns `None` for `1.5`, `NaN`, infinity, strings, and booleans. The stock-detail cache applies that helper to `individual` (`services/kr_market_stock_detail_service.py:105-114`), while the KRX pykrx-summary decoder applies it to `retail_buy_5d` but preserves independently decoded foreign/institution values (`engine/collectors/krx_local_data_mixin.py:462-474`). The UI carries `number | null` and renders null as `자료 없음` rather than applying a sign/color calculation (`frontend/src/app/dashboard/kr/closing-bet/page.tsx:407-415, 497-500, 712-721`).
3. **Reference cache generation prevents clear-after-start publish.** The in-flight key contains the captured generation, and publication is conditional on generation equality before memory or SQLite write (`services/investor_trend_5day_service.py:780-846`). `clear_investor_trend_5day_memory_cache` increments the generation and clears success, failure, and in-flight maps (`1102-1113`).
4. **Batch boundary remains bounded and ordered.** The screener first limits candidates, processes at most four prepared candidates, and consumes their results in prepared order (`engine/screener.py:227-270`). The service constrains batch input and prepares the CSV trend map before it submits at most four resolving tasks (`services/investor_trend_5day_service.py:1081-1100`).
5. **Public collector identity has one class surface.** The package re-exports `KRXCollector` from its submodule (`engine/collectors/__init__.py:3-8`) and `engine.__getattr__` defers public collector resolution to avoid service-first import cycles (`engine/__init__.py:15-22`). The identity and service-first import contracts are represented in `tests/engine/test_collectors_package_contract.py:6-17`.

## Test-surface assessment

The frozen test additions directly cover selected-date substitution, marked-bad detail-cache values, integral-float normalization, and the collector cache case where invalid personal data becomes `None` while foreign/institution remain `123`/`456` in `tests/services/test_investor_personal_flow.py:24-53, 65-98`. Bounded batch cutoff and de-duplication are covered in `tests/engine/test_screener_supply_batch.py:36-99`; clear, waiter release, failure TTL, and data-dir separation are covered in `tests/services/test_investor_trend_reference_concurrency.py:29-149`.

The preserved latest isolated-run artifacts report `77 passed` for the affected target suite (`pytarget-import-repair.json` / log), `2449 passed, 3 skipped` for the full pytest round (`pytest-import-repair.json` / log), and six fixture modes with correct SQLite repeats and blocked mutations (`fixture-import-repair.json` / log). The earlier performance artifact records a batch/serial median ratio of `0.277` at maximum concurrency four with identical result digests (`bench-final.json`). This reviewer read those records but did not execute them. Fixture validation likewise does not replace these product-level contracts.

## Trade-off and synthesis

The strongest counterargument is that serializing SQLite publication under the reference-cache lock can briefly delay `clear` while a cache write completes. The alternative—releasing the lock before persistence—would reopen the clear-after-start reinsert race the design explicitly rejects. The current design chooses correctness of the clear boundary; its bounded four-worker batch limits the affected contention.

## Architectural status

`CLEAR`
