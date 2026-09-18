## Summary

영향 재검토 결과 `CLEAR`입니다. 초기 WATCH 1~3은 코드와 회귀로 해소됐고, WATCH 4는 고정 높이 위험을 제거했습니다. 동적 S-8 실측은 여전히 필수지만 현재 코드에서 확인되는 아키텍처 차단 요소는 없습니다.

신뢰도: `높음(0.96)`.

## Analysis

- 최종 14개 SHA 중 변경된 것은 누적성과 화면과 해당 회귀 테스트 두 파일뿐이며, 현재 파일 해시가 manifest와 일치합니다. `docs/dev-cycle/evidence/performance-20260918/review-input-initial.json:7-20`, `docs/dev-cycle/evidence/performance-20260918/review-input.json:7-20`
- 최근 통계는 실제 `recentClosedCount`를 라벨에 사용해 1~9건 표본도 정확히 표현합니다. 2건/50% 회귀가 추가됐습니다. `frontend/src/app/dashboard/kr/cumulative/CumulativeClientPage.tsx:615-618`, `frontend/src/app/dashboard/kr/cumulative/CumulativeClientPage.tsx:675-684`, `frontend/src/app/dashboard/kr/cumulative/CumulativeClientPage.regression-performance-batch.test.tsx:216-234`
- 페이지 필터 범위를 `현재 페이지 내`로 명시하고, 필터 클릭 시 불필요하게 1페이지로 이동하던 결합을 제거했습니다. 2페이지에서 D와 LOSS를 연속 선택해도 같은 페이지와 동일 요청 수를 유지하는 회귀가 있습니다. `frontend/src/app/dashboard/kr/cumulative/CumulativeClientPage.tsx:1137-1161`, `frontend/src/app/dashboard/kr/cumulative/CumulativeClientPage.regression-performance-batch.test.tsx:236-271`
- effect cleanup의 `isActive`가 stale 응답의 KPI·pagination·trades 갱신뿐 아니라 오류 로그와 loading 갱신도 차단합니다. StrictMode의 취소된 초기 요청이 페이지 2 데이터와 KPI를 덮지 못하는 회귀가 실제 경합 순서를 고정합니다. `frontend/src/app/dashboard/kr/cumulative/CumulativeClientPage.tsx:943-987`, `frontend/src/app/dashboard/kr/cumulative/CumulativeClientPage.regression-performance-batch.test.tsx:273-318`
- 평균·누적 ROI 카드 두 곳만 `h-auto min-h-24`로 바뀌어 최소 높이를 보존하면서 네 등급 상세가 필요한 만큼 확장됩니다. 범위가 두 카드로 제한돼 다른 KPI 카드 정렬에는 영향을 주지 않습니다. `frontend/src/app/dashboard/kr/cumulative/CumulativeClientPage.tsx:1064-1093`, `frontend/src/app/dashboard/kr/cumulative/CumulativeClientPage.tsx:1097-1119`
- 상태 union 추가를 생략한 판단은 타당합니다. 현재 상태표는 알 수 없는 값을 중립 상태로 처리하는 안전한 런타임 경계를 이미 갖고 있고, 이번 두 파일 영향 수정과 무관합니다. `frontend/src/app/dashboard/kr/page.tsx:73-87`

## Root Cause

초기 WATCH의 공통 원인은 전체 KPI와 페이지 행의 범위를 UI 상태와 요청 생명주기에서 충분히 드러내지 않은 것이었습니다. 이번 수정은 범위 라벨, 필터 동작, 실제 표본 수, stale 응답 차단을 각각 기존 컴포넌트 안에서 직접 보완해 새 계층 없이 원인을 제거했습니다.

## Verification

- Vitest: 71 files, 505 tests 통과. `docs/dev-cycle/evidence/performance-20260918/vitest-final3.log:1754-1755`
- Lint: 0 errors, 기존 190 warnings. `docs/dev-cycle/evidence/performance-20260918/lint-final3.log:343`
- Build: 3/3 통과. `docs/dev-cycle/evidence/performance-20260918/build-review2.log:48-49`
- 프로젝트 `tsc --noEmit`: exit 0. `docs/dev-cycle/evidence/performance-20260918/typecheck-final3.json:6-15`
- 잘못된 LSP 가용성 출력은 성공 근거에서 제외한 판단을 유지합니다. `docs/dev-cycle/evidence/performance-20260918/diagnostics.md:1-5`

## Recommendations

1. 예정된 S-8에서 1280×720·375×812의 ROI 카드 높이와 필터 범위 문구 배치를 실측합니다.
2. 실측 실패가 없으면 추가 구조 변경 없이 현재 구현을 유지합니다.

## Architectural Status

`CLEAR`

동적 S-8은 완료 판정에 필요한 QA 게이트이며, 현재 소스에서 발견된 미해결 아키텍처 결함은 아닙니다.
