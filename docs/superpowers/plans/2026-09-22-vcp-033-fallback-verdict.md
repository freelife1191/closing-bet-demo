# [VCP-033] AI 규칙 기반 폴백의 판정 축 교체 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `engine/vcp_ai_analyzer_helpers.py` 의 `build_vcp_rule_based_recommendation` 이 합산 점수로 SELL·BUY 를 가르지 않고, 5일·1일 수급이 모두 순매도일 때만 SELL, 그 밖에는 HOLD 를 내며 BUY 는 내지 않게 한다.

**Architecture:** 한 함수 안의 두 갈래(정보 완전·정보 부족)가 서로 다른 점수 문턱을 쓰던 것을 수급 하나로 판정하는 한 흐름으로 합친다. 근거 문장은 종전 구조(패턴 상태 문장 + 5일·1일 수급 문장 + 맺음 문장)를 유지하되, 패턴 상태 문장을 만드는 `_describe_vcp_state` 가 합산 점수 대신 수축비만 보게 하고 점수 라벨을 「종합 점수」로 바로잡는다. 신뢰도는 계산하지 않고 55 하나로 둔다. 호출부(`engine/vcp_ai_analyzer.py` 의 Z.ai 네 갈래)와 프롬프트는 손대지 않는다.

**Tech Stack:** Python 3.11, pytest. 새 의존성 없음.

**Spec:** 설계 문서 없음(bounded). 범위는 `docs/dev-cycle/TODO.md` 의 `[VCP-033]` 항목이고, 승인은 2026-09-22 사용자 「백로그도 설계해서 진행해」 뒤 AskUserQuestion 「[VCP-033] VCP 설계」에서 추천안 「수급 이탈만 SELL, 나머지 HOLD」를 고른 것이다.

**계획 검토:** oh-my-claudecode:critic(`vcp033-plan-critic`, 2026-09-22) REVISE. MAJOR 1(BUY 를 고정한 `changes_by_signal_state` 검사의 대체를 명시하지 않음) → Task 1 에 대체를 명시. MAJOR 2(사본 자료에 5일·1일 모두 순매도인 행이 0건이라 하네스의 SELL 단언이 공허) → Task 3 에 합성 순매도 행을 필수로 추가. MINOR 3(「정보가 부족하여 보수적으로 SELL」 문구 모순) → 맺음 문장을 action 별로 나눔. MINOR 4(0.5 리터럴·`≤ 0.5` 갈래 검사 없음) → 모듈 상수 두 개와 검사 추가. MINOR 5(5일 음수·1일 0 경계 검사 없음) → 검사 추가. MINOR 6(패턴 상태 문장이 score 유무에 묶임) → 수축비만 있어도 상태 문장을 씀. MINOR 7(결측 수축비가 0 으로 저장되어 「강한 편」으로 읽힘) → 0 이하는 결측으로 취급. MINOR 8(하네스의 `None` 수급·ASSERT 스위치·사본 범위) → 반영. 설계 결정과 함수 본문은 코드와 맞다고 확인. 구현 뒤 심층 리뷰(oh-my-claudecode:critic `vcp033-deep-review`) REVISE: MAJOR 1(「시그널 행에 `vcp_score` 가 없다」는 전제 오류 — `scripts/init_data.py:1400` 이 0~10 으로 양자화된 값을 싣고 `build_vcp_prompt` 도 읽는다 → 아래 제약과 QA 이월 항목을 정정), MINOR 2(0.5 문턱이 `engine/vcp.py:164` 리터럴과 중복 → `VCPThresholds.STRONG_CONTRACTION_RATIO` 로 묶고 양쪽이 읽음), MINOR 3(경계 0.5·0.7·음수 검사 없음 → 매개변수 검사 추가), MINOR 4(표시값 「0.50」 두 종목이 다른 서술 → 소수 둘째 자리 반올림 값으로 판정), MINOR 5(600자 절단, 정보) 반영.

## Global Constraints

