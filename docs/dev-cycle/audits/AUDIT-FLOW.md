# AUDIT-FLOW — 수급·백테스트 감사

**감사 범위**: `services/investor_trend_5day_service.py`, `services/kr_market_backtest_*.py`(11개),
`services/kr_market_flow_service.py`
**읽은 파일 수**: 12개 / 총 2,767줄

담당 경로를 `.claude/skills/dev-cycle/references/archive-format.md` §2 표에서 확정한 뒤 감사했습니다.
영향 범위를 확인하기 위해 호출자(`app/routes/`, `engine/`, `frontend/`)를 함께 읽었지만,
지적은 담당 경로 안에서 고칠 수 있는 것만 적었습니다.

백로그에 이미 올라와 있는 `FLOW-001`(KIS 장중 수급 연동)과 `FLOW-002`(섹터별 수급 집계)는
착수 전에 `docs/dev-cycle/TODO.md` 69~80줄에서 직접 확인했으며, 아래 지적에서 제외했습니다.

---

## 1. 깨진 동작

### 1.1 같은 종가베팅 시그널의 승패가 두 계산 경로에서 반대로 갈린다

- 위치: `services/kr_market_backtest_scenario_helpers.py:167-178`,
  `services/kr_market_backtest_trade_helpers.py:134-160`
- 증상: 목표가와 손절가를 같은 날에 동시에 충족한 시그널을 한쪽은 손절로, 다른 쪽은 익절로
  판정합니다. 대시보드의 종가베팅 승률(`frontend/src/app/dashboard/kr/page.tsx:908`)은
  손절로 세고, 누적성과 페이지의 승률(`app/routes/kr_market_data_ai_routes.py:152-161`)은
  익절로 셉니다. 두 화면이 같은 시그널 집합을 놓고 서로 다른 승률을 표시합니다.
- 원인: `calculate_scenario_return` 은 `if first_low <= first_high: return -(stop_pct * 100)`
  으로 손절을 우선합니다(167~173줄, "기존 규칙 유지" 주석이 붙어 있습니다).
  `calculate_cumulative_trade_metrics` 는 `if first_win_date <= first_loss_date:` 로 익절을
  우선합니다(144~152줄). 판정 기준이 한 곳에 모여 있지 않아 각자 굳어졌습니다.
  익절·손절 폭도 마찬가지로 갈라져 있습니다. 시나리오 쪽은 `target_pct`/`stop_pct` 를
  인자로 받는데(110~118줄), 누적성과 쪽은 `entry_price * 1.09` 와 `entry_price * 0.95` 를
  본문에 직접 적었습니다(134~135줄).
- 영향: 사용자가 두 화면에서 서로 다른 승률을 보고, 어느 쪽이 맞는지 판단할 근거가 없습니다.
  익절·손절 폭을 조정할 때 한쪽만 고치면 두 값의 차이가 더 벌어집니다.

### 1.2 수급 교차검증이 불일치 판정과 무관하게 언제나 참조 데이터로 교체한다

- 위치: `services/investor_trend_5day_service.py:839`, `:882-886`
- 증상: CSV 와 pykrx 의 수급 값이 완전히 일치해도, 이상징후 플래그가 하나라도 붙으면 CSV 를
  버리고 pykrx 값으로 교체합니다. 특히 `stale_csv`(4일 초과 지연) 하나만으로 연휴 직후에는
  거의 모든 종목이 교체 대상이 됩니다.
- 원인: 참조 데이터는 839줄의 `if verify_with_references and csv_flags:` 안에서만 조회되므로,
  886줄의 `should_replace = any(disagreement_flags) or bool(csv_flags)` 에 도달하는 시점에는
  `csv_flags` 가 반드시 비어 있지 않습니다. 따라서 `should_replace` 는 항상 참이고,
  882~885줄이 계산한 `disagreement_flags` 는 결과에 아무런 영향을 주지 않습니다.
  `_is_large_disagreement`(467~498줄)와 그것이 쓰는 세 상수
  `_DISAGREE_RATIO_THRESHOLD`, `_DISAGREE_SIGNIFICANT_TOTAL`, `_DISAGREE_SIGNIFICANT_SIDE`
  (41~43줄)는 전부 도달 불가능한 코드입니다.
- 영향: 교차검증이 임계값을 두고 신중하게 고르는 것처럼 보이지만 실제로는 무조건 교체입니다.
  임계값을 조정해도 동작이 바뀌지 않으므로, 수급 값이 틀렸을 때 원인을 찾기 어렵습니다.
  종목마다 pykrx 네트워크 호출이 붙는 부담도 함께 발생합니다.

