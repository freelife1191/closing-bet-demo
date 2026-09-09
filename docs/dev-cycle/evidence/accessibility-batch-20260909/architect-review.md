## Summary

FE-034/FE-040 범위는 요구사항과 현재 구현이 일치하며 Architect 판정은 `CLEAR`입니다. 제목 계층과 breadcrumb 의미 구조는 시각 표현을 유지하면서 semantic heading/nav 구조를 보강했고, 빈 표 상태는 `overflow-x-auto` 바깥 카드 영역으로 이동해 모바일 폭에서 잘리지 않도록 했습니다.

## Analysis

- `frontend/src/app/components/Header.tsx:19-47`
  - breadcrumb를 `nav[aria-label="현재 위치"]` → `ol` → `li` 구조로 바꿨습니다.
  - 홈 링크에 `aria-label="홈"`을 부여하고 홈 아이콘은 `aria-hidden="true"`입니다.
  - 경로가 있으면 마지막 항목 하나만 `aria-current="page"`이고, 루트에서는 홈 항목이 current입니다.
  - 구분자 `/`는 `aria-hidden="true"`로 접근성 트리에서 제거됩니다.
  - 기존 경로 순서·label map·시각 배치는 유지됩니다.
- `frontend/src/app/components/Header.regression-fe-034.test.tsx`
  - 루트와 세 단계 breadcrumb 경로를 모두 검사합니다.
  - nav 이름, `OL`, list item 개수, 홈 링크 href, 항목 순서, 단일 `aria-current`, 구분자 숨김을 고정합니다.
- `frontend/src/app/dashboard/kr/closing-bet/page.tsx:1222-1538`
  - 페이지 제목을 `h1`로 올리고 Trading Tips를 `h2`, 하위 전략을 `h3`, 패턴/조건을 `h4`로 조정했습니다.
  - No Signals 상태는 페이지의 별도 `h2`로 유지됩니다.
  - 기존 독립 차트/상세 모달 제목은 범위 밖에서 보존됩니다.
- `frontend/src/app/dashboard/kr/closing-bet/page.tsx:2025-2310`
  - SignalCard의 종목명을 `h2`로 만들고 AI 분석을 `h3`, 시스템 계산/체크리스트를 `h4`로 조정했습니다.
  - 페이지 h1 아래 카드 h2, 카드 내부 세부 h3/h4라는 연속 계층이 형성됩니다.
  - tooltip·버튼·거래 조작 로직은 변경하지 않았습니다.
- `frontend/src/app/components/PaperTradingModal.tsx:510-606`
  - 보유 종목과 거래 내역의 빈 상태 `tr/td`를 제거하고, 가로 스크롤 wrapper 바깥에 카드 폭 기준 `div`로 배치했습니다.
  - 데이터 행과 거래 동작은 그대로 유지됩니다.
- `frontend/src/app/components/StockTradeHistoryModal.tsx:346-362`
  - 종목별 거래 내역 빈 상태를 table 내부에서 scroll wrapper 바깥으로 이동했습니다.
- `frontend/src/app/dashboard/kr/cumulative/CumulativeClientPage.tsx:885-901`
  - 누적성과 거래 내역 빈 상태도 동일하게 표의 overflow 영역 밖으로 이동했습니다.
- `frontend/src/app/components/emptyState.regression-fe-040.test.tsx`
  - 누적성과, 모의투자 보유/전체 거래, 개별 종목 거래의 빈 안내가 `.overflow-x-auto` 조상 밖에 있는지 검증합니다.
  - 테스트는 각 API를 빈 fixture로 고정해 외부 데이터나 실제 거래 동작을 사용하지 않습니다.
- `frontend/src/app/dashboard/kr/closing-bet/page.regression-fe-024.test.tsx`
  - 기존 비용 발생 조작 회귀 테스트에 제목 계층 검사를 추가했습니다.
  - 페이지 h1 하나, 종목 h2, 펼친 전략의 h2/h3/h4를 실제 렌더 트리에서 검증합니다.
