## Architectural Status

`BLOCK`

## Summary

검토한 6개 파일의 SHA-256은 `review-input.json`과 모두 일치합니다. 정적 검사는 통과했지만, 최초 VCP 대화의 화면 인덱스와 서버 인덱스가 달라 다른 메시지를 삭제하는 실측 결함이 확인됐습니다. 중복 삭제·스트리밍 경합·중첩 모달 Escape도 현재 공통 상태 경계에서 차단되지 않습니다.

## Analysis

### 1. BLOCKER — 최초 대화에서 다른 메시지를 삭제함

VCP 화면은 `chatHistory`의 렌더 인덱스 `i`를 삭제 인덱스로 그대로 넘깁니다([page.tsx](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/dashboard/kr/vcp/page.tsx:1982), [page.tsx](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/dashboard/kr/vcp/page.tsx:2052)). 그 값은 DELETE 쿼리에 그대로 들어가고, 성공하면 같은 UI 인덱스를 제거합니다([page.tsx](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/dashboard/kr/vcp/page.tsx:405), [page.tsx](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/dashboard/kr/vcp/page.tsx:424)).

하지만 최초 대화의 `chatHistory`에는 서버에 저장되지 않는 환영 메시지가 앞에 있습니다. 서버는 전달된 인덱스를 저장 이력 배열에 직접 적용합니다([kr_market_chatbot_request_helpers.py](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/services/kr_market_chatbot_request_helpers.py:75), [storage.py](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/chatbot/storage.py:322)).

실측에서도 삭제 전 서버 이력은 `user, model` 두 건이었고([preflight-history-before.json](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/docs/dev-cycle/evidence/chat-ui-20260914/preflight-history-before.json:2)), 질문 삭제 후 `user`만 남았습니다([preflight-history-after.json](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/docs/dev-cycle/evidence/chat-ui-20260914/preflight-history-after.json:2)). 화면에서 질문을 눌렀지만 서버에서는 모델 답변을 삭제한 것입니다.

현재 회귀 검사는 처음부터 서버 이력 한 건만 반환해 client-only 환영 메시지가 있는 상태를 만들지 않습니다([page.regression-chat-020.test.tsx](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/dashboard/kr/vcp/page.regression-chat-020.test.tsx:107)).

### 2. BLOCKER — 중복 방지가 세 삭제 진입점에 공통 적용되지 않음

`vcpChatDeletePendingRef`는 확인 모달의 `handleConfirmDeleteChatHistory`에만 적용됩니다([page.tsx](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/dashboard/kr/vcp/page.tsx:437)). `/clear`는 잠금 없이 `deleteVcpChatHistory`를 직접 호출하며([page.tsx](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/dashboard/kr/vcp/page.tsx:1080)), 공통 삭제 함수 자체에는 pending 검사가 없습니다([page.tsx](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/dashboard/kr/vcp/page.tsx:405)).

따라서 빠른 Enter·클릭 또는 모달 삭제와 `/clear`의 교차 호출은 같은 세션에 중복 DELETE를 보낼 수 있습니다. “세 삭제 진입점의 공통 처리와 중복 방지” 계약을 충족하지 않습니다([implementation-plan.md](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/docs/dev-cycle/evidence/chat-ui-20260914/implementation-plan.md:28)).

### 3. BLOCKER — 삭제 성공을 기존 SSE가 다시 덮을 수 있음

전송 경로는 사용자 메시지를 먼저 추가하고 세션 키를 만들며([page.tsx](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/dashboard/kr/vcp/page.tsx:1094)), 스트림 도중 새 세션 ID와 `chatHistory`를 계속 갱신합니다([page.tsx](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/dashboard/kr/vcp/page.tsx:1156), [page.tsx](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/dashboard/kr/vcp/page.tsx:1205)).

반면 삭제 성공은 세션 키를 제거하고 환영 메시지를 설정할 뿐, 진행 중 스트림의 세대를 폐기하거나 중단하지 않습니다([page.tsx](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/dashboard/kr/vcp/page.tsx:422)). 삭제 버튼도 스트리밍 상태와 무관하게 표시됩니다([page.tsx](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/dashboard/kr/vcp/page.tsx:1943)).

따라서 삭제 직후 늦은 SSE가 세션 키를 되살리거나 환영 메시지에 응답 조각을 붙일 수 있습니다. 현재 S-7은 지연 DELETE와 종목 전환을 다루지만, 전송 중 삭제는 포함하지 않습니다([CHAT-020.md](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/docs/dev-cycle/qa/CHAT-020.md:19)).

### 4. WATCH — 중첩 모달에서 Escape 한 번에 두 계층이 닫힘

drawer는 열린 동안 `window`의 Escape를 듣습니다([chatbot/page.tsx](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/chatbot/page.tsx:202)). drawer 안의 세션 삭제 버튼은 drawer를 유지한 채 확인 모달을 엽니다([chatbot/page.tsx](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/chatbot/page.tsx:621)).

확인 모달은 별도로 `document` Escape를 처리합니다([Modal.tsx](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/components/Modal.tsx:52)). 같은 keydown이 `document`에서 모달을 닫은 뒤 `window`까지 전달되어 drawer도 닫힙니다. ModalShell 내부의 최상위 모달 스택은 drawer 리스너까지 통제하지 못합니다.

