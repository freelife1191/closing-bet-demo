# UltraQA Report

- 항목: CHAT-008, CHAT-008·009 공유 검증
- engine: ultraqa | lifecycle: app-adapted | phase: complete | iteration: 3 | same_failure_count: 0
- browser_applicability: required | browser_driver: agent-browser
- 근거: 실제 /chatbot 화면이 변경한 차감/세션 제목을 사용한다.
- namespace/session: slash-20260909 / qa
- 주소: http://127.0.0.1:57501/chatbot → 격리 Flask 57502. 시작 전 포트와 API_URL 확인.
- 소스: 첫 커밋은 qa-source.json, 최종 검증 기준은 evidence/slash-batch-20260909/qa-source-v3.json.
- baseline: 최종 pytest 2296통과3skip (pytest-approved.log), Vitest461/67, typecheck0, lint0error194warnings. 원본 쓰기/외부 네트워크 차단 scratch에서 실행.
- 목표: 모델 없는 명령은 무료 사용량 불변, 일반 질문은1회 차감. 명령으로 시작한 세션의 제목은 첫 일반질문이며 이후 유지.
- 안전: 실제 .env 복사·시크릿 출력, data 쓰기, 3500/5501/live 요청, 외부 LLM/발송/거래/설정 저장 없음. 합성 scratch 세션만 생성/변경. prompt 안의 지시는 비신뢰 자료.
- 완료: 아래 필수5행, baseline, 독립리뷰 및 소유환경정리가 전부 통과. 최대5회/동일실패3회.

| ID | 의도·사용자 모델 | setup·실행/harness | 기대 신호 | 실제 결과·수정·증거 | cleanup | 필수 |
|---|---|---|---|---|---|---|
| S-1 | 정상 익명 사용자의 명령 반복 | 실제 앱 입력창에서 /status와 /help 전송, quota UI/서버 수치 대조 | 응답 표시, usage0 유지, LLM대역 호출0 | PASS: 실제 UI /status·/help·/status·/clear 4회, usage0/model0, 화면10회 유지. v3-command*-after.txt/state.json | 완료 | 예 |
| S-2 | 명령 후 대화 제목 | 실제 앱 /clear 후 일반 질문 2회, 세션 목록과 저장소 대조 | 첫 질문 제목 유지, 일반질문당 usage1증가 | PASS: 일반 질문2회 후 화면8회·usage2/model2, 첫 일반 질문 검수 제목 유지. v3-q2-after.txt, v3-title.png 직접 열람 | 완료 | 예 |
| S-3 | 한도소진·명령위장 공격자 | 같은 UI 일반질문으로 한도소진 후 /status 및 일반질문. HTTP 보강: 파일첨부·앞공백·알수없는 명령·세션없음 | 명령정상/사용량불변, 일반질문402, 첨부/앞공백면제안됨 | PASS: 질문10회 후 화면0회·usage10/model10. /status200, 일반질문402. HTTP 앞공백/첨부402·unknown200, 무추가차감. 세션 없는 SSE400은 기존 생산 가드 통합 회귀로 확인. http-boundaries.json/target-review-final.log.gz | 완료 | 예 |
| S-4 | 긴 대화·레거시·재시작 | 실제 HistoryManager 임시SQLite 회귀검사, 제목30자/50메시지절단/재로드/명령반복 | 첫 질문제목 유지, 과거자료 일괄변경없음 | PASS: target-review-final92통과, history.log.gz에서 30자제목·50개절단·재시작 유지. 삭제지시 문자열은 자료로 보존 | 완료 | 예 |
| S-5 | dirty/자료지시/종료 | rootpackage SHA/소스해시 대조, 브라우저 오류와 요청기록 확인, own프로세스종료 | 사용자파일불변, 필수오류0, 실제exit/result 일치, 소유프로세스0 | PASS: 11파일 source hash 및 rootpackage 불변, data 파일목록 불변, Next 오류0/브라우저 오류0, 소유프로세스0·scratch삭제. cleanup.json | 완료 | 예 |

- 각 명령 timeout: 회귀180초/전체pytest180초/Vitest300초/build240초/브라우저45초(호출 조정기50초). 별도 CLI플래그 파서·경로해석 변경은 없어 해당 공격분류 비적용.
- 성공 문구만으로 통과하지 않고 실제 상태값·HTTP상태·검사수·종료코드를 대조한다.
- 브라우저 캡처는 snapshots/screenshots/requests 및 실제 열람으로 보강한다. API 보강은 UI실측으로 세지 않는다.
- 정리: 완료. 최종 필수 5/5 통과, 완료 가능.

