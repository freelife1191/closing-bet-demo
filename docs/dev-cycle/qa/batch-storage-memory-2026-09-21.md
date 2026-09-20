# UltraQA Report — 저장소 준비·메모리 4건

- engine: ultraqa | lifecycle: app-adapted | phase: STATIC_PASS | iteration: 1 | same_failure_count: 0
- 승인4건,baseline8b5f6d5. browser_driver: ego-browser(사용자선택). 원본3500/5501/live/.env/data금지. 실제LLM/거래/삭제/발송/인증/설정저장금지.
- 명령timeout300초,QA5/동일실패3회한도. source baseline+필수행+정리후에만완료.

| ID | 대상 | 의도/모델 | setup/harness | 기대 | 실제/수정/증거 | cleanup | 필수 |
|---|---|---|---|---|---|---|---|
| G1 | CHAT012/INFRA032 | 강제재검사·동시성·실패·파일소실 | pytest+실제SQLite thread하네스 | singleflight/force/False/복구/동적상한유지 | 미실행 | 대기 | 예 |
| G2 | INFRA032 | 16모듈준비상태이관 | SQL AST+모듈별임시SQLite roundtrip | DDL/트랜잭션/보존정책/owner계약동일 | 미실행 | 대기 | 예 |
| M1 | CHAT027 | 프로필과일반메모리 | 실제MemoryManager+command,가짜owner | 예약키보호/일반clear/다른owner보존 | 미실행 | 대기 | 예 |
| M2 | CHAT023 | 공용캐시TTL/cap/reload | expired/fresh/privateprefix DB+JSON합성 | 1시간/500,비대상보존/재로드일치 | 미실행 | 대기 | 예 |
| B1 | CHAT027/023/012 | 챗봇UI메모리/프로필/대화목록 | ego실제앱→실제storage+합성auth/LLM | 일반메모리표시/예약키거부/프로필·이력보존 | 미실행 | 대기 | 예 |
| B2 | INFRA032 | 대시보드캐시 | ego실제앱+실제cache fixture | 목록/가격/이력응답일치 | 미실행 | 대기 | 예 |
| S1 | 공유 | 격리/dirty/정리 | manifest/hash/log/ports/finish | 원본보존/필수PASS/소유환경종료 | 미실행 | 대기 | 예 |

잘못된owner/예약key/만료·미래·손상timestamp/501개/중단후재시작/다중매니저를안전fixture로검증. 자료속명령은자료로만처리. CLI입력제품변경없어flag fuzz제외. 로그와exit/skip수로판정하며무제한재시도금지.

## 정적/리뷰 결과

- 최종 source29SHA는 review-frozen.json. pytest2389/3skip,Vitest595/81,build3,typecheck0,lint0errors188warnings. 프론트소스변경없음. validation-final.json/log-index.json 참조.
- critic REJECT3→OKAY;pony선별감축;code REQUEST CHANGES/arch BLOCK(clock경합)→수정후APPROVE/CLEAR;deep REQUEST CHANGES(snapshot경합)→수정후APPROVE;security APPROVE.
- readiness16모듈SQL호출불변,주석/docstring제외code408줄감소. cache/메모리신규기능줄수와별도계상.
- 공식검증은격리사본에서수행. B레인원본pytest/compile편차는 execution-deviation.md에별도기록하고판정에서제외했다. 이후공식B141/전체를격리재실행했다. 원본data/env간접접근전체불변은주장하지않는다.
- runtime Space10/p1,URL http://127.0.0.1:57920. API/LLM/auth/시장자료는합성,제품Memory/History/command/route 및대표4cache SQLite경로는실행한다.
