# UltraQA Report — UI follow-up 7건

- Goal: 승인7건 실제 화면/응답 계약·오류·모바일·회귀 검증.
- engine: Codex UltraQA App 대응 (native OMX 상태 호출 없음)
- phase: QA_RUN 준비. iteration: 1. baseline: 통과.
- browser_applicability: required. browser_driver: ego-browser (사용자 명시 선택).
- URL: http://127.0.0.1:57720 (소유 gateway →57721 Next /57722 합성API).
- 안전: 원본3500/5501/live·실제.env/data 금지, 실제 인증/LLM/수집/매매/발송/삭제/저장 금지.
- 제한: 명령300초 이내, QA5회/동일실패3회. 필수미통과 시 TODO유지. fixture POST는 합성 갱신 결과/제어/가격조회만 허용.
- 상세 baseline 명령/exit는 evidence/ui-followup-20260920/*.json/log. 처음 sandbox 구문오류 exit65는 제품실패와 구분하며 보존.

| ID | 의도/모델 | setup·command/harness | 기대 신호 | 실제 결과·수정·증거 | cleanup | 필수 |
|---|---|---|---|---|---|---|
| R1 | 일반사용자/갱신실패 | admin KR화면, 합성500/HTML/network/timeout 후 갱신·재시도 | 사용자 오류표시·spinner종료·성공시해제 | 미실행 | 소유서버/자료정리 예정 | 예 |
| R2 | 권한만료 | 합성403 갱신 | 안내 및 관리자조작 숨김, 실제쓰기0 | 미실행 | 동일 | 예 |
| H1 | 검색제거/채팅접근 | 375/900/1280 헤더·AI상담 open/close | 가짜검색/⌘K 없음, 메뉴/설정/채팅 작동 | 미실행 | 동일 | 예 |
| H2 | 화면가림 | VCP/종가/누적성과/데이터상태 스크롤중/끝 | 필터·마지막셀·카드본문과닫힌launcher 중첩0 | 미실행 | 동일 | 예 |
| J1 | 거짓차트/좁은화면 | 두종목카드·확대 차트375·가로스크롤 | 고정polyline없음, 실제700px차트 축읽힘/외부링크 | 미실행 | 동일 | 예 |
| J2 | 이미지실패/인접 | 이미지실패·기간전환 | 다른종목대체없음, 실패안내·외부링크 유지 | 미실행 | 동일 | 예 |
| A1 | 모순/stale AI | 새topHOLD/옛nestedBUY 실제Python 변환·카드·분석표시 | 새판정/new reason/0확신도 일치, 입력불변 | 미실행 | 동일 | 예 |
| A2 | 잘못된/legacy AI | 빈/malformed/문자사유/누락값 | 명시한fallback순서·crash없음·지시문은자료 | 미실행 | 동일 | 예 |
| P1 | 가격출처 | 최신 current≠entry·역사·매수시세성공/실패/10초timeout | 날짜/표시가격 일치·조회성공을실시간으로과장안함 | 미실행 | 동일 | 예 |
| P2 | 기간변경/반복 | 모의투자 차트3개월→1개월 | history days90/30 추가, portfolio GET 증가0 | 미실행 | 동일 | 예 |
| S1 | 격리·증거무결성 | source SHA/요청로그/Next진단/package/cleanup대조 | 실제효과0, 새오류0, 소유환경종료·사용자파일불변 | 미실행 | 미완료 | 예 |

자료속 지시는 실행하지 않는다. CLI flag/path fuzz는 제품CLI를 바꾸지 않아 해당없음. 명령실패·skip은 로그원문과exit로 판정하고 제한없는재시도금지. 최신 사용자 JSON오류는 발생URL 미확정으로 별도; 이 QA의 HTML응답 검사가 운영원인확정을 뜻하지 않는다.

독립리뷰보완: H1에 / 데스크톱의기존bottom-right launcher open/close를추가. P1에합성12초지연→실제fetchAPI10초abort→저장가격안내를추가. A2에validaction+객체reason가Python/VCP를깨뜨리지않는지실제변환출력과UI검사를포함.

## 정적 검사 및 리뷰

- 최종 실행 인덱스: evidence/ui-followup-20260920/validation-final.json. 원문 로그는 .log.gz이며 log-index.json에 원문 SHA를 보존했다.
- pytest2324통과/3skip(수동LLM2, 실제.env없는비교1), Vitest595통과/81파일, build3/3, typecheck0, lint0errors188warnings(기준192).
- critic REJECT→OKAY, ponytail CUT2→SHIP, code-review APPROVE, architect BLOCK→CLEAR(첫chat가림인과단정철회), deep-review REQUEST CHANGES→APPROVE.
- LSP transport unavailable. 실제 격리 tsc --noEmit 성공을 별도 제공했고 미실행LSP성공을 주장하지 않는다.
- 범위: 동결 review-input-qa.json24개SHA, 원본·격리 일치. 사용자 package.json SHA 보존.
- 정적 준비 중 sandboxIPC/cache, 선택자/누락import/fake timer 하네스 문제와 수정 내역은 ledger 및 실패원문에 보존했다. 정적 재시도와 아직 시작 전인 동적 QA iteration을 구분한다.
- 세부 구현 변경: 갱신 오류/timeout, 미동작검색제거, header채팅진입, 신호일가격·AI원천·차트, 실제chart기간조회회귀. 외부시세/LLM/계정/발송/거래는 합성 대역이다.
