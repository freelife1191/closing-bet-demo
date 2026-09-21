## 요약

아키텍처 판정은 `WATCH`입니다. 차단할 회귀는 찾지 못했으며 VCP-005/INFRA-008과 VCP-022 확신도 보완분은 출하 가능한 상태입니다. 다만 삭제된 `init_data` 심볼은 저장소 밖 수동 import와의 호환성을 의도적으로 끊으며, Z.ai echo 성공 복구 분기는 소스상 맞지만 직접 회귀 검사가 없습니다.

## 분석

- Z.ai의 1회 내부 루프 제거는 제어 흐름을 보존합니다. 모델당 최초 호출은 그대로 1회이며, echo는 같은 모델에서 최대 2회 재시도합니다. 복구되면 파싱으로 복귀하고, 소진 시 다음 모델로 전환하거나 마지막 모델에서 세션을 비활성화합니다. 품질 미달·파싱 실패·예외 역시 이전 `should_try_next_model`과 같은 위치에서 `continue`/`break` 합니다.
  근거: [engine/vcp_ai_analyzer.py:831](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/engine/vcp_ai_analyzer.py:831), [engine/vcp_ai_analyzer.py:933](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/engine/vcp_ai_analyzer.py:933), [engine/vcp_ai_analyzer.py:985](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/engine/vcp_ai_analyzer.py:985), [engine/vcp_ai_analyzer.py:1074](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/engine/vcp_ai_analyzer.py:1074)

- JSON repair도 유지됐습니다. 정상 JSON이 아니면서 응답 본문이 있을 때 같은 모델에 보정 요청을 보내고, 보정 성공 시 반환하며 실패하면 모델 체인을 계속 탑니다.
  근거: [engine/vcp_ai_analyzer.py:996](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/engine/vcp_ai_analyzer.py:996), [engine/vcp_ai_analyzer.py:1028](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/engine/vcp_ai_analyzer.py:1028), [tests/engine/test_vcp_ai_analyzer_refactor.py:753](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/tests/engine/test_vcp_ai_analyzer_refactor.py:753)

- HTTP 상태 추출 통합은 프로바이더별 차이를 보존합니다. Gemini 등은 `error.code`를 포함하고, Z.ai는 `include_code=False`로 `code`를 제외하면서 `response.status_code`와 문자열 상태 코드는 계속 인식합니다.
  근거: [engine/vcp_ai_analyzer.py:161](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/engine/vcp_ai_analyzer.py:161), [engine/vcp_ai_analyzer.py:1077](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/engine/vcp_ai_analyzer.py:1077), [tests/engine/test_vcp_ai_analyzer_refactor.py:1269](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/tests/engine/test_vcp_ai_analyzer_refactor.py:1269)

- Perplexity fallback은 설정에 포함된 Z.ai/GPT만 허용하고 Z.ai 우선 순서를 유지합니다. 제거된 반복문은 이미 추가된 두 값만 다시 순회하던 중복이었습니다.
  근거: [engine/vcp_ai_analyzer.py:1122](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/engine/vcp_ai_analyzer.py:1122), [engine/vcp_ai_analyzer.py:1134](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/engine/vcp_ai_analyzer.py:1134), [engine/vcp_ai_analyzer.py:1159](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/engine/vcp_ai_analyzer.py:1159)

- 확신도 변경은 결측값과 실제 0을 분리합니다. JSON·패턴 파서 모두 공통 `safe_confidence`를 사용하며, 원시 품질 검사는 무한대·범위 밖 값을 계속 거부합니다. 기존 구현이 변환 실패를 0으로 채우던 문제가 제거됐습니다.
  근거: [engine/vcp_ai_analyzer_helpers.py:213](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/engine/vcp_ai_analyzer_helpers.py:213), [engine/vcp_ai_analyzer_helpers.py:391](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/engine/vcp_ai_analyzer_helpers.py:391), [engine/vcp_ai_analyzer_helpers.py:674](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/engine/vcp_ai_analyzer_helpers.py:674), [review-diff.txt:644](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/docs/dev-cycle/evidence/vcp-cleanup-20260921/review-diff.txt:644)

