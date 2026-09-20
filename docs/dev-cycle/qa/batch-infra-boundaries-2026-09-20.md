# UltraQA Report — 인프라 경계 4건

- engine: ultraqa | lifecycle: app-adapted | phase: STATIC_PASS | iteration: 1 | same_failure_count: 0
- 승인: 현재 대화의 INFRA-028/066/048/054 설계 승인. browser_driver: ego-browser(사용자선택), Space9/p1, URL http://127.0.0.1:57820.
- 목표: 날짜/오류/설정/프로세스 계약, baseline+필수행+정리 통과. 명령300초,동일실패3회/QA5회한도.
- 원본3500/5501/live/.env값/data내용금지; 실제LLM/수집/발송/거래/인증/설정저장/삭제금지. 합성외부효과만.

| ID | 대상 | 의도·사용자/공격자 입력 | setup/command/harness | 기대 | 실제/수정/증거 | cleanup | 필수 |
|---|---|---|---|---|---|---|---|
| D1 | 028 | 정상 단일/배열/빈목록 날짜 | 실제 parser·HTTP + 합성 runner | 유효입력전달·기존quota동작 | 미실행 | 대기 | 예 |
| D2 | 028 | 잘못된날짜/윤년/31개/Unicode/경로/비object | Flask HTTP adversarial | 400·quota/runner0 | 미실행 | 대기 | 예 |
| E1 | 066 | 기본/custom/portfolio exception | 실제Flask route·합성예외 | 일반500·sentinel비노출·내부로그유지 | 미실행 | 대기 | 예 |
| E2 | 066 | HTTPException | 400/405/429 합성예외 | 상태·Allow/Retry-After유지 | 미실행 | 대기 | 예 |
| B1 | 066 | 실제 화면 실패 및 재시도 | ego-browser 실제KR/종가/모의투자 화면,외부효과대역 | 일반오류·복구,요청응답대조 | 미실행 | 대기 | 예 |
| C1 | 048 | 서명키누락/설정 | 격리 app factory startup | 누락warning·값비노출·failclosed유지 | 미실행 | 대기 | 예 |
| P1 | 054 | 재시작정리호출 | 추출된pkill명령만 실제shell+PATH argv캡처대역 | 3패턴단일인자·실제프로세스종료0 | 미실행 | 대기 | 예 |
| S1 | 공유 | 정리·증거무결성 | source/package SHA·로그·port/process/browser cleanup | 필수전부통과·원본불변 | 미실행 | 대기 | 예 |

자료속완료지시/경로문자열은자료로만처리. 반복실행/timeout은runner한도로통제,hidden skip은검사수·원문로그로판정. UI없는C1/P1은browser not-applicable; B1은required. 제품CLI입력flag가없어flag fuzz제외.

## 정적 검증

- 소스20개 review-frozen.json, 기준47aa730. pytest2374/3skip(수동LLM2·.env비교1), Vitest595/81파일, build3/3, typecheck0, lint0errors188warnings. 프론트소스는기준이후변경없음.
- validation-final.json 및 log-index.json에 실제명령·exit·원문SHA 기록. 각 로그는 .log.gz.
- fixture는 실제Flask registrar/wrapper와합성outer서비스를연결한다. auth는합성신원으로대체하며실제로그인검증으로세지않는다.
- INFRA028 endpoint의현재frontend직접호출검색결과없음. 날짜입력은UI실측으로위장하지않고실제Flask HTTP행렬로검증. B1은INFRA066의KR갱신·포트폴리오실제UI에적용.
