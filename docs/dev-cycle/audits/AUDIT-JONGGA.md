# AUDIT-JONGGA — 종가베팅 감사

**감사 범위**: `app/routes/kr_market_jongga_*.py`, `app/routes/kr_market_data_jongga_routes.py`,
`frontend/src/app/dashboard/kr/closing-bet/`
**읽은 파일 수**: 9개 / 총 3,947줄

담당 경로를 판정하기 위해 다음 파일들을 참고로 함께 읽었으나, 감사 대상에는 넣지
않았습니다. `app/routes/kr_market_signal_common.py`,
`services/kr_market_ai_payload_service.py`, `chatbot/signal_context.py`,
`frontend/src/app/dashboard/kr/vcp/page.tsx`, `tests/` 아래 종가 관련 테스트 파일들이
여기에 해당합니다.

`[JONGGA-001]` 이 담당하는 `engine/generator.py` 의 인라인 페이즈 로직은 이 리포트에서
다루지 않았습니다. 백로그에 이미 등록되어 있는 `INFRA-001`, `INFRA-002`, `FE-001`,
`FE-002`, `FLOW-001`, `FLOW-002` 와 겹치는 지적도 제외했습니다.

---

## 1. 깨진 동작

### 1.1 Gemini 재분석을 실행하면 AI 분석 사유가 화면에서 사라진다

- 위치: `app/routes/kr_market_jongga_reanalysis_helpers.py:119-125`,
  `app/routes/kr_market_jongga_ai_payload_helpers.py:22-39`
- 증상: 관리자가 종가베팅 화면의 재분석 버튼을 눌러 Gemini 재분석을 실행하면, AI 분석
  패널이 실제 분석 사유 대신 `No analysis available.` 을 표시합니다. 재분석을 실행하기
  전에는 사유가 정상적으로 보이던 종목에서 발생합니다.
- 원인: `_apply_gemini_reanalysis_results` 는 분석 사유 원문을
  `signal["score"]["llm_reason"]` 에 저장하면서(119행), 바로 아래에서 만드는
  `signal["ai_evaluation"]` 에는 `action`, `confidence`, `model` 만 담고 `reason` 키를
  넣지 않습니다(121-125행). 그런데 `_extract_jongga_ai_evaluation` 의 우선순위 체인은
  `score_details.ai_evaluation` → `score.ai_evaluation` → `signal.ai_evaluation` →
  `score.llm_reason` 순서이므로, 세 번째 단계에서 사유가 없는 `signal["ai_evaluation"]`
  을 먼저 집어 들고 네 번째 폴백까지 내려가지 않습니다.
- 영향: `services/kr_market_ai_payload_service.py:110-115` 는 종가 데이터가 VCP 데이터보다
  최신일 때 종가 시그널로 AI 분석 payload 를 구성하므로, 이 상태의
  `gemini_recommendation` 이 그대로 프론트엔드에 전달됩니다. 그 값을 받는
  `frontend/src/app/dashboard/kr/vcp/page.tsx:1744` 가 `rec.reason || 'No analysis
  available.'` 을 렌더링하고, 같은 파일 941행의 배지 툴팁도 비어 버립니다. 사유 원문은
  `score.llm_reason` 에 온전히 남아 있는데도 화면에는 분석이 없는 것처럼 보입니다.

### 1.2 체크리스트의 수급 항목이 키 이름 불일치로 항상 꺼져 있다

- 위치: `app/routes/kr_market_jongga_normalize_helpers.py:114-120`,
  `frontend/src/app/dashboard/kr/closing-bet/page.tsx:2307-2308`
- 증상: 종가베팅 카드의 체크리스트에서 "수급 양호 (외인/기관)" 배지가 켜지지 않고, 외국인
  또는 기관의 5일 순매수가 양수인 종목에서도 회색 "수급 보통" 으로만 표시됩니다.
