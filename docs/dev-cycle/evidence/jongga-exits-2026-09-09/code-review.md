# Code Review Summary

**검토 기준:** base `8febe19ad7d2a41301104b8efe5ff6bed7b3ccab`, `review-input-v4.json`, `review-v4.diff`

**Files Reviewed:** 32

**Total Issues:** 0

## By Severity

- CRITICAL: 0
- HIGH: 0
- MEDIUM: 0
- LOW: 0

## Verdict

**APPROVE**

JONGGA-012·013 명세의 코드·보안·품질 범위를 충족한다. 종가베팅 기본 가격은 공용 `+5%/-3%`로 통일됐고, 저장된 유효 목표가·손절가는 각 필드별로 우선된다. 누락·비정상 가격은 공용 해석 함수에서 보충되며 누락과 비정상 입력 모두 로그 증거를 남긴다. exact-price 경계는 pct 왕복 없이 가격 자체로 판정하고, 같은 일봉에서 목표·손절이 함께 충족되면 기존대로 손절을 우선한다.

요약과 누적성과는 같은 구조화 거래 계산을 재사용한다. raw `date` 컬럼/RangeIndex와 기존 DatetimeIndex를 모두 처리하며 원본 DataFrame을 변경하지 않는다. 요약은 누적성과와 같은 파일명 기준일을 사용하고, `ticker`/`stock_code`/`code` 과거 별칭을 유지한다. `price_map`은 후보 표시 갱신에만 쓰이며 일봉 유무에 따른 OPEN/집계 계약도 명세와 일치한다. 캐시 규칙 변경은 summary `1→2`, cumulative `4→5`로 무효화됐다.

최신·과거 날짜 응답 모두 동일 normalizer를 거친다. 과거 응답은 deepcopy 후 보정하므로 저장 파일을 덮어쓰지 않는다. 화면은 `entry_price`를 우선하고 과거 자료에만 `buy_price`를 fallback으로 쓰며, AI 원문을 React 텍스트로 그대로 표시하고 시스템 계산 가격의 출처를 별도로 설명한다. `dangerouslySetInnerHTML` 추가, 하드코딩된 비밀, 빈 catch, broad fallback, 실패를 숨기는 기본 반환은 발견하지 못했다. VCP 계산과 전용 화면 계약은 변경되지 않았다.

## 리뷰 중 발견 후 해소된 항목

- `services/kr_market_backtest_trade_helpers.py:223` — shared builder 도입 시 `code` 전용 또는 빈 `ticker`+유효 `stock_code` 신호가 누락될 수 있었으나 truthy alias 순서와 회귀 검사로 복구됐다.
- `services/kr_market_backtest_trade_helpers.py:159` — 한쪽 exact 가격이 반대쪽 사용자 지정 pct까지 기본값으로 바꾸던 호환 문제가 각 side별 해석과 로그 검사로 해소됐다.
- `app/routes/kr_market_data_jongga_routes.py:110` — 과거 날짜 응답의 누락 가격이 정규화되지 않아 카드에 0원으로 보일 수 있었으나 response copy 정규화와 HTTP 회귀로 해소됐다.
- `services/kr_market_analytics_service.py:364` — payload에 `date`가 없을 때 summary와 cumulative가 다른 기준일을 쓰던 문제가 기존 파일명 날짜 해석 재사용과 비변경 회귀로 해소됐다.

## Validation

- 변경된 TypeScript/TSX 파일별 진단: 0 diagnostics. 실제 `tsc --noEmit`, Next build, Vitest 424/424 통과.
- Python LSP 서버는 PATH에 없어 실행 불가. 대체 검증으로 변경 Python 15개 AST/compile 검사 통과, AST-grep 위험 패턴 0건, 관련 v4 회귀 77/77 통과.
- 전체 백엔드(최종 v4 보완 전): 2244 passed, 3 existing skipped. v4 보완은 관련 77개 회귀로 다시 검증됐다.
- ESLint: 0 errors, 기존 warnings 201건. 변경 범위 신규 오류 없음.
- `review-input-v4.json`의 생산 코드와 동작 검사는 현재 파일과 일치한다. 이후 `tests/services/test_kr_market_cumulative_cache.py`의 EOF 공백만 제거돼 SHA256이 `290e0d…`에서 `a6a8fb…`로 바뀌었고 코드·AST 변화는 없다(`whitespace-fix.json`). 현재 `git diff --check`는 깨끗하다. 제한된 재현 증거: `review-code-boundaries`, `review-code-mixed-pct`, `review-code-fixes-green`, `review-v4-green`.

## Reviewed Files

- `README.md`
- `app/routes/kr_market_data_jongga_routes.py`
- `app/routes/kr_market_jongga_normalize_helpers.py`
- `docs/dev-cycle/TODO.md`
- `docs/dev-cycle/qa/JONGGA-012.md`
- `docs/dev-cycle/qa/JONGGA-013.md`
- `docs/superpowers/plans/2026-09-09-jongga-exit-prices.md`
- `engine/config.py`
- `engine/constants_market.py`
- `engine/position_sizer.py`
- `frontend/src/app/components/ClosingBetCriteriaModal.tsx`
- `frontend/src/app/components/ClosingBetCriteriaModal.test.tsx`
- `frontend/src/app/dashboard/kr/closing-bet/page.tsx`
- `frontend/src/app/dashboard/kr/closing-bet/page.regression-jongga-015.test.tsx`
- `frontend/src/app/dashboard/kr/cumulative/CumulativeClientPage.tsx`
- `frontend/src/app/dashboard/kr/cumulative/CumulativeClientPage.regression-005.test.tsx`
- `frontend/src/app/dashboard/kr/page.tsx`
- `frontend/src/app/dashboard/kr/page.regression-flow-004.test.tsx`
- `services/kr_market_analytics_service.py`
- `services/kr_market_backtest_common.py`
- `services/kr_market_backtest_stats_helpers.py`
- `services/kr_market_backtest_summary_cache.py`
- `services/kr_market_backtest_trade_helpers.py`
- `services/kr_market_cumulative_cache.py`
- `tests/app/test_kr_market_helpers_contract.py`
- `tests/app/test_kr_market_jongga_helpers_refactor.py`
- `tests/app/test_kr_market_route_integration.py`
- `tests/engine/test_position_sizer_exit_prices.py`
- `tests/services/test_kr_market_analytics_service_refactor.py`
- `tests/services/test_kr_market_backtest_service.py`
- `tests/services/test_kr_market_backtest_summary_cache.py`
- `tests/services/test_kr_market_cumulative_cache.py`

## Low-confidence observations

- 홈 VCP 안내의 기존 `+9/-5`와 VCP 백테스트 `+15/-5` 불일치는 이번 변경이 만들지 않았고 `VCP-025`로 명시 이월됐다. 이번 종가베팅 승인 판정에는 포함하지 않았다.

**Stop condition:** v4 manifest와 이후 EOF 공백 제거 delta가 고정됐고, 리뷰 중 확인한 네 계약 문제가 소스와 회귀 검사에서 해소됐으며, 현재 범위에 미해결 CRITICAL/HIGH/MEDIUM/LOW finding이 없다.
