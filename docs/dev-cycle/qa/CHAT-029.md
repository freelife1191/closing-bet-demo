# UltraQA Report — CHAT-029

- engine: ultraqa
- lifecycle: app-adapted
- phase: complete
- iteration: 3
- same_failure_count: 0
- baseline: 대상Vitest5통과, typecheck0, lint0오류199기존경고
- browser_applicability: required — chatbot 첨부와 답변 중단 실제 UI
- browser_driver: agent-browser
- namespace/session: chat029-20260909 / qa
- 대상: http://127.0.0.1:57391/chatbot (소유한 격리Next, API57392)
- 소스 기준: 1b803ca — source-verification.json의2파일 SHA 일치
- cleanup: complete — cleanup.json
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
| S-1 | 회귀·Unicode | 합성텍스트파일2개첨부, 파일명별제거버튼확인후하나제거 | 파일이름으로각버튼구분, 선택한파일만제거, 전송없음 | 검수 🧪.txt와남길파일.csv이름분리, 첫제거뒤csv만남음 / 통과 | 제품 추가변경 없음 | attached-two.txt/png; one-remaining.txt | 완료 |
| S-2 | 회귀·중단 | 합성SSE답변을시작하고중단버튼확인·클릭 | aria-label=답변 중단, 중단후스트리밍UI종료, 합성요청만기록 | 응답headers전대기에서명시aria-label확인→실제중단클릭→중단메시지와버튼없음 / 통과 | 제품 추가변경 없음 | pending-stop.txt; stop-aria.txt; stopped.txt/json/png | 완료 |
| S-3 | 무결성·정리 | 대상검사/typecheck/lint, page/console/Next오류·파일SHA·owned종료 | 필수실패없음, 사용자파일불변, 소유브라우저/서버/scratch정리 | 대상5pass·typecheck/lint통과, page/console/Next runtime오류없음, 소유정리와package불변 / 통과 | 제품 추가변경 없음 | static-results.json; errors-final.json; get_errors.txt; cleanup.json | 완료 |

명칭만수정하므로JSON/경로parser공격은적용불가. 특이Unicode파일명은지시가아닌데이터로취급한다.
중단은제품버튼으로만수행하고 실제LLM은호출하지않는다. timeout/exit와로그를함께확인한다.

## 실행 결과

- 필수 통과: 3/3
- 미통과 필수: 없음
- 증거: ../evidence/chat029-20260909/

## QA 진단 및 완료 범위

S2의 최초문구는합성SSE로중단버튼을표시하려는설정이었다. 실제헤더를받으면기존CHAT013때문에버튼이사라지는것을발견했다. 독립architect는WATCH로분류하고라벨검증과스트리밍상태수정을분리했다. 필수S2는버튼이존재하는응답대기에서이름/클릭/Abort후UI종료를실행했다. SSEchunk수신후중단성공이나실제백엔드작업취소를주장하지않는다. CHAT013은유지한다.

iteration1: 즉시SSE헤더후버튼소실확인. 원본fixture는개행escape도잘못되어수정했고실패증거보존.
iteration2: headers지연으로버튼명확인했으나대기상태스크린샷이정체. 소유CLI3PID와namespace/browserPPID를검증후해당자식만종료하고정상close했다.
iteration3: 같은기준소스에서ref클릭→즉시중단ref클릭→DOM결과→스크린샷순서로실행. 최종중단메시지있음/stop버튼없음확인. attached두파일선택제거성공은동일소스의S1증거를유지했다.

준비/대기오류도진단문서에보존했다. cleanup스크립트의동일readonly변수오류는분리선언후성공. 초기Next재기동직후connectionrefused는Ready확인후reload성공.
실제browser기동과합성HTTP3POST는기록되어있다. 모두파일없는합성문자열이며외부LLM호출없음. HTTP로그200은fixture의선택한응답상태이며최종브라우저는헤더전abort했으므로응답수신성공과구분한다. 서버SSE작업취소보장은이번검증대상이아니다.
Next get_errors config/session[] 확인. webpack get_compilation_issues -32602미지원은성공으로세지않고실제컴파일로그/타입검사로보강. T1대상5개와타입/lint검사완료; 이전FE034040의전체446통과를현재변경전체재실행으로주장하지않는다.

ULTRAQA COMPLETE: Goal met after 3 cycles