S-2는 drawer 접기·닫기·항목 선택만 포함하며 중첩 확인 모달의 Escape 순서를 검증하지 않습니다([CHAT-010.md](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/docs/dev-cycle/qa/CHAT-010.md:14)).

## 8행 실측 계획 대조

| 행 | 판정 | 보강 필요 |
|---|---|---|
| S-1 | 적절 | 현재 계획 유지 |
| S-2 | 불충분 | drawer 위 삭제 확인 모달에서 첫 Escape는 모달만, 두 번째 Escape는 drawer와 초점 복원을 확인 |
| S-3 | 적절 | 현재 계획 유지 |
| S-4 | 차단 결함 발견 | 최초 세션의 `welcome + user + model` UI와 서버 `user + model` 인덱스를 함께 대조 |
| S-5 | 대체로 적절 | 빠른 확인 연타가 DELETE 한 건만 만드는지 추가 |
| S-6 | 불충분 | `/clear` 연타 및 모달 삭제와 `/clear` 교차 호출 확인 |
| S-7 | 불충분 | 같은 종목의 새 세션뿐 아니라 진행 중 SSE 이후 삭제 성공이 유지되는지 확인 |
| S-8 | 적절 | 위 시나리오의 요청·UI·서버 이력 증거를 포함해야 함 |

## Root Cause

UI 배열 위치를 서버 저장 메시지의 식별자로 사용하면서 client-only 메시지와 진행 중 스트림을 같은 배열에 섞었습니다. 삭제 중복 잠금과 비동기 세대 판정도 공통 삭제 경계가 아니라 일부 호출자에만 있어, 세 진입점과 기존 스트림이 하나의 정합성 규약을 공유하지 않습니다.

## Recommendations

1. **저장 메시지 인덱스를 명시적으로 분리** — 높은 우선순위
   client-only 환영 메시지를 서버 인덱스 계산에서 제외하고, 삭제 가능한 메시지에 저장 인덱스 또는 안정적인 로컬 식별자를 붙이십시오. 최소한 최초 전송 후 서버 이력으로 정규화해 UI 배열과 저장 배열을 일치시켜야 합니다.

2. **pending과 세대 검사를 공통 삭제 함수 바깥의 단일 래퍼로 이동** — 높은 우선순위
   모달의 전체 삭제·메시지 삭제·`/clear`가 모두 같은 래퍼를 통과하게 하고, ticker·session·operation generation을 응답 직전에 검사하십시오.

3. **전송과 삭제의 경합 계약을 정의** — 중간 노력
   삭제 시작 시 해당 chat operation generation을 증가시켜 이전 SSE의 `localStorage`와 `chatHistory` 쓰기를 폐기하거나, 스트림 종료 전 삭제를 명시적으로 막으십시오.

4. **drawer Escape에 최상위 오버레이 조건 추가** — 낮은 노력
   ModalShell로 drawer를 전환하는 큰 리팩터링 없이, 삭제 확인 등 상위 모달이 열렸으면 drawer의 `window` Escape가 반응하지 않도록 하십시오.

5. **회귀 검사와 QA 보강 후 전체 검증 재실행**
   현재 정적 증거는 Vitest 69파일·471검사 통과([vitest-review.log](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/docs/dev-cycle/evidence/chat-ui-20260914/vitest-review.log:1292)), lint 0오류·190경고([lint-review.log](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/docs/dev-cycle/evidence/chat-ui-20260914/lint-review.log:343)), build 3/3([build-review.log](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/docs/dev-cycle/evidence/chat-ui-20260914/build-review.log:43)), pytest 2296통과·3스킵([pytest.log](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/docs/dev-cycle/evidence/chat-ui-20260914/pytest.log:33))입니다. 위 결함을 다루지 않으므로 수정 후 새 SHA에서 다시 검증해야 합니다.

## Trade-offs

| 선택 | 장점 | 단점 |
|---|---|---|
| 환영 메시지 오프셋만 보정 | diff가 가장 작음 | 다른 client-only 메시지가 생기면 다시 깨짐 |
| 클라이언트 메시지에 저장 인덱스·세대 추가 | 백엔드 계약 변경 없이 정합성 확보 | 큰 단일 컴포넌트의 상태 모델이 조금 늘어남 |
| 서버가 안정적인 message ID 제공 | 장기적으로 가장 안전 | 승인된 백엔드 무변경 범위를 벗어남 |

가장 강한 반론은 “471개 검사가 통과했고 ticker·session 비교도 구현됐으므로 QA에서 확인하면 된다”입니다. 그러나 현재 검사는 서버에서 로드된 이력만 사용해 client-only 환영 메시지를 재현하지 않았고, 실제 서버 대조는 이미 다른 메시지가 삭제됨을 증명했습니다. 이 반론으로 출하할 수 없습니다.

검토 종료 조건은 위 세 BLOCKER 수정, 관련 회귀 추가, 8행 QA 계획 보강, 새 최종 SHA 기반의 독립 재검토입니다.
