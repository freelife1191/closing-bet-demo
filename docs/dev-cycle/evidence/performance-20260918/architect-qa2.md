## Summary

`CLEAR`입니다. 수정은 두 Tooltip 호출부의 기준점만 조정하며 공통 Tooltip, 성과 계산, 상태 정책에는 영향이 없습니다.

## Analysis

- 누적성과 툴팁은 아이콘 기준 `left` 정렬에서 `center` 정렬로 바뀌어 320px 폭이 모바일 우측으로만 뻗던 원인을 직접 제거합니다. `frontend/src/app/dashboard/kr/cumulative/CumulativeClientPage.tsx:703-708`
- 홈의 두 전략 툴팁은 전략명과 아이콘을 하나의 anchor로 묶어 `left-0` 기준을 카드 시작 쪽으로 이동합니다. 카드 상태·수치·기준표 버튼 구조는 유지됩니다. `frontend/src/app/dashboard/kr/page.tsx:1003-1014`, `frontend/src/app/dashboard/kr/page.tsx:1055-1066`
- `Tooltip`의 기존 `align` 계약만 사용하며 공통 위치 계산이나 최대 폭을 변경하지 않았습니다. `frontend/src/app/components/Tooltip.tsx:36-60`
- before-QA2 대비 변경 SHA는 해당 두 화면 파일뿐이며 현재 manifest와 일치합니다. `docs/dev-cycle/evidence/performance-20260918/review-input-before-qa2.json:7-20`, `docs/dev-cycle/evidence/performance-20260918/review-input.json:7-20`
- Vitest 506/71, lint 0 errors/190 warnings, build 3/3, typecheck exit 0입니다. `docs/dev-cycle/evidence/performance-20260918/vitest-qa2.log:1757-1758`, `docs/dev-cycle/evidence/performance-20260918/lint-qa2.log:343`, `docs/dev-cycle/evidence/performance-20260918/build-qa2.log:48-49`, `docs/dev-cycle/evidence/performance-20260918/typecheck-qa2.json:6-15`

## Architectural Status

`CLEAR`

viewport 자동 edge 보정까지 공통 컴포넌트를 확장하지 않은 선택도 범위상 타당합니다. 최종 모바일 실측에서 가로 경계와 세로 스크롤 접근성만 확인하면 됩니다.
