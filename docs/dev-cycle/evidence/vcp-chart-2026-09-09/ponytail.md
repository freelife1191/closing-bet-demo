[대체 실행 고지] 새 ponytail reviewer 역할 생성이 스레드 한도로 실패해 기존 native agent에 범위를 전달한 대체 실행입니다. `docs/dev-cycle/evidence/vcp-chart-2026-09-09/review-input.json`의 5개 SHA는 현재 입력과 전부 일치했습니다.

frontend/src/app/dashboard/kr/vcp/page.regression-vcp-010.test.tsx:L125: shrink: `dismissDetail`이 제목에서 `parentElement`를 네 번 따라가 오버레이를 찾는 6줄 DOM 구조 의존 코드를 둡니다. 이번 변경이 두 닫기 버튼에 `aria-label="차트 닫기"`를 추가했으므로 `fireEvent.click(screen.getAllByRole('button', { name: '차트 닫기' })[0])`를 쓰는 3줄 helper로 대체하면 테스트 의도는 유지되고 구조 결합이 줄어듭니다.

나머지 변경은 요청 세대 counter, 기간 선택, 날짜 간격 계산, 모바일 flex 배치에 필요한 최소 상태·분기이며 별도 추상화나 선행 scaffolding이 없습니다. Lean otherwise.
net:-3 lines possible

읽기 전용 검토만 수행했고 코드·문서·런타임·테스트를 수정하거나 실행하지 않았습니다.