- 원인: 백엔드의 `_normalize_jongga_signal_for_frontend` 는 체크리스트를
  `{"has_news", "volume_surge", "supply_demand"}` 세 개 키로 만들면서, 118-119행에서
  `foreign_5d` 와 `inst_5d` 를 실제로 계산해 `supply_demand` 에 담습니다. 반면 프론트엔드는
  `signal.checklist?.supply_positive` 를 읽습니다. 계산된 값이 어느 쪽에서도 소비되지
  않습니다. 프론트엔드의 `ChecklistDetail` 인터페이스(page.tsx:71-78)는 여섯 개 키를
  선언하지만 백엔드가 채우는 것은 세 개뿐이고, 그중 겹치는 것은 `has_news` 와
  `volume_surge` 두 개입니다.
- 영향: 저장소 안에 두 가지 표기가 함께 존재하기 때문에 한쪽만 고칠 위험이 큽니다.
  `tests/app/test_kr_market_helpers_contract.py:308` 은 `checklist["supply_demand"] is
  True` 를 단언해 잘못된 키를 고정하고 있고, `scripts/generate_mock_jongga.py:36` 과
  `tests/scripts/test_init_data_vcp_scheduler.py:270` 은 반대로 `supply_positive` 를
  씁니다. 최근 커밋에서 처리한 `ISSUE-006`(대소문자 불일치)과 같은 유형의 결함입니다.

### 1.3 AI 분석을 받지 않은 종목에 조작된 확신도와 매수 추천이 표시된다

- 위치: `frontend/src/app/dashboard/kr/closing-bet/page.tsx:1959-1966`,
  같은 파일 `2128-2152`
- 증상: AI 분석 결과가 전혀 없는 종목의 카드에도 `BUY` 배지와 확신도 막대가 그려지고,
  S 등급 종목에서는 확신도가 100% 로 표시됩니다.
- 원인: 1960-1966행의 마지막 폴백이 `action` 을 등급에서 유도하고
  (`['S','A'].includes(signal.grade) ? 'BUY' : 'HOLD'`), `confidence` 를
  `signal.score.total * 8 + (signal.grade === 'S' ? 10 : 0)` 이라는 임의의 식으로
  만들어 냅니다. 총점 상한은 같은 파일 1344행의 안내대로 19점이므로 이 식은 최대 162 를
  내고, 2148행과 2151행의 `Math.min(aiEval.confidence, 100)` 에 걸려 100% 로 잘립니다.
  총점이 12점만 되어도 이미 100% 에 도달합니다.
- 영향: 이 값을 감싸는 툴팁은 2130행에서 "Gemini AI의 매매 추천입니다", 2141행에서
  "AI가 평가한 추천 신뢰도입니다" 라고 설명하므로, 사용자는 계산으로 지어낸 숫자를
  AI 가 산출한 신뢰도로 읽게 됩니다. 추정임을 알리는 표시는 1964행이 넣는
  `Est. (Waiting for AI)` 라는 모델 이름표뿐인데, 그 이름표는 2213행의 두 번째 칼럼에
  렌더링되어 확신도 막대(첫 번째 칼럼)와 시각적으로 떨어져 있습니다.

---

## 2. 중복

### 2.1 숫자와 티커 정규화 헬퍼가 세 벌로 나뉘어 동작이 서로 다르다

- 위치: `app/routes/kr_market_signal_common.py:47-76`,
  `app/routes/kr_market_jongga_normalize_helpers.py:10-33`,
  `app/routes/kr_market_jongga_grade_helpers.py:23-70`
- 내용: 같은 목적의 문자열 숫자 변환기가 세 곳에 각각 구현되어 있고, 제거하는 기호가
  서로 다릅니다. 공통 모듈의 `_safe_float` 와 `_safe_int` 는 쉼표, 원화 기호, 달러 기호,
  퍼센트 기호를 제거합니다. 종가 정규화 헬퍼의 동명 함수는 퍼센트 기호를 제거하지
  않습니다. 종가 등급 헬퍼의 `_to_float` 와 `_to_int` 는 `_normalize_numeric_text` 를
  거쳐 퍼센트 기호와 "원" 글자까지 제거합니다. 즉 `"5%"` 라는 입력이 어느 경로를 타느냐에
  따라 `5.0` 이 되기도 하고 `0.0` 이 되기도 합니다.
