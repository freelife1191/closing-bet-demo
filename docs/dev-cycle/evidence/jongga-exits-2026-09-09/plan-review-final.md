**OKAY**

> 역할 전용 호출은 스레드 한도로 사용할 수 없어, 기존 native agent가
> `/Users/freelife/.codex/prompts/critic.md`를 직접 읽고 critic 역할 지침을 적용한 대체 검토다.
> 전용 critic 호출 성공으로 기록하지 않는다.

**Justification:** 계획은 JONGGA-012·013의 승인 범위를 실제 생성, 정규화, 요약,
누적성과, 캐시, 화면 경로에 연결하며 구현자가 정책을 추측하지 않아도 되는 함수 계약과
검증 경계를 갖췄다. 초기 검토에서 확인한 명시 가격의 pct 왕복, 반올림 수익률로 outcome을
재추론하는 문제, `buy_price`/`entry_price` 우선순위, 생산형 날짜 컬럼 입력, VCP 영향 범위,
실제 누적 화면 파일 누락이 모두 계획에 반영됐다.

## Summary

- Clarity: 통과. 기본 +5/-3, 저장된 유효 가격 우선, `entry_price` 정본과 `buy_price`
  fallback, 같은 일봉 손절 우선, AI 원문 보존이 명시돼 있다.
- Verifiability: 통과. 정확 target/stop 경계와 바깥 1원, float 꼬리, 반올림상 5.0%인
  미도달 OPEN, custom +8/-4, 동시 hit, 무자료 OPEN/0, 캐시 구버전 미적중을 각각 검사한다.
- Completeness: 통과. 생성·예외 폴백·정규화·요약·누적성과·두 캐시·카드·기준표·홈·누적
  화면과 정확한 테스트 파일, 전체 검증, agent-browser QA, 아카이브까지 포함한다.
- Big Picture: 통과. 종가베팅 계산을 한 가격 계약으로 모으면서 저장 자료와 AI 원문을
  수정하지 않고, VCP·실거래·알림·등급·진입 판단을 범위 밖으로 유지한다.
- Principle/Option Consistency (consensus): 해당 없음. 승인된 bounded 구현 계획이며
  consensus/ADR 계획이 아니다.
- Alternatives Depth (consensus): 해당 없음. 새 결과 계층 대신 기존
  `calculate_cumulative_trade_metrics`의 구조화 결과를 재사용하는 최소안이 확정됐다.
- Risk/Verification Rigor: 통과. T3 독립 리뷰 순서, 전체 pytest/Vitest/type-check/lint/build,
  격리 합성 데이터 브라우저 QA, 시간·반복 상한과 미완료 판정이 명시돼 있다.
- Deliberate Additions: 통과. 캐시 버전 증가와 정밀도 경계 검사는 계산 규칙 변경에 직접
  필요하며, 새 의존성·데이터 보충·LLM 호출은 없다.

## Representative Task Simulation

1. 생성·보정: `SignalConfig`의 +5/-3을 공용 상수로 옮기고 `PositionSizer` 정상·예외가
   같은 config 비율을 사용한다. 정규화는 `resolve_jongga_exit_prices`로 유효한 명시 가격을
   보존하고 누락·NaN·Infinity·0·반대 방향 값만 기본값으로 보충한다.
2. 요약·누적: 명시 target/stop을 keyword-only 원 가격으로 직접 전달하므로 pct로 바꿨다가
   재구성하는 원 단위 오차가 없다. 요약은 반환된 `outcome`을 직접 세어 반올림된 ROI를
   WIN/LOSS로 재해석하지 않는다. `date` 컬럼/RangeIndex 입력은 기존 prepare 함수로
   DatetimeIndex화하고 기존 DatetimeIndex와 원본 불변도 검사한다. `price_map`은 후보 표시만
   갱신하며 일봉 집계를 막지 않는다.
3. 화면·캐시: 카드 기준가는 유효한 `entry_price`를 우선하고 없을 때만 `buy_price`를 쓴다.
   `CumulativeClientPage.tsx`를 포함한 실제 +9/-5 문구 위치를 +5/-3으로 고치되, VCP 전용
   화면 +5/-3과 VCP 백테스트 +15/-5는 불변 검사로 보호한다. 홈 VCP +9/-5의 기존 불일치는
   별도 TODO로 남기고 이번에는 종가 분기만 바꾼다. summary 1→2, cumulative 4→5로 정책
   변경 전 캐시를 차단한다.

## Non-blocking Notes

- 전체 검증 명령은 저장소 `AGENTS.md`/`CLAUDE.md`의 정본 명령을 그대로 사용해야 한다.
- 홈 VCP +9/-5 안내 불일치의 별도 TODO 등록과 근거를 아카이브에 연결해야 한다.
- 필수 리뷰·전체 검증·격리 QA 중 하나라도 실패·차단·미실행이면 완료 아카이브를 만들지 않는
  것이 이 판정의 stop condition이다.

**Verdict:** OKAY — 구현을 시작할 수 있다.