### 1.3 손실이 없는 구간에서 손익비 자리에 총이익이 그대로 표시된다

- 위치: `services/kr_market_backtest_kpi_helpers.py:78`
- 증상: 손실 거래가 한 건도 없으면 손익비(Profit Factor)로 이익의 합계가 그대로 나옵니다.
  ROI 가 +9% 인 거래 다섯 건만 있으면 손익비가 `45.0` 으로 표시됩니다.
- 원인: `profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else round(gross_profit, 2)`
  에서, 분모가 0 일 때 비율 대신 분자를 그대로 돌려줍니다.
- 영향: 이 값은 `frontend/src/app/dashboard/kr/cumulative/CumulativeClientPage.tsx:1106` 에
  "손익비 (Profit Factor)" 로 표시되고, 같은 파일 258~266줄에서 2.0/1.5/1.2 를 기준으로
  등급까지 매깁니다. 비율이 아닌 값이 비율 기준에 걸려 항상 최고 등급으로 평가됩니다.

### 1.4 백테스트 상태 어휘가 소비자와 어긋나 있다

- 위치: `services/kr_market_backtest_common.py:51-59`,
  `services/kr_market_backtest_stats_helpers.py:31, 99, 101, 125, 168`
- 증상: 두 가지가 함께 어긋나 있습니다. 첫째, 전패한 구간이 "실패"가 아니라 "대기"로
  표시됩니다. 둘째, 화면의 확인 아이콘이 데이터가 없을 때만 켜집니다.
- 원인: `determine_backtest_status` 는 `if win_rate == 0: return "PENDING"` 을 가장 앞에 두어,
  승 0건 패 10건으로 승률이 0.0 인 경우와 종료된 거래가 아예 없는 경우를 구분하지 않습니다.
  또한 이 함수가 돌려주는 값은 `PENDING`/`EXCELLENT`/`GOOD`/`BAD` 네 가지뿐인데,
  `frontend/src/app/dashboard/kr/page.tsx:900, 963` 은 `status === 'OK'` 일 때 확인 아이콘을
  켭니다. `'OK'` 는 `calculate_vcp_backtest_stats` 가 125줄에서 임시로 넣었다가 거래가
  한 건이라도 있으면 168줄에서 덮어쓰는 값이므로, 거래가 0건일 때만 화면까지 도달합니다.
  종가베팅 쪽은 `'Accumulating'`/`'OK (New)'` 와 위 네 값만 내므로 `'OK'` 가 절대 나오지 않습니다.
- 영향: 성적이 가장 나쁜 구간이 아직 집계 중인 것처럼 보이고, 검증을 마친 전략에는 확인
  표시가 붙지 않습니다. 상태 문자열이 여섯 가지로 흩어져 있어 소비자가 무엇을 기대해야
  하는지 알 수 없습니다.

---

## 2. 중복

### 2.1 "이상징후면 다시 조회한다" 는 두 번 호출 패턴이 다섯 곳에 복제되어 있다

- 위치: 원인은 `services/investor_trend_5day_service.py:1002-1031`,
  복제된 곳은 `engine/screener.py:348, 359-372`, `engine/collectors.py:175, 1695-1712`,
  `engine/collectors/krx_local_data_mixin.py:485, 1240-1250`,
  `engine/collectors/naver_pykrx_mixin.py:437, 452-462`,
  `services/kr_market_stock_detail_service.py:231-267, 356-363`
- 증상: 모든 호출자가 같은 절차를 각자 구현합니다. 먼저 `verify_with_references=False` 로
  부르고, 반환된 `quality.csv_anomaly_flags` 가 비어 있지 않으면 `verify_with_references=True`
  로 한 번 더 부릅니다. 판정용 헬퍼 `_has_csv_anomaly_flags` 도 다섯 곳에 같은 내용으로
  각각 정의되어 있습니다.
- 원인: 서비스가 `verify_with_references` 를 단순한 켜고 끄기 플래그로만 노출합니다.
  "평소에는 CSV 로 빠르게 답하고 이상징후일 때만 참조를 조회한다" 는 정책이 서비스 안에
  없어서, 그 정책이 필요한 호출자마다 밖에서 다시 조립합니다.
- 영향: 판정 조건이 바뀌면 다섯 곳을 모두 찾아 고쳐야 하고, 한 곳이라도 빠지면 그 경로만
  낡은 기준으로 동작합니다. 담당 경로 밖의 네 곳은 다른 카테고리에 속하므로, 서비스 쪽
  진입점을 먼저 만들고 호출자를 순차로 옮기는 순서가 필요합니다.

