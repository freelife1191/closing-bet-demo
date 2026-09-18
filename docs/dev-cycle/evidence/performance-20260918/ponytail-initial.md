# ponytail 원문

`frontend/src/app/dashboard/kr/cumulative/CumulativeClientPage.regression-performance-batch.test.tsx:L45-60: yagni: CumulativeKpiFixture 16줄은 단일 fixture의 recentWinRate를 null로 한 번 덮어쓰기 위한 인터페이스다. KPI에서 30 as number | null로 타입만 넓히고 responseFor는 기본값 타입을 추론하게 한다.`

`net: -16 lines possible.`

프로덕션 코드는 이미 간결합니다. 나머지 테스트 보정도 필요한 회귀 계약을 직접 고정합니다.

## 부모 미반영 판단
AGENTS의 TypeScript 규약은 모든 데이터 구조에 인터페이스를 정의하도록 명시한다. nullable recentWinRate를 포함한 fixture 계약을 명시한 interface는 실행 레이어나 확장 골격이 아니다. 타입 단언으로 축약하는 대신 이 인터페이스를 유지한다. 소스 변경 없으며 reviewer에게 규범 맥락을 보내 확인했다.
