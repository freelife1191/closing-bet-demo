# QA CSS Delta Architecture Review

## Summary

`CLEAR`. 기준 `252568c` 이후 제품 변경은 종가베팅 카드의 가격 기준/체크리스트 grid를 모바일에서 1열, `sm` 이상에서 기존 2열로 바꾼 한 줄뿐이다(`frontend/src/app/dashboard/kr/closing-bet/page.tsx:2216`). 375px에서 두 영역이 같은 행을 공유해 날짜와 badge가 겹치던 원인을 직접 제거하며, 데이터·가격 계산·이벤트·데스크톱 구조에는 변화가 없다.

## Analysis

- 실패 증거는 날짜 영역 `(x=115.921875..204.734375, y=440.9375..452.9375)`와 체크리스트 badge `(x=195.5..269.5, y=421.9375..445.9375)`가 46.171875px² 겹쳤음을 보여 준다(`evidence/cycle1-mobile-source-geometry.json`). 두 요소는 동일한 항상-2열 grid의 첫째·둘째 자식이었다(`252568c:frontend/src/app/dashboard/kr/closing-bet/page.tsx:2216`, `:2217`-`:2269`).
- 현재 `grid-cols-1 sm:grid-cols-2`는 기본 viewport에서 두 자식을 서로 다른 행에 배치한다(`frontend/src/app/dashboard/kr/closing-bet/page.tsx:2216`). 날짜는 가격 목록 안에 그대로 있고(`frontend/src/app/dashboard/kr/closing-bet/page.tsx:2239`-`2243`), checklist badge는 둘째 grid item 안에 그대로 있으므로(`frontend/src/app/dashboard/kr/closing-bet/page.tsx:2267`-`2276`) 375px에서 두 사각형이 같은 행의 수평 공간을 경쟁하지 않는다.
- `sm:grid-cols-2`가 기존 2열 배치를 복원하므로 태블릿·데스크톱의 정보 밀도는 유지된다(`frontend/src/app/dashboard/kr/closing-bet/page.tsx:2216`). 저장소가 같은 반응형 패턴을 다른 카드/모달에도 사용한다(`frontend/src/app/dashboard/kr/closing-bet/page.tsx:1518`, `frontend/src/app/dashboard/kr/cumulative/CumulativeClientPage.tsx:466`).
- 변경은 class 문자열 하나뿐이다. `basePrice`, 목표·손절 비율, AI 원문, checklist 상태를 읽는 표현식이나 컴포넌트 경계는 건드리지 않았다(`frontend/src/app/dashboard/kr/closing-bet/page.tsx:2206`-`2276`). 따라서 API interface, 캐시, pandas shape, entry/target/stop 정밀도와 무관하다.
- ponytail 검토는 추가 추상화 없이 기존 Tailwind 반응형 유틸리티 한 줄로 해결했다고 판정했다(`evidence/ponytail-qa.md`). 전체 Vitest/build TypeScript 증거도 그대로 통과했다(`evidence/qa-layout-vitest.log`: 59 files, 424 tests).

## Root Cause

모바일에서도 가격 기준과 체크리스트를 강제로 2열에 놓아, 첫 열의 `whitespace-nowrap` 날짜가 좁은 열을 넘어 둘째 열 badge 영역과 겹쳤다. 콘텐츠나 데이터의 문제가 아니라 breakpoint 없는 grid 배치가 근본 원인이었다.

## Recommendations

1. 현재 CSS delta를 유지한다 — 낮은 노력, 375px 겹침의 직접 해소와 `sm` 이상 기존 배치 보존.
2. 진행 중인 격리 QA에서 375px post-fix geometry의 overlap=0과 1280px 2열 복귀를 증거로 남긴다 — 낮은 노력, 시각적 stop condition 확정.

## Architectural Status

`CLEAR`

이 판정은 QA CSS delta에 한정한다. 이전 최종 검토의 생산 계약 밖 DataFrame 직접 호출 `WATCH`는 별도이며 이번 변경으로 넓어지거나 악화되지 않았다.

## Trade-offs

| Option | Pros | Cons |
|---|---|---|
| 모바일 1열, `sm` 이상 2열 | 겹침 원인을 제거하고 넓은 화면 밀도를 보존 | 모바일 카드 높이가 체크리스트 높이만큼 증가 |
| 날짜만 줄바꿈/축약 | 카드 높이 증가가 작음 | 긴 날짜·지역화 문구에서 같은 폭 문제가 재발할 수 있고 정보 표현을 바꿈 |
| 항상 1열 | 가장 단순하고 모든 폭에서 안전 | 데스크톱의 활용 가능한 가로 공간과 기존 레이아웃을 불필요하게 잃음 |

## Strongest Counterargument

모바일에서 1열로 바꾸면 카드가 길어져 스크롤 비용이 늘어난다. 그러나 둘째 영역은 체크리스트 두 badge뿐이고, 날짜와 badge가 실제로 겹쳐 정보가 가려지는 문제보다 높이 증가의 비용이 작다. `sm` 이상에서는 즉시 기존 2열로 돌아가므로 영향 범위도 좁다.

## Validation

- 기준 이후 제품 diff: `frontend/src/app/dashboard/kr/closing-bet/page.tsx`의 `grid-cols-2` → `grid-cols-1 sm:grid-cols-2` 한 줄.
- 실패 기하: `evidence/qa-cycle1-failure.json`, `evidence/cycle1-mobile-source-geometry.json` — overlap 46.171875px².
- 정적/렌더 회귀: `evidence/qa-layout-vitest.log` — 59 files, 424 tests passed, 실제 build TypeScript 통과.
- 이 레인은 요청대로 테스트와 서버를 재실행하지 않았고, 소유 중인 QA 서버·원본 3500/5501/live에 요청하지 않았다.
