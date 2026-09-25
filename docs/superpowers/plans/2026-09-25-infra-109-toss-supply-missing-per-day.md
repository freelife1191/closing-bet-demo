# [INFRA-109] Toss 투자자 추이의 빈 순매수 수량을 날짜 단위 결측으로 보존한다 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 종가가 있는 행의 외국인·기관 순매수 수량이 비면 그날 값을 0 이 아니라 `None` 으로 두고, 행 순서를 유지해 전날 값이 1일 순매수 자리로 밀려 오르지 않게 한다.

**Architecture:** 결측의 단위는 날짜다. 파서(`parse_investor_trend`)는 5일 합계에 값이 있는 날만 더하고, 한 필드가 다섯 날 모두 비면 그 합계만 `None` 이다. 두 정규화기(`_normalize_toss_supply_payload`, `_normalize_external_trend_payload`)는 하루 값의 결측을 그 자리에 `None` 으로 두고, 5일 합계가 결측이면 페이로드 전체를 `None` 으로 돌려 기존 폴백(스크리너는 CSV, 참조 조회는 자료 없음)에 맡긴다. `_score_supply_core` 는 `[VCP-057]` 부터 `details` 의 `None` 을 받아 연속 매수 계산을 그 날에서 멈추고 1일 값을 `None` 으로 둔다.

**Tech Stack:** Python 3.11, pytest

**Spec:** 대화 설계(2026-09-25, 확인 시각 11:51, 「날짜 단위 보존」 선택. 11:48 의 「추이 전체를 결측 처리」 선택은 사용자가 「결측 하나로 5일 전체를 결측으로 보기엔 애매하다」고 되물어 철회했다), `docs/dev-cycle/TODO.md` `[INFRA-109]`

## Global Constraints

- 티어 T3: `services/investor_trend_5day_service.py` 가 tier-rules §2 「수급 집계」에 있다.
- 실제 순매수 0 은 0 으로 남는다. `0`, `"0"`, `0.0` 은 결측이 아니다.
- 5일 합계는 값이 있는 날만 더한다(현재 코드와 같은 값). 4일치 합계를 5일 임계값과 견주는 한계는 종전과 같고 이번 범위가 아니다.
- 파서의 `details` 는 합계에 넣은 행(종가가 있는 행)만 담는다. 종전에는 원본 `trends` 를 그대로 넘겨, 종가·수량이 모두 빈 행을 정규화기가 버리고 있었다. 날짜 단위 보존으로 바꾸면 그 행이 `details[0]` 의 `None` 으로 남아 1일 값과 연속 매수를 지우므로 파서에서 뺀다(critic REVISE). `scripts/init_data.py` 의 파일 저장 경로(`[INFRA-095]`)는 종가 없는 행을 원래 버리므로 바뀌지 않고, 개인 순매수는 원본 `trends` 로 따로 계산한다.
- 개인 순매수(`personal_flow_details`)는 이미 결측이면 `[]` 이므로 범위 밖이다.
- 원본 `data/`·네트워크·LLM 에 닿지 않는다.

## 변경 목록

| 파일 | 변경 |
|---|---|
| `engine/toss_collector_metric_parsers.py` | `parse_investor_trend`: 외국인·기관 수량을 엄격하게 읽는다(None·빈 문자열·숫자 아님·무한대는 결측). 값 있는 날만 합에 더하고, 한 날도 없으면 그 합은 `None` |
| `engine/screener_supply_helpers.py` | `_normalize_toss_supply_payload`: 하루 값이 결측이면 행을 버리지 않고 그 자리에 `None`. 합계 결측이면 `None` 반환(종전과 같은 `TypeError` 경로) |
| `services/investor_trend_5day_service.py` | `_normalize_external_trend_payload`: 합계가 결측이면 `None` 반환, 하루 값 결측은 `None` 유지 |
| `engine/toss_collector_numeric_helpers.py` | 공용 `optional_volume`: `None`·`bool`·빈 문자열·숫자 아님·무한대는 결측, 쉼표는 제거. 파서와 두 정규화기가 같이 쓴다 |

합계는 정규화기에서 `int(float(v))` 를 `try` 로 감싸 `(TypeError, ValueError, OverflowError)` 를 잡는다. 키가 없어도 결측이다. `_serialize_trend_map` 은 고치지 않는다. 추이 맵은 CSV 에서만 만들어지고 `fillna(0)` 을 거쳐 키와 값이 늘 있다(critic 지적).

알려진 한계(범위 밖): 상세 API 의 `investorTrend.foreign` 이 `null` 이면 화면이 0 으로 보인다(`[FE-048]`). Toss 참조의 SQLite 캐시는 날짜 토큰이 키라 장중에 최신일이 비었던 응답이 그날 동안 남는다(종전에는 0, 이제는 `None`). 최신일 수량이 빈 Toss 참조는 나머지 넷이 0 이 아니면 채택되어 1일 값 `None`·연속 매수 0 이 된다(종전 0 과 결과가 같다).

동작 변화(심층 리뷰 M1): `details` 가 종가 있는 행만 담으므로 size=5 응답에 종가 없는 행이 하나라도 있으면 Toss 참조가 `_reference_reject_reason` 의 `insufficient_days` 로 버려진다. 4일치를 5일 참조로 쓰지 않는 보수적 변화로 받아들인다. `test_parse_investor_trend_all_real_zero_is_zero_and_closeless_latest_row_is_dropped` 는 6행 응답으로 「종가 없는 행이 `details[0]` 을 차지하지 않음」만 고정한다. 종가는 없고 수량만 숫자인 행도 같이 빠진다(`closing-bet-reviewer` low 1). 그 행은 금액을 계산할 수 없어 원래 합계에 들어가지 않았고, 남기면 수량만 비었을 때 `details[0]` 이 `None` 이 되는 critic 지적과 같은 문제로 돌아가므로 빼는 쪽을 택했다. 스크리너 경로에서는 그 경우 전날 값이 1일 자리에 온다.