- 티커 정규화도 같은 상황입니다. `_normalize_ticker`(normalize_helpers:10-15)는 숫자가
  없으면 빈 문자열을 돌려주고, `_normalize_stock_code`(grade_helpers:67-70)는 같은
  경우에 `"000000"` 을 돌려줍니다. 두 규약이 충돌하기 때문에
  `normalize_helpers.py:54` 에 `ticker == "000000"` 을 걸러 내는 방어 코드가 따로
  들어가 있습니다.
- 위험: `kr_market_jongga_ai_payload_helpers.py:10` 이 이미 공통 모듈의 `_safe_float` 를
  가져다 쓰고 있으므로, 공용 구현은 이미 닿을 수 있는 자리에 있습니다. 그럼에도 한 파일
  건너에 같은 이름으로 다른 동작을 하는 사본이 있어서, 한쪽 함수만 고치면 나머지 경로가
  조용히 어긋납니다.

### 2.2 Tooltip 컴포넌트가 공용 파일과 별개로 두 번 더 정의되어 있다

- 위치: `frontend/src/app/components/Tooltip.tsx:13`,
  `frontend/src/app/dashboard/kr/closing-bet/page.tsx:11`,
  `frontend/src/app/dashboard/data-status/page.tsx:9`
- 내용: 공용 컴포넌트가 이미 존재하고 `frontend/src/app/dashboard/kr/page.tsx:8` 과
  `frontend/src/app/dashboard/kr/cumulative/CumulativeClientPage.tsx:5` 가 그것을 가져다
  쓰는데, 종가베팅 페이지와 데이터 상태 페이지는 각자 파일 안에서 같은 컴포넌트를 다시
  정의합니다. 종가베팅 쪽 사본은 공용 버전에 없는 `wide` 와 `width` 프롭을 갖고 있고,
  공용 버전에는 있는 `as` 프롭이 없습니다.
- 위험: 툴팁의 배경색이나 z-index 를 조정하는 작업이 들어오면 세 곳을 모두 찾아야
  하는데, 이름이 같아서 검색 결과만으로는 어느 것이 실제로 쓰이는지 구분되지 않습니다.

---

## 3. 과잉 설계

### 3.1 `_recalculate_jongga_grades` 의 기존 집계 승계 블록은 실행되지만 결과에 남지 않는다

- 위치: `app/routes/kr_market_jongga_grade_helpers.py:214-229`
- 내용: 214-223행은 기존 `data["by_grade"]` 의 값을 `new_by_grade` 로 옮겨 담습니다.
  그런데 곧바로 이어지는 225-229행이 `grade_count` 에 있는 모든 키를 덮어쓰고,
  `grade_count` 는 202행에서 `{"S": 0, "A": 0, "B": 0, "D": 0}` 으로 초기화되어 네 키를
  항상 갖고 있습니다. 따라서 214-223행이 읽어 온 값은 예외 없이 전부 교체됩니다.
- 판단: 열 줄 남짓이 결과에 아무 영향을 주지 않으면서, 읽는 사람에게는 "기존 집계를
  일부 보존하는 규칙이 있다" 는 잘못된 인상을 줍니다.

### 3.2 종가 헬퍼 재수출 계층이 소비자 하나를 위해 유지되고 있다

- 위치: `app/routes/kr_market_jongga_signal_helpers.py:1-55`
- 내용: 이 파일은 구현을 전혀 담지 않고 네 모듈에서 가져온 18개 심볼을 그대로 다시
  내보내기만 합니다. 이 파일을 가져다 쓰는 곳은 `app/routes/kr_market_signal_helpers.py:9`
  하나뿐이고, 그 파일 역시 재수출 계층이어서 `app/routes/kr_market_helpers.py:33` 이 다시
  가져가고, 최종 소비자인 `app/routes/kr_market_route_registry.py` 까지 재수출이 세 겹
  쌓여 있습니다.
