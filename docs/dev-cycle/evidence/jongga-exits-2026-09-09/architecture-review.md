# Architecture Review

## Summary

`WATCH`. v2에서 확인한 티커 별칭 누락 blocker와 후속 독립 리뷰의 혼합 exact/pct, 과거 조회 정규화, 파일명 기준일 결합 문제가 모두 공용 경계에서 수선됐다. 승인된 +5%/-3%, 저장 exact 가격 우선, entry 정본, 요약·누적 동일 결과, 캐시 2/5, AI 원문 보존, VCP 불변 설계는 생산 호출부까지 일관되게 연결되어 있으며 현재 남은 위험은 문서화된 생산 DataFrame 형식 밖에서 공개 metrics helper를 직접 호출하는 경우다.

## Analysis

### 공용 가격 정책과 생성 경로

- 종가베팅 기본값은 `engine/constants_market.py:53`-`55`의 +5%/-3% 한 곳에 있고, `SignalConfig`가 그대로 참조한다(`engine/config.py:52`-`55`). 생성 정상 경로와 예외 폴백도 모두 인스턴스 config의 동일 비율을 사용하므로 사용자 지정 8%/-4%가 예외 시 5%/-3%로 되돌아가지 않는다(`engine/position_sizer.py:40`-`45`, `engine/position_sizer.py:65`-`74`).
- 저장 가격 해석은 `resolve_jongga_exit_prices`에서 entry 유한성·양수와 target/stop 방향을 검사하고 유효한 쪽은 보존하며 잘못된 쪽만 기본값으로 보충한다(`services/kr_market_backtest_common.py:74`-`104`). 프론트 응답 정규화도 같은 resolver를 사용한다(`app/routes/kr_market_jongga_normalize_helpers.py:104`-`112`).
- 과거 날짜 조회는 payload를 deep copy한 뒤 같은 normalizer를 적용하므로 응답에는 누락 가격이 보충되지만 저장 원문과 AI reason은 바뀌지 않는다(`app/routes/kr_market_data_jongga_routes.py:103`-`113`). 이 계약은 저장 파일 byte 불변까지 검사한다(`tests/app/test_kr_market_route_integration.py:626`-`642`).

### exact 가격 정밀도와 요약·누적성과 일치

- metrics는 명시 target/stop을 pct로 환산했다가 재구성하지 않고 최종 가격을 `high >= target`, `low <= stop`에 직접 비교한다(`services/kr_market_backtest_trade_helpers.py:159`-`183`). target 101/entry 100과 target 109의 정확 경계·경계 직전 값 회귀가 이를 고정한다(`tests/services/test_kr_market_backtest_service.py:83`-`117`).
- 한쪽 exact 가격만 주어진 경우 다른 쪽은 해당 legacy pct 인자로 계산한 뒤 공용 유효성 검사를 거친다(`services/kr_market_backtest_trade_helpers.py:159`-`167`). 이로써 exact 한쪽을 추가했다고 사용자 지정 반대쪽 비율이 전역 기본값으로 바뀌지 않는다. 두 누락 side의 INFO 로그도 해당 경계에서 남는다(`services/kr_market_backtest_trade_helpers.py:159`-`162`, `tests/services/test_kr_market_backtest_service.py:768`-`777`).
- 같은 일봉의 양쪽 hit는 공용 `resolve_hit_outcome`에서 손절 우선이다(`services/kr_market_backtest_common.py:117`-`129`). 미도달 OPEN은 마지막 유효 close로 ROI를 계산하고 가격이 없으면 OPEN/0을 유지한다(`services/kr_market_backtest_trade_helpers.py:185`-`214`).
- 종가 요약은 이제 cumulative trade record의 구조화된 `outcome`과 `roi`를 직접 집계한다(`services/kr_market_backtest_stats_helpers.py:64`-`86`). 누적성과 라우트도 같은 record builder를 사용하므로 두 소비자가 별도 float 임계값으로 승패를 재해석하지 않는다(`app/routes/kr_market_data_ai_routes.py:141`-`165`).
- summary가 읽는 payload 기준일은 cumulative와 같은 파일명 추출기를 거친다. payload에 date가 없거나 어긋나도 `jongga_v2_results_YYYYMMDD.json`의 날짜가 우선하며 원본 payload는 spread copy로 보존된다(`services/kr_market_analytics_service.py:363`-`368`). 날짜 없는 history의 WIN/+5 결과와 입력 불변 검사가 있다(`tests/services/test_kr_market_analytics_service_refactor.py:766`-`784`).
- entry는 계산 경계에서 필수 정본이고 NaN/±Infinity/0 이하는 trade 자체를 만들지 않는다(`services/kr_market_backtest_trade_helpers.py:231`-`234`). UI만 과거 표시 호환을 위해 유효한 entry가 없을 때 `buy_price`를 사용하고, 비율 표시는 entry 우선으로 계산한다(`frontend/src/app/dashboard/kr/closing-bet/page.tsx:1954`-`1967`).

