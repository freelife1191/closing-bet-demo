## Summary

영향 재검토 결과 `CLEAR`입니다. warm SQLite가 실제로 만드는 `datetime64` 표현을 consumer 경계에서 좁게 허용한 수정은 타당하며, 기존 거부 계약을 약화하지 않았습니다. 홈페이지 기준표도 실제 백엔드 계산식과 일치합니다.

신뢰도: `높음(0.97)`.

## Analysis

### Producer/consumer 경계

- generic CSV SQLite serializer는 `date_format="iso"`로 저장하지만 `pd.read_json(..., orient="split")`이 날짜를 `datetime64`로 추론해 복원합니다. `services/kr_market_data_cache_sqlite_payload.py:673-681`, `services/kr_market_data_cache_sqlite_payload.py:703-714`
- 이 frame은 별도 정규화 없이 `load_backtest_price_snapshot`에서 반환되어 백테스트 계산기로 전달됩니다. `services/kr_market_data_cache_prices.py:210-230`
- 따라서 ISO 문자열만 받던 consumer 검증은 실제 생산 warm 경로와 충돌했습니다. RED 기록도 `datetime64` date가 동일 경계에서 거부됐음을 직접 보여줍니다. `docs/dev-cycle/evidence/performance-20260918/backend-sqlite-red.log:31-59`, `docs/dev-cycle/evidence/performance-20260918/backend-sqlite-red.log:106-125`

수정은 허용 범위를 다음 두 생산 표현으로 제한합니다.

- canonical `YYYY-MM-DD` 문자열
- dtype이 datetime64이고 timezone-naive, NaT 없음, 자정인 값

`services/kr_market_backtest_trade_helpers.py:147-167`

숫자 YYYYMMDD, 문자열 OHLC, timezone-aware date/index, NaT, 시간이 포함된 datetime, 비정렬 DatetimeIndex, 복소 OHLC는 계속 거부됩니다. `tests/services/test_performance_batch_20260918.py:90-147`

### 대안 평가

| 선택 | 장점 | 단점 |
|---|---|---|
| 현재 수정: 계산 경계에서 두 실제 생산 표현 허용 | 변경이 한 consumer 계약에 국한되고 generic cache에 영향 없음 | pandas 복원 표현을 계약에 명시해야 함 |
| generic SQLite 역직렬화 변경 | 모든 warm frame을 원래 문자열처럼 만들 수 있음 | 공용 캐시의 다른 소비자 dtype까지 바꾸는 넓은 영향 |
| snapshot loader에서 문자열로 재변환 | 이 producer만 정규화 가능 | 이미 계산 경계가 맡는 날짜 검증·정규화를 중복하고 다른 snapshot 소비자 표현을 바꿈 |

현재 선택이 가장 작고 안전합니다. warm SQLite 실제 흐름을 cold 저장 → 메모리 제거 → SQLite 복원 → 실제 `calculate_jongga_backtest_stats`까지 연결해 count 1, win 100%, avg 5%를 검증합니다. `tests/services/test_performance_batch_20260918.py:170-212`

### 성과 설명 정합성

홈 기준표의 새 문구는 실제 구현과 일치합니다.

- 승률: `WIN / (WIN + LOSS)`, OPEN 제외. `services/kr_market_backtest_stats_helpers.py:73-86`
- 평균: 청산 ROI와 OPEN 평가 ROI의 합을 전체 신호 수로 나눔. `services/kr_market_backtest_stats_helpers.py:73-86`
- VCP도 모든 처리 신호의 scenario return을 `total_count`로 나누며, 승률만 종료 거래를 분모로 사용합니다. `services/kr_market_backtest_stats_helpers.py:144-157`
- 화면 문구와 실제 모달 회귀가 이를 고정합니다. `frontend/src/app/dashboard/kr/page.tsx:124-144`, `frontend/src/app/dashboard/kr/page.regression-performance-batch.test.tsx:147-160`

### 변경 범위

before-deep-fix 대비 변경된 SHA는 정확히 네 파일입니다.

- `services/kr_market_backtest_trade_helpers.py`
- `tests/services/test_performance_batch_20260918.py`
- `frontend/src/app/dashboard/kr/page.tsx`
- `frontend/src/app/dashboard/kr/page.regression-performance-batch.test.tsx`

`docs/dev-cycle/evidence/performance-20260918/review-input-before-deep-fix.json:7-20`, `docs/dev-cycle/evidence/performance-20260918/review-input.json:7-20`

누적 UI 두 파일은 이전 `CLEAR` SHA와 동일합니다.

## Verification

- pytest: 2314 passed, 3 skipped. `docs/dev-cycle/evidence/performance-20260918/pytest-deep-fix.log:34`
- Vitest: 71 files, 506 tests passed. `docs/dev-cycle/evidence/performance-20260918/vitest-deep-fix.log:1760-1761`
- lint: 0 errors, 기존 190 warnings. `docs/dev-cycle/evidence/performance-20260918/lint-deep-fix.log:343`
- build: 3/3 passed. `docs/dev-cycle/evidence/performance-20260918/build-deep-fix.log:48-49`
- typecheck: exit 0. `docs/dev-cycle/evidence/performance-20260918/typecheck-deep-fix.json:6-15`

## Root Cause

입력 계약을 cold CSV의 문자열 표현만 보고 정의해, 같은 데이터를 warm SQLite가 복원할 때의 datetime64 표현을 생산 계약에서 누락한 것이 원인이었습니다. 수정은 serializer 전체를 바꾸지 않고 실제 두 생산 표현을 계산 경계에 명시해 해결했습니다.

## Architectural Status

`CLEAR`

새 cache version이나 공용 serializer 변경은 필요하지 않습니다. 잘못된 strict guard는 아직 배포되지 않은 중간 변경이므로 구 규칙으로 생성된 운영 캐시도 존재하지 않습니다. 예정된 동적 S-8 QA는 이전 UI 검증 게이트로 계속 수행하면 됩니다.

## 위 운영 캐시 문장의 철회 — reviewer 후속 원문

정정합니다.

기존 문장의 “구 규칙으로 생성된 운영 캐시도 존재하지 않습니다”는 증거 범위를 넘는 단정이므로 철회합니다. 확인된 사실은 부모가 원본 3500/5501 요청·재시작·배포를 수행하지 않았고, 검증이 격리 scratch에서만 실행됐다는 점입니다. 운영 환경의 캐시 존재 여부는 조사하지 않았으므로 알 수 없습니다.

코드 판정 `CLEAR`, consumer 경계에서의 제한적 허용, 공용 serializer를 변경하지 않은 판단은 그대로 유지합니다. 보고서에는 다음처럼 적는 것이 정확합니다.

> 이번 검증은 격리 scratch에서 수행됐으며 운영 환경의 캐시 상태는 확인하지 않았다. 공용 serializer를 바꾸지 않고 실제 cold/warm 생산 표현을 계산 경계에서 허용한 코드 수정의 타당성만 확인했다.