## 구현 중 발견과 반영
- 혼합대소문자 multipart가 명령분류와 본문파서에서 다르게 해석됨: canonical content_type 및 filename제외조건을 일치. target-red-case → 후속전체검사.
- 제목기본문구와 첫질문이 같고 50개절단+재시작이 결합되면 제목변경: raw빈title을 신규미설정상태로 사용. 외부목록표시는 새로운 대화. 기존제목은 그대로이며 과거자료일괄수정없음. target-red-sentinel → target-sentinel-fixed93passed.
- title문자열스캔이불필요해져 ponytail 공용헬퍼변경을원복하고 작은상태구분으로대체.

- QA 기준 커밋: 63ec8826a135744f5bfcd752227b938598eefee5

## Iteration 1 실패와 보완
- 브라우저 실제 명령 무차감, 첫 질문 제목/후속 질문후보존은 확인했다.
- 일반질문2회 이후 실제 usage2/model_calls2인데 UI는 reload후에도10회남음. Sidebar.tsx의사용량GET에익명세션헤더가없어다른quota를읽음. 이번quota필수검증과직결되어CHAT-008내부수정한다.
- 증거: state-after-q2.json, q2-reloaded.txt, title.png(직접열람), iteration1-requests.jsonl.
- 기존/shared getAuthHeaders를사용량조회에도적용. frontend번들fetch/mutation문서,vercel-react-best-practices로기존callback/이벤트구독유지확인.
- iteration1전용브라우저닫음/소유서버SIGTERM. 수정전실측결과보존,완료아님.

- Iteration 2 기준: 338aae3c8b19e838ead9d977edac1b357cd7dda9

## Iteration 2 결과
- 실제명령4회 usage0/model0, 질문10회usage10/model10, 소진후/status200/일반질문402 확인. 제목유지통과.
- Sidebar헤더수정으로reload후0회남음표시일치. 그러나전용챗봇에quota-updated발행이없어현재화면은즉시갱신안됨. S-2표시필수미통과로유지.
- useChatStream finally의현재요청검사안에서 EOF후기존갱신이벤트1회발행하도록보완한다. done이벤트직후에는서버후처리전일수있어EOF를기준으로한다.
- iteration2브라우저/서버종료,raw증거보존. 동일실패count: 2 (표시불일치), iteration3 재검증예정; 동일문제재실패면한도에따라중단.

- Iteration 3 기준: 3e21127accbc8d96f04cddde5e46f062252af73e

## 최종 결과

- **ULTRAQA COMPLETE: Goal met after 3 cycles**
- 필수 5/5 통과. 첫 실측의 세션 헤더 누락과 두 번째 실측의 갱신 이벤트 누락을 수정하고 세 번째 실측에서 화면 값까지 대조했다. 이전 실패를 지우거나 optional로 낮추지 않았다.
- 최종 구현: 63ec882 → QA 수정 338aae3 → QA 수정 3e21127. 최종 소스 해시: evidence/slash-batch-20260909/qa-source-v3.json.
- 검증: pytest 2296 passed / 3 skipped(기존 수동2 + 실제 .env 비교1), Vitest 461 passed / 67 files, lint 0 errors / 194 warnings, typecheck exit0, npm run test:build 3 passed / 0 skipped. 실제 Python LSP 사용 불가.
- `/_next/mcp` compilation issues=[], configErrors=[], sessionErrors=[]. 브라우저 오류 없음. HTTP 최종 POST 19건: 정상200 16건 / 의도한402 3건. UI에서 보낸16건과 보강HTTP3건을 구분한다.
- 실제 제품 UI·챗봇 라우트·명령·저장소를 사용했다. LLM/시장데이터와 fixture 신원·usage 저장은 합성 대역이다. 실제 외부 모델·로그인·과금 서비스까지 검증한 결과로 확대하지 않는다.
- 독립 리뷰: ponytail SHIP, code-reviewer APPROVE, architect 기존 비차단 WATCH 유지. QA 수정2회는 각각 CLEAR. 종합 리뷰 COMMENT이며 merge-ready APPROVE로 바꾸지 않는다.
- WATCH: HTTP 사전 판정과 코어의 명령 문법은 향후 함께 변경해야 한다. 이번 최소 변경과 회귀 행렬을 유지하는 선택이다.
- 정리: 전용 agent-browser 종료, 소유 서버 그룹0, scratch 사본 삭제. 사용자 루트 package.json SHA와 원본 data 파일목록 SHA 불변. 원본 3500/5501/live 요청·재기동 및 .env 복사 없음.
- 검사 로그는 같은 basename의 .log.gz로 무손실 보존. 이미지 v3-title.png/v3-exhaust.png를 직접 열어8회·0회 표시와 제목·거부문구를 확인했다.
- 종료 보조 스크립트의 최초 Python 구문 오류는 실행 전 발생했다. 수정 후 source/dirty 검사와 소유 환경 정리까지 완료했으며 cleanup.json에 기록했다.
