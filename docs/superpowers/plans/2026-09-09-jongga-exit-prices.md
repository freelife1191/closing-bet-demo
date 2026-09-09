# 종가베팅 목표·손절 기준 Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task. The leader owns integration and verification; bounded native-agent slices may assist.

**Goal:** JONGGA-012와 JONGGA-013의 생성·누락값 보정·백테스트·화면 가격 기준을 일치시키고 AI 원문 출처를 구분한다.

**Architecture:** 기존 SignalConfig의 기본 +5%/-3%를 공용 상수로 재사용한다. 저장된 유효한 목표/손절 가격이 있으면 그대로 우선하며, 누락/비정상 값은 공통 규칙으로 보충한다. 요약과 누적성과는 동일 가격을 사용하며 기존 승패 순서(같은 일봉에서는 손절 우선)를 유지한다. AI 원문은 수정하지 않는다.

**Tech Stack:** Python/Flask, pandas, Next.js 16.3.4, React 19.2.4, pytest, Vitest.

**Spec:** 2026-09-09 현재 대화의 두 라운드 bounded 설계와 후속 사용자 「진행해」 승인. 별도 architectural 설계 문서는 없다. T3 규칙에 따라 이 구현 계획과 critic 검토를 남긴다.

## Global Constraints

- 기본 목표 +5%, 손절 -3%. 기존 저장 자료/AI 원문은 덮어쓰지 않는다.
- 저장된 유효 가격은 우선한다. NaN/Infinity/음수/0/진입가 반대쪽 가격은 계산용 값으로 사용하지 않는다. 누락 필드와 같은 기본값으로 보충하고 로그를 남긴다.
- VCP 전략·등급·진입 판단·실거래·알림은 변경하지 않는다. 종가베팅 백테스트 계산만 승인 범위다.
- 새 의존성·타입 억제·외부 API·실제 시크릿·원본 data 변경 없음.
- develop 독립 clone에서 작업. 원본 package.json 미추적 파일 보존. 원본3500/5501/live 접속·재시작 금지.
- T3: ponytail → code-review 독립 두 레인 → review 심층 검토 → 전체 정적 검증 → 첫 구현/QA 행렬 커밋 → UltraQA → 정리/아카이브.
- 리뷰 단계당 15분, 테스트명령당 900초, QA 명령당 60초/서버상태대기120초, 최대5회/동일실패3회. 회복 가능한 실패는 원인 수정 후 재시도한다.

## Task 1: 생성·보정의 기본값과 저장 가격 해석

**Files:** engine/constants_market.py, engine/config.py, engine/position_sizer.py, services/kr_market_backtest_common.py, app/routes/kr_market_jongga_normalize_helpers.py. 기존 tests/app/test_kr_market_jongga_helpers_refactor.py 및 tests/app/test_kr_market_helpers_contract.py, 새 tests/engine/test_position_sizer_exit_prices.py.

**Interfaces:** 공용 상수 JONGGA_TARGET_PCT=0.05/JONGGA_STOP_PCT=0.03를 engine/constants_market.py에 정의하고 기존 backtest_common import 경로는 재노출한다. 공용 가격 해석 resolve_jongga_exit_prices(entry_price, target_price=None, stop_price=None) -> tuple[float,float]는 services/kr_market_backtest_common.py에 둔다. 생성 계산은 SignalConfig 값과 동일한 공식이며 정상·예외 양쪽에서 같은 config 비율을 쓴다.

- [x] RED: 정상 설정·사용자 설정 및 예외 폴백의 가격을 검사한다. 누락 보정 기본 100000 → 105000/97000, 명시값 108000/96000 보존, 한 필드만 누락, 비정상 숫자/문자열 경계를 표로 검사한다.

```python
def test_missing_exit_prices_use_generation_defaults():
    signal = {"entry_price": 100000}
    _normalize_jongga_signal_for_frontend(signal)
    assert signal["target_price"] == 105000
    assert signal["stop_price"] == 97000
```

- [x] `./venv/bin/python -m pytest -q tests/app/test_kr_market_jongga_helpers_refactor.py tests/app/test_kr_market_helpers_contract.py tests/engine/test_position_sizer_exit_prices.py`로 실패 확인.
- [x] 공용 기본값과 실제 소비부를 최소 수정한다. 유효한 명시값은 보존하며 기본 가격은 entry*(1+pct)다. 정밀도 손실 없이 일관되게 계산하고 UI만 표시 반올림한다.

```python
JONGGA_TARGET_PCT = 0.05
JONGGA_STOP_PCT = 0.03
# SignalConfig 기본값은 위 두 상수를 참조한다.
# normalize와 backtest는 resolve_jongga_exit_prices를 통해 같은 가격을 얻는다.
```

- [x] 위 targeted 검사를 다시 통과시키고 실제 실패/수정 증거를 저장한다.