- 티어 T3. `engine/vcp_ai_analyzer_helpers.py` 는 `tier-rules.md` §2 「VCP 판정」 위험 경로다. 줄 수와 무관하게 `/ponytail-review` → `/code-review` → `/review`, pytest·vitest 전체, QA 2단계를 거친다.
- 건드리는 파일은 `engine/vcp_ai_analyzer_helpers.py`, `tests/engine/test_vcp_ai_analyzer_helpers_refactor.py`, `tests/engine/test_vcp_ai_analyzer_refactor.py`(폴백 결과를 BUY 로 고정한 검사 한 건)에, 심층 리뷰 MINOR 2 로 `engine/constants_market_scoring.py`(`STRONG_CONTRACTION_RATIO` 한 줄)와 `engine/vcp.py`(점수 구간의 리터럴 0.5·0.7 을 상수로, 동작 변화 없음)를 더한 다섯이다.
- 폴백이 받는 `stock_data` 는 `engine/screener_result_builders.py` `build_signal_item` 이 만든 시그널 행이다. 열은 `score`(합산: 수급 ≤70 + 거래량 ≤20 + VCP ≤10), `contraction_ratio`(결측이면 0 으로 저장됨), `foreign_5d`, `inst_5d`, `foreign_1d`, `inst_1d`(1일은 결측이면 `None`)이고, `vcp_score` 는 `scripts/init_data.py:1400` 이 0~10 으로 양자화해 싣는 값이라(저장 행은 패턴 통과라 5~10) 원점수 해상도가 없다. 그래서 패턴 상태 서술은 수축비로 한다. 저장된 시그널은 `is_vcp` 를 통과했으므로(`engine/vcp.py:204`) 수축비 ≤ `VCP_THRESHOLDS.CONTRACTION_RATIO`(0.7, 정의는 `engine/constants_market_scoring.py:30`) 다.
- 종전 판정(`score <= 62 → SELL`, `score >= 78 ∧ … → BUY`)은 `[VCP-032]` 이전의 저장 게이트(합산 ≥ 60)를 전제한 것이다. 이제 합산 27~53 의 시그널이 정상 저장되므로 폴백을 타는 시그널은 거의 예외 없이 SELL 이었다(기준선: 사본 20행 전부 SELL 72%).
- 폴백은 BUY 를 내지 않는다. LLM 응답을 읽지 못한 것은 매수 근거가 아니다. 이 결정으로 「폴백 BUY」를 고정한 검사 두 건(`tests/engine/test_vcp_ai_analyzer_helpers_refactor.py` 의 `changes_by_signal_state`, `tests/engine/test_vcp_ai_analyzer_refactor.py` 의 `all_parsing_fails`)의 계약이 바뀐다. 삭제가 아니라 같은 입력으로 새 계약을 고정하는 검사로 대체하고 아카이브에 대체 내역을 적는다.
- 결측 처리 원칙(`safe_optional_float`, 결측을 기본값으로 바꾸지 않음)과 정보 부족 갈래의 신뢰도 55 는 유지한다. 맺음 문장은 action 별로 나눈다. HOLD 는 종전 「정보가 부족하여 보수적으로 HOLD 판단을 유지합니다」(정보 부족)·「이 신호를 종합해 현재 판단은 HOLD입니다」(정보 완전), SELL 은 「5일·1일 수급이 모두 순매도라 SELL 로 판단합니다」 하나다. SELL 은 실제 근거가 모두 관측된 뒤에만 나오므로 「보수적으로 SELL」 이라는 말은 쓰지 않는다.
- 수축비 0 이하는 결측으로 본다. `build_signal_item` 이 결측을 0 으로 저장하므로 그대로 두면 새 규칙에서 「강한 편」으로 읽힌다.
- 수축비 문턱은 `VCPThresholds` 의 `STRONG_CONTRACTION_RATIO`(0.5, `engine/vcp.py` 의 40점 구간과 같은 경계, 심층 리뷰 MINOR 2 로 상수화)와 `CONTRACTION_RATIO`(0.7, 패턴 통과 문턱) 둘이다. 판정과 문장은 소수 둘째 자리로 반올림한 값을 함께 쓴다(MINOR 4).
- 원본 `data/` 는 읽기 전용이다. QA 하네스는 저장소 전체 사본(scratchpad `jongga041-scratch`, 소스와 `data/` 최상위 파일 포함)을 cwd 로 삼아 `vcp_signals_latest.json` 행을 읽고 파싱 실패를 주입한 가짜 Z.ai 클라이언트로 `_analyze_with_zai` 를 돌린다. 운영 서버와 3500·5501 포트에 접근하지 않는다.
- 범위 밖: `_analyze_with_zai` 의 모델 체인·재시도, 프롬프트(`build_vcp_prompt`), Gemini·Perplexity 갈래(폴백을 부르지 않음), 양자화된 `vcp_score` 를 서술에 함께 쓰는 일(별도 판단), 신뢰도 55 를 화면에서 어떻게 보일지.