- `init_data`의 현재 `main()`과 명령행 분기에는 삭제된 시장 게이트·캐시·등급 함수가 연결돼 있지 않습니다. 계획에는 저장소 내부 검색에서도 호출자가 없었다고 기록돼 있습니다. 다만 삭제 전 `assign_grade`가 스스로 “하위호환 함수”라고 명시했으므로, 저장소 밖 수동 import의 존재까지 부정할 수는 없습니다.
  근거: [scripts/init_data.py:2170](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/scripts/init_data.py:2170), [scripts/init_data.py:2319](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/scripts/init_data.py:2319), [review-diff.txt:683](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/docs/dev-cycle/evidence/vcp-cleanup-20260921/review-diff.txt:683), [plan.md:67](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/docs/dev-cycle/evidence/vcp-cleanup-20260921/plan.md:67)

- 동결된 6개 경로의 현재 SHA는 `review-frozen.json`과 일치합니다. 기록된 검증은 대상 103건, clamp 46건, 최종 pytest 2464건과 3 skip, Vitest 640건, lint 0 errors, typecheck·build 통과입니다. 이번 검토에서는 명시된 제약에 따라 재실행하지 않았습니다.
  근거: [review-frozen.json:2](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/docs/dev-cycle/evidence/vcp-cleanup-20260921/review-frozen.json:2), [pytarget-green2.log:3](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/docs/dev-cycle/evidence/vcp-cleanup-20260921/pytarget-green2.log:3), [pytarget-clamp.log:2](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/docs/dev-cycle/evidence/vcp-cleanup-20260921/pytarget-clamp.log:2), [pytest-final.log:39](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/docs/dev-cycle/evidence/vcp-cleanup-20260921/pytest-final.log:39), [vitest.log:2008](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/docs/dev-cycle/evidence/vcp-cleanup-20260921/vitest.log:2008)

## 근본 원인

동일한 상태 코드 추출·확신도 정규화·모델 전환 로직이 여러 위치에 중복돼 프로바이더별 차이와 결측 의미가 숨겨졌고, 사용되지 않는 호환 함수와 1회 루프가 실제 진입점처럼 남아 있었습니다. 이번 변경은 공통 함수를 재사용하고 실제 모델 루프를 직접 표현해 그 결합을 줄였습니다.

## 권고

1. **현재 변경 출하** — 낮은 추가 작업, 높은 정리 효과. VCP-005/INFRA-008 완료와 VCP-022 확신도 부분 보완으로 기록하십시오.
2. **VCP-022는 계속 미완료 유지** — 과거 모의 산출물과 실행 이력 요구는 설계상 남아 있습니다. [design.md:10](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/docs/dev-cycle/evidence/vcp-cleanup-20260921/design.md:10)
3. **저비용 후속 검사 추가 권장** — 첫 echo 후 두 번째 호출에서 정상 JSON을 돌려 “같은 모델 복구 후 파싱” 경로를 직접 고정하십시오. 현재 검사는 echo 완전 소진과 세션 비활성화만 직접 고정합니다. [tests/engine/test_vcp_ai_analyzer_refactor.py:1097](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/tests/engine/test_vcp_ai_analyzer_refactor.py:1097)
4. **마감 기록에 호환성 범위 명시** — `assign_grade`, `create_market_gate`, 캐시 함수의 저장소 밖 import 호환성은 보장하지 않는다고 남기십시오.

## Architectural Status

`WATCH`

출하 차단 사유는 없습니다. 감시점은 삭제된 스크립트 import 표면과 echo 성공 복구 분기의 직접 테스트 부재입니다.

## 트레이드오프

| 선택 | 장점 | 단점 |
|---|---|---|
| 현재 삭제 유지 | 467줄 순감소, 중복·죽은 네트워크 경로 제거, 실제 실행 구조가 선명해짐 | 저장소 밖 수동 import가 있었다면 즉시 깨짐 |
| 호환 wrapper 유지 | 외부 import 파손 가능성 감소 | 사용되지 않는 옛 등급 기준과 시장 데이터 생성 경로가 계속 정본처럼 보임 |

강한 반론은 `assign_grade`가 명시적으로 하위호환 함수였으므로 호출자 검색만으로 삭제를 정당화하기 어렵다는 것입니다. 다만 이 모듈은 현재 CLI와 `main()`에서 해당 심볼을 노출하지 않고, 프로젝트가 교육·개인 사용 범위이며 외부 API 호환을 목표로 하지 않는다는 설계 경계를 감안하면 현재 삭제가 더 타당합니다.