## Task 2: 요약·누적성과와 캐시 정합성

**Files:** services/kr_market_backtest_stats_helpers.py, services/kr_market_backtest_trade_helpers.py, services/kr_market_backtest_summary_cache.py, services/kr_market_cumulative_cache.py, tests/services/test_kr_market_backtest_service.py, tests/services/test_kr_market_backtest_summary_cache.py, tests/services/test_kr_market_cumulative_cache.py.

**Interfaces:** Task1의 공용 가격 해석으로 저장된 정확 가격을 얻고 calculate_cumulative_trade_metrics(..., *, target_price=None, stop_price=None)에 keyword-only 가격으로 직접 전달한다. pct로 변환 후 가격을 재구성하지 않는다. 명시 가격이 없을 때만 기존 pct 인자로 계산하며 인자 호환을 유지한다. 입력 stock_prices에 date 컬럼이 있으면 같은 파일의 prepare_cumulative_price_dataframe을 먼저 적용해 DatetimeIndex로 만든다(생산 price_index의 group은 ticker/date 컬럼과 RangeIndex를 가진다). 기존 DatetimeIndex 입력은 그대로 사용한다. 원본 frame을 변경하지 않는다. 이 함수의 기존 반환 {outcome, roi, ...}를 요약과 누적성과가 함께 사용해 WIN/LOSS를 직접 센다. 종가 요약의 calculate_scenario_return→수익률 비교 경로를 이 기존 구조화 계산으로 대체하고 VCP의 float 시나리오 API는 그대로 둔다. OPEN 수익률은 같은 일봉 마지막 close 기준, 자료가 없으면 OPEN/0이며 두 집계의 의미가 같다. 요약의 current_price <= 0 continue 게이트는 제거한다. price_map은 후보 표시 갱신에만 사용한다. price_map 없음+일봉 있음은 거래 집계에 포함하고, price_map 있음+일봉 없음은 OPEN/0으로 포함하는 두 fixture를 검사한다. entry_price가 유효하면 정본이며 buy_price는 UI에서 entry가 없을 때만 과거자료 표시용 fallback이다. 실제 함수 입력은 entry_price를 필요로 한다.

- [x] RED: 동일 합성 OHLC를 요약과 누적성과에 넣어 기본 +5 hit, -3 hit, custom +8/-4 hit, 같은 날 양쪽hit 손절 우선, 아직 OPEN, 가격 없는 경우를 독립 기대값으로 검사한다. VCP 기존 출력도 보존한다. 명시target101원/entry100원(이진꼬리 재현값은 검사에서 확정), 정확 target/stop 경계와 경계바깥 1원, 반올림상5.0%지만 target 미도달인 OPEN을 검사한다.

```python
prices = pd.DataFrame({"high": [106000], "low": [99000], "close": [104000]}, index=pd.to_datetime(["2026-09-02"]))
metrics = calculate_cumulative_trade_metrics(100000, "2026-09-01", prices)
assert metrics["outcome"] == "WIN"
assert metrics["roi"] == 5.0
```

- [x] `./venv/bin/python -m pytest -q tests/services/test_kr_market_backtest_service.py`로 RED 확인 후 공용 해석과 인자 전달을 구현한다.
- [x] 기존 캐시 버전 증가: summary 1→2, cumulative 4→5. 기존 캐시 키가 재적중하지 않고 새 계산결과가 읽히는 동작 검사. 실제 사용자 DB는 건드리지 않는다.
- [x] 위 3개 services 테스트를 통과시킨다. 기존 +9/-5 기대값은 승인된 기본값 변경의 영향만 갱신하고 실패를 숨기는 삭제/완화는 하지 않는다.

## Task 3: 가격 안내와 AI 원문 출처

**Files:** README.md의 종가 가격 표·설명(기존 AI 답변 예시는 원문 보존), frontend/src/app/components/ClosingBetCriteriaModal.tsx, frontend/src/app/dashboard/kr/closing-bet/page.tsx, frontend/src/app/dashboard/kr/page.tsx, frontend/src/app/dashboard/kr/cumulative/CumulativeClientPage.tsx; 기존 frontend/src/app/dashboard/kr/closing-bet/page.regression-jongga-015.test.tsx 및 page.regression-jongga-016.test.tsx, frontend/src/app/dashboard/kr/page.regression-flow-004.test.tsx, frontend/src/app/dashboard/kr/cumulative/CumulativeClientPage.regression-005.test.tsx, 신규 frontend/src/app/components/ClosingBetCriteriaModal.test.tsx.