- 판단: 파일 머리말은 "기존 import 경로를 유지" 하기 위한 호환 계층이라고 밝히고
  있는데, 실제 호출자는 이미 세 겹 위에 있고 테스트 두 개
  (`tests/services/test_jongga_reanalyze_supply.py:7`,
  `tests/manual/qa_jongga_quality_loop.py:38`)는 계층을 건너뛰고 구현 모듈을 직접
  가져옵니다. 유지할 이유가 남아 있는지 확인할 만합니다.

---

## 4. 비대한 파일

### 4.1 종가베팅 페이지 한 파일이 여섯 가지 책임을 함께 지고 있다

- 위치: `frontend/src/app/dashboard/kr/closing-bet/page.tsx` (2,680줄)
- 내용: 최상위 선언이 열세 개이고, 성격이 다음과 같이 갈립니다.
  1. 범용 프리미티브: `Tooltip`(11행), `PriceRangeBar`(306행), `StatBox`(1884행),
     `ScoreBar`(2660행)
  2. 외부 위젯 연동: `TradingViewChart`(209행), `ChartModal`(269행)
  3. 별도 API 를 호출하는 모달: `StockDetailModal`(450행)
  4. 폴링을 수행하는 상태 박스: `DataStatusBox`(1656행)
  5. 정적 참조 문서: `GradeGuideModal`(2483행부터 177줄에 걸친 등급 기준표)
  6. 페이지 본체와 카드: `JonggaV2Page`(857행), `SignalCard`(1905행),
     `getTrendingThemes`(351행), `TrendingThemesBox`(367행)
- 판단: 줄 수 자체보다 성격이 다른 책임이 섞여 있는 점이 문제입니다. 1번과 5번은 종가베팅
  고유 로직을 전혀 담고 있지 않고, `frontend/src/app/components/` 라는 정착된 자리가 이미
  있어서 옮길 곳을 새로 정할 필요도 없습니다. 실제로 §2.2 의 Tooltip 중복이 이 구조에서
  나왔고, `ClosingBetCriteriaModal` 은 같은 성격인데도 이미 컴포넌트 디렉터리에 나가
  있습니다(5-7행의 import 참조). 한 화면의 결함을 고치려고 파일을 열면 관계없는 열두 개
  선언을 함께 지나가야 합니다.

---

## 5. 검증 공백

### 5.1 정렬과 정규화, AI 추출 헬퍼 네 개에 대응하는 테스트가 없다

- 위치와 대상:
  - `app/routes/kr_market_jongga_grade_helpers.py:238-253` `_jongga_sort_key`
  - `app/routes/kr_market_jongga_normalize_helpers.py:73-134`
    `_normalize_jongga_signal_for_frontend`
  - `app/routes/kr_market_jongga_ai_payload_helpers.py:13-39`
    `_extract_jongga_ai_evaluation`
  - `app/routes/kr_market_jongga_reanalysis_helpers.py:72-82`
    `_build_normalized_gemini_result_map`
- 내용: `tests/` 전체에서 위 네 심볼을 이름으로 참조하는 파일이 하나도 없습니다. 네 개
  모두 분기를 담고 있습니다. `_jongga_sort_key` 는 등급 우선순위 표에 없는 등급을 조용히
  0 으로 떨어뜨리는 판정을 하고, `_normalize_jongga_signal_for_frontend` 는 목표가와
  손절가를 `entry_price * 1.09` 및 `entry_price * 0.95` 로 합성하며(123-126행), 이 두
  계수는 `engine/constants.py` 에 없고 이 파일에만 나타납니다.
  `_extract_jongga_ai_evaluation` 은 네 단계 우선순위 체인이고, 바로 §1.1 의 결함이
  일어나는 자리입니다. `_build_normalized_gemini_result_map` 은 정규식으로 종목명 뒤의
  괄호를 떼어 내는 파서입니다.
- 영향: §1.1 이 지금까지 드러나지 않은 이유가 여기에 있습니다. 우선순위 체인을 검사하는
  테스트가 하나라도 있었다면 재분석 경로에서 `reason` 이 사라지는 것을 잡을 수 있었습니다.