### 2.2 티커 6자리 패딩 헬퍼가 공용 유틸을 두고 다시 구현되어 있다

- 위치: `services/kr_market_backtest_scenario_helpers.py:17-26`,
  `services/kr_market_backtest_trade_helpers.py:17-26`
- 증상: 두 파일이 열 줄짜리 `_get_ticker_padded_series` 를 글자 하나 다르지 않게 각각 가지고
  있습니다.
- 원인: 같은 기능이 `services/kr_market_csv_utils.py:202` 에 `get_ticker_padded_series` 로
  이미 공개되어 있고, 같은 카테고리의 `services/kr_market_flow_service.py:20-23` 과
  `services/investor_trend_5day_service.py:26` 은 그 공용 유틸을 가져다 씁니다.
  백테스트 모듈만 자체 구현을 들고 있습니다.
- 영향: 지금은 동작이 같아서 드러나지 않지만, 공용 유틸의 캐시 컬럼 규칙이 바뀌면 백테스트
  경로만 다르게 동작합니다. 담당 경로 밖인 `engine/` 에도 같은 복제가 다섯 개 더 있습니다.

---

## 3. 과잉 설계

### 3.1 계산 로직이 없는 재노출 전용 계층이 네 겹 쌓여 있다

- 위치: `services/kr_market_backtest_service.py`(38줄),
  `services/kr_market_backtest_calculators.py`(39줄),
  `services/kr_market_backtest_cumulative.py`(30줄),
  `services/kr_market_backtest_signal_stats.py`(26줄)
- 증상: 네 파일 합계 133줄이 전부 `import` 와 `__all__` 뿐이고 실행되는 계산은 한 줄도
  없습니다. 호출 경로는 `app/routes/kr_market_backtest_helpers.py:14` →
  `..._service` → `..._calculators` → `..._cumulative` / `..._signal_stats` →
  실제 구현(`..._trade_helpers`, `..._kpi_helpers`, `..._scenario_helpers`, `..._stats_helpers`)
  입니다. 함수 하나를 따라가려면 파일 다섯 개를 열어야 합니다.
- 원인: `..._calculators` 는 `..._service` 하나만, `..._signal_stats` 는 `..._calculators`
  하나만 가져다 씁니다. 구현체가 하나뿐인 중간 계층이 "호환 레이어"라는 이름으로 남았는데,
  호환을 지켜 줄 외부 호출자가 실제로는 존재하지 않습니다.
- 영향: 함수를 추가하거나 이름을 바꿀 때마다 네 파일의 `import` 와 `__all__` 을 함께 고쳐야
  합니다. 같은 자리에 `services/investor_trend_5day_service.py:971-999` 의
  `load_investor_trend_5day_map` 도 있습니다. `__all__` 에 공개되어 있지만 프로덕션 호출자가
  한 곳도 없고, 테스트 세 건만 이 함수를 붙들고 있습니다.

---

## 4. 비대한 파일

### 4.1 investor_trend_5day_service.py 가 책임 여섯 개를 한 파일에 담고 있다

- 위치: `services/investor_trend_5day_service.py`(1,048줄)
- 증상: 한 파일이 다음 여섯 가지를 모두 맡습니다.
  (1) CSV 5거래일 합산(`_load_trend_df`, `_build_trend_map`, 307~420줄)
  (2) 메모리 LRU 캐시(`_TREND_CACHE`, `_REFERENCE_CACHE`, 44~57줄과 905~968줄)
  (3) SQLite 스냅숏 직렬화(`_serialize_trend_map`, `_deserialize_trend_map`, 229~304줄)
  (4) pykrx 참조 조회와 영업일 해석(`_resolve_pykrx_latest_market_date`,
      `_fetch_pykrx_reference_trend`, 543~678줄)
  (5) Toss 참조 조회(`_get_toss_collector`, `_fetch_toss_reference_trend`, 681~717줄)
  (6) 이상징후 판정과 최종 선택(`_detect_csv_anomaly_flags`, `_resolve_best_payload`,
      501~540줄과 824~902줄)
- 원인: 파일 이름이 가리키는 "5거래일 합산 제공"에 교차검증과 두 단계 캐시가 차례로
  얹히면서, 서로 다른 이유로 바뀌는 코드가 한자리에 모였습니다.
