REJECT

Justification: 범위와 안전 경계는 타당하지만, 실행자가 추측해야 하는 핵심 계약이 남았습니다. 중단 조건은 아래 네 항목을 계획에 반영하고 재검토에서 OKAY를 받는 것입니다.

Summary:
- Clarity: Header와 전역 ChatWidget 간 제어 방식, AI 평가 유효성 규칙이 불명확합니다.
- Verifiability: 7개 ID별 QA 필수 행과 Next MCP 검증 연결이 빠졌습니다.
- Completeness: 필수 Next.js 문서·프론트엔드 스킬과 정확한 QA 경로가 누락됐습니다.
- Big Picture: 7건 묶음, T3 공유 게이트, 격리 실행, ego-browser 우선은 적절합니다.
- Principle/Option Consistency (ralplan): 해당 없음.
- Alternatives Depth (ralplan): 해당 없음.
- Risk/Verification Rigor: 실패 — 항목별 완료 판정과 컴파일·런타임 검증이 충분히 고정되지 않았습니다.
- Deliberate Additions: 해당 없음.

필수 개선 사항:
1. ChatWidget은 root layout.tsx에, Header는 대시보드 layout에 따로 마운트됩니다. 이벤트·context 등 제어 계약을 하나로 고정하고 단일 launcher, aria-expanded 동기화, 닫기와 초점, 대시보드 밖 fallback, /chatbot 숨김을 명시해야 합니다.
2. AI 평가의 유효함을 정확히 정의해야 합니다. 기존 bare-string 호환, 허용 action, 빈 객체, placeholder reason, confidence: 0, 선택한 판정에 사유가 없을 때 score.llm_reason을 쓰는 규칙을 고정하고 실제 테스트 파일도 지정해야 합니다.
3. QA 경로를 docs/dev-cycle/qa/batch-ui-followup-2026-09-20.md와 7개 docs/dev-cycle/qa/<ID>.md로 명시하고 공유 행을 각 ID의 필수 판정에 연결해야 합니다. 일부 실패 시 해당 ID만 TODO에 유지하는 규칙과 격리 URL의 get_compilation_issues·get_errors 확인도 추가해야 합니다.
4. 계획에 필수 사전 자료를 적어야 합니다. 최소 Next 번들 문서 05, 06·07, layout 변경 시 02·03, vercel-react-best-practices, Header–ChatWidget 경계 재설계 시 composition-patterns 판정을 포함해야 합니다.

FE-021을 실제 PaperTradingAssetChart 회귀 파일로 분리하는 부모의 계획 갱신은 적절합니다.
