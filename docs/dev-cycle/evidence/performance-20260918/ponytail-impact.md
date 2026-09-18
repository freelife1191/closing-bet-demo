# 영향 ponytail 원문

`frontend/src/app/dashboard/kr/cumulative/CumulativeClientPage.regression-performance-batch.test.tsx:L166-175: yagni: 한 assertion에서만 쓰는 10줄 recentStatValue helper. nextElementSibling?.textContent를 assertion에서 직접 검사한다.`

`net: -10 lines possible.`

프로덕션 보완은 간결하며 추가 과잉설계가 없습니다.

## 부모 판단
한 번만 쓰는 DOM 조회 helper를 assertion에 직접 옮기는 제안을 채택했다. 최근 값에 범위를 고정하는 assertion과 기대50%는 유지하며 전체 getAllByText로 완화하지 않는다. 이전 명시적 fixture 인터페이스 제거 지적은 저장소 규약 때문에 철회한 상태를 그대로 유지한다.