**Interfaces:** 기존 target_price/stop_price/entry_price 및 AI reason을 그대로 소비한다. 신규 API나 LLM 호출 없음. 기본 안내 +5/-3과 저장된 개별 가격 우선 원칙을 표시한다. 카드의 매수가와 비율은 entry_price를 우선하며 buy_price는 entry가 없는 과거자료 표시용 fallback으로만 사용한다. VCP 시그널 가격/전용 화면 안내의 기존 +5/-3과 VCP 백테스트의 기존 +15/-5를 모두 변경하지 않는다. 홈의 VCP +9/-5 문구는 기존 불일치로 별도 TODO에 이월하며 이번 변경은 종가베팅 분기에만 적용한다. VCP 계산/전용화면 불변을 회귀로 확인한다.

- [x] RED: 실제 카드 렌더링에서 105000/97000 및 custom108000/96000 값·비율, AI본문142000/130000 원문보존과 시스템가격 출처 구분을 검사한다. entry100000/buy120000이면 매수가100000, +5/-3로 표시하는 회귀를 포함한다.

```typescript
expect(await screen.findByText('₩105,000')).toBeTruthy();
expect(screen.getByText(/시스템 계산 기준/)).toBeTruthy();
expect(screen.getByText(/142,000원/)).toBeTruthy();
```

- [x] Next 번들 05-server-and-client-components와 관련 React 지침을 읽고 해당 Vitest RED를 기록한다.
- [x] 점수표/Trading Tips/가격툴팁/종가 홈성과 안내를 정리한다. 임의 매매정책(분할매도/시간/금액별 손절)을 계산 기준처럼 설명하지 않는다. AI 원문 바로 옆에 ‘AI 원문에는 다른 가격이 포함될 수 있으며, 이 화면의 시스템 계산 기준은 아래 목표가·손절가입니다’라는 출처 설명을 둔다.
- [x] 대상 Vitest 및 type-check/lint를 통과시킨다.

## Task 4: 독립 검토·검증·실측·마감

- [x] 입력 파일 SHA256와 base 8febe19ad7d2a41301104b8efe5ff6bed7b3ccab diff를 고정해 ponytail, code-review 두 독립 레인, T3 review를 순서대로 진행하고 지적을 반영한다.
- [x] 전체 pytest/Vitest, type-check/lint, 빌드 smoke를 실행하고 exit/검사수를 기록한다. LSP가 없으면 부재와 대체 증거를 명시한다.
- [x] docs/dev-cycle/qa/JONGGA-012.md 및 JONGGA-013.md에 UltraQA 행렬을 만들고 첫 구현/행렬 커밋한다. TODO는 유지한다.
- [x] 실제 Next 화면과 변경한 백엔드 계산을 합성 데이터로 연결한 격리 앱에서 agent-browser로 카드/점수표/전략안내/홈성과/누적성과/모바일/AI원문·Unicode/누락·custom·동시hit·OPEN을 실측한다. Next MCP compilation/errors도 확인한다.
- [x] 필수 행·증거·소유 프로세스/fixture 정리가 통과한 뒤 develop에 검증된 커밋만 통합하고 두 항목을 월별/일별 아카이브로 이동한다. 원본 미추적파일 SHA를 다시 확인한다.

## Critic 보완 이력

- 초기 REJECT: pct 왕복에 따른 정확 경계 누락, 요약 float 재추론 계약 미정, buy/entry 우선순위·실제 누적 client 경로 누락.
- 반영: 정확 가격 keyword 인자, 기존 cumulative 구조화 결과를 요약에서 재사용(새 결과계층 없음), entry 우선/동일fixture 검사, CumulativeClientPage 경로 확정. 캐시 기존버전 결과를 적재한 뒤 새시그니처 메모리·SQLite 미적중/새 결과 저장을 검사한다.

- critic 추가 반영: 생산 요약의 raw date컬럼/RangeIndex group을 기존 prepare_cumulative_price_dataframe으로 계산 진입 전 정규화. 실제 `{date,ticker,high,low,close}` raw frame 및 그 build_ticker_price_index를 전달하는 요약↔누적 회귀를 필수로 추가한다.

## 독립 코드·아키텍처 리뷰 보완

- 기존 summary의 code-only/empty ticker 신호를 shared builder의 truthy ticker→stock_code→code로 복구하고 회귀를 추가한다.
- 가격 keyword는 각 side별로만 기존 pct를 덮어쓴다. 한쪽만 명시한 사용자 지정 pct도 유지한다.
- app/routes/kr_market_data_jongga_routes.py의 실제 history 응답에 기존 normalizer를 주입해 response deepcopy에만 가격을 보충한다. tests/app/test_kr_market_route_integration.py의 저장/누락 HTTP 회귀와 과거 날짜 브라우저 선택으로 검증한다.
- services/kr_market_analytics_service.py의 summary는 기존 extract_stats_date_from_results_filename으로 누적성과와 같은 파일 기준일을 쓰며 payload copy에만 보충한다. tests/services/test_kr_market_analytics_service_refactor.py에 실제계산 회귀를 둔다.
