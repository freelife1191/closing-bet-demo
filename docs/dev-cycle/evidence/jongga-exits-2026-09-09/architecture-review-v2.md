# Architecture Review v2

## Summary

`BLOCK`. 승인된 핵심 설계인 공용 +5%/-3%, 저장 가격 우선, 요약·누적성과의 동일 판정, exact-price 직접 비교, 캐시 버전 증가는 코드에 연결되어 있다. 다만 요약을 공용 trade builder로 합치면서 기존에 허용하던 티커 별칭 입력 계약이 축소되어 일부 과거 신호가 통계와 누적성과에서 조용히 누락된다.

## Analysis

### BLOCK — 공용 trade 경계가 기존 티커 별칭을 잃는다

- `services/kr_market_backtest_stats_helpers.py:64`-`69`는 종가 요약의 모든 신호를 `build_cumulative_trade_record`에 위임한다. 통합 자체는 요약과 누적성과의 판정 드리프트를 없애는 올바른 방향이다.
- v2의 `services/kr_market_backtest_trade_helpers.py:226`은 `signal.get("ticker", signal.get("stock_code", ""))`를 사용한다. `code`만 있는 신호는 지원하지 않고, `ticker` 키가 존재하지만 빈 문자열 또는 `None`이면 유효한 `stock_code`로도 폴백하지 않는다.
- 변경 전 요약은 `stock_code or code or ticker`를 순서대로 해석했고, 현재 저장소의 공용 프론트 정규화 경계도 `stock_code`, `ticker`, `code`를 모두 허용한다(`app/routes/kr_market_jongga_normalize_helpers.py:66`-`69`). 따라서 이번 기능과 무관한 입력 호환성이 공용화 과정에서 줄었다.
- 제한 재현 `evidence/review-arch-contract-v2.log`에서 v2 manifest의 모든 파일 해시가 일치한 상태로 `code_only_count=0`, `empty_ticker_trade=None`을 확인했다. 같은 실행에서 표준 `stock_code` 입력은 요약 `EXCELLENT/100%`, 누적 trade `WIN/9.0`으로 정상 처리됐다.
- 영향은 예외가 아니라 조용한 데이터 누락이다. builder가 `None`을 반환하면 요약은 해당 신호를 세지 않고(`services/kr_market_backtest_stats_helpers.py:70`-`73`), 누적 라우트도 trade를 추가하지 않는다(`app/routes/kr_market_data_ai_routes.py:151`-`159`).

### 승인된 가격 판정 구조는 의도대로 연결된다

- 공용 기본값은 `engine/constants_market.py:53`-`55`의 +5%/-3%이고, `SignalConfig`가 이를 직접 참조한다(`engine/config.py:52`-`55`). 생성 정상·예외 경로 모두 같은 config 필드를 사용한다(`engine/position_sizer.py:40`-`45`, `engine/position_sizer.py:65`-`74`).
- 저장 가격의 유효성은 공용 resolver에서 유한성, 양수, 진입가의 올바른 방향으로 검사하고 한쪽씩 보충한다(`services/kr_market_backtest_common.py:74`-`104`). 프론트 정규화도 이 resolver를 사용하므로 저장된 유효 가격을 보존하고 누락·비정상 값만 채운다(`app/routes/kr_market_jongga_normalize_helpers.py:104`-`112`).
- exact price는 pct로 되돌리지 않고 `high >= resolved_target`, `low <= resolved_stop`으로 직접 비교한다(`services/kr_market_backtest_trade_helpers.py:158`-`178`). 요약과 누적성과가 동일한 구조화 결과를 소비한다(`services/kr_market_backtest_stats_helpers.py:64`-`78`, `services/kr_market_backtest_trade_helpers.py:243`-`260`). 제한 재현에서는 target 109 경계가 정확히 `WIN/9.0`이었고 원본 raw frame도 불변이었다(`evidence/review-arch-contract-v2.log`).
- 같은 일봉의 양쪽 hit는 공용 판정에서 손절 우선이다(`services/kr_market_backtest_common.py:117`-`129`). OPEN은 관측된 마지막 close로 ROI를 계산하고 가격이 없으면 OPEN/0을 유지한다(`services/kr_market_backtest_trade_helpers.py:184`-`213`). 이는 승인된 요약·누적 의미 통일과 일치한다.
- 생산 raw group은 ticker/date 컬럼과 RangeIndex를 가지며 metrics 진입 시 복사·DatetimeIndex 변환된다(`services/kr_market_backtest_trade_helpers.py:41`-`60`, `services/kr_market_backtest_trade_helpers.py:131`-`148`). 원본 frame을 복사하는 경계도 확인됐다.
- 캐시 계산 규칙 버전은 summary 2(`services/kr_market_backtest_summary_cache.py:38`-`40`), cumulative 5(`services/kr_market_cumulative_cache.py:51`-`53`)이고 두 signature에 버전이 포함된다(`services/kr_market_backtest_summary_cache.py:253`-`259`, `services/kr_market_cumulative_cache.py:191`-`197`). 이전 규칙의 메모리·SQLite 키와 충돌하지 않는다.
- VCP 계산 경로는 여전히 +15%/-5%의 독립 시나리오 API를 사용한다(`services/kr_market_backtest_stats_helpers.py:123`-`149`). 홈의 기존 +9%/-5% 문구는 종가 분기와 분리되어 유지되므로 승인된 VCP-025 이월 경계를 넘지 않는다(`frontend/src/app/dashboard/kr/page.tsx:538`-`542`).

