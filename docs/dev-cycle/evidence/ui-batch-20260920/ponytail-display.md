Lean already. Ship.

- `formatMarketAmount` 하나로 `formatBigNumber`·`formatFlow`·카드 인라인 포맷을 통합했습니다.
- 빈 자료/필터 0, 전체 테마, 엔진·화면 집계 구분은 기존 파생값만 사용하며 새 상태·추상화를 추가하지 않았습니다.
- 모바일 보완은 기존 컨테이너의 wrap·최소폭 클래스 변경으로 끝났습니다.
- Task 5 제품 코드는 기능 추가 후에도 순감축 2줄입니다.
- 영향 10파일 LSP 진단 0건, `git diff --check` 통과.
- 부모 제공 targeted 검증: 42/42 PASS.

`net: 추가 감축 0 lines.`

현재 `review-input.json` 43개 중 `vcp/page.tsx`, `page.regression-vcp-011.test.tsx` 두 SHA가 검사 중 후속 수정과 달라 최종 동결 시 manifest만 다시 갱신해야 합니다.

부모 후속 확인: 단위문구수정과targetRED/GREEN후manifest재생성,verify_sources.py로43개원본/사본SHA일치확인. 사용자packageSHA보존. 드리프트를그대로승인근거로사용하지않음.