- 영향: §1.2 처럼 도달 불가능한 분기가 생겨도 눈에 띄지 않습니다. 이 파일은
  `tier-rules.md` §2 의 위험 경로이므로 한 줄만 건드려도 T3 검증이 붙습니다. 그래서 분할
  자체를 별도 항목으로 세우지 않고, 같은 파일을 이미 여는 `[FLOW-005]` 가 끝난 뒤에
  실제 경계가 드러나면 그때 다시 판단하는 편이 낫다고 봅니다.

---

## 5. 검증 공백

### 5.1 누적성과 승패 판정에 테스트가 한 건도 없다

- 위치: `services/kr_market_backtest_trade_helpers.py:89-191`
  (`calculate_cumulative_trade_metrics`)
- 증상: 103줄짜리 함수가 WIN/LOSS/OPEN 판정, 동시 충족 시 우선순위, ROI, 최대상승률,
  가격 궤적 보정을 모두 결정하는데 저장소 전체에서 이 함수를 직접 부르는 테스트가 없습니다.
- 원인: 짝이 되는 `calculate_scenario_return` 쪽은 동시 충족 규칙이
  `tests/services/test_kr_market_backtest_service.py:77`
  (`test_calculate_scenario_return_prefers_stop_when_same_day_hits_both`)에 고정되어
  있습니다. 한쪽만 테스트로 묶여 있어서 §1.1 의 불일치가 드러나지 않았습니다.
- 영향: §1.1 을 고칠 때 어느 쪽이 기존 동작인지 판단할 근거가 한쪽에만 있습니다.

### 5.2 KPI 집계와 상태 판정이 스텁으로만 등장한다

- 위치: `services/kr_market_backtest_kpi_helpers.py:15-101`(`aggregate_cumulative_kpis`),
  `services/kr_market_backtest_common.py:51-59`(`determine_backtest_status`)
- 증상: `aggregate_cumulative_kpis` 는 승률, 평균 ROI, 등급별 ROI, 평균 보유일, 손익비를
  계산하는 87줄인데, 테스트에 나오는 것은
  `tests/app/test_kr_market_data_ai_routes_refactor.py:130, 177` 의
  `lambda trades, _price_df, _now: {"count": len(trades)}` 같은 스텁뿐입니다.
  실제 구현을 부르는 테스트는 없습니다. `determine_backtest_status` 는 저장소 어디에서도
  이름조차 나오지 않습니다.
- 원인: 라우트 배선을 검증하는 테스트가 계산 함수를 주입 지점에서 대체하다 보니, 배선은
  덮이고 계산은 비었습니다.
- 영향: §1.3 의 손익비와 §1.4 의 상태 판정이 둘 다 이 공백 안에 있습니다.

---

## 요약

| 관점 | 발견 | 그중 P0 | P1 | P2 |
|---|---|---|---|---|
| 깨진 동작 | 4 | 1 | 3 | 0 |
| 중복 | 2 | 0 | 1 | 1 |
| 과잉 설계 | 1 | 0 | 0 | 1 |
| 비대한 파일 | 1 | 0 | 0 | 1 |
| 검증 공백 | 2 | 1 | 1 | 0 |
| 합계 | 10 | 2 | 5 | 3 |

### 담당 경로 밖에서 관찰한 사실

- `app/routes/kr_market_backtest_helpers.py` 는 §3.1 이 지적한 재노출 사슬의 다섯 번째
  계층으로, 열두 개 함수를 인자만 그대로 넘겨 다시 감쌉니다. 종가베팅·라우트 카테고리에
  속하므로 여기서는 사실만 적습니다.
- `_has_csv_anomaly_flags` 의 동일 복제가 `engine/` 아래 네 곳에 더 있습니다(§2.1 위치 참고).

---

# 2부: TODO 항목 초안

일련번호는 `docs/dev-cycle/` 전체에서 `FLOW` 의 최대 번호가 `FLOW-002` 임을 확인한 뒤
`FLOW-003` 부터 매겼습니다. 티어는 `.claude/skills/dev-cycle/references/tier-rules.md` §3
절차로 판정했습니다. `services/investor_trend_5day_service.py` 는 §2 "수급 집계" 위험 경로에
있으므로 그 파일을 여는 항목은 줄 수와 무관하게 `T3` 입니다. `services/kr_market_backtest_*`
는 위험 경로 목록에 없으므로 예상 변경 규모로 갈랐습니다.

