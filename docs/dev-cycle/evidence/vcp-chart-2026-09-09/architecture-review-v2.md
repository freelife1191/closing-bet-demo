## Summary

새 review-input의 5개 SHA-256이 모두 일치합니다. 이번 delta는 `page.tsx`와 `page.regression-vcp-010.test.tsx`의 차트 오류 상태 복구와 회귀 검증 보완이며, 아키텍처 상태는 `CLEAR`입니다. 현재 요청에만 오류를 귀속하고 재시도 시 오류 상태를 초기화하는 경계가 기존 요청 세대 토큰과 일관됩니다.

## Analysis

- `frontend/src/app/dashboard/kr/vcp/page.tsx:921-945` — 새 요청 시작 시 `setChartError(false)`로 이전 오류를 지우고, `catch`에서는 `requestId === chartRequest.current`일 때만 오류를 설정합니다. `finally`도 같은 세대 조건으로 loading을 해제하므로 늦은 A 실패가 진행 중인 B의 로딩/오류 상태를 오염시키지 않습니다.
- `frontend/src/app/dashboard/kr/vcp/page.tsx:1693-1720` — 상태 우선순위가 loading → current error/retry → data → empty로 분리되어 네트워크 실패와 정상 빈 응답을 구분합니다. 재시도 버튼은 현재 `chartPeriod`와 현재 날짜 컨텍스트를 다시 `openChart`에 전달하므로 기존 기간/과거 날짜 계약을 유지합니다.
- `frontend/src/app/dashboard/kr/vcp/page.regression-vcp-010.test.tsx:184-207` — 현재 요청 실패가 빈 자료와 구분되고 재시도 성공 후 alert가 사라지는지, B 완료 후 A 실패가 B 화면을 보존하는지, 긴 날짜 간격 안내가 짧은 응답으로 전환할 때 제거되는지를 페이지 렌더링 결과로 검증합니다.
- 기존 요청 경합 보호는 `frontend/src/app/dashboard/kr/vcp/page.tsx:921-943`의 request generation과 결합되어 있습니다. 오류 상태가 별도 boolean으로 추가되었지만 세대 판정은 단일 ref를 계속 사용하므로 상태 소유권이 분리되지 않았습니다.

## Root Cause

이전 구현은 실패를 빈 자료와 동일하게 표시했고, `finally`가 늦은 요청의 loading을 해제할 수 있었습니다. 이번 보완은 오류 상태를 현재 요청 세대에만 귀속하고, 렌더링 분기를 명시해 복구 가능한 오류와 정상 공백을 분리했습니다.

## Recommendations

1. `CLEAR` — 승인된 오류 복구 범위에서 현재 구현은 충분합니다. 기존 테스트 결과(RED 1 fail → GREEN 52 pass, typecheck 0)와 새 회귀 세 가지가 설계 경계를 뒷받침합니다.
2. `WATCH` — `chartPeriod` 종목 전환 유지, 날짜 배열 정렬, SMA 유한값 전제는 이전 리뷰에서 기록한 기존 계약/범위 한계이며 이번 오류 복구 delta의 차단 사유가 아닙니다.
3. `WATCH` — 이번 UI QA는 통제 입력 기반이므로 백엔드 데이터 정합성 PASS로 확대 해석하지 않아야 합니다.

## Architectural Status

`CLEAR`

## References

- 새 SHA 검증 대상: `chartUtils.test.ts`, `StockChart.tsx`, `page.regression-vcp-010.test.tsx`, `chartUtils.ts`, `page.tsx` 모두 `review-input.json`과 일치.
- 변경 delta: `page.tsx`의 `chartError`/retry/current-generation 처리 및 `page.regression-vcp-010.test.tsx`의 세 회귀 검증.
- 기존 WATCH: 종목 간 `chartPeriod` 유지, 날짜 정렬/SMA 유한값은 기존 전제이며 범위 밖.
- 검토는 read-only로 수행했고, 테스트 실행·HTTP/API·실제 환경변수·data 접근은 하지 않았습니다.
