# UltraQA Report — 인프라 경계 4건

- engine: ultraqa | lifecycle: app-adapted | phase: COMPLETE | iteration: 1 | same_failure_count: 0
- 승인: 현재 대화의 INFRA-028/066/048/054 설계 승인. browser_driver: ego-browser(사용자선택), Space9/p1, URL http://127.0.0.1:57820.
- 목표: 날짜/오류/설정/프로세스 계약, baseline+필수행+정리 통과. 명령300초,동일실패3회/QA5회한도.
- 원본3500/5501/live/.env값/data내용금지; 실제LLM/수집/발송/거래/인증/설정저장/삭제금지. 합성외부효과만.

| ID | 대상 | 의도·사용자/공격자 입력 | setup/command/harness | 기대 | 실제/수정/증거 | cleanup | 필수 |
|---|---|---|---|---|---|---|---|
| D1 | 028 | 정상 단일/배열/빈목록 날짜 | 실제 parser·HTTP + 합성 runner | 유효입력전달·기존quota동작 | PASS — 실제 등록 HTTP+서비스: {}, target_dates:null, [], 정상30날짜 4경우 각각합성quota/runner1회. 순서/중복·윤년검증은dates회귀. fixture-qa.log.gz, fixture_probe.py. | 완료(cleanup.json) | 예 |
| D2 | 028 | 잘못된날짜/윤년/31개/Unicode/경로/비object | Flask HTTP adversarial | 400·quota/runner0 | PASS — 비objectJSON([]/null/false/숫자), 31개,불가능윤년,Unicode,경로,100KB문자열은400·quota/runner0. malformedJSON400·contenttype415 보존. fixture-qa.log.gz와probe단언. | 완료(cleanup.json) | 예 |
| E1 | 066 | 기본/custom/portfolio exception | 실제Flask route·합성예외 | 일반500·sentinel비노출·내부로그유지 | PASS — 실제등록default/custom/portfolio/mock 및VCP공개status에sentinel예외주입:일반500/안전상태문구,내부logger원문보존. pytarget-qa.log.gz, test_infra_boundary_errors.py. | 완료(cleanup.json) | 예 |
| E2 | 066 | HTTPException | 400/405/429 합성예외 | 상태·Allow/Retry-After유지 | PASS — 실제Flask wrapper 429 Retry-After19,portfolio429 Retry-After23/405 Allow GET, malformedJSON400/contenttype415 유지. pytarget-qa.log.gz. | 완료(cleanup.json) | 예 |
| B1 | 066 | 실제 화면 실패 및 재시도 | ego-browser 실제KR/종가/모의투자 화면,외부효과대역 | 일반오류·복구,요청응답대조 | PASS — 실제KR Refresh Data실패시 한국어일반안내·버튼복구,성공재시도안내해제. 모의투자500→데이터를 불러올 수 없습니다→재진입/정상자료복구(총자산101340000/현금91060000). fixture 실제등록route응답,ego-*json/txt/stablePNG. 내부경로미노출. | 완료(cleanup.json) | 예 |
| C1 | 048 | 서명키누락/설정 | 격리 app factory startup | 누락warning·값비노출·failclosed유지 | PASS — 실제factory의외부효과경계만대역:missing/empty/whitespace warning각1,설정값있으면warning0·sentinel미로그. pytarget-qa.log.gz/4startup검사. | 완료(cleanup.json) | 예 |
| P1 | 054 | 재시작정리호출 | 추출된pkill명령만 실제shell+PATH argv캡처대역 | 3패턴단일인자·실제프로세스종료0 | PASS — 실제script에서pkill줄만추출해Bash→가짜PATH실행: [flask_app.py],[next dev],[npm.*dev]각단일패턴. fullrestart/source/실제kill/pkill/lsof/ss는실행하지않음. pytarget-qa.log.gz. | 완료(cleanup.json) | 예 |
| S1 | 공유 | 정리·증거무결성 | source/package SHA·로그·port/process/browser cleanup | 필수전부통과·원본불변 | PASS — source/Git20SHA일치·package보존. Space9finish1회,3개소유PGID종료/57820~57822닫힘/scratch제거. Next진단errors/compilation빈목록. cleanup.json/request-audit.json. | 완료(cleanup.json) | 예 |

