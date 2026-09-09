## Ponytail Review — INFRA-069

**Scope:** `tests/engine/test_news_collector_refactor.py` only; two test changes at lines 32-33 and 64-65.

### Verdict

**APPROVE** — no overengineering and no verification weakening found.

The patch adds the smallest local isolation needed for the two source-aggregation tests. Both tests now stub only `_load_cached_news_items` and `_save_cached_news_items`, so their existing mocked fetcher, merge, sort, limit, and source-failure assertions remain unchanged. This directly addresses the observed failure mode where a real cache entry was read before the mocked fetchers, while cache behavior itself remains covered by the later dedicated snapshot tests beginning at line 86.

The change does not modify product code, add dependencies, alter expected values, broaden fixtures, or remove assertions. The two cache stubs are explicit and symmetrical, making the test intent clear. No concern about hidden failures or weakened coverage was found.

**Confidence:** high.
