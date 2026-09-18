# Task 3 테스트 준비 보고

- 변경 파일: `frontend/src/app/dashboard/kr/page.regression-performance-batch.test.tsx`, `frontend/src/app/dashboard/kr/page.regression-flow-004.test.tsx`, `tests/app/test_performance_mock_20260918.py`.
- 구현 파일: `frontend/src/app/dashboard/kr/page.tsx`, `frontend/src/app/page.tsx`, `app/routes/common_market_mock_routes.py`, `frontend/src/app/dashboard/kr/vcp/page.tsx`.
- 고정한 화면 계약: 두 성과 카드는 `Accumulating`, `OK (New)`, `PENDING`, `unknown/undefined`에서 중립 라벨·건수·안내만 보이고 0%·평균·성적 조언·판정 아이콘을 보이지 않는다. `EXCELLENT`, `GOOD`, `BAD`에서만 실제 승률·평균·동일 테마·판정 아이콘을 보인다. `BAD`의 실제 0%도 성과 수치로 남긴다.
- 정책 문구 계약: VCP 백테스트는 `+15%/-5%`, 개별 시그널 기본은 `+5%/-3%`로 구분한다. 랜딩 종가베팅은 저장 목표·손절 우선, 누락 기본 `+5%/-3%`, 미청산 OPEN 계속 추적·승률 계산 제외, 승률 60% 가정 기대값 `+1.8%`와 비용 제외를 명시한다. 스코어링 탭도 같은 `+5%/-3%`, `+1.8%`로 정정했다. VCP 전용 화면의 저장 가격 툴팁도 같은 정책으로 구현했다.
- 정정 기록: 초기 회귀 기대값의 `OPEN 신호는 … 성과에서 제외`는 실제 KPI 계약과 달랐다. OPEN은 현재 평가가 총·평균 ROI에 남고 승률 분모에서만 빠지므로, 테스트와 문구를 `미청산(OPEN)은 계속 추적하며 승률 계산에서 제외합니다.`로 바꿨다.
- 경계 기록: `toString` 같은 프로토타입 키도 unknown으로 처리하는 회귀를 추가했다. zero count의 기존 표기는 `No trades`이므로, 상태 표시 작업에서 공통 건수 형식을 `0 trades`로 바꾸지 않고 테스트 기대만 제품 계약에 맞췄다.
- 문구 정정: 기준표의 이전 약식 평균 공식은 괄호와 수익률 합계를 생략해 연산 순서와 단위를 모호하게 했다. 계산은 바꾸지 않고 `(청산 수익률 합 + OPEN 평가수익률 합) / 전체 신호 수`로 명시했으며, 모달의 textContent 회귀도 같은 문구를 확인한다.
- 모의 라우트 계약: `/api/kr/backtest-summary`는 기존 수치 VCP 62.5/4.2/16에 `EXCELLENT`, 종가 58.3/3.8/12에 `GOOD`를 반환한다.
- 실행: 원본 작업 트리 실행 금지 규칙에 따라 테스트·서버·HTTP 요청을 실행하지 않았다. 부모 에이전트가 git archive scratch에서 GREEN 검증을 이어간다.
