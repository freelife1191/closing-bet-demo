# 완료 전 원본 항목

### [VCP-005] `vcp_ai_analyzer.py` 의 죽은 폴백 코드와 중복 헬퍼 정리

- 진행 라운드: 2026-09-21 VCP 정리 T3. 사용자 「승인도 알아서 진행하고 완료」 위임에 따른 리더 설계·계획 검토. `evidence/vcp-cleanup-20260921/design.md`, `plan.md`. 독립 critic ACCEPT. 원본 비밀·자료·서비스 접근 없이 scratch 실행.
- [x] 관련 baseline90 / 회귀103 통과; 구현 완료, 전체 baseline·리뷰·UltraQA 진행 중. 완료 아카이브 전 항목 유지.
- 카테고리: VCP 시그널 | 티어: T3 | 근거: AUDIT-VCP §3.1, §2.1
- 티어 근거: `engine/vcp_ai_analyzer.py` 는 `tier-rules.md` §2 의 "VCP 판정" 위험 경로에
  올라 있으므로 줄 수와 무관하게 T3 입니다. 리뷰는 `/ponytail-review` → `/code-review` →
  `/review` 순서를 지킵니다. 실행 코드를 바꾸므로 `/qa-only` 는 돌립니다. 화면이 바뀌지는
  않으므로 agent-browser 로 값을 대조할 자리는 없습니다.
- [ ] 호출자가 없는 `_fallback_to_zai` 제거
- [ ] `_resolve_perplexity_fallback_providers` 와 `_build_perplexity_fallback_chain` 의
      실행되지 않는 분기 정리
- [ ] `_extract_status_code` 세 사본을 하나로 통합
- [ ] `max_parse_attempts = 1` 로 죽어 있는 재시도 구조 정리
- [ ] 기존 27건의 Z.ai 테스트가 그대로 통과하는지 확인

### [INFRA-008] init_data 의 죽은 진입점 정리

- 진행 라운드: 2026-09-21 VCP 정리 T3. 사용자 「승인도 알아서 진행하고 완료」 위임에 따른 리더 설계·계획 검토. `evidence/vcp-cleanup-20260921/design.md`, `plan.md`. 독립 critic ACCEPT. 원본 비밀·자료·서비스 접근 없이 scratch 실행.
- [x] 관련 baseline90 / 회귀103 통과; 구현 완료, 전체 baseline·리뷰·UltraQA 진행 중. 완료 아카이브 전 항목 유지.
- 카테고리: 인프라 | 티어: T3 | 근거: AUDIT-INFRA §3.1, §3.2
- `scripts/init_data.py` 가 위험 경로에 있어 T3 입니다.
- [ ] `create_market_gate`(1993-2096)를 삭제하고 Market Gate 생성 경로가
      `engine/market_gate.MarketGate` 하나임을 확인
- [ ] `reset_cache`(529-534)의 존치 여부를 판단하고 불필요하면 삭제
- [ ] `assign_grade`(91-145)를 실제 등급 판정 경로에 연결하거나,
      `tests/test_grading_logic.py` 와 함께 폐기
- [ ] pytest 전체 통과 확인
