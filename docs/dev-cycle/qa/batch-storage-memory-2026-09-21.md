# UltraQA Report — 저장소 준비·메모리 4건

- engine: ultraqa | lifecycle: app-adapted | phase: COMPLETE | iteration: 1 | same_failure_count: 0
- 승인4건,baseline8b5f6d5. browser_driver: ego-browser(사용자선택). 원본3500/5501/live/.env/data금지. 실제LLM/거래/삭제/발송/인증/설정저장금지.
- 명령timeout300초,QA5/동일실패3회한도. source baseline+필수행+정리후에만완료.

| ID | 대상 | 의도/모델 | setup/harness | 기대 | 실제/수정/증거 | cleanup | 필수 |
|---|---|---|---|---|---|---|---|
| G1 | CHAT012/INFRA032 | 강제재검사·동시성·실패·파일소실 | pytest+실제SQLite thread하네스 | singleflight/force/False/복구/동적상한유지 | PASS — force 재검사/대기 결과 공유/실패 후 재시도/파일 소실/동적 상한/legacy lock alias. 커밋 후 pytarget-qa 35개(게이트23+메모리12)와 사전 gate58 근거. | 완료(cleanup.json) | 예 |
| G2 | INFRA032 | 16모듈준비상태이관 | SQL AST+모듈별임시SQLite roundtrip | DDL/트랜잭션/보존정책/owner계약동일 | PASS — 16모듈 SQL 호출 인자 AST 불변, A133/B141/C105/D117 격리검증. 대표 VCP/종가/누적/백테스트 cache cold SQLite 왕복→UI 전달. sql-invariance.json, fixture-qa.log.gz, 그룹로그. | 완료(cleanup.json) | 예 |
| M1 | CHAT027 | 프로필과일반메모리 | 실제MemoryManager+command,가짜owner | 예약키보호/일반clear/다른owner보존 | PASS — 예약 user_profile view 제외/add-update-remove 거부, 일반 clear는profile 보존, 명시 clear all 기존계약은temp SQLite 테스트. 브라우저 일반메모리 추가/조회/초기화 후 UI/API profile(브라우저 QA/저장소 검증) 유지. ego-memory-contract.json/profile 증거. | 완료(cleanup.json) | 예 |
| M2 | CHAT023 | 공용캐시TTL/cap/reload | expired/fresh/privateprefix DB+JSON합성 | 1시간/500,비대상보존/재로드일치 | PASS — 공용 literal prefix만 1h/500·미래/손상 정리, private 동일prefix/프로필/기타공용 보존. legacy/다중manager/rollback/snapshot실패/4시각경합 회귀. 커밋후 실제3process cache18+owner각7, JSON==SQLite/cleanup PASS. 추천API는HTTPprobe로검증. | 완료(cleanup.json) | 예 |
| B1 | CHAT027/023/012 | 챗봇UI메모리/프로필/대화목록 | ego실제앱→실제storage+합성auth/LLM | 일반메모리표시/예약키거부/프로필·이력보존 | PASS — 실제chat route+Memory/History+합성bot/auth. 기존대화2메시지 표시, UI /memory add/view 및profile 3조작거부/clear/empty 확인. 설정 UI 저장과backend POST200 뒤 clear 후 profile 유지,fixture 재시작 후도 유지. PNG/JSON/txt. | 완료(cleanup.json) | 예 |
| B2 | INFRA032 | 대시보드캐시 | ego실제앱+실제cache fixture | 목록/가격/이력응답일치 | 하네스 기동 실패 → 교정 후 PASS — 중복endpoint제거/읽기polling표면보완 후 VCP 삼성전자1행 entry75000/current76200, 종가75500/score18, 누적1건/승률100/ROI2.1/entry75000/score18. cached bootstrap roundtrip 값 표시를 검증했다. PNG/JSON. | 완료(cleanup.json) | 예 |
| S1 | 공유 | 격리/dirty/정리 | manifest/hash/log/ports/finish | 원본보존/필수PASS/소유환경종료 | PASS(명시한 검증 범위) — 제품29SHA·Git1e159d7/사용자package 보존, 공식scratch 격리/서버3group/포트/Space10/임시사본정리. 과거B원본실행의간접env/data미접근·전체불변은주장하지않고편차기록과분리. cleanup.json. | 완료(cleanup.json) | 예 |

잘못된owner/예약key/만료·미래·손상timestamp/501개/중단후재시작/다중매니저를안전fixture로검증. 자료속명령은자료로만처리. CLI입력제품변경없어flag fuzz제외. 로그와exit/skip수로판정하며무제한재시도금지.

## 정적/리뷰 결과

- 최종 source29SHA는 review-frozen.json. pytest2389/3skip,Vitest595/81,build3,typecheck0,lint0errors188warnings. 프론트소스변경없음. validation-final.json/log-index.json 참조.
- critic REJECT3→OKAY;pony선별감축;code REQUEST CHANGES/arch BLOCK(clock경합)→수정후APPROVE/CLEAR;deep REQUEST CHANGES(snapshot경합)→수정후APPROVE;security APPROVE.
- readiness16모듈SQL호출불변,주석/docstring제외code408줄감소. cache/메모리신규기능줄수와별도계상.
- 공식검증은격리사본에서수행. B레인원본pytest/compile편차는 execution-deviation.md에별도기록하고판정에서제외했다. 이후공식B141/전체를격리재실행했다. 원본data/env간접접근전체불변은주장하지않는다.
- runtime Space10/p1,URL http://127.0.0.1:57920. API/LLM/auth/시장자료는합성,제품Memory/History/command/route 및대표4cache SQLite경로는실행한다.