자료속완료지시/경로문자열은자료로만처리. 반복실행/timeout은runner한도로통제,hidden skip은검사수·원문로그로판정. UI없는C1/P1은browser not-applicable; B1은required. 제품CLI입력flag가없어flag fuzz제외.

## 정적 검증

- 소스20개 review-frozen.json, 기준47aa730. pytest2374/3skip(수동LLM2·.env비교1), Vitest595/81파일, build3/3, typecheck0, lint0errors188warnings. 프론트소스는기준이후변경없음.
- validation-final.json 및 log-index.json에 실제명령·exit·원문SHA 기록. 각 로그는 .log.gz.
- fixture는 실제Flask registrar/wrapper와합성outer서비스를연결한다. auth는합성신원으로대체하며실제로그인검증으로세지않는다.
- INFRA028 endpoint의현재frontend직접호출검색결과없음. 날짜입력은UI실측으로위장하지않고실제Flask HTTP행렬로검증. B1은INFRA066의KR갱신·포트폴리오실제UI에적용.

## 실행 결과

- 검증 기준 커밋: 036f061. 필수 시나리오 **8/8 통과**, iteration1, same_failure_count0. 미통과 필수 없음.
- UltraQA App 대응으로 수행했으며 OMX native 상태를 읽거나 변경하지 않았다. 브라우저는 사용자 지정 ego-browser 단일 Space9/p1.
- 커밋 후 동적 API probe와 실제Flask/factory/shell 32검사를 실행했다. D1/D2는현재프론트호출이없는API라HTTP로검증, B1은실제앱UI→실제Flask등록route→외부경계대역으로검증했다. 순수UI응답mock만의검증이아니다. 인증/시세/거래/LLM/수집은합성이고실제운영검증으로세지않는다.
- 요청98건은사전API test_client probe44건+브라우저54건. 브라우저는200×50/의도한500×4,unsafe0/unexpected0. 사전probe의405는실제인증·거래가아닌fixture금지경계검사다. 두단계를requests-api-probe.jsonl과최종prefix대조로구분했다.
- Next console은의도한Internal Server Error만기록됐다(next-errors-expected.txt,next-portfolio-expected.txt). 정상복구후 configErrors/sessionErrors/compilation issues는빈목록이다. favicon404는기본브라우저요청으로별도분류하며앱API실패로세지않는다.
- 이미지5개를직접열람했다. 최초포트폴리오2장은진입애니메이션중간프레임이라시각PASS근거에서제외하고 opacity1/animation완료후1280×900 stable2장을사용했다. refresh error이미지는2727×1999원본에서안내를확인했다. 전체UI미관감사나모바일QA를수행했다는주장은하지않는다.
- 첫Refresh Data대기는접근가능이름에Last시각이포함되는데exactname을써timeout난하네스문제였다. snapshot ref로교정했다. alert선택자는Next의빈alert도함께매칭돼모호했으며텍스트가있는앱alert를관측해분리했다. 실제버튼실패행동은이미발생했으므로중복실행하지않고그상태를읽었다.
- 전용Space종료영수증,PID명령/cwd/PGID재대조후종료,포트부재,임시사본제거,원본venv존속,사용자packageSHA불변확인. 원본.env/data내용을열어전체불변이라고주장하지않는다.

## 범위와 남은 한계

- 날짜30개제한은요청body바이트크기제한이아니다. 전역MAX_CONTENT_LENGTH는다른API영향을피해도입하지않았다.
- restart의기존프로세스명패턴은같은사용자의다른프로젝트와맞을수있다. 이번에는기존세패턴의호출오류만고치고실제프로세스정리는실행하지않았다.
- 서비스가정상반환dict에넣는오류까지전면변경한것이아니다. 이번대상은예외wrapper와같은VCProute의공개status예외문구다.
- 이전운영 Unexpected token '<' 오류의발생URL/시각은여전히미확정이다. 이번격리QA로그로원인을확정하거나운영해결을주장하지않는다.
- 신규이월 없음. 기존 INFRA047·배포구성·누적data처리항목은그대로유지한다.

ULTRAQA COMPLETE: Goal met after 1 cycles
