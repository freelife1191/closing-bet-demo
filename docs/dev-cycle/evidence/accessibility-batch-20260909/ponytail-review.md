## Ponytail Review — FE-034 / FE-040

**Scope:** eight exact files listed in `docs/dev-cycle/evidence/accessibility-batch-20260909/review-input.json`, base `f7801ff`.

### Verdict

**APPROVE** — the changes are bounded, direct, and do not weaken verification.

`frontend/src/app/components/Header.tsx:21-43` converts the existing visual breadcrumb into native `nav`/`ol`/`li` semantics, gives the home icon an accessible name, hides decorative separators from assistive technology, and marks the current item with `aria-current="page"`. The visible layout classes remain on the list/items.

The heading updates in `frontend/src/app/dashboard/kr/closing-bet/page.tsx:1225,1444,1461,1486,1515,1536,2028,2221,2258,2308` repair the local h1→h2→h3→h4 hierarchy while preserving text and presentation classes. No independent chart/detail modal heading was broadened.

The four empty-state changes in `PaperTradingModal.tsx:512-526,592-604`, `StockTradeHistoryModal.tsx:348-360`, and `CumulativeClientPage.tsx:887-899` move explanatory text outside table bodies. Conditions, wording, data row rendering, and trade behavior remain unchanged; this avoids invalid/non-semantic table rows for empty states and keeps the message inside the existing card width/overflow boundary.

No new abstraction, dependency, runtime path, data mutation, or type suppression was introduced. The regression tests are focused and preserve existing assertions. The exact eight worktree hashes match the supplied review input.

No overengineering or verification weakening found. Confidence: high.

## Exact Scope SHA-256

```text
e4e94645db19cb1589cb414652e1a0a9e5768147e0c27e7852fe6b71762417a8  frontend/src/app/components/Header.tsx
a5b15b5b9147aab7134ea0cb0142e06f656dfac678c8b7a2d4b6024d62ffaa97  frontend/src/app/components/PaperTradingModal.tsx
0b0c434c4b88d9ae27c0292b69a0b2d8c44f1e6f7d4345d20abd107776c0bb8d  frontend/src/app/components/StockTradeHistoryModal.tsx
1487bd472b2872ab623e46b84462ff2d7f832a6b734f36e6774cb7811500ef1b  frontend/src/app/dashboard/kr/closing-bet/page.regression-fe-024.test.tsx
3b4366be604195c06a19e9097159d39755bfaf59ee5db768007266395a951d8a  frontend/src/app/dashboard/kr/closing-bet/page.tsx
a9d162b4a9b939ba0f14c25f43439fd4c32ecbdcdf61d426795dd006eef8cc44  frontend/src/app/dashboard/kr/cumulative/CumulativeClientPage.tsx
6a0b0155c252246ab40dcfe8ff0b587bbd305d9842f52b13ee3a5cd1e70ace93  frontend/src/app/components/Header.regression-fe-034.test.tsx
d23da83bdef7adcf3ccd423ec524b3c0aa12ea4ceac4581ceabb1a68adf4b91b  frontend/src/app/components/emptyState.regression-fe-040.test.tsx
```
