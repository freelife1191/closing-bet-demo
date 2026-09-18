# Task 1 테스트 준비 보고

- 변경 파일: `tests/services/test_performance_batch_20260918.py`
- 구현 파일: `services/kr_market_backtest_kpi_helpers.py`, `services/kr_market_backtest_trade_helpers.py`, `services/kr_market_cumulative_cache.py`.
- 구현 범위: D 등급 KPI, 추천일 기준 최근 10건 정렬(`date`, `code`, `id` 내림차순), 종료 거래 없음, 비어 있지 않은 가격 프레임의 세 가지 거부 경계, 정상 정규화/생산 가격 입력 보존, 캐시 스키마 6.
- 캐시 회귀는 상수값 직접 비교 대신 version 5 시그니처로 저장한 payload가 version 6 시그니처에서 재사용되지 않는지 확인한다.
- 생산 경로 정정: cold CSV 입력은 ISO 문자열 date이지만, warm SQLite CSV snapshot은 `pd.read_json(..., orient="split")`에서 date 열을 naive `datetime64`로 복원한다. 이 frame은 `load_backtest_price_snapshot`→`build_ticker_price_index`→`calculate_jongga_backtest_stats`로 전달되므로, helper 경계는 ISO 문자열과 이 기존 naive datetime64 표현을 모두 허용해야 한다.
- date 열 허용 하한: ticker·실수/정수 OHLC와 함께 strict ISO `YYYY-MM-DD` 문자열 또는 SQLite가 복원한 naive·결측 없음·자정 `datetime64`만 받는다. timezone-aware·NaT·시간이 포함된 datetime은 거부한다.
- 추가 입력 경계: 정규화된 `DatetimeIndex`의 하한은 naive·결측 없음·오름차순이며, OHLC는 실수/정수 수치 열이어야 한다. timezone-aware 또는 비정렬 index, complex OHLC는 계산 단계의 비교 예외·첫-hit 오판정을 막기 위해 경고 후 `ValueError`로 거부한다.
- 실행: 원본 작업 트리 실행 금지 규칙에 따라 실행하지 않았다. 부모 에이전트가 git archive scratch에서 GREEN 및 기존 service/cache 회귀를 검증한다.
