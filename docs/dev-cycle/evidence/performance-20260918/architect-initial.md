## Summary

아키텍처 상태는 `WATCH`입니다. 차단 결함은 없으며, 최종 14개 SHA가 `review-input.json`과 일치하고 백엔드 전체 집계 → 캐시 → 페이지네이션 경계도 올바릅니다. 다만 전체 KPI와 현재 페이지 필터의 의미가 화면에서 명시되지 않고, 최근 통계 표본 수와 좁은 화면 카드 높이는 최종 QA에서 확인해야 합니다.

신뢰도: 코드·계약 `높음(0.94)`, 시각 배치 `중간(0.70, S-8 미실행)`.

## Analysis

### 확인된 설계 정합성

- 전체 거래로 KPI와 최근 통계를 계산한 뒤 캐시하고, 그 후 거래 목록만 페이지네이션합니다. 따라서 KPI·D 등급·최근 지표가 페이지별 행에 오염되지 않습니다. `app/routes/kr_market_data_ai_routes.py:161-186`
- 최근 통계는 `WIN/LOSS`만 추천일·코드·ID 내림차순으로 정렬하고, 최근 최대 10건 승률과 전체 최신 연패를 각각 계산합니다. OPEN은 여기서 제외됩니다. `services/kr_market_backtest_kpi_helpers.py:93-115`
- OPEN의 평가 ROI는 전체·등급별 합계와 평균에 계속 포함되고, 승률 분모에서만 제외됩니다. `services/kr_market_backtest_kpi_helpers.py:36-67`, `tests/services/test_kr_market_backtest_service.py:675-698`
- D는 누락 없이 등급 누산·API 계약·화면 기본값·카드·필터에 추가됐습니다. `services/kr_market_backtest_kpi_helpers.py:28-31`, `frontend/src/app/dashboard/kr/cumulative/CumulativeClientPage.tsx:42-47`, `frontend/src/app/dashboard/kr/cumulative/CumulativeClientPage.tsx:908-910`, `frontend/src/app/dashboard/kr/cumulative/CumulativeClientPage.tsx:987-997`
- 캐시 스키마 6이 시그니처에 포함되므로 version 5 payload가 메모리·SQLite 경계에서 재사용되지 않습니다. `services/kr_market_cumulative_cache.py:51-58`, `services/kr_market_cumulative_cache.py:175-197`, `tests/services/test_performance_batch_20260918.py:155-178`
- 입력 계약은 빈 입력의 기존 OPEN 반환을 유지하면서, nonempty frame의 필수 OHLC·실수형 숫자·ISO date+ticker 또는 naive 오름차순 DatetimeIndex를 명시적으로 검증합니다. `services/kr_market_backtest_trade_helpers.py:124-167`
- 정책도 보존됐습니다. 종가베팅은 저장 가격 우선·누락 시 +5/-3이고, VCP 요약 백테스트만 +15/-5입니다. `services/kr_market_backtest_common.py:74-104`, `engine/constants_market.py:53-55`, `services/kr_market_backtest_stats_helpers.py:134-149`, `frontend/src/app/dashboard/kr/page.tsx:597-607`
- 상태 표는 현재 백엔드의 여섯 어휘와 일치하며, 알 수 없는 값은 중립으로 실패 안전 처리합니다. `services/kr_market_backtest_stats_helpers.py:36-40`, `services/kr_market_backtest_stats_helpers.py:80-88`, `services/kr_market_backtest_common.py:58-71`, `frontend/src/app/dashboard/kr/page.tsx:34-87`

### WATCH 1 — 페이지 필터의 범위가 UI에서 모호함

필터는 서버가 이미 페이지네이션한 `trades`에만 적용되며, 건수도 현재 페이지 기준입니다. 하지만 화면은 이를 “현재 페이지 필터”라고 설명하지 않습니다. 사용자가 D 필터를 전체 이력 검색으로 해석하면 결과가 불완전해 보일 수 있습니다. `frontend/src/app/dashboard/kr/cumulative/CumulativeClientPage.tsx:978-983`, `frontend/src/app/dashboard/kr/cumulative/CumulativeClientPage.tsx:1129-1147`

현재 승인 범위에서는 서버 필터 API까지 확장할 필요가 없습니다. 최소 보수는 필터 영역에 “현재 페이지 내”를 표시하는 것입니다. 전체 이력 필터가 제품 요구라면 이후 `grade/outcome` 쿼리와 필터 기준 pagination metadata를 서버에 추가해야 합니다.

### WATCH 2 — 최근 표본이 1~9건이어도 “최근 10건”으로 표시됨

백엔드는 실제 `recentClosedCount`를 제공하지만 화면 라벨은 항상 “최근 10건 승률”입니다. 종료 거래가 2건이면 계산은 정확해도 표본 설명은 부정확합니다. `frontend/src/app/dashboard/kr/cumulative/CumulativeClientPage.tsx:615-618`, `frontend/src/app/dashboard/kr/cumulative/CumulativeClientPage.tsx:675-684`

