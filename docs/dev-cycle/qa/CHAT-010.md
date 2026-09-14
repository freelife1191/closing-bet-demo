# UltraQA Report

- 항목: CHAT-010 (CHAT-019·010·020 공유 행렬)
- engine: ultraqa | lifecycle: app-adapted | phase: qa-retry | iteration: 2 | same_failure_count: 1
- browser_applicability: required | browser_driver: agent-browser
- 기준: 정적 검증과 첫 커밋 후 qa-source.json에 고정. 현재 설계 승인 후 구현 준비.
- 대상: http://127.0.0.1:57601/chatbot 및 /dashboard/kr/vcp → 격리 Flask57602.
- 완료 기준: 필수8/8, 정적 검사, 독립 리뷰, 소유 환경 정리. 최대5회/동일실패3회.
- 안전: 원본3500/5501/live/.env/data쓰기·실제LLM/발송/거래/설정저장/삭제 없음. gitarchive와 합성 세션에서만 조작한다. 실제 사용자 로그인 세션을 재사용하지 않는다.

| ID | 의도·모델 | setup·조작/harness | 기대 신호 | 실제·수정·증거 | 정리 | 필수 |
|---|---|---|---|---|---|---|
| S-1 | 작은 화면 사용자 | 1280×577·1440×900·375×812 실제 /chatbot, 빈화면/슬래시팝업 | 카드·빠른조회·명령문구가 겹치지 않고 모두 읽힘, 필요시 정상스크롤 | 미실행 | 전용브라우저 | 예 |
| S-2 | 키보드 사용자 | 모바일서랍 열기·내비접기·Tab·닫기·항목선택 | 접힌 링크가탭에서제외, 닫힌뒤열기버튼초점. 서랍 위 확인모달 Escape는 모달만, 다음Escape는서랍닫힘 | 미실행 | 전용브라우저 | 예 |
| S-3 | 창 크기 변경 사용자 | desktop→mobile, mobile열기→desktop→mobile 및초기모바일 | 남은overlay없음, 메뉴를열어정상사용 | 미실행 | 전용브라우저 | 예 |
| S-4 | VCP 메시지삭제 사용자 | 실제 UI 성공/500/404+세션유효/404+세션없음 | 첫세션welcome/user/model UI와서버user/model인덱스대조후선택메시지만삭제. 실패내용보존+오류, 유효세션유지+재조회, 죽은key정리 | 미실행 | 합성세션 | 예 |
| S-5 | 대화삭제 사용자 | 실제삭제확인→합성200/404/500 | 성공·사라진세션복구, 500기록보존·오류 | 미실행 | 합성세션 | 예 |
| S-6 | /clear 사용자 | 실제입력명령→합성200/404/500 | 대화삭제와동일계약, 연타/교차호출DELETE1회, 실제명령설명과일치 | 미실행 | 합성세션 | 예 |
| S-7 | 빠른종목전환 사용자 | 지연DELETE중다른종목선택·닫기·재진입 | 늦은응답이현재종목/새세션key/메시지오염안함. 초기GET/전송중삭제와늦은SSE도보호 | 미실행 | 지연fixture종료 | 예 |
| S-8 | 경계/증거/정리 | raw결과·NextMCP·console·rootpackage/source/data목록SHA,프로세스확인 | 숨은실패없음, 사용자파일불변, 소유환경제거 | 미실행 | scratch/browser/server | 예 |

- 정상 경로와 HTTP 오류·stale 메시지/세션·중복/지연 응답을 검사한다. 별도 CLI 플래그·경로 파서·외부 LLM 지시 실행은 이번 UI 변경에 해당하지 않는다. 합성 응답/문구는 자료이며 검증 생략 등의 지시를 따르지 않는다.
- 각 CLI/브라우저 호출은 timeout으로 제한한다. 실제 파일/프로세스 소유 범위만 정리한다.
- 단위검사만으로 UI 실측을 대체하지 않는다. DOM/요청/스크린샷과 실제열람을 연결한다.
- 현재 결과: 미실행. 완료 불가.

## 검토/구현 중 추가 재현
- 첫대화후질문삭제가답변을삭제함: preflight-history-before/after.json. client-only환영문구와서버배열의index불일치. vcp-red-index1실패4통과.
- drawer+확인모달 Escape가둘다닫힘: chat-red-nested1실패6통과. 이행위도S-2필수에포함.
- 독립리뷰가공통pending/스트리밍/전환이력결속경계미완성을차단. source수정/회귀/독립재검토후QA한다.
- 위관찰은첫QA커밋전구현검증이며최종QA통과로세지않는다. preflight소유브라우저/서버종료.

- 정적검증: pytest2296/3skip,Vitest487/69,typecheck-after-build0,lint0error190,build3/3. 독립검토전부통과(T3포함), 실제QA는다음단계.

- QA 기준 커밋: b86358f00b56c536cad17dd4db9d149d1a408a60

## UltraQA iteration 1 결과와 수정

S1/S3 및 VCP S4~S7은실제UI/HTTP/저장이력대조통과. S2는native Escape로상위확인모달과서랍이함께닫혀실패했다(layout-qa/report.md). 원본unit dispatchEvent에서는안보였으나리스너사이에React상태를flush하는회귀variant에서동일하게실패했다(chat-red-browser-escape.log). window Escape검사를capture단계로옮겨상위dialog닫힘처리전에가드를판정한다. 수정후chat-capture-fixed8/8통과. 영향리뷰/전체정적검사후QA2에서S2와인접S3를재검증한다. 기존S1/S4~S7의소스기능은변경없으며증거를보존한다.

하네스보완: VCP전체삭제버튼은외부FontAwesome CSS차단환경에서0×0으로확인되어실제키보드focus+Enter로활성화했다. 전송버튼의pointer가가려지는경우는별도기존FE-010의floatingwidget겹침이며지원되는Enter전송을썼다. 스크립트상태나DOM을강제로바꿔성공처리하지않았다.

## UltraQA iteration 2 계획

수정 범위는 window Escape capture와 재현 테스트 두 파일이다. 최신 정적 검사: Vitest 488/69, lint 0오류/190경고, build 3/3, build 후 typecheck exit 0. S-2 전체와 S-3 인접 흐름을 실제 브라우저에서 재실행한다. S-1 및 S-4~7은 iteration 1 증거를 유지하되 VCP 소스 불변과 레이아웃 변경 없음에 한해 재사용한다. S-8은 현재 소스·오류·정리 결과로 최종 판정한다. 아직 완료 아님.
