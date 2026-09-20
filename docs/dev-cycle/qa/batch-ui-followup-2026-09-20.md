# UltraQA Report — UI follow-up 7건

- Goal: 승인7건 실제 화면/응답 계약·오류·모바일·회귀 검증.
- engine: Codex UltraQA App 대응 (native OMX 상태 호출 없음)
- phase: COMPLETE. iteration: 1. baseline: 통과.
- lifecycle: app-adapted | same_failure_count: 0 (제품 실패 없음, 하네스 진단은 별도 기록)
- browser_applicability: required. browser_driver: ego-browser (사용자 명시 선택).
- URL: http://127.0.0.1:57720 (소유 gateway →57721 Next /57722 합성API).
- 안전: 원본3500/5501/live·실제.env/data 금지, 실제 인증/LLM/수집/매매/발송/삭제/저장 금지.
- 제한: 명령300초 이내, QA5회/동일실패3회. 필수미통과 시 TODO유지. fixture POST는 합성 갱신 결과/제어/가격조회만 허용.
- 상세 baseline 명령/exit는 evidence/ui-followup-20260920/*.json/log. 처음 sandbox 구문오류 exit65는 제품실패와 구분하며 보존.

| ID | 의도/모델 | setup·command/harness | 기대 신호 | 실제 결과·수정·증거 | cleanup | 필수 |
|---|---|---|---|---|---|---|
| R1 | 일반사용자/갱신실패 | admin KR화면, 합성500/HTML/network/timeout 후 갱신·재시도 | 사용자 오류표시·spinner종료·성공시해제 | PASS — error500/HTML500/network 차단 모두 화면 오류·버튼 복구. timeout10144ms, 성공 재시도 오류 해제. ego-r1-errors-retry.json, ego-r1-network-timeout.json, ego-r1-timeout.png. Next 예상 console5건은 next-errors-r1.txt. | 정리 완료 (cleanup.json) | 예 |
| R2 | 권한만료 | 합성403 갱신 | 안내 및 관리자조작 숨김, 실제쓰기0 | PASS — 403 안내 dialog, 갱신 버튼2개 숨김. ego-r2-forbidden.json/png. 설정 저장·권한 변경 실행 없음. | 정리 완료 (cleanup.json) | 예 |
| H1 | 검색제거/채팅접근 | 375/900/1280 헤더·AI상담 open/close | 가짜검색/⌘K 없음, 메뉴/설정/채팅 작동 | PASS — 검색/⌘K 없음, 설정 open/close·메뉴 이동·채팅 open/close. Chat 모바일 닫기 후 focus=AI 상담. / 데스크톱 launcher z120·hit true·닫힘. ego-h1-actions.json, ego-h1-mobile-stable.json, ego-h1-menu.json, ego-h1-home.json 및 stable PNG. | 정리 완료 (cleanup.json) | 예 |
| H2 | 화면가림 | VCP/종가/누적성과/데이터상태 스크롤중/끝 | 필터·마지막셀·카드본문과닫힌launcher 중첩0 | PASS — 네 화면375/900/1280에서 launcher y14..50, 지정 본문/마지막셀과 겹침0. 종가900 controls6개 hit true 및 조회버튼 실제 클릭. ego-p1-history-h2.json, ego-h2-closing-edges.json, ego-a1-h2-vcp.json, ego-h2-cumulative-status.json 및 PNG. | 정리 완료 (cleanup.json) | 예 |
| J1 | 거짓차트/좁은화면 | 두종목카드·확대 차트375·가로스크롤 | 고정polyline없음, 실제700px차트 축읽힘/외부링크 | PASS — 고정polyline0. 375px에서700px 원본 이미지·client341/scroll732, ArrowRight scrollLeft0→7, wheel→391(끝). ego-jongga-contract.json, ego-j1-viewport-keyboard.json, ego-j1-chart.json/png. | 정리 완료 (cleanup.json) | 예 |
| J2 | 이미지실패/인접 | 이미지실패·기간전환 | 다른종목대체없음, 실패안내·외부링크 유지 | PASS — 주봉이미지 차단 시 다른 종목 대체 없이 안내/외부링크2개, 일봉 선택 후700px이미지 복구. ego-j2-image.json/png. | 정리 완료 (cleanup.json) | 예 |
| A1 | 모순/stale AI | 새topHOLD/옛nestedBUY 실제Python 변환·카드·분석표시 | 새판정/new reason/0확신도 일치, 입력불변 | PASS — 카드/실제Python변환응답/VCP Gemini 모두 새HOLD·confidence0·새사유. ego-jongga-contract.json, ego-a1-response.json, ego-a1-h2-vcp.json, ego-a1-vcp-gemini.png. | 정리 완료 (cleanup.json) | 예 |
| A2 | 잘못된/legacy AI | 빈/malformed/문자사유/누락값 | 명시한fallback순서·crash없음·지시문은자료 | PASS — 객체reason/model/confidence 제거 후 API는actionBUY만; VCP2행 유지/Gemini는값없음. 검증 문자열의script와완료지시는글자로표시, 실행sentinel false/script노드없음. 정상모드복구. ego-a2-malformed.json/png 및 fixture-probe. | 정리 완료 (cleanup.json) | 예 |
| P1 | 가격출처 | 최신 current≠entry·역사·매수시세성공/실패/10초timeout | 날짜/표시가격 일치·조회성공을실시간으로과장안함 | PASS — 최신/18일 이력3타일 모두 entry와날짜일치(75200/183500/217000), 역사매수비활성. 모달184500원 조회값/저장값 출처구분, timeout10129ms 후fallback. ego-p1-history-h2.json, ego-p1-buy.json 및 PNG. | 정리 완료 (cleanup.json) | 예 |
| P2 | 기간변경/반복 | 모의투자 차트3개월→1개월 | history days90/30 추가, portfolio GET 증가0 | PASS — 3개월/1개월에서 asset days90/30만 추가, portfolio HTTP누적4→4→4. 초기365요청2회는개발모드동작이며제거됐다고주장하지않음. ego-p2-requests.json/png. | 정리 완료 (cleanup.json) | 예 |
| S1 | 격리·증거무결성 | source SHA/요청로그/Next진단/package/cleanup대조 | 실제효과0, 새오류0, 소유환경종료·사용자파일불변 | PASS — 정리·무결성 확인 완료 — source24일치, package보존, Next errors/compilation빈목록, 요청279개 중 예상5오류만·unsafe0. request-audit.json, next-final-get_errors.txt, next-final-get_compilation_issues.txt. 최종요청279건 재집계 완료. | 정리 완료 (cleanup.json) | 예 |

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

## 브라우저 실행 결과 — 완료

- 기준 코드: d1163eb. 제품 소스 수정 없이 ego-browser TaskSpace5/p1에서 수행했다.
- 필수 행 R1~S1 11/11 통과. 소유 브라우저·서버·임시 사본 정리와 최종 요청 대조까지 완료했다.
- 모든 PASS용 스크린샷을 view_image로 직접 열람했다(image-review.json). 차트의 외부 네이버 이미지는 가독성만 검증했으며 합성 시세와 가격을 대조하지 않았다.
- HTTP/계정/가격/자료는 합성이다. A1/A2는 실제 Python 추출·정규화·응답 변환기를 함께 실행했다. 실제 수집·LLM·인증·거래·삭제·발송·설정 저장은 수행하지 않았다.
- 본문 정체 timeout은 표준 Response/ReadableStream 회귀로 검증했다. 브라우저 timeout 행은 합성 응답 지연을 이용해 실제10초중단과화면fallback을 확인했다.

### 하네스 진단과 관측의 한계

- ego의 이름 없는 role locator를 CSS로 교체했다. 네트워크 차단은 finally에서 해제했고 실제 오류 안내와 Next 오류를 보존했다.
- 최초 모바일 header/chat 캡처는 resize/fade 중간 프레임이었다. 원본을 보존하고 stable 파일만 시각 PASS에 사용했다.
- 첫 종목 DOM probe는 h3를 가정했고 이후에는 카드 상단만 읽어 AI본문을 놓쳤다. 실제 h2 및 관측된 부모 범위로 수정한 ego-jongga-contract.json이 통과 근거다.
- 키보드 스크롤 진단 중 viewport가2727px/region894px로 돌아가 스크롤 여유가 없음을 확인했다. 이후 매 호출에서375px와실제client/scroll폭을 확인했고 동일 high-level ArrowRight가 작동했다. 제품에 수동스크롤코드를 재도입하지 않았다. 진단용window변수/listener는제거했다.
- 가운데점 hit-test의 최초 대상은 화면 하단에 일부만 보였다. 네이티브 스크롤로 전체대상을보이게한뒤 다시 측정했다. chatOverlap은처음에도false였다.
- 설정창의 open/close는 확인했지만 activeElement의 aria-label은null이었다. 이를 설정창 초점반환 PASS 근거로 삼지 않는다. FE010의 Chat launcher 초점반환은별도확인했다.
- 예전 발생 위치가 미확정인 운영 JSON 오류의 원인은 이번 합성 검증으로 확정하지 않았다.

### 검증 및 리뷰 보완 이력

초기 API/상태/가격 누락과 테스트 selector/import/fake-timer 보완, sandbox IPC 및 캐시 문제는 ledger.md와원시실패로그(.log.gz)에보존했다. 기존테스트는변경계약에맞게준비조건/범위를옮겼으며삭제하거나기대를낮추지않았다. 네이티브스크롤을미러한신규검사만실제키보드실측으로대체했다.

### 요청 및 오류 분류

request-audit.json은 합성 API 로그의집계다. Gateway에서는브라우저기본favicon.ico탐색404와의도한갱신취소뒤upstreamTimeoutError도관측됐다. 둘은합성API의예상500/403/503 및브라우저차단/abort와구분한다. 앱필수데이터의미구성경로404는없었고, 최종Next configErrors/sessionErrors/compilation issues는빈목록이다. 원문gateway/fixture로그도보존한다.

## 정리 및 최종 판정

- cleanup.json: Space5/p1 finish 1회, 소유 PID/cwd/PGID 대조 후 3개 그룹 종료, 57720/57721/57722 listener 없음, 임시 사본 제거·원본 venv 존속.
- 동결 소스 24/24와 d1163eb Git 객체 24/24 일치, 사용자 package.json SHA 보존. 원본 data 전체 내용 불변을 조사하거나 주장하지 않았다.
- 종료 후 요청 로그 279건 재집계: 예상 오류 5건, unsafe mutations 0, unexpected failures 0. 런타임 로그 압축 전 SHA는 cleanup.json에 보존했다.
- 필수 시나리오: 통과 11 / 전체 11. 미통과 필수: 없음. 새 이월: 없음.
