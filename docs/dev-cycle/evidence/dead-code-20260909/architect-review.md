# 전용 architect 원문 — /root/dead_code_architect

## Summary

아키텍처 레인 판정은 **`CLEAR`**입니다. 변경은 종료·파사드·리포트 책임의 경계를 바로잡으면서 살아 있는 모델 호환 경로와 CSV/SQLite 캐시 경계를 보존합니다. 차단 항목은 없으며 신뢰도는 **높음(0.96)**입니다.

## Analysis

- `close()`는 실제 제품 코드에서 싱글턴의 `atexit` 정리로만 호출됩니다(`chatbot/__init__.py:8-19`). 현재 구현은 클라이언트 종료 서비스에 위임하고 참조를 `None`으로 만드는 데 그칩니다(`chatbot/core.py:155-158`). 캐시·종목 맵·기본 세션 초기화는 생성자의 책임으로 남아 있습니다(`chatbot/core.py:116-153`). 따라서 종료 시 종목 CSV를 다시 읽던 역방향 수명주기 결합이 제거됐습니다.
- `model_name` 공개 호환 경로는 유지됩니다. `chat()`은 `model_name`을 `model`보다 우선하고 레거시 모델 호출 뒤 일반 핸들러로 위임합니다(`chatbot/core.py:208-248`). 관련 레거시 실행 경로도 그대로입니다(`chatbot/core.py:192-205`).
- 삭제한 세 private 래퍼는 클래스 파사드에서만 제거됐습니다. 실제 캐시 fallback은 여전히 서비스 함수를 직접 사용합니다(`chatbot/data_service.py:31-55`), VCP 종목 감지는 현재 믹스인 경로로 유지됩니다(`chatbot/core_data_access_mixin.py:142-164`). 하위 서비스 함수의 독립 계약도 보존돼 있습니다(`chatbot/stock_query_service.py:37-62`, `chatbot/stock_query_service.py:102-142`).
- 프롬프트 삭제는 살아 있는 빌더 경계를 침범하지 않습니다. 시스템 프롬프트 빌더는 정상 반환하고 웰컴 메시지 API도 이어집니다(`chatbot/prompts.py:169-197`). 기준 커밋 검색에서는 삭제한 세 상수가 정의부 외에 사용되지 않았습니다.
- `get_performance_report`, 전용 정규화 함수와 defaults만 사라졌고, `SignalTracker`의 분석 믹스인 구성은 그대로입니다(`engine/signal_tracker.py:18-38`). 최소 컬럼 로더와 메모리/SQLite 캐시 경계는 유지됩니다(`engine/signal_tracker_analysis_mixin.py:199-260`).
- 캐시 보존은 테스트에서 구체적으로 잠겨 있습니다. 메모리 signature 재사용, SQLite 재사용, 저장 직후 performance 캐시 priming을 각각 검사합니다(`tests/engine/test_signal_tracker_refactor.py:603-719`).
- 제품 코드 삭제량은 파일별 11+16+6+107+66줄로 정확히 **206줄**입니다. 입력의 7개 SHA-256과 사용자 소유 `package.json` 해시도 모두 일치합니다(`docs/dev-cycle/evidence/dead-code-20260909/review-input.json:2-13`).

## Root Cause

파사드 믹스인이 호출자 없는 래퍼와 성과 리포트 계약을 계속 노출했고, 종료 메서드가 리소스 해제와 생성자 초기화 책임을 섞었습니다. 이번 삭제는 호출자 없는 계약을 제거하고 객체 생성·사용·종료 책임을 다시 분리합니다.

## Recommendations

1. **현재 범위 그대로 진행** — 낮은 노력 — 요구된 경계 정리를 충족하며 추가 결합을 만들지 않습니다.
2. **첫 커밋에 미추적 회귀 테스트 포함 확인** — 낮은 노력 — `tests/chatbot/test_core_close_cleanup.py:21-36`이 아직 미추적 상태이므로 누락되면 `close()` 계약 보호가 사라집니다.
3. 외부 패키지 소비자가 별도로 존재한다면 `SignalTracker.get_performance_report` 제거를 릴리스 노트에 명시하십시오. 저장소 내부 호출자는 없지만 저장소 밖 호출자는 정적 검색으로 증명할 수 없습니다.

## Architectural Status

`CLEAR`

## Trade-offs

| 옵션 | 장점 | 단점 |
|---|---|---|
| 현재의 제한된 삭제 | 변경 범위가 작고 서비스·캐시 호환 경계를 보존 | 현재 제품 호출자가 없는 performance 캐시 표면은 남음 |
| 연관 서비스·캐시까지 확대 삭제 | 표면을 더 줄일 수 있음 | 명시 범위를 벗어나며 독립 서비스 소비자와 캐시 회귀 위험 증가 |

가장 강한 반론은 `get_performance_report`가 이름상 public 메서드라 저장소 밖 소비자가 있을 수 있다는 점입니다. 다만 이 저장소에서는 정의와 전용 테스트 외 호출자가 없고, 요구사항이 명시적으로 제거를 선택했으므로 차단 사유로 보지 않았습니다.

## 검증 상태와 한계

- 변경 경로: 표적 INFRA 20개, CHAT 호환 46개와 신규 close 회귀 1개 통과(`docs/dev-cycle/evidence/dead-code-20260909/scope.md:16`).
- 격리 전체 pytest: **2,279 통과, 3 skip**(`docs/dev-cycle/evidence/dead-code-20260909/pytest.log:33`).
- 격리 Vitest: **67파일, 462개 통과**, 실제 Next build와 TypeScript 검사 포함(`docs/dev-cycle/evidence/dead-code-20260909/vitest.log:1170-1178`).
- 7개 파일 AST 파싱 통과(`docs/dev-cycle/evidence/dead-code-20260909/syntax.json:1-5`).
- 본 레인은 요청대로 전체 테스트를 재실행하지 않고 고정 해시의 기존 로그를 검토했습니다. 브라우저는 API·응답·UI 계약 변경이 없고 `close()`의 제품 호출자가 `atexit`뿐이라 적용 대상이 아닙니다(`docs/dev-cycle/evidence/dead-code-20260909/scope.md:10-11`).
- 이는 architect 레인 판정입니다. 최종 병합 판정은 별도 code-reviewer 레인과 합성해야 합니다.
