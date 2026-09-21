## 요약

보완 delta 판정은 `CLEAR`입니다. 새 검사가 이전 WATCH 사유였던 “echo 감지 후 같은 모델에서 성공적으로 복구되는 분기”를 실제 `_analyze_with_zai` 경계에서 직접 고정했고, 외부 수동 import 비호환은 승인된 내부 정리 범위로 명확해졌습니다.

## 분석

- 검사는 실제 `_analyze_with_zai`를 호출하며 `asyncio.to_thread`를 대체하지 않습니다. 첫 응답은 echo, 두 번째 응답은 BUY/88 정상 JSON이고, 결과 전체가 기대값과 동일한지 확인합니다. [test_vcp_ai_analyzer_refactor.py:1280](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/tests/engine/test_vcp_ai_analyzer_refactor.py:1280)

- 호출 기록은 같은 `primary-zai-model`에서 온도 `0.0 → 0.3` 두 번만 허용합니다. 따라서 두 번째 호출이 다음 모델 전환이나 JSON repair가 아니라 echo 재시도 경로였음을 판별합니다. 세션 비활성화 상태도 생기지 않아 성공 복구 후 상태 오염까지 막습니다. [test_vcp_ai_analyzer_refactor.py:1294](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/tests/engine/test_vcp_ai_analyzer_refactor.py:1294)

- 최초 실패는 제품 결함이 아니라 fixture 문구가 echo 판정 임계값을 만족하지 못해 JSON repair 경로로 들어간 것이 원인이었습니다. 실패 기록의 두 번째 호출 온도는 `0.0`이었고, 현재 fixture는 detector가 요구하는 복수 패턴을 명시적으로 포함합니다. [pytarget-echo.log:26](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/docs/dev-cycle/evidence/vcp-cleanup-20260921/pytarget-echo.log:26), [engine/vcp_ai_analyzer_helpers.py:201](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/engine/vcp_ai_analyzer_helpers.py:201)

- 수정된 검사는 기존 echo 소진 검사와 함께 2건 모두 통과했습니다. [pytarget-echo2.log:1](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/docs/dev-cycle/evidence/vcp-cleanup-20260921/pytarget-echo2.log:1)

- 갱신된 테스트 SHA `7204a44f...`는 동결 파일과 현재 파일이 일치합니다. 제품 코드 3개 경로의 해시는 이전 동결과 동일하므로 이 delta는 테스트만 추가했습니다. [review-frozen.json:2](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/docs/dev-cycle/evidence/vcp-cleanup-20260921/review-frozen.json:2)

- 삭제된 `init_data` 함수의 저장소 밖 수동 import 비호환은 설계가 인정한 경계입니다. 공개 API가 아닌 교육용 내부 스크립트에서 호출자 없는 옛 구현을 제거하는 승인 범위이므로 별도 호환 wrapper를 요구하지 않습니다. [design.md:9](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/docs/dev-cycle/evidence/vcp-cleanup-20260921/design.md:9), [plan.md:67](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/docs/dev-cycle/evidence/vcp-cleanup-20260921/plan.md:67)

## 근본 원인

최초 보완 검사의 echo 문자열이 실제 detector의 “패턴 2개 이상” 계약을 만족하지 않아 repair 분기를 검사했습니다. 현재 fixture는 그 계약을 충족하며 원하는 성공 복구 분기를 직접 검증합니다.

## 권고

1. 현재 동결본으로 리뷰를 통과시키십시오.
2. 최초 실패 로그는 fixture 수정의 인과 증거로 그대로 보존하십시오.
3. VCP-022의 역사 자료 요구는 기존 계획대로 미완료 상태를 유지하십시오.

## Architectural Status

`CLEAR`

## 트레이드오프

| 선택 | 장점 | 단점 |
|---|---|---|
| 현재 직접 경계 검사 | 실제 async/thread·echo 흐름과 상태를 함께 고정 | 대상 검사 실행에 약간 더 많은 비용 |
| 내부 helper만 단위 검사 | 빠르고 단순함 | 모델 전환·repair와의 제어 흐름 결합을 검증하지 못함 |

강한 반론은 전체 pytest를 새 테스트 추가 후 다시 실행하지 않았다는 점입니다. 그러나 제품 해시는 변하지 않았고 추가된 테스트 자체와 기존 echo 소진 검사가 함께 통과했으므로, 이 테스트 전용 delta에서 추가 전체 재실행은 아키텍처 승인 조건이 아닙니다.
