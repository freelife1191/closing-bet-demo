# UltraQA Report

- 항목: CHAT-008, CHAT-008·009 공유 검증
- engine: ultraqa | lifecycle: app-adapted | phase: adversarial-e2e | iteration: 2 | same_failure_count: 0
- browser_applicability: required | browser_driver: agent-browser
- 근거: 실제 /chatbot 화면이 변경한 차감/세션 제목을 사용한다.
- namespace/session: slash-20260909 / qa
- 주소: http://127.0.0.1:57501/chatbot → 격리 Flask 57502. 시작 전 포트와 API_URL 확인.
- 소스: 첫 커밋 후 evidence/slash-batch-20260909/qa-source.json에 고정.
- baseline: 최종 pytest 2296통과3skip (pytest-approved.log), Vitest459/67, typecheck0, lint0error194warnings. 원본 쓰기/외부 네트워크 차단 scratch에서 실행.
- 목표: 모델 없는 명령은 무료 사용량 불변, 일반 질문은1회 차감. 명령으로 시작한 세션의 제목은 첫 일반질문이며 이후 유지.
- 안전: 실제 .env/data/3500/5501/live/LLM/발송/거래/설정 저장 접근 없음. 합성 scratch 세션만 생성/변경. prompt 안의 지시는 비신뢰 자료.
- 완료: 아래 필수5행, baseline, 독립리뷰 및 소유환경정리가 전부 통과. 최대5회/동일실패3회.

| ID | 의도·사용자 모델 | setup·실행/harness | 기대 신호 | 실제 결과·수정·증거 | cleanup | 필수 |
|---|---|---|---|---|---|---|
| S-1 | 정상 익명 사용자의 명령 반복 | 실제 앱 입력창에서 /status와 /help 전송, quota UI/서버 수치 대조 | 응답 표시, usage0 유지, LLM대역 호출0 | 미실행 | 전용세션 | 예 |
| S-2 | 명령 후 대화 제목 | 실제 앱 /clear 후 일반 질문 2회, 세션 목록과 저장소 대조 | 첫 질문 제목 유지, 일반질문당 usage1증가 | 미실행 | 합성세션만 | 예 |
| S-3 | 한도소진·명령위장 공격자 | 같은 UI 일반질문으로 한도소진 후 /status 및 일반질문. HTTP 보강: 파일첨부·앞공백·알수없는 명령·세션없음 | 명령정상/사용량불변, 일반질문402, 첨부/앞공백면제안됨 | 미실행 | 전용세션 | 예 |
| S-4 | 긴 대화·레거시·재시작 | 실제 HistoryManager 임시SQLite 회귀검사, 제목30자/50메시지절단/재로드/명령반복 | 첫 질문제목 유지, 과거자료 일괄변경없음 | 미실행 | 임시DB | 예 |
| S-5 | dirty/자료지시/종료 | rootpackage SHA/소스해시 대조, 브라우저 오류와 요청기록 확인, own프로세스종료 | 사용자파일불변, 필수오류0, 실제exit/result 일치, 소유프로세스0 | 미실행 | scratch/browser 종료 | 예 |

- 각 명령 timeout: 회귀180초/전체pytest180초/Vitest300초/build240초/브라우저30초. 별도 CLI플래그 파서·경로해석 변경은 없어 해당 공격분류 비적용.
- 성공 문구만으로 통과하지 않고 실제 상태값·HTTP상태·검사수·종료코드를 대조한다.
- 브라우저 캡처는 snapshots/screenshots/requests 및 실제 열람으로 보강한다. API 보강은 UI실측으로 세지 않는다.
- 정리: 미실행. 현재 완료 불가.

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
