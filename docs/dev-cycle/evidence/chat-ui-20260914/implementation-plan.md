# 챗봇 UI·삭제 처리 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans for remaining implementation tasks. Do not repeat completed work.

**Goal:** CHAT-019·010·020의 겹침·초점·삭제 실패/경합을 고치고 실제 화면으로 검증한다.

**Architecture:** 기존 컴포넌트와 이벤트를 유지한다. VCP의 세 삭제 진입점은 작은 로컬 처리 경로를 공유하고 응답과 캡처한 종목/세션 일치를 확인한 뒤 UI를 변경한다. 백엔드 계약과 저장소 스키마는 변경하지 않는다.

**Tech Stack:** 설치된 React19/Next16.3, Vitest/pytest, 실제 앱+합성 Flask fixture.

**Spec:** scope.md 및 사용자의 세 항목 bounded 설계 `승인`.

## 시점과 범위

처음에는 T2 묶음으로 예상했으나, 세 항목의 실제 production diff 합계가300줄을 넘어 T3로 높였다. 이 계획은 구현 이후 범위 재판정 시점의 보강 기록이며 사전에 쓴 것처럼 표시하지 않는다. 기능 범위는 승인안과 같다. 아래 완료 체크는 raw RED와 source diff로 확인한 진행이며 최종 승인/QA완료를 뜻하지 않는다.

## Tasks

### 1. CHAT-019·010
- [x] 기존 회귀를 참조한 신규검사6개 작성 → 격리 RED6/6 확인.
- [x] chatbot/page.tsx의 툴바·명령목록을 정상 흐름으로 배치하고 높이 제한, 실제 삭제설명으로 수정. ChatWidget설명도맞춤.
- [x] drawer mediaquery, inert, 닫기/refocus 및 Escape를 기존 state경로에 연결.
- [x] 문구누락1회수정후격리6/6확인. 실제baseline에서겹침/숨은Tab/모바일왕복메뉴재등장확인.
- [ ] 3개viewport와키보드·리사이즈·명령목록을최종source로실측.

### 2. CHAT-020
- [x] page.regression-chat-020.test.tsx4개 작성,부모격리RED4/4확인.
- [x] VCPpage 세DELETE경로를 공통 처리. 성공후UI반영,404 GET재조회,다른오류메시지보존.
- [x] 캡처ticker/session/open상태와pending중복가드로늦은응답격리.
- [ ] 격리GREEN 및성공/실패/404변형/지연종목전환 실측.

### 3. 공유 검수·마감
- [x] gitarchive사본,원본쓰기/외부network차단,합성VCP2종목/실제HistoryManager fixture 준비.
- [x] 백엔드전체pytest실행(수정은프론트엔드한정).
- [ ] critic 계획검토→ponytail→독립code-reviewer/architect→T3 review.
- [x] frontend 1차 전체검사 실행: vitest.json/log exit1(기존15건matchMedia부재),typecheck.json/log exit2(신규test HTMLElement/MediaQueryList/DOMmatcher타입),build.json/log exit1(동일타입오류),lint exit0.
- [ ] jsdom의실제브라우저API부재를공용테스트설정으로보완하고신규test타입을정확히수정한다. productguard/타입억제/기대값완화로실패를숨기지않는다.
- [ ] 영향받는ponytail/code-reviewer/architect/T3 review를최종소스해시로실행하고전체Vitest·lint·typecheck·build를재실행한다. 본단계실패면첫커밋/QA진입불가.
- [ ] Next MCP/브라우저검사. 정적통과→첫구현커밋→QA→정리→완료아카이브순서유지.
- [ ] QA행렬8행 및기준소스첫커밋. 사용자rootpackage제외하고cachedcheck0확인.
- [ ] UltraQA App대응 최대5회/동일실패3회. source/dirty/소유프로세스정리증거가모두통과한항목만완료아카이브.

## Constraints

원본3500/5501/live접근·재시작, 실제 .env/data복사/쓰기, LLM/발송/거래/설정저장/삭제 금지. 합성scratch안에서만데이터변경. 새의존성/타입억제/스키마변경/무관리팩터링금지. 추가리뷰는읽기전용이고지원불가를성공으로표시하지않는다.

VCP executor의원본단일테스트실행위반은execution-deviation.md에남겼으며더이상실행을위임하지않는다. 부모격리결과만검증증거로쓴다.

## 읽은 프론트엔드 기준

- frontend-skills.md, frontend/AGENTS.md.
- Next16.3 번들 02-project-structure.md,03-layouts-and-pages.md,05-server-and-client-components.md,06-fetching-data.md,07-mutating-data.md. 기존클라이언트페이지경계와라우트위치는유지한다.
- vercel-react-best-practices: useEffect의미디어쿼리/Escape리스너해제,안정콜백과기존state재사용확인. 새의존성/캐시체계없음.
- QA8행필수성은그대로다. 위1차실패는계획작성뒤실행에서발견해기록을갱신했다. 개별GREEN만으로전체PASS라하지않는다.

## 독립 리뷰 차단 후 보강

- [x] 실제최초대화에서UI질문삭제가DB답변삭제임을확인, vcp-red-index로재현.
- [x] 중첩모달Escape동시닫힘을chat-red-nested로재현.
- [ ] UI삭제대상을ticker/session/generation/serverIndex와결속한다. 합성환영문구는서버index를갖지않는다. 전환/초기조회/스트리밍동안일치하지않는행위차단.
- [ ] 3진입점공통pending보호와확인모달소유권,오래된GET/SSE쓰기무효화를회귀로고정.
- [ ] 상위모달이열려있으면drawerEscape가반응하지않게하고nested회귀실행.
- [ ] 최종해시로전검사·ponytail·독립2레인·T3심층검토후첫커밋및QA8행수행.

## 메시지 정합성 구현 후 검증 보완

vitest-fixed에서4실패가발생했다. 3건은테스트의randomUUID반환값(접미사)을전체session_id로기대한fixture오류로, 실제클라이언트기존vcp_<ticker>_접두사와불일치했다. 실제UI/서버대조에서잘못된메시지삭제는이미확정됐으므로이fixture수정이그결함의재현을대체하지않는다. 명시적인서버session_id프레임으로배정/삭제대상을검증한다. 나머지1건은미확정메시지삭제버튼을숨기는새보호계약에따라존재/비활성검사를구분한다. typecheck-fixed의undefined/null불일치1건도보완후전체재실행한다.

## 최종 검사 실행 순서 보정

release에서독립tsc와next build를병렬실행해.next/types재생성중TS6053이발생했다. build자체의후속tsc는통과했으며,명시적tsc도build종료후직렬실행한typecheck-after-build에서exit0을확인했다. 이실패는제품소스수정으로숨기지않고실행순서를보정했다. 이후build/dev와독립typecheck를겹쳐실행하지않는다.
