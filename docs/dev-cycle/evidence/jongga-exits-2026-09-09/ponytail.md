services/kr_market_backtest_stats_helpers.py:L64: shrink: `build_cumulative_trade_record`가 ticker·entry 유효성을 이미 검사하고 `None`으로 거부하므로 L64-L78의 같은 전처리를 삭제하고 L80의 공용 진입점만 신뢰하면 계약은 그대로이고 15줄이 줄어듭니다.
services/kr_market_backtest_trade_helpers.py:L238: shrink: 여기서 `resolve_jongga_exit_prices`로 보정한 값을 L158에서 다시 같은 함수에 넣고 있습니다. 저장 원값을 metrics 호출에 넘겨 L158 한 곳에서만 보정하면 중복 계산·중복 계약 없이 5줄을 줄일 수 있습니다.
tests/services/test_kr_market_backtest_summary_cache.py:L274: delete: 이 테스트는 signature를 직접 두 개 만들어 서로 다른 키의 조회가 miss인지 다시 검사할 뿐 실제 schema signature 생성기를 거치지 않습니다. L471의 `test_schema_version_participates_in_the_signature`와 기존 save/get 검사가 각각 배선과 저장 계약을 이미 고정하므로 13줄을 삭제할 수 있습니다.
tests/services/test_kr_market_cumulative_cache.py:L492: delete: 바로 위 L445의 `test_bumping_schema_version_drops_payloads_saved_under_the_old_rule`가 실제 signature builder로 버전을 올리고 이전 payload miss까지 더 강하게 검증합니다. 수동 signature로 같은 동작을 반복하는 L492-L508은 17줄 전부 삭제할 수 있습니다.
net:-50 lines possible