### [FLOW-003] 종가베팅 승패 판정을 한 곳으로 모은다
- 카테고리: 수급·백테스트 | 티어: T2 | 우선순위: P0 | 근거: AUDIT-FLOW §1.1, §5.1
- 두 계산 경로를 함께 고치고 회귀 테스트를 새로 붙이므로 50줄을 넘을 것으로 봅니다.
  위험 경로에는 닿지 않습니다.
- [ ] 동시 충족 시 익절과 손절 중 무엇을 우선할지 결정하고 근거를 항목에 남김
- [ ] 판정 규칙과 익절·손절 폭을 공용 함수 하나로 모아 두 호출부가 함께 쓰도록 교체
- [ ] `calculate_cumulative_trade_metrics` 의 `1.09`/`0.95` 하드코딩 제거
- [ ] `calculate_cumulative_trade_metrics` 의 동시 충족·ROI·최대상승률 회귀 테스트 추가
- [ ] 대시보드 승률과 누적성과 승률이 같은 시그널 집합에서 일치하는지 확인

### [FLOW-004] 백테스트 상태 어휘와 손익비 계산을 바로잡는다
- 카테고리: 수급·백테스트 | 티어: T2 | 우선순위: P1 | 근거: AUDIT-FLOW §1.3, §1.4, §5.2
- [ ] 전패(승 0건, 패 N건)와 미집계(종료 거래 0건)를 구분하도록 `determine_backtest_status` 수정
- [ ] 상태 문자열 집합을 확정하고 프론트엔드의 `status === 'OK'` 비교를 그 집합에 맞춤
- [ ] 손실이 0일 때의 손익비 표기 방식을 결정해 반영 (비율이 아닌 값을 내보내지 않음)
- [ ] `aggregate_cumulative_kpis` 실구현 테스트 추가 (승률·평균 ROI·손익비·등급별 ROI)
- [ ] `determine_backtest_status` 경계값 테스트 추가

### [FLOW-005] 수급 교차검증을 서비스 안에서 끝낸다
- 카테고리: 수급·백테스트 | 티어: T3 | 우선순위: P1 | 근거: AUDIT-FLOW §1.2, §2.1, §3.1
- `services/investor_trend_5day_service.py` 는 `tier-rules.md` §2 "수급 집계" 위험 경로이므로
  줄 수와 무관하게 T3 입니다. 호출자 정리는 `engine/` 과 종목상세 카테고리에 걸치므로,
  서비스 쪽 진입점을 먼저 만들고 호출자는 뒤이어 옮깁니다.
- [ ] `_resolve_best_payload` 의 교체 조건을 다시 정의해 `_is_large_disagreement` 가 실제로
      판정에 쓰이도록 하거나, 쓰지 않기로 하면 함수와 세 상수를 함께 제거
- [ ] `stale_csv` 단독으로 무조건 교체하던 동작을 의도한 규칙으로 고침
- [ ] 이상징후 재조회를 서비스 내부에서 수행하는 단일 진입점 추가
- [ ] 호출자 다섯 곳의 `_has_csv_anomaly_flags` 와 두 번 호출 패턴을 그 진입점으로 교체
- [ ] 호출자가 없는 `load_investor_trend_5day_map` 의 존치 여부 결정
- [ ] 교체 규칙 회귀 테스트 추가 (일치·불일치·지연 각 경우)

### [FLOW-006] 백테스트 재노출 전용 계층을 걷어낸다
- 카테고리: 수급·백테스트 | 티어: T2 | 우선순위: P2 | 근거: AUDIT-FLOW §3.1
- [ ] `..._service`, `..._calculators`, `..._cumulative`, `..._signal_stats` 네 파일의
      외부 호출자를 확인한 뒤 남길 진입점 하나를 결정
- [ ] 나머지 재노출 계층 제거하고 `app/routes/kr_market_backtest_helpers.py` 의 import 정리
- [ ] `tests/services/test_kr_market_backtest_service.py` 의 import 경로 갱신
- [ ] pytest 전체 통과 확인

### [FLOW-007] 티커 패딩 헬퍼를 공용 유틸로 통합한다
- 카테고리: 수급·백테스트 | 티어: T1 | 우선순위: P2 | 근거: AUDIT-FLOW §2.2
- [ ] `..._scenario_helpers` 와 `..._trade_helpers` 의 자체 구현을
      `services.kr_market_csv_utils.get_ticker_padded_series` 로 교체
- [ ] 캐시 컬럼(`_ticker_padded`) 동작이 교체 전후로 같은지 확인
- [ ] `tests/services/test_kr_market_backtest_service.py` 통과 확인
