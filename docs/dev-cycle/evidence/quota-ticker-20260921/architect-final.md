## 요약

독립 재검수 결과 **Architectural Status: `CLEAR`** 입니다. 초기 `BLOCK` 원인이었던 raw 보유 티커와 canonical 가격 캐시의 단절은 canonical-first/raw-fallback으로 보완되었고, 저장 티커 불변과 자산 이력 연결도 유지됩니다.

## 분석

- 가격 해석은 canonical 키를 먼저 조회하고, 없을 때만 raw 키로 폴백합니다. 무효 티커는 빈 canonical 키를 조회하지 않습니다. `services/paper_trading_valuation_helpers.py:15`
- 같은 해석 함수가 개별 보유 평가와 포트폴리오 주식가치 합계에 함께 쓰입니다. `services/paper_trading_valuation_helpers.py:27,60`
- 평가 합계 total_stock_value가 그대로 자산 이력 기록에 전달됩니다. 따라서 5930/0007c0 보유도 canonical 가격으로 평가된 값이 history에 연결됩니다. `services/paper_trading_valuation_service.py:104,114`, `services/paper_trading_history_mixin.py:48`
- 매수 저장 경계는 입력 티커를 그대로 유지합니다. 평가용 정규화가 DB의 보유·거래 티커를 다시 쓰지 않습니다. `services/paper_trading_trade_account_mixin.py:179,204`
- legacy/lowercase, canonical 충돌 우선순위, 무효 빈 키, 저장 티커 불변을 새 회귀검사가 고정합니다. RED는 충돌 시 raw 값 110을 잘못 선택했고, 수정 후 관련 102건이 PASS했습니다. `tests/services/test_paper_trading_ticker_valuation.py:12,23`, `pytarget-valuation-authority-red.json:16`, `pytarget-valuation-authority-green.json:18`
- code review의 공백 alias 지적 3곳도 raw 문자열 exact 비교로 보완되었습니다. SQLite 동률은 canonical 원문을 우선하고 JSON 맵도 같은 정책을 따릅니다. `services/kr_market_data_cache_prices.py:40`, `services/kr_market_realtime_price_cache.py:377`, `services/kr_market_realtime_price_service.py:84`, `tests/services/test_kr_market_ticker_normalization.py:146`
- 세션 로딩 중 quota는 요청하지 않고 pending으로 표시됩니다. 이전 계정 응답과 같은 신원의 역순 응답도 generation/identity 경계에서 폐기합니다. `frontend/src/hooks/useQuota.ts:61,88,116`
- FLOW-006은 단일 공개 facade를 유지하고 내부 사용자는 leaf helper를 직접 참조합니다. 제거된 세 facade 경로의 남은 Python import는 발견되지 않았습니다. `services/kr_market_backtest_service.py:1`, `services/kr_market_analytics_service.py:21`

## 검증 상태

동결 SHA와 핵심 제품 소스가 일치했습니다. 최신 증거는 pytest **2422 passed / 3 skipped**, Vitest **629 passed**, lint **0 errors / 184 warnings**, 타입 보완 후 build **3 passed**입니다. git diff --check에도 오류가 없습니다. 실행·import·네트워크·원본 데이터 접근은 하지 않았습니다.

## Root Cause

초기 결함은 가격 생산자가 canonical 키를 만들었지만 평가 소비자가 저장된 raw 티커만 조회해, legacy/lowercase 보유 종목이 매수가로 잘못 폴백하던 생산자–소비자 키 계약 불일치였습니다. 공통 평가 경계에서 canonical-first/raw-fallback으로 해결되어 추가 저장소 마이그레이션은 필요하지 않습니다.

## Trade-offs

| 선택 | 장점 | 비용 |
|---|---|---|
| 현재 canonical-first/raw-fallback | 최신 canonical 가격을 권위값으로 사용하며 기존 저장 티커와 거래 이력을 보존 | 평가 시 티커 정규화 1회 추가 |
| 저장 티커 마이그레이션 | DB 키가 단일 형식으로 정리됨 | 기존 거래 데이터 변경과 충돌 처리 위험이 커 현재 범위를 벗어남 |

**최종 판정: `CLEAR`**