### WATCH — DataFrame 정규화 함수의 직접 호출 계약은 생산 형태보다 좁다

- `prepare_cumulative_price_dataframe`은 date와 ticker가 모두 없으면 빈 frame을 반환한다(`services/kr_market_backtest_trade_helpers.py:41`-`46`). metrics는 date 컬럼만 보고 이를 호출한 뒤 곧바로 index와 `Timestamp`를 비교한다(`services/kr_market_backtest_trade_helpers.py:131`-`148`).
- 제한 재현 `evidence/review-arch-shapes.log`에서 ticker 없는 date-column frame은 `TypeError`, 숫자형 `YYYYMMDD`는 1970년 나노초로 해석되어 OPEN/0, DatetimeIndex이지만 문자열 OHLC인 frame은 비교 `TypeError`가 났다.
- 이 경계는 승인된 생산 계약인 `{date,ticker,high,low,close}`와 ISO 날짜를 벗어나므로 v2의 별도 blocker로 올리지는 않는다. 다만 `calculate_cumulative_trade_metrics`가 facade에서 공개되어 있어 향후 직접 호출자가 생산 loader의 dtype 보장을 우회하면 실패가 예외 또는 조용한 OPEN으로 나타난다.

## Root Cause

요약 계산을 누적성과의 공용 trade builder로 합치면서 판정 로직은 통일됐지만, 요약의 기존 티커 해석 계약까지 builder의 더 좁은 계약으로 치환했다. 공용화 경계에서 계산 정책뿐 아니라 입력 별칭·결측 폴백도 합집합으로 보존했어야 한다.

## Recommendations

1. `services/kr_market_backtest_trade_helpers.py:226`의 식별자 해석을 `ticker or stock_code or code`의 truthy 폴백으로 복구한다 — 낮은 노력, 과거/혼합 schema 신호의 조용한 누락 방지.
2. `code`-only, 빈 `ticker`+유효 `stock_code`, `None ticker`+유효 `stock_code`를 요약과 누적 builder 양쪽의 동일 fixture로 고정한다 — 낮은 노력, 공용 경계 회귀 방지.
3. 직접 metrics API의 허용 DataFrame schema를 문서화하거나, date-column 입력의 ticker 부재·숫자 날짜·문자열 OHLC를 명시적으로 검증한다 — 중간 노력, facade 직접 호출의 실패 형태를 예측 가능하게 만듦. 생산 경로가 현재 계약을 지키므로 후속 항목으로 분리할 수 있다.

## Architectural Status

`BLOCK`

## Trade-offs

| Option | Pros | Cons |
|---|---|---|
| 공용 builder에서 세 별칭을 truthy 폴백 | 기존 요약 호환성과 누적성과 일관성을 함께 보존; 변경이 한 줄로 국소적 | 서비스 경계가 세 schema 별칭을 계속 알아야 함 |
| 저장 schema를 `ticker` 하나로 강제 | 장기적으로 입력 계약이 단순해짐 | 기존 저장 자료 마이그레이션이 필요하고 이번 승인 범위를 벗어남; 누락 위험이 큼 |
| DataFrame 경계를 지금 넓게 정규화 | 공개 helper가 다양한 직접 입력에 견고해짐 | 생산 계약 밖 범위를 넓히고 이번 변경의 diff와 검증 부담이 증가함 |

## Strongest Counterargument

실제 `Signal.to_dict()` 저장 경로는 `stock_code`를 항상 만들기 때문에(`engine/models.py:80`-`95`, `engine/generator_result_storage.py:36`-`40`) `code`-only 또는 빈 `ticker` 혼합 자료가 현재 생산 파일에 없을 수 있다. 따라서 별칭 복구 없이도 현재 생성 자료의 +5%/-3% 결과는 맞을 수 있다. 그러나 변경 전 요약과 공용 정규화가 해당 별칭을 명시적으로 받아 왔고, 실패가 오류가 아닌 통계 누락으로 나타나므로 호환성 축소를 정당화할 근거가 없다.

## Validation

- v2 입력 해시: `review-input-v2.json`의 모든 파일 SHA256 일치 — `evidence/review-arch-contract-v2.log`.
- exact target 109, raw date/RangeIndex, 원본 frame 불변, 요약·누적 동일 WIN 결과 통과 — `evidence/review-arch-contract-v2.log`.
- DataFrame 경계 재현 — `evidence/review-arch-shapes.log`.
- 전체 suite는 이 레인에서 재실행하지 않았다. 제공 증거는 backend 2244 pass/3 기존 skip, frontend 424 pass이며, v2 이후 파일 변경 전의 결과로 취급한다.