## Review Focus

1. 기존 일곱 검사 가운데 `changes_by_signal_state` 를 대체하고 나머지 여섯(`handles_nan…`, `keeps_missing_one_day…` 5벌, `keeps_absent_core_data…`, `keeps_absent_one_day…`, `partial_sell…`, `preserves_real_zero…`)이 고정한 문구·신뢰도가 새 계약에서 유지되거나 의도한 곳만 바뀌는지: Task 1.
2. `_describe_vcp_state` 가 수축비만 보게 바뀐 뒤 세 문장의 경계(`0 < r ≤ 0.5`, `≤ 0.7`, 그 밖)와 결측(0 이하) 처리가 검사로 고정되는지: Task 2.
3. 하네스가 실제 시그널 20행에서 BUY 0·SELL 0(순매도 행 없음)이고, 합성 순매도 행에서만 SELL 을 내는지: Task 3.

---

### Task 1: 판정 축을 수급 하나로 합친다

**Files:**
- Modify: `engine/vcp_ai_analyzer_helpers.py:539-630` (`build_vcp_rule_based_recommendation`)
- Test: `tests/engine/test_vcp_ai_analyzer_helpers_refactor.py:253-427`, `tests/engine/test_vcp_ai_analyzer_refactor.py:851-854`

**Interfaces:**
- Consumes: `safe_optional_float`, `_describe_flow_state`, `_topic_particle`(기존), Task 2 의 `_describe_vcp_state(contraction_ratio)`.
- Produces: `build_vcp_rule_based_recommendation(*, stock_name, stock_data) -> {"action": "SELL"|"HOLD", "confidence": 55, "reason": str}`. 시그니처는 그대로다.

- [ ] **Step 1: 검사를 새 계약으로 바꾼다**

`tests/engine/test_vcp_ai_analyzer_helpers_refactor.py`:

(가) `test_build_vcp_rule_based_recommendation_changes_by_signal_state`(253~291행)를 **같은 입력 세 벌로** 다음 검사로 대체한다.

```python
def test_build_vcp_rule_based_recommendation_never_buys_and_sells_only_on_outflows():
    """[VCP-033] 폴백은 BUY 를 내지 않고, 5일·1일 수급이 모두 순매도일 때만 SELL 이다."""
    inflow_case = build_vcp_rule_based_recommendation(
        stock_name="A",
        stock_data={"score": 83, "contraction_ratio": 0.72, "foreign_5d": 1000, "inst_5d": 400, "foreign_1d": 100, "inst_1d": 50},
    )
    mixed_case = build_vcp_rule_based_recommendation(
        stock_name="B",
        stock_data={"score": 69, "contraction_ratio": 0.9, "foreign_5d": 10, "inst_5d": -5, "foreign_1d": 0, "inst_1d": 0},
    )
    outflow_case = build_vcp_rule_based_recommendation(
        stock_name="C",
        stock_data={"score": 58, "contraction_ratio": 1.03, "foreign_5d": -500, "inst_5d": -300, "foreign_1d": -80, "inst_1d": -40},
    )

    assert inflow_case["action"] == "HOLD"
    assert mixed_case["action"] == "HOLD"
    assert outflow_case["action"] == "SELL"
    assert outflow_case["reason"].endswith("5일·1일 수급이 모두 순매도라 SELL 로 판단합니다.")
    assert {inflow_case["confidence"], mixed_case["confidence"], outflow_case["confidence"]} == {55}
```

(나) 새 검사 세 건을 더한다.