테스트는 10건과 0건만 고정하고 1~9건 UI를 다루지 않습니다. `frontend/src/app/dashboard/kr/cumulative/CumulativeClientPage.regression-performance-batch.test.tsx:165-205`
`최근 청산 ${recentClosedCount}건 승률` 또는 `최근 최대 10건 승률`이 정확합니다.

### WATCH 3 — 비동기 응답 순서 경합

페이지·페이지 크기가 빠르게 바뀌면 이전 요청이 늦게 도착해 최신 state를 덮을 수 있습니다. 현재 effect에는 AbortController나 요청 세대 번호가 없습니다. 이 경우 선택기는 새 페이지를 가리키면서 표·pagination·KPI는 이전 응답을 표시할 수 있습니다. `frontend/src/app/dashboard/kr/cumulative/CumulativeClientPage.tsx:938-976`

이번 변경이 새로 만든 결함은 아니지만, 전체 KPI와 페이지 행의 일관성을 강조한 작업이므로 후속 보강 후보입니다.

### WATCH 4 — 시각 QA가 필요한 고정 높이

평균·누적 ROI 카드는 4개 등급 상세를 추가했지만 `StatCard` 기본 높이는 `h-24`입니다. `md:grid-cols-6`의 좁은 카드에서 등급 상세가 두 줄로 감기면 넘침 가능성이 있습니다. 아직 제품 실패로 확정할 근거는 없습니다. `frontend/src/app/dashboard/kr/cumulative/CumulativeClientPage.tsx:366-386`, `frontend/src/app/dashboard/kr/cumulative/CumulativeClientPage.tsx:1053-1075`

필수 S-8이 이 위험을 정확히 다루지만 현재 QA 문서는 미실행 상태입니다. `docs/dev-cycle/qa/batch-performance-2026-09-18.md:21-27`

## Task Coverage

- **Task 1:** 충족. D, 정렬/tie, OPEN 제외, 종료 없음, 8개 invalid frame, 정상 2형태, cache version 회귀가 있습니다. `tests/services/test_performance_batch_20260918.py:18-178`
- **Task 2:** 정적·회귀 범위 충족. D 카드/필터, 서버 KPI 직접 사용, 페이지 전환 안정성, null 최근 통계를 고정합니다. `frontend/src/app/dashboard/kr/cumulative/CumulativeClientPage.regression-performance-batch.test.tsx:140-205`
- **Task 3:** 충족. 여섯 상태+unknown·prototype key, 두 카드 일관성, VCP +15/-5와 개별 +5/-3, OPEN 문구, mock status가 고정됐습니다. `frontend/src/app/dashboard/kr/page.regression-performance-batch.test.tsx:75-162`, `tests/app/test_performance_mock_20260918.py:45-67`
- **Task 4:** 정적 검증은 통과했지만 필수 브라우저 QA 10개는 아직 미실행입니다. `docs/dev-cycle/qa/batch-performance-2026-09-18.md:12-27`

검증 증거는 pytest 2310/3 skip, Vitest 501/71, lint 0 error/190 warning, build 3/3, 프로젝트 `tsc --noEmit` exit 0입니다. `diagnostics.md`의 잘못된 LSP 판정은 성공 근거로 사용하지 않았습니다. `docs/dev-cycle/evidence/performance-20260918/pytest-final.log:34`, `docs/dev-cycle/evidence/performance-20260918/vitest-final2.log:1762`, `docs/dev-cycle/evidence/performance-20260918/lint-final2.log:343`, `docs/dev-cycle/evidence/performance-20260918/build-final2.log:46`, `docs/dev-cycle/evidence/performance-20260918/typecheck-final2.log:1-2`

## Root Cause

API는 전체 범위 KPI와 페이지 범위 거래를 한 응답에 함께 담지만, 범위 정보가 타입이나 UI 라벨로 표현되지 않습니다. 구현과 테스트는 범위를 올바르게 분리했으나 사용자는 필터·최근 표본의 실제 범위를 화면만 보고 정확히 알기 어렵습니다.

## Recommendations

1. **필수 QA 진행** — 낮은 노력 — S-8에서 1280×720·375×812의 `h-24` 넘침을 확인하고, 실패 시 ROI 카드만 `h-auto min-h-24`로 조정.
2. **범위 문구 보강** — 낮은 노력 — 필터에 “현재 페이지 내”, 최근 통계에 실제 `recentClosedCount`를 표시.
3. **요청 순서 보호** — 낮은~중간 노력 — 누적 API effect에 AbortController 또는 request sequence guard 추가.
4. **상태 타입 강화** — 낮은 노력 — `status?: string`을 상태 union으로 좁히고 `judged`를 presentation 정의에 포함해 상태 목록과 판정 목록의 이중 관리를 제거. 현재 unknown fallback은 유지.

## Architectural Status

`WATCH`

차단 사유는 없습니다. 가장 강한 반론은 “전체 KPI 화면에 붙은 필터와 최근 10건 표기가 실제로는 현재 페이지 필터와 최대 10건 표본”이라는 범위 오해 가능성입니다. 백엔드·캐시 구조는 유지하고 UI에 범위를 명시하는 것이 가장 작은 합성안입니다.
