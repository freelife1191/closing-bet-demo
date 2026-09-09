## Summary

5개 변경 파일의 SHA-256이 `review-input.json`과 모두 일치했고, diff도 지정된 `VCP-012`, `FE-018`, `VCP-014` 범위에 한정됩니다. 아키텍처 상태는 `WATCH`입니다. 요청 경합 무효화와 모바일 레이아웃 분리는 경계가 명확하지만, 차트 데이터 형식·기간 상태·SMA 계산의 기존 전제가 일부 남아 있습니다.

## Analysis

- `frontend/src/app/dashboard/kr/vcp/page.tsx:920-942` — 각 `openChart` 호출마다 `chartRequest.current`를 증가시키고, 응답/`finally` 모두 현재 요청인지 확인합니다. `closeChart()`도 요청 세대를 증가시키므로 닫힌 모달에 늦은 응답이 재진입하지 않습니다. 새 요청 시작 시 `chartData=[]`, `chartLoading=true`로 이전 종목의 캔들을 먼저 제거합니다. 다만 `krAPI.getStockChart()`가 성공하면서 `res.data`가 `undefined`인 경우에는 데이터가 이미 비워진 상태라 안전하지만, 오류 메시지를 별도 상태에 보존하지 않고 일반 빈 차트로 표시합니다.
- `frontend/src/app/dashboard/kr/vcp/StockChart.tsx:43-146` — SMA series는 차트 생성 시 한 번 만들고, `visibleSMAs` 변경 시 `applyOptions`만 호출합니다. 데이터/VCP 범위 변경 때 차트 전체를 재생성하며, SMA 토글 상태 자체는 유지됩니다. `StockChart.tsx:166-223`의 모바일 변경은 차트 영역과 SMA 컨트롤을 flex column으로 분리하고, AI 패널은 페이지 하단의 고정 높이 영역으로 배치합니다.
- `frontend/src/app/dashboard/kr/vcp/page.tsx:944-949,1668-1680` — 기간 버튼은 `1m`, `3m`, `6m`, `1y`를 직접 API에 전달합니다. `activeDateTab === 'history'`이면 `selectedHistoryDate`를 모든 기간 요청에 함께 전달하므로 과거 날짜가 보존됩니다. `chartPeriod`가 종목 전환 시 초기화되지 않고 페이지 생명주기 동안 유지되는 것은 현재 동작상 일관적이지만, 직전 종목의 기간 선택이 다음 종목에도 적용되는 상태 결합입니다.
- `frontend/src/app/dashboard/kr/vcp/chartUtils.ts:44-64` — `findChartDateGaps`는 거래일 달력을 추론하지 않고 응답에 실제로 나타난 날짜 사이가 7일 초과일 때만 표시합니다. ISO 날짜 형식이 아니거나 round-trip 검증을 통과하지 못하는 값은 제외하고, 입력 배열을 정렬하지 않아 API 응답 순서를 그대로 보존합니다.
- `frontend/src/app/dashboard/kr/vcp/chartUtils.ts:11-41` — `calculateSMA`는 유효하지 않은 `close`를 건너뛰지만 윈도우 크기는 원래 배열 인덱스 기준입니다. 데이터 중간의 NaN/누락 close에서는 유효 관측값 기준 SMA와 달라질 수 있으나 이번 변경에서 새로 생긴 문제는 아닙니다.
- `frontend/src/app/dashboard/kr/vcp/page.regression-vcp-010.test.tsx:133-180` — A/B 성공 경합, A 실패 경합, 빈 B 응답, 4개 기간과 과거 날짜 보존을 페이지 수준에서 직접 검증합니다. 실제 렌더링된 `₩250`, `Loading chart data...`, `No chart data available.`를 확인하므로 stale state 회귀를 포착합니다.

## Root Cause

이번 변경의 근본 문제는 차트 상세 요청이 React state보다 오래 살아남는 비동기 경계였고, 이를 `chartRequest` 세대 토큰으로 해결했습니다. 현재 남은 위험은 기능 실패보다는 데이터 계약의 암묵성입니다. 차트 날짜가 정렬된 ISO 날짜이고 SMA 입력이 유효한 수치라는 전제가 호출부/유틸리티 사이에 명시적으로 공유되지 않습니다.

## Recommendations

1. `WATCH` — 현재 라운드에서는 승인 가능하나, `getStockChart` 응답 계약에 정렬된 `YYYY-MM-DD`와 유한 OHLCV 수치를 명시하거나 유틸리티 경계에서 정규화하는 후속 항목을 권장합니다.
2. `WATCH` — `chartPeriod`를 종목 전환 간 공유하는 것이 의도인지 결정해야 합니다. 의도가 전역 사용자 선택 유지라면 현재 구현이 맞습니다.
3. `WATCH` — 날짜 간격 안내는 의도대로 “관측 간격”만 표시합니다. 휴장일/거래정지/수집 누락 판별에는 백엔드 거래일 달력 또는 데이터 품질 메타데이터가 필요합니다.

## Architectural Status

`WATCH`

## Trade-offs

| Option | Pros | Cons |
|---|---|---|
| 현재 세대 토큰 유지 | 변경 폭이 작고 A/B 및 close 경합을 모두 차단 | 요청 상태가 숫자 ref에 의존 |
| AbortController 도입 | 폐기된 요청 자체를 중단 가능 | API 계층과 테스트가 복잡해지고 서버 요청은 이미 진행됐을 수 있음 |
| 날짜 gap을 프론트에서 정규화 | 표시가 일관됨 | 거래일 의미를 프론트가 잘못 추론할 위험 |
| 현재처럼 관측 간격만 표시 | 오판이 적고 백엔드 변경 불필요 | 사용자에게 원인까지 설명하지 못함 |

## References

- SHA 검증 대상 5개 파일 모두 `review-input.json`의 SHA와 일치.
- diff 범위: base `96a0f72d74c9b24e3f1f2c8a5b5af6533e313b4f` 대비 지정된 5개 파일만 검토.
- 검토는 read-only로 수행했으며 테스트 실행, 서버/API 접근, 파일 변경은 하지 않았습니다.

추가 설명: 기존 `chartPeriod` 선택 유지가 승인 범위의 현행 계약이므로 종목 전환 시 기간 유지에 대한 WATCH는 비차단 근거로 처리합니다. 데이터 정렬/SMA 유한값은 이번 변경 밖의 기존 전제로 인정하며, UI QA는 통제 입력으로 진행되어 백엔드 정합성 PASS를 주장하지 않습니다. 새 architect 역할 생성이 thread limit으로 실패하여, 기존 native agent가 `/Users/freelife/.codex/prompts/architect.md`를 읽고 대체 실행했습니다.