## Review Focus

- 합계 `None` 이 `_score_supply_core` 에 닿으면 `None > 50_000_000_000` 이 `TypeError` 로 종목을 통째로 건너뛴다(`engine/screener.py:263` 의 `except`). 두 정규화기가 합계 결측에서 `None` 을 돌려주므로 닿지 않아야 한다. 테스트로 고정한다.
- `_normalize_external_trend_payload` 의 결과는 SQLite 참조 캐시에 저장되고 `from_cache=True` 로 같은 함수를 다시 지난다. `None` 이 JSON `null` 로 왕복해도 `None` 으로 남아야 한다.
- 참조 검증(`_reference_reject_reason`, `_detect_csv_anomaly_flags`)은 `_safe_int` 로 `None` 을 0 으로 읽는다. 절댓값 합에서 0 은 「그날 거래 없음」과 같은 효과이고 참조를 더 버리는 쪽이라 그대로 둔다.
- 빈 문자열·`"-"`·`"1,234"` 입력: 앞의 둘은 결측, 마지막은 1234.
- 1일 값(`details[0]`)만 결측이면 `foreign_1d`/`inst_1d` 가 `None`, 5일 합계는 나머지 넷의 합.

## Task 1: 파서와 정규화기

- [ ] `tests/engine/test_toss_collector_parsers_refactor.py` 에 실패 테스트: 최신일 외국인 수량 `""`·기관 `None` 인 5행 → `foreign` 은 나머지 네 날의 금액 합, `details[0]` 원본 유지. 다섯 날 모두 외국인 결측 → `foreign is None`, `institution` 은 정상 합. 실제 `0`·`"0"` → 합에 0 으로 들어가고 결측 아님
- [ ] `tests/engine/test_screener_supply_helpers_refactor.py` 에 실패 테스트: `_normalize_toss_supply_payload` 가 가운데 날 `None` 을 그 자리에 두고 길이 5 유지, 합계 `None` 이면 `None`. `score_supply_from_toss_trend` 까지 이어 `foreign_1d is None` 과 연속 매수 중단 확인
- [ ] `tests/services/test_investor_trend_5day_service.py` 에 실패 테스트: `_normalize_external_trend_payload` 가 하루 결측을 `None` 으로, 합계 결측이면 `None`. `json.loads(json.dumps(result))` 를 `from_cache=True` 로 다시 넣어도 같은 결과. `_serialize_trend_map` 에 키 없는 detail 을 넣으면 그 detail 이 빠진다
- [ ] 세 테스트 파일에서 새 테스트가 실패하는 것을 확인한 뒤 구현
- [ ] `git grep -n "to_float(item.get(\"net\|_safe_int(item.get(\"net\|get(\"netForeignerBuyVolume\", 0)" -- engine services` 에서 남는 줄이 참조 검증의 `_safe_int(detail.get(...))` 두 함수뿐인지 확인
- [ ] 세 파일 대상 pytest 통과, pytest 전체 통과

## 검증과 QA

실행 코드를 바꾸므로 QA 계획을 거친다. 사용자 진입 흐름은 종가베팅·VCP 신호의 수급 점수와 1일 순매수 표시이며, 모두 이 정규화기 결과를 읽는다. 격리 사본에서 가짜 Toss 응답(최신일 수량 공란, 전부 공란, 정상)을 `TossCollector.get_investor_trend` 자리에 끼우고 `calculate_supply_score_with_toss` 와 참조 경로의 결과를 수정 전후로 비교하는 하네스로 판정한다. 네트워크는 막는다.

## 계획 검토 반영(critic REVISE)

- REVISE(종가 없는 행이 정규화기에서 `None` 행으로 남음): 파서가 합계에 넣은 행만 `details` 로 넘기게 고쳤다. 기존 테스트 `test_parse_investor_trend_ignores_non_dict_or_zero_close_items` 의 `len(details) == 3` 은 이 의도된 변경에 맞춰 「종가 있는 행 하나」로 바꿨다. 최신 행의 종가·수량이 모두 빈 경우를 테스트로 추가했다.
- `_serialize_trend_map` 변경과 그 테스트는 필요 없다는 지적대로 뺐다.
- 공용 도우미 `optional_volume` 을 계획 문구에 반영했다.
- 권고 테스트 (a) 합계 결측이면 폴백하고 캐시에 저장하지 않음, (b) Toss SQLite 캐시 왕복 뒤 하루 `None` 보존, 다섯 날 실제 0 의 합계 0 을 추가했다. (c) 참조 채택 뒤 `screener.py:375` 경로는 외부 정규화기의 JSON 왕복 테스트와 `_score_supply_core` 의 기존 `None` 처리(`[VCP-057]`)로 갈음했다.
- 상세 API 의 `null` 이 화면에서 0 으로 보이는 점은 `[FE-048]` 로 등록했다.
- 기존 픽스처 `{"foreign": 10}` 에 `"institution": 0` 을 넣었다. 실제 파서는 두 키를 늘 채우며, 키가 없으면 결측으로 보는 것이 이번 설계다. 기대값은 바꾸지 않았다.
