# 제거한 구현 전용 검사와 대체 경로

기존 baseline에서 통과한 검사들. 통합 후 대상 private 구현이 제거되었으므로 기대값 변경으로 통과시키지 않고 공개 canonical 계약으로 대체한다.

- test_read_csv_cached_uses_cache_and_invalidates_on_mtime: 폐기된 read_csv_cached helper 전용. 공용 services CSV 캐시 검사 유지.
- test_read_csv_cached_prefers_shared_loader_when_supported: 폐기된 read_csv_cached helper 전용. 공용 services CSV 캐시 검사 유지.
- test_read_csv_cached_falls_back_to_pd_read_csv_for_unsupported_kwargs: 폐기된 read_csv_cached helper 전용. 공용 services CSV 캐시 검사 유지.
- test_read_csv_cached_uses_shared_loader_with_dtype: 폐기된 read_csv_cached helper 전용. 공용 services CSV 캐시 검사 유지.
- test_read_csv_cached_falls_back_to_pd_read_csv_when_dtype_cast_fails: 폐기된 read_csv_cached helper 전용. 공용 services CSV 캐시 검사 유지.
- test_read_csv_cached_retries_shared_loader_without_usecols_on_schema_mismatch: 폐기된 read_csv_cached helper 전용. 공용 services CSV 캐시 검사 유지.
- test_read_csv_cached_projects_existing_columns_on_pd_fallback_after_usecols_mismatch: 폐기된 read_csv_cached helper 전용. 공용 services CSV 캐시 검사 유지.
- test_read_csv_cached_separates_cache_by_usecols: 폐기된 read_csv_cached helper 전용. 공용 services CSV 캐시 검사 유지.
- test_read_local_csv_projects_existing_columns_on_usecols_mismatch: 폐기된 modular-only private helper/캐시 전용. test_collectors_refactor의 실사용 CSV/캐시/날짜/차트/수급 검사 및 이 파일의 canonical 검사로 대체.
- test_load_from_local_csv_reuses_cached_files: 폐기된 modular-only private helper/캐시 전용. test_collectors_refactor의 실사용 CSV/캐시/날짜/차트/수급 검사 및 이 파일의 canonical 검사로 대체.
- test_load_from_local_csv_does_not_backfill_explicit_missing_date: 폐기된 modular-only private helper/캐시 전용. test_collectors_refactor의 실사용 CSV/캐시/날짜/차트/수급 검사 및 이 파일의 canonical 검사로 대체.
- test_load_from_local_csv_converts_cached_date_column_once: 폐기된 modular-only private helper/캐시 전용. test_collectors_refactor의 실사용 CSV/캐시/날짜/차트/수급 검사 및 이 파일의 canonical 검사로 대체.
- test_load_from_local_csv_reuses_stock_lookup_map_without_repadding: 폐기된 modular-only private helper/캐시 전용. test_collectors_refactor의 실사용 CSV/캐시/날짜/차트/수급 검사 및 이 파일의 canonical 검사로 대체.
- test_load_from_local_csv_invalidates_stock_lookup_map_when_file_changes: 폐기된 modular-only private helper/캐시 전용. test_collectors_refactor의 실사용 CSV/캐시/날짜/차트/수급 검사 및 이 파일의 canonical 검사로 대체.
- test_get_chart_data_fallback_reads_minimum_columns: 폐기된 modular-only private helper/캐시 전용. test_collectors_refactor의 실사용 CSV/캐시/날짜/차트/수급 검사 및 이 파일의 canonical 검사로 대체.
- test_get_chart_data_reuses_pykrx_sqlite_snapshot_after_memory_clear: 폐기된 modular-only private helper/캐시 전용. test_collectors_refactor의 실사용 CSV/캐시/날짜/차트/수급 검사 및 이 파일의 canonical 검사로 대체.
- test_get_supply_data_fallback_reads_minimum_columns: 폐기된 modular-only private helper/캐시 전용. test_collectors_refactor의 실사용 CSV/캐시/날짜/차트/수급 검사 및 이 파일의 canonical 검사로 대체.
- test_get_supply_data_uses_pykrx_fallback_when_unified_trend_has_anomaly_flags: 폐기된 modular-only private helper/캐시 전용. test_collectors_refactor의 실사용 CSV/캐시/날짜/차트/수급 검사 및 이 파일의 canonical 검사로 대체.
- test_get_supply_data_fallback_reuses_precomputed_supply_summary_map: 폐기된 modular-only private helper/캐시 전용. test_collectors_refactor의 실사용 CSV/캐시/날짜/차트/수급 검사 및 이 파일의 canonical 검사로 대체.
- test_get_top_gainers_reuses_pykrx_sqlite_snapshot_after_memory_clear: 폐기된 modular-only private helper/캐시 전용. test_collectors_refactor의 실사용 CSV/캐시/날짜/차트/수급 검사 및 이 파일의 canonical 검사로 대체.
- test_get_supply_data_reuses_pykrx_sqlite_snapshot_after_memory_clear: 폐기된 modular-only private helper/캐시 전용. test_collectors_refactor의 실사용 CSV/캐시/날짜/차트/수급 검사 및 이 파일의 canonical 검사로 대체.
- test_load_supply_summary_map_reuses_sqlite_snapshot_after_memory_clear: 폐기된 modular-only private helper/캐시 전용. test_collectors_refactor의 실사용 CSV/캐시/날짜/차트/수급 검사 및 이 파일의 canonical 검사로 대체.
- test_load_stock_lookup_maps_reuses_sqlite_snapshot_after_memory_clear: 폐기된 modular-only private helper/캐시 전용. test_collectors_refactor의 실사용 CSV/캐시/날짜/차트/수급 검사 및 이 파일의 canonical 검사로 대체.
- test_load_from_local_csv_reuses_top_gainers_sqlite_snapshot_after_memory_clear: 폐기된 modular-only private helper/캐시 전용. test_collectors_refactor의 실사용 CSV/캐시/날짜/차트/수급 검사 및 이 파일의 canonical 검사로 대체.