### 5.2 종가베팅 페이지의 필터 분기와 AI 폴백 단계에 테스트가 없다

- 위치: `frontend/src/app/dashboard/kr/closing-bet/page.tsx:914-940`(필터),
  `1941-1966`(AI 평가 3단 폴백),
  `frontend/src/app/dashboard/kr/closing-bet/page.regression-001.test.tsx`
- 내용: 이 화면의 유일한 vitest 파일은 `ISSUE-001` 회귀만 검사하며, 조회가 끝난 뒤
  `NO DATA` 가 표시되는지 한 가지만 확인합니다. `getFilteredSignals` 의 네 가지 필터
  분기(거래대금, 상승률, 등급 이상 비교, 총점)와 `SignalCard` 의 AI 평가 3단 폴백은
  어느 테스트도 통과하지 않습니다. §1.3 의 결함이 세 번째 폴백에 들어 있습니다.
- 부수 사항: 같은 테스트 파일 12-14행은 `/api/kr/jongga-v2/dates` 응답을
  `{ dates: [] }` 라는 객체로 흉내 내는데, 실제 백엔드
  (`app/routes/kr_market_data_jongga_routes.py:69-78`)는 배열을 그대로 돌려주고
  페이지(1131-1135행)도 `Array.isArray` 로 배열을 기대합니다. 지금은 두 경우 모두 빈
  목록이라 결과가 같지만, 날짜 목록이 관여하는 검사를 추가하면 이 목이 실제 응답과
  어긋납니다.

---

## 요약

| 관점 | 발견 | 그중 P0 | P1 | P2 |
|---|---|---|---|---|
| 깨진 동작 | 3 | 3 | 0 | 0 |
| 중복 | 2 | 0 | 1 | 1 |
| 과잉 설계 | 2 | 0 | 0 | 2 |
| 비대한 파일 | 1 | 0 | 1 | 0 |
| 검증 공백 | 2 | 0 | 2 | 0 |
| 합계 | 10 | 3 | 4 | 3 |

---

# 2부: TODO 항목 초안

일련번호는 `docs/dev-cycle/` 전체에서 `JONGGA` 약어의 최대 번호가 `JONGGA-001` 임을
확인한 뒤 `JONGGA-002` 부터 매겼습니다. 티어는
`.claude/skills/dev-cycle/references/tier-rules.md` §3 절차로 판정했으며, 다섯 항목 모두
§2 의 위험 경로 목록에 닿지 않으므로 예상 변경 줄 수로 갈랐습니다.

## P0 — 즉시

### [JONGGA-002] Gemini 재분석 결과의 AI 사유 유실 수정
- 카테고리: 종가베팅 | 티어: T1 | 근거: AUDIT-JONGGA §1.1
- 구현 변경은 두 파일에서 30줄 이내로 끝날 것으로 봅니다. 테스트 파일은 `tier-rules.md`
  §1 마지막 문단의 제외 조항에 따라 합계에서 뺐습니다.
- [ ] `_apply_gemini_reanalysis_results` 가 `ai_evaluation` 에 `reason` 을 함께 담도록 수정
- [ ] `_extract_jongga_ai_evaluation` 이 사유가 빈 항목을 만나면 `score.llm_reason` 으로
      내려가도록 우선순위 체인 보강
- [ ] 재분석 전후로 `gemini_recommendation.reason` 이 유지되는지 검사하는 회귀 테스트 추가
- [ ] AI 분석 payload 를 소비하는 VCP 화면의 분석 사유 표시가 복구되는지 확인

### [JONGGA-003] 체크리스트 수급 항목의 키 이름 통일
- 카테고리: 종가베팅 | 티어: T1 | 근거: AUDIT-JONGGA §1.2
- 프론트엔드와 목 데이터 생성기가 이미 `supply_positive` 를 쓰고 있으므로, 백엔드를
  그쪽에 맞추는 방향이 변경 범위가 작습니다.
