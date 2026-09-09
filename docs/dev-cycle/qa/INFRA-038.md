# UltraQA Report

- item: INFRA-038
- engine: ultraqa
- lifecycle: app-adapted
- phase: cleanup
- iteration: 1
- same_failure_count: 0
- active: true
- cleanup: runtime/credentials complete; workspace removal pending integration
- browser_applicability: required
- browser_driver: agent-browser
- namespace: devcycle-errors-k6-l42b8
- sessions: admin, viewer
- source_commit: 214e996ff2f68b83c6125b15df5f2d8a12ac4a96
- target: http://127.0.0.1:57162/dashboard/kr, /dashboard/data-status → Flask127.0.0.1:57161
- updated: 2026-09-09T11:25:48.706186

목표는 HTTP 요청 오류와 서버 장애를 구분하고, 지정 오류 응답에서 내부 경로·예외 종류를 제거하는 것이다. 실제 Next UI/proxy/env 중계와 실제 Flask create_app·요청 컨텍스트·오류 처리기를 사용했다. 스케줄러 기동과 비대상 조회만 fixture로 대체했다. env 읽기 실패는 실제 reader 경계에서 주입했고 전역 오류는 실제 factory의 테스트 before_request에서 발생시켰다. API 응답을 브라우저 mock으로 바꾸지 않았다.

| ID | 의도·사용자/공격자 | setup·명령/하네스 | 기대 신호 | 실제 결과 | 수정 | 증거 | cleanup | 필수 |
|---|---|---|---|---|---|---|---|---|
| N1 | 관리자 정상조회 | 실제 Next 설정 모달 열기 | GET200·기존마스킹 | PASS: 200·마스킹 확인 | 아래 기록 | settings-normal.png; requests.jsonl.gz | 런타임 완료 | 필수 |
| A1 | 관리자: env 읽기 경계 OSError | fixture-control env_read_error 후 실제 모달 재진입 | GET500 고정error·UI경로비노출 | PASS: 500 {error:Internal Server Error}, UI는 기존대로 빈필드; 경로없음 | 아래 기록 | settings-fault.json; settings-fault.png | 런타임 완료 | 필수 |
| A2 | 공격자: 내부경로/지시문 canary | 실제 데이터 상태 화면 조회에 RuntimeError 주입 | 500 fixed error/message·type/원문비노출·내부로그 원인유지 | PASS: 500 고정본문, 콘솔도고정문구; 내부로그원인존재 | 아래 기록 | data-runtime.json; data-runtime.png; data_case.py.gz | 런타임 완료 | 필수 |
| A3 | 정상복구와 비관리자 | 주입해제후모달재진입; viewer설정 및API조회 | 200복구·viewer403/관리자탭없음 | PASS: 200복구, viewer403, 관리자탭없음; 데이터상태200복구 | 아래 기록 | settings-recovered.json; settings-recovered.png; settings-viewer.json; settings-viewer.png; viewer-env-probe.json; data-normal.json | 런타임 완료 | 필수 |

## 명령과 증거

증거 기준 디렉터리: `../evidence/http-errors-2026-09-09/`. 명령별 실제 인자·cwd·timeout·exit·소요시간은 각 JSON, 전체 출력은 log.gz에 남겼다.

- `python3 verify.py pytest-baseline`: exit0,2220passed/3skipped.
- `python3 verify.py pytest-017-red ...`: exit1,6failed/2passed로 기존400/404/405/429→500 재현.
- `python3 verify.py pytest-017-green ...`: exit0,43passed.
- `python3 verify.py pytest-038-red ...`: exit1,3failed/21passed로 원문 노출 재현.
- `python3 verify.py pytest-wrapper-red ...`: exit1,2failed로 wrapper400/415→500 재현.
- `python3 verify.py pytest-errors-v2-full`: exit0,2232passed/3skipped. 기존 제외3건 유지.
- `python3 verify.py vitest-baseline`: exit0,405passed/58files; 실제 next build와 타입 스모크 포함. frontend 변경이 없어 같은 실행 증거를 재사용했다.
- `python3 verify.py typecheck-errors`, `lint-errors`: exit0; 린트0errors/기존204warnings.
- `probe_errors.py`: exit0,브라우저HTTP10종 모두통과; routing critical 로그없음.
- `ui_driver.py admin settings`, `ui_case.py` fault/recovered/viewer, `data_case.py` missing/runtime/normal: 각exit0. 실제 최신 snapshot ref로 설정 버튼·탭을 클릭했다. 스크린샷7장을 저장 후 모두 열어 확인했다.
- 프로세스당 검증480초·브라우저명령60초로 제한했다. 원본3500/5501/live 요청은 금지했고 외부 네트워크는 sandbox/deny proxy로 차단했다.

## 발견·수정 및 판정

ponytail APPROVE, 독립 code-reviewer APPROVE. architect v1 BLOCK은 공통 wrapper가 HTTPException을 먼저 삼키는 경로였다. 400/415 RED 후 type-only WARNING과 raise로 보완하고 v2 코드/ponytail APPROVE, architect CLEAR를 받았다. 이 수정은 동적 QA 시작 전이므로 QA iteration은1이다. LSP의 Transport closed는 미실행이며 성공으로 세지 않았다. AST·실제 pytest·타입/빌드 검증은 별도로 통과했다.

동적 QA 제품 실패0. data-missing과 data-runtime의 콘솔에는 각각 예상404/500 오류가 React dev에서2번씩 기록되며, page error는0이다. 복구 후 콘솔 오류0. expected 오류를 숨기거나 일반오류0으로 보고하지 않았다. 응답내 canary0, 브라우저/공개static 포함64개 산출물의 fake 비밀값 일치0.

설정 읽기 실패의 사용자용 안내가 없는 기존 UI는 변경하지 않았다. HTTPException의 명시적 응답은 원래 본문·헤더를 유지한다. 다른 개별라우트의 독자 오류 빌더는 이번 두 항목 범위 밖이며 INFRA-066으로 이월한다. 지시문 canary는 데이터로만 취급했다. 제품에 cancel/resume API가 없어 해당 분류는 비적용; 작업의 재개·cleanup 상태는 이 문서와 source hash로 관리했다.

## 정리와 잔여 작업

자신의 브라우저2개·Next/Flask·deny proxy 종료, namespace·fake env/쿠키/프로필 삭제 완료. 원본 package.json은보존. 독립clone 삭제와 완료 아카이브만 남았다. `.omx` hook 상태 명령은 실행하지 않은 App 대응이다.

필수4/4 PASS. 작업공간 정리 전에는 COMPLETE로 표시하지 않는다.