- 제공된 검증 evidence
  - FE-034 회귀 13건 통과
  - FE-040 회귀 3건 및 인접 24건 통과
  - 전체 Vitest: 446 passed, 64 files
  - type-check 통과
  - lint: 0 errors, 199 warnings
  - 범위는 300줄 미만의 bounded T2이며 위험 경로/새 의존성/타입 억제가 없습니다.

## Root Cause

FE-034의 원인은 breadcrumb와 제목이 시각적 `<div>/<span>` 중심으로 구성되어 보조기술이 위치·계층을 안정적으로 해석하기 어려웠던 점입니다.
FE-040의 원인은 빈 상태 메시지를 `min-width`가 있는 table 내부에 `td[colSpan]`로 넣어 모바일 viewport에서 table의 가로 overflow를 함께 따르게 한 점입니다. 현재 변경은 빈 상태를 table 데이터 구조와 분리해 카드 폭 기준으로 렌더링합니다.

## Strongest Counterargument

빈 상태를 table 밖으로 옮기면 의미상 table의 “행이 없음”과 안내가 DOM에서 분리된다는 반론은 가능합니다. 그러나 빈 결과는 데이터 행이 아니라 사용자 안내이고, 현재 구현은 표 자체를 빈 `tbody`로 유지하면서 안내를 같은 카드·같은 섹션에 두므로 데이터 semantics와 responsive layout을 함께 보존합니다.
제목 계층을 일괄적으로 한 단계씩 낮추면 일부 하위 제목이 실제 시각적 중요도와 달라질 수 있다는 반론도 있으나, regression test가 페이지 h1 → 카드/전략 h2 → 하위 h3 → 패턴 h4를 직접 고정하고 있어 승인된 요구와 일치합니다.

## Recommendations

1. `CLEAR`: 현재 FE-034/040 범위는 통합 가능합니다.
2. table empty-state를 공통 컴포넌트로 추상화하지 않은 선택은 이번 범위의 “새 공용 추상화 없음”과 일치합니다.
3. lint warning 199건은 오류가 아니며 이번 변경의 blocker로 판단할 근거가 없습니다.

## Architectural Status

`CLEAR`

## 전달 기록

독립 notification_round_map에 설치 architect prompt를 적용했다. 전용 역할 호출 성공으로 주장하지 않는다. 부모가 회신 본문을 보존했으며 반복된 절대경로 접두사는 저장소 상대경로로 표기했다. 회신한8개 File Hashes는 review-input.json과 모두 동일하다.

## File Hashes

```json
{
  "frontend/src/app/components/Header.tsx": "e4e94645db19cb1589cb414652e1a0a9e5768147e0c27e7852fe6b71762417a8",
  "frontend/src/app/components/PaperTradingModal.tsx": "a5b15b5b9147aab7134ea0cb0142e06f656dfac678c8b7a2d4b6024d62ffaa97",
  "frontend/src/app/components/StockTradeHistoryModal.tsx": "0b0c434c4b88d9ae27c0292b69a0b2d8c44f1e6f7d4345d20abd107776c0bb8d",
  "frontend/src/app/dashboard/kr/closing-bet/page.regression-fe-024.test.tsx": "1487bd472b2872ab623e46b84462ff2d7f832a6b734f36e6774cb7811500ef1b",
  "frontend/src/app/dashboard/kr/closing-bet/page.tsx": "3b4366be604195c06a19e9097159d39755bfaf59ee5db768007266395a951d8a",
  "frontend/src/app/dashboard/kr/cumulative/CumulativeClientPage.tsx": "a9d162b4a9b939ba0f14c25f43439fd4c32ecbdcdf61d426795dd006eef8cc44",
  "frontend/src/app/components/Header.regression-fe-034.test.tsx": "6a0b0155c252246ab40dcfe8ff0b587bbd305d9842f52b13ee3a5cd1e70ace93",
  "frontend/src/app/components/emptyState.regression-fe-040.test.tsx": "d23da83bdef7adcf3ccd423ec524b3c0aa12ea4ceac4581ceabb1a68adf4b91b"
}
```