### 숨은 결합과 입력 별칭 수선

- 공용 builder는 `ticker or stock_code or code`의 truthy 폴백으로 세 기존 schema를 받아들인다(`services/kr_market_backtest_trade_helpers.py:217`-`229`). v2의 `dict.get` 기본값 방식이 `code`-only 및 빈 ticker+유효 stock_code를 조용히 누락하던 문제는 제거됐다.
- 동일 신호가 요약과 누적 builder 모두에서 WIN으로 남는 세 별칭 회귀가 추가됐다(`tests/services/test_kr_market_backtest_service.py:754`-`765`). 조용한 누락이 count·win rate 양쪽으로 번지던 v2 blocker의 stop condition을 직접 검증한다.
- 생산 price snapshot은 date/ticker/high/low/close를 함께 로드한다(`services/kr_market_data_cache_prices.py:184`-`217`). ticker별 raw group은 metrics 진입 시 복사되고 date를 DatetimeIndex로 바꾸며 OHLC를 숫자로 변환하므로 원본 frame을 변경하지 않는다(`services/kr_market_backtest_trade_helpers.py:41`-`60`, `services/kr_market_backtest_trade_helpers.py:132`-`149`).

### 캐시 마이그레이션과 UI/AI/VCP 경계

- 계산 규칙 변경은 summary schema 2(`services/kr_market_backtest_summary_cache.py:38`-`40`)와 cumulative schema 5(`services/kr_market_cumulative_cache.py:51`-`53`)로 분리된다. 양쪽 signature의 첫 요소가 버전이므로 이전 메모리·SQLite key가 새 계산에 재적중하지 않는다(`services/kr_market_backtest_summary_cache.py:253`-`260`, `services/kr_market_cumulative_cache.py:191`-`197`). cumulative는 실제 old payload 저장 후 version bump의 miss까지 검사한다(`tests/services/test_kr_market_cumulative_cache.py:445`-`487`).
- 카드에는 AI reason을 그대로 텍스트로 렌더링하고 별도 출처 안내와 시스템 계산 기준을 표시한다(`frontend/src/app/dashboard/kr/closing-bet/page.tsx:2206`-`2220`). target/stop 표시 자체는 구조화 필드를 소비하므로 AI 본문 속 숫자가 계산 가격으로 다시 파싱되지 않는다(`frontend/src/app/dashboard/kr/closing-bet/page.tsx:2245`-`2262`).
- VCP 요약은 기존 `calculate_scenario_return`과 +15%/-5%를 그대로 사용한다(`services/kr_market_backtest_stats_helpers.py:123`-`149`). 홈의 기존 VCP +9%/-5% 문구도 종가 분기와 분리되어 유지되며, 알려진 불일치는 VCP-025 범위로 남는다(`frontend/src/app/dashboard/kr/page.tsx:538`-`542`). 이번 변경이 VCP 정책을 암묵적으로 바꾸지 않았다.

### 잔여 WATCH — 공개 metrics helper의 DataFrame 형태

- metrics docstring은 date-column 입력을 ticker와 ISO 날짜 문자열을 포함한 생산 일봉 형식으로 제한하고, 그 외에는 정규화된 DatetimeIndex를 받는다고 명시한다(`services/kr_market_backtest_trade_helpers.py:101`-`116`). 생산 loader와 builder는 이 계약을 충족한다.
- 다만 `prepare_cumulative_price_dataframe`은 ticker가 없는 date-column frame을 빈 frame으로 만들고(`services/kr_market_backtest_trade_helpers.py:41`-`46`), metrics는 그 뒤 index를 `Timestamp`와 비교한다(`services/kr_market_backtest_trade_helpers.py:132`-`149`). 제한 재현 `evidence/review-arch-shapes.log`에서 ticker 없는 date frame은 `TypeError`, 숫자형 `YYYYMMDD`는 OPEN/0 오판정, 문자열 OHLC를 가진 DatetimeIndex frame은 `TypeError`였다.
- 이는 현재 생산 계약 밖이며 이번 승인 범위를 넓혀 보정할 근거가 없어 release blocker로 보지 않는다. facade의 공개 helper를 향후 다른 호출부가 사용할 때는 docstring 계약을 지키거나 별도 입력 검증을 추가해야 한다.

