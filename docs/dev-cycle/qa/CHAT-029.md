# UltraQA Report — CHAT-029

- engine: ultraqa
- lifecycle: app-adapted
- phase: planning
- iteration: 1
- same_failure_count: 0
- baseline: 대상Vitest5통과, typecheck0, lint0오류199기존경고
- browser_applicability: required — chatbot 첨부와 답변 중단 실제 UI
- browser_driver: agent-browser
- namespace/session: chat029-20260909 / qa
- 대상: http://127.0.0.1:57391/chatbot (소유한 격리Next, API57392)
- 소스 기준: 첫 구현 커밋 후 기록
- cleanup: 미실행
- UltraQA Report: [CHAT-029.md](CHAT-029.md)

## 목표와 경계

첨부 제거 버튼은 파일명+첨부 제거, 답변 중단 버튼은 명시적 aria-label을 제공한다. 기존동작유지.
실제Next화면·전송/중단훅은유지하고 외부HTTP/SSE만합성대역을사용한다. 실제LLM전송/비용없음.
원본3500/5501/live/env/data/userpackage를변경하지않는다. .omx/state미조작.
필수행·정적검사·정리모두통과해야완료. 같은실패3회/총5회상한, 명령30초·검사15분·QA30분상한.

## 행렬

모든행필수. 사용자모델은합성일반사용자. command/harness는agent-browser의open→snapshot→upload/ref조작→wait→snapshot/screenshot이며S3은정적증거도대조한다.

| ID | 의도·분류 | setup·조작 | 기대 신호 | 실제·결과 | 수정 | 증거 | cleanup |
|---|---|---|---|---|---|---|---|
| S-1 | 회귀·Unicode | 합성텍스트파일2개첨부, 파일명별제거버튼확인후하나제거 | 파일이름으로각버튼구분, 선택한파일만제거, 전송없음 | 미실행 | 없음 | 미실행 | 미실행 |
| S-2 | 회귀·중단 | 합성SSE답변을시작하고중단버튼확인·클릭 | aria-label=답변 중단, 중단후스트리밍UI종료, 합성요청만기록 | 미실행 | 없음 | 미실행 | 미실행 |
| S-3 | 무결성·정리 | 대상검사/typecheck/lint, page/console/Next오류·파일SHA·owned종료 | 필수실패없음, 사용자파일불변, 소유브라우저/서버/scratch정리 | 미실행 | 없음 | 미실행 | 미실행 |

명칭만수정하므로JSON/경로parser공격은적용불가. 특이Unicode파일명은지시가아닌데이터로취급한다.
중단은제품버튼으로만수행하고 실제LLM은호출하지않는다. timeout/exit와로그를함께확인한다.

## 실행 결과

- 필수 통과: 0/3
- 미통과 필수: S-1~S-3
- 증거: ../evidence/chat029-20260909/
