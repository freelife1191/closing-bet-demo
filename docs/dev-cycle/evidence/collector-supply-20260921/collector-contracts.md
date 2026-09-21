# KRX method ownership — initial port and final disposition

기준: 실사용 legacy KRX 계약. 날짜/캐시/이름 클래스 상태 공유.

- __init__: krx.py
- __aenter__: krx.py
- __aexit__: krx.py
- _stable_token_to_int: krx.py
- _latest_market_date_cache_token: krx.py
- _latest_market_date_sqlite_context: krx.py
- _load_cached_latest_market_date: krx.py
- _save_cached_latest_market_date: krx.py
- clear_latest_market_date_cache: krx.py
- clear_stock_lookup_cache: krx.py
- _stock_name_sqlite_context: krx.py
- _set_stock_name_memory_cache: krx.py
- _load_cached_stock_name: krx.py
- _save_cached_stock_name: krx.py
- _stock_lookup_memory_cache_key: krx_local_data_mixin.py
- _stock_lookup_sqlite_context: krx_local_data_mixin.py
- _deserialize_stock_lookup_maps: krx_local_data_mixin.py
- _load_cached_stock_lookup_maps: krx_local_data_mixin.py
- _save_cached_stock_lookup_maps: krx_local_data_mixin.py
- _normalize_top_gainers_target_token: krx_local_data_mixin.py
- _top_gainers_sqlite_context: krx_local_data_mixin.py
- _top_gainers_memory_cache_key: krx_local_data_mixin.py
- _serialize_top_gainers: krx_local_data_mixin.py
- _deserialize_top_gainers: krx_local_data_mixin.py
- _load_cached_top_gainers: krx_local_data_mixin.py
- _save_cached_top_gainers: krx_local_data_mixin.py
- _pykrx_supply_sqlite_context: krx_local_data_mixin.py
- _deserialize_pykrx_supply_payload: krx_local_data_mixin.py
- _load_cached_pykrx_supply_summary: krx_local_data_mixin.py
- _save_cached_pykrx_supply_summary: krx_local_data_mixin.py
- _pykrx_chart_sqlite_context: krx_local_data_mixin.py
- _serialize_pykrx_chart_payload: krx_local_data_mixin.py
- _deserialize_pykrx_chart_payload: krx_local_data_mixin.py
- _load_cached_pykrx_chart_data: krx_local_data_mixin.py
- _save_cached_pykrx_chart_data: krx_local_data_mixin.py
- _pykrx_fundamental_sqlite_context: krx_local_data_mixin.py
- _deserialize_pykrx_fundamental_payload: krx_local_data_mixin.py
- _load_cached_pykrx_fundamental: krx_local_data_mixin.py
- _save_cached_pykrx_fundamental: krx_local_data_mixin.py
- _get_latest_market_date: krx.py
- get_top_gainers: krx_data_mixin.py
- _should_use_toss_top_gainers_fallback: krx_data_mixin.py
- _load_from_toss_prices: krx_local_data_mixin.py
- _process_ohlcv_dataframe: krx_data_mixin.py
- _load_from_local_csv: krx_local_data_mixin.py
- get_stock_detail: krx_local_data_mixin.py
- get_chart_data: krx_local_data_mixin.py
- get_supply_data: krx_local_data_mixin.py
- _get_stock_name: krx.py
- _get_sector: krx.py

Ruling: 이미 검증된 모듈형 row parser를 유지해 numeric string/혼합영문 ticker 입력을 보존한다. 정상 legacy 입력결과는 동일하며 비정상 입력 처리만 모듈형 계약으로 수렴한다.

## 최종 정리

초기 50메서드 이동 지도 이후 ponytail 검토로 KRX 펀더멘털 private 캐시는 실제 호출자가 없어 제거했다. __aenter__/__aexit__는 같은 계약의 BaseCollector를 상속한다. _get_data_dir는 config.DATA_DIR를 같은 프로젝트 루트에서 해석하도록 추가했다.
