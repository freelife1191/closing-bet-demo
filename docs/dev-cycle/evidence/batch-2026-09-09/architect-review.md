## Summary
`engine/phases_pipeline.py`의 단일 Phase1 호출 변경과 회귀 테스트는 설계 목표에 맞습니다. 다만 현재 지정 범위에는 `frontend/src/app/chatbot/page.regression-chat-004.test.tsx`의 엄격한 TypeScript 타입 위험이 하나 있어 `WATCH` 판정입니다. 이 테스트는 `useChatStream`의 실제 SSE 종료 계약과는 일치하지만, resolver 타입을 명시하지 않으면 `strict: true`에서 type-check가 실패할 가능성이 있습니다.

## Analysis
- `engine/phases_pipeline.py:40-68`: SignalGenerationPipeline.execute는 Phase1Analyzer.execute(candidates, target_date=target_date)를 정확히 한 번 호출합니다. 내부 TypeError를 인자 호환성으로 오인해 재호출하던 경로가 제거되었습니다. Phase1 예외가 발생하면 Phase2~4로 진행하지 않으므로 오류 동일성·호출 횟수 검사가 유효합니다. market_status는 기존처럼 Phase3에만 전달되고, target_date는 Phase1·Phase4에 전달되어 외부 인터페이스 변경은 없습니다.
- `tests/engine/test_phases_pipeline_refactor.py:178-195`: 새 테스트는 같은 TypeError 객체가 전파되는지, Phase1 호출이 정확히 한 번인지 검증합니다. 후속 Phase 미호출은 _build_pipeline의 호출 기록 구조상 간접적으로 보장됩니다.
- `frontend/src/app/chatbot/useChatStream.ts:179-208`: 실제 루프는 SSE의 data.done 필드로 종료하지 않고 reader의 {done: true}로 종료합니다. 따라서 테스트가 마지막 done: true 이벤트를 전달한 뒤 별도로 close()를 호출하는 구조는 실제 구현과 맞습니다. 청크마다 deliverNextChunk()가 pending reader.read()를 해소하므로 시간 기반 대기보다 결정적입니다.
- `frontend/src/app/chatbot/page.regression-chat-004.test.tsx:65,74`: pendingReads는 resolver에 { value: Uint8Array | undefined; done: boolean } 타입을 선언했지만 new Promise(resolve => ...)에 Promise 제네릭이 없습니다. frontend/tsconfig.json은 strict: true입니다. 따라서 resolve가 unknown 값을 받는 함수로 추론되어 pendingReads.push(resolve)에서 TypeScript 오류가 날 수 있습니다. Promise<{ value: Uint8Array | undefined; done: boolean }>를 명시하는 것이 안전합니다.
- `tests/app/test_kr_market_data_signals_routes_refactor.py:370-434`: 시간 기반 sleep/deadline 대신 threading.Event 세 개로 시작·완료·중지 순서를 동기화했습니다. finally에서 release event를 설정하고 완료를 기다려 daemon thread가 다음 테스트로 남지 않도록 했습니다. 이 변경은 지정된 재분석 중지 경합 테스트에 국한되며 pipeline 단일 호출과 직접 결합되지 않습니다.
- `frontend/package.json:10-11`: test를 vitest run으로 바꾸고 watch 모드를 test:watch로 분리했습니다. 기존 CI/개발 호출자가 npm run test를 종료형 검사로 기대하는 변경입니다. watch가 필요한 개발자는 명시적으로 npm run test:watch를 사용해야 합니다.

## Root Cause
Pipeline 결함의 근본 원인은 Phase1 내부 TypeError를 구버전 호출 시그니처 호환 실패로 간주한 broad fallback입니다. 현재 변경은 이 모호한 재호출을 제거하고 실제 예외를 보존합니다.
Chat-004 테스트 변경의 유일한 건축상 위험은 구현이 아니라 mock의 Promise resolver 타입 추론입니다. 동작 순서는 올바르지만 strict 컴파일 계약이 명시적으로 잠기지 않았습니다.

## Recommendations
1. WATCH 해소: page.regression-chat-004.test.tsx:74의 new Promise에 반환 타입을 명시합니다. 테스트 동작 변경 없이 type-check 위험만 제거됩니다.
2. CLEAR: phases_pipeline.py와 해당 Python 회귀 테스트의 단일 호출 계약은 승인된 JONGGA-014 범위와 일치합니다.
3. WATCH: frontend/package.json의 test 스크립트 변경은 의도된 종료형 테스트 계약으로 보이지만, 문서/CI에서 npm run test를 watch 모드로 전제하는 호출자가 없는지 별도 확인이 필요합니다. 지정 파일 외 변경은 이 조사에서 추정하지 않았습니다.

## Architectural Status
WATCH
구체적인 구현 흐름은 CLEAR이나, strict TypeScript resolver 타입과 종료형 npm test 계약 확인 전에는 전체 묶음을 CLEAR로 올리기 어렵습니다.

## Trade-offs
resolver Promise 타입 명시: 최소 diff, strict type-check 안정성 / 테스트 보조 코드에 타입 한 줄 추가.
현재 추론 유지: 코드가 짧음 / TypeScript 버전·추론 변화에 따라 type-check가 깨질 수 있음.

## 재판정 원문
리더가 제공한 fresh evidence와 실제 `strict` type-check 결과를 반영하면 이전 `WATCH`는 해소됩니다. 현재 지정 범위의 아키텍처 상태는 `CLEAR`입니다.
- baseline-results.json: 전체 pytest exit0 2260통과/2skip, Vitest exit0 424통과/59파일, npm run type-check exit0.
`pendingReads.push(resolve)`는 Promise resolver가 구체 타입을 받을 수 있는 구조이고, 실제 저장소의 strict type-check가 exit 0으로 통과했으므로 앞서 제기한 타입 오류는 실제 잔여 결함이 아닌 가설로 폐기합니다.
`frontend/package.json`의 `npm test` 종료형 전환도 사용자 승인 범위이며 `test:watch`가 별도 제공됩니다. 따라서 계약 불일치 잔여도 없습니다.
### Architectural Status
CLEAR
Pipeline 단일 호출, SSE 테스트 제어 흐름, stop 경합 동기화, 종료형 Vitest 명령 계약 모두 현재 증거와 일치합니다. 추가적인 구현 차원의 blocker는 확인되지 않았습니다.

부록: 검토 파일 SHA는 review-input.json. 경로/서식을 정리하고 원문 판단 및 미확인 가설·철회 이력을 보존했다.