- [ ] `_normalize_jongga_signal_for_frontend` 가 만드는 체크리스트 키를 `supply_positive`
      로 맞춤
- [ ] `tests/app/test_kr_market_helpers_contract.py:308` 의 단언을 새 키로 갱신
- [ ] 저장소에 남은 `supply_demand` 표기를 전수 확인해 종가 체크리스트 경로에서 제거
- [ ] 외국인·기관 5일 순매수가 양수일 때 배지가 켜지는지 화면에서 확인

### [JONGGA-004] AI 미분석 종목의 확신도 추정치 표기 정리
- 카테고리: 종가베팅 | 티어: T2 | 근거: AUDIT-JONGGA §1.3
- 폴백 블록(1959-1966행)과 확신도 렌더 블록(2128-2154행)을 함께 손대고 대체 표기를
  넣으면 50줄을 넘길 것으로 보아 T2 로 판정했습니다. 화면 표시가 바뀌므로 T2 검증이
  요구하는 실측이 실제로 필요합니다. Next.js 가 16.1.6 이므로
  `frontend-skills.md` §3 에 따라 `next-dev-loop` 이 아니라 agent-browser 로 실측합니다.
- [ ] 등급에서 확신도를 유도하는 계산식을 제거하거나, 산출값을 확신도가 아닌 별도 이름으로
      분리
- [ ] AI 분석 결과가 없는 상태에서는 확신도 막대와 매매 추천 배지를 감추거나 추정임을
      배지 자리에서 바로 알 수 있게 표기
- [ ] 두 툴팁 문구를 실제 데이터 출처에 맞게 수정
- [ ] AI 결과가 없는 시그널과 있는 시그널을 각각 렌더링하는 vitest 추가
- [ ] agent-browser 로 카드 표시를 실측

## P1 — 이번 주기

### [JONGGA-005] 종가 라우트의 숫자·티커 정규화 헬퍼 통합
- 카테고리: 종가베팅 | 티어: T2 | 근거: AUDIT-JONGGA §2.1, §5.1
- [ ] `kr_market_signal_common` 의 `_safe_float` 와 `_safe_int` 로 변환 규칙을 일원화하고,
      퍼센트 기호와 "원" 글자 처리 기준을 한 곳에서 정함
- [ ] 종가 정규화 헬퍼와 등급 헬퍼의 지역 사본을 제거
- [ ] 티커 정규화의 빈 값 규약을 하나로 정하고, `"000000"` 방어 코드를 정리
- [ ] `_jongga_sort_key` 와 `_normalize_jongga_signal_for_frontend` 에 대한 테스트를
      함께 추가하고, 목표가·손절가 계수 1.09 와 0.95 의 근거를 상수로 옮길지 판단
- [ ] pytest 전체 통과 확인

### [JONGGA-006] 종가베팅 페이지에서 범용 컴포넌트와 정적 모달 분리
- 카테고리: 종가베팅 | 티어: T3 | 근거: AUDIT-JONGGA §2.2, §4.1
- 이동만으로도 추가와 삭제의 합계가 300줄을 크게 넘으므로 T3 입니다. 분량이 부담되면
  범용 프리미티브 이동과 정적 모달 이동을 두 항목으로 쪼개는 방안을 먼저 검토합니다.
- [ ] `Tooltip` 지역 정의를 제거하고 `frontend/src/app/components/Tooltip.tsx` 를 사용.
      필요한 `wide` 와 `width` 프롭은 공용 컴포넌트 쪽에 반영
- [ ] `data-status/page.tsx` 의 세 번째 Tooltip 사본도 같은 방향으로 정리
- [ ] `PriceRangeBar`, `StatBox`, `ScoreBar` 를 컴포넌트 디렉터리로 이동
- [ ] `GradeGuideModal` 을 `ClosingBetCriteriaModal` 과 같은 자리로 이동
- [ ] `npm run build`, `npm run type-check`, vitest 전체 통과 확인
- [ ] agent-browser 로 종가베팅 화면과 데이터 상태 화면을 실측