```python
def test_rule_based_fallback_holds_low_composite_score_with_inflows():
    """[VCP-033] 합산 27~53 의 정상 시그널(수급 유입)은 SELL 이 아니라 HOLD 다."""
    result = build_vcp_rule_based_recommendation(
        stock_name="톱텍",
        stock_data={"score": 31, "contraction_ratio": 0.55, "foreign_5d": 120, "inst_5d": 30, "foreign_1d": 5, "inst_1d": 2},
    )

    assert result["action"] == "HOLD"
    assert result["confidence"] == 55
    assert "종합 점수 31.0점" in result["reason"]
    assert "변동성 수축 신호가 유지되는 구간입니다" in result["reason"]
    assert result["reason"].endswith("이 신호를 종합해 현재 판단은 HOLD입니다.")


def test_rule_based_fallback_treats_flat_one_day_flow_as_not_outflow():
    """5일이 순매도여도 1일이 0 이면 순매도가 아니다(`<` 를 `<=` 로 잘못 쓰면 잡힌다)."""
    result = build_vcp_rule_based_recommendation(
        stock_name="A",
        stock_data={"score": 40, "contraction_ratio": 0.6, "foreign_5d": -100, "inst_5d": 0, "foreign_1d": 0, "inst_1d": 0},
    )

    assert result["action"] == "HOLD"
    assert "5일 수급은 순매도 우위입니다. 1일 수급은 중립입니다." in result["reason"]


def test_rule_based_fallback_describes_contraction_without_score():
    """패턴 상태 문장은 수축비만으로 정하고, 0 이하 수축비는 결측으로 본다."""
    strong = build_vcp_rule_based_recommendation(stock_name="A", stock_data={"contraction_ratio": 0.39})
    missing = build_vcp_rule_based_recommendation(stock_name="B", stock_data={"score": 27, "contraction_ratio": 0})

    assert "수축비율 0.39로 변동성 수축 신호가 강한 편입니다." in strong["reason"]
    assert strong["reason"].endswith("정보가 부족하여 보수적으로 HOLD 판단을 유지합니다.")
    assert "종합 점수 27.0점이 확인됩니다." in missing["reason"]
    assert "강한 편" not in missing["reason"] and "수축비율" not in missing["reason"]
```

(다) `test_rule_based_fallback_partial_sell_uses_only_real_negative_evidence` 의 기대를 바꾼다.

```python
    assert low_score["action"] == "HOLD"
    assert low_score["confidence"] == 55
    assert "종합 점수 58.0점" in low_score["reason"]
    assert negative_flows["action"] == "SELL"
    assert negative_flows["confidence"] == 55
    assert "점수" not in negative_flows["reason"]
    assert "5일 수급은 순매도 우위입니다" in negative_flows["reason"]
    assert "1일 수급은 순매도 우위입니다" in negative_flows["reason"]
    assert negative_flows["reason"].endswith("5일·1일 수급이 모두 순매도라 SELL 로 판단합니다.")
```

(라) `test_rule_based_fallback_preserves_real_zero_and_complete_verdicts` 를 `test_rule_based_fallback_complete_data_verdicts_ignore_score` 로 바꾸고 기대를 다음으로 둔다(입력 세 벌은 그대로).

```python
    assert zero_case["action"] == "HOLD"
    assert zero_case["confidence"] == 55
    assert "1일 수급은 중립입니다" in zero_case["reason"]
    assert buy_case["action"] == "HOLD"
    assert buy_case["confidence"] == 55
    assert buy_case["reason"] == (
        "D는 종합 점수 83.0점, 수축비율 0.72로 변동성 수축 신호가 약화된 구간입니다. "
        "5일 수급은 순매수 우위입니다. 1일 수급은 순매수 우위입니다. "
        "이 신호를 종합해 현재 판단은 HOLD입니다."
    )
    assert sell_case["action"] == "SELL"
    assert sell_case["confidence"] == 55
```

(마) `tests/engine/test_vcp_ai_analyzer_refactor.py:851-854`:

```python
    assert result is not None
    assert result["action"] == "HOLD"
    assert result["confidence"] == 55
    assert "현재 판단은 HOLD" in result["reason"]
```

나머지 검사(`handles_nan_without_literal_nan_text`, `keeps_missing_one_day_flow_out_of_reason` 5벌, `keeps_absent_core_data_as_conservative_hold`, `keeps_absent_one_day_fields_out_of_verdict`)는 그대로 둔다. 새 구현에서도 참이어야 한다.

