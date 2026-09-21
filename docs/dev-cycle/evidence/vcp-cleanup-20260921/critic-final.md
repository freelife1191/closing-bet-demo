최종 판정: **ACCEPT**

설계와 보완된 계획은 현재 저장소 호출 관계에 맞고, VCP-005·INFRA-008 완료와 VCP-022 confidence 부분 보완을 같은 라운드에서 실행할 수 있습니다.

확인된 근거:

- `assign_grade`는 `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/tests/test_grading_logic.py`에서만 직접 사용되며, 실제 엔진 등급 계약은 `tests/engine/test_grade_classifier_refactor.py`가 계속 검증합니다.
- `create_market_gate`, `reset_cache`, `get_market_indices`, `get_sector_indices`는 저장소 내 외부 호출자가 확인되지 않았습니다.
- VCP confidence 정규화는 JSON 경로와 패턴 복구 경로 두 곳 모두 `safe_confidence`로 전환해야 하며, `None`은 저품질로 처리하고 실제 `0`은 보존하는 계획이 명확합니다.
- 기존 Z.ai 모델 전환·echo 재시도·JSON repair·provider 제한 테스트를 보존하도록 계획에 반영됐습니다.

남은 중대 위험은 구현 시 반드시 확인해야 하는 제어 흐름 두 가지입니다.

1. 공통 status-code helper 전환 후 Gemini의 `code` 인식과 Z.ai의 `code` 무시 차이를 유지해야 합니다. `response.status_code`와 문자열 내 HTTP 코드 추출도 각각 회귀 테스트가 필요합니다.

2. Z.ai의 `max_parse_attempts = 1` 루프 제거 시 `should_try_next_model`, 내부 `break`, 외부 `continue`가 유지되어야 합니다. 마지막 모델 실패 시 규칙 기반 fallback이 실행되고, provider 목록 밖 fallback이 실행되지 않아야 합니다.

이 조건들은 계획의 테스트·리뷰·UltraQA 단계에서 검증 가능하며, 별도 설계 변경을 요구할 정도의 차단 문제는 확인되지 않았습니다. 원본 `.env`·`data`·`logs`, 서버·라이브 접근 없이 진행 가능한 범위입니다.
