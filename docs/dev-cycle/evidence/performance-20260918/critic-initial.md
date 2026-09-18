# 계획 검토 최초 판정: REJECT

최초 검토 원문 지적:
1. Task 3에 두 카드 공통 상태 매핑을 확정하십시오. 예: `Accumulating=축적 중`, `OK (New)=신규·판정 전`, `PENDING=집계 전`, `EXCELLENT=우수`, `GOOD=양호`, `BAD=미흡`. 앞의 세 상태에서는 승률·평균값과 적색 성과 테마를 숨기고 중립 테마를 쓴다고 명시해야 합니다. 현재 문구만으로는 라벨과 색상, 0% 표시 여부를 테스트 작성자가 발명해야 합니다.
2. Task 1의 “Public metrics boundary”를 `calculate_cumulative_trade_metrics`로 명시하고 허용 입력을 고정하십시오. 빈 프레임은 기존 OPEN 동작 유지, 비어 있지 않은 date-column 입력은 `ticker`·ISO 날짜·숫자 `high/low/close`, index 입력은 `DatetimeIndex`·숫자 `high/low/close`만 허용하며 나머지는 로그 후 `ValueError`라고 적으면 충분합니다.
3. mock 라우트 선택을 확정하십시오. 현재 등록 순서상 중복 mock은 도달 불가지만 계획의 “align 또는 remove”는 실행 중 설계 결정을 남깁니다. 기존 라우트를 보존하려면 VCP `62.5% → EXCELLENT`, 종가 `58.3% → GOOD`으로 맞추고 작은 라우트 회귀 검사를 필수로 지정하는 것이 최소 변경입니다.

부모 조치: 세 계약을 plan.md '실행 계약 보완'에 명시하고 mock 회귀를 필수로 고정. 아직 소스 구현 전이며 재검토 요청.