- [ ] **Step 2: 실패를 확인한다**

Run: `source venv/bin/activate && pytest -q -p no:cacheprovider tests/engine/test_vcp_ai_analyzer_helpers_refactor.py tests/engine/test_vcp_ai_analyzer_refactor.py -k "rule_based or fallback"`
Expected: 바꾼 검사(`never_buys…`, `holds_low_composite…`, `treats_flat_one_day…`, `describes_contraction_without_score`, `partial_sell…`, `complete_data…`)와 analyzer 의 `all_parsing_fails` 가 FAIL, 나머지 PASS.

- [ ] **Step 3: 함수를 한 흐름으로 바꾼다**

`engine/vcp_ai_analyzer_helpers.py` 의 `build_vcp_rule_based_recommendation` 본문 전체를 다음으로 바꾼다.

```python
def build_vcp_rule_based_recommendation(
    *,
    stock_name: str,
    stock_data: dict[str, Any],
) -> dict[str, Any]:
    """LLM JSON 응답 복구 실패 시 사용하는 규칙 기반 보정 추천.

    판정 축은 수급뿐이다([VCP-033]). 5일·1일 수급이 모두 순매도면 SELL, 그 밖에는 HOLD 이고
    BUY 는 내지 않는다. 응답을 읽지 못한 것은 매수 근거가 아니다. 합산 점수(수급 70 + 거래량 20
    + VCP 10)는 패턴 강도가 아니어서 근거 문장에만 쓴다. 종전의 `score <= 62 → SELL` 은 저장
    게이트(합산 ≥ 60)를 전제한 것이라 [VCP-032] 뒤 거의 모든 시그널을 SELL 로 몰았다.
    """
    score = safe_optional_float(stock_data.get("score"))
    contraction_ratio = safe_optional_float(stock_data.get("contraction_ratio"))
    if contraction_ratio is not None and contraction_ratio <= 0:
        # build_signal_item 은 결측 수축비를 0 으로 저장한다. 0 은 「강한 수축」이 아니라 결측이다.
        contraction_ratio = None
    foreign_5d = safe_optional_float(stock_data.get("foreign_5d"))
    inst_5d = safe_optional_float(stock_data.get("inst_5d"))
    foreign_1d = safe_optional_float(stock_data.get("foreign_1d"))
    inst_1d = safe_optional_float(stock_data.get("inst_1d"))
    flow_5d = foreign_5d + inst_5d if foreign_5d is not None and inst_5d is not None else None
    flow_1d = foreign_1d + inst_1d if foreign_1d is not None and inst_1d is not None else None
    is_complete = all(
        value is not None
        for value in (score, contraction_ratio, foreign_5d, inst_5d, foreign_1d, inst_1d)
    )
    has_outflows = flow_5d is not None and flow_1d is not None and flow_5d < 0 and flow_1d < 0
    action = "SELL" if has_outflows else "HOLD"

    evidence: list[str] = []
    if score is not None and contraction_ratio is not None:
        evidence.append(
            f"종합 점수 {score:.1f}점, 수축비율 {contraction_ratio:.2f}로 {_describe_vcp_state(contraction_ratio)}."
        )
    elif score is not None:
        evidence.append(f"종합 점수 {score:.1f}점이 확인됩니다.")
    elif contraction_ratio is not None:
        evidence.append(f"수축비율 {contraction_ratio:.2f}로 {_describe_vcp_state(contraction_ratio)}.")
    if flow_5d is not None:
        evidence.append(f"{_describe_flow_state(flow_5d, '5일')}.")
    if flow_1d is not None:
        evidence.append(f"{_describe_flow_state(flow_1d, '1일')}.")
    detail = " ".join(evidence)
    if has_outflows:
        closing = "5일·1일 수급이 모두 순매도라 SELL 로 판단합니다."
    elif is_complete:
        closing = "이 신호를 종합해 현재 판단은 HOLD입니다."
    else:
        closing = "정보가 부족하여 보수적으로 HOLD 판단을 유지합니다."
    reason = f"{stock_name}{_topic_particle(stock_name)} {detail + ' ' if detail else ''}{closing}"
    return {
        "action": action,
        # 규칙 폴백은 신뢰도를 계산하지 않는다. AI 가 답하지 못한 자리라 낮은 값 하나로 둔다.
        "confidence": 55,
        "reason": reason[:600],
    }
```

