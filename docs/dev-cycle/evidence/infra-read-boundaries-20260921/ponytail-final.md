실제 delta 검증 결과 **SHIP**입니다.

- `services/kr_market_market_gate_validity.py`의 `resolve_market_gate_filename`이 ASCII `[0-9]` 기반 `YYYY-MM-DD`/`YYYYMMDD`만 허용하고 `datetime.strptime`로 달력 유효성까지 검사합니다.
- `app/routes/kr_market_system_http_routes.py`는 `ValueError`를 loader 호출 전에 400으로 반환하며, 현재 invalid date 테스트가 경로 탐색·loader 미호출을 고정합니다.
- scheduler는 새 감시 스레드 없이 `_ensure_paper_trading_sync`를 leader bootstrap에서 즉시 1회 호출하고 `paper_price_sync` tagged 1분 job으로 재시도합니다. bootstrap에서 기존 tag를 clear하므로 중복 job 누적도 없습니다.
- 테스트는 sync 시작 실패 후 tagged job 재호출 복구와 scheduler lock/disabled 경계를 고정합니다.

`_needs_update`는 의도적으로 GET 갱신 판단을 버리고 validity/fallback 계산만 유지하는 자리의 무시 반환값이며, 이번 delta의 과잉 helper나 불필요한 감시 경로는 발견되지 않았습니다.
