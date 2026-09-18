# FLOW-009 mock 라우트 범위 확인

- app/__init__.py:251-252는 kr_bp를 /api/kr로 먼저, common_bp를 /api로 뒤에 등록한다.
- 실제 kr_market_data_backtest_stock_routes.py:33의 /backtest-summary와 common_market_mock_routes.py:95의 /kr/backtest-summary는 /api/kr/backtest-summary에서 겹친다. 현재 순서는 실제 kr 라우트가 우선한다.
- 같은 mock 파일의 GET /stock/<ticker>는 /api/stock/<ticker>, POST /realtime-prices는 /api/realtime-prices다. KR의 실시간 가격 POST는 /api/kr/realtime-prices로 주소가 다르다. 앞의 두 common route는 중복으로 가려진 동일 사례가 아니므로 삭제하지 않았다. 이는 등록/경로 대조이며 모든 신원으로 인가된다는 주장이 아니다.
- 이번 수정은 backtest mock의 기존 수치 62.5/58.3에 맞게 status만 EXCELLENT/GOOD로 정렬한다. standalone 실제 Flask route 회귀를 실행했고, 원본의 GET/POST를 실측하지 않았다.
