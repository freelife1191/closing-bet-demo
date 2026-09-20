## 코드 리뷰 요약

**검토 파일:** 35개(소스 13, 테스트 22)
**총 이슈:** 2

### 심각도
- CRITICAL: 0
- HIGH: 1
- MEDIUM: 1
- LOW: 0

### 이슈

[HIGH] FE-017의 모달 닫기 버튼 이름 요구가 완료되지 않았습니다.
파일: `frontend/src/app/components/BuyStockModal.tsx:206`, `SellStockModal.tsx:129`, `PaperTradingModal.tsx:254`, `PaperTradingModal.tsx:274`
문제: 아이콘 전용 닫기 버튼에 `aria-label`이 없습니다. FE-017과 U8은 모달 닫기 버튼의 정확한 이름을 필수로 요구합니다. 페이지 회귀 테스트가 해당 모달을 mock하므로 현재 검증에서 누락됩니다.
수정: 각 버튼에 구체적인 `aria-label`을 추가하고, 실제 매수·매도·모의투자 모달을 렌더해 이름을 검증하십시오.

[MEDIUM] 느린 포인터로 툴팁 팝업에 이동하면 중간에 닫힐 수 있습니다.
파일: `frontend/src/app/components/Tooltip.tsx:28`, `Tooltip.tsx:29`, `Tooltip.tsx:101`, `Tooltip.tsx:178`, `frontend/src/app/components/Tooltip.test.tsx:185`
문제: 트리거와 팝업 사이에 8px 간격이 있지만 닫기 유예는 40ms입니다. 이동 시간이 40ms를 넘으면 팝업 진입 전에 언마운트되어 “팝업으로 이동해도 유지” 요구를 충족하지 못합니다. 현재 테스트는 leave와 enter를 같은 tick에 실행해 이 경계를 확인하지 않습니다.
수정: 충분한 유예 시간이나 hover bridge를 적용하고, 실제 유예 시간이 지난 이동을 회귀 테스트로 고정하십시오.

모달 스택·최상단 Escape·SSR 포털·마스킹 payload 보존은 정적 대조상 계약과 일치했습니다. 우회 경로로 실패를 숨기는 코드나 신규 보안 문제는 확인되지 않았습니다.

최신 증거는 Vitest 538/538, build 3/3, typecheck 성공, lint 0 errors입니다. 직접 검사는 작업 지시상 재실행하지 않았습니다.

### 권고
**REQUEST CHANGES**
