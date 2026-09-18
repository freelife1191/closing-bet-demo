Pre-Landing Review: No issues found.

- 이전 HIGH: warm SQLite → 메모리 초기화 → 실제 종가 집계 경로가 통과하며, 허용 범위는 naive·자정·NaT 없는 datetime64로 제한됐습니다.
- 이전 MEDIUM: 기준표 승률과 평균 수익률 문구가 생산 계산식과 일치하고 실제 모달 회귀가 추가됐습니다.
- 14개 SHA 모두 manifest와 일치합니다.
- 증거: pytest 2314/3 skip, Vitest 506/71, lint 0 errors, build 3/3, typecheck exit 0.

**Recommendation: APPROVE**

필수 동적 QA는 별도 후속 gate입니다.