- [ ] **Step 4: 통과를 확인한다** (Task 2 를 먼저 끝낸 뒤 실행한다. `_describe_vcp_state` 의 시그니처가 바뀌기 때문이다)

Run: `source venv/bin/activate && pytest -q -p no:cacheprovider tests/engine/test_vcp_ai_analyzer_helpers_refactor.py tests/engine/test_vcp_ai_analyzer_refactor.py`
Expected: 전부 PASS.

- [ ] **Step 5: 커밋은 dev-cycle 의 첫 커밋(정적 검증·QA 문서 뒤)에서 한다.** 여기서 따로 커밋하지 않는다.

### Task 2: 패턴 상태 문장을 수축비로만 만든다

**Files:**
- Modify: `engine/vcp_ai_analyzer_helpers.py:510-517` (`_describe_vcp_state`), 모듈 상단 import
- Modify: `engine/constants_market_scoring.py` (`VCPThresholds.STRONG_CONTRACTION_RATIO = 0.5` 추가), `engine/vcp.py:164-167` (리터럴 0.5·0.7 → 상수, 심층 리뷰 MINOR 2)

**Interfaces:**
- Consumes: `engine.constants.VCP_THRESHOLDS.CONTRACTION_RATIO`(0.7)·`STRONG_CONTRACTION_RATIO`(0.5). 모듈 상단에 `from engine.constants import VCP_THRESHOLDS` 를 추가한다(지금은 없다).
- Produces: `_describe_vcp_state(contraction_ratio: float) -> str`. Task 1 이 소수 둘째 자리로 반올림한 값으로 부른다. 다른 호출자는 없다.

- [x] **Step 1: 상수와 헬퍼를 바꾼다**

```python
def _describe_vcp_state(contraction_ratio: float) -> str:
    # 합산 점수는 패턴 강도가 아니므로 수축비만 본다([VCP-033]). 경계는 engine/vcp.py 의 점수 구간과 같은
    # 상수다. 저장된 시그널은 CONTRACTION_RATIO 이하다.
    if contraction_ratio <= VCP_THRESHOLDS.STRONG_CONTRACTION_RATIO:
        return "변동성 수축 신호가 강한 편입니다"
    if contraction_ratio <= VCP_THRESHOLDS.CONTRACTION_RATIO:
        return "변동성 수축 신호가 유지되는 구간입니다"
    return "변동성 수축 신호가 약화된 구간입니다"
```

0 이하는 Task 1 이 결측으로 걸러 여기에 오지 않는다. 경계(0.5·0.7 포함, 0.4952·0.5027 → 「0.50」 강함, 음수 결측)는
`test_rule_based_fallback_contraction_boundaries_follow_the_shown_two_decimals` 와 `..._treats_negative_contraction_ratio_as_missing`
가 고정한다(심층 리뷰 MINOR 3·4).

- [x] **Step 2: Task 1 Step 4 의 명령으로 통과를 확인한다.**

### Task 3: 파싱 실패를 주입한 하네스로 실제 시그널 행과 합성 순매도 행을 검사한다

**Files:**
- Create (scratchpad, 저장소 밖): `vcp033_qa.py`
- Create: `docs/dev-cycle/qa/VCP-033.md`

**Interfaces:**
- Consumes: 저장소 전체 사본(scratchpad `jongga041-scratch`)의 `data/vcp_signals_latest.json`(2026-09-21 시그널 20건, 읽기 전용), `VCPMultiAIAnalyzer._analyze_with_zai`, 가짜 `zai_client`(analyzer 테스트 807행과 같은 구조로 JSON 이 아닌 문장을 돌려준다), `asyncio.to_thread`·`asyncio.sleep` monkeypatch. 환경 변수 `ASSERT`(기본 1, 0 이면 집계만).
- Produces: 행마다 `(ticker, score, contraction_ratio, flow_5d, flow_1d, action, confidence, reason 앞 80자)` 와 집계. 실제 20행: BUY 0·SELL 0·HOLD 20(사본 자료에 5일·1일 모두 순매도인 행이 없다). 합성 행(한농화성 011500 의 5일 수급을 음수로 바꾼 사본 행, 메모리에서만): SELL 55 와 「… SELL 로 판단합니다.」.