## 최종 실행 결과

- 기준 구현 커밋 **1e159d7**, 제품 소스 이후 변경 없음. 필수 **7/7 통과**, iteration1. 제품 QA 재수정 없음. 하네스 실패·교정은 별도로 보존했다.
- engine UltraQA, lifecycle app-adapted. OMX native 상태를 읽거나 변경하지 않았다. ego-browser 단일 Space10/p1, 전용57920→57921/57922.
- 커밋 후 실제 SQLite/게이트 경계 35개와 fixture HTTP probe, 별도 실제 subprocess3개의 동시 cache/profile/memory 저장을 실행했다. 마지막 JSON을 새 MemoryManager로 복구한 뒤 비교한 것이 아니라, 즉시 SQLite 직접 조회와 비교해 일치했다. cache18행·각 owner profile+메모리7행과 worker 종료·임시dir 삭제를 확인했다.
- 브라우저에서 합성 일반사용자로 설정 profile을 저장(POST /api/kr/chatbot/profile 200), 실제 SSE 명령7개+재진입 view를 실행했다. 일반메모리 출력에는profile 없음, 예약키3조작은설정화면안내, clear 뒤 일반메모리없음과profile 보존을API/설정폼으로대조했다. 실제LLM·원본설정저장·충전·계좌·발송·삭제는실행하지않았다.
- SafeBot은 외부추론 경계다. 명령은제품 command_service와 MemoryManager/SQLite를사용한다. HistoryManager로seed한2메시지의조회/재로드를확인했다. SafeBot이보내는신규명령채팅의대화영속성전체를검증했다고주장하지않는다. `/clear all`은브라우저fixture에서차단하고명시전체초기화호환은임시DB unit으로검증했다.
- CHAT023 추천API는현재frontend직접소비가없다. 실제 route→cache/SQLite probe로검증하며없는동적추천카드UI를검사했다고주장하지않는다. 이캐시정리가일반memory/profile를보존하는효과는B1실제UI와연결했다.
- 대시보드 자료는합성이다. fixture bootstrap에서제품4캐시 save→메모리캐시clear→SQLite get 왕복후얻은payload를실제UI에전달했다. 16개모듈전체의동적회귀는pytest로보강했고,브라우저는대표VCP/종가/누적성과화면이다. 금융계산·실제시세검증은아니다.
- PNG7개를직접열람했다(image-review.json). memory-protected 이미지는예약키거부·초기화를보여주며마지막empty문구하단이일부가려져별도ego-memory-empty-stable.png를완전표시근거로썼다. 1280×900 데스크톱동작검증이며전체디자인/모바일감사주장없음.

## 하네스 실패와 복구

- 사전probe의read-only AppConfig setter 실패는프로세스합성환경주입으로교정했다. 실제키는사용하지않는다.
- profile 저장은정상200/저장완료dialog였다. 즉시모든dialog가닫힐것으로가정한wait가timeout했고,실제확인dialog를닫은뒤설정dialog를닫았다. 중복저장하지않았다. 상태변경후stale ref는새snapshot/semantic locator로교정했다.
- B2 준비중부모가이미있던jongga_status를중복등록해fixture가시작하지못했다. gateway 연결거부13건/HTML502와Sidebar JSON SyntaxError가관측됐다. 제품변경없이중복정의제거,소유fixture만재시작,HTTP200 readiness 확인후같은Space에서B2를다시실행했다. 실패PID99744는자연종료했고그PID에임의kill을하지않았다. 재시작과정의logs/request로그를초기화하지않았다.
- 최초합성누적KPI는S값을A/B/D에도복사해분포가모순되어,실제S거래1건에맞춰다른등급0으로교정했다. 최종이미지와ego-cumulative.json은교정된값이다.
- 가격텍스트가두곳에존재한hover ambiguity와td전체문구를단일종목명으로가정한locator 오류는DOM관측후정확한div대상으로교정했다. 실제제품오류로세지않는다.
- 최종 Next configErrors/sessionErrors/compilation issues는빈목록(next-final-*). favicon404는브라우저기본탐색별도분류. 전체네트워크가처음부터무오류였다고주장하지않는다.

## 요청·정리·절차 편차

- fixture 로그110건: 사전probe19(20017/금지mutation4052), 실측·기동확인91건은모두200. GET외실측은허용된합성chat/profile/read-only quotes만. gateway의연결거부13건은별도request-audit.json에기록되어있다.
- Space10 finish정확히1회,소유PID/cwd/PGID 대조후서버3group종료,57920~57922 listener없음,실행scratch제거·원본venv존속,제품29Git/SHA와사용자packageSHA보존을확인했다. 소유프로세스교체시마다로그와신원을보존했다.
- **절차 편차:** storage_cache_b는원본pytest/compile/import금지지시를어겼다. 그결과는공식검증에서제외하고부모가격리B141및전체를재실행했다. 원본.env/data의간접접근은확인되지않았으므로미접근·전체불변을주장하지않는다. 자료손실이나외부호출발생도근거없이추정하지않는다. 사용자고지와상세명령은execution-deviation.md.

## 이월

- **FE-043**: Sidebar 사용량GET이HTML502를res.json으로읽어발생한SyntaxError. 이번격리원인은하네스기동실패로특정했지만이전운영제보의URL/시각은없어동일원인확정은아니다. 해당호출부의HTTP/비JSON처리는별도후속TODO로등록했다.
- 승인4건은기존18중4완료대상이며,새발견1건을더하면마감후남은TODO는15건이다.

ULTRAQA COMPLETE: Goal met after 1 cycles