## Root Cause

원래 문제의 근본 원인은 생성, 응답 보정, 요약, 누적성과, UI가 목표·손절 정책과 결과 판정을 따로 소유했다는 점이다. 최종 구조는 상수·가격 resolver·trade outcome을 공용 경계로 모으되, 공용화 과정에서 드러난 별칭·날짜·혼합 인자 호환성까지 기존 입력 계약의 합집합으로 복구했다.

## Recommendations

1. 현재 구현으로 격리 브라우저 QA를 진행한다 — 낮은 노력, 화면의 기본/custom/AI 원문/동시 hit/OPEN 연결을 최종 확인.
2. 향후 `calculate_cumulative_trade_metrics` 직접 호출이 늘면 DataFrame schema validator 또는 date/OHLC 정규화 경계를 별도 TODO로 추가한다 — 중간 노력, 예외와 조용한 OPEN 오판정 방지.
3. VCP-025에서 홈 문구 +9/-5와 실제 VCP 요약 +15/-5를 별도 정책 결정으로 정리한다 — 중간 노력, 이번 종가베팅 변경과 독립된 기존 사용자 안내 불일치 해소.

## Architectural Status

`WATCH`

## Trade-offs

| Option | Pros | Cons |
|---|---|---|
| 현재 공용 resolver + trade record 구조 | 요약·누적의 exact 가격과 손절 우선 판정이 한 곳에 모임; 기존 저장 가격과 API schema 유지 | trade record가 티커 별칭과 가격 frame shape를 함께 알아야 함 |
| 입력을 먼저 단일 canonical DTO로 마이그레이션 | 계산 함수가 더 단순해지고 타입 계약이 명확해짐 | 기존 저장 자료 migration과 더 큰 범위가 필요하며 이번 승인 목표를 초과함 |
| metrics에서 모든 pandas shape를 관대하게 보정 | 직접 호출이 다양한 frame에 견고해짐 | 숫자 날짜 해석 규칙 등 새 정책이 생기고 잘못된 입력을 조용히 수용할 위험이 있음 |

## Strongest Counterargument

가장 강한 반론은 summary와 cumulative를 한 builder에 묶어 단일 결과를 얻는 대신, summary count의 의미까지 바뀌었다는 점이다. 이제 price_map이나 일봉이 없는 유효 entry 신호도 OPEN/0으로 포함되어 총건수와 평균 ROI를 희석할 수 있다(`services/kr_market_backtest_stats_helpers.py:73`-`86`). 그러나 이는 승인된 계약에 명시된 동작이고, win rate 분모는 종료 거래만 사용하며, 두 화면이 동일 신호를 서로 다른 결과로 보여 주던 더 큰 오류를 제거한다. UI가 total signals와 closed-only win rate를 구분해 설명하는 한 이 trade-off는 수용 가능하다.

## Validation

- 기준 base: `8febe19ad7d2a41301104b8efe5ff6bed7b3ccab`.
- `review-input-v4.json` 32개 파일 SHA256 일치: `evidence/review-arch-v4-hash.log`.
- 이후 `git diff --check` 정리를 위해 `tests/services/test_kr_market_cumulative_cache.py` 끝 빈 줄만 제거했다. 나머지 31개는 v4와 동일하고, old/new SHA와 AST 무변경 설명은 `evidence/whitespace-fix.json`, 현재 대조는 `evidence/review-arch-v4-post-whitespace-hash.log`에 있다.
- 티커 별칭, 혼합 exact/pct, exact 경계, 과거 조회 deep-copy 정규화, 파일명 기준일: `evidence/review-arch-v4-contracts.log` — 7 passed.
- 관련 4개 파일 묶음: `evidence/review-v4-green.log` — 77 passed.
- 전체 backend: `evidence/backend-final-v4.log` — 2249 passed, 3 기존 skip.
- 제공 frontend 증거: 424 passed, 실제 build TypeScript 통과, lint 0 errors/201 warnings. 이 아키텍처 레인은 전체 suite를 재실행하지 않았다.
- `git diff --check` 현재 통과. 실제 3500/5501/live 요청, 재시작, 실제 data/시크릿/LLM/거래/설정/삭제는 수행하지 않았다.