- [ ] **Step 1: 하네스를 만든다**

```python
# vcp033_qa.py — 저장소 전체 사본 cwd 에서 실행. 원본 data/ 를 열지 않는다. ASSERT=0 이면 집계만 한다(기준선).
import asyncio, json, os, sys
from types import SimpleNamespace
from unittest import mock
sys.path.insert(0, ".")
from engine.vcp_ai_analyzer import VCPMultiAIAnalyzer

ASSERT = os.environ.get("ASSERT", "1") == "1"
rows = json.load(open("data/vcp_signals_latest.json", encoding="utf-8"))["signals"]
synthetic = next(r for r in rows if r["ticker"] == "011500") | {"name": "합성-한농화성", "foreign_5d": -50_000_000, "inst_5d": -1_000_000}
analyzer = object.__new__(VCPMultiAIAnalyzer)
analyzer.zai_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
    create=lambda **_k: SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="서술형 답변이라 JSON 이 아닙니다."))]))))
analyzer._build_vcp_prompt = lambda *_a, **_k: "prompt"

def _flow(row, a, b):
    try: return float(row[a]) + float(row[b])
    except (TypeError, ValueError, KeyError): return None
async def _to_thread(func, *a, **k): return func(*a, **k)
async def _no_sleep(_s): return None

counts = {"BUY": 0, "HOLD": 0, "SELL": 0}
with mock.patch("engine.vcp_ai_analyzer.asyncio.to_thread", _to_thread), mock.patch("engine.vcp_ai_analyzer.asyncio.sleep", _no_sleep):
    for row in [*rows, synthetic]:
        result = asyncio.run(analyzer._analyze_with_zai(row["name"], row))
        flow_5d, flow_1d = _flow(row, "foreign_5d", "inst_5d"), _flow(row, "foreign_1d", "inst_1d")
        expect = "SELL" if flow_5d is not None and flow_1d is not None and flow_5d < 0 and flow_1d < 0 else "HOLD"
        if ASSERT:
            assert result["action"] == expect, (row["ticker"], result)
            assert result["confidence"] == 55, (row["ticker"], result)
        counts[result["action"]] += 1
        print(f'{row["ticker"]} {row["name"]} score={row["score"]} ratio={row["contraction_ratio"]} flow5={flow_5d} flow1={flow_1d} -> {result["action"]} ({result["confidence"]}) {result["reason"][:80]}')
print("rows", len(rows) + 1, "counts", counts, "assert", ASSERT)
```

- [ ] **Step 2: 고치기 전 기준선을 남긴다** (이미 실행함: 사본이 `HEAD` 의 helper 를 그대로 가진 상태에서 `ASSERT=0` 으로 돌려 `rows 20 … counts {'BUY': 0, 'HOLD': 0, 'SELL': 20}`. QA 문서 baseline 에 기록.)

- [ ] **Step 3: 새 helper 를 사본에 복사한 뒤 `ASSERT=1 python vcp033_qa.py` 를 돌린다**

Expected: 21행 전부 단언 통과, `counts {'BUY': 0, 'HOLD': 20, 'SELL': 1}`, 합성 행만 SELL 이고 그 사유가 「… 5일 수급은 순매도 우위입니다. 1일 수급은 순매도 우위입니다. 5일·1일 수급이 모두 순매도라 SELL 로 판단합니다.」, 수축비 ≤ 0.5 인 행(대림제지 0.39 등)은 「강한 편」, 나머지는 「유지되는 구간」.

- [ ] **Step 4: `docs/dev-cycle/qa/VCP-033.md` 에 S-1(회귀: 실제 20행 HOLD·BUY 0, 필수)·S-2(회귀: 합성 순매도 행 SELL, 필수)·S-3(인접: 결측 갈래 pytest)·S-4(인접: 폴백 호출부 pytest)를 기록한다.**
