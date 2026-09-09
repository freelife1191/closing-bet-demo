## Summary

최신 review-input의 5개 SHA-256이 일치합니다. 마지막 QA delta는 `page.tsx`의 두 차트 닫기 버튼에서 외부 Font Awesome 아이콘 의존성을 제거한 접근성/클릭 영역 보완입니다. 기존 `CLEAR` 판정을 유지하며, 기능 인터페이스와 요청 세대·오류 복구 경계에는 의미 있는 변화가 없습니다.

## Analysis

- `frontend/src/app/dashboard/kr/vcp/page.tsx:1672-1674` — 모바일 닫기 버튼은 기존 `onClick={closeChart}`와 `aria-label="차트 닫기"`를 유지하면서 `p-2` 클릭 영역과 `aria-hidden="true"` 텍스트 `×`를 갖습니다.
- `frontend/src/app/dashboard/kr/vcp/page.tsx:1781-1783` — 데스크톱 닫기 버튼에도 동일한 계약을 적용했습니다. `lg:hidden`/`hidden lg:block` 표시 경계와 닫기 핸들러는 그대로입니다.
- QA 증거 `docs/dev-cycle/evidence/vcp-chart-2026-09-09/qa-cycle-1-failure.json`은 외부 Font Awesome stylesheet 차단 시 기존 `<i>` 전용 버튼이 0x0이었던 원인을 기록합니다. 이번 수정은 아이콘 폰트가 없어도 버튼의 레이아웃 크기와 pointer target을 보장합니다.
- 변경은 `page.tsx` 단일 파일의 presentation/interaction surface에 한정되며, 차트 요청 세대, 오류/재시도 상태, 기간·과거 날짜 전달, gap 계산, StockChart/SMA 데이터 흐름은 변경하지 않습니다.

## Root Cause

닫기 동작 자체는 `closeChart`에 연결되어 있었지만, 시각 아이콘만 가진 버튼은 외부 폰트가 차단된 환경에서 크기가 0이 되어 포인터 사용자가 실제 target을 클릭할 수 없었습니다. 텍스트 기호와 padding을 버튼 내부에 두어 외부 스타일 리소스와 hit-area를 분리했습니다.

## Recommendations

1. `CLEAR` — QA가 보고한 UI 경계만 보완했으며 `onClick`과 accessible label을 보존했습니다. 보고된 기능 위험에 대한 구조적 해결입니다.
2. `WATCH` — QA 증거의 outcome이 cycle2 회귀 재검증 필요로 표시되어 있으나, 제공된 최신 상태에 `qa-close-target52`, typecheck 0, lint 0 및 code-review-v3 APPROVE가 기록되어 있습니다. 이는 이 delta의 정적/통제 검증 근거이며 실제 브라우저 재검증 결과로 확대하지 않습니다.
3. `CLEAR` — 기존 전체 판정은 유지합니다. 종목 전환 기간 유지, 날짜 정렬/SMA 유한값은 기존 계약/범위 한계로 이전 리뷰에 기록된 상태이며 이번 presentation delta와 무관합니다.

## Architectural Status

`CLEAR`

## References

- 최신 SHA 검증 대상 5개 파일 모두 최신 `review-input.json`과 일치.
- 변경 위치: `frontend/src/app/dashboard/kr/vcp/page.tsx:1672-1674,1781-1783`.
- QA 원인: `docs/dev-cycle/evidence/vcp-chart-2026-09-09/qa-cycle-1-failure.json`.
- 판정: 기존 `architecture-review-v2.md`의 `CLEAR`를 보존하며, 이번 delta는 의미 있는 인터페이스 변화가 없는 UI hit-area 보정입니다.
- 검토는 read-only로 수행했고 테스트/HTTP/API/실제 env/data 접근은 하지 않았습니다.
